"""Network layer: geocoding, four-model ensemble fetching and persistence."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Final

import requests
from PySide6.QtCore import QObject, QThread, Signal
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)
GEOCODE_URL: Final[str] = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL: Final[str] = "https://api.open-meteo.com/v1/forecast"
#: Four independent systems blended into the ensemble median. The ``aifs`` entry is
#: ECMWF's machine-learning model (AIFS) — a third party's AI model, not ours.
MODELS: Final[dict[str, str]] = {
    "ecmwf_ifs025": "ECMWF IFS (physics)",
    "ecmwf_aifs025_single": "ECMWF AIFS (machine learning)",
    "gfs_seamless": "NOAA GFS", "icon_seamless": "DWD ICON"}
CURRENT_VARS: Final[str] = ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                            "is_day,precipitation,weather_code,pressure_msl,"
                            "wind_speed_10m,wind_direction_10m")
HOURLY_VARS: Final[str] = "temperature_2m,precipitation_probability,weather_code"
DAILY_VARS: Final[str] = ("weather_code,temperature_2m_max,temperature_2m_min,"
                          "precipitation_probability_max,sunrise,sunset")
REQUEST_TIMEOUT: Final[float] = 12.0
RETRY_TOTAL, RETRY_BACKOFF, MAX_WORKERS = 3, 0.6, 4
RETRY_STATUSES: Final[tuple[int, ...]] = (429, 500, 502, 503, 504)
FORECAST_DAYS, HOURLY_WINDOW, DAILY_WINDOW, GEOCODE_COUNT = 6, 24, 5, 10
USER_AGENT: Final[str] = "weather-app/2.0 (+https://open-meteo.com)"
STORE_PATH: Final[Path] = Path.home() / ".weather_forecast.json"
DEFAULT_CITY: Final[str] = "Puri, IN"
Payloads = list[tuple[str, dict[str, Any]]]


class WeatherError(RuntimeError):
    """Raised when a location cannot be resolved or no model returned data."""


@dataclass(slots=True)
class Place:
    """A geocoded location returned by the Open-Meteo geocoding service."""

    name: str; country: str; latitude: float
    longitude: float; timezone: str; population: int

    @property
    def label(self) -> str:
        """Return a display label such as ``Puri, India``."""
        return f"{self.name}, {self.country}" if self.country else self.name


@dataclass(slots=True)
class HourPoint:
    """One hour of the forward-looking strip."""

    time: datetime; temp: float; code: int; precip_prob: float | None
    ifs_temp: float | None = None


@dataclass(slots=True)
class DayPoint:
    """One day of the multi-day outlook."""

    day: date; tmin: float; tmax: float; code: int; precip_prob: float | None


@dataclass(slots=True)
class Snapshot:
    """A resolved, ensemble-aggregated weather view for a single location."""

    place_label: str; latitude: float; longitude: float; timezone: str; is_day: bool
    temp: float; feels_like: float; humidity: float; wind: float; wind_dir: float
    pressure: float; rain: float; code: int; models_ok: int; models_total: int
    spread: float; hourly: list[HourPoint]; daily: list[DayPoint]; fetched_at: datetime
    sunrise: datetime | None = None
    sunset: datetime | None = None
    city_now: datetime | None = None
    degraded: bool = False


def build_session() -> requests.Session:
    """Create a session with bounded retries and exponential backoff."""
    retry = Retry(total=RETRY_TOTAL, backoff_factor=RETRY_BACKOFF,
                  status_forcelist=RETRY_STATUSES, allowed_methods=frozenset({"GET"}))
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=MAX_WORKERS * 2))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def split_query(query: str) -> tuple[str, str | None]:
    """Split ``"City, CC"`` into a city name and an optional ISO country code.

    A two-letter code goes through the dedicated ``countryCode`` parameter, because
    the free-text name would otherwise match a first-level administrative code.
    """
    city, _, qualifier = query.partition(",")
    code = qualifier.strip()
    if len(code) == 2 and code.isalpha():
        return city.strip(), code.upper()
    return query.strip(), None


def geocode(session: requests.Session, query: str) -> Place:
    """Resolve ``query`` (``"Puri, IN"``) to the most populous matching place.

    Args:
        session: Shared HTTP session.
        query: City name, optionally qualified by a country code.

    Returns:
        The most populous matching :class:`Place`.

    Raises:
        WeatherError: If the service is unreachable or nothing matched.
    """
    name, country_code = split_query(query)
    if not name:
        raise WeatherError("Type a city name to search.")
    params: dict[str, Any] = {"name": name, "count": GEOCODE_COUNT, "language": "en",
                              "format": "json"}
    if country_code:
        params["countryCode"] = country_code
    try:
        response = session.get(GEOCODE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        results = (response.json().get("results")) or []
    except requests.RequestException as exc:
        LOGGER.warning("Geocoding request failed: %s", exc)
        raise WeatherError(
            f"Could not reach the location service ({exc.__class__.__name__}).") from exc
    except ValueError as exc:
        LOGGER.warning("Geocoding returned invalid JSON: %s", exc)
        raise WeatherError("The location service returned an unreadable response.") from exc
    if not results:
        raise WeatherError(f'No place matched "{query.strip()}". Try the "City, Country" form.')
    best = max(results, key=lambda row: row.get("population") or 0)
    return Place(name=best.get("name", name), country=best.get("country", ""),
                 latitude=float(best["latitude"]), longitude=float(best["longitude"]),
                 timezone=best.get("timezone", "UTC"),
                 population=int(best.get("population") or 0))


def _values(payloads: Payloads, block: str, variable: str,
            index: int | None = None) -> list[float]:
    # Open-Meteo suffixes each variable with the model name when ``models`` is sent,
    # so both the suffixed and the bare key are tried; a list is indexed instead.
    values: list[float] = []
    for model, payload in payloads:
        section = payload.get(block)
        if not isinstance(section, dict):
            continue
        raw = section.get(f"{variable}_{model}", section.get(variable))
        if isinstance(raw, list):
            raw = raw[index] if index is not None and index < len(raw) else None
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            values.append(float(raw))
    return values


def _axis(payloads: Payloads, block: str) -> list[str]:
    for model, payload in payloads:
        section = payload.get(block)
        raw = section.get(f"time_{model}", section.get("time")) if section else None
        if isinstance(raw, list):
            return [str(item) for item in raw]
    return []


def _string_at(payloads: Payloads, block: str, variable: str,
               index: int) -> str | None:
    """Return a string value (e.g. an ISO timestamp) from any responding payload."""
    for model, payload in payloads:
        section = payload.get(block)
        if not isinstance(section, dict):
            continue
        raw = section.get(f"{variable}_{model}", section.get(variable))
        if isinstance(raw, list) and index < len(raw) and raw[index] is not None:
            return str(raw[index])
    return None


def _ifs_value(payloads: Payloads, block: str, variable: str,
               index: int) -> float | None:
    """Return a single value from the ECMWF IFS payload only, if present."""
    for model, payload in payloads:
        if model != "ecmwf_ifs025":
            continue
        section = payload.get(block)
        if not isinstance(section, dict):
            return None
        raw = section.get(f"{variable}_{model}", section.get(variable))
        if isinstance(raw, list) and index < len(raw) and raw[index] is not None:
            try:
                return float(raw[index])
            except (TypeError, ValueError):
                return None
    return None


def _median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _fetch_model(session: requests.Session, place: Place,
                 model: str) -> dict[str, Any] | None:
    # One model failing must never break the ensemble, so errors return None.
    params = {"latitude": place.latitude, "longitude": place.longitude,
              "current": CURRENT_VARS, "hourly": HOURLY_VARS, "daily": DAILY_VARS,
              "timezone": "auto", "forecast_days": FORECAST_DAYS, "models": model}
    try:
        response = session.get(FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        LOGGER.warning("Model %s unavailable: %s", model, exc)
        return None


def _points(payloads: Payloads) -> tuple[list[HourPoint], list[DayPoint]]:
    hours: list[HourPoint] = []
    stamps = _axis(payloads, "hourly")
    if stamps:
        parsed = [datetime.fromisoformat(stamp) for stamp in stamps]
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        start = next((i for i, moment in enumerate(parsed) if moment >= now), 0)
        for index in range(start, min(start + HOURLY_WINDOW, len(parsed))):
            temp = _median(_values(payloads, "hourly", "temperature_2m", index))
            if temp is None:
                continue
            hours.append(HourPoint(
                parsed[index], temp,
                int(_median(_values(payloads, "hourly", "weather_code", index)) or 0.0),
                _median(_values(payloads, "hourly", "precipitation_probability", index)),
                _ifs_value(payloads, "hourly", "temperature_2m", index)))
    days: list[DayPoint] = []
    for index, stamp in enumerate(_axis(payloads, "daily")[:DAILY_WINDOW]):
        high = _median(_values(payloads, "daily", "temperature_2m_max", index))
        low = _median(_values(payloads, "daily", "temperature_2m_min", index))
        if high is None or low is None:
            continue
        days.append(DayPoint(
            date.fromisoformat(stamp), low, high,
            int(_median(_values(payloads, "daily", "weather_code", index)) or 0.0),
            _median(_values(payloads, "daily", "precipitation_probability_max", index))))
    return hours, days


def _parse_stamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp, tolerating missing or malformed input."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def aggregate(place: Place, payloads: Payloads, fetched_at: datetime) -> Snapshot:
    """Blend every responding model into one median :class:`Snapshot`.

    Args:
        place: The resolved location the payloads describe.
        payloads: ``(model_name, raw_json)`` pairs from the responding models.
        fetched_at: Timestamp to record on the snapshot.

    Returns:
        The ensemble snapshot, before any local calibration is applied.

    Raises:
        WeatherError: If no model supplied a usable temperature.
    """
    if not payloads:
        raise WeatherError("Every forecast model failed. Check your connection.")
    temps = _values(payloads, "current", "temperature_2m")
    if not temps:
        raise WeatherError("Models returned no temperature for this location.")
    feels = _values(payloads, "current", "apparent_temperature") or temps
    hours, days = _points(payloads)
    return Snapshot(
        place_label=place.label, latitude=place.latitude, longitude=place.longitude,
        timezone=str(payloads[0][1].get("timezone", place.timezone)),
        is_day=bool(round(_median(_values(payloads, "current", "is_day")) or 0.0)),
        temp=float(median(temps)), feels_like=float(median(feels)),
        humidity=_median(_values(payloads, "current", "relative_humidity_2m")) or 0.0,
        wind=_median(_values(payloads, "current", "wind_speed_10m")) or 0.0,
        wind_dir=_median(_values(payloads, "current", "wind_direction_10m")) or 0.0,
        pressure=_median(_values(payloads, "current", "pressure_msl")) or 0.0,
        rain=_median(_values(payloads, "current", "precipitation")) or 0.0,
        code=int(round(_median(_values(payloads, "current", "weather_code")) or 0.0)),
        models_ok=len(payloads), models_total=len(MODELS),
        spread=round(max(temps) - min(temps), 1) if len(temps) > 1 else 0.0,
        hourly=hours, daily=days, fetched_at=fetched_at,
        sunrise=_parse_stamp(_string_at(payloads, "daily", "sunrise", 0)),
        sunset=_parse_stamp(_string_at(payloads, "daily", "sunset", 0)),
        city_now=_parse_stamp(str(payloads[0][1].get("current", {}).get("time", ""))))


def build_snapshot(session: requests.Session,
                   place: Place) -> tuple[Place, Payloads, Snapshot]:
    """Query every ensemble model in parallel and aggregate the median.

    Args:
        session: Shared HTTP session with retry handling.
        place: The resolved location to forecast for.

    Returns:
        ``(place, payloads, snapshot)`` — raw payloads are returned so the caller
        can cache them and re-aggregate offline.

    Raises:
        WeatherError: If no model returned usable data.
    """
    payloads: Payloads = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_model, session, place, name): name for name in MODELS}
        for future in as_completed(futures):
            try:
                payload = future.result()
            except Exception as exc:  # one bad model must never break the ensemble
                LOGGER.warning("Model %s raised %s", futures[future], exc)
                continue
            if payload:
                payloads.append((futures[future], payload))
    return place, payloads, aggregate(place, payloads, datetime.now())


def load_store(path: Path = STORE_PATH) -> dict[str, Any]:
    """Load persisted preferences, tolerating a missing or corrupt file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Could not read %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_store(data: dict[str, Any], path: Path = STORE_PATH) -> None:
    """Persist preferences; write failures are logged, never raised."""
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("Could not write %s: %s", path, exc)


