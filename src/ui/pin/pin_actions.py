"""Pin window action methods (text, eraser, undo/redo, transform, toolbar)."""

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit

from ...annotations import Annotation
from ...core.logger import setup_logger
from ...core.utils import pil_to_qpixmap, qpixmap_to_pil
from .pin_eraser import PinWindowEraserMixin

logger = setup_logger("pin_actions")


class PinWindowActionsMixin(PinWindowEraserMixin):
    """Action methods for pin window (text, eraser, undo/redo, toolbar).

    Subclass must provide:
    - self.annotations (list[Annotation])
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
    - self._draw_start (QPointF)
    - self._draw_points (list[QPointF])
    - self._zoom_factor (float)
    - self.SHADOW (int)
    - self._resized_by_user (bool)
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
        ann = self._preview_annotation
        self._preview_annotation = None
        if ann.type in ("arrow", "line"):
            start = ann.start
            end = ann.end
            if (end - start).manhattanLength() < 5:
                return  # too short
        self._add_annotation(ann)
        self._drawing = False
        self._draw_points = []

    def _content_pos(self, event) -> QPointF:
        """Convert widget position to content-area coordinates (in original image space)."""
        display_x = event.position().x() - self.SHADOW
        display_y = event.position().y() - self.SHADOW
        if self._zoom_factor != 1.0 and not self._resized_by_user:
            orig_x = display_x / self._zoom_factor
            orig_y = display_y / self._zoom_factor
        else:
            orig_x = display_x
            orig_y = display_y
        return QPointF(orig_x, orig_y)

    def _start_drawing(self, event) -> None:
        self._deselect_annotation()
        self._drawing = True
        pos = self._content_pos(event)
        self._draw_start = pos
        self._draw_points = [pos]

        t = self.current_tool
        if t == "text":
            self._finish_text(pos)
            self._drawing = False
        elif t == "number_marker":
            count = sum(1 for a in self.annotations if a.type == "number_marker") + 1
            ann = Annotation(
                type="number_marker",
                pos=(pos.x(), pos.y()),
                radius=14,
                number=count,
                color=self.current_color.name(),
                text_color="#ffffff",
            )
            self._add_annotation(ann)
            self._drawing = False
        elif t in ("rect", "ellipse", "arrow", "line", "highlighter", "freehand", "mosaic", "blur", "magnifier"):
            pass

    def _update_drawing(self, event) -> None:
        pos = self._content_pos(event)
        t = self.current_tool

        MIN_DRAW_THRESHOLD = 5

        if t in ("rect", "ellipse", "highlighter"):
            r = QRectF(self._draw_start, pos).normalized()
            self._preview_annotation = Annotation(
                type=t,
                rect=(r.x(), r.y(), r.width(), r.height()),
                color=self.current_color.name(),
                width=self.current_width if t not in ("highlighter",) else 12,
            )
        elif t == "mosaic":
            r = QRectF(self._draw_start, pos).normalized()
            if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                self._preview_annotation = Annotation(
                    type="mosaic",
                    rect=(r.x(), r.y(), r.width(), r.height()),
                    scale=self.current_mosaic_scale,
                )
        elif t == "blur":
            r = QRectF(self._draw_start, pos).normalized()
            if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                self._preview_annotation = Annotation(
                    type="blur",
                    rect=(r.x(), r.y(), r.width(), r.height()),
                    radius=self.current_blur_radius,
                )
        elif t == "magnifier":
            r = QRectF(self._draw_start, pos).normalized()
            if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                self._preview_annotation = Annotation(
                    type="magnifier",
                    rect=(r.x(), r.y(), r.width(), r.height()),
                    zoom=self.current_magnifier_zoom,
                )
        elif t in ("arrow", "line"):
            self._preview_annotation = Annotation(
                type=t,
                start=(self._draw_start.x(), self._draw_start.y()),
                end=(pos.x(), pos.y()),
                color=self.current_color.name(),
                width=self.current_width,
            )
        elif t == "freehand":
            self._draw_points.append(pos)
            self._preview_annotation = Annotation(
                type="freehand",
                points=[(p.x(), p.y()) for p in self._draw_points],
                color=self.current_color.name(),
                width=self.current_width,
            )
        self.update()

    def _add_annotation(self, ann: Annotation) -> None:
        self.annotations.append(ann)
        # Select the newly added annotation (matching overlay behavior)
        self._selected_annotation_index = len(self.annotations) - 1
        self._undo_stack.append({"type": "add", "ann": ann.clone(), "index": len(self.annotations) - 1})
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
                    ann.text = text
                    ann.color = self.text_color.name()
                    ann.font_family = self.text_font_family
                    ann.font_size = self.text_font_size
                    ann.bold = self.text_bold
                    ann.italic = self.text_italic
            else:
                # Store pos as tuple for consistency with other PinWindow annotations
                self.annotations.append(Annotation(
                    type="text",
                    pos=(self._text_editor_pos.x(), self._text_editor_pos.y()),
                    text=text,
                    color=self.text_color,
                    font_family=self.text_font_family,
                    font_size=self.text_font_size,
                    bold=self.text_bold,
                    italic=self.text_italic,
                ))
                ann = self.annotations[-1]
                self._undo_stack.append({
                    "type": "add", "ann": ann, "index": len(self.annotations) - 1
                })
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
        if key == "color":
            ann.color = value if isinstance(value, str) else value.name()
        elif key == "width":
            ann.width = value
        elif key == "blur_radius" and ann.type == "blur":
            ann.blur_radius = value
            ann._cached = None
        elif key == "magnifier_zoom" and ann.type == "magnifier":
            ann.zoom = value
            ann._cached = None
        elif key == "mosaic_scale" and ann.type == "mosaic":
            ann.scale = value
            ann._cached = None
        elif key == "font_family" and ann.type == "text":
            ann.font_family = value
        elif key == "font_size" and ann.type == "text":
            ann.font_size = value
        elif key == "bold" and ann.type == "text":
            ann.bold = value
        elif key == "italic" and ann.type == "text":
            ann.italic = value
        elif key == "text_color" and ann.type == "text":
            ann.color = value if isinstance(value, str) else value.name()
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
        """Apply *xform(x, y) → (x', y')* to every annotation's coordinates."""
        for ann in self.annotations:
            t = ann.type
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                r = ann.rect
                nx, ny = xform(r.x(), r.y())
                ann.rect = QRectF(nx, ny, r.width(), r.height())
                ann._cached = None
            elif t in ("arrow", "line"):
                ann.start = QPointF(xform(ann.start.x(), ann.start.y()))
                ann.end = QPointF(xform(ann.end.x(), ann.end.y()))
            elif t == "freehand":
                ann.points = [QPointF(xform(p.x(), p.y())) for p in ann.points]
                ann._path = None
            elif t in ("text", "number_marker"):
                ann.pos = QPointF(xform(ann.pos.x(), ann.pos.y()))

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
        from ...core.i18n import _
        from ..common.toast import ToastManager
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
            t = a.type
            keep = False
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                r = a.rect
                keep = r.intersects(crop_rect)
                if keep:
                    a.rect = QRectF(r.x() - x, r.y() - y, r.width(), r.height())
                if t in ("mosaic", "blur", "magnifier"):
                    a._cached = None
            elif t in ("arrow", "line"):
                sp = a.start
                ep = a.end
                keep = crop_rect.contains(sp) or crop_rect.contains(ep)
                if keep:
                    a.start = QPointF(sp.x() - x, sp.y() - y)
                    a.end = QPointF(ep.x() - x, ep.y() - y)
            elif t == "freehand":
                pts = a.points
                keep = any(crop_rect.contains(p) for p in pts)
                if keep:
                    a.points = [QPointF(p.x() - x, p.y() - y) for p in pts]
                a._path = None
            elif t in ("text", "number_marker"):
                pos = a.pos
                keep = crop_rect.contains(pos)
                if keep:
                    a.pos = QPointF(pos.x() - x, pos.y() - y)
            if keep:
                surviving.append(a)

        self.annotations = surviving
        self._selected_annotation_index = -1

        # Exit crop mode and update
        self._exit_crop_mode()
        self._after_transform()

        from ...core.i18n import _
        from ..common.toast import ToastManager
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
