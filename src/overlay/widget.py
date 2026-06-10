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
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QLinearGradient
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSizeF, Signal, QEvent, QTimer

from ..core.utils import capture_all_screens
from ..core.context import AppContext, get_context
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
from ..core.glass_effect import draw_glass_morphism, draw_glass_text

logger = setup_logger("overlay")

# Toolbar fixed dimensions
TOOLBAR_FIXED_WIDTH = 420  # px - 足够容纳最宽的工具菜单
TOOLBAR_FIXED_HEIGHT = 32  # px - 标准工具栏高度


class CaptureOverlay(QWidget, OcrMixin, OverlayRenderingMixin, OverlayActionsMixin, OverlaySelectionMixin, OverlayDrawingMixin):
    """Full-screen semi-transparent overlay with selection, annotation, and OCR."""

    pin_requested = Signal(object, object)
    copy_requested = Signal(object)
    save_requested = Signal(object, bool)  # (pixmap, has_annotations)

    def __init__(self, ctx: AppContext | None = None) -> None:
        super().__init__()
        self.ctx = ctx or get_context()

        self.total_geometry: QRect = QRect()
        for screen in QApplication.screens():
            self.total_geometry = self.total_geometry.united(screen.geometry())

        logger.info(f"init overlay, screen: {self.total_geometry}")
        # Check if cursor should be included
        s = self.ctx.settings
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
        s = self.ctx.settings
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
        self.current_arrow_style: str = "solid"  # solid / hollow / solid_tail / hollow_tail
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

        # ─── Crop mode state ───
        self._crop_mode: bool = False
        self._crop_rect: QRectF | None = None
        self._crop_dragging: bool = False
        self._crop_start: QPointF = QPointF()
        self._crop_handle: str = ""  # "", "move", "nw", "ne", "sw", "se"

        self.text_font_family: str = s.default_font_family
        self.text_font_size: int = s.default_font_size
        self.text_bold: bool = False
        self.text_italic: bool = False
        self.text_color: QColor = QColor(s.default_color)
        logger.debug(f"加载标注设置: color={s.default_color}, width={s.default_line_width}, "
                     f"font={s.default_font_family}, size={s.default_font_size}")

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.toolbar = OverlayToolbar(self)
        self.toolbar.setup()

        # Update toolbar UI to reflect the restored tool
        if self.current_tool in self.toolbar._tool_btns:
            for tid, btn in self.toolbar._tool_btns.items():
                btn.setChecked(tid == self.current_tool)

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
        # 工具栏移动时关闭子菜单（避免菜单位置不同步）
        self.toolbar.close_menus()

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
        self.toolbar.animate_show()
        self.toolbar.toolbar.raise_()

    # ─── Painting ───

    _first_paint = True

    def paintEvent(self, event) -> None:
        painter = QPainter(self)

        # 诊断：首次绘制时保存原始截图到临时文件
        if CaptureOverlay._first_paint:
            CaptureOverlay._first_paint = False
            try:
                fp = os.path.join(os.environ.get("TEMP", os.environ.get("TMPDIR", ".")), "my_snipaste_debug_screenshot.png")
                self.full_screenshot.save(fp)
                logger.info(f"[paintEvent] saved debug screenshot to {fp}, "
                           f"size={self.full_screenshot.width()}x{self.full_screenshot.height()}, "
                           f"dpr={self.full_screenshot.devicePixelRatio()}, "
                           f"widget_rect={self.rect()}, "
                           f"widget_dpr={self.devicePixelRatio()}")
            except Exception as e:
                logger.error(f"[paintEvent] failed to save debug screenshot: {e}")

        try:
            # 手动处理高 DPI 绘制：使用物理尺寸确保整张截图被绘制
            dpr = self.full_screenshot.devicePixelRatio()
            log_w = self.full_screenshot.width() / dpr
            log_h = self.full_screenshot.height() / dpr
            painter.drawPixmap(0, 0, int(log_w), int(log_h), self.full_screenshot)

            logger.debug(f"[paintEvent] draw: log_size={log_w}x{log_h}, dpr={dpr}, "
                        f"physical={self.full_screenshot.width()}x{self.full_screenshot.height()}, "
                        f"widget={self.width()}x{self.height()}")

            # Theme-aware overlay colors (re-evaluated each paint for dynamic theme switching)
            # 注意：Qt6 的 QColor(string) 构造器对 rgba() 的 alpha 解析有歧义，
            # 使用整数构造器 QColor(r,g,b,a) 避免此问题，alpha 始终是 0-255 范围。
            def _hex_to_qcolor(hex_str: str, fallback_r: int, fallback_g: int, fallback_b: int, fallback_a: int = 255) -> QColor:
                try:
                    if hex_str.startswith("#") and len(hex_str) == 9:
                        r = int(hex_str[1:3], 16)
                        g = int(hex_str[3:5], 16)
                        b = int(hex_str[5:7], 16)
                        a = int(hex_str[7:9], 16)
                        return QColor(r, g, b, a)
                    return QColor(fallback_r, fallback_g, fallback_b, fallback_a)
                except Exception:
                    return QColor(fallback_r, fallback_g, fallback_b, fallback_a)
            _dim_color = _hex_to_qcolor(_tw.get("overlay_dim", "#0000008C"), 0, 0, 0, 140)
            _sel_color = _hex_to_qcolor(_tw.get("sel_border", "#0078D7"), 0, 120, 215)
            logger.debug(f"[paintEvent] overlay_dim -> "
                         f"rgba({_dim_color.red()},{_dim_color.green()},{_dim_color.blue()},{_dim_color.alpha()})")

            # Window/element auto-detect highlight (before any selection)
            if self._detected_window_rect is not None and self.selection_rect.isNull():
                wr = self._detected_window_rect
                # Semi-transparent blue fill
                painter.fillRect(wr, QColor(_sel_color.red(), _sel_color.green(), _sel_color.blue(), 30))
                # 2px blue border
                painter.setPen(QPen(QColor(_sel_color), 2))
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
                    painter.fillRect(h_rect, Qt.white)
                    painter.setPen(QPen(_sel_color, 1))
                    painter.drawRect(h_rect)

                self._draw_size_info(painter, rect)
                self._draw_auto_action_hint(painter, rect)
            else:
                painter.fillRect(self.rect(), _dim_color)

            if self.current_tool == "eraser_dot" and not self.selection_rect.isNull():
                painter.setPen(QPen(QColor(255, 255, 255, 180), 2))  # handle_border
                painter.setBrush(QColor(255, 255, 255, 40))         # handle_fill
                painter.drawEllipse(self.current_mouse_pos, self.eraser_size, self.eraser_size)
                painter.setPen(QPen(QColor(0, 0, 0, 120), 1))  # sel_dash
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.current_mouse_pos, self.eraser_size, self.eraser_size)

            # erase-fill selection preview (blue)
            if self._erase_fill_rect_start is not None and self._erase_fill_rect_current is not None:
                erase_rect = QRect(self._erase_fill_rect_start, self._erase_fill_rect_current).normalized()
                painter.setPen(QPen(QColor(52, 152, 219, 200), 2, Qt.DashLine))
                painter.setBrush(QColor(52, 152, 219, 30))
                painter.drawRect(erase_rect)

            # Crop mode overlay
            if self._crop_mode and not self.selection_rect.isNull():
                sr = self.selection_rect
                if self._crop_rect and not self._crop_rect.isEmpty():
                    # Convert crop rect to screen coordinates
                    crop_screen = QRectF(
                        self._crop_rect.x() + sr.x(),
                        self._crop_rect.y() + sr.y(),
                        self._crop_rect.width(),
                        self._crop_rect.height()
                    )
                    # Darken area outside crop rect (within selection)
                    painter.fillRect(sr.x(), sr.y(), sr.width(), int(self._crop_rect.y()),
                                     QColor(0, 0, 0, 120))
                    painter.fillRect(sr.x(), int(crop_screen.bottom()), sr.width(),
                                     int(sr.height() - self._crop_rect.y() - self._crop_rect.height()),
                                     QColor(0, 0, 0, 120))
                    painter.fillRect(sr.x(), int(crop_screen.y()), int(self._crop_rect.x()),
                                     int(self._crop_rect.height()), QColor(0, 0, 0, 120))
                    painter.fillRect(int(crop_screen.right()), int(crop_screen.y()),
                                     int(sr.width() - self._crop_rect.x() - self._crop_rect.width()),
                                     int(self._crop_rect.height()), QColor(0, 0, 0, 120))
                    # Draw crop border
                    painter.setPen(QPen(Qt.white, 2, Qt.DashLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(crop_screen)
                    # Draw crop handles
                    self._draw_crop_handles(painter, crop_screen)

            if not (self.toolbar.toolbar.isVisible() and self.toolbar.toolbar.geometry().contains(self.current_mouse_pos)):
                self._draw_coord_tooltip(painter)

        except Exception as e:
            logger.error(f"[paintEvent] unhandled exception: {e}", exc_info=True)

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
        self.toolbar.close_menus()  # 关闭子菜单
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
                self.toolbar.close_menus()  # 关闭子菜单
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

            # ─── Crop mode handling ───
            if self._crop_mode:
                local_pos = self._sel_to_local(pos)
                handle = self._get_crop_handle(local_pos)
                if handle:
                    # Start resize/move existing crop rect
                    self._crop_handle = handle
                    self._crop_start = local_pos
                    self._crop_dragging = True
                else:
                    # Start new crop rect
                    self._crop_rect = QRectF(local_pos, QSizeF(0, 0))
                    self._crop_start = local_pos
                    self._crop_dragging = True
                    self._crop_handle = ""
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
                    if ann_type in ("arrow", "line"):
                        # Arrow/line: just select (show handles), no body-drag
                        if self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                            self._selected_annotation_idx = hit_idx
                            # Don't save drag_orig or set _drag_mode — no body-moving
                            self.update()
                            return
                    elif self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
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
        # Crop mode handling
        if self._crop_mode:
            local_pos = self._sel_to_local(self.current_mouse_pos)
            if self._crop_dragging:
                if self._crop_handle == "":
                    # Drawing new crop rect
                    self._crop_rect = QRectF(self._crop_start, local_pos).normalized()
                elif self._crop_handle == "move":
                    # Moving existing crop rect
                    delta = local_pos - self._crop_start
                    self._crop_rect.translate(delta)
                    self._crop_start = local_pos
                else:
                    # Resizing crop rect
                    self._resize_crop_rect(local_pos)
            else:
                # Update cursor based on handle hover
                handle = self._get_crop_handle(local_pos)
                self._update_crop_cursor(handle)
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
                # Arrow/line: vertical bidirectional cursor (not move)
                if ann_type in ("arrow", "line"):
                    self.setCursor(Qt.SizeVerCursor)
                # Show move cursor (four-way arrows) if select tool or matching tool
                elif self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
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
        # End crop mode drag
        if self._crop_mode and self._crop_dragging:
            self._crop_dragging = False
            self._crop_handle = ""
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
            self._drag_mode = None
            self._position_toolbar()
            self.toolbar.toolbar.show()
            self.toolbar.animate_show()
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

        # Crop mode: double-click inside crop rect to confirm
        if self._crop_mode and self._crop_rect:
            local_pos = self._sel_to_local(event.pos())
            if self._crop_rect.contains(local_pos):
                self._execute_crop()
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
        s = self.ctx.settings
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

        s = self.ctx.settings
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

            # Cancel crop mode
            if self._crop_mode:
                self._exit_crop_mode()
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
            # Enter key: confirm crop if in crop mode
            if self._crop_mode:
                if self._crop_rect and not self._crop_rect.isEmpty():
                    self._execute_crop()
                else:
                    self._exit_crop_mode()
                return
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
        # 只在拖动选区时显示提示（避免遮挡工具栏）
        if self._drag_mode is None:
            return  # 不在拖动状态，不显示

        mode = self._drag_mode[0]
        if mode not in ("move", "resize"):
            return  # 只在拖动选区时显示，不在拖动标注时显示

        s = self.ctx.settings
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

        # Draw hint below the size info - Glass morphism style
        font = QFont("Segoe UI", 12, QFont.Medium)
        painter.setFont(font)

        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(hint_text)
        th = fm.height()
        padding_h = 12
        padding_v = 8

        # Position: below the selection rect, centered
        bx = rect.center().x() - tw // 2 - padding_h
        by = rect.bottom() + 12
        if by + th + padding_v * 2 > self.height() - 10:
            # If too close to bottom, show above selection
            by = rect.top() - th - padding_v * 2 - 32

        bw = tw + padding_h * 2
        bh = th + padding_v * 2
        hint_rect = QRectF(bx, by, bw, bh)

        # macOS Big Sur 毛玻璃效果（使用通用函数）
        is_dark = _tw.is_dark()

        # 绘制玻璃态背景
        draw_glass_morphism(painter, hint_rect, radius=12, is_dark=is_dark, draw_shadow=True)

        # 绘制文字
        draw_glass_text(
            painter,
            int(bx + padding_h),
            int(by + padding_v + fm.ascent()),
            hint_text,
            is_dark=is_dark,
            glow_enabled=True
        )

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

    # ─── Crop mode helpers ───

    def _get_crop_handle(self, pos: QPointF) -> str:
        """Check if pos is over a crop handle. Returns handle name or empty string."""
        if not self._crop_rect or self._crop_rect.isEmpty():
            return ""
        HANDLE_SIZE = 8
        r = self._crop_rect
        handles = {
            "nw": QRectF(r.left() - HANDLE_SIZE / 2, r.top() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE),
            "ne": QRectF(r.right() - HANDLE_SIZE / 2, r.top() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE),
            "sw": QRectF(r.left() - HANDLE_SIZE / 2, r.bottom() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE),
            "se": QRectF(r.right() - HANDLE_SIZE / 2, r.bottom() - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE),
        }
        for name, rect in handles.items():
            if rect.contains(pos):
                return name
        if r.contains(pos):
            return "move"
        return ""

    def _update_crop_cursor(self, handle: str) -> None:
        """Update cursor based on crop handle."""
        cursors = {
            "nw": Qt.SizeFDiagCursor,
            "se": Qt.SizeFDiagCursor,
            "ne": Qt.SizeBDiagCursor,
            "sw": Qt.SizeBDiagCursor,
            "move": Qt.SizeAllCursor,
        }
        self.setCursor(cursors.get(handle, Qt.CrossCursor))

    def _resize_crop_rect(self, pos: QPointF) -> None:
        """Resize crop rect by dragging a corner handle."""
        if not self._crop_rect:
            return
        r = self._crop_rect
        if self._crop_handle == "nw":
            r.setTopLeft(pos)
        elif self._crop_handle == "ne":
            r.setTopRight(pos)
        elif self._crop_handle == "sw":
            r.setBottomLeft(pos)
        elif self._crop_handle == "se":
            r.setBottomRight(pos)
        self._crop_rect = r.normalized()

    def _draw_crop_handles(self, painter: QPainter, rect: QRectF) -> None:
        """Draw resize handles at corners of crop rect."""
        HANDLE_SIZE = 8
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(Qt.white)
        corners = [
            (rect.left() - HANDLE_SIZE / 2, rect.top() - HANDLE_SIZE / 2),
            (rect.right() - HANDLE_SIZE / 2, rect.top() - HANDLE_SIZE / 2),
            (rect.left() - HANDLE_SIZE / 2, rect.bottom() - HANDLE_SIZE / 2),
            (rect.right() - HANDLE_SIZE / 2, rect.bottom() - HANDLE_SIZE / 2),
        ]
        for x, y in corners:
            painter.fillRect(int(x), int(y), HANDLE_SIZE, HANDLE_SIZE, Qt.white)
            painter.drawRect(int(x), int(y), HANDLE_SIZE, HANDLE_SIZE)
