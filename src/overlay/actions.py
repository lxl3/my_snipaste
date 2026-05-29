"""Overlay action/operation mixin (OCR, save, undo/redo, erase, text edit)."""

import math

from PySide6.QtWidgets import QMessageBox, QLineEdit
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF, QRect, QPoint
from ..core.i18n import _
from ..core.logger import setup_logger
from ..ui.toast import ToastManager
from ..core.screenshot_history import ScreenshotHistory

logger = setup_logger("overlay_actions")


class OverlayActionsMixin:
    """Annotation actions: OCR, pin/copy/save, undo/redo, erase, text editing.

    Subclass must provide:
    - self.selection_rect (QRectF)
    - self.annotations (list[dict])
    - self._redo_stack (list[dict])
    - self.full_screenshot (QPixmap)
    - self.current_mouse_pos (QPoint)
    - self.toolbar (object) — at minimum update_undo_redo_state()

    Mixin expects host to have:
    - QWidget: close(), update(), grabKeyboard(), releaseKeyboard()
    """

    # ─── OCR ───

    def _on_ocr(self) -> None:
        if self.selection_rect.isNull():
            return
        ToastManager.show(_("OCR recognizing..."), "🔍", "info", parent=self)
        captured = self._render_annotated_pixmap()
        from ..ocr.engine import OcrWorker
        from ..core.utils import qpixmap_to_pil
        pil_image = qpixmap_to_pil(captured)
        self._ocr_worker = OcrWorker(pil_image)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._show_ocr_progress(self._cancel_ocr)
        self._ocr_worker.start()

    def _on_ocr_finished(self, text: str) -> None:
        self._cleanup_ocr()
        if text:
            ToastManager.show(_("Recognition complete"), "✓", "success", parent=self)
            from ..ui.ocr_dialog import OcrResultDialog
            self.releaseKeyboard()
            OcrResultDialog(text, self).exec()
            self.grabKeyboard()
        else:
            QMessageBox.warning(self, _("OCR Result"), _("No text recognized"))

    def _on_ocr_error(self, error_msg: str) -> None:
        self._cleanup_ocr()
        QMessageBox.critical(self, _("OCR Error"), _("Text recognition failed:\n{error}").format(error=error_msg))

    # ─── Pin / Copy / Save ───

    def on_pin(self) -> None:
        if self.selection_rect.isNull():
            return
        pixmap = self._render_annotated_pixmap()
        has_annotations = len(self.annotations) > 0

        # Save to history
        try:
            ScreenshotHistory().add_screenshot(pixmap, has_annotations)
        except Exception as e:
            logger.error(f"Failed to save screenshot to history: {e}")

        self.pin_requested.emit(pixmap, self._capture_pos())
        # 先关闭覆盖层，再显示 Toast（parent=None 避免阻塞关闭）
        self.close()
        ToastManager.show(_("Pinned to desktop"), "📌", "success", parent=None)

    def on_copy(self) -> None:
        if self.selection_rect.isNull():
            return
        pixmap = self._render_annotated_pixmap()
        has_annotations = len(self.annotations) > 0

        # Save to history
        try:
            ScreenshotHistory().add_screenshot(pixmap, has_annotations)
        except Exception as e:
            logger.error(f"Failed to save screenshot to history: {e}")

        self.copy_requested.emit(pixmap)
        ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)
        self.close()

    def on_save(self) -> None:
        if self.selection_rect.isNull():
            return
        pixmap = self._render_annotated_pixmap()
        has_annotations = len(self.annotations) > 0
        self.save_requested.emit(pixmap, has_annotations)
        # No Toast here - save dialog is shown, overlay will close after successful save

    # ─── Undo / Redo ───
    # Action-based undo/redo: each action is a dict with
    # {"type": "add" | "remove" | "batch_remove",
    #  "ann": dict, "index": int} for singles, or
    # {"type": "batch_remove", "anns": [{"ann": dict, "index": int}, ...]}
    # for batch operations.

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        if action["type"] == "add":
            # Undo an add → remove the annotation
            ann = self.annotations.pop(action["index"])
            self._redo_stack.append({"type": "remove", "ann": ann, "index": action["index"]})
        elif action["type"] == "remove":
            # Undo a remove → re-insert the annotation
            self.annotations.insert(action["index"], action["ann"])
            self._redo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        elif action["type"] == "batch_remove":
            # Undo a batch remove → re-insert all in reverse index order
            for item in reversed(action["anns"]):
                self.annotations.insert(item["index"], item["ann"])
            self._redo_stack.append(action)  # same structure for redo
        self.toolbar.update_undo_redo_state()
        self.update()
        ToastManager.show(_("Undone"), "↶", "info", parent=self)

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        if action["type"] == "add":
            # Redo an add → re-insert the annotation
            self.annotations.insert(action["index"], action["ann"])
            self._undo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        elif action["type"] == "remove":
            # Redo a remove → remove the annotation again
            ann = self.annotations.pop(action["index"])
            self._undo_stack.append({"type": "remove", "ann": ann, "index": action["index"]})
        elif action["type"] == "batch_remove":
            # Redo a batch remove → remove all in reverse index order
            removed = []
            for item in reversed(action["anns"]):
                removed.append({"ann": self.annotations.pop(item["index"]), "index": item["index"]})
            self._undo_stack.append({"type": "batch_remove", "anns": removed})
        self.toolbar.update_undo_redo_state()
        self.update()
        ToastManager.show(_("Redone"), "↷", "info", parent=self)

    # ─── Erase ───

    def _try_erase_annotation(self, pos: QPoint) -> None:
        local = self._sel_to_local(QPointF(pos))
        r = self.eraser_size
        logger.debug(f"擦除检测: local=({local.x():.0f},{local.y():.0f}), r={r}, annotations={len(self.annotations)}")
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann["type"]
            if t in ("rect", "ellipse", "mosaic"):
                ann_rect = QRectF(ann["rect"])
                d = self._point_to_rect_distance(local, ann_rect)
                logger.debug(f"  [{i}] type={t}, rect={ann_rect}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 annotation {i} (type={t})")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t in ("arrow", "line"):
                d = self._point_to_segment_distance(local, ann["start"], ann["end"])
                logger.debug(f"  [{i}] type={t}, start={ann['start']}, end={ann['end']}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 annotation {i} (type={t})")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t == "freehand":
                pts = ann["points"]
                for j in range(len(pts) - 1):
                    d = self._point_to_segment_distance(local, pts[j], pts[j + 1])
                    if d < r:
                        logger.debug(f"  → 擦除 freehand[{i}] segment {j}, dist={d:.1f}")
                        self._on_annotation_removed(i)
                        removed = self.annotations.pop(i)
                        self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                        self._redo_stack.clear()
                        self.toolbar.update_undo_redo_state()
                        self.update()
                        return
            elif t == "text":
                font = QFont(ann["font_family"], ann["font_size"])
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = QFontMetrics(font)
                tw = fm.horizontalAdvance(ann["text"])
                th = fm.height()
                text_rect = QRectF(ann["pos"].x(), ann["pos"].y(), tw, th)
                d = self._point_to_rect_distance(local, text_rect)
                logger.debug(f"  [{i}] type=text, pos={ann['pos']}, text_rect={text_rect}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 text annotation {i}")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t == "number_marker":
                center = QPointF(ann["pos"])
                radius = ann.get("radius", 14)
                d = math.hypot(local.x() - center.x(), local.y() - center.y())
                logger.debug(f"  [{i}] type=number_marker, center={center}, dist={d:.1f}")
                if d < r + radius:
                    logger.debug(f"  → 擦除 number_marker {i}")
                    self._on_annotation_removed(i)
                    removed = self.annotations.pop(i)
                    self._undo_stack.append({"type": "remove", "ann": removed, "index": i})
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
        logger.debug("  → 未命中任何标注")

    def _on_annotation_removed(self, removed_idx: int) -> None:
        """Update selection state when an annotation is removed by index."""
        sel = getattr(self, '_selected_annotation_idx', None)
        if sel is None:
            return
        if sel == removed_idx:
            self._deselect_annotation()
        elif sel > removed_idx:
            self._selected_annotation_idx = sel - 1

    @staticmethod
    def _point_to_rect_distance(point: QPointF, rect: QRectF) -> float:
        cx = max(rect.left(), min(point.x(), rect.right()))
        cy = max(rect.top(), min(point.y(), rect.bottom()))
        return math.hypot(point.x() - cx, point.y() - cy)

    @staticmethod
    def _point_to_segment_distance(point: QPointF, p1: QPointF, p2: QPointF) -> float:
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return math.hypot(point.x() - p1.x(), point.y() - p1.y())
        t = max(0, min(1, ((point.x() - p1.x()) * dx + (point.y() - p1.y()) * dy) / length_sq))
        proj_x = p1.x() + t * dx
        proj_y = p1.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

    def _erase_all_in_selection(self) -> None:
        if self.selection_rect.isNull():
            return
        sel_rect = QRectF(self.selection_rect)
        remaining = []
        removed_items = []  # track for undo
        for idx, ann in enumerate(self.annotations):
            t = ann["type"]
            keep = False
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                ann_global = QRectF(ann["rect"]).translated(QPointF(self.selection_rect.topLeft()))
                keep = not sel_rect.intersects(ann_global.toRect())
            elif t in ("arrow", "line"):
                # keep segment if neither endpoint is inside the new selection
                start_in = sel_rect.contains(ann["start"] + QPointF(self.selection_rect.topLeft()))
                end_in = sel_rect.contains(ann["end"] + QPointF(self.selection_rect.topLeft()))
                keep = not (start_in or end_in)
            elif t == "freehand":
                pts = ann["points"]
                any_in = any(
                    sel_rect.contains(p + QPointF(self.selection_rect.topLeft()))
                    for p in pts
                )
                keep = not any_in
            elif t == "text":
                font = QFont(ann["font_family"], ann["font_size"])
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = QFontMetrics(font)
                tw = fm.horizontalAdvance(ann["text"])
                th = fm.height()
                text_global_pos = QPointF(self.selection_rect.topLeft()) + ann["pos"]
                text_global_rect = QRectF(text_global_pos.x(), text_global_pos.y(), tw, th)
                keep = not sel_rect.intersects(text_global_rect)
            elif t == "number_marker":
                r = ann.get("radius", 14)
                marker_global_pos = QPointF(self.selection_rect.topLeft()) + ann["pos"]
                marker_global_rect = QRectF(marker_global_pos.x() - r, marker_global_pos.y() - r, r * 2, r * 2)
                keep = not sel_rect.intersects(marker_global_rect)
            else:
                keep = True
            if keep:
                remaining.append(ann)
            else:
                removed_items.append({"ann": ann, "index": idx})
        if removed_items:
            self._undo_stack.append({"type": "batch_remove", "anns": removed_items})
            self._redo_stack.clear()
            self.annotations = remaining
            self._deselect_annotation()  # selection index invalidated
            self.toolbar.update_undo_redo_state()
            self.update()

    def _erase_in_rect(self, erase_rect: QRect) -> None:
        if self.selection_rect.isNull() or erase_rect.isNull():
            return

        # convert to coords relative to selection top-left
        local_erase = QRectF(
            erase_rect.x() - self.selection_rect.x(),
            erase_rect.y() - self.selection_rect.y(),
            erase_rect.width(),
            erase_rect.height()
        )

        remaining = []
        removed_items = []  # track for undo
        for idx, ann in enumerate(self.annotations):
            t = ann["type"]
            keep = False
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                keep = not local_erase.intersects(ann["rect"])
            elif t in ("arrow", "line"):
                start_in = local_erase.contains(ann["start"])
                end_in = local_erase.contains(ann["end"])
                keep = not (start_in or end_in)
            elif t == "freehand":
                pts = ann["points"]
                any_in = any(local_erase.contains(p) for p in pts)
                keep = not any_in
            elif t == "text":
                font = QFont(ann["font_family"], ann["font_size"])
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = QFontMetrics(font)
                tw = fm.horizontalAdvance(ann["text"])
                th = fm.height()
                text_rect = QRectF(ann["pos"].x(), ann["pos"].y(), tw, th)
                keep = not local_erase.intersects(text_rect)
            elif t == "number_marker":
                r = ann.get("radius", 14)
                marker_rect = QRectF(ann["pos"].x() - r, ann["pos"].y() - r, r * 2, r * 2)
                keep = not local_erase.intersects(marker_rect)
            else:
                keep = True
            if keep:
                remaining.append(ann)
            else:
                removed_items.append({"ann": ann, "index": idx})

        if removed_items:
            self._undo_stack.append({"type": "batch_remove", "anns": removed_items})
            self._redo_stack.clear()
            self.annotations = remaining
            self._deselect_annotation()  # selection index invalidated
            self.toolbar.update_undo_redo_state()
            self.update()

    # ─── Text editing ───

    def _adjust_text_editor_size(self) -> None:
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
                self.annotations.append({
                    "type": "text", "pos": self._text_editor_pos, "text": text,
                    "color": QColor(self.text_color), "font_family": self.text_font_family,
                    "font_size": self.text_font_size, "bold": self.text_bold,
                    "italic": self.text_italic,
                })
                self._undo_stack.append({"type": "add", "ann": self.annotations[-1], "index": len(self.annotations) - 1})
            self._redo_stack.clear()
            self.toolbar.update_undo_redo_state()
            self.update()

        self._text_editor.textChanged.disconnect()
        self._text_editor.returnPressed.disconnect()
        self._text_editor.editingFinished.disconnect()
        self._text_editor.hide()
        self._text_editor.deleteLater()
        self._text_editor = None
        self._text_editor_pos = None
        self._editing_annotation_idx = None
        self.grabKeyboard()

    # ─── Text re-edit ───

    def _reopen_text_editor(self, ann_idx: int) -> None:
        """Re-open the text editor to edit an existing text annotation."""
        if not (0 <= ann_idx < len(self.annotations)):
            return
        ann = self.annotations[ann_idx]
        if ann["type"] != "text":
            return

        self._editing_annotation_idx = ann_idx
        self._deselect_annotation()

        # Restore font/color to match the annotation
        self.text_font_family = ann.get("font_family", self.text_font_family)
        self.text_font_size = ann.get("font_size", self.text_font_size)
        self.text_bold = ann.get("bold", False)
        self.text_italic = ann.get("italic", False)
        self.text_color = ann.get("color", self.text_color)

        local_pos = ann["pos"]
        self._text_editor_pos = local_pos
        self._text_editor = QLineEdit(self)
        font = QFont(self.text_font_family, self.text_font_size)
        font.setBold(self.text_bold)
        font.setItalic(self.text_italic)
        self._text_editor.setFont(font)
        self._text_editor.setText(ann.get("text", ""))
        self._text_editor.selectAll()
        self._text_editor_window_pos = self.selection_rect.topLeft() + local_pos.toPoint()
        self._text_editor.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none; padding: 0px;
                color: {self.text_color.name()};
            }}
        """)
        self._text_editor.setTextMargins(0, 0, 0, 0)
        self._text_editor.move(self._text_editor_window_pos)
        self._text_editor.setMinimumWidth(10)
        self._text_editor.setAttribute(Qt.WA_DeleteOnClose)
        self._text_editor.textChanged.connect(self._adjust_text_editor_size)
        self._adjust_text_editor_size()
        self.releaseKeyboard()
        self._text_editor.show()
        self._text_editor.setFocus()
        self._text_editor.returnPressed.connect(self._finish_text_input)
        self._text_editor.editingFinished.connect(self._finish_text_input)
