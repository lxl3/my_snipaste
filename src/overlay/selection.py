"""Overlay selection and hit-testing mixin."""

import math

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QFont, QFontMetrics, QColor

from ..core.constants import HANDLE_SIZE


class OverlaySelectionMixin:
    """Selection, hit-testing, and annotation dragging logic.

    Subclass must provide:
    - self.total_geometry (QRect)
    - self.selection_rect (QRect)
    - self.annotations (list[dict])
    - self._selected_annotation_idx (int | None)
    - self._annotation_drag_orig (dict)
    - self._drag_start_pos (QPointF)
    - self._drag_mode (tuple)
    - self.current_mouse_pos (QPoint)
    - self.current_tool (str)
    - self.toolbar (OverlayToolbar)
    - self._point_to_segment_distance (method from OverlayActionsMixin)
    - QWidget: update(), width(), height()
    """

    # ─── Selection helpers ───

    def _capture_pos(self) -> QPoint:
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

    def _sel_to_local(self, pos: QPoint) -> QPointF:
        return QPointF(pos - self.selection_rect.topLeft())

    # ─── Annotation hit-test & selection ───

    def _hit_test_annotation(self, pos: QPoint) -> int | None:
        """Return index of annotation at *pos* (topmost first), or None.
        Freehand annotations are excluded from selection entirely.
        For rect/ellipse: only detect border (Snipaste-style), not interior."""
        BORDER_THRESHOLD = 8  # pixels - distance from border to detect

        local = self._sel_to_local(QPointF(pos))
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann["type"]
            if t == "freehand":
                continue  # freehand is never selectable
            try:
                if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                    r = QRectF(ann["rect"])
                    # Check if point is near border (Snipaste-style)
                    if r.contains(local):
                        # Point is inside - check distance to nearest edge
                        dist_left = abs(local.x() - r.left())
                        dist_right = abs(local.x() - r.right())
                        dist_top = abs(local.y() - r.top())
                        dist_bottom = abs(local.y() - r.bottom())
                        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
                        if min_dist <= BORDER_THRESHOLD:
                            return i
                elif t in ("arrow", "line"):
                    d = self._point_to_segment_distance(local, ann["start"], ann["end"])
                    if d < 8:
                        return i
                elif t == "freehand":
                    pts = ann["points"]
                    for j in range(len(pts) - 1):
                        d = self._point_to_segment_distance(local, pts[j], pts[j + 1])
                        if d < 8:
                            return i
                elif t == "number_marker":
                    center = QPointF(ann["pos"])
                    r = ann.get("radius", 14)
                    if math.hypot(local.x() - center.x(), local.y() - center.y()) < r + 4:
                        return i
                elif t == "text":
                    fm = QFontMetrics(QFont(ann["font_family"], ann["font_size"]))
                    tw = fm.horizontalAdvance(ann["text"])
                    th = fm.height()
                    text_rect = QRectF(ann["pos"].x(), ann["pos"].y(), tw, th)
                    if text_rect.contains(local):
                        return i
            except Exception:
                continue
        return None

    def _select_annotation(self, idx: int, event_pos: QPointF) -> None:
        """Select annotation at *idx* and prepare for possible drag."""
        self._selected_annotation_idx = idx
        ann = self.annotations[idx]
        # Snapshot original position data for drag delta calculation
        self._annotation_drag_orig = {}
        t = ann["type"]
        if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
            self._annotation_drag_orig["rect"] = QRectF(ann["rect"])
        elif t in ("arrow", "line"):
            self._annotation_drag_orig["start"] = QPointF(ann["start"])
            self._annotation_drag_orig["end"] = QPointF(ann["end"])
        elif t == "freehand":
            self._annotation_drag_orig["points"] = [QPointF(p) for p in ann["points"]]
        elif t in ("text", "number_marker"):
            self._annotation_drag_orig["pos"] = QPointF(ann["pos"])
        self._drag_start_pos = event_pos
        self._drag_mode = ("move_annotation",)
        self.toolbar.toolbar.hide()
        self.update()

    def _deselect_annotation(self) -> None:
        self._selected_annotation_idx = None
        self._annotation_drag_orig = {}
        self.update()

    def _apply_property_to_selected(self, key: str, value) -> None:
        """Update a property on the currently selected annotation, if any."""
        if self._selected_annotation_idx is None:
            return
        ann = self.annotations[self._selected_annotation_idx]
        if key == "color" and "color" in ann:
            ann["color"] = QColor(value) if isinstance(value, str) else value
        elif key == "width" and "width" in ann:
            ann["width"] = value
        elif key == "blur_radius" and ann["type"] == "blur":
            ann["radius"] = value
            ann.pop("_cached", None)  # force re-render
        elif key == "magnifier_zoom" and ann["type"] == "magnifier":
            ann["zoom"] = value
            ann.pop("_cached", None)  # force re-render with new zoom
        elif key == "mosaic_scale" and ann["type"] == "mosaic":
            ann["scale"] = value
            ann.pop("_cached", None)  # force re-render with new scale
        elif key == "font_family" and ann["type"] == "text":
            ann["font_family"] = value
        elif key == "font_size" and ann["type"] == "text":
            ann["font_size"] = value
        elif key == "bold" and ann["type"] == "text":
            ann["bold"] = value
        elif key == "italic" and ann["type"] == "text":
            ann["italic"] = value
        elif key == "text_color" and ann["type"] == "text":
            ann["color"] = QColor(value) if isinstance(value, str) else value
        self.update()

    def _get_annotation_bounds_local(self, ann: dict) -> QRectF:
        """Bounding rect of an annotation in *local* (selection-relative) coords."""
        t = ann["type"]
        try:
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                return QRectF(ann["rect"])
            elif t in ("arrow", "line"):
                pts = [ann["start"], ann["end"]]
                xs = [p.x() for p in pts]
                ys = [p.y() for p in pts]
                margin = ann.get("width", 3) + 4
                return QRectF(min(xs) - margin, min(ys) - margin,
                              max(xs) - min(xs) + margin * 2,
                              max(ys) - min(ys) + margin * 2)
            elif t == "freehand":
                pts = ann["points"]
                if not pts:
                    return QRectF()
                margin = ann.get("width", 3) + 4
                xs = [p.x() for p in pts]
                ys = [p.y() for p in pts]
                return QRectF(min(xs) - margin, min(ys) - margin,
                              max(xs) - min(xs) + margin * 2,
                              max(ys) - min(ys) + margin * 2)
            elif t == "number_marker":
                r = ann.get("radius", 14)
                return QRectF(ann["pos"].x() - r, ann["pos"].y() - r, r * 2, r * 2)
            elif t == "text":
                fm = QFontMetrics(QFont(ann["font_family"], ann["font_size"]))
                tw = fm.horizontalAdvance(ann["text"])
                th = fm.height()
                return QRectF(ann["pos"].x(), ann["pos"].y(), tw, th)
        except Exception:
            pass
        return QRectF()

    def _move_selected_annotation(self, delta: QPointF) -> None:
        """Apply *delta* to the drag-origin snapshot of the selected annotation."""
        if self._selected_annotation_idx is None:
            return
        ann = self.annotations[self._selected_annotation_idx]
        t = ann["type"]
        orig = self._annotation_drag_orig
        if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier") and "rect" in orig:
            r = orig["rect"]
            ann["rect"] = QRectF(r.x() + delta.x(), r.y() + delta.y(),
                                  r.width(), r.height())
            # Invalidate cached render (position-dependent for blur/mosaic/magnifier)
            if t in ("mosaic", "blur", "magnifier"):
                ann.pop("_cached", None)
        elif t in ("arrow", "line") and "start" in orig and "end" in orig:
            ann["start"] = QPointF(orig["start"].x() + delta.x(),
                                    orig["start"].y() + delta.y())
            ann["end"] = QPointF(orig["end"].x() + delta.x(),
                                  orig["end"].y() + delta.y())
        elif t == "freehand" and "points" in orig:
            ann["points"] = [QPointF(p.x() + delta.x(), p.y() + delta.y())
                             for p in orig["points"]]
            ann.pop("_path", None)
        elif t in ("text", "number_marker") and "pos" in orig:
            ann["pos"] = QPointF(orig["pos"].x() + delta.x(),
                                  orig["pos"].y() + delta.y())

    # ─── Selection rectangle handle detection ───

    def _get_all_handles(self, rect: QRect) -> list[QRect]:
        half = HANDLE_SIZE // 2
        r = rect
        return [
            QRect(r.left() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.left() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.center().x() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.center().x() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.left() - half, r.center().y() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.center().y() - half, HANDLE_SIZE, HANDLE_SIZE),
        ]

    def _handle_at_pos(self, pos: QPoint) -> str | None:
        handles = self._get_all_handles(self.selection_rect)
        names = ["top-left", "top-right", "bottom-left", "bottom-right",
                 "top-center", "bottom-center", "left-center", "right-center"]
        for h_rect, name in zip(handles, names):
            if h_rect.contains(pos):
                return name
        return None

    def _cursor_for_handle(self, handle_name: str | None) -> Qt.CursorShape:
        if not handle_name:
            inside = self.selection_rect.contains(self.current_mouse_pos)
            if self.current_tool == "select" and inside:
                return Qt.SizeAllCursor
            return Qt.ArrowCursor if inside else Qt.CrossCursor
        mapping = {
            "top-left": Qt.SizeFDiagCursor, "bottom-right": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor, "bottom-left": Qt.SizeBDiagCursor,
            "top-center": Qt.SizeVerCursor, "bottom-center": Qt.SizeVerCursor,
            "left-center": Qt.SizeHorCursor, "right-center": Qt.SizeHorCursor,
        }
        return mapping.get(handle_name, Qt.ArrowCursor)

    # ─── Selection rectangle constraints ───

    def _constrain_rect_to_screen(self, rect: QRect) -> QRect:
        """限制矩形在屏幕范围内"""
        screen_width = self.width()
        screen_height = self.height()

        # 获取矩形的位置和尺寸
        x = max(0, rect.x())
        y = max(0, rect.y())
        w = min(rect.width(), screen_width - x)
        h = min(rect.height(), screen_height - y)

        # 如果矩形太小，设置最小尺寸
        MIN_SIZE = 10
        w = max(MIN_SIZE, w)
        h = max(MIN_SIZE, h)

        return QRect(x, y, w, h)
