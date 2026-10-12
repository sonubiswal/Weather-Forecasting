"""Design tokens: palette, geometry, typography, adaptive sky and WMO codes."""
from __future__ import annotations

import math
from datetime import date, datetime
from functools import lru_cache
from typing import Final, NamedTuple

ACCENT, ACCENT_HOVER, ACCENT_GLOW = "#5B8DEF", "#7BA5F5", "rgba(91,141,239,0.30)"
TEXT_PRIMARY, TEXT_SECONDARY = "#F3F7FF", "rgba(243,247,255,0.74)"
TEXT_MUTED, TEXT_FAINT = "rgba(243,247,255,0.60)", "rgba(243,247,255,0.55)"
CARD_FILL, CARD_FILL_HOVER = "rgba(255,255,255,0.10)", "rgba(255,255,255,0.16)"
CARD_BORDER, CONTROL_FILL = "rgba(255,255,255,0.17)", "rgba(255,255,255,0.08)"
CONTROL_BORDER, WHITE, DIALOG_BG = "rgba(255,255,255,0.14)", "#FFFFFF", "#1B2233"
SHADOW_RGBA: Final[tuple[int, int, int, int]] = (0, 0, 0, 90)
VIGNETTE_RGBA: Final[tuple[int, int, int, int]] = (8, 12, 26, 70)
SPACE_1, SPACE_2, SPACE_3, SPACE_4 = 8, 16, 24, 32
RADIUS_WINDOW, RADIUS_CARD, RADIUS_CONTROL = 26, 20, 15
CONTROL_H, TITLEBAR_H, SHADOW_BLUR, SHADOW_DY = 36, 46, 30, 6
WINDOW_W, WINDOW_H, WINDOW_MIN_W, WINDOW_MIN_H = 980, 1020, 700, 560
HERO_MIN_H, TILE_H, DAY_CARD_H, CHIP_W, CHIP_H = 200, 58, 96, 74, 90
FADE_MS, UNIT_FADE_MS = 420, 260
FONT_STACK: Final[str] = '"Segoe UI", "SF Pro Display", "Inter", Arial, sans-serif'
UNIT_LABEL: Final[dict[str, str]] = {"C": "°C", "F": "°F"}


class Font(NamedTuple):
    """A typographic role: point size plus Qt font weight."""

    size: int
    weight: int

    @property
    def css(self) -> str:
        """Render the role as a Qt style-sheet fragment."""
        return f"font-size: {self.size}pt; font-weight: {self.weight};"


FONT_CITY, FONT_TEMP = Font(22, 600), Font(72, 300)
FONT_DESC, FONT_VALUE = Font(14, 500), Font(12, 600)
FONT_LABEL, FONT_BUTTON = Font(9, 400), Font(10, 600)
FONT_CHIP, FONT_ICON = Font(10, 500), Font(46, 400)


# ============================================================
#  Adaptive sky engine (ported from a JS reference)
# ============================================================
# Nine sky phases, each with a 3-stop vertical gradient (top → 55% → bottom)
# and a glow colour. The phase is chosen by the current hour at the searched
# city and smoothly interpolated between the two nearest phases. The result
# is blended toward grey in proportion to how overcast the weather is.
#
# IMPORTANT: ``hour``, ``sunrise_h`` and ``sunset_h`` must all be in the
# searched city's LOCAL time (not the PC's clock).

RGB = tuple[int, int, int]


class SkyPhases(NamedTuple):
    """One sky phase: gradient stops, glow, star density, label."""

    c: tuple[str, str, str]
    glow: str
    ga: float      # glow opacity 0..1
    stars: float   # star intensity 0..1
    label: str


SKY_PHASES: Final[dict[str, SkyPhases]] = {
    "midnight":  SkyPhases(("#050816", "#0a1030", "#0f1a3d"), "#4466aa", 0.10, 1.00, "Midnight"),
    "predawn":   SkyPhases(("#121a45", "#4a3470", "#d98a7a"), "#ff9f7a", 0.35, 0.50, "Pre-dawn"),
    "sunrise":   SkyPhases(("#2a2358", "#c4576a", "#f6a65a"), "#ffd08a", 0.75, 0.00, "Sunrise golden hour"),
    "morning":   SkyPhases(("#2563c9", "#5aa8ee", "#bfe3fa"), "#fff3c4", 0.25, 0.00, "Morning"),
    "noon":      SkyPhases(("#1d4ed8", "#3b82f6", "#8fd0f7"), "#ffffff", 0.15, 0.00, "Midday"),
    "afternoon": SkyPhases(("#2a5fd0", "#5aa4ec", "#cbe6f7"), "#fff0c8", 0.20, 0.00, "Afternoon"),
    "sunset":    SkyPhases(("#2d2260", "#b8455f", "#f59a4a"), "#ffc274", 0.80, 0.00, "Sunset golden hour"),
    "dusk":      SkyPhases(("#1c1a4f", "#4a2c78", "#b04a77"), "#ff8fa3", 0.40, 0.35, "Dusk"),
    "night":     SkyPhases(("#0a1030", "#111a3d", "#16224d"), "#3355aa", 0.12, 0.90, "Night"),
}

