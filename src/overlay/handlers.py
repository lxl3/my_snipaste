"""Event handler mixin for CaptureOverlay.

Provides mouse and keyboard event handling that delegates to
other mixins via the composition pattern.
"""

import os

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from ..core.constants import MIN_SELECTION_SIZE
from ..core.i18n import _
from ..core.logger import setup_logger
from ..core.theme_pkg import draw_glass_morphism, draw_glass_text
from ..core.theme_pkg import theme as _t
from .hotkey_panel import HotkeyHelpPanel

logger = setup_logger("overlay")


class OverlayEventHandlerMixin:
    """Mouse and keyboard event handling for CaptureOverlay.

    Contract (resolved at runtime on CaptureOverlay):
        State:
            selection_rect, current_mouse_pos, current_tool, is_selecting
            start_point, end_point, annotations, _selected_annotation_idx
            _drawing, _erasing, _drag_mode, _erase_fill_rect_start/current
            _text_editor, _text_editor_pos, _preview_annotation
            _undo_stack, _redo_stack, _closing_on_release
            ctx, toolbar, crop, window_snap, _hotkey_panel
        Methods:
            on_copy, on_save, on_pin, _undo, _redo
            _deselect_annotation, _select_annotation, _hit_test_annotation
            _annotation_handle_at_pos, _begin_annotation_resize
            _handle_at_pos, _cursor_for_handle, _cursor_for_annotation_handle
            _start_selection, _begin_drag, _update_drag
            _constrain_rect_to_screen, _start_drawing, _update_drawing, _finish_drawing
            _try_erase_annotation, _execute_erase_fill, _erase_in_rect
            _on_tool_selected, _position_toolbar, _render_annotated_pixmap
            _finish_text_input, _reopen_text_editor
    """

    def mousePressEvent(self, event) -> None:
        if self._text_editor and not self._text_editor.geometry().contains(event.position().toPoint()):
            self._finish_text_input()

        if event.button() == Qt.RightButton:
            event.accept()
            if not self.selection_rect.isNull():
                return
            if self._drag_mode:
                self.selection_rect = QRect()
                self._drag_mode = None
                self._deselect_annotation()
                self.annotations.clear()
                self.toolbar.close_menus()
                self.toolbar.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
            self.window_snap.reset()
            self._closing_on_release = True
            return

        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self.window_snap.save_for_snap()
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

            if self.crop.active:
                self.crop.handle_mouse_press(pos)
                return

            # ─── Annotation selection / hit-test ───
            if not self.selection_rect.isNull() and self.annotations:
                hit_idx = self._hit_test_annotation(pos)
                if hit_idx is not None:
                    if hit_idx == self._selected_annotation_idx:
                        handle = self._annotation_handle_at_pos(
                            self.annotations[hit_idx], pos, self.selection_rect.topLeft()
                        )
                        if handle:
                            self._begin_annotation_resize(hit_idx, handle, event.position())
                            return
                    ann_type = self.annotations[hit_idx]["type"]
                    if ann_type in ("arrow", "line"):
                        if self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                            self._selected_annotation_idx = hit_idx
                            self.update()
                            return
                    elif self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                        self._select_annotation(hit_idx, event.position())
                        return
                if self._selected_annotation_idx is not None:
                    self._deselect_annotation()

            if not self.selection_rect.isNull():
                handle = self._handle_at_pos(pos)
                if handle:
                    self._begin_drag(("resize", handle), event)
                    return
                if self.current_tool != "select":
                    self._start_drawing(pos)
                    return
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
        if self.crop.active:
            self.crop.handle_mouse_move(self.current_mouse_pos)
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
            self.window_snap.update_detection(self.current_mouse_pos)
        elif not self.selection_rect.isNull():
            hit_idx = self._hit_test_annotation(self.current_mouse_pos)
            if hit_idx is not None:
                if hit_idx == self._selected_annotation_idx:
                    handle = self._annotation_handle_at_pos(
                        self.annotations[hit_idx], self.current_mouse_pos, self.selection_rect.topLeft()
                    )
                    if handle:
                        self.setCursor(self._cursor_for_annotation_handle(handle))
                        self.update()
                        return
                ann_type = self.annotations[hit_idx]["type"]
                if ann_type in ("arrow", "line"):
                    self.setCursor(Qt.SizeVerCursor)
                elif self.current_tool == "select" or self.current_tool == ann_type or self.current_tool == "":
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    handle = self._handle_at_pos(self.current_mouse_pos)
                    self.setCursor(self._cursor_for_handle(handle))
            else:
                handle = self._handle_at_pos(self.current_mouse_pos)
                self.setCursor(self._cursor_for_handle(handle))
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            event.accept()
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
        if self.crop.active and self.crop.dragging:
            self.crop.handle_mouse_release()
            return
        if self._drawing:
            self._finish_drawing()
            return
        if self._drag_mode:
            mode = self._drag_mode[0]
            # Commit annotation resize/move to undo stack
            if mode in ("move_annotation", "resize_annotation") and self._selected_annotation_idx is not None:
                self._redo_stack.clear()
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
            elif sr := self.window_snap.apply_snap():
                self.selection_rect = sr
                self._position_toolbar()
            else:
                self.selection_rect = QRect()

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to re-edit text or auto-finish capture."""
        if event.button() != Qt.LeftButton:
            return
        if self.selection_rect.isNull():
            return

        if self.crop.handle_mouse_double_click(event.pos()):
            return

        # Text annotation re-edit (takes priority)
        hit_idx = self._hit_test_annotation(event.pos())
        if hit_idx is not None and self.annotations[hit_idx]["type"] == "text":
            self._reopen_text_editor(hit_idx)
            return

        # Only auto-finish if we have a valid selection
        if self.selection_rect.contains(event.pos()):
            self._auto_finish()

    def keyPressEvent(self, event) -> None:
        # Hotkey help panel toggle
        if event.key() == Qt.Key_Question or event.key() == Qt.Key_F1:
            self._toggle_hotkey_panel()
            event.accept()
            return

        # ─── Single-key tool shortcuts (only when no modifier held) ───
        if (not event.modifiers()
                and self._text_editor is None
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
                if self.current_tool == tid:
                    self._on_tool_selected("select")
                else:
                    self._on_tool_selected(tid)
                event.accept()
                return

        if event.key() == Qt.Key_Escape:
            if self._hotkey_panel and self._hotkey_panel.isVisible():
                self._hotkey_panel.hide()
                return
            if self._text_editor:
                self._text_editor.hide()
                self._text_editor.deleteLater()
                self._text_editor = None
                self._text_editor_pos = None
                self.grabKeyboard()
                return
            if self.crop.handle_escape():
                return
            if self._drawing or self._erasing or self._erase_fill_rect_start is not None:
                self._drawing = False
                self._erasing = False
                self._erase_fill_rect_start = None
                self._erase_fill_rect_current = None
                self._preview_annotation = None
                self.update()
                return
            if self.is_selecting:
                self.is_selecting = False
                self.selection_rect = QRect()
                self.update()
                return
            if self._selected_annotation_idx is not None:
                self._deselect_annotation()
                return
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
            if self.crop.handle_enter():
                return
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

    # ─── Helpers ───

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

    def _auto_save(self) -> None:
        """Automatically save to configured directory."""
        if self.selection_rect.isNull():
            return

        s = self.ctx.settings
        if not s.auto_save_dir:
            logger.warning("Auto-save requested but no directory configured")
            self.on_save()
            return

        from datetime import datetime
        filename = f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{s.auto_save_format}"
        filepath = os.path.join(s.auto_save_dir, filename)

        pixmap = self._render_annotated_pixmap()
        pixmap.save(filepath)
        logger.info(f"Auto-saved to {filepath}")
        self.close()

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
            panel_x = (self.width() - self._hotkey_panel.width()) // 2
            panel_y = (self.height() - self._hotkey_panel.height()) // 2
            self._hotkey_panel.move(panel_x, panel_y)
            self._hotkey_panel.show()
        elif self._hotkey_panel.isVisible():
            self._hotkey_panel.hide()
        else:
            self._hotkey_panel.show()

    # ─── Drawing helpers (used by paintEvent in widget.py) ───

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
        if self._drag_mode is None:
            return
        mode = self._drag_mode[0]
        if mode not in ("move", "resize"):
            return

        s = self.ctx.settings
        action = s.capture_after_action
        if action == "none":
            return

        if action == "copy":
            hint_text = _("💡 Double-click or press Enter to copy")
        elif action == "save":
            hint_text = _("💡 Double-click or press Enter to save")
        else:
            return

        font = QFont("Segoe UI", 12, QFont.Medium)
        painter.setFont(font)

        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(hint_text)
        th = fm.height()
        padding_h = 12
        padding_v = 8

        bx = rect.center().x() - tw // 2 - padding_h
        by = rect.bottom() + 12
        if by + th + padding_v * 2 > self.height() - 10:
            by = rect.top() - th - padding_v * 2 - 32

        bw = tw + padding_h * 2
        bh = th + padding_v * 2
        hint_rect = QRect(bx, by, bw, bh)

        is_dark = _t.is_dark()
        draw_glass_morphism(painter, hint_rect, radius=12, is_dark=is_dark, draw_shadow=True)
        draw_glass_text(
            painter,
            int(bx + padding_h),
            int(by + padding_v + fm.ascent()),
            hint_text,
            is_dark=is_dark,
            glow_enabled=True
        )

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