def cache_entry(place: Place, payloads: Payloads, fetched_at: datetime) -> dict[str, Any]:
    """Return a JSON-ready cache record for one successful fetch."""
    return {"place": asdict(place), "payloads": payloads,
            "fetched_at": fetched_at.isoformat()}


def read_cache(store: dict[str, Any]) -> tuple[Place, Snapshot] | None:
    """Rebuild the last cached ``(place, snapshot)`` pair, or ``None`` if unusable."""
    cached = store.get("cache")
    if not isinstance(cached, dict):
        return None
    try:
        place = Place(**cached["place"])
        snapshot = aggregate(place, cached["payloads"],
                             datetime.fromisoformat(cached["fetched_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("Discarding unreadable cache: %s", exc)
        return None
    return place, snapshot


def city_bias(data: dict[str, Any], city: str) -> float:
    """Return the stored calibration offset in °C for *city*."""
    try:
        return float((data.get("biases") or {}).get(city.lower(), 0.0))
    except (TypeError, ValueError):
        return 0.0


def set_city_bias(data: dict[str, Any], city: str, value: float) -> None:
    """Store the calibration offset in °C for *city*."""
    biases = data.setdefault("biases", {})
    if isinstance(biases, dict):
        biases[city.lower()] = round(float(value), 2)


class WeatherFetcher(QThread):
    """Background worker that resolves a query and builds an ensemble snapshot.

    Signals:
        resolved: Emitted with the :class:`Place` as soon as geocoding succeeds.
        succeeded: Emitted with ``(place, payloads, snapshot)`` on completion.
        failed: Emitted with a human-readable message when the fetch cannot finish.
    """

    resolved = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, query: str, request_id: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._query = query
        self._request_id = request_id
        self._session = build_session()

    @property
    def request_id(self) -> int:
        """The monotonic id used to drop stale responses."""
        return self._request_id

    def run(self) -> None:
        """Resolve the place, then emit the ensemble snapshot or an error."""
        try:
            place = geocode(self._session, self._query)
        except WeatherError as exc:
            LOGGER.info("Geocoding failed for %r: %s", self._query, exc)
            self.failed.emit(str(exc))
            return
        self.resolved.emit(place)
        try:
            self.succeeded.emit(build_snapshot(self._session, place))
        except WeatherError as exc:
            LOGGER.warning("Ensemble failed for %s: %s", place.label, exc)
            self.failed.emit(str(exc))