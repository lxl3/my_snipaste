"""Overlay drawing state management and tool handling."""

from PySide6.QtWidgets import QLineEdit
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QTimer

from ..core.constants import MIN_DRAW_THRESHOLD, MIN_SELECTION_SIZE
from ..core.settings import get_settings
from ..core.logger import setup_logger

logger = setup_logger("overlay_drawing")


class OverlayDrawingMixin:
    """Drawing state management, tool selection, and toolbar callbacks.

    Subclass must provide:
    - self.selection_rect (QRect)
    - self.annotations (list[dict])
    - self.current_mouse_pos (QPoint)
    - self.current_tool (str)
    - self.current_color (QColor)
    - self.current_width (int)
    - self.current_mosaic_scale (int)
    - self.current_blur_radius (int)
    - self.current_magnifier_zoom (int)
    - self.text_font_family (str)
    - self.text_font_size (int)
    - self.text_bold (bool)
    - self.text_italic (bool)
    - self.text_color (QColor)
    - self._drawing (bool)
    - self._draw_start (QPointF)
    - self._draw_points (list[QPointF])
    - self._preview_annotation (dict | None)
    - self._text_editor (QLineEdit | None)
    - self._text_editor_pos (QPointF)
    - self._text_editor_window_pos (QPoint)
    - self._marker_counter (int)
    - self._drag_mode (tuple | None)
    - self._drag_start_pos (QPointF)
    - self._drag_start_rect (QRect)
    - self._undo_stack (list[dict])
    - self._redo_stack (list[dict])
    - self.toolbar (OverlayToolbar)
    - self.is_selecting (bool)
    - self.start_point (QPoint)
    - self.end_point (QPoint)
    - self._sel_to_local (method from parent)
    - self._constrain_rect_to_screen (method from OverlaySelectionMixin)
    - self._deselect_annotation (method from OverlaySelectionMixin)
    - self._move_selected_annotation (method from OverlaySelectionMixin)
    - self._adjust_text_editor_size (method from OverlayActionsMixin)
    - self._finish_text_input (method from OverlayActionsMixin)
    - QWidget: update(), releaseKeyboard()
    """

    # ─── Drawing State Management ───

    def _start_drawing(self, pos: QPoint) -> None:
        """Start drawing an annotation at the given position."""
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

    def _update_drawing(self) -> None:
        """Update current drawing annotation based on mouse movement."""
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
                    "arrow_style": self.current_arrow_style,
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

    def _finish_drawing(self) -> None:
        """Finish current drawing and add annotation to the list."""
        self._drawing = False
        if self._preview_annotation and self._preview_annotation["type"] != "freehand":
            ann = self._preview_annotation
            if ann["type"] in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier") and ann["rect"].width() > MIN_DRAW_THRESHOLD and ann["rect"].height() > MIN_DRAW_THRESHOLD:
                self.annotations.append(ann)
                self._selected_annotation_idx = len(self.annotations) - 1
                self._undo_stack.append({"type": "add", "ann": ann, "index": len(self.annotations) - 1})
                self._redo_stack.clear()
                self.toolbar.update_undo_redo_state()
            elif ann["type"] in ("arrow", "line"):
                dx = ann["end"].x() - ann["start"].x()
                dy = ann["end"].y() - ann["start"].y()
                if abs(dx) > MIN_DRAW_THRESHOLD or abs(dy) > MIN_DRAW_THRESHOLD:
                    self.annotations.append(ann)
                    self._selected_annotation_idx = len(self.annotations) - 1
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

    # ─── Selection State Management ───

    def _start_selection(self, pos: QPoint) -> None:
        """Start a new selection rectangle at the given position."""
        # safety: keep annotations when eraser is active
        if self.current_tool in ("eraser_dot", "eraser_fill") and self.annotations:
            logger.warning(f"_start_selection called during eraser mode (annotations={len(self.annotations)}), ignoring")
            return
        self.is_selecting = True
        self.toolbar.close_menus()  # 关闭子菜单
        self.toolbar.toolbar.hide()
        self._deselect_annotation()
        self._detected_window_rect = None  # clear window highlight
        self._window_snap_rect = None  # clear pending snap
        self.annotations.clear()
        self.start_point = pos
        self.end_point = self.start_point
        self.selection_rect = QRect()
        # Use _on_tool_selected to properly save/restore settings
        self._on_tool_selected("select")
        self.update()

    def _begin_drag(self, mode, event) -> None:
        """Begin dragging operation (move/resize selection or move annotation)."""
        self._drag_mode = mode
        self._drag_start_pos = event.position()
        self._drag_start_rect = QRect(self.selection_rect)
        self.toolbar.close_menus()  # 关闭子菜单
        self.toolbar.toolbar.hide()

    def _update_drag(self, current_pos: QPointF) -> None:
        """Update drag operation based on current mouse position."""
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
        elif mode == "resize_annotation":
            if self._selected_annotation_idx is not None:
                self._resize_annotation(
                    self.annotations[self._selected_annotation_idx],
                    delta, self._drag_mode[1]
                )
        self.update()

    # ─── Tool Settings ───

    def _save_current_tool_settings(self) -> None:
        """Save current tool settings to persistent storage."""
        # Only save settings for annotation tools (not select or eraser)
        if self.current_tool not in ("select", "eraser_dot", "eraser_fill"):
            settings_dict = {
                "color": self.current_color.name(),
                "width": self.current_width,
            }
            # Save arrow_style for arrow/line tools
            if self.current_tool in ("arrow", "line"):
                settings_dict["arrow_style"] = self.current_arrow_style
            s = get_settings()
            s.save_tool_settings(self.current_tool, settings_dict)

    # ─── Toolbar Callbacks ───

    def _on_tool_selected(self, tool_id: str) -> None:
        """Handle tool selection from toolbar."""
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
                # Restore arrow_style for arrow/line tools
                if tool_id in ("arrow", "line"):
                    saved_arrow_style = tool_settings.get("arrow_style", "solid")
                    if saved_arrow_style in ("solid", "hollow", "solid_tail", "hollow_tail"):
                        self.current_arrow_style = saved_arrow_style

        # Update UI
        for tid, btn in self.toolbar._tool_btns.items():
            btn.setChecked(tid == tool_id)
        self.update()
        if tool_id in ("eraser_dot", "eraser_fill"):
            self.setCursor(Qt.CrossCursor)
        elif tool_id == "select":
            self.setCursor(Qt.SizeAllCursor if not self.selection_rect.isNull() else Qt.CrossCursor)

    def _on_color_changed(self, color: QColor) -> None:
        """Handle color change from toolbar."""
        self.current_color = color
        if self.current_tool == "mosaic":
            QTimer.singleShot(50, self.update)

    def _on_width_changed(self, width: int) -> None:
        """Handle width change from toolbar."""
        self.current_width = width
        if self.current_tool == "mosaic":
            QTimer.singleShot(50, self.update)

    def _on_font_family_changed(self, family: str) -> None:
        """Handle font family change from toolbar."""
        self.text_font_family = family

    def _on_font_size_changed(self, size: int) -> None:
        """Handle font size change from toolbar."""
        self.text_font_size = size

    def _on_bold_toggled(self, bold: bool) -> None:
        """Handle bold toggle from toolbar."""
        self.text_bold = bold

    def _on_italic_toggled(self, italic: bool) -> None:
        """Handle italic toggle from toolbar."""
        self.text_italic = italic
