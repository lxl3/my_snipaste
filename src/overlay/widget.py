"""Full-screen overlay for area selection, annotation, and event handling.

Composed of CaptureOverlay (main class) + 3 mixins:
- OcrMixin              — OCR progress / cancellation
- OverlayRenderingMixin — annotation rendering
- OverlayActionsMixin   — actions / text editing
"""

import math
import os
from PySide6.QtWidgets import QWidget, QApplication, QLineEdit
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, Signal, QEvent, QTimer

from ..core.utils import capture_all_screens
from ..core.settings import get_settings
from .toolbar import OverlayToolbar
from .rendering import OverlayRenderingMixin
from .actions import OverlayActionsMixin
from .ocr_mixin import OcrMixin
from .hotkey_panel import HotkeyHelpPanel
from ..core.constants import (
    DEFAULT_ANNOTATION_COLOR, SELECTION_BORDER_COLOR, DIM_OVERLAY_COLOR,
    HANDLE_SIZE, MIN_SELECTION_SIZE, MIN_DRAW_THRESHOLD,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_LINE_WIDTH,
)
from ..core.i18n import _
from ..core.logger import setup_logger

logger = setup_logger("overlay")

# Toolbar fixed dimensions
TOOLBAR_FIXED_WIDTH = 420  # px - 足够容纳最宽的工具菜单
TOOLBAR_FIXED_HEIGHT = 32  # px - 标准工具栏高度


