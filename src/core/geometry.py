"""Shared geometry utilities for hit-testing, crop handles, and point-to-segment distance."""

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt


def point_to_segment_distance(point: QPointF, a: QPointF, b: QPointF) -> float:
    """Euclidean distance from *point* to the line segment a–b."""
    dx = b.x() - a.x()
    dy = b.y() - a.y()
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(point.x() - a.x(), point.y() - a.y())
    t = max(0, min(1, ((point.x() - a.x()) * dx + (point.y() - a.y()) * dy) / length_sq))
    proj_x = a.x() + t * dx
    proj_y = a.y() + t * dy
    return math.hypot(point.x() - proj_x, point.y() - proj_y)


# ─── Crop handle helpers ─────────────────────────────────────────

HANDLE_SIZE = 8

_HANDLE_NAMES = ("nw", "ne", "sw", "se")
_CURSOR_MAP: dict[str, Qt.CursorShape] = {
    "nw": Qt.SizeFDiagCursor,
    "se": Qt.SizeFDiagCursor,
    "ne": Qt.SizeBDiagCursor,
    "sw": Qt.SizeBDiagCursor,
    "move": Qt.SizeAllCursor,
}


def get_crop_handle(rect: QRectF, pos: QPointF, handle_size: int = HANDLE_SIZE) -> str:
    """Return the crop handle name at *pos*, or ``""`` / ``"move"``."""
    if rect.isNull() or rect.isEmpty():
        return ""
    hs = handle_size
    for name in _HANDLE_NAMES:
        corner = getattr(rect, f"{name}")() if hasattr(rect, name) else _corner(rect, name)
        handle_rect = QRectF(
            corner.x() - hs / 2, corner.y() - hs / 2, hs, hs
        )
        if handle_rect.contains(pos):
            return name
    return "move" if rect.contains(pos) else ""


def _corner(rect: QRectF, name: str) -> QPointF:
    return {
        "nw": rect.topLeft(),
        "ne": rect.topRight(),
        "sw": rect.bottomLeft(),
        "se": rect.bottomRight(),
    }[name]


def cursor_for_crop_handle(handle: str) -> Qt.CursorShape:
    return _CURSOR_MAP.get(handle, Qt.CrossCursor)


def resize_crop_rect(rect: QRectF, handle: str, pos: QPointF) -> QRectF:
    """Resize *rect* from *handle* toward *pos*, returning normalized rect."""
    r = QRectF(rect)
    if handle == "nw":
        r.setTopLeft(pos)
    elif handle == "ne":
        r.setTopRight(pos)
    elif handle == "sw":
        r.setBottomLeft(pos)
    elif handle == "se":
        r.setBottomRight(pos)
    return r.normalized()


def draw_crop_handles(painter: QPainter, rect: QRectF, handle_size: int = HANDLE_SIZE) -> None:
    """Draw white square handles at the four corners of *rect*."""
    hs = handle_size
    painter.setPen(QPen(Qt.white, 1))
    painter.setBrush(Qt.white)
    for corner in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
        x, y = int(corner.x() - hs / 2), int(corner.y() - hs / 2)
        painter.fillRect(x, y, hs, hs, Qt.white)
        painter.drawRect(x, y, hs, hs)
