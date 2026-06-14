"""Eraser mixin for PinWindow.

Provides annotation erasing logic that can be reused across
different pin window implementations.
"""

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont, QFontMetrics

from ...core.logger import setup_logger

logger = setup_logger("pin_eraser")


class PinWindowEraserMixin:
    """Eraser logic for pin window.

    Contract (resolved at runtime on PinWindow):
        State:
            annotations (list), eraser_size (int)
            _selected_annotation_index (int)
            _undo_stack (list), _redo_stack (list)
            _toolbar_obj (OverlayToolbar)
        Methods:
            _deselect_annotation(), _update_toolbar_undo_redo(), update()
    """

    def _on_annotation_removed(self, removed_idx: int) -> None:
        """Update selection state when an annotation is removed by index."""
        sel = getattr(self, '_selected_annotation_index', None)
        if sel is None:
            return
        if sel == removed_idx:
            self._deselect_annotation()
        elif sel > removed_idx:
            self._selected_annotation_index = sel - 1

    @staticmethod
    def _point_to_rect_distance(point: QPointF, rect: QRectF) -> float:
        """Calculate minimum distance from a point to a rectangle."""
        cx = max(rect.left(), min(point.x(), rect.right()))
        cy = max(rect.top(), min(point.y(), rect.bottom()))
        return math.hypot(point.x() - cx, point.y() - cy)

    @staticmethod
    def _point_to_segment_distance(point: QPointF, p1: QPointF, p2: QPointF) -> float:
        """Calculate minimum distance from a point to a line segment."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return math.hypot(point.x() - p1.x(), point.y() - p1.y())
        t = max(0, min(1, ((point.x() - p1.x()) * dx + (point.y() - p1.y()) * dy) / length_sq))
        proj_x = p1.x() + t * dx
        proj_y = p1.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

    def _try_erase_annotation(self, pos: QPointF) -> None:
        """Try to erase annotation at the given position."""
        r = self.eraser_size
        logger.debug(f"擦除检测: pos=({pos.x():.0f},{pos.y():.0f}), r={r}, annotations={len(self.annotations)}")
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann.type
            if t in ("rect", "ellipse", "mosaic", "blur", "magnifier"):
                ann_rect = ann.rect
                d = self._point_to_rect_distance(pos, ann_rect)
                logger.debug(f"  [{i}] type={t}, rect={ann_rect}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 annotation {i} (type={t})")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self._update_toolbar_undo_redo()
                    self.update()
                    return
            elif t in ("arrow", "line"):
                start = ann.start
                end = ann.end
                d = self._point_to_segment_distance(pos, start, end)
                logger.debug(f"  [{i}] type={t}, start={start}, end={end}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 annotation {i} (type={t})")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self._update_toolbar_undo_redo()
                    self.update()
                    return
            elif t == "freehand":
                pts = ann.points
                for j in range(len(pts) - 1):
                    p1 = pts[j]
                    p2 = pts[j + 1]
                    d = self._point_to_segment_distance(pos, p1, p2)
                    if d < r:
                        logger.debug(f"  → 擦除 freehand[{i}] segment {j}, dist={d:.1f}")
                        self._on_annotation_removed(i)
                        removed = self.annotations.pop(i)
                        self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                        self._redo_stack.clear()
                        self._update_toolbar_undo_redo()
                        self.update()
                        return
            elif t == "text":
                font = QFont(ann.font_family, ann.font_size)
                font.setBold(ann.bold)
                font.setItalic(ann.italic)
                fm = QFontMetrics(font)
                tw = fm.horizontalAdvance(ann.text)
                th = fm.height()
                text_pos = ann.pos
                text_rect = QRectF(text_pos.x(), text_pos.y(), tw, th)
                d = self._point_to_rect_distance(pos, text_rect)
                logger.debug(f"  [{i}] type=text, pos={ann.pos}, text_rect={text_rect}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 text annotation {i}")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self._update_toolbar_undo_redo()
                    self.update()
                    return
            elif t == "number_marker":
                center = ann.pos
                radius = ann.radius
                d = math.hypot(pos.x() - center.x(), pos.y() - center.y())
                logger.debug(f"  [{i}] type=number_marker, center={center}, dist={d:.1f}")
                if d < r + radius:
                    logger.debug(f"  → 擦除 number_marker {i}")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self._update_toolbar_undo_redo()
                    self.update()
                    return
        logger.debug("  → 未命中任何标注")
