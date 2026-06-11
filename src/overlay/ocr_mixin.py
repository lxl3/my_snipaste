"""Shared OCR progress dialog and cleanup logic mixin."""

from collections.abc import Callable

from ..core.logger import setup_logger
from ..ui.ocr.ocr_progress_dialog import OcrProgressDialog

logger = setup_logger("ocr_mixin")


class OcrMixin:
    """Shared OCR progress dialog, cancellation, and cleanup.

    Subclass must provide:
    - self._ocr_progress (QMessageBox | None)
    - self._ocr_worker (QThread worker with finished/error signals | None)
    - self._ocr_timer (QTimer | None) - for progress updates
    - self._ocr_start_time (float | None) - for elapsed time tracking
    """

    def _show_ocr_progress(self, cancel_callback: Callable[[], None]) -> None:
        """显示 OCR 识别进度对话框（玻璃效果设计）"""
        self._ocr_progress = OcrProgressDialog(self)
        self._ocr_progress.rejected.connect(cancel_callback)
        self._ocr_progress.show()

    def _cancel_ocr(self) -> None:
        """取消 OCR 识别"""
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            self._ocr_worker.cancel()
            self._ocr_worker.quit()
            self._ocr_worker.wait(3000)
        if hasattr(self, '_ocr_progress') and self._ocr_progress:
            self._ocr_progress.close()
            self._ocr_progress = None

    def _cleanup_ocr(self) -> None:
        """清理 OCR 资源"""
        if hasattr(self, '_ocr_progress') and self._ocr_progress:
            self._ocr_progress.close()
            self._ocr_progress = None
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            if self._ocr_worker.isRunning():
                self._ocr_worker.cancel()
                self._ocr_worker.quit()
                self._ocr_worker.wait(3000)
            self._ocr_worker = None
