import sys
from threading import Thread

from PySide6.QtCore import QObject, Signal

from .logger import setup_logger

logger = setup_logger("hotkeys")


# 默认快捷键配置（根据平台）
DEFAULT_HOTKEY = {
    'darwin': 'cmd+shift+x',    # macOS: Cmd+Shift+X（类似系统截图）
    'win32': 'f12',              # Windows: F12
    'linux': 'f12',              # Linux: F12
}


def get_default_hotkey():
    """获取当前平台的默认快捷键"""
    return DEFAULT_HOTKEY.get(sys.platform, 'f12')


class HotkeyListener(QObject):
    """全局快捷键监听器（支持自定义快捷键）"""
    capture_signal = Signal()

    def __init__(self, hotkey=None):
        """
        Args:
            hotkey: 快捷键字符串，如 'f12', 'cmd+shift+x', 'ctrl+shift+a'
                    如果为 None，使用平台默认值
        """
        super().__init__()
        self.hotkey = hotkey or get_default_hotkey()
        self.listener = None
        self.running = False
        self._current_keys = set()  # 当前按下的键

        logger.info(f"快捷键设置为: {self.hotkey} (平台: {sys.platform})")

    def start(self):
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _parse_hotkey(self):
        """解析快捷键字符串为 pynput 键集合

        Returns:
            set: 需要同时按下的键集合
        """
        from pynput import keyboard

        parts = self.hotkey.lower().split('+')
        keys = set()

        for part in parts:
            part = part.strip()
            # 修饰键
            if part in ('ctrl', 'control'):
                keys.add(keyboard.Key.ctrl_l)
            elif part in ('cmd', 'command', 'super'):
                keys.add(keyboard.Key.cmd)
            elif part in ('shift'):
                keys.add(keyboard.Key.shift_l)
            elif part in ('alt', 'option'):
                keys.add(keyboard.Key.alt_l)
            # 功能键
            elif part.startswith('f') and part[1:].isdigit():
                key_num = int(part[1:])
                keys.add(getattr(keyboard.Key, f'f{key_num}'))
            # 字母键
            elif len(part) == 1 and part.isalpha():
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                logger.warning(f"未识别的快捷键部分: {part}")

        return keys

    def _listen(self):
        try:
            from pynput import keyboard

            required_keys = self._parse_hotkey()

            def on_press(key):
                if not self.running:
                    return False

                try:
                    # 标准化键（左右修饰键统一处理）
                    normalized_key = self._normalize_key(key)
                    self._current_keys.add(normalized_key)

                    # 检查是否所有必需的键都按下了
                    if required_keys.issubset(self._current_keys):
                        logger.debug(f"快捷键触发: {self.hotkey}")
                        self.capture_signal.emit()
                        # 清空以避免重复触发
                        self._current_keys.clear()

                except Exception as e:
                    logger.debug(f"按键处理异常: {e}")

            def on_release(key):
                if not self.running:
                    return False

                try:
                    normalized_key = self._normalize_key(key)
                    self._current_keys.discard(normalized_key)
                except Exception:
                    pass

            with keyboard.Listener(on_press=on_press, on_release=on_release) as self.listener:
                self.listener.join()

        except ImportError:
            logger.warning("pynput 未安装，全局快捷键不可用")
        except OSError as e:
            logger.error(f"快捷键监听失败（权限不足）: {e}")
            if sys.platform == 'darwin':
                logger.info("macOS 提示：请在 系统偏好设置 -> 安全性与隐私 -> 辅助功能 中授权")
        except Exception as e:
            logger.error(f"快捷键监听异常: {e}")

    def _normalize_key(self, key):
        """标准化键（统一处理左右修饰键）

        Args:
            key: pynput 键对象

        Returns:
            标准化的键
        """
        from pynput import keyboard

        # 统一左右 Ctrl/Shift/Alt/Cmd
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl_l
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift_l
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            return keyboard.Key.alt_l
        elif key in (keyboard.Key.cmd, keyboard.Key.cmd_r):
            return keyboard.Key.cmd

        return key

    def __del__(self):
        self.stop()
