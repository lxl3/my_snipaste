"""Floating pinned window with drop shadow, zoom, and annotation tools.

Composed of PinWindow (main class) + 4 mixins:
- OcrMixin               — OCR progress / cancellation
- PinWindowRenderingMixin  — annotation rendering via AnnotationRenderer
- PinWindowActionsMixin    — actions / text editing / transforms / crop / drawing
- PinWindowResizeMixin     — window resize helpers / thumbnail mode
- PinWindowMenuMixin       — context menu and action handlers
"""

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLineEdit, QMessageBox, QWidget

from ...annotations import Annotation
from ...core.context import AppContext, get_context
from ...core.geometry import cursor_for_crop_handle, get_crop_handle, point_to_segment_distance, resize_crop_rect
from ...core.i18n import _
from ...core.logger import setup_logger
from ...core.utils import qpixmap_to_pil
from ...overlay.ocr_mixin import OcrMixin
from ...overlay.toolbar import OverlayToolbar
from ..common.toast import ToastManager
from .pin_actions import PinWindowActionsMixin
from .pin_menu import PinWindowMenuMixin
from .pin_rendering import PinWindowRenderingMixin
from .pin_resize import PinWindowResizeMixin

logger = setup_logger("pin_window")


class PinWindow(QWidget, OcrMixin, PinWindowRenderingMixin, PinWindowActionsMixin,
                PinWindowResizeMixin, PinWindowMenuMixin):
    """Floating pinned window with drop shadow, zoom, and annotation tools."""

    # Signals for communication with main application
    copy_requested = Signal(QPixmap)
    save_requested = Signal(QPixmap, bool)
    close_requested = Signal()
    toggle_topmost_requested = Signal(bool)
    opacity_changed = Signal(int)
    resize_requested = Signal(QSize)
    thumbnail_mode_toggled = Signal(bool)

    SHADOW = 4        # px shadow ring around the image
    MIN_WIDTH = 100
    MIN_HEIGHT = 100

    def __init__(self, pixmap: QPixmap, pos, ctx: AppContext | None = None) -> None:
        super().__init__()
        PinWindowRenderingMixin.__init__(self)
        self.ctx = ctx or get_context()
        self.pixmap = pixmap
        self._dragging: bool = False
        self._drag_pos: QPoint | None = None
        self._resizing: bool = False
        self._resize_dir: str = ""
        self._thumbnail_mode: bool = False
        self._original_size: QSize | None = None
        self._original_pixmap: QPixmap | None = None
        self._resized_by_user: bool = False

        # --- Zoom ---
        self._zoom_factor = 1.0
        dpr = pixmap.devicePixelRatio()
        self._base_img_w = int(pixmap.width() / dpr)
        self._base_img_h = int(pixmap.height() / dpr)

        logger.debug(f"PinWindow init: pixmap physical={pixmap.width()}x{pixmap.height()}, dpr={dpr}, logical={self._base_img_w}x{self._base_img_h}")

        # --- Annotation state (same interface as CaptureOverlay) ---
        self.annotations: list[Annotation] = []
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._preview_annotation: Annotation | None = None
        self._drawing: bool = False
        self._draw_start: QPointF = QPointF()
        self._draw_points: list[QPointF] = []
        self._selected_annotation_index: int = -1

        # Annotation dragging state
        self._annotation_drag_orig: dict = {}
        self._dragging_annotation: bool = False

        # Mouse tracking
        self._current_mouse_pos: QPoint = QPoint()

        # Crop mode state
        self._crop_mode: bool = False
        self._crop_rect: QRectF | None = None
        self._crop_dragging: bool = False
        self._crop_start: QPointF = QPointF()
        self._crop_handle: str = ""  # "", "move", "nw", "ne", "sw", "se"

        # Tool state (matching overlay toolbar expectations)
        s = self.ctx.settings
        self.current_tool: str = "select"
        self.current_color: QColor = QColor(s.default_color)
        self.current_width: int = s.default_line_width
        self.current_blur_radius: int = 10
        self.current_mosaic_scale: int = 8
        self.current_magnifier_zoom: int = 2
        self.eraser_size: int = 20
        self.text_font_family: str = s.default_font_family
        self.text_font_size: int = s.default_font_size
        self.text_bold: bool = False
        self.text_italic: bool = False
        self.text_color: QColor = QColor(s.default_color)
        self.current_arrow_style: str = "solid"

        # Text editor for inline editing
        self._text_editor: QLineEdit | None = None
        self._text_editor_pos: QPointF | None = None
        self._text_editor_window_pos: QPoint | None = None
        self._editing_annotation_idx: int | None = None

        # OCR worker (required by OcrMixin)
        self._ocr_worker = None
        self._ocr_progress = None
        self._ocr_timer = None
        self._ocr_start_time = None

        # --- Toolbar ---
        self._toolbar_obj: OverlayToolbar | None = None
        self._toolbar_shown: bool = False
        self._toolbar_extra_height: int = 0

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Window = image logical size + shadow ring
        self._img_w = self._base_img_w
        self._img_h = self._base_img_h
        self.setFixedSize(self._img_w + self.SHADOW * 2,
                          self._img_h + self.SHADOW * 2)
        if pos is not None:
            self.move(pos.x(), pos.y())

        opacity = self.ctx.settings.pin_window_opacity
        self.setWindowOpacity(opacity / 100.0)

        self.setMouseTracking(True)

    # ─── Paint ───────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        s = self.SHADOW
        img_rect = QRect(s, s, self._img_w, self._img_h)

        # --- Draw drop shadow ---
        if not self._resized_by_user and self._zoom_factor == 1.0:
            for i in range(s):
                alpha = max(0, 40 - i * 8)
                if alpha <= 0:
                    break
                offset = s - i
                r = img_rect.adjusted(-offset, -offset, offset, offset)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(135, 206, 250, alpha))
                painter.drawRoundedRect(r, 3, 3)

        # --- Draw the image ---
        painter.drawPixmap(img_rect, self.pixmap)

        # --- Draw annotations ---
        painter.save()
        painter.setClipRect(img_rect)
        painter.translate(img_rect.topLeft())
        if self._zoom_factor != 1.0 and not self._resized_by_user:
            painter.scale(self._zoom_factor, self._zoom_factor)
        for ann in self.annotations:
            self._draw_annotation(painter, ann)
        if self._preview_annotation:
            self._draw_annotation(painter, self._preview_annotation)
        if 0 <= self._selected_annotation_index < len(self.annotations):
            self._draw_selection_indicator(painter, self.annotations[self._selected_annotation_index])

        # Draw eraser cursor
        if self.current_tool in ("eraser_dot", "eraser_fill") and self._toolbar_shown:
            mouse_in_img = self._current_mouse_pos - img_rect.topLeft()
            if img_rect.contains(self._current_mouse_pos):
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.setBrush(Qt.NoBrush)
                scaled_r = self.eraser_size * self._zoom_factor if not self._resized_by_user and self._zoom_factor != 1.0 else self.eraser_size
                painter.drawEllipse(mouse_in_img, scaled_r, scaled_r)

        painter.restore()

        # --- Draw crop mode overlay ---
        if self._crop_mode:
            painter.save()
            if self._crop_rect and not self._crop_rect.isEmpty():
                zoom = self._zoom_factor if not self._resized_by_user else 1.0
                crop_window = QRectF(
                    self._crop_rect.x() * zoom + s,
                    self._crop_rect.y() * zoom + s,
                    self._crop_rect.width() * zoom,
                    self._crop_rect.height() * zoom,
                )

                mask_color = QColor(0, 0, 0, 128)
                painter.setBrush(mask_color)
                painter.setPen(Qt.NoPen)
                painter.drawRect(QRectF(img_rect.x(), img_rect.y(),
                                        img_rect.width(), crop_window.y() - img_rect.y()))
                painter.drawRect(QRectF(img_rect.x(), crop_window.bottom(),
                                        img_rect.width(), img_rect.bottom() - crop_window.bottom()))
                painter.drawRect(QRectF(img_rect.x(), crop_window.y(),
                                        crop_window.x() - img_rect.x(), crop_window.height()))
                painter.drawRect(QRectF(crop_window.right(), crop_window.y(),
                                        img_rect.right() - crop_window.right(), crop_window.height()))

                painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(crop_window)
                self._draw_crop_handles(painter, crop_window)
            painter.restore()

    # ─── Zoom ────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return

        current_pos = self.pos()

        if not self._toolbar_shown:
            actual_w = self.width() - self.SHADOW * 2
            actual_h = self.height() - self.SHADOW * 2

            if actual_w != self._img_w or actual_h != self._img_h:
                self._img_w = actual_w
                self._img_h = actual_h
                if self._base_img_w > 0 and self._base_img_h > 0:
                    self._zoom_factor = self._img_w / self._base_img_w

        old_width = self._img_w
        old_height = self._img_h

        if delta > 0:
            self._zoom_factor *= 1.05
        elif delta < 0:
            self._zoom_factor /= 1.05
        self._zoom_factor = max(0.1, min(5.0, self._zoom_factor))

        new_img_w = max(1, int(self._base_img_w * self._zoom_factor))
        new_img_h = max(1, int(self._base_img_h * self._zoom_factor))

        logger.debug(f"wheelEvent: delta={delta}, zoom={self._zoom_factor:.3f}, base={self._base_img_w}x{self._base_img_h}, old={old_width}x{old_height}, new={new_img_w}x{new_img_h}")

        if new_img_w == old_width and new_img_h == old_height:
            event.accept()
            return

        self._img_w = new_img_w
        self._img_h = new_img_h

        if self._toolbar_shown:
            current_pos_before = self.pos()
            self._position_toolbar()
            self.move(current_pos_before)
        else:
            self.setFixedSize(self._img_w + self.SHADOW * 2,
                              self._img_h + self.SHADOW * 2)
            self.move(current_pos)

        self.update()
        event.accept()

    # ─── Annotation Selection & Dragging ─────────────────

    def _hit_test_annotations(self, pos: QPointF) -> int | None:
        BORDER_THRESHOLD = 8
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann.type
            try:
                if t in ("rect", "ellipse", "highlighter", "mosaic", "blur", "magnifier"):
                    r = ann.rect
                    if r.contains(pos):
                        dist_left = abs(pos.x() - r.left())
                        dist_right = abs(pos.x() - r.right())
                        dist_top = abs(pos.y() - r.top())
                        dist_bottom = abs(pos.y() - r.bottom())
                        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
                        if min_dist <= BORDER_THRESHOLD:
                            return i
                elif t in ("arrow", "line"):
                    start = ann.start
                    end = ann.end
                    dist = self._point_to_line_distance(pos, start, end)
                    if dist < 10:
                        return i
                elif t == "freehand":
                    pts = ann.points
                    for p in pts:
                        if (pos - p).manhattanLength() < 10:
                            return i
                elif t in ("text", "number_marker"):
                    ann_pos = ann.pos
                    if (pos - ann_pos).manhattanLength() < 20:
                        return i
            except Exception:
                continue
        return None

    def _point_to_line_distance(self, p: QPointF, a: QPointF, b: QPointF) -> float:
        return point_to_segment_distance(p, a, b)

    def _select_annotation(self, idx: int, event_pos: QPointF) -> None:
        self._selected_annotation_index = idx
        ann = self.annotations[idx]
        self._annotation_drag_orig = {}
        t = ann.type
        if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
            self._annotation_drag_orig["rect"] = QRectF(ann.rect)
        elif t in ("arrow", "line"):
            self._annotation_drag_orig["start"] = QPointF(ann.start)
            self._annotation_drag_orig["end"] = QPointF(ann.end)
        elif t == "freehand":
            self._annotation_drag_orig["points"] = [QPointF(p) for p in ann.points]
        elif t in ("text", "number_marker"):
            self._annotation_drag_orig["pos"] = QPointF(ann.pos)
        self._drag_start = event_pos
        self._dragging_annotation = True
        self.setCursor(Qt.ClosedHandCursor)
        self.update()

    def _deselect_annotation(self) -> None:
        self._selected_annotation_index = -1
        self._annotation_drag_orig = {}
        self.update()

    def _move_selected_annotation(self, delta: QPointF) -> None:
        if self._selected_annotation_index < 0:
            return
        ann = self.annotations[self._selected_annotation_index]
        t = ann.type
        orig = self._annotation_drag_orig
        if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier") and "rect" in orig:
            r = orig["rect"]
            ann.rect = QRectF(r.x() + delta.x(), r.y() + delta.y(), r.width(), r.height())
            if t in ("mosaic", "blur", "magnifier") and ann._cached is not None:
                ann._cached = None
        elif t in ("arrow", "line") and "start" in orig and "end" in orig:
            ann.start = QPointF(orig["start"].x() + delta.x(), orig["start"].y() + delta.y())
            ann.end = QPointF(orig["end"].x() + delta.x(), orig["end"].y() + delta.y())
        elif t == "freehand" and "points" in orig:
            ann.points = [QPointF(p.x() + delta.x(), p.y() + delta.y()) for p in orig["points"]]
        elif t in ("text", "number_marker") and "pos" in orig:
            ann.pos = QPointF(orig["pos"].x() + delta.x(), orig["pos"].y() + delta.y())

    # ─── Mouse Events ────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        # Crop mode handling
        if self._crop_mode:
            pos = self._content_pos(event)
            handle = self._get_crop_handle(pos)
            if handle:
                self._crop_handle = handle
                self._crop_start = pos
                self._crop_dragging = True
            else:
                self._crop_rect = QRectF(pos, QSizeF(0, 0))
                self._crop_start = pos
                self._crop_dragging = True
                self._crop_handle = ""
            event.accept()
            return

        # Finish text input if clicking outside the text editor
        if self._text_editor and not self._text_editor.geometry().contains(event.position().toPoint()):
            self._finish_text_input()

        # Check resize first
        resize_dir = self._get_resize_direction(event.position().toPoint())
        if resize_dir:
            self._resizing = True
            self._resize_dir = resize_dir
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_start_geometry = self.geometry()
            event.accept()
            return

        # Annotation handling when toolbar is shown
        if self._toolbar_shown:
            pos = self._content_pos(event)

            if self.current_tool in ("eraser_dot", "eraser_fill"):
                self._try_erase_annotation(pos)
                event.accept()
                return

            hit_idx = self._hit_test_annotations(pos)
            if hit_idx is not None:
                ann_type = self.annotations[hit_idx]["type"]
                if self.current_tool == "select" or self.current_tool == ann_type:
                    self._select_annotation(hit_idx, pos)
                    event.accept()
                    return

            if self._selected_annotation_index >= 0:
                self._deselect_annotation()

            if self.current_tool not in ("select", ""):
                self._start_drawing(event)
                event.accept()
                return

        # Default: drag window
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self._dragging = True
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self._current_mouse_pos = event.position().toPoint()

        if self._crop_mode:
            pos = self._content_pos(event)
            if self._crop_dragging:
                if self._crop_handle == "":
                    self._crop_rect = QRectF(self._crop_start, pos).normalized()
                elif self._crop_handle == "move":
                    delta = pos - self._crop_start
                    self._crop_rect.translate(delta)
                    self._crop_start = pos
                else:
                    self._resize_crop_rect(pos)
                self.update()
            else:
                handle = self._get_crop_handle(pos)
                self._update_crop_cursor(handle)
            event.accept()
            return

        if self._resizing and self._resize_dir:
            self._handle_resize(event.globalPosition().toPoint())
            event.accept()
        elif self._dragging_annotation:
            pos = self._content_pos(event)
            delta = pos - self._drag_start
            self._move_selected_annotation(delta)
            self.update()
            event.accept()
        elif self.current_tool == "eraser_dot" and event.buttons() & Qt.LeftButton:
            pos = self._content_pos(event)
            self._try_erase_annotation(pos)
            event.accept()
        elif self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        elif self._drawing and self._toolbar_shown:
            self._update_drawing(event)
            event.accept()
        else:
            resize_dir = self._get_resize_direction(event.position().toPoint())
            if resize_dir:
                self._update_cursor(resize_dir)
            elif self._toolbar_shown and self.current_tool in ("eraser_dot", "eraser_fill"):
                self.update()
            elif self._toolbar_shown:
                pos = self._content_pos(event)
                hit_idx = self._hit_test_annotations(pos)
                if hit_idx is not None:
                    ann_type = self.annotations[hit_idx].type
                    if self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                        self.setCursor(Qt.SizeAllCursor)
                    else:
                        self.setCursor(Qt.ArrowCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
            else:
                self._update_cursor(resize_dir)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self._crop_mode and self._crop_dragging:
                self._crop_dragging = False
                self._crop_handle = ""
                event.accept()
                return

            if self._drawing and self._toolbar_shown:
                self._finish_drawing()
                event.accept()
                return
            elif self._dragging_annotation:
                self._dragging_annotation = False
                self._deselect_annotation()
                self.setCursor(Qt.ArrowCursor)
                event.accept()
                return
            else:
                self._dragging = False
                self._resizing = False
                event.accept()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._crop_mode and self._crop_rect:
            pos = self._content_pos(event)
            if self._crop_rect.contains(pos):
                self._execute_crop()
                event.accept()
                return

        if self._thumbnail_mode:
            self._exit_thumbnail_mode()
        else:
            self.close()

    def keyPressEvent(self, event) -> None:
        if self._crop_mode:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self._crop_rect and not self._crop_rect.isEmpty():
                    self._execute_crop()
                event.accept()
                return
            elif event.key() == Qt.Key_Escape:
                self._exit_crop_mode()
                event.accept()
                return
        super().keyPressEvent(event)

    # ─── OCR ─────────────────────────────────────────────

    def _on_ocr(self) -> None:
        """Perform OCR on the pinned image with annotations."""
        ToastManager.show(_("OCR recognizing..."), "🔍", "info", parent=self)
        captured = self._render_annotated_pixmap()
        from ..ocr.engine import OcrWorker
        pil_image = qpixmap_to_pil(captured)
        self._ocr_worker = OcrWorker(pil_image, self.ctx.settings.ocr_language)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._show_ocr_progress(self._cancel_ocr)
        self._ocr_worker.start()

    def _on_ocr_finished(self, text: str) -> None:
        """Handle OCR completion."""
        self._cleanup_ocr()
        if text:
            ToastManager.show(_("Recognition complete"), "✓", "success", parent=self)
            from ..ocr.ocr_dialog import OcrResultDialog
            OcrResultDialog(text, self).exec()
        else:
            QMessageBox.warning(self, _("OCR Result"), _("No text recognized"))

    def _on_ocr_error(self, error_msg: str) -> None:
        """Handle OCR error."""
        self._cleanup_ocr()
        QMessageBox.critical(self, _("OCR Error"), _("Text recognition failed:\n{error}").format(error=error_msg))

    def _on_done_editing(self) -> None:
        """Called by toolbar 'Done' button. Hides the toolbar."""
        self._hide_toolbar()

    def on_pin(self) -> None:
        """Original pin action - not used in pin window mode."""
        pass

    def on_save(self) -> None:
        """Save annotated pixmap - called by toolbar save button."""
        p = self._render_annotated_pixmap()
        self.save_requested.emit(p, True)

    def on_copy(self) -> None:
        """Copy annotated pixmap - called by toolbar copy button."""
        p = self._render_annotated_pixmap()
        self.copy_requested.emit(p)
        ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)

    def _render_annotated_pixmap(self) -> QPixmap:
        """Render the original pixmap with all annotations baked in."""
        result = self.pixmap.copy()
        if not self.annotations:
            return result
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        dpr = result.devicePixelRatio()
        logical_w = result.width() / dpr
        logical_h = result.height() / dpr
        sx = logical_w / self._img_w if self._img_w > 0 else 1.0
        sy = logical_h / self._img_h if self._img_h > 0 else 1.0
        painter.scale(sx, sy)
        for ann in self.annotations:
            self._draw_annotation(painter, ann)
        painter.end()
        return result

    def set_current_tool(self, tool_id: str) -> None:
        """Set current tool (used by toolbar)."""
        if self._text_editor:
            self._finish_text_input()
        self.current_tool = tool_id

    # ─── Toolbar Show / Hide ─────────────────────────────

    def _show_toolbar(self) -> None:
        """Create and show the annotation toolbar below the image."""
        if self._toolbar_obj is None:
            self._toolbar_obj = OverlayToolbar(self, pin_window_mode=True)
            self._toolbar_obj.setup()
            if self.current_tool in self._toolbar_obj._tool_btns:
                for tid, btn in self._toolbar_obj._tool_btns.items():
                    btn.setChecked(tid == self.current_tool)

        tb = self._toolbar_obj.toolbar
        tb.setParent(self)

        TOOLBAR_WIDTH = 420
        TOOLBAR_HEIGHT = 32
        tb.setFixedSize(TOOLBAR_WIDTH, TOOLBAR_HEIGHT)

        self._toolbar_shown = True
        self._position_toolbar()

    def _position_toolbar(self) -> None:
        """Position toolbar below the image, adjusting window size if needed."""
        if not self._toolbar_shown or not self._toolbar_obj:
            return

        tb = self._toolbar_obj.toolbar
        TOOLBAR_WIDTH = 420
        TOOLBAR_HEIGHT = 32

        s = self.SHADOW
        extra = TOOLBAR_HEIGHT + 6
        self._toolbar_extra_height = extra

        min_content_width = max(self._img_w, TOOLBAR_WIDTH + 4)
        window_width = min_content_width + s * 2
        window_height = self._img_h + s * 2 + extra

        self.setFixedSize(window_width, window_height)

        content_width = min_content_width
        if TOOLBAR_WIDTH <= content_width - 4:
            tb_x = s + content_width - TOOLBAR_WIDTH - 2
        else:
            tb_x = s + (content_width - TOOLBAR_WIDTH) // 2

        tb_y = s + self._img_h + 4
        tb.move(tb_x, tb_y)
        tb.show()
        tb.raise_()
        self.update()

    def _hide_toolbar(self) -> None:
        """Hide the annotation toolbar and restore window size."""
        if self._toolbar_obj:
            self._toolbar_obj.close_menus()
            if self._toolbar_obj.toolbar:
                self._toolbar_obj.toolbar.hide()
        self._toolbar_shown = False
        self._toolbar_extra_height = 0
        s = self.SHADOW
        self.setFixedSize(self._img_w + s * 2, self._img_h + s * 2)
        self.current_tool = "select"
        self._preview_annotation = None
        self._drawing = False
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def closeEvent(self, event) -> None:
        if self._text_editor:
            self._text_editor.hide()
            self._text_editor.deleteLater()
            self._text_editor = None
        self._cleanup_ocr()
        self._hide_toolbar()
        super().closeEvent(event)

    # ─── Crop Mode Helpers ───────────────────────────────

    def _get_crop_handle(self, pos: QPointF) -> str:
        return get_crop_handle(self._crop_rect, pos, 10) if self._crop_rect else ""

    def _update_crop_cursor(self, handle: str) -> None:
        self.setCursor(cursor_for_crop_handle(handle))

    def _resize_crop_rect(self, pos: QPointF) -> None:
        if self._crop_rect:
            self._crop_rect = resize_crop_rect(self._crop_rect, self._crop_handle, pos)

    def _draw_crop_handles(self, painter: QPainter, rect: QRectF) -> None:
        """Draw resize handles at corners of crop rect."""
        HANDLE_SIZE = 8
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        for corner in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
            painter.drawRect(QRectF(
                corner.x() - HANDLE_SIZE / 2,
                corner.y() - HANDLE_SIZE / 2,
                HANDLE_SIZE, HANDLE_SIZE,
            ))
