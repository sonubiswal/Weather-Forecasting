"""Forecast accountability: save predictions, score them against later observations.

Every time the app fetches new data it saves the 24-hour temperature strip to a
local SQLite database and records the current reading as an "observation". When
the app is opened later, past predictions whose target hour has passed are
matched to the closest observation within ±30 minutes, and standard verification
metrics are computed:

  * MAE   — mean absolute error of the ensemble, in °C
  * RMSE  — root mean squared error, in °C
  * bias  — mean signed error (positive = the forecast ran warm)

The score is compared with two honest baselines:

  * persistence ("tomorrow = today") — the classic naive forecast
  * ECMWF IFS alone — the strongest single physics model in the ensemble

Because the "current" reading is model output rather than a station observation,
these scores measure skill against the same source the app itself uses. This is
a standard meteorological verification pattern (persistence-based verification)
and is reported transparently rather than as ground truth.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

LOGGER = logging.getLogger(__name__)
DB_PATH: Path = Path.home() / ".weather_forecast_history.db"
MATCH_TOLERANCE_MIN = 30
SCORE_WINDOW_DAYS = 30
MIN_SCORED_FOR_DISPLAY = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place TEXT NOT NULL,
    made_at TEXT NOT NULL,
    target_time TEXT NOT NULL,
    horizon_hours REAL NOT NULL,
    predicted_temp REAL NOT NULL,
    model TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pred_place_target
    ON predictions(place, target_time);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    temp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_place_time
    ON observations(place, observed_at);
"""


@dataclass(slots=True)
class Score:
    """Aggregated accuracy metrics for one place over a window of days."""

    place: str
    days: int
    scored: int
    mae: float
    rmse: float
    bias: float
    persistence_mae: float
    ifs_mae: float

    @property
    def gain_over_persistence(self) -> float:
        """Percent improvement vs persistence, or 0 if there is no baseline yet."""
        if self.persistence_mae <= 0:
            return 0.0
        return (self.persistence_mae - self.mae) / self.persistence_mae * 100.0

    @property
    def gain_over_ifs(self) -> float:
        """Percent improvement vs the ECMWF IFS single-model member."""
        if self.ifs_mae <= 0:
            return 0.0
        return (self.ifs_mae - self.mae) / self.ifs_mae * 100.0

    def summary(self) -> str:
        """Return a compact one-line summary suitable for a status bar."""
        if self.scored < MIN_SCORED_FOR_DISPLAY:
            return f"collecting data · {self.scored} matched so far"
        parts = [f"Last {self.days}d · MAE {self.mae:.2f}°C",
                 f"{self.scored} scored"]
        if self.persistence_mae > 0:
            parts.append(f"{self.gain_over_persistence:+.0f}% vs persistence")
        if self.ifs_mae > 0:
            parts.append(f"{self.gain_over_ifs:+.0f}% vs IFS")
        return " · ".join(parts)


def _connect() -> sqlite3.Connection:
    """Open the history database, creating the schema on first use."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def record_observation(place: str, observed_at: datetime, temp: float) -> None:
    """Insert a new observed temperature, de-duplicating by place and hour."""
    hour_start = observed_at.replace(minute=0, second=0, microsecond=0)
    try:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM observations WHERE place = ? AND observed_at = ?",
                (place, hour_start.isoformat()))
            conn.execute(
                "INSERT INTO observations(place, observed_at, temp) VALUES (?, ?, ?)",
                (place, hour_start.isoformat(), float(temp)))
    except sqlite3.Error as exc:
        LOGGER.warning("Could not record observation: %s", exc)


def record_ensemble(place: str, made_at: datetime,
                    hourly: list[tuple[datetime, float]],
                    model: str = "ensemble") -> None:
    """Insert a full 24-hour strip of predictions in one transaction."""
    if not hourly:
        return
    rows = [(place, made_at.isoformat(), t.isoformat(),
             (t - made_at).total_seconds() / 3600.0, float(temp), model)
            for t, temp in hourly]
    try:
        with _connect() as conn:
            conn.executemany(
                "INSERT INTO predictions(place, made_at, target_time, horizon_hours,"
                " predicted_temp, model) VALUES (?, ?, ?, ?, ?, ?)", rows)
    except sqlite3.Error as exc:
        LOGGER.warning("Could not record forecasts: %s", exc)


def _nearest_observation(conn: sqlite3.Connection, place: str,
                         target: datetime) -> float | None:
    """Return the observation closest to *target* within the tolerance window."""
    lower = (target - timedelta(minutes=MATCH_TOLERANCE_MIN)).isoformat()
    upper = (target + timedelta(minutes=MATCH_TOLERANCE_MIN)).isoformat()
    row = conn.execute(
        "SELECT temp FROM observations WHERE place = ? AND observed_at BETWEEN ? AND ?"
        " ORDER BY ABS(julianday(observed_at) - julianday(?)) LIMIT 1",
        (place, lower, upper, target.isoformat())).fetchone()
    return float(row[0]) if row else None


def score(place: str, days: int = SCORE_WINDOW_DAYS) -> Score | None:
    """Compute accuracy metrics for *place* over the last *days*, or None if no data."""
    cutoff = datetime.now() - timedelta(days=days)
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT target_time, predicted_temp, model, made_at FROM predictions"
                " WHERE place = ? AND target_time >= ? ORDER BY target_time",
                (place, cutoff.isoformat())).fetchall()
            errors: list[float] = []
            persistence_errors: list[float] = []
            ifs_errors: list[float] = []
            for target_iso, predicted, model, made_iso in rows:
                target = datetime.fromisoformat(target_iso)
                observed = _nearest_observation(conn, place, target)
                if observed is None:
                    continue
                errors.append(observed - predicted)
                if model == "ecmwf_ifs025":
                    ifs_errors.append(observed - predicted)
                baseline = _nearest_observation(conn, place,
                                                datetime.fromisoformat(made_iso))
                if baseline is not None:
                    persistence_errors.append(observed - baseline)
    except (sqlite3.Error, ValueError) as exc:
        LOGGER.warning("Scoring failed: %s", exc)
        return None

    if not errors:
        return None
    return Score(
        place=place, days=days, scored=len(errors),
        mae=mean(abs(e) for e in errors),
        rmse=(mean(e * e for e in errors)) ** 0.5,
        bias=mean(errors),
        persistence_mae=(mean(abs(e) for e in persistence_errors)
                         if persistence_errors else 0.0),
        ifs_mae=(mean(abs(e) for e in ifs_errors) if ifs_errors else 0.0))