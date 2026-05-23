"""Shared OCR progress dialog and cleanup logic mixin."""

from typing import Callable
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class OcrMixin:
    """Shared OCR progress dialog, cancellation, and cleanup.

    Subclass must provide:
    - self._ocr_progress (QMessageBox | None)
    - self._ocr_worker (QThread worker with finished/error signals | None)
    """

    def _show_ocr_progress(self, cancel_callback: Callable[[], None]) -> None:
        """Show non-modal OCR progress dialog."""
        self._ocr_progress = QMessageBox(self)
        self._ocr_progress.setWindowTitle("OCR in progress")
        self._ocr_progress.setText("Recognizing text, please wait...")
        self._ocr_progress.setStandardButtons(QMessageBox.Cancel)
        self._ocr_progress.setWindowModality(Qt.NonModal)
        self._ocr_progress.rejected.connect(cancel_callback)
        self._ocr_progress.show()

    def _cancel_ocr(self) -> None:
        if hasattr(self, '_ocr_worker'):
            self._ocr_worker.cancel()
            self._ocr_worker.quit()
            self._ocr_worker.wait(3000)
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()
            self._ocr_progress = None

    def _cleanup_ocr(self) -> None:
        if hasattr(self, '_ocr_progress') and self._ocr_progress:
            self._ocr_progress.close()
            self._ocr_progress = None
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            if self._ocr_worker.isRunning():
                self._ocr_worker.cancel()
                self._ocr_worker.quit()
                self._ocr_worker.wait(3000)
            self._ocr_worker = None
