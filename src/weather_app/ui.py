"""Application window: layout, micro-interactions and refresh orchestration."""
from __future__ import annotations

import logging
from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QFocusEvent
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QScrollArea, QSizeGrip, QVBoxLayout, QWidget)

from . import alerts
from . import scoring
from . import theme
from .fetcher import (DEFAULT_CITY, MODELS, Payloads, Place, Snapshot, WeatherFetcher,
                      cache_entry, city_bias, load_store, read_cache, save_store,
                      set_city_bias)
from .widgets import (Backdrop, GlassCard, HScroll, HoverButton, LineSpec, SunArc,
                      TitleBar, ValueCard, fade_in, label, moon_phase)

LOGGER = logging.getLogger(__name__)
REFRESH_MS, FOCUS_REFRESH_S, SHUTDOWN_WAIT_MS = 10 * 60 * 1000, 5 * 60, 2000
DETAIL_COLUMNS, OUTLOOK_DAYS, CONFIDENCE_MIN_W = 4, 5, 240
SCREEN_MARGIN = 60
DETAIL_CAPTIONS: tuple[str, ...] = ("Feels like", "Humidity", "Wind", "Direction",
                                    "Pressure", "Rain now", "Daylight", "Ensemble")
LEFT, CENTRE = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
BODY_MARGINS = (theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2)
HERO_MARGINS = (theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_3)
TILE_MARGINS = (theme.SPACE_2, theme.SPACE_1, theme.SPACE_2, theme.SPACE_1)
DAY_MARGINS = (theme.SPACE_1, theme.SPACE_2, theme.SPACE_1, theme.SPACE_2)
CHIP_MARGINS = (0, theme.SPACE_1, 0, theme.SPACE_1)
DIALOG_MARGINS = (theme.SPACE_3, theme.SPACE_3, theme.SPACE_3, theme.SPACE_3)
ADVISORY_MARGINS = (theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2)
DAY_LINES: tuple[LineSpec, ...] = (
    ("—", theme.FONT_LABEL, theme.TEXT_MUTED, CENTRE),
    ("—", theme.FONT_DESC, theme.TEXT_PRIMARY, CENTRE),
    ("—", theme.FONT_VALUE, theme.TEXT_PRIMARY, CENTRE),
    ("—", theme.FONT_LABEL, theme.TEXT_MUTED, CENTRE))
FIELD_QSS: str = (
    f"QLineEdit {{ background-color: {theme.CONTROL_FILL}; color: {theme.TEXT_PRIMARY};"
    f" border: 1px solid {theme.CONTROL_BORDER}; border-radius: {theme.RADIUS_CONTROL}px;"
    f" padding: 0 {theme.SPACE_2}px; {theme.FONT_CHIP.css} }}"
    f"QLineEdit:focus {{ border: 1px solid {theme.ACCENT}; }}")
DIALOG_QSS: str = (
    f"QDialog {{ background-color: {theme.DIALOG_BG}; }}"
    f"QLabel {{ color: {theme.TEXT_PRIMARY}; background: transparent; border: none;"
    f" {theme.FONT_CHIP.css} }}"
    f"QDoubleSpinBox {{ background-color: {theme.CONTROL_FILL}; color: {theme.TEXT_PRIMARY};"
    f" border: 1px solid {theme.CONTROL_BORDER}; border-radius: {theme.RADIUS_CONTROL}px;"
    f" padding: 6px 8px; {theme.FONT_CHIP.css} }}")
#: Kills the default grey box that Qt puts behind every QLabel.
LABEL_RESET_QSS: str = (
    "QLabel { background: transparent; border: none; }"
    "QToolTip { background: #1B2233; color: #F3F7FF; border: 1px solid rgba(255,255,255,0.18);"
    " border-radius: 6px; padding: 4px 8px; }")


