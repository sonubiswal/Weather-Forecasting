"""Thirty-second check: fetch the four-model ensemble, print a summary, optionally open the GUI.

Usage::

    python preview.py                 # ensemble summary for a default city
    python preview.py "Paris, FR"     # summary for another city
    python preview.py --gui           # summary, then launch the desktop app
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from weather_app import theme  # noqa: E402
from weather_app.fetcher import (  # noqa: E402
    MODELS, WeatherError, build_session, build_snapshot, geocode)

def main() -> int:
    """Print the ensemble summary for a city, then optionally launch the desktop app."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = sys.argv[1:]
    city = next((arg for arg in args if not arg.startswith("--")), "Puri, IN")
    session = build_session()
    try:
        place = geocode(session, city)
        _, _, snapshot = build_snapshot(session, place)
    except WeatherError as exc:
        logging.error("Preview fetch failed: %s", exc)
        return 1
    print(f"\n{snapshot.place_label}  ({snapshot.latitude:.3f}, {snapshot.longitude:.3f})")
    print(f"  median temperature : {snapshot.temp:.1f} °C  (spread {snapshot.spread:.1f}°"
          f" across {snapshot.models_ok}/{snapshot.models_total} models)")
    print(f"  feels like         : {snapshot.feels_like:.1f} °C")
    print(f"  humidity / wind    : {snapshot.humidity:.0f}% / {snapshot.wind:.1f} km/h")
    print(f"  condition          : {theme.describe(snapshot.code).label}")
    print(f"  confidence         : "
          f"{theme.confidence_label(snapshot.spread, snapshot.models_ok, len(MODELS))}")
    print(f"  hours / days       : {len(snapshot.hourly)} / {len(snapshot.daily)}")
    print(f"  models configured  : {', '.join(MODELS)}\n")
    if "--gui" in args:
        from weather_app.main import main as run_app

        return run_app()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