class CaptureOverlay(QWidget, OcrMixin, OverlayRenderingMixin, OverlayActionsMixin):
    """Full-screen semi-transparent overlay with selection, annotation, and OCR."""

    pin_requested = Signal(object, object)
    copy_requested = Signal(object)
    save_requested = Signal(object, bool)  # (pixmap, has_annotations)

    def __init__(self) -> None:
        super().__init__()

        self.total_geometry: QRect = QRect()
        for screen in QApplication.screens():
            self.total_geometry = self.total_geometry.united(screen.geometry())

        logger.info(f"init overlay, screen: {self.total_geometry}")
        # Check if cursor should be included
        s = get_settings()
        include_cursor = s.capture_cursor
        self.full_screenshot = capture_all_screens(include_cursor=include_cursor)
        logger.debug(f"screenshot size: {self.full_screenshot.width()}x{self.full_screenshot.height()}")

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(self.total_geometry)
        self.setCursor(Qt.CrossCursor)

        self.is_selecting: bool = False
        self.start_point: QPoint = QPoint()
        self.end_point: QPoint = QPoint()
        self.selection_rect: QRect = QRect()
        self.current_mouse_pos: QPoint = QPoint()

        self._drag_mode: tuple | None = None
        self._drag_start_pos: QPointF = QPointF()
        self._drag_start_rect: QRect = QRect()

        # Restore tool settings from memory
        s = get_settings()
        self.current_tool: str = s.last_tool

        # Restore tool-specific settings
        tool_settings = s.get_tool_settings(self.current_tool)
        if tool_settings:
            # Restore color if saved
            saved_color = tool_settings.get("color")
            if saved_color:
                color = QColor(saved_color)
                self.current_color: QColor = color if color.isValid() else QColor(s.default_color)
            else:
                self.current_color: QColor = QColor(s.default_color)
            # Restore width if saved
            self.current_width: int = tool_settings.get("width", s.default_line_width)
        else:
            # No saved settings, use defaults
            self.current_color: QColor = QColor(s.default_color)
            self.current_width: int = s.default_line_width
        self.current_blur_radius: int = 10
        self.current_magnifier_zoom: int = 2
        self.current_mosaic_scale: int = 8
        self.annotations: list[dict] = []
        self._undo_stack: list[dict] = []  # action history for undo
        self._redo_stack: list[dict] = []  # reversed actions for redo
        self._drawing: bool = False
        self._draw_start: QPointF = QPointF()
        self._draw_points: list[QPointF] = []
        self._preview_annotation: dict | None = None

        self.eraser_size: int = 20
        self._eraser_target_size: int = 20
        self._eraser_size_animating: bool = False
        self._erasing: bool = False
        self._closing_on_release: bool = False  # 标记右键释放时关闭

        self._erase_fill_rect_start: QPoint | None = None
        self._erase_fill_rect_current: QPoint | None = None

        self._text_editor: QLineEdit | None = None
        self._text_editor_pos: QPointF | None = None
        self._editing_annotation_idx: int | None = None  # non-None when re-editing existing text

        # ─── Annotation selection / editing state ───
        self._selected_annotation_idx: int | None = None
        self._annotation_drag_orig: dict = {}  # original position data for drag

        self.text_font_family: str = s.default_font_family
        self.text_font_size: int = s.default_font_size
        self.text_bold: bool = False
        self.text_italic: bool = False
        self.text_color: QColor = QColor(s.default_color)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.toolbar = OverlayToolbar(self)
        self.toolbar.setup()

        # Update toolbar UI to reflect the restored tool
        if self.current_tool in self.toolbar._tool_btns:
            for tid, btn in self.toolbar._tool_btns.items():
                btn.setChecked(tid == self.current_tool)

        self.grabKeyboard()

        self._hotkey_panel = None

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
        x = rect.x()
        y = rect.y()
        w = rect.width()
        h = rect.height()

        # 限制位置（确保左上角在屏幕内）
        x = max(0, min(x, screen_width - w))
        y = max(0, min(y, screen_height - h))

        # 限制尺寸（如果矩形超出屏幕，裁剪尺寸）
        if x + w > screen_width:
            w = screen_width - x
        if y + h > screen_height:
            h = screen_height - y

        return QRect(x, y, max(1, w), max(1, h))

    # ─── Toolbar positioning ───

    def _position_toolbar(self) -> None:
        """Position toolbar at bottom-right of selection (right-aligned)."""
        rect = self.selection_rect
        if rect.isNull():
            self.toolbar.toolbar.hide()
            return

        # 使用固定尺寸（不调用 adjustSize）
        tw = TOOLBAR_FIXED_WIDTH
        th = TOOLBAR_FIXED_HEIGHT
        self.toolbar.toolbar.setFixedSize(tw, th)

        screen_width = self.width()
        screen_height = self.height()

        # 默认位置：右下角对齐
        x = rect.right() - tw
        y = rect.bottom() + 8

        # 垂直方向：如果底部超出，移到上方
        if y + th > screen_height:
            y = rect.top() - th - 8
            # 如果上方也超出，则放在选区内部顶部
            if y < 0:
                y = max(0, rect.top() + 8)

        # 水平方向：处理工具栏宽度大于选区的情况
        if tw > rect.width():
            # 工具栏比选区宽：居中对齐选区，但确保不超出屏幕
            x = rect.center().x() - tw // 2
            # 确保完全可见
            x = max(0, min(x, screen_width - tw))
        else:
            # 工具栏比选区窄：右对齐
            x = rect.right() - tw
            # 处理左侧超出
            if x < 0:
                x = rect.left()
                # 如果左对齐还超出，贴齐屏幕左侧
                if x < 0:
                    x = 0
            # 处理右侧超出
            if x + tw > screen_width:
                x = screen_width - tw

        self.toolbar.toolbar.move(x, y)
        self.toolbar.toolbar.show()
        self.toolbar.toolbar.raise_()

    # ─── Painting ───

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.full_screenshot)

        rect = self.selection_rect
        if not rect.isNull():
            # 4 semi-transparent dimming strips around the selection
            w = self.width()
            h = self.height()
            painter.fillRect(0, 0, w, rect.top(), DIM_OVERLAY_COLOR)
            painter.fillRect(0, rect.bottom() + 1, w, h - rect.bottom() - 1, DIM_OVERLAY_COLOR)
            painter.fillRect(0, rect.top(), rect.left(), rect.height(), DIM_OVERLAY_COLOR)
            painter.fillRect(rect.right() + 1, rect.top(), w - rect.right() - 1, rect.height(), DIM_OVERLAY_COLOR)

            self._draw_annotations(painter, rect.size(), rect.topLeft())

            # Selection indicator for selected annotation
            if self._selected_annotation_idx is not None:
                try:
                    ann = self.annotations[self._selected_annotation_idx]
                    self._draw_selection_indicator(painter, ann, rect.topLeft())
                except IndexError:
                    self._deselect_annotation()

            painter.setPen(QPen(SELECTION_BORDER_COLOR, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            for h_rect in self._get_all_handles(rect):
                painter.fillRect(h_rect, SELECTION_BORDER_COLOR)
                painter.setPen(QPen(Qt.white, 1))
                painter.drawRect(h_rect)

            self._draw_size_info(painter, rect)
            self._draw_auto_action_hint(painter, rect)
        else:
            painter.fillRect(self.rect(), DIM_OVERLAY_COLOR)

        if self.current_tool == "eraser_dot" and not self.selection_rect.isNull():
            painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
            painter.setBrush(QColor(255, 255, 255, 40))
            painter.drawEllipse(self.current_mouse_pos, self.eraser_size, self.eraser_size)
            painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self.current_mouse_pos, self.eraser_size, self.eraser_size)

        # erase-fill selection preview (blue)
        if self._erase_fill_rect_start is not None and self._erase_fill_rect_current is not None:
            erase_rect = QRect(self._erase_fill_rect_start, self._erase_fill_rect_current).normalized()
            painter.setPen(QPen(QColor(52, 152, 219, 200), 2, Qt.DashLine))
            painter.setBrush(QColor(52, 152, 219, 30))
            painter.drawRect(erase_rect)

        if not (self.toolbar.toolbar.isVisible() and self.toolbar.toolbar.geometry().contains(self.current_mouse_pos)):
            self._draw_coord_tooltip(painter)

    # ─── Event handling ───

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Enter:
            self.setCursor(Qt.ArrowCursor)
        elif event.type() == QEvent.Leave:
            self.setCursor(Qt.ArrowCursor if not self.selection_rect.isNull() else Qt.CrossCursor)
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        # Save current tool settings before closing
        self._save_current_tool_settings()

        # ensure text editor is cleaned up
        if self._text_editor:
            self._text_editor.hide()
            self._text_editor.deleteLater()
            self._text_editor = None

        # ensure hotkey panel is cleaned up
        if self._hotkey_panel:
            self._hotkey_panel.hide()
            self._hotkey_panel.deleteLater()
            self._hotkey_panel = None

        try:
            self.releaseKeyboard()
        except RuntimeError:
            pass
        self.toolbar.toolbar.hide()
        self.deleteLater()
        super().closeEvent(event)

    def _begin_drag(self, mode, event) -> None:
        self._drag_mode = mode
        self._drag_start_pos = event.position()
        self._drag_start_rect = QRect(self.selection_rect)
        self.toolbar.toolbar.hide()

    def mousePressEvent(self, event) -> None:
        if self._text_editor and not self._text_editor.geometry().contains(event.position().toPoint()):
            self._finish_text_input()

        if event.button() == Qt.RightButton:
            event.accept()  # 消费事件，防止传递到底层窗口
            if self._drag_mode or not self.selection_rect.isNull():
                self.selection_rect = QRect()
                self._drag_mode = None
                self._deselect_annotation()
                self.annotations.clear()
                self.toolbar.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
            # 标记在右键释放时关闭，避免释放事件传递到底层窗口
            self._closing_on_release = True
            return

        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            # dot eraser: erase annotations under cursor immediately
            if not self.selection_rect.isNull() and self.current_tool == "eraser_dot":
                logger.debug(f"dot erase at {pos}, annotations={len(self.annotations)}")
                try:
                    self._erasing = True
                    self._try_erase_annotation(pos)
                except Exception as e:
                    logger.exception(f"dot erase error: {e}")
                finally:
                    return
            # fill eraser: drag to select area, then erase all annotations inside
            if not self.selection_rect.isNull() and self.current_tool == "eraser_fill":
                self._erase_fill_rect_start = pos
                self._erase_fill_rect_current = pos
                self.update()
                return

            # ─── Annotation selection / hit-test ───
            if not self.selection_rect.isNull() and self.annotations:
                hit_idx = self._hit_test_annotation(pos)
                if hit_idx is not None:
                    # Select & drag when using "select" or matching annotation tool
                    ann_type = self.annotations[hit_idx]["type"]
                    drag_tools = {"magnifier", "mosaic", "blur"}
                    if self.current_tool == "select" or \
                       self.current_tool == ann_type and ann_type in drag_tools:
                        self._select_annotation(hit_idx, event.position())
                        return
                # Click on empty space → deselect
                if self._selected_annotation_idx is not None:
                    self._deselect_annotation()

            if not self.selection_rect.isNull() and self.current_tool != "select":
                self._start_drawing(pos)
                return
            if not self.selection_rect.isNull():
                handle = self._handle_at_pos(pos)
                if handle:
                    self._begin_drag(("resize", handle), event)
                    return
                if self.selection_rect.contains(pos):
                    self._begin_drag(("move",), event)
                    return
            self._start_selection(pos)

    def _start_drawing(self, pos: QPoint) -> None:
        local = self._sel_to_local(QPointF(pos))
        self._drawing = True
        self._draw_start = local
        self._draw_points = [local]
        if self.current_tool == "text":
            if self._text_editor:
                self._finish_text_input()
            self._text_editor_pos = local
            self._text_editor = QLineEdit(self)
            font = QFont(self.text_font_family, self.text_font_size)
            font.setBold(self.text_bold)
            font.setItalic(self.text_italic)
            self._text_editor.setFont(font)

            # Subtract 1px offset to compensate for QLineEdit internal rendering
            self._text_editor_window_pos = self.selection_rect.topLeft() + local.toPoint() - QPoint(1, 1)

            self._text_editor.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent;
                    border: none;
                    padding: 0px;
                    color: {self.text_color.name()};
                }}
            """)
            self._text_editor.setTextMargins(0, 0, 0, 0)
            self._text_editor.setContentsMargins(0, 0, 0, 0)
            # Ensure left alignment so text expands to the right
            self._text_editor.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self._text_editor.move(self._text_editor_window_pos)
            self._text_editor.setMinimumWidth(50)
            self._text_editor.setAttribute(Qt.WA_DeleteOnClose)
            self._text_editor.textChanged.connect(self._adjust_text_editor_size)
            self._adjust_text_editor_size()
            self.releaseKeyboard()
            self._text_editor.show()
            self._text_editor.setFocus()
            self._text_editor.returnPressed.connect(self._finish_text_input)
            self._text_editor.editingFinished.connect(self._finish_text_input)
            self._drawing = False
        elif self.current_tool == "number_marker":
            self._marker_counter = getattr(self, '_marker_counter', 0) + 1
            ann = {
                "type": "number_marker", "pos": local,
                "number": self._marker_counter,
                "color": QColor(self.current_color),
                "text_color": QColor("#ffffff"),
                "radius": 14,
            }
            self.annotations.append(ann)
            self._undo_stack.append({"type": "add", "ann": ann, "index": len(self.annotations) - 1})
            self._redo_stack.clear()
            self.toolbar.update_undo_redo_state()
            self._drawing = False
            self.update()

    def _start_selection(self, pos: QPoint) -> None:
        # safety: keep annotations when eraser is active
        if self.current_tool in ("eraser_dot", "eraser_fill") and self.annotations:
            logger.warning(f"_start_selection called during eraser mode (annotations={len(self.annotations)}), ignoring")
            return
        self.is_selecting = True
        self.toolbar.toolbar.hide()
        self._deselect_annotation()
        self.annotations.clear()
        self.start_point = pos
        self.end_point = self.start_point
        self.selection_rect = QRect()
        # Use _on_tool_selected to properly save/restore settings
        self._on_tool_selected("select")
        self.update()

    def _save_current_tool_settings(self) -> None:
        """Save current tool settings to persistent storage."""
        # Only save settings for annotation tools (not select or eraser)
        if self.current_tool not in ("select", "eraser_dot", "eraser_fill"):
            settings_dict = {
                "color": self.current_color.name(),
                "width": self.current_width,
            }
            s = get_settings()
            s.save_tool_settings(self.current_tool, settings_dict)

    def _on_tool_selected(self, tool_id: str) -> None:
        logger.debug(f"tool selected: {tool_id}")

        # Deselect any selected annotation when switching tools
        self._deselect_annotation()

        # Save current tool settings before switching
        self._save_current_tool_settings()

        # Switch to new tool
        self.current_tool = tool_id

        # Update last_tool in settings
        s = get_settings()
        s.last_tool = tool_id
        s.save()

        # Restore new tool's settings
        if tool_id not in ("select", "eraser_dot", "eraser_fill"):
            tool_settings = s.get_tool_settings(tool_id)
            if tool_settings:
                # Restore color if saved
                if "color" in tool_settings:
                    color = QColor(tool_settings["color"])
                    self.current_color = color if color.isValid() else QColor(s.default_color)
                else:
                    self.current_color = QColor(s.default_color)
                # Restore width if saved
                saved_width = tool_settings.get("width")
                if saved_width is not None:
                    self.current_width = saved_width

        # Update UI
        for tid, btn in self.toolbar._tool_btns.items():
            btn.setChecked(tid == tool_id)
        self.update()
        if tool_id in ("eraser_dot", "eraser_fill"):
            self.setCursor(Qt.CrossCursor)
        elif tool_id == "select":
            self.setCursor(Qt.SizeAllCursor if not self.selection_rect.isNull() else Qt.CrossCursor)

    def _on_color_changed(self, color: QColor) -> None:
        self.current_color = color
        if self.current_tool == "mosaic":
            QTimer.singleShot(50, self.update)

    def _on_width_changed(self, width: int) -> None:
        self.current_width = width
        if self.current_tool == "mosaic":
            QTimer.singleShot(50, self.update)

    def _on_font_family_changed(self, family: str) -> None:
        self.text_font_family = family

    def _on_font_size_changed(self, size: int) -> None:
        self.text_font_size = size

    def _on_bold_toggled(self, bold: bool) -> None:
        self.text_bold = bold

    def _on_italic_toggled(self, italic: bool) -> None:
        self.text_italic = italic

    def mouseMoveEvent(self, event) -> None:
        self.current_mouse_pos = event.position().toPoint()
        # eraser drag
        if self._erasing:
            self._try_erase_annotation(self.current_mouse_pos)
            self.update()
            return
        # fill eraser selection preview
        if self._erase_fill_rect_start is not None:
            self._erase_fill_rect_current = self.current_mouse_pos
            self.update()
            return
        if self._drawing:
            self._update_drawing()
            return
        if self._drag_mode:
            self._update_drag(event.position())
            return
        if self.is_selecting:
            self.end_point = self.current_mouse_pos
            rect = QRect(self.start_point, self.end_point).normalized()
            self.selection_rect = self._constrain_rect_to_screen(rect)
            self.update()
        elif not self.selection_rect.isNull():
            # Check if hovering over annotation border first (Snipaste-style)
            hit_idx = self._hit_test_annotation(self.current_mouse_pos)
            if hit_idx is not None:
                ann_type = self.annotations[hit_idx]["type"]
                # Show drag cursor if select tool or matching tool
                if self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                    self.setCursor(Qt.OpenHandCursor)
                else:
                    handle = self._handle_at_pos(self.current_mouse_pos)
                    self.setCursor(self._cursor_for_handle(handle))
            else:
                handle = self._handle_at_pos(self.current_mouse_pos)
                self.setCursor(self._cursor_for_handle(handle))
            self.update()

    def _update_drawing(self) -> None:
        local = self._sel_to_local(QPointF(self.current_mouse_pos))
        if self.current_tool == "freehand":
            self._draw_points.append(local)
            if len(self._draw_points) == 2:
                self.annotations.append({
                    "type": "freehand", "points": list(self._draw_points),
                    "color": QColor(self.current_color), "width": self.current_width,
                })
                self._undo_stack.append({"type": "add", "ann": self.annotations[-1], "index": len(self.annotations) - 1})
                self._redo_stack.clear()
                self.toolbar.update_undo_redo_state()
            elif len(self._draw_points) > 2 and self.annotations and self.annotations[-1]["type"] == "freehand":
                ann = self.annotations[-1]
                ann["points"] = list(self._draw_points)
                ann.pop("_path", None)
        else:
            dx = local.x() - self._draw_start.x()
            dy = local.y() - self._draw_start.y()
            if self.current_tool in ("rect", "ellipse"):
                self._preview_annotation = {
                    "type": self.current_tool, "rect": QRectF(self._draw_start, local).normalized(),
                    "color": QColor(self.current_color), "width": self.current_width,
                }
            elif self.current_tool in ("arrow", "line") and (abs(dx) > MIN_DRAW_THRESHOLD or abs(dy) > MIN_DRAW_THRESHOLD):
                self._preview_annotation = {
                    "type": self.current_tool, "start": QPointF(self._draw_start),
                    "end": QPointF(local), "color": QColor(self.current_color), "width": self.current_width,
                }
            elif self.current_tool == "mosaic":
                r = QRectF(self._draw_start, local).normalized()
                if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                    self._preview_annotation = {"type": "mosaic", "rect": r, "scale": self.current_mosaic_scale}
            elif self.current_tool == "highlighter":
                self._preview_annotation = {
                    "type": "highlighter", "rect": QRectF(self._draw_start, local).normalized(),
                    "color": QColor(self.current_color), "width": self.current_width,
                }
            elif self.current_tool == "blur":
                r = QRectF(self._draw_start, local).normalized()
                if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                    self._preview_annotation = {"type": "blur", "rect": r, "radius": self.current_blur_radius}
            elif self.current_tool == "magnifier":
                r = QRectF(self._draw_start, local).normalized()
                if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                    self._preview_annotation = {"type": "magnifier", "rect": r, "zoom": self.current_magnifier_zoom}
        self.update()

    def _update_drag(self, current_pos: QPointF) -> None:
        delta = current_pos - self._drag_start_pos
        mode = self._drag_mode[0]
        if mode == "move":
            rect = QRect(
                round(self._drag_start_rect.x() + delta.x()), round(self._drag_start_rect.y() + delta.y()),
                self._drag_start_rect.width(), self._drag_start_rect.height(),
            )
            self.selection_rect = self._constrain_rect_to_screen(rect)
        elif mode == "resize":
            handle = self._drag_mode[1]
            r = QRect(self._drag_start_rect)
            if "left" in handle:
                r.setLeft(round(self._drag_start_rect.left() + delta.x()))
            if "right" in handle:
                r.setRight(round(self._drag_start_rect.right() + delta.x()))
            if "top" in handle:
                r.setTop(round(self._drag_start_rect.top() + delta.y()))
            if "bottom" in handle:
                r.setBottom(round(self._drag_start_rect.bottom() + delta.y()))
            self.selection_rect = self._constrain_rect_to_screen(r.normalized())
        elif mode == "move_annotation":
            self._move_selected_annotation(delta)
        self.update()

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

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            event.accept()  # 消费右键释放事件，防止传递到底层窗口
            # 如果右键按下时标记了关闭，现在释放时才真正关闭
            if self._closing_on_release:
                self.close()
            return
        # end eraser drag
        self._erasing = False

        # confirm fill erase selection
        if self._erase_fill_rect_start is not None:
            self._execute_erase_fill()
            self._erase_fill_rect_start = None
            self._erase_fill_rect_current = None
            self.update()
            return
        if self._drawing:
            self._finish_drawing()
            return
        if self._drag_mode:
            mode = self._drag_mode[0]
            # Commit annotation move to undo stack
            if mode == "move_annotation" and self._selected_annotation_idx is not None:
                self._redo_stack.clear()  # new action invalidates redo
                self.toolbar.update_undo_redo_state()
                # Auto-deselect after drag (Snipaste-style)
                self._deselect_annotation()
            self._drag_mode = None
            self._position_toolbar()
            self.toolbar.toolbar.show()
            return
        if self.is_selecting:
            self.is_selecting = False
            if self.selection_rect.width() > MIN_SELECTION_SIZE and self.selection_rect.height() > MIN_SELECTION_SIZE:
                self._position_toolbar()
            else:
                self.selection_rect = QRect()

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to re-edit text or auto-finish capture."""
        if event.button() != Qt.LeftButton:
            return
        if self.selection_rect.isNull():
            return

        # Text annotation re-edit (takes priority)
        hit_idx = self._hit_test_annotation(event.pos())
        if hit_idx is not None and self.annotations[hit_idx]["type"] == "text":
            self._reopen_text_editor(hit_idx)
            return

        # Only auto-finish if we have a valid selection
        if self.selection_rect.contains(event.pos()):
            self._auto_finish()

    def _auto_finish(self) -> None:
        """Execute auto action based on capture_after_action setting."""
        s = get_settings()
        action = s.capture_after_action

        if action == "copy":
            logger.info("Auto-finishing: copy to clipboard")
            self.on_copy()
        elif action == "save":
            logger.info("Auto-finishing: save to file")
            self._auto_save()
        # else: action == "none", do nothing (stay in editor)

    def _auto_save(self) -> None:
        """Automatically save to configured directory."""
        if self.selection_rect.isNull():
            return

        s = get_settings()
        if not s.auto_save_dir:
            # Fallback to manual save dialog if no directory configured
            logger.warning("Auto-save requested but no directory configured")
            self.on_save()
            return

        # Generate filename
        from datetime import datetime
        filename = f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{s.auto_save_format}"
        filepath = os.path.join(s.auto_save_dir, filename)

        # Save the annotated pixmap
        pixmap = self._render_annotated_pixmap()
        pixmap.save(filepath)
        logger.info(f"Auto-saved to {filepath}")
        self.close()

    def _finish_drawing(self) -> None:
        self._drawing = False
        if self._preview_annotation and self._preview_annotation["type"] != "freehand":
            ann = self._preview_annotation
            if ann["type"] in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier") and ann["rect"].width() > MIN_DRAW_THRESHOLD and ann["rect"].height() > MIN_DRAW_THRESHOLD:
                self.annotations.append(ann)
                self._undo_stack.append({"type": "add", "ann": ann, "index": len(self.annotations) - 1})
                self._redo_stack.clear()
                self.toolbar.update_undo_redo_state()
            elif ann["type"] in ("arrow", "line"):
                dx = ann["end"].x() - ann["start"].x()
                dy = ann["end"].y() - ann["start"].y()
                if abs(dx) > MIN_DRAW_THRESHOLD or abs(dy) > MIN_DRAW_THRESHOLD:
                    self.annotations.append(ann)
                    self._undo_stack.append({"type": "add", "ann": ann, "index": len(self.annotations) - 1})
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
        elif self.current_tool == "freehand" and self.annotations and self.annotations[-1]["type"] == "freehand":
            if len(self.annotations[-1]["points"]) < 2:
                self.annotations.pop()
            else:
                # Freehand drawing complete — push to undo stack (only once, not per segment)
                pass  # freehand is added incrementally in _update_drawing
        self._preview_annotation = None
        self.update()

    def keyPressEvent(self, event) -> None:
        # Hotkey help panel toggle
        if event.key() == Qt.Key_Question or event.key() == Qt.Key_F1:
            self._toggle_hotkey_panel()
            event.accept()
            return

        # ─── Single-key tool shortcuts (only when no modifier held) ───
        if (not event.modifiers()
                and self._text_editor is None  # not editing text
                and Qt.Key_A <= event.key() <= Qt.Key_Z):
            tool_map = {
                Qt.Key_R: "rect",
                Qt.Key_E: "ellipse",
                Qt.Key_A: "arrow",
                Qt.Key_L: "line",
                Qt.Key_P: "freehand",
                Qt.Key_T: "text",
                Qt.Key_H: "highlighter",
                Qt.Key_B: "blur",
                Qt.Key_N: "number_marker",
                Qt.Key_V: "select",
            }
            tid = tool_map.get(event.key())
            if tid:
                # Toggle: if same tool active, switch back to select
                if self.current_tool == tid:
                    self._on_tool_selected("select")
                else:
                    self._on_tool_selected(tid)
                event.accept()
                return

        if event.key() == Qt.Key_Escape:
            # First ESC: Hide hotkey panel if visible
            if self._hotkey_panel and self._hotkey_panel.isVisible():
                self._hotkey_panel.hide()
                return

            # Second ESC: Cancel current operation (text editing, drawing, etc.)
            if self._text_editor:
                self._text_editor.hide()
                self._text_editor.deleteLater()
                self._text_editor = None
                self._text_editor_pos = None
                self.grabKeyboard()
                return

            # Cancel any active operation
            if self._drawing or self._erasing or self._erase_fill_rect_start is not None:
                self._drawing = False
                self._erasing = False
                self._erase_fill_rect_start = None
                self._erase_fill_rect_current = None
                self._preview_annotation = None
                self.update()
                return

            # Cancel selection in progress
            if self.is_selecting:
                self.is_selecting = False
                self.selection_rect = QRect()
                self.update()
                return

            # Deselect annotation if one is selected
            if self._selected_annotation_idx is not None:
                self._deselect_annotation()
                return

            # Any other ESC: Close immediately
            self.close()
            return
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._selected_annotation_idx is not None:
                idx = self._selected_annotation_idx
                ann = self.annotations.pop(idx)
                self._undo_stack.append({"type": "remove", "ann": ann, "index": idx})
                self._redo_stack.clear()
                self._deselect_annotation()
                self.toolbar.update_undo_redo_state()
                self.update()
                return
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Enter key: auto-finish if selection exists
            if not self.selection_rect.isNull():
                self._auto_finish()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            self._undo()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Y:
            self._redo()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.on_copy()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_S:
            self.on_save()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_P:
            self.on_pin()
        super().keyPressEvent(event)

    # ─── Size info ───

    def _draw_size_info(self, painter: QPainter, rect: QRect) -> None:
        text = _("{width} × {height}").format(width=rect.width(), height=rect.height())
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        font = QFont("Segoe UI", 12)
        painter.setFont(font)

        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        margin = 4
        bx = rect.center().x() - tw // 2 - margin
        by = rect.top() - th - margin * 2 - 2
        if by < 0:
            by = rect.bottom() + 2
        bw = tw + margin * 2
        bh = th + margin * 2

        painter.fillRect(bx, by, bw, bh, QColor(0, 0, 0, 100))
        painter.setPen(Qt.white)
        painter.drawText(bx + margin, by + margin + fm.ascent(), text)

    def _draw_auto_action_hint(self, painter: QPainter, rect: QRect) -> None:
        """Draw hint text for auto-finish action if enabled."""
        s = get_settings()
        action = s.capture_after_action

        if action == "none":
            return  # No hint needed for normal mode

        # Determine hint text based on action
        if action == "copy":
            hint_text = _("💡 Double-click or press Enter to copy")
        elif action == "save":
            hint_text = _("💡 Double-click or press Enter to save")
        else:
            return

        # Draw hint below the size info
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        font = QFont("Segoe UI", 11)
        painter.setFont(font)

        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(hint_text)
        th = fm.height()
        margin = 6

        # Position: below the selection rect, centered
        bx = rect.center().x() - tw // 2 - margin
        by = rect.bottom() + 8
        if by + th + margin * 2 > self.height() - 10:
            # If too close to bottom, show above selection
            by = rect.top() - th - margin * 2 - 30

        bw = tw + margin * 2
        bh = th + margin * 2

        # Semi-transparent background with slight blue tint
        painter.fillRect(bx, by, bw, bh, QColor(30, 144, 255, 180))
        painter.setPen(Qt.white)
        painter.drawText(bx + margin, by + margin + fm.ascent(), hint_text)

    # ─── Coord tooltip ───

    def _draw_coord_tooltip(self, painter: QPainter) -> None:
        pos = self.current_mouse_pos
        text = _("X:{x} Y:{y}").format(x=pos.x(), y=pos.y())
        painter.setPen(Qt.white)
        font = QFont("Segoe UI", 11)
        painter.setFont(font)
        margin = 6
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + margin * 2
        th = fm.height() + margin * 2
        x = pos.x() + 15
        y = pos.y() + 15
        if x + tw > self.width():
            x = pos.x() - tw - 5
        if y + th > self.height():
            y = pos.y() - th - 5
        painter.fillRect(x, y, tw, th, QColor(0, 0, 0, 100))
        painter.drawText(x + margin, y + margin + fm.ascent(), text)

    def _execute_erase_fill(self) -> None:
        """Fill erase: delete all annotations inside the selection rect."""
        if self._erase_fill_rect_start is None or self._erase_fill_rect_current is None:
            return
        erase_rect = QRect(self._erase_fill_rect_start, self._erase_fill_rect_current).normalized()
        self._erase_in_rect(erase_rect)

    def _toggle_hotkey_panel(self) -> None:
        """Toggle keyboard shortcut help panel display."""
        if self._hotkey_panel is None:
            self._hotkey_panel = HotkeyHelpPanel(self)
            # Center the panel in the overlay window
            panel_x = (self.width() - self._hotkey_panel.width()) // 2
            panel_y = (self.height() - self._hotkey_panel.height()) // 2
            self._hotkey_panel.move(panel_x, panel_y)
            self._hotkey_panel.show()
        elif self._hotkey_panel.isVisible():
            self._hotkey_panel.hide()
        else:
            self._hotkey_panel.show()