def stack(spacing: int = theme.SPACE_1, margins: tuple[int, int, int, int] = (0, 0, 0, 0),
          horizontal: bool = False) -> QHBoxLayout | QVBoxLayout:
    """Return a vertical (default) or horizontal layout with spacing and margins."""
    layout = QHBoxLayout() if horizontal else QVBoxLayout()
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


class CalibrateDialog(QDialog):
    """Collects a real-world reading so the app can learn a per-city offset."""

    def __init__(self, model_temp: float, unit: str, city: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._unit = unit.upper()
        self.setWindowTitle("Calibrate this city")
        self.setModal(True)
        self.setMinimumWidth(430)
        self.setStyleSheet(DIALOG_QSS)
        body = stack(theme.SPACE_2, DIALOG_MARGINS)
        prompt = QLabel(f"Model says {theme.format_temp(model_temp, self._unit)}. Enter the "
                        f"real reading from IMD (or your trusted source) for {city}.")
        prompt.setWordWrap(True)
        body.addWidget(prompt)
        self._reading = QDoubleSpinBox()
        self._reading.setDecimals(1)
        self._reading.setSingleStep(0.5)
        self._reading.setRange(*((-90.0, 70.0) if self._unit == "C" else (-130.0, 160.0)))
        self._reading.setSuffix(f" °{self._unit}")
        self._reading.setValue(round(theme.convert_temp(model_temp, self._unit), 1))
        self._reading.setToolTip("The temperature actually observed right now")
        body.addWidget(self._reading)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)
        self.setLayout(body)

    def observed_celsius(self) -> float:
        """Return the entered reading converted back to Celsius."""
        value = self._reading.value()
        return value if self._unit == "C" else (value - 32.0) * 5.0 / 9.0


