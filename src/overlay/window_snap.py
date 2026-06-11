"""Window/element detection and single-click snap for CaptureOverlay."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.window_detector import detect_window_under_cursor


class WindowSnapDetector:
    """Auto-detect windows under cursor and snap selection on single click.

    Composed into CaptureOverlay. Expects ``overlay`` to provide:
    - rect(), setCursor(), update() — QWidget
    - selection_rect (QRect, read externally)
    """

    def __init__(self, overlay: QWidget) -> None:
        self.overlay = overlay
        self.detected_rect: QRect | None = None
        self.snap_rect: QRect | None = None

    def update_detection(self, mouse_pos) -> None:
        """Call from mouseMoveEvent when no selection or annotation is active."""
        win_rect = detect_window_under_cursor(mouse_pos)
        if win_rect is not None and win_rect.isValid():
            win_rect = win_rect.intersected(self.overlay.rect())
            if win_rect != self.detected_rect:
                self.detected_rect = win_rect
                self.overlay.setCursor(Qt.CrossCursor)
                self.overlay.update()
        else:
            if self.detected_rect is not None:
                self.detected_rect = None
                self.overlay.update()

    def save_for_snap(self) -> None:
        """Save detected rect for single-click snap (left press without drag)."""
        self.snap_rect = self.detected_rect
        self.detected_rect = None

    def apply_snap(self) -> QRect | None:
        """Return snap rect and clear it, or None if no snap pending."""
        if self.snap_rect is not None:
            r = self.snap_rect
            self.snap_rect = None
            return r
        return None

    def reset(self) -> None:
        """Clear all state (right-click cancel)."""
        self.detected_rect = None
        self.snap_rect = None

    def paint_highlight(self, painter: QPainter, sel_color: QColor) -> None:
        """Draw detected window highlight outline and fill.

        Call *before* drawing the selection (only when selection is null).
        """
        wr = self.detected_rect
        if wr is None:
            return
        painter.fillRect(wr, QColor(sel_color.red(), sel_color.green(), sel_color.blue(), 30))
        painter.setPen(QPen(QColor(sel_color), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(wr)
