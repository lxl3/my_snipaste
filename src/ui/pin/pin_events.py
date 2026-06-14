"""Event handler mixin for PinWindow.

Provides mouse and keyboard event handling that delegates to
other mixins via the composition pattern.
"""

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ...core.geometry import cursor_for_crop_handle, get_crop_handle, resize_crop_rect
from ...core.logger import setup_logger

logger = setup_logger("pin_window")


class PinWindowEventHandlerMixin:
    """Mouse and keyboard event handling for PinWindow.

    Contract (resolved at runtime on PinWindow):
        State:
            _crop_mode, _crop_rect, _crop_dragging, _crop_start, _crop_handle
            _text_editor, _resizing, _resize_dir, _resize_start_pos, _resize_start_geometry
            _toolbar_shown, current_tool, _selected_annotation_index
            _dragging, _drag_pos, _dragging_annotation, _drag_start
            _drawing, _current_mouse_pos, _img_w, _img_h, _zoom_factor
            _resized_by_user, _base_img_w, _base_img_h, _toolbar_extra_height
            _thumbnail_mode, _preview_annotation, _annotation_drag_orig
            annotations, pixmap, ctx, toolbar_obj
            eraser_size, _toolbar_obj
        Methods:
            _finish_text_input, _get_resize_direction, _handle_resize, _update_cursor
            _try_erase_annotation, _hit_test_annotations, _select_annotation, _deselect_annotation
            _start_drawing, _update_drawing, _finish_drawing
            _position_toolbar, _hide_toolbar, _show_toolbar
            _execute_crop, _exit_crop_mode
            setFixedSize, setCursor, move, update, geometry, pos, width, height
            grabKeyboard, releaseKeyboard, close
    """

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
                ann_type = self.annotations[hit_idx].type
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