class WeatherApp(QMainWindow):
    """Frameless glassmorphism window with ensemble status and auto-refresh."""

    def __init__(self) -> None:
        super().__init__()
        self._store = load_store()
        self._unit = str(self._store.get("unit", "C")).upper()
        self._bias = 0.0
        self._snapshot: Snapshot | None = None
        self._fetchers: list[WeatherFetcher] = []
        self._req_id = 0
        self._last_fetch: datetime | None = None
        self.setWindowTitle("Weather")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(theme.WINDOW_MIN_W, theme.WINDOW_MIN_H)
        self._fit_to_screen()
        self.setStyleSheet(LABEL_RESET_QSS)

        self._backdrop = Backdrop()
        self.setCentralWidget(self._backdrop)
        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(lambda: self._refresh(self._current_city()))
        self._timer.start()
        self._restore_cache()
        self._refresh(self._current_city(), announce=True)

    def _fit_to_screen(self) -> None:
        """Size the window to fit the available screen area and centre it."""
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width, height = theme.WINDOW_W, theme.WINDOW_H
        if available is not None:
            width = min(width, max(available.width() - SCREEN_MARGIN,
                                   theme.WINDOW_MIN_W))
            height = min(height, max(available.height() - SCREEN_MARGIN,
                                     theme.WINDOW_MIN_H))
        self.resize(width, height)
        if available is not None:
            x = available.x() + (available.width() - width) // 2
            y = available.y() + (available.height() - height) // 2
            self.move(x, y)

    def _all_cards(self) -> list:
        """Return every card that supports set_fill (GlassCard or ValueCard)."""
        cards: list = []
        for name in ("_current_card", "_advisory_card", "_score_card"):
            card = getattr(self, name, None)
            if card is not None and hasattr(card, "set_fill"):
                cards.append(card)
        cards.extend(self._tiles.values())
        cards.extend(self._day_cards)
        return cards

    # ------------------------------------------------------------------
    #  Layout
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = stack(0, (0, 0, 0, 0))

        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_body = stack(theme.SPACE_2,
                            (theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_1))
        self._title_bar = TitleBar(self._unit)
        self._title_bar.unit_changed.connect(self._on_unit_changed)
        self._title_bar.minimize_requested.connect(self.showMinimized)
        self._title_bar.close_requested.connect(self.close)
        header_body.addWidget(self._title_bar)
        header_body.addLayout(self._build_search())
        header.setLayout(header_body)
        outer.addWidget(header, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,0.25);"
            " border-radius: 4px; min-height: 40px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical"
            " { background: transparent; }")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_col = stack(theme.SPACE_2, BODY_MARGINS)

        self._current_card = self._build_hero()
        self._advisory_card = self._build_advisory_panel()
        self._details_card = self._build_details()
        self._strips_card = self._build_strips()
        self._score_card = self._build_score_panel()

        body_col.addWidget(self._current_card, 4)
        body_col.addWidget(self._advisory_card, 0)
        body_col.addWidget(self._details_card, 2)
        body_col.addWidget(self._strips_card, 3)
        body_col.addWidget(self._score_card, 0)
        body.setLayout(body_col)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        footer_row = stack(theme.SPACE_2,
                           (theme.SPACE_3, theme.SPACE_1, theme.SPACE_3, theme.SPACE_2),
                           horizontal=True)
        self._status_label = label("Starting…", theme.FONT_LABEL, theme.TEXT_FAINT)
        self._status_label.setToolTip("Last update, model coverage and ensemble confidence")
        footer_row.addWidget(self._status_label, 1)
        grip = QSizeGrip(footer)
        grip.setToolTip("Drag to resize the window")
        footer_row.addWidget(grip, 0, Qt.AlignmentFlag.AlignRight |
                             Qt.AlignmentFlag.AlignBottom)
        footer.setLayout(footer_row)
        outer.addWidget(footer, 0)

        self._backdrop.setLayout(outer)

    def _build_search(self) -> QHBoxLayout:
        bar = stack(horizontal=True)
        self._search = QLineEdit()
        self._search.setPlaceholderText('Search a city — e.g. "Puri, IN" or "Paris, FR"')
        self._search.setToolTip("City name, optionally followed by a country code")
        self._search.setMinimumHeight(theme.CONTROL_H)
        self._search.setStyleSheet(FIELD_QSS)
        self._search.returnPressed.connect(
            lambda: self._refresh(self._search.text(), announce=True))
        bar.addWidget(self._search, 1)
        search_button = HoverButton("Search", "Fetch the ensemble forecast", primary=True)
        search_button.clicked.connect(
            lambda: self._refresh(self._search.text(), announce=True))
        bar.addWidget(search_button)
        calibrate = HoverButton("Calibrate",
                                "Record a real reading and learn a per-city offset")
        calibrate.clicked.connect(self._on_calibrate)
        bar.addWidget(calibrate)
        return bar

    def _build_hero(self) -> GlassCard:
        card = GlassCard(hero=True)
        card.setMinimumHeight(theme.HERO_MIN_H)
        layout = stack(theme.SPACE_3, HERO_MARGINS, horizontal=True)

        left = stack()
        self._city_label = label(DEFAULT_CITY, theme.FONT_CITY, theme.TEXT_PRIMARY, LEFT)
        self._temp_label = label("--°", theme.FONT_TEMP, theme.TEXT_PRIMARY, LEFT)
        self._desc_label = label("Waiting for data…", theme.FONT_DESC,
                                 theme.TEXT_SECONDARY, LEFT)
        for widget in (self._city_label, self._temp_label, self._desc_label):
            left.addWidget(widget)
        left.addStretch(1)
        layout.addLayout(left, 1)

        right = stack(theme.SPACE_1)
        right.addStretch(1)
        self._icon_label = label("⛅", theme.FONT_ICON, theme.TEXT_PRIMARY, CENTRE)
        right.addWidget(self._icon_label)

        self._sun_arc = SunArc()
        right.addWidget(self._sun_arc, 0, Qt.AlignmentFlag.AlignHCenter)

        self._moon_label = label("", theme.FONT_CHIP, theme.TEXT_SECONDARY, CENTRE)
        right.addWidget(self._moon_label)

        self._confidence_label = label("—", theme.FONT_LABEL, theme.TEXT_MUTED, CENTRE)
        self._confidence_label.setWordWrap(True)
        self._confidence_label.setMinimumWidth(CONFIDENCE_MIN_W)
        right.addWidget(self._confidence_label)
        right.addStretch(1)
        layout.addLayout(right)

        card.setLayout(layout)
        return card

    def _build_advisory_panel(self) -> GlassCard:
        """Glass card showing the top impact advisory and the anomaly line."""
        card = GlassCard()
        card.setMinimumHeight(72)
        column = stack(theme.SPACE_1, ADVISORY_MARGINS)
        self._advisory_label = label("Checking conditions…", theme.FONT_DESC,
                                     theme.TEXT_PRIMARY, LEFT)
        self._advisory_detail = label("", theme.FONT_LABEL, theme.TEXT_MUTED, LEFT)
        self._advisory_detail.setWordWrap(True)
        column.addWidget(self._advisory_label)
        column.addWidget(self._advisory_detail)
        card.setLayout(column)
        return card

    def _build_details(self) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(theme.SPACE_1)
        self._tiles: dict[str, ValueCard] = {}
        for index, caption in enumerate(DETAIL_CAPTIONS):
            tile = ValueCard([("—", theme.FONT_VALUE, theme.TEXT_PRIMARY, LEFT),
                              (caption.upper(), theme.FONT_LABEL, theme.TEXT_MUTED, LEFT)],
                             TILE_MARGINS, height=theme.TILE_H)
            self._tiles[caption] = tile
            grid.addWidget(tile, index // DETAIL_COLUMNS, index % DETAIL_COLUMNS)
        return holder

    def _build_strips(self) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        body = stack(theme.SPACE_2)
        body.addWidget(label("NEXT 24 HOURS", theme.FONT_LABEL, theme.TEXT_MUTED))
        self._hourly = HScroll()
        self._hourly.setToolTip("Scroll horizontally with the mouse wheel")
        self._hourly_body = QWidget()
        self._hourly_body.setStyleSheet("background: transparent;")
        self._hourly_row = stack(horizontal=True)
        self._hourly_body.setLayout(self._hourly_row)
        self._hourly.setWidget(self._hourly_body)
        body.addWidget(self._hourly)
        body.addWidget(label("OUTLOOK", theme.FONT_LABEL, theme.TEXT_MUTED))
        cards = stack(horizontal=True)
        self._day_cards = [ValueCard(DAY_LINES, DAY_MARGINS, height=theme.DAY_CARD_H,
                                     spacing=2) for _ in range(OUTLOOK_DAYS)]
        for card in self._day_cards:
            cards.addWidget(card, 1)
        body.addLayout(cards)
        holder.setLayout(body)
        return holder

    def _build_score_panel(self) -> GlassCard:
        """The self-scoring accuracy strip shown at the bottom of the body."""
        card = GlassCard()
        card.setMinimumHeight(52)
        row = stack(theme.SPACE_2,
                    (theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2),
                    horizontal=True)
        self._score_label = label("📊  Accuracy tracker · collecting data…",
                                  theme.FONT_LABEL, theme.TEXT_SECONDARY, LEFT)
        self._score_label.setToolTip(
            "The app saves every forecast it makes and later scores it against"
            " observations, then compares with persistence and with ECMWF IFS alone.")
        row.addWidget(self._score_label, 1)
        card.setLayout(row)
        return card

    # ------------------------------------------------------------------
    #  Data flow
    # ------------------------------------------------------------------
    def _current_city(self) -> str:
        return str(self._store.get("last_city", "")) or DEFAULT_CITY

    def _refresh(self, query: str, announce: bool = False) -> None:
        if not query.strip():
            self._status_label.setText("Type a city name first.")
            return
        self._req_id += 1
        request_id = self._req_id
        if announce:
            self._status_label.setText(f"Fetching {query} from {len(MODELS)} models…")
        fetcher = WeatherFetcher(query, request_id)
        fetcher.resolved.connect(lambda place, rid=request_id: self._on_resolved(place, rid))
        fetcher.succeeded.connect(lambda result, rid=request_id: self._on_success(result, rid))
        fetcher.failed.connect(lambda msg, rid=request_id: self._on_failure(msg, rid))
        fetcher.finished.connect(lambda f=fetcher: self._fetchers.remove(f)
                                 if f in self._fetchers else None)
        self._fetchers.append(fetcher)
        fetcher.start()

    def _on_resolved(self, place: Place, request_id: int) -> None:
        if request_id != self._req_id:
            return
        self._city_label.setText(place.label)
        self._city_label.setToolTip(
            f"{place.latitude:.3f}, {place.longitude:.3f} · {place.timezone}"
            f" · population {place.population:,}")

    def _on_success(self, result: tuple[Place, Payloads, Snapshot], request_id: int) -> None:
        if request_id != self._req_id:
            return
        place, payloads, snapshot = result
        self._snapshot = snapshot
        self._last_fetch = datetime.now()
        self._bias = city_bias(self._store, snapshot.place_label)
        self._store["last_city"] = snapshot.place_label
        self._store["cache"] = cache_entry(place, payloads, snapshot.fetched_at)
        save_store(self._store)
        self._search.setText(snapshot.place_label)
        self._render(snapshot)
        fade_in(self._icon_label)

        # ---- self-scoring: persist the observation and the forecast strips ----
        try:
            made_at = snapshot.fetched_at
            scoring.record_observation(snapshot.place_label, made_at, snapshot.temp)
            ensemble_rows = [(p.time, p.temp) for p in snapshot.hourly]
            scoring.record_ensemble(snapshot.place_label, made_at, ensemble_rows)
            ifs_rows = [(p.time, p.ifs_temp) for p in snapshot.hourly
                        if p.ifs_temp is not None]
            scoring.record_ensemble(snapshot.place_label, made_at, ifs_rows,
                                    model="ecmwf_ifs025")
        except Exception as exc:  # never let scoring break the UI
            LOGGER.warning("Scoring persistence failed: %s", exc)

        self._refresh_score(snapshot.place_label)

    def _refresh_score(self, place: str) -> None:
        """Update the accuracy panel with the latest score for *place*."""
        try:
            result = scoring.score(place)
        except Exception as exc:
            LOGGER.warning("Score query failed: %s", exc)
            result = None
        if result is None:
            self._score_label.setText(
                f"📊  Accuracy tracker · no matched data yet for {place}")
            return
        self._score_label.setText("📊  " + result.summary())

    def _on_failure(self, message: str, request_id: int) -> None:
        if request_id != self._req_id:
            return
        LOGGER.info("Fetch failed: %s", message)
        if self._snapshot is not None:
            self._snapshot.degraded = True
            self._render(self._snapshot)
        else:
            self._status_label.setText(f"Could not load weather — {message}")

    # ------------------------------------------------------------------
    #  Rendering
    # ------------------------------------------------------------------
    def _render(self, snapshot: Snapshot) -> None:
        # ---- adaptive sky: interpolate through 9 phases by city-local hour ----
        if snapshot.city_now and snapshot.sunrise and snapshot.sunset:
            hour_f = snapshot.city_now.hour + snapshot.city_now.minute / 60.0
            sunrise_f = snapshot.sunrise.hour + snapshot.sunrise.minute / 60.0
            sunset_f = snapshot.sunset.hour + snapshot.sunset.minute / 60.0
        else:
            now = datetime.now()
            hour_f = now.hour + now.minute / 60.0
            sunrise_f, sunset_f = 6.0, 18.0
        condition_key = theme.wmo_to_condition(snapshot.code)
        sky = theme.adaptive_sky(hour_f, sunrise_f, sunset_f, condition_key)
        self._backdrop.set_sky(sky)
        for card in self._all_cards():
            card.set_fill(sky.card_fill)

        self._city_label.setText(snapshot.place_label)
        self._city_label.setToolTip(
            f"{snapshot.latitude:.3f}, {snapshot.longitude:.3f} · {snapshot.timezone}")
        self._temp_label.setText(theme.format_temp(snapshot.temp + self._bias, self._unit))
        self._desc_label.setText(theme.describe(snapshot.code).label)
        self._icon_label.setText(theme.emoji_for(snapshot.code, snapshot.is_day))

        self._sun_arc.set_times(snapshot.sunrise, snapshot.sunset,
                                snapshot.city_now, snapshot.is_day)

        today = (snapshot.city_now.date() if snapshot.city_now
                 else snapshot.fetched_at.date() if snapshot.fetched_at
                 else date.today())
        phase_label, phase_glyph = moon_phase(today)
        self._moon_label.setText(f"{phase_glyph}  {phase_label}")

        parts = [theme.confidence_label(snapshot.spread, snapshot.models_ok,
                                        snapshot.models_total)]
        if self._bias:
            parts.append(f"calibrated {theme.format_delta(self._bias, self._unit)}")
        self._confidence_label.setText(" · ".join(parts))

        self._render_advisories(snapshot)
        self._render_details(snapshot)
        self._render_hourly(snapshot)
        self._render_daily(snapshot)
        stamp = theme.format_clock(snapshot.fetched_at)
        lead = f"showing saved data from {stamp}" if snapshot.degraded else f"Updated {stamp}"
        self._status_label.setText(
            f"{lead} · {snapshot.models_ok}/{snapshot.models_total} models"
            f" · {theme.confidence_phrase(snapshot.spread)}")

    def _render_advisories(self, snapshot: Snapshot) -> None:
        """Compute impact advisories and the anomaly flag, then update the panel."""
        precip_prob = snapshot.hourly[0].precip_prob if snapshot.hourly else None
        advisories = alerts.impact_advisories(
            temp_c=snapshot.temp, feels_c=snapshot.feels_like,
            wind_kmh=snapshot.wind, rain_mm=snapshot.rain,
            precip_prob=precip_prob, humidity=snapshot.humidity, uv=None)
        try:
            anomaly = alerts.detect_anomaly(snapshot.place_label, snapshot.temp)
        except Exception as exc:
            LOGGER.warning("Anomaly check failed: %s", exc)
            anomaly = None

        if advisories:
            top = advisories[0]
            self._advisory_label.setText(f"{top.glyph}  {top.headline}")
            extras = " · ".join(a.headline for a in advisories[1:3])
            lines = [top.detail]
            if extras:
                lines.append(f"Also: {extras}")
            if anomaly is not None:
                lines.append(anomaly.summary)
            self._advisory_detail.setText("\n".join(lines))
        elif anomaly is not None:
            self._advisory_label.setText(anomaly.summary)
            self._advisory_detail.setText(
                "Nothing unusual in wind, rain, or humidity today.")
        else:
            self._advisory_label.setText("✅  Nothing unusual today")
            self._advisory_detail.setText(
                "Comfortable conditions — no advisories to report.")

    def _render_details(self, snapshot: Snapshot) -> None:
        s, unit, bias = snapshot, self._unit, self._bias
        rows = ((theme.format_temp(s.feels_like + bias, unit), "Feels like"),
                (f"{s.humidity:.0f}%", "Humidity"),
                (theme.format_wind(s.wind, unit), "Wind"),
                (f"{theme.compass(s.wind_dir)} {s.wind_dir:.0f}°", "Direction"),
                (f"{s.pressure:.0f} hPa", "Pressure"),
                (f"{s.rain:.1f} mm", "Rain now"),
                ("Day" if s.is_day else "Night", "Daylight"),
                (f"{s.models_ok}/{s.models_total} models", "Ensemble"))
        for value, caption in rows:
            self._tiles[caption].set_lines([value, caption.upper()])

    def _render_hourly(self, snapshot: Snapshot) -> None:
        while self._hourly_row.count():
            if (widget := self._hourly_row.takeAt(0).widget()) is not None:
                widget.deleteLater()
        for index, point in enumerate(snapshot.hourly):
            name = "Now" if index == 0 else theme.format_clock(point.time)
            chip = ValueCard(
                [(name, theme.FONT_LABEL, theme.TEXT_MUTED, CENTRE),
                 (theme.emoji_for(point.code, snapshot.is_day), theme.FONT_DESC,
                  theme.TEXT_PRIMARY, CENTRE),
                 (theme.format_temp(point.temp + self._bias, self._unit), theme.FONT_VALUE,
                  theme.TEXT_PRIMARY, CENTRE)],
                CHIP_MARGINS, spacing=2, size=(theme.CHIP_W, theme.CHIP_H),
                fill=theme.ACCENT_GLOW if index == 0 else theme.CARD_FILL,
                border=theme.ACCENT if index == 0 else theme.CARD_BORDER)
            rain = "" if point.precip_prob is None else f" · {point.precip_prob:.0f}% rain"
            chip.setToolTip(f"{name} · {theme.describe(point.code).label}{rain}")
            self._hourly_row.addWidget(chip)
        self._hourly_row.addStretch(1)

    def _render_daily(self, snapshot: Snapshot) -> None:
        for index, card in enumerate(self._day_cards):
            if index >= len(snapshot.daily):
                card.set_lines(["—", "🌡️", "—", "—"])
                card.setToolTip("No data")
                continue
            day = snapshot.daily[index]
            rain = (f"{day.precip_prob:.0f}% rain" if day.precip_prob is not None
                    else "no data")
            card.set_lines([theme.weekday(day.day), theme.emoji_for(day.code, True),
                            f"{theme.format_temp(day.tmax + self._bias, self._unit)} / "
                            f"{theme.format_temp(day.tmin + self._bias, self._unit)}", rain])
            card.setToolTip(f"{theme.describe(day.code).label} · {day.day.isoformat()}")

    def _restore_cache(self) -> None:
        cached = read_cache(self._store)
        if cached is None:
            return
        place, snapshot = cached
        snapshot.degraded = True
        self._snapshot = snapshot
        self._bias = city_bias(self._store, snapshot.place_label)
        self._search.setText(place.label)
        self._render(snapshot)

    # ------------------------------------------------------------------
    #  Interaction
    # ------------------------------------------------------------------
    def _on_unit_changed(self, unit: str) -> None:
        self._unit = unit.upper()
        self._store["unit"] = self._unit
        save_store(self._store)
        if self._snapshot is not None:
            self._render(self._snapshot)
            fade_in(self._temp_label, theme.UNIT_FADE_MS)

    def _on_calibrate(self) -> None:
        if self._snapshot is None:
            self._status_label.setText("Fetch a city before calibrating.")
            return
        dialog = CalibrateDialog(self._snapshot.temp + self._bias, self._unit,
                                 self._snapshot.place_label, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._bias = dialog.observed_celsius() - self._snapshot.temp
        set_city_bias(self._store, self._snapshot.place_label, self._bias)
        save_store(self._store)
        self._render(self._snapshot)
        self._status_label.setText(
            f"Calibrated {self._snapshot.place_label} by "
            f"{theme.format_delta(self._bias, self._unit)}")

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        stale = (self._last_fetch is None
                 or (datetime.now() - self._last_fetch).total_seconds() > FOCUS_REFRESH_S)
        if stale:
            self._refresh(self._current_city())

    def closeEvent(self, event: QCloseEvent) -> None:
        self._timer.stop()
        save_store(self._store)
        for fetcher in list(self._fetchers):
            fetcher.wait(SHUTDOWN_WAIT_MS)
        super().closeEvent(event)