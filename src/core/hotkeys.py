from threading import Thread

from PySide6.QtCore import QObject, Signal

from .logger import setup_logger

logger = setup_logger("hotkeys")


class HotkeyListener(QObject):
    capture_signal = Signal()

    def __init__(self):
        super().__init__()
        self.listener = None
        self.running = False

    def start(self):
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _listen(self):
        try:
            from pynput import keyboard

            def on_press(key):
                if not self.running:
                    return False
                try:
                    if key == keyboard.Key.f12:
                        self.capture_signal.emit()
                except Exception:
                    pass

            with keyboard.Listener(on_press=on_press) as self.listener:
                self.listener.join()
        except ImportError:
            logger.warning("pynput 未安装，全局快捷键不可用")
        except OSError as e:
            logger.error(f"快捷键监听失败（权限不足）: {e}")
        except Exception as e:
            logger.error(f"快捷键监听异常: {e}")

    def __del__(self):
        self.stop()
