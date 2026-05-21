from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFileDialog, QApplication, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QMessageBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QFont, QClipboard
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, QTimer

from .ocr_engine import extract_text
from .editor_view import AnnotationView
from .editor_toolbar import EditorToolbar
from .logger import setup_logger

logger = setup_logger("editor")


class EditorWindow(QWidget):
    def __init__(self, pixmap, capture_pos=None):
        super().__init__()
        self.captured_pixmap = pixmap
        self.ocr_text = ""

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MySnipaste - 编辑器")

        screen = QApplication.primaryScreen().availableGeometry()
        max_w, max_h = screen.width() - 20, screen.height() - 20
        self.setMinimumSize(100, 100)

        dpr = pixmap.devicePixelRatio()
        self.resize(min(int(pixmap.width() / dpr), max_w), min(int(pixmap.height() / dpr), max_h))

        if capture_pos is not None:
            self.move(capture_pos.x(), capture_pos.y())
        else:
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.pixmap_item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.scene.addItem(self.pixmap_item)

        border = QGraphicsRectItem(self.pixmap_item.boundingRect())
        border.setPen(QPen(QColor(10, 125, 255, 80), 2))
        border.setBrush(Qt.NoBrush)
        self.scene.addItem(border)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.pixmap_item.setGraphicsEffect(shadow)

        self.view = AnnotationView(self.scene)
        self.view.source_pixmap = pixmap
        self.view.current_color = QColor(255, 50, 50)
        self.view.current_width = 3

        self.undo_stack = []
        self.redo_stack = []
        self._window_dragging = False

        self.undo_btn = None
        self.redo_btn = None

        self.toolbar = EditorToolbar(self)
        self.toolbar.setup()

        self.view.annotation_added.connect(self._on_annotation_changed)
        self._position_toolbar()
        self.fit_in_view()
        self.view.viewport().installEventFilter(self)

    def _position_toolbar(self):
        self.toolbar.toolbar.setParent(None)
        self.toolbar.toolbar.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        window_rect = self.frameGeometry()
        self.toolbar.toolbar.move(window_rect.right() - self.toolbar.toolbar.width(), window_rect.bottom() + 8)
        self.toolbar.toolbar.show()
        self.toolbar.toolbar.raise_()
        self.toolbar.toolbar.installEventFilter(self)
        for child in self.toolbar.toolbar.findChildren(QWidget):
            child.installEventFilter(self)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(2, 2)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.toolbar.toolbar.setGraphicsEffect(shadow)

    def _update_toolbar_position(self):
        if self.toolbar.toolbar.parent() is not None:
            return
        window_rect = self.frameGeometry()
        self.toolbar.toolbar.move(window_rect.right() - self.toolbar.toolbar.width(), window_rect.bottom() + 8)

    def eventFilter(self, obj, event):
        if obj is self.view.viewport():
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.close()
                return True
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._press_pos = event.globalPosition().toPoint()
                self._window_dragging = False
                return False
            if event.type() == QEvent.MouseMove and event.buttons() == Qt.LeftButton:
                if self._window_dragging:
                    delta = event.globalPosition().toPoint() - self._drag_start_global
                    self.move(self._drag_start_window + delta)
                    return True
                if self.view.current_tool == "select":
                    distance = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                    if distance > 10:
                        self._window_dragging = True
                        self._drag_start_global = self._press_pos
                        self._drag_start_window = self.pos()
                        self.toolbar.toolbar.hide()
                return False
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._window_dragging:
                    self._window_dragging = False
                    self.toolbar.toolbar.show()
                    return True
                return False
            return False
        return super().eventFilter(obj, event)

    def _on_annotation_changed(self, item):
        if item is None:
            return
        self.undo_stack.append(item)
        self.redo_stack.clear()
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(False)

    def _undo(self):
        if not self.undo_stack:
            return
        item = self.undo_stack.pop()
        item.setVisible(False)
        self.redo_stack.append(item)
        self.undo_btn.setEnabled(bool(self.undo_stack))
        self.redo_btn.setEnabled(True)
        self.scene.update()

    def _redo(self):
        if not self.redo_stack:
            return
        item = self.redo_stack.pop()
        item.setVisible(True)
        self.undo_stack.append(item)
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(bool(self.redo_stack))
        self.scene.update()

    def _get_image_with_annotations(self):
        rect = self.scene.sceneRect()
        dpr = self.captured_pixmap.devicePixelRatio()
        pixmap = QPixmap(int(rect.width() * dpr), int(rect.height() * dpr))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scene.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()), rect)
        painter.end()
        return pixmap

    def _do_ocr(self):
        from .ocr_engine import OcrWorker
        from .utils import qpixmap_to_pil

        self._ocr_progress = QMessageBox(self)
        self._ocr_progress.setWindowTitle("OCR 识别中")
        self._ocr_progress.setText("正在识别文字，请稍候...")
        self._ocr_progress.setStandardButtons(QMessageBox.Cancel)
        self._ocr_progress.setWindowModality(Qt.NonModal)
        self._ocr_progress.rejected.connect(self._cancel_ocr)
        self._ocr_progress.show()

        self._ocr_worker = OcrWorker(qpixmap_to_pil(self.captured_pixmap))
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()

    def _cancel_ocr(self):
        if hasattr(self, '_ocr_worker') and self._ocr_worker.isRunning():
            self._ocr_worker.terminate()
            self._ocr_worker.wait(1000)
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()

    def _on_ocr_finished(self, text):
        self._cleanup_ocr()
        self.ocr_text = text
        from .utils import OcrResultDialog
        OcrResultDialog(text if text else "(未检测到文字)", self).exec()

    def _on_ocr_error(self, error_msg):
        self._cleanup_ocr()
        QMessageBox.critical(self, "OCR 错误", f"文字识别失败：\n{error_msg}")

    def _cleanup_ocr(self):
        for attr in ('_ocr_progress', '_ocr_worker'):
            if hasattr(self, attr):
                obj = getattr(self)
                obj.close() if attr == '_ocr_progress' else obj.deleteLater()
                delattr(self, attr)

    def _pin(self):
        self.toolbar.toolbar.hide()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.show()

    def _copy_to_clipboard(self):
        QApplication.clipboard().setPixmap(self._get_image_with_annotations())

    def _save_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存截图", "截图.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*)",
        )
        if file_path:
            self._get_image_with_annotations().save(file_path)

    def fit_in_view(self):
        scene_rect = self.scene.sceneRect()
        view_rect = self.view.viewport().rect()
        ratio = min(view_rect.width() / scene_rect.width(), view_rect.height() / scene_rect.height())
        self.view.resetTransform()
        self.view.scale(min(ratio, 1.0), min(ratio, 1.0))
        self.view.centerOn(self.pixmap_item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_toolbar_position()
        QTimer.singleShot(50, self.fit_in_view)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._update_toolbar_position()

    def closeEvent(self, event):
        if self.toolbar.toolbar.parent() is None:
            self.toolbar.toolbar.close()
        self.deleteLater()
        super().closeEvent(event)
