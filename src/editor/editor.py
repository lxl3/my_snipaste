from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QFileDialog, QApplication, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QMessageBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRectF, QEvent, QTimer

from .view import AnnotationView
from .toolbar import EditorToolbar
from ..overlay.ocr_mixin import OcrMixin
from ..core.constants import (
    SCREEN_MARGIN, MIN_EDITOR_SIZE, BORDER_BLUE, SHADOW_BLUR, SHADOW_OFFSET,
    SHADOW_COLOR, TOOLBAR_SHADOW_BLUR, TOOLBAR_SHADOW_OFFSET, TOOLBAR_SHADOW_COLOR,
    DRAG_THRESHOLD, RESIZE_DEBOUNCE_MS, DEFAULT_ANNOTATION_COLOR, DEFAULT_LINE_WIDTH, TOOLBAR_MARGIN,
)
from ..core.logger import setup_logger

logger = setup_logger("editor")


class EditorWindow(QWidget, OcrMixin):
    def __init__(self, pixmap: QPixmap, capture_pos=None) -> None:
        super().__init__()
        self.captured_pixmap = pixmap
        self.ocr_text: str = ""

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MySnipaste - 编辑器")

        screen = QApplication.primaryScreen().availableGeometry()
        max_w, max_h = screen.width() - SCREEN_MARGIN, screen.height() - SCREEN_MARGIN
        self.setMinimumSize(*MIN_EDITOR_SIZE)

        dpr = pixmap.devicePixelRatio()
        self.resize(min(int(pixmap.width() / dpr), max_w), min(int(pixmap.height() / dpr), max_h))

        if capture_pos is not None:
            self.move(capture_pos.x(), capture_pos.y())
        else:
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.scene.addItem(self.pixmap_item)

        border = QGraphicsRectItem(self.pixmap_item.boundingRect())
        border.setPen(QPen(BORDER_BLUE, 2))
        border.setBrush(Qt.NoBrush)
        self.scene.addItem(border)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(SHADOW_BLUR)
        shadow.setColor(SHADOW_COLOR)
        shadow.setOffset(*SHADOW_OFFSET)
        self.pixmap_item.setGraphicsEffect(shadow)

        self.view = AnnotationView(self.scene)
        self.view.source_pixmap = pixmap
        self.view.current_color = QColor(DEFAULT_ANNOTATION_COLOR)
        self.view.current_width = DEFAULT_LINE_WIDTH
        self.view.annotation_added.connect(self._on_annotation_added)

        self.undo_stack: list = []
        self.redo_stack: list = []
        self._window_dragging: bool = False
        self._press_pos = None
        self._drag_start_global = None
        self._drag_start_window = None

        self.undo_btn = None
        self.redo_btn = None

        self.toolbar = EditorToolbar(self)
        self.toolbar.setup()

    def _on_annotation_added(self, item) -> None:
        self.undo_stack.append(item)
        self.redo_stack.clear()
        self.toolbar.update_undo_redo_state()

    def _undo(self) -> None:
        if self.undo_stack:
            item = self.undo_stack.pop()
            self.view._items.pop()
            self.scene.removeItem(item)
            self.redo_stack.append(item)
            self.toolbar.update_undo_redo_state()

    def _redo(self) -> None:
        if self.redo_stack:
            item = self.redo_stack.pop()
            self.scene.addItem(item)
            self.view._items.append(item)
            self.undo_stack.append(item)
            self.toolbar.update_undo_redo_state()

    def _render_pixmap(self) -> QPixmap:
        dpr = self.captured_pixmap.devicePixelRatio()
        w = int(self.captured_pixmap.width() / dpr)
        h = int(self.captured_pixmap.height() / dpr)

        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.scene.render(painter, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
        painter.end()
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def _do_ocr(self) -> None:
        from ..ocr.engine import OcrWorker
        from ..core.utils import qpixmap_to_pil
        self._show_ocr_progress(self._cancel_ocr)
        self._ocr_worker = OcrWorker(qpixmap_to_pil(self.captured_pixmap))
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()

    def _on_ocr_finished(self, text: str) -> None:
        self._cleanup_ocr()
        self.ocr_text = text
        from ..ui.ocr_dialog import OcrResultDialog
        OcrResultDialog(text if text else "(未检测到文字)", self).exec()

    def _on_ocr_error(self, error_msg: str) -> None:
        self._cleanup_ocr()
        QMessageBox.critical(self, "OCR 错误", f"文字识别失败：\n{error_msg}")

    def pin(self) -> None:
        self.toolbar.toolbar.hide()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.show()
        pixmap = self._render_pixmap()
        logger.info("Editor pinned")

    def closeEvent(self, event) -> None:
        self._cleanup_ocr()
        super().closeEvent(event)
