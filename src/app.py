import sys
from threading import Thread

from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QAction, QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
)

from .overlay import CaptureOverlay
from .editor import EditorWindow
from .ocr_engine import extract_text
from .utils import create_app_icon


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
            pass
        except Exception as e:
            print(f"Hotkey listener error: {e}")

    def __del__(self):
        self.stop()


class SnipasteApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("MySnipaste")
        self.setOrganizationName("MySnipaste")
        self.setQuitOnLastWindowClosed(False)

        self.overlay = None
        self.editor = None

        self.setup_tray()
        self.setup_hotkeys()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon)
        self.tray_icon.setToolTip("MySnipaste - 按 F12 截屏")

        menu = QMenu()

        capture_action = QAction("截屏 (F12)", self)
        capture_action.triggered.connect(self.start_capture)
        menu.addAction(capture_action)

        ocr_action = QAction("OCR 剪贴板图片", self)
        ocr_action.triggered.connect(self.ocr_clipboard)
        menu.addAction(ocr_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.start_capture()

    def setup_hotkeys(self):
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.start()

    def start_capture(self):
        if self.overlay is not None:
            return
        if self.editor is not None:
            self.editor.close()
            self.editor = None

        self.overlay = CaptureOverlay()
        self.overlay.capture_completed.connect(self._on_capture_completed)
        self.overlay.capture_cancelled.connect(self._on_capture_cancelled)
        self.overlay.show()

    def _on_capture_completed(self, pixmap: QPixmap, capture_pos):
        if self.overlay:
            self.overlay.close()
            self.overlay = None

        self.editor = EditorWindow(pixmap, capture_pos)
        self.editor.show()

    def _on_capture_cancelled(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None

    def ocr_clipboard(self):
        clipboard = self.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap is None or pixmap.isNull():
            QMessageBox.information(
                None, "OCR 剪贴板",
                "剪贴板中没有图片。\n"
                "请先复制一张图片，然后再试。"
            )
            return

        text = extract_text(pixmap)
        if text:
            clipboard.setText(text)
            QMessageBox.information(
                None, "OCR 结果",
                f"文本已提取并复制到剪贴板：\n\n{text[:500]}"
            )

    def cleanup(self):
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()

    def quit(self):
        self.cleanup()
        super().quit()

    def __del__(self):
        self.cleanup()
