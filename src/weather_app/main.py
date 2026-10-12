"""Entry point for the weather desktop application.

Run with ``python -m weather_app.main`` from the ``src`` directory, or use the
``preview.py`` script at the repository root.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import __version__
from .theme import FONT_STACK
from .ui import WeatherApp

LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FONT_FAMILIES: tuple[str, ...] = ("Segoe UI", "SF Pro Display", "Inter", "Helvetica Neue",
                                  "Arial")
BASE_POINT_SIZE: int = 10

def main() -> int:
    """Create the Qt application, show the window and run the event loop.

    Returns:
        The process exit code produced by the Qt event loop.
    """
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.getLogger(__name__).info("Starting weather app %s", __version__)
    app = QApplication(sys.argv)
    app.setApplicationName("Weather")
    app.setApplicationVersion(__version__)
    font = QFont()
    font.setFamilies(list(FONT_FAMILIES))
    font.setPointSize(BASE_POINT_SIZE)
    app.setFont(font)
    app.setStyleSheet(f"QToolTip {{ font-family: {FONT_STACK}; }}")
    window = WeatherApp()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
