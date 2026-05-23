import sys
import time
from threading import Thread

from PySide6.QtCore import QObject, Signal

from .logger import setup_logger

logger = setup_logger("hotkeys")

_DBG = "/tmp/my_snipaste_debug.log"


def _d(msg):
    with open(_DBG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


DEFAULT_HOTKEY = {
    'darwin': 'cmd+shift+x',
    'win32': 'f12',
    'linux': 'f12',
}


def get_default_hotkey():
    return DEFAULT_HOTKEY.get(sys.platform, 'f12')


class HotkeyListener(QObject):
    """全局快捷键监听器"""
    capture_signal = Signal()

    def __init__(self, hotkey=None):
        super().__init__()
        self.hotkey = hotkey or get_default_hotkey()
        self.running = False
        self._listener = None
        logger.info(f"快捷键设置为: {self.hotkey} (平台: {sys.platform})")

    def start(self):
        if self.running:
            return
        self._listener = _PynputListener(self.hotkey)
        self._listener.capture_signal.connect(
            lambda: self.capture_signal.emit()
        )
        self._listener.start()
        self.running = True

    def stop(self):
        self.running = False
        if self._listener:
            self._listener.stop()

    def __del__(self):
        self.stop()


class _PynputListener(QObject):
    """pynput 全局快捷键监听（Windows/Linux，macOS 备用）"""
    capture_signal = Signal()

    def __init__(self, hotkey):
        super().__init__()
        self.hotkey = hotkey
        self.listener = None
        self.running = False
        self._current_keys = set()

    def start(self):
        _d("PynputListener 启动中...")
        if sys.platform == 'darwin':
            try:
                from .permissions import (
                    request_input_monitoring_permission,
                    open_input_monitoring_settings,
                )
                _d("PynputListener 请求输入监控权限...")
                granted = request_input_monitoring_permission()
                if not granted:
                    _d("PynputListener 权限请求被拒，打开系统设置引导")
                    open_input_monitoring_settings()
            except Exception as e:
                _d(f"PynputListener 权限请求异常: {e}")
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        _d("PynputListener 停止")
        self.running = False

    def _parse_hotkey(self):
        from pynput import keyboard
        parts = self.hotkey.lower().split('+')
        keys = set()
        for part in parts:
            part = part.strip()
            if part in ('ctrl', 'control'):
                keys.add(keyboard.Key.ctrl_l)
            elif part in ('cmd', 'command', 'super'):
                keys.add(keyboard.Key.cmd)
            elif part in ('shift'):
                keys.add(keyboard.Key.shift_l)
            elif part in ('alt', 'option'):
                keys.add(keyboard.Key.alt_l)
            elif part.startswith('f') and part[1:].isdigit():
                keys.add(getattr(keyboard.Key, f'f{int(part[1:])}'))
            elif len(part) == 1 and part.isalpha():
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                logger.warning(f"未识别的快捷键部分: {part}")
        _d(f"PynputListener 热键解析完成: {self.hotkey} → {len(keys)} keys")
        return keys

    def _listen(self):
        _d("PynputListener 监听线程已启动")
        try:
            from pynput import keyboard
            required_keys = self._parse_hotkey()
            _d(f"PynputListener 目标组合键: {required_keys}")

            def on_press(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.add(normalized)
                    _d(f"按键按下: {key} normalized={normalized}")
                    if required_keys.issubset(self._current_keys):
                        _d(f"快捷键触发: {self.hotkey}")
                        logger.debug(f"快捷键触发: {self.hotkey}")
                        self.capture_signal.emit()
                        self._current_keys.clear()
                except Exception as e:
                    _d(f"on_press 异常: {e}")
                    pass

            def on_release(key):
                if not self.running:
                    return False
                try:
                    normalized = self._normalize(key)
                    self._current_keys.discard(normalized)
                except Exception:
                    pass

            _d("PynputListener 创建 keyboard.Listener...")
            with keyboard.Listener(on_press=on_press, on_release=on_release) as self.listener:
                _d("PynputListener 加入监听循环")
                self.listener.join()
                _d("PynputListener 监听循环已退出！pynput 线程静默结束了")

        except Exception as e:
            _d(f"pynput 监听失败: {e}")
            logger.error(f"pynput 监听失败: {e}")

    def _normalize(self, key):
        from pynput import keyboard
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


class _MacOSListener(QObject):
    """macOS 全局快捷键监听，基于 ctypes + CoreGraphics 轮询"""
    capture_signal = Signal()

    MODIFIER_CODES = {
        'cmd': (0x37, 0x36),
        'command': (0x37, 0x36),
        'shift': (0x38, 0x3C),
        'ctrl': (0x3B, 0x3E),
        'control': (0x3B, 0x3E),
        'alt': (0x3A, 0x3D),
        'option': (0x3A, 0x3D),
    }

    FUNCTION_CODES = {
        'f1': 0x7A, 'f2': 0x78, 'f3': 0x63, 'f4': 0x76,
        'f5': 0x60, 'f6': 0x61, 'f7': 0x62, 'f8': 0x64,
        'f9': 0x65, 'f10': 0x6D, 'f11': 0x67, 'f12': 0x6F,
        'f13': 0x69, 'f14': 0x6B, 'f15': 0x71, 'f16': 0x6A,
        'f17': 0x40, 'f18': 0x4F, 'f19': 0x50, 'f20': 0x5A,
    }

    def __init__(self, hotkey):
        super().__init__()
        self.hotkey = hotkey
        self.running = False
        self._cg_func = None
        self._thread = None
        self._triggered = False
        self._last_trigger = 0.0
        self._key_variants = self._parse_hotkey()
        logger.info(f"macOS 轮询快捷键: {self.hotkey}")

    def _build_char_map(self):
        try:
            from pynput._util.darwin import get_unicode_to_keycode_map
            return get_unicode_to_keycode_map()
        except Exception as e:
            logger.warning(f"构建键盘映射失败: {e}")
            return {}

    def _parse_hotkey(self):
        parts = self.hotkey.lower().split('+')
        char_map = self._build_char_map()
        variants = []
        for part in parts:
            part = part.strip()
            if part in self.MODIFIER_CODES:
                variants.append(self.MODIFIER_CODES[part])
            elif part in self.FUNCTION_CODES:
                variants.append((self.FUNCTION_CODES[part],))
            elif len(part) == 1 and part.isalpha():
                code = char_map.get(part)
                if code is None:
                    logger.warning(f"无法映射字符 '{part}'")
                    continue
                variants.append((code,))
            else:
                logger.warning(f"未识别的快捷键部分: {part}")
        return variants

    def start(self):
        if self.running:
            return
        self._cg_func = self._init_cg()
        if not self._cg_func:
            _d("CGEventSourceKeyState 初始化失败")
            return
        self.running = True
        self._thread = Thread(target=self._poll, daemon=True)
        self._thread.start()
        _d("轮询线程已启动")

    def stop(self):
        self.running = False

    def _init_cg(self):
        try:
            import ctypes
            import ctypes.util
            path = ctypes.util.find_library("CoreGraphics")
            if not path:
                path = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            cg = ctypes.cdll.LoadLibrary(path)
            func = cg.CGEventSourceKeyState
            func.restype = ctypes.c_bool
            func.argtypes = [ctypes.c_uint32, ctypes.c_uint16]
            return func
        except Exception as e:
            logger.error(f"初始化 CoreGraphics 失败: {e}")
            return None

    def _poll(self):
        cg_func = self._cg_func
        # kCGEventSourceStateHIDSystemState = 1
        # 直接读取硬件键盘状态（最可靠，不依赖进程焦点或权限）
        STATE = 1
        MIN_INTERVAL = 0.3
        count = 0

        while self.running:
            count += 1
            states = {}
            for codes in self._key_variants:
                for code in codes:
                    states[code] = cg_func(STATE, code)

            all_pressed = all(
                any(states[c] for c in codes)
                for codes in self._key_variants
            )

            if all_pressed and not self._triggered:
                now = time.time()
                if now - self._last_trigger >= MIN_INTERVAL:
                    _d(f"触发截图 {states}")
                    self._triggered = True
                    self._last_trigger = now
                    self.capture_signal.emit()
            elif not all_pressed:
                self._triggered = False

            if count % 200 == 0:
                _d(f"心跳 #{count} {states}")
            time.sleep(0.05)

    def __del__(self):
        self.stop()
