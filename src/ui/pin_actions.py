"""Pin window action methods (text, eraser, undo/redo, transform, toolbar)."""

import math

from PIL import Image
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPixmap, QPainter
from PySide6.QtWidgets import QLineEdit

from ..core.logger import setup_logger
from ..core.utils import qpixmap_to_pil, pil_to_qpixmap

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
        # Select the newly added annotation (matching overlay behavior)
        self._selected_annotation_index = len(self.annotations) - 1
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
        # Deselect any selected annotation when switching tools
        self._deselect_annotation()
        # Clean up text editor when switching tools
        if self._text_editor:
            self._finish_text_input()
        self.current_tool = tool_id

    def _apply_property_to_selected(self, key: str, value) -> None:
        """Update a property on the currently selected annotation, if any."""
        if not (0 <= self._selected_annotation_index < len(self.annotations)):
            return
        ann = self.annotations[self._selected_annotation_index]
        if key == "color" and "color" in ann:
            ann["color"] = value if isinstance(value, str) else value.name()
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
            ann["color"] = value if isinstance(value, str) else value.name()
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

    # ─── Image transforms (rotate / flip) ─────────────────

    def _transform_annotations(self, xform) -> None:
        """Apply *xform(x, y) → (x', y')* to every annotation's coordinates.
        Annotations in PinWindow use tuple coords relative to image (0,0).
        """
        for ann in self.annotations:
            t = ann["type"]
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                x, y, w, h = ann["rect"]
                nx, ny = xform(x, y)
                ann["rect"] = (nx, ny, w, h)
                ann.pop("_cached", None)
            elif t in ("arrow", "line"):
                ann["start"] = xform(*ann["start"])
                ann["end"] = xform(*ann["end"])
            elif t == "freehand":
                ann["points"] = [xform(*p) for p in ann["points"]]
                ann.pop("_path", None)
            elif t in ("text", "number_marker"):
                ann["pos"] = xform(*ann["pos"])

    def _rotate_cw(self) -> None:
        """Rotate image and annotations 90° clockwise."""
        pil_img = qpixmap_to_pil(self.pixmap)
        rotated = pil_img.rotate(-90, expand=True, fillcolor=(0, 0, 0, 0))
        self.pixmap = pil_to_qpixmap(rotated)
        self.pixmap.setDevicePixelRatio(self.pixmap.devicePixelRatio())

        old_w, old_h = self._base_img_w, self._base_img_h
        self._base_img_w, self._base_img_h = old_h, old_w

        def xform(x, y):
            return old_h - y, x

        self._transform_annotations(xform)
        self._after_transform()

    def _rotate_ccw(self) -> None:
        """Rotate image and annotations 90° counter-clockwise."""
        pil_img = qpixmap_to_pil(self.pixmap)
        rotated = pil_img.rotate(90, expand=True, fillcolor=(0, 0, 0, 0))
        self.pixmap = pil_to_qpixmap(rotated)
        self.pixmap.setDevicePixelRatio(self.pixmap.devicePixelRatio())

        old_w, old_h = self._base_img_w, self._base_img_h
        self._base_img_w, self._base_img_h = old_h, old_w

        def xform(x, y):
            return y, old_w - x

        self._transform_annotations(xform)
        self._after_transform()

    def _flip_h(self) -> None:
        """Flip image and annotations horizontally."""
        pil_img = qpixmap_to_pil(self.pixmap)
        flipped = pil_img.transpose(Image.FLIP_LEFT_RIGHT)
        self.pixmap = pil_to_qpixmap(flipped)
        self.pixmap.setDevicePixelRatio(self.pixmap.devicePixelRatio())

        w = self._base_img_w

        def xform(x, y):
            return w - x, y

        self._transform_annotations(xform)
        self._after_transform()

    def _flip_v(self) -> None:
        """Flip image and annotations vertically."""
        pil_img = qpixmap_to_pil(self.pixmap)
        flipped = pil_img.transpose(Image.FLIP_TOP_BOTTOM)
        self.pixmap = pil_to_qpixmap(flipped)
        self.pixmap.setDevicePixelRatio(self.pixmap.devicePixelRatio())

        h = self._base_img_h

        def xform(x, y):
            return x, h - y

        self._transform_annotations(xform)
        self._after_transform()

    # ─── Crop ────────────────────────────────────────────

    def _crop(self) -> None:
        """Enter crop mode or execute crop if already in crop mode with selection."""
        # Already in crop mode with valid selection → execute crop
        if self._crop_mode and self._crop_rect and not self._crop_rect.isEmpty():
            self._execute_crop()
            return

        # Enter crop mode
        self._crop_mode = True
        self._crop_rect = None
        self._crop_dragging = False
        self._crop_handle = ""
        # Hide toolbar to focus on cropping
        if self._toolbar_shown:
            self._hide_toolbar()
        self.setCursor(Qt.CrossCursor)
        self.update()
        # Show usage hint
        from ..core.i18n import _
        from ..ui.toast import ToastManager
        ToastManager.show(
            _("Drag to select area, Enter to confirm, Esc to cancel"),
            "✂", "info", parent=self, duration=3000
        )

    def _execute_crop(self) -> None:
        """Execute the crop operation with current crop_rect."""
        if not self._crop_rect or self._crop_rect.isEmpty():
            return

        x, y = self._crop_rect.x(), self._crop_rect.y()
        w, h = self._crop_rect.width(), self._crop_rect.height()

        if w <= 1 or h <= 1:
            self._exit_crop_mode()
            return

        # Clamp to image bounds
        x = max(0, x)
        y = max(0, y)
        w = min(w, self._base_img_w - x)
        h = min(h, self._base_img_h - y)

        pil_img = qpixmap_to_pil(self.pixmap)
        dpr = self.pixmap.devicePixelRatio()
        crop_box = (int(x * dpr), int(y * dpr),
                    int((x + w) * dpr), int((y + h) * dpr))
        cropped = pil_img.crop(crop_box)
        self.pixmap = pil_to_qpixmap(cropped)
        self.pixmap.setDevicePixelRatio(dpr)

        new_w = int(w)
        new_h = int(h)
        self._base_img_w = new_w
        self._base_img_h = new_h
        crop_rect = QRectF(0, 0, new_w, new_h)

        # Filter & offset surviving annotations
        surviving = []
        for a in self.annotations:
            t = a["type"]
            keep = False
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                r = a["rect"]
                r_rect = QRectF(r) if isinstance(r, QRectF) else QRectF(*r)
                keep = r_rect.intersects(crop_rect)
                if keep:
                    a["rect"] = (r_rect.x() - x, r_rect.y() - y,
                                 r_rect.width(), r_rect.height())
                if t in ("mosaic", "blur", "magnifier"):
                    a.pop("_cached", None)
            elif t in ("arrow", "line"):
                sd, ed = a["start"], a["end"]
                sp = sd if isinstance(sd, QPointF) else QPointF(*sd)
                ep = ed if isinstance(ed, QPointF) else QPointF(*ed)
                keep = crop_rect.contains(sp) or crop_rect.contains(ep)
                if keep:
                    a["start"] = (sp.x() - x, sp.y() - y)
                    a["end"] = (ep.x() - x, ep.y() - y)
            elif t == "freehand":
                pts = [p if isinstance(p, QPointF) else QPointF(*p) for p in a["points"]]
                keep = any(crop_rect.contains(p) for p in pts)
                if keep:
                    a["points"] = [(p.x() - x, p.y() - y) for p in pts]
                a.pop("_path", None)
            elif t in ("text", "number_marker"):
                pd = a["pos"]
                pos = QPointF(*pd) if isinstance(pd, (list, tuple)) else QPointF(pd)
                keep = crop_rect.contains(pos)
                if keep:
                    a["pos"] = (pos.x() - x, pos.y() - y)
            if keep:
                surviving.append(a)

        self.annotations = surviving
        self._selected_annotation_index = -1

        # Exit crop mode and update
        self._exit_crop_mode()
        self._after_transform()

        from ..core.i18n import _
        from ..ui.toast import ToastManager
        ToastManager.show(
            _("Cropped to {w} × {h}").format(w=new_w, h=new_h),
            "✂", "success", parent=self
        )

    def _exit_crop_mode(self) -> None:
        """Exit crop mode without cropping."""
        self._crop_mode = False
        self._crop_rect = None
        self._crop_dragging = False
        self._crop_handle = ""
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def _after_transform(self) -> None:
        """Common post-transform steps: reset zoom, resize window, clear undo/redo."""
        self._zoom_factor = 1.0
        self._img_w = self._base_img_w
        self._img_h = self._base_img_h
        self.setFixedSize(self._img_w + self.SHADOW * 2,
                          self._img_h + self.SHADOW * 2)
        if self._toolbar_obj and self._toolbar_shown:
            self._position_toolbar()
        self._undo_stack.clear()
        self._redo_stack.clear()
        if self._toolbar_obj:
            self._toolbar_obj.update_undo_redo_state()
        self.update()
        logger.info("Image transformed")
