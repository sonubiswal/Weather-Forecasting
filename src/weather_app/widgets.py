"""Reusable presentation widgets: backdrop, glass cards, tiles, arcs and strips."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Sequence

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt,
                            Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QMouseEvent, QPainter,
                           QPainterPath, QPaintEvent, QRadialGradient, QWheelEvent)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from . import theme

#: One tile line: initial text, type role, colour and alignment.
LineSpec = tuple[str, theme.Font, str, Qt.AlignmentFlag]
_UI_FAMILIES = ["Segoe UI", "SF Pro Display", "Inter", "Arial"]


def label(text: str, font: theme.Font, color: str,
          align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft) -> QLabel:
    """Return a label styled with the given type role, colour and alignment.

    ``background: transparent; border: none;`` is included so Qt does not draw
    the default grey box behind the label.
    """
    widget = QLabel(text)
    widget.setAlignment(align)
    widget.setStyleSheet(
        f"color: {color}; background: transparent; border: none; {font.css}")
    return widget


def card_qss(radius: int = theme.RADIUS_CARD, fill: str = theme.CARD_FILL,
             border: str = theme.CARD_BORDER) -> str:
    """Return the glassmorphism style sheet for a rounded card."""
    return (f"QFrame {{ background-color: {fill}; border: 1px solid {border};"
            f" border-radius: {radius}px; }}")


def fade_in(widget: QWidget, duration_ms: int = theme.FADE_MS) -> None:
    """Fade *widget* in, then remove the opacity effect so text renders sharp again.

    Note: a widget can hold only one graphics effect. Do not call this on a
    ``GlassCard(hero=True)`` (it would replace the drop shadow); fade its
    container instead.
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._fade_animation = animation          # parent=widget keeps it alive
    animation.start()


def moon_phase(moment: date) -> tuple[str, str]:
    """Return ``(label, emoji)`` for the moon phase on *moment*.

    Uses a simple synodic-cycle approximation anchored on the new moon of
    2000-01-06. Accurate to within a few hours — plenty for a UI label.
    """
    reference = date(2000, 1, 6)
    days = (moment - reference).days
    phase = (days % 29.530588) / 29.530588
    if phase < 0.03 or phase >= 0.97:
        return "New moon", "🌑"
    if phase < 0.22:
        return "Waxing crescent", "🌒"
    if phase < 0.28:
        return "First quarter", "🌓"
    if phase < 0.47:
        return "Waxing gibbous", "🌔"
    if phase < 0.53:
        return "Full moon", "🌕"
    if phase < 0.72:
        return "Waning gibbous", "🌖"
    if phase < 0.78:
        return "Last quarter", "🌗"
    return "Waning crescent", "🌘"


