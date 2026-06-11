import sys
from threading import Thread

from PySide6.QtCore import QObject, Signal

from .logger import setup_logger

logger = setup_logger("hotkeys")


DEFAULT_HOTKEY = {
    'darwin': 'cmd+shift+x',
    'win32': 'f12',
    'linux': 'f12',
}


def get_default_hotkey() -> str:
    return DEFAULT_HOTKEY.get(sys.platform, 'f12')



class MultiHotkeyListener(QObject):
    """支持多个全局快捷键组合的监听器。

    使用单个 pynput listener 跟踪按键状态，同时检测多个快捷键组合。
    每个快捷键有独立的信号，避免混淆。
    """
    capture_signal = Signal()
    ocr_signal = Signal()
    delay_capture_signal = Signal()
    pin_capture_signal = Signal()
    full_capture_signal = Signal()
    color_picker_signal = Signal()
    settings_signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._hotkey_configs: dict[str, str] = {}  # name -> hotkey string
        self._required_sets: dict[str, set] = {}  # name -> set of keys
        self._signal_map: dict[str, Signal] = {}  # name -> signal
        self.running: bool = False
        self._listener: _MultiPynputListener | None = None

    def set_hotkey(self, name: str, hotkey: str) -> None:
        """Set a single hotkey by name. Call before start() or via update()."""
        self._hotkey_configs[name] = hotkey
        if self._listener and self.running:
            self._listener.update_hotkeys(self._hotkey_configs)

    def set_hotkeys(self, hotkeys: dict[str, str]) -> None:
        """Set multiple hotkeys at once: {name: hotkey_string}."""
        self._hotkey_configs.update(hotkeys)
        if self._listener and self.running:
            self._listener.update_hotkeys(self._hotkey_configs)

    def get_all_hotkeys(self) -> dict[str, str]:
        """Return all registered hotkey configs."""
        return dict(self._hotkey_configs)

    def start(self) -> None:
        if self.running:
            return
        self._listener = _MultiPynputListener(self._hotkey_configs)
        # Map each named hotkey to the corresponding signal
        self._signal_map = {
            "capture": self.capture_signal,
            "ocr": self.ocr_signal,
            "delay_capture": self.delay_capture_signal,
            "pin_capture": self.pin_capture_signal,
            "full_capture": self.full_capture_signal,
            "color_picker": self.color_picker_signal,
            "settings": self.settings_signal,
        }
        # Connect matched signals
        self._listener.hotkey_triggered.connect(self._on_hotkey_triggered)
        self._listener.start()
        self.running = True

    def stop(self) -> None:
        self.running = False
        if self._listener:
            self._listener.stop()

    def _on_hotkey_triggered(self, name: str) -> None:
        signal = self._signal_map.get(name)
        if signal:
            signal.emit()


class _MultiPynputListener(QObject):
    """Internal pynput listener that tracks multiple hotkey combinations."""
    hotkey_triggered = Signal(str)  # emits the hotkey name when triggered

    def __init__(self, hotkey_configs: dict[str, str]) -> None:
        super().__init__()
        self._hotkey_configs = dict(hotkey_configs)
        self._required_sets: dict[str, set] = {}
        self.listener = None
        self.running: bool = False
        self._current_keys: set = set()

        # Pre-parse all hotkeys
        for name, hk in self._hotkey_configs.items():
            self._required_sets[name] = self._parse_hotkey(hk)

    def update_hotkeys(self, hotkey_configs: dict[str, str]) -> None:
        """Update hotkey configs without restarting."""
        self._hotkey_configs = dict(hotkey_configs)
        self._required_sets.clear()
        for name, hk in self._hotkey_configs.items():
            self._required_sets[name] = self._parse_hotkey(hk)
        self._current_keys.clear()

    def start(self) -> None:
        logger.debug("MultiPynputListener 启动中...")
        if sys.platform == 'darwin':
            try:
                from .permissions import (
                    open_input_monitoring_settings,
                    request_input_monitoring_permission,
                )
                granted = request_input_monitoring_permission()
                if not granted:
                    open_input_monitoring_settings()
            except Exception:
                pass
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        logger.debug("MultiPynputListener 停止")
        self.running = False
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass

    def _parse_hotkey(self, hotkey: str) -> set:
        """Parse a hotkey string into a set of pynput key objects."""
        from pynput import keyboard
        parts = hotkey.lower().split('+')
        keys = set()
        for part in parts:
            part = part.strip()
            if part in ('ctrl', 'control'):
                keys.add(keyboard.Key.ctrl_l)
            elif part in ('cmd', 'command', 'super'):
                keys.add(keyboard.Key.cmd)
            elif part in ('shift',):
                keys.add(keyboard.Key.shift_l)
            elif part in ('alt', 'option'):
                keys.add(keyboard.Key.alt_l)
            elif part.startswith('f') and part[1:].isdigit():
                keys.add(getattr(keyboard.Key, f'f{int(part[1:])}'))
            elif len(part) == 1:
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                logger.warning(f"未识别的快捷键部分: {part}")
        return keys

    def _listen(self) -> None:
        logger.debug("MultiPynputListener 监听线程已启动")
        try:
            from pynput import keyboard

            def on_press(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.add(normalized)
                    # Check all registered hotkey combinations
                    for name, required in self._required_sets.items():
                        if required and required.issubset(self._current_keys):
                            logger.debug(f"多快捷键触发: {name} = {self._hotkey_configs.get(name, '?')}")
                            self.hotkey_triggered.emit(name)
                            self._current_keys.clear()
                            break  # Only trigger one hotkey per press
                except Exception as e:
                    logger.debug(f"on_press 异常: {e}")

            def on_release(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.discard(normalized)
                except Exception:
                    pass

            logger.debug("MultiPynputListener 创建 keyboard.Listener...")
            with keyboard.Listener(on_press=on_press, on_release=on_release) as self.listener:
                self.listener.join()
                logger.debug("MultiPynputListener 监听循环已退出")

        except Exception as e:
            logger.error(f"pynput 多热键监听失败: {e}")

    def _normalize(self, key) -> object:
        from pynput import keyboard
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl_l
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift_l
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            return keyboard.Key.alt_l
        elif key in (keyboard.Key.cmd, keyboard.Key.cmd_r):
            return keyboard.Key.cmd
        elif hasattr(key, 'char') and key.char:
            char = key.char
            if len(char) == 1 and 0x01 <= ord(char) <= 0x1A:
                char = chr(ord(char) + ord('a') - 1)
            return keyboard.KeyCode.from_char(char.lower())
        return key


