"""Full-screen overlay for area selection, annotation, and event handling.

Composed of CaptureOverlay (main class) + 5 mixins:
- OcrMixin              — OCR progress / cancellation
- OverlayRenderingMixin — annotation rendering
- OverlayActionsMixin   — actions / text editing
- OverlaySelectionMixin — selection / hit-testing / dragging
- OverlayDrawingMixin   — drawing state / tool selection
"""

import math
import os
from PySide6.QtWidgets import QWidget, QApplication, QLineEdit
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, Signal, QEvent, QTimer

from ..core.utils import capture_all_screens
from ..core.settings import get_settings
from ..core.window_detector import detect_window_under_cursor
from .toolbar import OverlayToolbar
from .rendering import OverlayRenderingMixin
from .actions import OverlayActionsMixin
from .selection import OverlaySelectionMixin
from .drawing import OverlayDrawingMixin
from .ocr_mixin import OcrMixin
from .hotkey_panel import HotkeyHelpPanel
from ..core.constants import (
    DEFAULT_ANNOTATION_COLOR,
    HANDLE_SIZE, MIN_SELECTION_SIZE, MIN_DRAW_THRESHOLD,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_LINE_WIDTH,
)
from ..core.i18n import _
from ..core.logger import setup_logger
from ..core.theme import theme as _tw

logger = setup_logger("overlay")

# Toolbar fixed dimensions
TOOLBAR_FIXED_WIDTH = 420  # px - 足够容纳最宽的工具菜单
TOOLBAR_FIXED_HEIGHT = 32  # px - 标准工具栏高度


