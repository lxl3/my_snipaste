"""Unified annotation editor.

Provides hit-testing, handle management, resize, and move operations
for ``Annotation`` objects.  Both the overlay and pin_window can use
this instead of duplicating the logic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRect, QRectF, Qt

from ..core.constants import HANDLE_SIZE
from .models import ANN_TYPE_ARROW, ANN_TYPE_FREEHAND, ANN_TYPE_LINE, Annotation

BORDER_THRESHOLD = 8  # pixels — distance from border to detect for shapes

# 8-handle name order (matching handle rect order)
_HANDLE_NAMES = ["tl", "tr", "bl", "br", "tc", "bc", "lc", "rc"]


# ── hit testing ──────────────────────────────────────────────────


def hit_test(annotations: Sequence[Annotation],
             point: QPointF) -> int | None:
    """Return the index of the topmost annotation at *point*, or ``None``.

    Freehand annotations are excluded (Snipaste-style behaviour).
    """
    for i in range(len(annotations) - 1, -1, -1):
        ann = annotations[i]
        if ann.type == ANN_TYPE_FREEHAND:
            continue
        if ann.contains(point, BORDER_THRESHOLD):
            return i
    return None


# ── handle management ────────────────────────────────────────────


def get_handles(ann: Annotation,
                offset: QPointF = QPointF()) -> list[QRect]:
    """Return resize handle rects in screen coords.

    For arrow/line: 2 handles at start and end points.
    For everything else: 8 handles (4 corners + 4 edge midpoints).
    """
    half = HANDLE_SIZE // 2

    if ann.type in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
        sp = QPointF(ann.start) + offset
        ep = QPointF(ann.end) + offset
        return [
            QRect(int(sp.x()) - half, int(sp.y()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(ep.x()) - half, int(ep.y()) - half, HANDLE_SIZE, HANDLE_SIZE),
        ]

    bounds = ann.bounds()
    if bounds.isNull():
        return []
    gb = bounds.translated(offset)
    return [
        QRect(int(gb.left()) - half, int(gb.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.right()) - half, int(gb.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.left()) - half, int(gb.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.right()) - half, int(gb.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.center().x()) - half, int(gb.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.center().x()) - half, int(gb.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.left()) - half, int(gb.center().y()) - half, HANDLE_SIZE, HANDLE_SIZE),
        QRect(int(gb.right()) - half, int(gb.center().y()) - half, HANDLE_SIZE, HANDLE_SIZE),
    ]


def get_handle_names(ann: Annotation) -> list[str]:
    """Handle names matching the output order of :func:`get_handles`."""
    if ann.type in (ANN_TYPE_ARROW, ANN_TYPE_LINE):
        return ["start", "end"]
    return list(_HANDLE_NAMES)


def handle_at_pos(ann: Annotation, pos: QPointF,
                  offset: QPointF = QPointF()) -> str | None:
    """Return the handle name at *pos*, or ``None``."""
    handles = get_handles(ann, offset)
    names = get_handle_names(ann)
    for hr, name in zip(handles, names):
        if hr.contains(pos.toPoint()):
            return name
    return None


# ── cursor mapping ────────────────────────────────────────────────


_HANDLE_CURSORS: dict[str, Qt.CursorShape] = {
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    "tc": Qt.SizeVerCursor, "bc": Qt.SizeVerCursor,
    "lc": Qt.SizeHorCursor, "rc": Qt.SizeHorCursor,
    "start": Qt.SizeVerCursor, "end": Qt.SizeVerCursor,
}


def cursor_for_handle(name: str | None) -> Qt.CursorShape:
    """Cursor shape for the given handle name."""
    return _HANDLE_CURSORS.get(name or "", Qt.ArrowCursor)


# ── annotation bounds for selection indicator ────────────────────


def selection_bounds(ann: Annotation) -> QRectF:
    """Return bounding rect expanded slightly to include line width margin."""
    b = ann.bounds()
    if b.isNull():
        return b
    return b.adjusted(-4, -4, 4, 4)


# ── helper: point-to-segment distance ────────────────────────────


def _point_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    """Shortest distance from *p* to the line segment *a*-*b*."""
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
