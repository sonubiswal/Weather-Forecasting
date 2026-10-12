"""Impact-based advisories and anomaly detection, computed from the snapshot.

Two lightweight, dependency-free features:

  * impact_advisories — turns raw numbers (temp, wind, rain, humidity) into
    plain-language advice for a person: "Take an umbrella", "Heat stress —
    avoid peak hours", "Good day for drying clothes".

  * detect_anomaly — compares today's temperature to the last 7 recorded days
    for the same place, using z-score thresholds. Flags unseasonably warm or
    cool days.

Both rely only on the data the app already has, plus the scoring SQLite file
that stores historical observations.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Final

LOGGER = logging.getLogger(__name__)
DB_PATH: Final[Path] = Path.home() / ".weather_forecast_history.db"
ANOMALY_WINDOW_DAYS: Final[int] = 7
ANOMALY_MIN_SAMPLES: Final[int] = 4
WARM_Z: Final[float] = 1.5
COOL_Z: Final[float] = -1.5


@dataclass(slots=True)
class Advisory:
    """One plain-language advisory: an emoji, a headline, and a detail line."""

    glyph: str
    headline: str
    detail: str
    severity: int = 0  # 0 = info, 1 = caution, 2 = warning


def impact_advisories(temp_c: float, feels_c: float, wind_kmh: float,
                      rain_mm: float, precip_prob: float | None,
                      humidity: float,
                      uv: float | None = None) -> list[Advisory]:
    """Return a ranked list of advisories derived from the current conditions."""
    out: list[Advisory] = []

    # ---- Heat & cold ----
    if feels_c >= 40:
        out.append(Advisory("🥵", "Heat stress warning",
                            f"Feels like {feels_c:.0f}°C. Avoid outdoor work from"
                            f" 12:00–16:00; drink water every 20 min.", severity=2))
    elif feels_c >= 35:
        out.append(Advisory("🌡️", "Hot day",
                            f"Feels like {feels_c:.0f}°C. Prefer shaded routes,"
                            f" carry water.", severity=1))
    if feels_c <= 5:
        out.append(Advisory("🥶", "Cold conditions",
                            f"Feels like {feels_c:.0f}°C. Layer up before going out.",
                            severity=1))

    # ---- Rain ----
    if rain_mm >= 0.5:
        out.append(Advisory("☔", "It's raining now",
                            f"{rain_mm:.1f} mm in the last hour. Carry an umbrella.",
                            severity=1))
    elif precip_prob is not None and precip_prob >= 60:
        out.append(Advisory("🌧️", "Rain likely soon",
                            f"{precip_prob:.0f}% chance in the next hour. Umbrella"
                            f" recommended.", severity=1))
    elif precip_prob is not None and precip_prob >= 30:
        out.append(Advisory("🌦️", "Possible showers",
                            f"{precip_prob:.0f}% chance. Worth keeping an umbrella"
                            f" nearby."))

    # ---- Wind ----
    if wind_kmh >= 60:
        out.append(Advisory("💨", "Strong winds",
                            f"{wind_kmh:.0f} km/h. Secure loose objects; avoid"
                            f" cycling.", severity=2))
    elif wind_kmh >= 35:
        out.append(Advisory("🌬️", "Breezy",
                            f"{wind_kmh:.0f} km/h. Fine for most activities."))

    # ---- Humidity ----
    if humidity >= 85 and temp_c >= 28:
        out.append(Advisory("💧", "Muggy air",
                            f"{humidity:.0f}% humidity is making it feel warmer"
                            f" than it is."))
    elif humidity <= 25 and temp_c >= 30:
        out.append(Advisory("🏜️", "Very dry",
                            f"{humidity:.0f}% humidity. Keep hydrating."))

    # ---- UV ----
    if uv is not None and uv >= 8:
        out.append(Advisory("☀️", "Very high UV",
                            f"UV index {uv:.0f}. Sunscreen, hat, sunglasses.",
                            severity=1))
    elif uv is not None and uv >= 6:
        out.append(Advisory("🕶️", "High UV",
                            f"UV index {uv:.0f}. Consider sunscreen if out long."))

    # ---- Lifestyle hints ----
    if (precip_prob or 0) < 20 and 20 <= temp_c <= 35 and wind_kmh < 20:
        out.append(Advisory("👕", "Good day for drying clothes",
                            "Low rain chance, moderate temperature, light wind."))
    if (precip_prob or 0) < 20 and wind_kmh < 15 and humidity < 80:
        out.append(Advisory("🚶", "Nice weather for a walk",
                            "Comfortable temperature, low wind, low rain risk."))

    return sorted(out, key=lambda a: -a.severity)


@dataclass(slots=True)
class Anomaly:
    """A deviation of the current temperature from recent history."""

    direction: str   # "warm" or "cool"
    delta_c: float
    z_score: float
    samples: int

    @property
    def glyph(self) -> str:
        return "🔥" if self.direction == "warm" else "❄️"

    @property
    def summary(self) -> str:
        word = "warmer" if self.direction == "warm" else "cooler"
        return (f"{self.glyph}  {abs(self.delta_c):.1f}°C {word} than the "
                f"recent {self.samples}-day average")


def detect_anomaly(place: str, current_temp: float,
                   days: int = ANOMALY_WINDOW_DAYS) -> Anomaly | None:
    """Return an Anomaly if the current temperature is unusual for this place."""
    if not DB_PATH.exists():
        return None
    cutoff = (datetime.now() - timedelta(days=days + 1)).isoformat()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT temp, observed_at FROM observations"
                " WHERE place = ? AND observed_at >= ?"
                " ORDER BY observed_at DESC LIMIT 200",
                (place, cutoff)).fetchall()
    except sqlite3.Error as exc:
        LOGGER.warning("Anomaly query failed: %s", exc)
        return None

    # Collapse to one average per calendar day.
    by_day: dict[str, list[float]] = {}
    for temp, iso in rows:
        day = iso[:10]
        by_day.setdefault(day, []).append(float(temp))
    daily = [mean(values) for values in by_day.values()]

    if len(daily) < ANOMALY_MIN_SAMPLES:
        return None

    mu = mean(daily)
    sigma = pstdev(daily) or 0.0
    if sigma < 0.5:  # essentially no variation — not meaningful
        return None

    delta = current_temp - mu
    z = delta / sigma
    if z >= WARM_Z:
        return Anomaly("warm", delta, z, len(daily))
    if z <= COOL_Z:
        return Anomaly("cool", delta, z, len(daily))
    return None