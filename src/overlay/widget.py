"""Full-screen overlay for area selection, annotation, and event handling.

Composed of CaptureOverlay (main class) + 7 mixins:
- OverlayEventHandlerMixin — mouse/keyboard events, auto-finish, helpers
- OcrMixin                 — OCR progress / cancellation
- OverlayRenderingMixin    — annotation rendering
- OverlayActionsMixin      — actions / text editing
- OverlayTransformsMixin   — image rotate / flip
- OverlaySelectionMixin    — selection / hit-testing / dragging
- OverlayDrawingMixin      — drawing state / tool selection
"""

import os

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from ..annotations import Annotation
from ..core.context import AppContext, get_context
from ..core.i18n import _
from ..core.logger import setup_logger
from ..core.theme_pkg import theme as _t
from ..core.utils import capture_all_screens
from .actions import OverlayActionsMixin
from .crop_mode import CropMode
from .drawing import OverlayDrawingMixin
from .handlers import OverlayEventHandlerMixin
from .ocr_mixin import OcrMixin
from .rendering import OverlayRenderingMixin
from .selection import OverlaySelectionMixin
from .toolbar import OverlayToolbar
from .transforms import OverlayTransformsMixin
from .window_snap import WindowSnapDetector

logger = setup_logger("overlay")

# Toolbar fixed dimensions
TOOLBAR_FIXED_WIDTH = 420  # px - 足够容纳最宽的工具菜单
TOOLBAR_FIXED_HEIGHT = 32  # px - 标准工具栏高度


class CaptureOverlay(OverlayEventHandlerMixin, OverlayRenderingMixin, OverlayActionsMixin,
                     OverlayTransformsMixin, OverlaySelectionMixin, OverlayDrawingMixin,
                     OcrMixin, QWidget):
    """Full-screen semi-transparent overlay with selection, annotation, and OCR."""

    pin_requested = Signal(object, object)
    copy_requested = Signal(object)
    save_requested = Signal(object, bool)  # (pixmap, has_annotations)

    def __init__(self, ctx: AppContext | None = None) -> None:
        QWidget.__init__(self)
        OverlayRenderingMixin.__init__(self)
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
        self.window_snap = WindowSnapDetector(self)

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
        self.annotations: list[Annotation] = []
        self._undo_stack: list[dict] = []  # action history for undo
        self._redo_stack: list[dict] = []  # reversed actions for redo
        self._drawing: bool = False
        self._draw_start: QPointF = QPointF()
        self._draw_points: list[QPointF] = []
        self._preview_annotation: Annotation | None = None

        self.eraser_size: int = 20
        self._eraser_target_size: int = 20
        self._eraser_size_animating: bool = False
        self._erasing: bool = False
        self._closing_on_release: bool = False  # 标记右键释放时关闭

        self._erase_fill_rect_start: QPoint | None = None
        self._erase_fill_rect_current: QPoint | None = None

        self._last_mouse_release_time: float = 0.0
        self._text_editor: QLineEdit | None = None
        self._text_editor_pos: QPointF | None = None
        self._editing_annotation_idx: int | None = None  # non-None when re-editing existing text

        # ─── Annotation selection / editing state ───
        self._selected_annotation_idx: int | None = None
        self._annotation_drag_orig: dict = {}  # original position data for drag

        # ─── Crop mode ───
        self.crop = CropMode(self)

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

    def contextMenuEvent(self, event) -> None:
        if self.selection_rect.isNull():
            return

        from PySide6.QtGui import QAction
        from ..ui.common.glass_widget import GlassMenu

        menu = GlassMenu(self)

        qrcode_action = QAction(_("QR Code Recognition"), self)
        qrcode_action.triggered.connect(self._on_qrcode)
        menu.addAction(qrcode_action)

        ocr_action = QAction(_("OCR Text Recognition"), self)
        ocr_action.triggered.connect(self._on_ocr)
        menu.addAction(ocr_action)

        menu.exec(event.globalPos())

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
            _dim_color = _hex_to_qcolor(_t.get("overlay_dim", "#0000008C"), 0, 0, 0, 140)
            _sel_color = _hex_to_qcolor(_t.get("sel_border", "#0078D7"), 0, 120, 215)
            logger.debug(f"[paintEvent] overlay_dim -> "
                         f"rgba({_dim_color.red()},{_dim_color.green()},{_dim_color.blue()},{_dim_color.alpha()})")

            # Window/element auto-detect highlight (before any selection)
            if self.selection_rect.isNull():
                self.window_snap.paint_highlight(painter, _sel_color)

            rect = self.selection_rect
            if not rect.isNull():
                # 4 semi-transparent dimming strips around the selection
                w = self.width()
                h = self.height()
                painter.fillRect(0, 0, w, rect.top(), _dim_color)
                painter.fillRect(0, rect.bottom() + 1, w, h - rect.bottom() - 1, _dim_color)
                painter.fillRect(0, rect.top(), rect.left(), rect.height(), _dim_color)
                painter.fillRect(rect.right() + 1, rect.top(), w - rect.right() - 1, rect.height(), _dim_color)

                painter.save()
                painter.setClipRect(rect)
                self._draw_annotations(painter, rect.size(), rect.topLeft())
                painter.restore()

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

            self.crop.paint(painter, self.selection_rect)

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
