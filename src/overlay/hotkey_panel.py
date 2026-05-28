"""Hotkey help panel overlay component."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

from ..core.i18n import _


class HotkeyHelpPanel(QWidget):
    """Keyboard shortcut help panel with semi-transparent background."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel(_("Hotkeys"))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #333;")
        layout.addWidget(title)

        # Shortcut list
        shortcuts = [
            (_("Copy"), "Ctrl+C"),
            (_("Save"), "Ctrl+S"),
            (_("Pin"), "Ctrl+P"),
            ("", ""),  # Separator
            (_("Undo"), "Ctrl+Z"),
            (_("Redo"), "Ctrl+Y"),
            ("", ""),  # Separator
            (_("Toggle help"), "? / F1"),
        ]

        for label, key in shortcuts:
            if not label:
                # Separator line
                sep = QLabel()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #e0e0e0;")
                layout.addWidget(sep)
            else:
                row = QWidget()
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)

                row_label = QLabel(f'<span style="color: #555;">{label}</span>'
                                  f'<span style="float: right; background: #f0f0f0; '
                                  f'padding: 2px 8px; border-radius: 3px; font-size: 11px;">{key}</span>')
                row_label.setStyleSheet("font-size: 13px;")
                row_layout.addWidget(row_label)

                layout.addWidget(row)

        # Close hint
        close_hint = QLabel(_("Press Esc to close"))
        close_hint.setStyleSheet("font-size: 12px; color: #888;")
        close_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(close_hint)

        self.setFixedWidth(350)
        self.adjustSize()

    def paintEvent(self, event):
        """Draw semi-transparent white background with rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background: semi-transparent white (rgba(255, 255, 255, 0.92))
        color = QColor(255, 255, 255, 235)
        painter.setBrush(color)
        # Border: subtle white (rgba(255, 255, 255, 0.3))
        painter.setPen(QColor(255, 255, 255, 77))
        painter.drawRoundedRect(self.rect(), 6, 6)
