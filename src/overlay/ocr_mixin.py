"""OCR 进度对话框和清理逻辑的共享 Mixin。"""

from typing import Callable
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class OcrMixin:
    """提供 OCR 进度对话框、取消、清理的共享实现。

    子类必须提供:
    - self._ocr_progress (QMessageBox)
    - self._ocr_worker (QThread worker with finished/error signals)
    """

    def _show_ocr_progress(self, cancel_callback: Callable[[], None]) -> None:
        """显示非模态的 OCR 进度对话框。"""
        self._ocr_progress = QMessageBox(self)
        self._ocr_progress.setWindowTitle("OCR 识别中")
        self._ocr_progress.setText("正在识别文字，请稍候...")
        self._ocr_progress.setStandardButtons(QMessageBox.Cancel)
        self._ocr_progress.setWindowModality(Qt.NonModal)
        self._ocr_progress.rejected.connect(cancel_callback)
        self._ocr_progress.show()

    def _cancel_ocr(self) -> None:
        if hasattr(self, '_ocr_worker') and self._ocr_worker.isRunning():
            self._ocr_worker.terminate()
            self._ocr_worker.wait(1000)
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()
            self._ocr_progress = None

    def _cleanup_ocr(self) -> None:
        if hasattr(self, '_ocr_progress') and self._ocr_progress:
            self._ocr_progress.close()
            self._ocr_progress = None
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            if self._ocr_worker.isRunning():
                self._ocr_worker.quit()
                self._ocr_worker.wait(1000)
            self._ocr_worker = None
