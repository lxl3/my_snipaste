from threading import Thread

from PySide6.QtCore import QObject, Signal, Qt, QPoint
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget, QFileDialog,
)
from .overlay import CaptureOverlay
from .ocr_engine import extract_text
from .utils import create_app_icon


class PinWindow(QWidget):
    def __init__(self, pixmap: QPixmap, pos):
        super().__init__()
        self.pixmap = pixmap
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        dpr = pixmap.devicePixelRatio()
        w = int(pixmap.width() / dpr)
        h = int(pixmap.height() / dpr)
        self.resize(w, h)
        self.move(pos)

        self.setMouseTracking(True)
        self._dragging = False
        self._drag_pos = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap, self.pixmap.rect())

        pen = QPen(QColor(200, 200, 200, 100), 1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.deleteLater()
        super().closeEvent(event)
        self.close()

    def closeEvent(self, event):
        self.deleteLater()
        super().closeEvent(event)


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
        self.pin_windows = []

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

        self.overlay = CaptureOverlay()
        self.overlay.pin_requested.connect(self._on_pin)
        self.overlay.copy_requested.connect(self._on_copy)
        self.overlay.save_requested.connect(self._on_save)
        self.overlay.destroyed.connect(lambda: setattr(self, 'overlay', None))
        self.overlay.show()

    def _on_pin(self, pixmap: QPixmap, pos):
        win = PinWindow(pixmap, pos)
        win.destroyed.connect(lambda: self.pin_windows.remove(win) if win in self.pin_windows else None)
        self.pin_windows.append(win)
        win.show()

    def _on_copy(self, pixmap: QPixmap):
        self.clipboard().setPixmap(pixmap)

    def _on_save(self, pixmap: QPixmap):
        file_path, _ = QFileDialog.getSaveFileName(
            None, "保存截图", "截图.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*)",
        )
        if file_path:
            pixmap.save(file_path)

    def ocr_clipboard(self):
        clipboard = self.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap is None or pixmap.isNull():
            QMessageBox.information(
                None, "OCR 剪贴板",
                "剪贴板中没有图片。\n请先复制一张图片，然后再试。"
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