#: Weather condition → grey blend strength and effect layers (rain, cloud, fog, storm).
WEATHER_BLEND: Final[dict[str, dict[str, float | str]]] = {
    "clear":      {"g": 0.00, "rain": 0.0, "cloud": 0.12, "fog": 0.0, "storm": 0.0, "label": "Clear"},
    "partly":     {"g": 0.25, "rain": 0.0, "cloud": 0.55, "fog": 0.0, "storm": 0.0, "label": "Partly cloudy"},
    "cloudy":     {"g": 0.55, "rain": 0.0, "cloud": 0.90, "fog": 0.0, "storm": 0.0, "label": "Cloudy"},
    "light_rain": {"g": 0.45, "rain": 0.4, "cloud": 0.80, "fog": 0.0, "storm": 0.0, "label": "Light rain"},
    "rain":       {"g": 0.75, "rain": 1.0, "cloud": 1.00, "fog": 0.0, "storm": 0.0, "label": "Rain"},
    "downpour":   {"g": 0.85, "rain": 1.4, "cloud": 1.00, "fog": 0.0, "storm": 0.0, "label": "Heavy rain"},
    "storm":      {"g": 0.90, "rain": 1.6, "cloud": 1.00, "fog": 0.0, "storm": 1.0, "label": "Thunderstorm"},
    "fog":        {"g": 0.60, "rain": 0.0, "cloud": 0.60, "fog": 1.0, "storm": 0.0, "label": "Fog"},
}

_GREY_NIGHT: Final[tuple[str, str, str]] = ("#0d1320", "#19212f", "#26303f")
_GREY_DAY: Final[tuple[str, str, str]] = ("#566174", "#6f7d92", "#9aa8bb")

# Legibility tuning: light skies get a dark scrim over the whole background
# and a darker card fill, so the light text tokens stay readable all day.
SCRIM_RGB: Final[tuple[int, int, int]] = (8, 12, 26)
_SCRIM_RGB = SCRIM_RGB   # backwards-compatible alias
_CARD_TINT_RGB: Final[tuple[int, int, int]] = (10, 20, 46)
_SCRIM_MAX, _CARD_TINT_MAX = 0.55, 0.45


@lru_cache(maxsize=None)
def _hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return float(int(h[0:2], 16)), float(int(h[2:4], 16)), float(int(h[4:6], 16))


def _mix(a: tuple[float, ...], b: tuple[float, ...], t: float) -> tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _luminance(c: tuple[float, ...]) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# WMO weather interpretation codes (Open-Meteo) → engine weather keys.
_WMO_CONDITION: Final[dict[int, str]] = {
    0: "clear", 1: "clear", 2: "partly", 3: "cloudy",
    45: "fog", 48: "fog",
    51: "light_rain", 53: "light_rain", 55: "rain", 56: "light_rain", 57: "rain",
    61: "light_rain", 63: "rain", 65: "downpour", 66: "rain", 67: "downpour",
    71: "cloudy", 73: "cloudy", 75: "cloudy", 77: "cloudy",      # snow treated as overcast
    80: "light_rain", 81: "rain", 82: "downpour",
    85: "cloudy", 86: "cloudy",
    95: "storm", 96: "storm", 99: "storm",
}


def wmo_to_condition(code: int) -> str:
    """Map a WMO weather code to one of the engine's weather keys."""
    return _WMO_CONDITION.get(code, "partly")   # unknown code → neutral, not "clear"


class Sky(NamedTuple):
    """Result of the adaptive sky engine: three gradient stops plus metadata.

    The last four fields have defaults, so existing positional constructors
    keep working.  ``scrim_alpha`` is the opacity of a ``_SCRIM_RGB`` overlay
    to paint over the whole background; ``card_fill`` replaces ``CARD_FILL``.
    """

    top: RGB
    mid: RGB
    bottom: RGB
    phase_label: str
    weather_label: str
    stars: float
    rain: float
    cloud: float
    glow: RGB
    glow_alpha: float
    fog: float = 0.0
    storm: float = 0.0
    scrim_alpha: float = 0.0
    card_fill: str = CARD_FILL