class SunArc(QWidget):
    """Compact sunrise→sunset arc that marks where the sun/moon is right now."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(240, 76)
        self._sunrise: datetime | None = None
        self._sunset: datetime | None = None
        self._now: datetime | None = None
        self._is_day = True

    def set_times(self, sunrise: datetime | None, sunset: datetime | None,
                  now: datetime | None, is_day: bool) -> None:
        """Update the arc geometry and repaint."""
        self._sunrise, self._sunset, self._now, self._is_day = sunrise, sunset, now, is_day
        self.update()

    def _progress(self) -> float:
        """Fraction of the daylight window that has elapsed (0 at sunrise, 1 at sunset)."""
        if not (self._sunrise and self._sunset and self._now):
            return 0.5
        total = (self._sunset - self._sunrise).total_seconds()
        if total <= 0:
            return 0.5
        elapsed = (self._now - self._sunrise).total_seconds()
        return max(0.0, min(1.0, elapsed / total))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width, height = self.width(), self.height()

        pad_x = 18
        arc_w = width - 2 * pad_x
        arc_h = arc_w * 0.42                # vertical semi-axis of the ellipse
        baseline_y = height - 22.0

        # ---- dashed horizon ----
        painter.setPen(QColor(255, 255, 255, 55))
        pen = painter.pen()
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(pad_x), int(baseline_y),
                         int(pad_x + arc_w), int(baseline_y))

        # ---- the arc itself (upper half of an ellipse) ----
        arc_rect = QRectF(pad_x, baseline_y - arc_h, arc_w, arc_h * 2.0)
        painter.setPen(QColor(255, 255, 255, 130))
        painter.drawArc(arc_rect, 0, 180 * 16)

        # ---- position marker ----
        progress = self._progress()
        theta = math.radians(180.0 - 180.0 * progress)
        cx = arc_rect.center().x() + (arc_w / 2.0) * math.cos(theta)
        cy = arc_rect.center().y() - arc_h * math.sin(theta)

        glow = QColor(255, 209, 102, 70) if self._is_day else QColor(221, 230, 255, 70)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), 12, 12)

        core = QColor("#FFD166") if self._is_day else QColor("#DDE6FF")
        painter.setBrush(QBrush(core))
        painter.drawEllipse(QPointF(cx, cy), 5, 5)

        # ---- sunrise / sunset time labels ----
        font = QFont()
        font.setFamilies(_UI_FAMILIES)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(243, 247, 255, 180))
        sunrise_text = self._sunrise.strftime("%H:%M") if self._sunrise else "—"
        sunset_text = self._sunset.strftime("%H:%M") if self._sunset else "—"
        left_rect = QRectF(0, baseline_y + 2, width / 2.0 - 6, 18)
        right_rect = QRectF(width / 2.0 + 6, baseline_y + 2, width / 2.0 - 6, 18)
        painter.drawText(left_rect, int(Qt.AlignmentFlag.AlignLeft |
                                        Qt.AlignmentFlag.AlignVCenter), sunrise_text)
        painter.drawText(right_rect, int(Qt.AlignmentFlag.AlignRight |
                                         Qt.AlignmentFlag.AlignVCenter), sunset_text)
        painter.end()


class Backdrop(QWidget):
    """Sky gradient + horizon glow + legibility scrim + vignette."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sky: theme.Sky = theme.SKY_FALLBACK

    def set_sky(self, sky: theme.Sky) -> None:
        """Switch the backdrop to a new adaptive sky and repaint."""
        self._sky = sky
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        sky = self._sky
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), float(theme.RADIUS_WINDOW),
                            float(theme.RADIUS_WINDOW))

        gradient = QLinearGradient(0.0, 0.0, 0.0, float(self.height()))
        gradient.setColorAt(0.00, QColor(*sky.top))
        gradient.setColorAt(0.55, QColor(*sky.mid))
        gradient.setColorAt(1.00, QColor(*sky.bottom))
        painter.fillPath(path, gradient)

        if sky.glow_alpha > 0.02:
            r, g, b = sky.glow
            glow = QRadialGradient(QPointF(self.width() / 2.0, self.height() * 1.05),
                                   max(self.width(), self.height()) * 0.75)
            # Fade to the SAME colour at alpha 0 (not transparent black) so the
            # glow never gets a dark, muddy fringe.
            glow.setColorAt(0.0, QColor(r, g, b, int(255 * sky.glow_alpha)))
            glow.setColorAt(1.0, QColor(r, g, b, 0))
            painter.fillPath(path, glow)

        if sky.scrim_alpha > 0.01:
            scrim = QColor(*theme.SCRIM_RGB)
            scrim.setAlphaF(min(1.0, sky.scrim_alpha))
            painter.fillPath(path, scrim)

        vignette = QRadialGradient(QPointF(self.rect().center()),
                                   max(self.width(), self.height()) * 0.72)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(*theme.VIGNETTE_RGBA))
        painter.fillPath(path, vignette)
        painter.end()


