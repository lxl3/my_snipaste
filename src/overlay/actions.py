"""Overlay action/operation mixin (OCR, save, undo/redo, erase, text edit)."""

import math

from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import QRectF, QPointF, QRect, QPoint
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
        ToastManager.show(_("Pinned to desktop"), "📌", "success", parent=self)
        self.close()

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

    def _undo(self) -> None:
        if self.annotations:
            self._redo_stack.append(self.annotations.pop())
            self.toolbar.update_undo_redo_state()
            self.update()
            ToastManager.show(_("Undone"), "↶", "info", parent=self)

    def _redo(self) -> None:
        if self._redo_stack:
            self.annotations.append(self._redo_stack.pop())
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
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t in ("arrow", "line"):
                d = self._point_to_segment_distance(local, ann["start"], ann["end"])
                logger.debug(f"  [{i}] type={t}, start={ann['start']}, end={ann['end']}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 annotation {i} (type={t})")
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t == "freehand":
                pts = ann["points"]
                for j in range(len(pts) - 1):
                    d = self._point_to_segment_distance(local, pts[j], pts[j + 1])
                    if d < r:
                        logger.debug(f"  → 擦除 freehand[{i}] segment {j}, dist={d:.1f}")
                        self._redo_stack.append(self.annotations.pop(i))
                        self.toolbar.update_undo_redo_state()
                        self.update()
                        return
            elif t == "text":
                d = math.hypot(local.x() - ann["pos"].x(), local.y() - ann["pos"].y())
                logger.debug(f"  [{i}] type=text, pos={ann['pos']}, dist={d:.1f}")
                if d < r:
                    logger.debug(f"  → 擦除 text annotation {i}")
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
        logger.debug("  → 未命中任何标注")

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
        for ann in self.annotations:
            t = ann["type"]
            keep = False
            if t in ("rect", "ellipse", "mosaic"):
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
                text_pos = QPointF(self.selection_rect.topLeft()) + ann["pos"]
                keep = not sel_rect.contains(text_pos)
            else:
                keep = True
            if keep:
                remaining.append(ann)
        removed = len(self.annotations) - len(remaining)
        if removed > 0:
            self._redo_stack.extend(
                a for a in self.annotations if a not in remaining
            )
            self.annotations = remaining
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
        for ann in self.annotations:
            t = ann["type"]
            keep = False
            if t in ("rect", "ellipse", "mosaic"):
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
                keep = not local_erase.contains(ann["pos"])
            else:
                keep = True
            if keep:
                remaining.append(ann)

        removed = len(self.annotations) - len(remaining)
        if removed > 0:
            self._redo_stack.extend(
                a for a in self.annotations if a not in remaining
            )
            self.annotations = remaining
            self.toolbar.update_undo_redo_state()
            self.update()

    # ─── Text editing ───

    def _adjust_text_editor_size(self) -> None:
        if not self._text_editor:
            return
        text = self._text_editor.text()
        fm = self._text_editor.fontMetrics()
        width = fm.horizontalAdvance(text) + 14 if text else 10
        height = fm.height() + 6
        current_pos = getattr(self, '_text_editor_window_pos', self._text_editor.pos())
        self._text_editor.setFixedSize(max(width, 10), height)
        self._text_editor.move(current_pos)

    def _finish_text_input(self) -> None:
        if not self._text_editor or self._text_editor_pos is None:
            return
        text = self._text_editor.text().strip()
        if text:
            self.annotations.append({
                "type": "text", "pos": self._text_editor_pos, "text": text,
                "color": QColor(self.text_color), "font_family": self.text_font_family,
                "font_size": self.text_font_size, "bold": self.text_bold,
                "italic": self.text_italic,
            })
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
        self.grabKeyboard()