class CaptureOverlay(QWidget, OcrMixin, OverlayRenderingMixin, OverlayActionsMixin, OverlaySelectionMixin, OverlayDrawingMixin):
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
        self._detected_window_rect: QRect | None = None
        self._window_snap_rect: QRect | None = None  # pending single-click window snap

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

    # ─── Helper needed by mixins ───

    def _sel_to_local(self, pos: QPoint) -> QPointF:
        """Convert screen position to selection-relative position."""
        return QPointF(pos - self.selection_rect.topLeft())

    def _capture_pos(self) -> QPoint:
        """Return top-left corner of selection in screen coordinates."""
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

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

        # Theme-aware overlay colors (re-evaluated each paint for dynamic theme switching)
        _dim_color = QColor(_tw.get("overlay_dim"))
        _sel_color = QColor(_tw.get("sel_border"))

        # Window/element auto-detect highlight (before any selection)
        if self._detected_window_rect is not None and self.selection_rect.isNull():
            wr = self._detected_window_rect
            # Semi-transparent blue fill
            painter.fillRect(wr, QColor(0, 120, 215, 30))
            # 2px blue border
            painter.setPen(QPen(QColor(_tw.get("sel_border", "rgba(0, 120, 215, 255)")), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(wr)

        rect = self.selection_rect
        if not rect.isNull():
            # 4 semi-transparent dimming strips around the selection
            w = self.width()
            h = self.height()
            painter.fillRect(0, 0, w, rect.top(), _dim_color)
            painter.fillRect(0, rect.bottom() + 1, w, h - rect.bottom() - 1, _dim_color)
            painter.fillRect(0, rect.top(), rect.left(), rect.height(), _dim_color)
            painter.fillRect(rect.right() + 1, rect.top(), w - rect.right() - 1, rect.height(), _dim_color)

            self._draw_annotations(painter, rect.size(), rect.topLeft())

            # Selection indicator for selected annotation
            if self._selected_annotation_idx is not None:
                try:
                    ann = self.annotations[self._selected_annotation_idx]
                    self._draw_selection_indicator(painter, ann, rect.topLeft())
                except IndexError:
                    self._deselect_annotation()

            painter.setPen(QPen(_sel_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            for h_rect in self._get_all_handles(rect):
                painter.fillRect(h_rect, _sel_color)
                painter.setPen(QPen(Qt.white, 1))
                painter.drawRect(h_rect)

            self._draw_size_info(painter, rect)
            self._draw_auto_action_hint(painter, rect)
        else:
            painter.fillRect(self.rect(), _dim_color)

        if self.current_tool == "eraser_dot" and not self.selection_rect.isNull():
            painter.setPen(QPen(QColor(_tw.get("handle_border", "rgba(255,255,255,180)")), 2))
            painter.setBrush(QColor(_tw.get("handle_fill", "rgba(255,255,255,40)")))
            painter.drawEllipse(self.current_mouse_pos, self.eraser_size, self.eraser_size)
            painter.setPen(QPen(QColor(_tw.get("sel_dash", "rgba(0,0,0,120)")), 1))
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
            self._detected_window_rect = None
            self._window_snap_rect = None
            # 标记在右键释放时关闭，避免释放事件传递到底层窗口
            self._closing_on_release = True
            return

        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            # Window/element snap: save detected rect for later; don't snap
            # yet so the user can still drag to create a free-form selection.
            # The snap is applied in mouseReleaseEvent only on single-click.
            if self._detected_window_rect is not None and self.selection_rect.isNull():
                self._window_snap_rect = self._detected_window_rect
                self._detected_window_rect = None
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
                    # Check if clicking on a resize handle of the already-selected annotation
                    if hit_idx == self._selected_annotation_idx:
                        handle = self._annotation_handle_at_pos(
                            self.annotations[hit_idx], pos, self.selection_rect.topLeft()
                        )
                        if handle:
                            self._begin_annotation_resize(hit_idx, handle, event.position())
                            return
                    # Select & drag when using "select" or matching annotation tool (Snipaste-style)
                    ann_type = self.annotations[hit_idx]["type"]
                    if self.current_tool == "select" or self.current_tool == ann_type:
                        self._select_annotation(hit_idx, event.position())
                        return
                # Click on empty space → deselect
                if self._selected_annotation_idx is not None:
                    self._deselect_annotation()

            if not self.selection_rect.isNull():
                # 优先检测选区手柄（无论当前工具是什么）
                handle = self._handle_at_pos(pos)
                if handle:
                    self._begin_drag(("resize", handle), event)
                    return
                # 非 select 工具且没点到手柄 → 开始画图
                if self.current_tool != "select":
                    self._start_drawing(pos)
                    return
                # select 工具 → 拖动选区
                if self.selection_rect.contains(pos):
                    self._begin_drag(("move",), event)
                    return
            self._start_selection(pos)

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
        elif self.selection_rect.isNull() and self._selected_annotation_idx is None:
            # Window/element auto-detect (only before any selection/annotation)
            win_rect = detect_window_under_cursor(self.current_mouse_pos)
            if win_rect is not None and win_rect.isValid():
                win_rect = win_rect.intersected(self.rect())  # clip to overlay
                if win_rect != self._detected_window_rect:
                    self._detected_window_rect = win_rect
                    self.setCursor(Qt.CrossCursor)
                    self.update()
            else:
                if self._detected_window_rect is not None:
                    self._detected_window_rect = None
                    self.update()
        elif not self.selection_rect.isNull():
            # Check if hovering over annotation border first (Snipaste-style)
            hit_idx = self._hit_test_annotation(self.current_mouse_pos)
            if hit_idx is not None:
                # If hovering over selected annotation, check for resize handles first
                if hit_idx == self._selected_annotation_idx:
                    handle = self._annotation_handle_at_pos(
                        self.annotations[hit_idx], self.current_mouse_pos, self.selection_rect.topLeft()
                    )
                    if handle:
                        self.setCursor(self._cursor_for_annotation_handle(handle))
                        self.update()
                        return
                ann_type = self.annotations[hit_idx]["type"]
                # Show move cursor (four-way arrows) if select tool or matching tool
                if self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                    self.setCursor(Qt.SizeAllCursor)  # 四向箭头移动光标
                else:
                    handle = self._handle_at_pos(self.current_mouse_pos)
                    self.setCursor(self._cursor_for_handle(handle))
            else:
                handle = self._handle_at_pos(self.current_mouse_pos)
                self.setCursor(self._cursor_for_handle(handle))
            self.update()

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
            # Commit annotation resize/move to undo stack
            if mode in ("move_annotation", "resize_annotation") and self._selected_annotation_idx is not None:
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
            elif self._window_snap_rect is not None:
                # Single click on detected window (no significant drag) → snap
                self.selection_rect = self._window_snap_rect
                self._window_snap_rect = None
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
