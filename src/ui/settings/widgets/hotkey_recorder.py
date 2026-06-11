"""快捷键录制组件"""
import sys

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from ....core import qss_base
from ....core.i18n import _
from ....core.logger import setup_logger

logger = setup_logger("hotkey_recorder")


class HotkeyRecorderWidget(QWidget):
    """Widget for recording keyboard shortcuts."""

    hotkey_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recording = False
        self._current_keys = set()
        self._hotkey = ""

        self.setFocusPolicy(Qt.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._display = QLineEdit()
        self._display.setReadOnly(True)
        self._display.setPlaceholderText(_("Click 'Record' and press keys..."))
        layout.addWidget(self._display, 1)

        self._record_btn = QPushButton(_("Record"))
        self._record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self._record_btn)

        self._clear_btn = QPushButton(_("Clear"))
        self._clear_btn.clicked.connect(self._clear_hotkey)
        layout.addWidget(self._clear_btn)

    def set_hotkey(self, hotkey: str) -> None:
        """Set the displayed hotkey."""
        self._hotkey = hotkey
        self._display.setText(hotkey)

    def get_hotkey(self) -> str:
        """Get the current hotkey."""
        return self._hotkey

    def _toggle_recording(self) -> None:
        """Toggle recording mode."""
        self._recording = not self._recording
        if self._recording:
            self._record_btn.setText(_("Stop"))
            self._record_btn.setStyleSheet(qss_base.pushbutton_qss(
                bg="$accent",
                color="$text_accent"
            ))
            self._display.setText(_("Press keys..."))
            self._current_keys.clear()
            self.setFocus()
        else:
            self._stop_recording()

    def _stop_recording(self) -> None:
        """Stop recording and finalize the hotkey."""
        self._recording = False
        self._record_btn.setText(_("Record"))
        self._record_btn.setStyleSheet("")

        if self._current_keys:
            hotkey = self._format_hotkey(self._current_keys)
            self._hotkey = hotkey
            self._display.setText(hotkey)
            self.hotkey_changed.emit(hotkey)
            logger.debug(f"Recorded hotkey: {hotkey}")

    def _clear_hotkey(self) -> None:
        """Clear the current hotkey."""
        self._hotkey = ""
        self._display.clear()
        self._current_keys.clear()
        self.hotkey_changed.emit("")

    def focusOutEvent(self, event: QEvent) -> None:
        if self._recording:
            self._stop_recording()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Capture key press during recording."""
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()

        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        modifiers = event.modifiers()
        self._current_keys.clear()

        if sys.platform == 'darwin':
            if modifiers & Qt.ControlModifier:
                self._current_keys.add('cmd')
            if modifiers & Qt.MetaModifier:
                self._current_keys.add('ctrl')
        else:
            if modifiers & Qt.ControlModifier:
                self._current_keys.add('ctrl')
            if modifiers & Qt.MetaModifier:
                self._current_keys.add('meta')
        if modifiers & Qt.ShiftModifier:
            self._current_keys.add('shift')
        if modifiers & Qt.AltModifier:
            self._current_keys.add('alt')

        key_name = self._key_to_string(key)
        if key_name:
            self._current_keys.add(key_name)
            preview = self._format_hotkey(self._current_keys)
            self._display.setText(preview)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Finalize hotkey on key release."""
        if not self._recording:
            super().keyReleaseEvent(event)
            return

        if self._current_keys and event.key() not in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            self._stop_recording()

    def _key_to_string(self, key: int) -> str:
        """Convert Qt key code to string representation."""
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f'f{key - Qt.Key_F1 + 1}'

        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key).lower()

        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(key)

        special_keys = {
            Qt.Key_Space: 'space',
            Qt.Key_Return: 'return',
            Qt.Key_Enter: 'enter',
            Qt.Key_Tab: 'tab',
            Qt.Key_Backspace: 'backspace',
            Qt.Key_Escape: 'esc',
        }
        return special_keys.get(key, '')

    def _format_hotkey(self, keys: set) -> str:
        """Format a set of keys into hotkey string."""
        if not keys:
            return ""

        modifiers = []
        main_key = None

        for key in keys:
            if key in ('ctrl', 'shift', 'alt', 'cmd', 'meta'):
                modifiers.append(key)
            else:
                main_key = key

        modifier_order = {'ctrl': 0, 'shift': 1, 'alt': 2, 'cmd': 3, 'meta': 3}
        modifiers.sort(key=lambda x: modifier_order.get(x, 99))

        parts = modifiers
        if main_key:
            parts.append(main_key)

        return '+'.join(parts)
