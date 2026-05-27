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


class HotkeyListener(QObject):
    """全局快捷键监听器"""
    capture_signal = Signal()

    def __init__(self, hotkey: str | None = None) -> None:
        super().__init__()
        self.hotkey: str = hotkey or get_default_hotkey()
        self.running: bool = False
        self._listener: _PynputListener | None = None
        logger.info(f"快捷键设置为: {self.hotkey} (平台: {sys.platform})")

    def start(self) -> None:
        if self.running:
            return
        self._listener = _PynputListener(self.hotkey)
        self._listener.capture_signal.connect(
            lambda: self.capture_signal.emit()
        )
        self._listener.start()
        self.running = True

    def stop(self) -> None:
        self.running = False
        if self._listener:
            self._listener.stop()

    def update_hotkey(self, hotkey: str) -> None:
        """Update hotkey without restarting the pynput listener / CGEventTap."""
        self.hotkey = hotkey
        if self._listener and self.running:
            self._listener.update_hotkey(hotkey)

class _PynputListener(QObject):
    """pynput 全局快捷键监听（Windows/Linux，macOS 备用）"""
    capture_signal = Signal()

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        self.hotkey = hotkey
        self.listener = None
        self.running: bool = False
        self._current_keys: set = set()
        self._required_keys: set = set()

    def start(self) -> None:
        logger.debug("PynputListener 启动中...")
        if sys.platform == 'darwin':
            try:
                from .permissions import (
                    open_input_monitoring_settings,
                    request_input_monitoring_permission,
                )
                logger.debug("PynputListener 请求输入监控权限...")
                granted = request_input_monitoring_permission()
                if not granted:
                    logger.debug("PynputListener 权限请求被拒，打开系统设置引导")
                    open_input_monitoring_settings()
            except Exception as e:
                logger.debug(f"PynputListener 权限请求异常: {e}")
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        logger.debug("PynputListener 停止")
        self.running = False
        if self.listener is not None:
            try:
                self.listener.stop()
                logger.debug("pynput Listener.stop() 已调用")
            except Exception as e:
                logger.debug(f"停止 pynput Listener 时异常: {e}")

        # Don't join: the thread is a daemon and will exit on its own.
        # Joining blocks the Qt main thread and can cause event loop issues.

    def update_hotkey(self, hotkey: str) -> None:
        """Update target hotkey without restarting the pynput listener / CGEventTap."""
        self.hotkey = hotkey
        self._parse_hotkey()
        self._current_keys.clear()

    def _parse_hotkey(self) -> set:  # set[keyboard.Key | keyboard.KeyCode]
        from pynput import keyboard
        parts = self.hotkey.lower().split('+')
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
            elif len(part) == 1 and part.isalpha():
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                logger.warning(f"未识别的快捷键部分: {part}")
        self._required_keys = keys
        logger.debug(f"PynputListener 热键解析完成: {self.hotkey} → {len(keys)} keys")
        return keys

    def _listen(self) -> None:
        logger.debug("PynputListener 监听线程已启动")
        try:
            from pynput import keyboard
            self._parse_hotkey()
            logger.debug(f"PynputListener 目标组合键: {self._required_keys}")

            def on_press(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.add(normalized)
                    logger.debug(f"按键按下: {key} normalized={normalized}")
                    if self._required_keys and self._required_keys.issubset(self._current_keys):
                        logger.debug(f"快捷键触发: {self.hotkey}")
                        self.capture_signal.emit()
                        self._current_keys.clear()
                except Exception as e:
                    logger.debug(f"on_press 异常: {e}")
                    pass

            def on_release(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.discard(normalized)
                except Exception:
                    pass

            logger.debug("PynputListener 创建 keyboard.Listener...")
            with keyboard.Listener(on_press=on_press, on_release=on_release) as self.listener:
                logger.debug("PynputListener 加入监听循环")
                self.listener.join()
                logger.debug("PynputListener 监听循环已退出！pynput 线程静默结束了")

        except Exception as e:
            logger.error(f"pynput 监听失败: {e}")

    def _normalize(self, key) -> object:
        from pynput import keyboard
        # Normalize modifier keys
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl_l
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift_l
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            return keyboard.Key.alt_l
        elif key in (keyboard.Key.cmd, keyboard.Key.cmd_r):
            return keyboard.Key.cmd
        # Normalize letter/number keys by their character
        elif hasattr(key, 'char') and key.char:
            char = key.char
            # Convert Ctrl+letter combinations (ASCII 0x01-0x1A) back to letters
            # Ctrl+A=0x01, Ctrl+Z=0x1A, so we add ord('a')-1 to get the letter
            if len(char) == 1 and 0x01 <= ord(char) <= 0x1A:
                char = chr(ord(char) + ord('a') - 1)
                logger.debug(f"转换控制字符: {repr(key.char)} -> '{char}'")
            # Convert to lowercase for consistent comparison
            return keyboard.KeyCode.from_char(char.lower())
        return key


