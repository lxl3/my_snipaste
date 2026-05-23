import os
import sys
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QFileDialog,
)

from .overlay.widget import CaptureOverlay
from .ocr.engine import extract_text
from .core.utils import create_app_icon, ScreenCaptureError
from .core.logger import setup_logger
from .core.hotkeys import HotkeyListener
from .core.permissions import (
    check_macos_accessibility,
    check_screen_recording_permission,
    open_screen_recording_settings,
    request_screen_recording_permission,
    show_permission_guide,
)
from .ui.pin_window import PinWindow
from .ui.tray import TrayManager

logger = setup_logger("app")


def _dbg_app(msg: str):
    """写调试日志到 /tmp/my_snipaste_app.log"""
    import time as _t
    with open("/tmp/my_snipaste_app.log", "a") as _f:
        _f.write(f"[{_t.strftime('%H:%M:%S')}] {msg}\n")


def _show_dialog(icon, title, text):
    """显示一个必定置顶的对话框，避免被其他窗口挡住。"""
    _mac_activate_app()
    msg = QMessageBox()
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.exec()


def _mac_activate_app():
    """macOS: 强制把 app 提到前台（后台托盘 app 需要）"""
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


class SnipasteApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("MySnipaste")
        self.setOrganizationName("MySnipaste")
        self.setQuitOnLastWindowClosed(False)

        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.overlay = None
        self.pin_windows = []

        self.setup_focused_hotkey()

        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.capture_signal.connect(self.start_capture)

        check_macos_accessibility()

        self.tray = TrayManager(self)
        self.tray.setup(True)

        self.hotkey_listener.start()
        logger.info("全局快捷键已启动")

        self.aboutToQuit.connect(self.cleanup)
        logger.info("MySnipaste 应用初始化完成")
        QTimer.singleShot(500, self._show_startup_notification)

    def setup_focused_hotkey(self):
        self.f12_shortcut = QShortcut(QKeySequence("F12"), self)
        self.f12_shortcut.activated.connect(self.start_capture)

    def _show_startup_notification(self):
        from .core.hotkeys import get_default_hotkey
        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText("MySnipaste 已启动")
        msg.setInformativeText(f"按 {hotkey_display} 开始截图\n点击托盘图标也可启动")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(3000, msg.close)
        msg.exec()
        logger.info("启动提示框已关闭")

    def start_capture(self):
        _dbg_app("start_capture 被调用")
        logger.info("start_capture() 被调用")
        _mac_activate_app()
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        # macOS: 检测屏幕录制权限
        if sys.platform == "darwin":
            perm = check_screen_recording_permission()
            _dbg_app(f"权限检测结果: {perm}")
            if perm is False:
                show_permission_guide()
                open_screen_recording_settings()
                _show_dialog(
                    QMessageBox.Warning, "权限不足",
                    "MySnipaste 需要「屏幕录制」权限才能截图。\n\n"
                    "请在弹出的系统设置中：\n"
                    "  1. 点击锁图标解锁\n"
                    "  2. 点击 ＋ 添加 MySnipaste\n"
                    "  3. 勾选授权\n\n"
                    "授权后请重新打开应用。"
                )
                return

        logger.info("启动截图")
        try:
            self.overlay = CaptureOverlay()
        except ScreenCaptureError as e:
            logger.error(f"截屏失败: {e}")
            _dbg_app(f"ScreenCaptureError: {e}")
            show_permission_guide()
            open_screen_recording_settings()
            _show_dialog(
                QMessageBox.Critical, "截图失败",
                f"{e}\n\n"
                "请在系统设置中：\n"
                "  1. 点击锁图标解锁\n"
                "  2. 点击 ＋ 添加 MySnipaste\n"
                "  3. 勾选授权\n\n"
                "授权后重新打开应用。"
            )
            return
        except Exception as e:
            logger.exception(f"截图异常: {e}")
            _dbg_app(f"意外异常: {e}")
            return
        self.overlay.pin_requested.connect(self._on_pin)
        self.overlay.copy_requested.connect(self._on_copy)
        self.overlay.save_requested.connect(self._on_save)
        self.overlay.destroyed.connect(lambda: setattr(self, 'overlay', None))
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()

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
            if self.overlay:
                self.overlay.close()

    def ocr_clipboard(self):
        logger.info("开始 OCR 剪贴板图片")
        clipboard = self.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap is None or pixmap.isNull():
            logger.warning("剪贴板中没有图片")
            QMessageBox.information(
                None, "OCR 剪贴板",
                "剪贴板中没有图片。\n请先复制一张图片，然后再试。"
            )
            return

        text = extract_text(pixmap)
        if text:
            clipboard.setText(text)
            logger.info(f"OCR 识别成功，{len(text)} 个字符已复制到剪贴板")
            QMessageBox.information(
                None, "OCR 结果",
                f"文本已提取并复制到剪贴板：\n\n{text[:500]}"
            )
        else:
            logger.warning("OCR 识别结果为空")

    def cleanup(self):
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        if hasattr(self, 'tray'):
            self.tray.cleanup()

    def quit(self):
        logger.info("用户请求退出应用")
        self.cleanup()
        QTimer.singleShot(300, super().quit)