class GlassCard(QFrame):
    """A rounded translucent panel; ``hero=True`` adds the drop shadow."""

    def __init__(self, radius: int = theme.RADIUS_CARD, hero: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._fill = theme.CARD_FILL
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(card_qss(radius))
        if hero:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(theme.SHADOW_BLUR)
            shadow.setOffset(0, theme.SHADOW_DY)
            shadow.setColor(QColor(*theme.SHADOW_RGBA))
            self.setGraphicsEffect(shadow)

    def set_fill(self, fill: str) -> None:
        """Change the card colour; the style sheet is only rebuilt when it differs."""
        if fill != self._fill:
            self._fill = fill
            self.setStyleSheet(card_qss(self._radius, fill))


class ValueCard(QFrame):
    """Rounded glass tile whose text lines are replaced with :meth:`set_lines`."""

    def __init__(self, specs: Sequence[LineSpec], margins: tuple[int, int, int, int],
                 height: int = 0, spacing: int = 0, fill: str = theme.CARD_FILL,
                 border: str = theme.CARD_BORDER, size: tuple[int, int] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fill, self._border = fill, border
        self.setStyleSheet(card_qss(theme.RADIUS_CONTROL, fill, border))
        if size:
            self.setFixedSize(*size)
        else:
            self.setMinimumHeight(height)
        column = QVBoxLayout(self)
        column.setContentsMargins(*margins)
        column.setSpacing(spacing)
        self._labels = [label(*spec) for spec in specs]
        for widget in self._labels:
            column.addWidget(widget)

    def set_lines(self, texts: Sequence[str]) -> None:
        """Replace every text line on this tile, in order."""
        for widget, text in zip(self._labels, texts):
            widget.setText(text)

    def set_fill(self, fill: str) -> None:
        """Change the tile colour; rebuilds the style sheet only when it differs."""
        if fill != self._fill:
            self._fill = fill
            self.setStyleSheet(card_qss(theme.RADIUS_CONTROL, fill, self._border))


class HoverButton(QPushButton):
    """Push button that brightens on hover; ``primary`` fills it with the accent."""

    def __init__(self, text: str, tooltip: str = "", primary: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._primary = primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(tooltip or text)
        self.setMinimumHeight(theme.CONTROL_H)
        self.setStyleSheet(self._qss())

    def _qss(self) -> str:
        """One style sheet with a :hover state, so no enter/leave handlers are needed."""
        rest = theme.ACCENT if self._primary else theme.CONTROL_FILL
        hover = theme.ACCENT_HOVER if self._primary else theme.CARD_FILL_HOVER
        border = theme.ACCENT if self._primary else theme.CONTROL_BORDER
        color = theme.WHITE if self._primary else theme.TEXT_PRIMARY
        return (f"QPushButton {{ background-color: {rest}; color: {color};"
                f" border: 1px solid {border}; border-radius: {theme.RADIUS_CONTROL}px;"
                f" padding: 0 {theme.SPACE_2}px; {theme.FONT_BUTTON.css} }}"
                f"QPushButton:hover {{ background-color: {hover};"
                f" border: 1px solid {theme.ACCENT}; }}"
                f"QPushButton:focus {{ border: 1px solid {theme.ACCENT}; }}"
                f"QPushButton:pressed {{ background-color: {theme.ACCENT_GLOW}; }}")


class TitleBar(QWidget):
    """Custom draggable title bar with window controls and a unit switch."""

    minimize_requested = Signal()
    close_requested = Signal()
    unit_changed = Signal(str)

    def __init__(self, unit: str = "C", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(theme.TITLEBAR_H)
        self._unit = unit.upper()
        self._origin: QPoint | None = None
        bar = QHBoxLayout(self)
        bar.setContentsMargins(theme.SPACE_2, 0, theme.SPACE_1, 0)
        bar.setSpacing(theme.SPACE_1)
        brand = QLabel("⛅  Weather")
        brand.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; background: transparent;"
            f" border: none; {theme.FONT_BUTTON.css}")
        bar.addWidget(brand)
        bar.addStretch(1)
        self._unit_button = HoverButton(theme.UNIT_LABEL[self._unit], "Toggle °C / °F")
        self._unit_button.setFixedWidth(76)
        self._unit_button.clicked.connect(self._toggle_unit)
        bar.addWidget(self._unit_button)
        for text, tooltip, signal in (("—", "Minimise", self.minimize_requested),
                                      ("✕", "Close", self.close_requested)):
            button = HoverButton(text, tooltip)
            button.setFixedSize(38, theme.CONTROL_H - 6)
            button.clicked.connect(signal.emit)
            bar.addWidget(button)

    def _toggle_unit(self) -> None:
        self._unit = "F" if self._unit == "C" else "C"
        self._unit_button.setText(theme.UNIT_LABEL[self._unit])
        self.unit_changed.emit(self._unit)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = (event.globalPosition().toPoint()
                            - self.window().frameGeometry().topLeft())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._origin)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._origin = None


class HScroll(QScrollArea):
    """Horizontal strip that also scrolls on vertical mouse-wheel input."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(theme.CHIP_H + theme.SPACE_2)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                           "QScrollArea > QWidget > QWidget { background: transparent; }")

    def wheelEvent(self, event: QWheelEvent) -> None:
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - (event.angleDelta().y() or event.angleDelta().x()))
        event.accept()