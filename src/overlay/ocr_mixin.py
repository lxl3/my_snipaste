"""Shared OCR progress dialog and cleanup logic mixin."""

from collections.abc import Callable
from PySide6.QtWidgets import QMessageBox, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer
from ..core.i18n import _
from ..core.logger import setup_logger

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
        """Show non-modal OCR progress dialog with enhanced feedback."""
        # Create custom widget for better layout
        progress_widget = QWidget()
        layout = QVBoxLayout(progress_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Status label
        status_label = QLabel(_("Recognizing text, please wait..."))
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)

        # Progress bar (indeterminate)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)  # Indeterminate
        progress_bar.setFixedHeight(8)
        layout.addWidget(progress_bar)

        # Time elapsed label
        time_label = QLabel("00:00")
        time_label.setAlignment(Qt.AlignCenter)
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(time_label)

        # Create message box with custom widget
        self._ocr_progress = QMessageBox(self)
        self._ocr_progress.setWindowTitle(_("OCR in progress"))
        self._ocr_progress.setIcon(QMessageBox.NoIcon)
        self._ocr_progress.setStandardButtons(QMessageBox.Cancel)
        self._ocr_progress.layout().addWidget(progress_widget, 0, 0, 1, self._ocr_progress.layout().columnCount())
        self._ocr_progress.setWindowModality(Qt.WindowModal)
        self._ocr_progress.rejected.connect(cancel_callback)
        
        # Store references for updates
        self._ocr_status_label = status_label
        self._ocr_time_label = time_label
        self._ocr_start_time = None
        
        # Setup timer for elapsed time updates
        self._ocr_timer = QTimer(self)
        self._ocr_timer.timeout.connect(self._update_ocr_elapsed_time)
        self._ocr_timer.start(1000)  # Update every second
        
        self._ocr_progress.show()

    def _update_ocr_elapsed_time(self) -> None:
        """Update the elapsed time display."""
        if not hasattr(self, '_ocr_start_time') or self._ocr_start_time is None:
            import time
            self._ocr_start_time = time.time()
            return
            
        import time
        elapsed = int(time.time() - self._ocr_start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        if hasattr(self, '_ocr_time_label'):
            self._ocr_time_label.setText(time_str)
            
        # Update status message for longer operations
        if elapsed > 10 and elapsed % 5 == 0:  # Every 5 seconds after 10 seconds
            if hasattr(self, '_ocr_status_label'):
                self._ocr_status_label.setText(
                    _("Still recognizing text... ({elapsed}s)").format(elapsed=elapsed)
                )

    def _cancel_ocr(self) -> None:
        if hasattr(self, '_ocr_worker'):
            self._ocr_worker.cancel()
            self._ocr_worker.quit()
            self._ocr_worker.wait(3000)
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()
            self._ocr_progress = None
        # Cleanup timer
        if hasattr(self, '_ocr_timer') and self._ocr_timer:
            self._ocr_timer.stop()
            self._ocr_timer = None
        if hasattr(self, '_ocr_start_time'):
            self._ocr_start_time = None

    def _cleanup_ocr(self) -> None:
        if hasattr(self, '_ocr_progress') and self._ocr_progress:
            self._ocr_progress.close()
            self._ocr_progress = None
        # Cleanup timer
        if hasattr(self, '_ocr_timer') and self._ocr_timer:
            self._ocr_timer.stop()
            self._ocr_timer = None
        if hasattr(self, '_ocr_start_time'):
            self._ocr_start_time = None
        if hasattr(self, '_ocr_worker') and self._ocr_worker:
            if self._ocr_worker.isRunning():
                self._ocr_worker.cancel()
                self._ocr_worker.quit()
                self._ocr_worker.wait(3000)
            self._ocr_worker = None