#: A sensible dark default used before the first real snapshot arrives.
SKY_FALLBACK: Final[Sky] = Sky((43, 58, 85), (92, 110, 138), (92, 110, 138),
                               "Night", "Clear", 0.5, 0.0, 0.0,
                               (51, 85, 170), 0.10)


def _phase_keys(sunrise_h: float, sunset_h: float) -> list[tuple[float, str]]:
    """Build strictly increasing phase keys, whatever the sunrise/sunset data."""
    sr = _clamp(sunrise_h, 1.25, 11.0)
    ss = _clamp(sunset_h, 13.0, 21.5)
    if ss - sr < 4.0:                       # polar day/night or bad data
        sr, ss = 6.0, 18.0
    noon = (sr + ss) / 2.0
    return [
        (0.0, "midnight"),
        (sr - 1.0, "predawn"),
        (sr, "sunrise"),
        (sr + 1.5, "morning"),
        (noon, "noon"),
        (ss - 1.5, "afternoon"),
        (ss, "sunset"),
        (ss + 0.8, "dusk"),
        (ss + 2.0, "night"),
        (24.0, "midnight"),
    ]


def adaptive_sky(hour: float, sunrise_h: float, sunset_h: float,
                 condition: str) -> Sky:
    """Return the interpolated sky for *hour* (0–24) at sunrise/sunset times."""
    if not all(math.isfinite(v) for v in (hour, sunrise_h, sunset_h)):
        return SKY_FALLBACK
    hour %= 24.0
    keys = _phase_keys(sunrise_h, sunset_h)
    i = 0
    while i < len(keys) - 2 and hour >= keys[i + 1][0]:
        i += 1
    a, b = SKY_PHASES[keys[i][1]], SKY_PHASES[keys[i + 1][1]]
    span = keys[i + 1][0] - keys[i][0]
    f = _smoothstep(_clamp((hour - keys[i][0]) / span, 0.0, 1.0))
    w = WEATHER_BLEND.get(condition, WEATHER_BLEND["clear"])
    g_strength = float(w["g"])

    stops = [_mix(_hex_rgb(a.c[k]), _hex_rgb(b.c[k]), f) for k in range(3)]
    dayness = _clamp(_luminance(stops[1]) * 1.7, 0.0, 1.0)
    stops = [
        _mix(c, _mix(_hex_rgb(_GREY_NIGHT[k]), _hex_rgb(_GREY_DAY[k]), dayness), g_strength)
        for k, c in enumerate(stops)
    ]
    glow = _mix(_hex_rgb(a.glow), _hex_rgb(b.glow), f)
    glow_alpha = (a.ga + (b.ga - a.ga) * f) * (1.0 - g_strength * 0.85)
    stars = (a.stars + (b.stars - a.stars) * f) * (1.0 - g_strength)

    # Legibility: darken light skies, then tint the cards if still too bright.
    backdrop = _mix(stops[1], stops[2], 0.5)                 # where the cards sit
    scrim = _clamp((_luminance(backdrop) - 0.20) * 1.25, 0.0, _SCRIM_MAX)
    after_scrim = _luminance(_mix(backdrop, _SCRIM_RGB, scrim))
    tint = _clamp((after_scrim - 0.14) * 2.2, 0.0, _CARD_TINT_MAX)
    card_fill = (CARD_FILL if tint < 0.04
                 else f"rgba({_CARD_TINT_RGB[0]},{_CARD_TINT_RGB[1]},{_CARD_TINT_RGB[2]},{tint:.2f})")

    to_rgb = lambda c: (int(round(c[0])), int(round(c[1])), int(round(c[2])))
    return Sky(
        top=to_rgb(stops[0]), mid=to_rgb(stops[1]), bottom=to_rgb(stops[2]),
        phase_label=(a if f < 0.5 else b).label,
        weather_label=str(w["label"]),
        stars=float(stars), rain=float(w["rain"]), cloud=float(w["cloud"]),
        glow=to_rgb(glow), glow_alpha=float(glow_alpha),
        fog=float(w["fog"]), storm=float(w["storm"]),
        scrim_alpha=float(scrim), card_fill=card_fill)


# ============================================================
#  WMO codes → labels and emoji
# ============================================================
class Wmo(NamedTuple):
    """Human label plus day and night glyphs for one WMO weather code."""

    label: str
    day: str
    night: str


