"""Annotation data model.

Replaces the raw dict approach used in both overlay and pin_window
with a typed dataclass.  All coordinate data is stored as QPointF/QRectF
(the canonical form); hex strings for colors ensure serialisability.

Callers construct Annotation instances directly.  Use ``to_dict()`` /
``from_dict()`` when round-tripping through JSON or tuple-based storage
(the pin_window convention).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainterPath, QPixmap

# ── Annotation types ────────────────────────────────────────────

ANN_TYPE_RECT = "rect"
ANN_TYPE_ELLIPSE = "ellipse"
ANN_TYPE_ARROW = "arrow"
ANN_TYPE_LINE = "line"
ANN_TYPE_FREEHAND = "freehand"
ANN_TYPE_TEXT = "text"
ANN_TYPE_HIGHLIGHTER = "highlighter"
ANN_TYPE_NUMBER_MARKER = "number_marker"
ANN_TYPE_MOSAIC = "mosaic"
ANN_TYPE_BLUR = "blur"
ANN_TYPE_MAGNIFIER = "magnifier"

# ── Helper for mutable defaults ──────────────────────────────────


def _rect() -> QRectF:
    return QRectF()


def _point() -> QPointF:
    return QPointF()


# ── Annotation model ─────────────────────────────────────────────


@dataclass
class Annotation:
    """Unified annotation model.

    Every annotation type shares this single dataclass.  Fields that
    don't apply to a particular type are simply left at their default.

    ``color`` and ``text_color`` are always stored as hex strings
    (e.g. ``"#ff0000"``) so the object is trivially serialisable.
    Callers that need a ``QColor`` can call ``QColor(ann.color)``.

    The ``_path`` / ``_cached`` fields are rendering caches that are
    *not* considered by ``__eq__``, ``__hash__`` or ``to_dict()``.
    """

    # ── discriminator ────────────────────────────────────────
    type: str = ""

    # ── common shape / line properties ────────────────────────
    color: str = "#ff0000"
    width: int = 3

    # ── shape annotations (rect, ellipse, highlighter) ────────
    rect: QRectF | None = None

    # ── line annotations (arrow, line) ────────────────────────
    start: QPointF | None = None
    end: QPointF | None = None
    arrow_style: str = "solid"

    # ── freehand ──────────────────────────────────────────────
    points: list[QPointF] | None = None

    # ── text ──────────────────────────────────────────────────
    pos: QPointF | None = None
    text: str = ""
    font_family: str = "sans-serif"
    font_size: int = 20
    bold: bool = False
    italic: bool = False

    # ── number marker ─────────────────────────────────────────
    number: int = 1
    text_color: str = "#ffffff"
    radius: int = 14

    # ── effect parameters ─────────────────────────────────────
    scale: int = 8          # mosaic pixelation factor
    blur_radius: int = 10   # Gaussian-blur radius
    zoom: float = 2.0       # magnifier zoom factor

    # ── rendering cache (excluded from eq / repr / dict) ──────
    _path: QPainterPath | None = field(default=None, repr=False, compare=False)
    _cached: QPixmap | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Normalise coordinate and colour fields after construction.

        The constructor accepts both QRectF/QPointF objects (overlay
        style) and plain tuples (pin_window style) — normalise to the
        canonical PySide6 types so downstream code can always call
        ``QRectF(ann.rect)`` / ``QPointF(ann.pos)`` safely.
        """
        # ── coordinates ──────────────────────────────────────
        if self.rect is not None:
            self.rect = _parse_rect(self.rect)
        if self.start is not None:
            self.start = _parse_point(self.start)
        if self.end is not None:
            self.end = _parse_point(self.end)
        if self.pos is not None:
            self.pos = _parse_point(self.pos)
        if self.points is not None:
            self.points = _parse_points(self.points)
        # ── colours ───────────────────────────────────────────
        self.color = _parse_color(self.color)
        self.text_color = _parse_color(self.text_color)

    # ── bounds ────────────────────────────────────────────────

    def bounds(self) -> QRectF:
        """Bounding rectangle of this annotation (local coords)."""
        t = self.type
        try:
            if t in (ANN_TYPE_RECT, ANN_TYPE_ELLIPSE,
                     ANN_TYPE_HIGHLIGHTER, ANN_TYPE_MOSAIC,
                     ANN_TYPE_BLUR, ANN_TYPE_MAGNIFIER):
                return QRectF(self.rect) if self.rect else QRectF()

            if t in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
                if self.start and self.end:
                    r = QRectF(self.start, self.end).normalized()
                    margin = self.width + 4
                    return r.adjusted(-margin, -margin, margin, margin)
                return QRectF()

            if t == ANN_TYPE_FREEHAND:
                pts = self.points or []
                if not pts:
                    return QRectF()
                xs = [p.x() for p in pts]
                ys = [p.y() for p in pts]
                margin = self.width + 4
                return QRectF(min(xs) - margin, min(ys) - margin,
                              max(xs) - min(xs) + margin * 2,
                              max(ys) - min(ys) + margin * 2)

            if t == ANN_TYPE_NUMBER_MARKER:
                p = self.pos or QPointF()
                r = self.radius
                return QRectF(p.x() - r, p.y() - r, r * 2, r * 2)

            if t == ANN_TYPE_TEXT:
                p = self.pos or QPointF()
                fm = QFontMetrics(QFont(self.font_family, self.font_size))
                tw = fm.horizontalAdvance(self.text)
                th = fm.height()
                return QRectF(p.x(), p.y(), tw, th)
        except Exception:
            pass
        return QRectF()

    # ── hit testing ───────────────────────────────────────────

    def contains(self, point: QPointF, border_threshold: int = 8) -> bool:
        """Check whether *point* hits this annotation.

        The semantics follow Snipaste-style: for shape annotations
        (rect, ellipse) only clicks near the border count; for
        line/freehand the distance to the segment is considered.

        Returns ``True`` when the point is considered "on" the
        annotation.
        """
        t = self.type
        try:
            if t in (ANN_TYPE_RECT, ANN_TYPE_ELLIPSE,
                     ANN_TYPE_HIGHLIGHTER, ANN_TYPE_MOSAIC,
                     ANN_TYPE_BLUR, ANN_TYPE_MAGNIFIER):
                return self._contains_border(point, border_threshold)

            if t in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
                return self._contains_segment(point, border_threshold + 4)

            if ANN_TYPE_FREEHAND:
                pts = self.points or []
                for i in range(len(pts) - 1):
                    if _point_segment_distance(point, pts[i], pts[i + 1]) < 8:
                        return True
                return False

            if t == ANN_TYPE_NUMBER_MARKER:
                c = self.pos or QPointF()
                r = self.radius
                return math.hypot(point.x() - c.x(), point.y() - c.y()) < r + 4

            if t == ANN_TYPE_TEXT:
                p = self.pos or QPointF()
                fm = QFontMetrics(QFont(self.font_family, self.font_size))
                tw = fm.horizontalAdvance(self.text)
                th = fm.height()
                return QRectF(p.x(), p.y(), tw, th).contains(point)
        except Exception:
            pass
        return False

    def _contains_border(self, point: QPointF, threshold: int) -> bool:
        r = QRectF(self.rect) if self.rect else QRectF()
        if not r.contains(point):
            return False
        d = min(
            abs(point.x() - r.left()), abs(point.x() - r.right()),
            abs(point.y() - r.top()), abs(point.y() - r.bottom()),
        )
        return d <= threshold

    def _contains_segment(self, point: QPointF, threshold: int) -> bool:
        s = self.start or QPointF()
        e = self.end or QPointF()
        return _point_segment_distance(point, s, e) < threshold

    # ── translation ───────────────────────────────────────────

    def translate(self, dx: float, dy: float) -> None:
        """Move this annotation by ``(dx, dy)``."""
        t = self.type
        if t in (ANN_TYPE_RECT, ANN_TYPE_ELLIPSE,
                 ANN_TYPE_HIGHLIGHTER, ANN_TYPE_MOSAIC,
                 ANN_TYPE_BLUR, ANN_TYPE_MAGNIFIER):
            if self.rect:
                self.rect = QRectF(
                    self.rect.x() + dx, self.rect.y() + dy,
                    self.rect.width(), self.rect.height(),
                )
            self.invalidate_cache()
        elif t in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
            if self.start:
                self.start = QPointF(self.start.x() + dx, self.start.y() + dy)
            if self.end:
                self.end = QPointF(self.end.x() + dx, self.end.y() + dy)
        elif t == ANN_TYPE_FREEHAND:
            if self.points:
                self.points = [QPointF(p.x() + dx, p.y() + dy) for p in self.points]
            self._path = None
        elif t in (ANN_TYPE_TEXT, ANN_TYPE_NUMBER_MARKER):
            if self.pos:
                self.pos = QPointF(self.pos.x() + dx, self.pos.y() + dy)

    # ── resize ────────────────────────────────────────────────

    def resize_rect(self, handle: str, dx: float, dy: float, orig_rect: QRectF) -> None:
        """Resize a rect-based annotation by moving *handle*.

        *handle* is one of ``"tl"``, ``"tr"``, ``"bl"``, ``"br"``,
        ``"tc"``, ``"bc"``, ``"lc"``, ``"rc"``.
        """
        r = QRectF(orig_rect)
        if handle == "tl":
            r.setLeft(r.left() + dx)
            r.setTop(r.top() + dy)
        elif handle == "tr":
            r.setRight(r.right() + dx)
            r.setTop(r.top() + dy)
        elif handle == "bl":
            r.setLeft(r.left() + dx)
            r.setBottom(r.bottom() + dy)
        elif handle == "br":
            r.setRight(r.right() + dx)
            r.setBottom(r.bottom() + dy)
        elif handle == "tc":
            r.setTop(r.top() + dy)
        elif handle == "bc":
            r.setBottom(r.bottom() + dy)
        elif handle == "lc":
            r.setLeft(r.left() + dx)
        elif handle == "rc":
            r.setRight(r.right() + dx)
        self.rect = r.normalized()
        self.invalidate_cache()

    def resize_line(self, handle: str, dx: float, dy: float,
                    orig_start: QPointF, orig_end: QPointF) -> None:
        """Move one endpoint of an arrow/line annotation."""
        if handle == "start":
            self.start = QPointF(orig_start.x() + dx, orig_start.y() + dy)
        elif handle == "end":
            self.end = QPointF(orig_end.x() + dx, orig_end.y() + dy)

    def resize_number_marker(self, handle: str, dx: float, dy: float,
                             orig_pos: QPointF, orig_radius: int) -> None:
        """Resize a number marker: corner handles change radius, edge handles move."""
        if handle in ("tl", "tr", "bl", "br"):
            diag = max(abs(dx), abs(dy))
            sign = 1 if (dx + dy) > 0 else -1
            self.radius = max(4, int(orig_radius + sign * diag))
        else:
            self.pos = QPointF(orig_pos.x() + dx, orig_pos.y() + dy)

    # ── cache ─────────────────────────────────────────────────

    def invalidate_cache(self) -> None:
        """Clear rendering caches, forcing re-render on next paint."""
        self._path = None
        self._cached = None

    # ── serialisation ─────────────────────────────────────────

    def to_dict(self, *, use_hex_color: bool = True) -> dict[str, Any]:
        """Convert to a plain dict suitable for JSON / tuple-storage.

        Parameters
        ----------
        use_hex_color:
            When True (default), colours are hex strings (e.g.
            ``"#ff0000"``).  When False, the original dict convention
            of storing raw ``QColor`` objects is used (overlay style).
        """
        d: dict[str, Any] = {"type": self.type}

        def _store_color(val: str):
            return val if use_hex_color else QColor(val)

        d["color"] = _store_color(self.color)

        if self.type in (ANN_TYPE_RECT, ANN_TYPE_ELLIPSE,
                         ANN_TYPE_HIGHLIGHTER, ANN_TYPE_MOSAIC,
                         ANN_TYPE_BLUR, ANN_TYPE_MAGNIFIER):
            d["rect"] = _rect_to_tuple(self.rect)
            d["width"] = self.width
            if self.type == ANN_TYPE_MOSAIC:
                d["scale"] = self.scale
            elif self.type == ANN_TYPE_BLUR:
                d["radius"] = self.blur_radius
            elif self.type == ANN_TYPE_MAGNIFIER:
                d["zoom"] = self.zoom

        elif self.type in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
            d["start"] = _point_to_tuple(self.start)
            d["end"] = _point_to_tuple(self.end)
            d["width"] = self.width
            d["arrow_style"] = self.arrow_style

        elif self.type == ANN_TYPE_FREEHAND:
            pts = self.points or []
            d["points"] = [_point_to_tuple(p) for p in pts]
            d["width"] = self.width

        elif self.type == ANN_TYPE_TEXT:
            d["pos"] = _point_to_tuple(self.pos)
            d["text"] = self.text
            d["color"] = _store_color(self.color)
            d["font_family"] = self.font_family
            d["font_size"] = self.font_size
            d["bold"] = self.bold
            d["italic"] = self.italic

        elif self.type == ANN_TYPE_NUMBER_MARKER:
            d["pos"] = _point_to_tuple(self.pos)
            d["color"] = _store_color(self.color)
            d["text_color"] = _store_color(self.text_color)
            d["number"] = self.number
            d["radius"] = self.radius

        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Annotation:
        """Create an Annotation from a raw dict (overlay or pin_window format).

        Supports both Qt-object format (QRectF, QPointF, QColor) and
        tuple/hex-string format used by PinWindow.
        """
        t = data.get("type", "")
        ann = cls(type=t)

        if t in (ANN_TYPE_RECT, ANN_TYPE_ELLIPSE,
                 ANN_TYPE_HIGHLIGHTER, ANN_TYPE_MOSAIC,
                 ANN_TYPE_BLUR, ANN_TYPE_MAGNIFIER):
            ann.rect = _parse_rect(data.get("rect"))
            ann.width = data.get("width", 3)
            if t == ANN_TYPE_MOSAIC:
                ann.scale = data.get("scale", ann.scale)
            elif t == ANN_TYPE_BLUR:
                ann.blur_radius = data.get("radius", ann.blur_radius)
            elif t == ANN_TYPE_MAGNIFIER:
                ann.zoom = data.get("zoom", ann.zoom)

        elif t in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
            ann.start = _parse_point(data.get("start"))
            ann.end = _parse_point(data.get("end"))
            ann.width = data.get("width", 3)
            ann.arrow_style = data.get("arrow_style", "solid")

        elif t == ANN_TYPE_FREEHAND:
            ann.points = _parse_points(data.get("points", []))
            ann.width = data.get("width", 3)

        elif t == ANN_TYPE_TEXT:
            ann.pos = _parse_point(data.get("pos"))
            ann.text = data.get("text", "")
            ann.font_family = data.get("font_family", "sans-serif")
            ann.font_size = data.get("font_size", 20)
            ann.bold = data.get("bold", False)
            ann.italic = data.get("italic", False)

        elif t == ANN_TYPE_NUMBER_MARKER:
            ann.pos = _parse_point(data.get("pos"))
            ann.number = data.get("number", 1)
            ann.radius = data.get("radius", 14)

        # colour parsing (handles both QColor and hex string)
        color_val = data.get("color")
        if color_val is not None:
            ann.color = _parse_color(color_val)
        text_color_val = data.get("text_color")
        if text_color_val is not None:
            ann.text_color = _parse_color(text_color_val)

        return ann

    # ── cloning ───────────────────────────────────────────────

    def clone(self) -> Annotation:
        """Return an independent copy (caches excluded)."""
        a = copy.deepcopy(self)
        a._path = None
        a._cached = None
        return a


