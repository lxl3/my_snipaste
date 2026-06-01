"""Pin window action methods (text, eraser, undo/redo, toolbar)."""

import math

from PySide6.QtWidgets import QLineEdit
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint

from ..core.logger import setup_logger

logger = setup_logger("pin_actions")


class PinWindowActionsMixin:
    """Action methods for pin window (text, eraser, undo/redo, toolbar).

    Subclass must provide:
    - self.annotations (list[dict])
    - self._undo_stack (list[dict])
    - self._redo_stack (list[dict])
    - self._text_editor (QLineEdit | None)
    - self._text_editor_pos (QPointF)
    - self._text_editor_window_pos (QPoint)
    - self._editing_annotation_idx (int | None)
    - self.current_tool (str)
    - self._selected_annotation_index (int)
    - self._toolbar_obj (OverlayToolbar)
    - self._preview_annotation (dict | None)
    - self._drawing (bool)
    - self._draw_points (list)
    - self._zoom_factor (float)
    - self.SHADOW (int)
    - self.text_font_family (str)
    - self.text_font_size (int)
    - self.text_bold (bool)
    - self.text_italic (bool)
    - self.text_color (QColor)
    - self.eraser_size (int)
    - QWidget: update()
    """

    # ─── Drawing Logic ───────────────────────────────────

    def _finish_drawing(self) -> None:
        if self._preview_annotation is None:
            return
        ann = dict(self._preview_annotation)
        self._preview_annotation = None
        if ann["type"] in ("arrow", "line"):
            start = QPointF(ann["start"][0], ann["start"][1])
            end = QPointF(ann["end"][0], ann["end"][1])
            if (end - start).manhattanLength() < 5:
                return  # too short
        self._add_annotation(ann)
        self._drawing = False
        self._draw_points = []

    def _add_annotation(self, ann: dict) -> None:
        self.annotations.append(ann)
        self._undo_stack.append({"type": "add", "ann": dict(ann), "index": len(self.annotations) - 1})
        self._redo_stack.clear()
        self._update_toolbar_undo_redo()
        self.update()

    # ─── Text Editing ────────────────────────────────────

    def _finish_text(self, pos: QPointF) -> None:
        """Create inline text editor at the clicked position."""
        # Clean up any existing text editor
        if self._text_editor:
            self._finish_text_input()

        self._text_editor_pos = pos
        self._editing_annotation_idx = None

        # Create QLineEdit for inline editing
        self._text_editor = QLineEdit(self)
        font = QFont(self.text_font_family, self.text_font_size)
        font.setBold(self.text_bold)
        font.setItalic(self.text_italic)
        self._text_editor.setFont(font)

        # Convert content position to window position
        # pos is already in image coordinates, need to convert to widget coordinates
        window_x = int(pos.x() * self._zoom_factor) + self.SHADOW - 1
        window_y = int(pos.y() * self._zoom_factor) + self.SHADOW - 1
        self._text_editor_window_pos = QPoint(window_x, window_y)

        # Style the text editor to be transparent with colored text
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
        self._text_editor.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._text_editor.move(self._text_editor_window_pos)
        self._text_editor.setMinimumWidth(50)
        self._text_editor.setAttribute(Qt.WA_DeleteOnClose)

        # Connect signals for dynamic resizing and finishing
        self._text_editor.textChanged.connect(self._adjust_text_editor_size)
        self._adjust_text_editor_size()

        self._text_editor.show()
        self._text_editor.setFocus()
        self._text_editor.returnPressed.connect(self._finish_text_input)
        self._text_editor.editingFinished.connect(self._finish_text_input)

    def _adjust_text_editor_size(self) -> None:
        """Dynamically adjust text editor size to fit content (from OverlayActionsMixin)."""
        if not self._text_editor:
            return
        text = self._text_editor.text()
        fm = self._text_editor.fontMetrics()

        # Calculate width: text width + padding for cursor + buffer space
        # Need enough padding to prevent text from being clipped during typing
        # Cursor width (~2px) + buffer for comfortable typing (~15px)
        padding = 20
        width = fm.horizontalAdvance(text) + padding if text else 50
        height = fm.height() + 4

        # Get fixed left position - this ensures the editor expands to the right
        current_pos = getattr(self, '_text_editor_window_pos', self._text_editor.pos())

        # Resize first (expands rightward due to AlignLeft), then move to keep left edge fixed
        self._text_editor.resize(max(width, 50), height)
        self._text_editor.move(current_pos)

    def _finish_text_input(self) -> None:
        """Finalize text input from the inline editor (from OverlayActionsMixin)."""
        if not self._text_editor or self._text_editor_pos is None:
            return
        text = self._text_editor.text().strip()
        if text:
            # Update existing text annotation OR create new one
            if getattr(self, '_editing_annotation_idx', None) is not None:
                idx = self._editing_annotation_idx
                if 0 <= idx < len(self.annotations):
                    ann = self.annotations[idx]
                    ann["text"] = text
                    ann["color"] = QColor(self.text_color)
                    ann["font_family"] = self.text_font_family
                    ann["font_size"] = self.text_font_size
                    ann["bold"] = self.text_bold
                    ann["italic"] = self.text_italic
            else:
                # Store pos as tuple for consistency with other PinWindow annotations
                self.annotations.append({
                    "type": "text",
                    "pos": (self._text_editor_pos.x(), self._text_editor_pos.y()),
                    "text": text,
                    "color": QColor(self.text_color),
                    "font_family": self.text_font_family,
                    "font_size": self.text_font_size,
                    "bold": self.text_bold,
                    "italic": self.text_italic,
                })
                self._undo_stack.append({"type": "add", "ann": self.annotations[-1], "index": len(self.annotations) - 1})
            self._redo_stack.clear()
            self._update_toolbar_undo_redo()
            self.update()

        self._text_editor.textChanged.disconnect()
        self._text_editor.returnPressed.disconnect()
        self._text_editor.editingFinished.disconnect()
        self._text_editor.hide()
        self._text_editor.deleteLater()
        self._text_editor = None
        self._text_editor_pos = None
        self._editing_annotation_idx = None

    # ─── Eraser ──────────────────────────────────────────

    def _on_annotation_removed(self, removed_idx: int) -> None:
        """Update selection state when an annotation is removed by index (from OverlayActionsMixin)."""
        sel = getattr(self, '_selected_annotation_index', None)
        if sel is None:
            return
        if sel == removed_idx:
            self._deselect_annotation()
        elif sel > removed_idx:
            self._selected_annotation_index = sel - 1

    @staticmethod
    def _point_to_rect_distance(point: QPointF, rect: QRectF) -> float:
        """Calculate minimum distance from a point to a rectangle (from OverlayActionsMixin)."""
        cx = max(rect.left(), min(point.x(), rect.right()))
        cy = max(rect.top(), min(point.y(), rect.bottom()))
        return math.hypot(point.x() - cx, point.y() - cy)

    @staticmethod
    def _point_to_segment_distance(point: QPointF, p1: QPointF, p2: QPointF) -> float:
        """Calculate minimum distance from a point to a line segment (from OverlayActionsMixin)."""
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
        """Try to erase annotation at the given position (adapted from OverlayActionsMixin)."""
        r = self.eraser_size
        print(f"[DEBUG] 擦除检测: pos=({pos.x():.0f},{pos.y():.0f}), r={r}, annotations={len(self.annotations)}")
        logger.debug(f"擦除检测: pos=({pos.x():.0f},{pos.y():.0f}), r={r}, annotations={len(self.annotations)}")
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann["type"]
            if t in ("rect", "ellipse", "mosaic", "blur", "magnifier"):
                # Support both tuple and QRectF formats
                rect_data = ann["rect"]
                if isinstance(rect_data, tuple):
                    ann_rect = QRectF(rect_data[0], rect_data[1], rect_data[2], rect_data[3])
                else:
                    ann_rect = QRectF(rect_data)
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
                # Support both tuple and QPointF formats for start/end
                start = ann["start"] if isinstance(ann["start"], QPointF) else QPointF(ann["start"][0], ann["start"][1])
                end = ann["end"] if isinstance(ann["end"], QPointF) else QPointF(ann["end"][0], ann["end"][1])
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
                pts = ann["points"]
                for j in range(len(pts) - 1):
                    p1 = pts[j] if isinstance(pts[j], QPointF) else QPointF(pts[j][0], pts[j][1])
                    p2 = pts[j + 1] if isinstance(pts[j + 1], QPointF) else QPointF(pts[j + 1][0], pts[j + 1][1])
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
                font = QFont(ann["font_family"], ann["font_size"])
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = QFontMetrics(font)
                tw = fm.horizontalAdvance(ann["text"])
                th = fm.height()
                # Support both tuple and QPointF formats
                text_pos = ann["pos"]
                if isinstance(text_pos, tuple):
                    text_rect = QRectF(text_pos[0], text_pos[1], tw, th)
                else:
                    text_rect = QRectF(text_pos.x(), text_pos.y(), tw, th)
                d = self._point_to_rect_distance(pos, text_rect)
                logger.debug(f"  [{i}] type=text, pos={ann['pos']}, text_rect={text_rect}, dist={d:.1f}")
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
                # Support both tuple and QPointF formats
                marker_pos = ann["pos"]
                center = QPointF(marker_pos[0], marker_pos[1]) if isinstance(marker_pos, tuple) else QPointF(marker_pos)
                radius = ann.get("radius", 14)
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

    # ─── Toolbar Interface (called by OverlayToolbar) ────

    def _on_tool_selected(self, tool_id: str) -> None:
        # Clean up text editor when switching tools
        if self._text_editor:
            self._finish_text_input()
        self.current_tool = tool_id

    def _apply_property_to_selected(self, prop: str, value) -> None:
        if 0 <= self._selected_annotation_index < len(self.annotations):
            self.annotations[self._selected_annotation_index][prop] = value
            self.update()

    # ─── Undo / Redo ─────────────────────────────────────

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        if action["type"] == "add":
            ann = self.annotations.pop(action["index"])
            self._redo_stack.append({"type": "remove", "ann": ann, "index": action["index"]})
        elif action["type"] == "remove":
            self.annotations.insert(action["index"], action["ann"])
            self._redo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        self._update_toolbar_undo_redo()
        self.update()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        if action["type"] == "add":
            self.annotations.append(action["ann"])
            self._undo_stack.append({"type": "remove", "ann": action["ann"], "index": len(self.annotations) - 1})
        elif action["type"] == "remove":
            self.annotations.insert(action["index"], action["ann"])
            self._undo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        self._update_toolbar_undo_redo()
        self.update()

    def _update_toolbar_undo_redo(self) -> None:
        if self._toolbar_obj:
            self._toolbar_obj.update_undo_redo_state()
