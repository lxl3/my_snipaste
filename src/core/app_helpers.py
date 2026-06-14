# ruff: noqa: I001 — qss_base must be after theme_pkg to avoid circular import
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from .theme_pkg import theme as _t
from . import qss_base


def mac_activate_app() -> None:
    """macOS: bring app to foreground (needed for tray app)."""
    if sys.platform != 'darwin':
        return
    try:
        import subprocess
        subprocess.run([
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of every process whose unix id is {os.getpid()} to true'
        ], capture_output=True, timeout=5)
    except Exception:
        pass


def show_dialog(icon: QMessageBox.Icon, title: str, text: str) -> None:
    """Show an always-on-top dialog to ensure visibility."""
    mac_activate_app()
    msg = QMessageBox()
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.setAttribute(Qt.WA_StyledBackground)
    msg.setStyleSheet(
        _t.qss("""
            QMessageBox {
                background: $bg_primary;
                color: $text_primary;
            }
            QMessageBox QLabel {
                color: $text_primary;
            }
        """)
        + qss_base.pushbutton_qss(selector="QMessageBox QPushButton")
    )
    msg.exec()