WMO_ROWS: Final[tuple[tuple[int, str, str, str], ...]] = (
    (0, "Clear sky", "☀️", "🌙"), (1, "Mainly clear", "🌤️", "🌙"),
    (2, "Partly cloudy", "⛅", "☁️"), (3, "Overcast", "☁️", "☁️"),
    (45, "Fog", "🌫️", "🌫️"), (48, "Rime fog", "🌫️", "🌫️"),
    (51, "Light drizzle", "🌦️", "🌧️"), (53, "Drizzle", "🌦️", "🌧️"),
    (55, "Dense drizzle", "🌧️", "🌧️"),
    (56, "Light freezing drizzle", "🌧️", "🌧️"), (57, "Freezing drizzle", "🌧️", "🌧️"),
    (61, "Light rain", "🌦️", "🌧️"), (63, "Rain", "🌧️", "🌧️"),
    (65, "Heavy rain", "🌧️", "🌧️"),
    (66, "Light freezing rain", "🌧️", "🌧️"), (67, "Freezing rain", "🌧️", "🌧️"),
    (71, "Light snow", "🌨️", "🌨️"), (73, "Snow", "❄️", "❄️"),
    (75, "Heavy snow", "❄️", "❄️"), (77, "Snow grains", "🌨️", "🌨️"),
    (80, "Light showers", "🌦️", "🌧️"), (81, "Showers", "🌧️", "🌧️"),
    (82, "Violent showers", "⛈️", "⛈️"), (85, "Snow showers", "🌨️", "🌨️"),
    (86, "Heavy snow showers", "❄️", "❄️"), (95, "Thunderstorm", "⛈️", "⛈️"),
    (96, "Storm with hail", "⛈️", "⛈️"), (99, "Storm with hail", "⛈️", "⛈️"))
WMO: Final[dict[int, Wmo]] = {code: Wmo(label, day, night)
                              for code, label, day, night in WMO_ROWS}
UNKNOWN: Final[Wmo] = Wmo("Unknown conditions", "🌡️", "🌡️")


def describe(code: int) -> Wmo:
    """Return the label and glyphs for a WMO code, with a safe fallback."""
    return WMO.get(code, UNKNOWN)


def emoji_for(code: int, is_day: bool) -> str:
    """Return the day or night glyph for a WMO code."""
    entry = describe(code)
    return entry.day if is_day else entry.night


# ============================================================
#  Formatting helpers
# ============================================================
KMH_TO_MPH: Final[float] = 0.621371
COMPASS_POINTS: Final[tuple[str, ...]] = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW",
    "NW", "NNW")
CONFIDENCE_BANDS: Final[tuple[tuple[float, str], ...]] = (
    (1.0, "High confidence"), (2.5, "Good confidence"), (5.0, "Moderate confidence"))


def _no_neg_zero(value: float, decimals: int) -> float:
    """Round *value* and turn -0.0 into 0.0 so we never print ``-0°``."""
    rounded = round(value, decimals)
    return 0.0 if rounded == 0 else rounded


def convert_temp(celsius: float, unit: str) -> float:
    """Convert a Celsius value into *unit* (``"C"`` or ``"F"``)."""
    return celsius if unit.upper() == "C" else celsius * 9.0 / 5.0 + 32.0


def format_temp(celsius: float, unit: str, decimals: int = 0) -> str:
    """Format an absolute Celsius value in the active unit with a degree mark."""
    value = _no_neg_zero(convert_temp(celsius, unit), decimals)
    return f"{value:.{decimals}f}°{unit.upper()}"


def format_delta(celsius_delta: float, unit: str, decimals: int = 1) -> str:
    """Format a temperature difference (no +32 offset) with an explicit sign."""
    delta = celsius_delta if unit.upper() == "C" else celsius_delta * 9.0 / 5.0
    return f"{_no_neg_zero(delta, decimals):+.{decimals}f}°"


def format_wind(kmh: float, unit: str) -> str:
    """Format a wind speed in km/h or mph depending on the active unit."""
    return f"{kmh * KMH_TO_MPH:.0f} mph" if unit.upper() == "F" else f"{kmh:.0f} km/h"


def format_clock(moment: datetime) -> str:
    """Format a timestamp as a short local clock time."""
    return moment.strftime("%H:%M")


def weekday(moment: date) -> str:
    """Return a short weekday label such as ``Mon``."""
    return moment.strftime("%a")


def compass(degrees: float) -> str:
    """Convert a wind bearing in degrees to a 16-point compass label."""
    return COMPASS_POINTS[int((degrees % 360) / 22.5 + 0.5) % 16]


def confidence_phrase(spread: float) -> str:
    """Return just the confidence band for an ensemble spread in °C."""
    return next((name for limit, name in CONFIDENCE_BANDS if spread <= limit),
                "Low confidence")


def confidence_label(spread: float, models_ok: int, models_total: int) -> str:
    """Render the ensemble spread as a plain-language confidence sentence."""
    if models_ok <= 0:
        return f"No forecast models responded · 0 of {models_total}"
    if models_ok == 1:
        return f"Single-model estimate · 1 of {models_total} models responded"
    return f"{confidence_phrase(spread)} · {models_ok} models within {spread:.1f}°"