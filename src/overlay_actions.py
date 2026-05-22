"""截图覆盖层动作/操作 Mixin（OCR、保存、撤销、擦除、文本编辑）。"""

import math

from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import QRectF, QPointF


class OverlayActionsMixin:
    """提供覆盖层上的交互动作：OCR、pin/copy/save、undo/redo、擦除、文本编辑。

    子类必须提供:
    - self.selection_rect (QRect)
    - self.full_screenshot (QPixmap)
    - self.annotations (list)
    - self._redo_stack (list)
    - self.current_tool (str)
    - self.current_color (QColor)
    - self.current_width (int)
    - self.text_font_family (str)
    - self.text_font_size (int)
    - self.text_bold (bool)
    - self.text_italic (bool)
    - self.text_color (QColor)
    - self._text_editor (QLineEdit | None)
    - self._text_editor_pos (QPointF | None)
    - self.toolbar (object) — 至少提供 update_undo_redo_state()
    - self.pin_requested (Signal)
    - self.copy_requested (Signal)
    - self.save_requested (Signal)
    - QWidget 方法: self.close(), self.update(), self.grabKeyboard(),
      self.releaseKeyboard(), self.setCursor(), self.fontMetrics()
    """

    # ─── OCR ───

    def _on_ocr(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        from .ocr_engine import OcrWorker
        from .utils import qpixmap_to_pil
        pil_image = qpixmap_to_pil(captured)
        self._ocr_worker = OcrWorker(pil_image)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()
        self._show_ocr_progress(self._cancel_ocr)

    def _on_ocr_finished(self, text):
        self._cleanup_ocr()
        if text:
            from .utils import OcrResultDialog
            OcrResultDialog(text, self).exec()
        else:
            QMessageBox.warning(self, "OCR 结果", "未识别到文字")

    def _on_ocr_error(self, error_msg):
        self._cleanup_ocr()
        QMessageBox.critical(self, "OCR 错误", f"文字识别失败：\n{error_msg}")

    # ─── Pin / Copy / Save ───

    def on_pin(self):
        if self.selection_rect.isNull():
            return
        self.pin_requested.emit(self._render_annotated_pixmap(), self._capture_pos())
        self.close()

    def on_copy(self):
        if self.selection_rect.isNull():
            return
        self.copy_requested.emit(self._render_annotated_pixmap())
        self.close()

    def on_save(self):
        if self.selection_rect.isNull():
            return
        self.save_requested.emit(self._render_annotated_pixmap())

    # ─── Undo / Redo ───

    def _undo(self):
        if self.annotations:
            self._redo_stack.append(self.annotations.pop())
            self.toolbar.update_undo_redo_state()
            self.update()

    def _redo(self):
        if self._redo_stack:
            self.annotations.append(self._redo_stack.pop())
            self.toolbar.update_undo_redo_state()
            self.update()

    # ─── Erase ───

    def _try_erase_annotation(self, pos):
        local = self._sel_to_local(QPointF(pos))
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann["type"]
            if t in ("rect", "ellipse", "mosaic"):
                if QRectF(ann["rect"]).contains(local):
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t in ("arrow", "line"):
                if self._point_to_segment_distance(local, ann["start"], ann["end"]) < 10:
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t == "freehand":
                pts = ann["points"]
                for j in range(len(pts) - 1):
                    if self._point_to_segment_distance(local, pts[j], pts[j + 1]) < 10:
                        self._redo_stack.append(self.annotations.pop(i))
                        self.toolbar.update_undo_redo_state()
                        self.update()
                        return
            elif t == "text":
                font = QFont(ann.get("font_family", "Segoe UI"), ann.get("font_size", 20))
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = self.fontMetrics()
                text_w = fm.horizontalAdvance(ann["text"]) + 8
                text_h = fm.height() + 4
                text_rect = QRectF(ann["pos"].x(), ann["pos"].y(), text_w, text_h)
                if text_rect.contains(local):
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return

    @staticmethod
    def _point_to_segment_distance(point, p1, p2):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return math.hypot(point.x() - p1.x(), point.y() - p1.y())
        t = max(0, min(1, ((point.x() - p1.x()) * dx + (point.y() - p1.y()) * dy) / length_sq))
        proj_x = p1.x() + t * dx
        proj_y = p1.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

    # ─── Text editing ───

    def _adjust_text_editor_size(self):
        if not self._text_editor:
            return
        text = self._text_editor.text()
        fm = self._text_editor.fontMetrics()
        width = fm.horizontalAdvance(text) + 14 if text else 10
        height = fm.height() + 6
        current_pos = getattr(self, '_text_editor_window_pos', self._text_editor.pos())
        self._text_editor.setFixedSize(max(width, 10), height)
        self._text_editor.move(current_pos)

    def _finish_text_input(self):
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