# ── Internal helpers ──────────────────────────────────────────────


def _parse_rect(val: Any) -> QRectF:
    if isinstance(val, QRectF):
        return QRectF(val)
    if isinstance(val, (list, tuple)) and len(val) == 4:
        return QRectF(val[0], val[1], val[2], val[3])
    return QRectF()


def _parse_point(val: Any) -> QPointF:
    if isinstance(val, QPointF):
        return QPointF(val)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return QPointF(float(val[0]), float(val[1]))
    return QPointF()


def _parse_points(val: Any) -> list[QPointF]:
    if not val:
        return []
    result: list[QPointF] = []
    for p in val:
        if isinstance(p, QPointF):
            result.append(QPointF(p))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            result.append(QPointF(float(p[0]), float(p[1])))
    return result


def _parse_color(val: Any) -> str:
    if isinstance(val, QColor):
        return val.name()
    return str(val)


def _rect_to_tuple(val: QRectF | tuple | None) -> tuple[float, float, float, float]:
    """Normalise a rect (QRectF or tuple) to output tuple."""
    if isinstance(val, QRectF):
        return (val.x(), val.y(), val.width(), val.height())
    if isinstance(val, (list, tuple)) and len(val) == 4:
        return (float(val[0]), float(val[1]), float(val[2]), float(val[3]))
    return (0.0, 0.0, 0.0, 0.0)


def _point_to_tuple(val: QPointF | tuple | None) -> tuple[float, float]:
    """Normalise a point (QPointF or tuple) to output tuple."""
    if isinstance(val, QPointF):
        return (val.x(), val.y())
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return (float(val[0]), float(val[1]))
    return (0.0, 0.0)


def _point_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    """Shortest distance from point *p* to line segment *a*-*b*."""
    ax, ay = a.x(), a.y()
    bx, by = b.x(), b.y()
    px, py = p.x(), p.y()

    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nx = ax + t * dx
    ny = ay + t * dy
    return math.hypot(px - nx, py - ny)
