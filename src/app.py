from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QFileDialog,
)

from .overlay.widget import CaptureOverlay
from .ocr.engine import extract_text
from .core.utils import create_app_icon
from .core.logger import setup_logger
from .core.permissions import check_macos_accessibility
from .core.hotkeys import HotkeyListener
from .ui.pin_window import PinWindow
from .ui.tray import TrayManager

logger = setup_logger("app")


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

        have_hotkey = check_macos_accessibility()
        self.tray = TrayManager(self)
        self.tray.setup(have_hotkey)

        if have_hotkey:
            self.setup_hotkeys()
        else:
            logger.warning("辅助功能权限未授权，全局快捷键不可用")
        logger.info("MySnipaste 应用初始化完成")

        if have_hotkey:
            QTimer.singleShot(500, self._show_startup_notification)
        else:
            QTimer.singleShot(500, self._show_no_hotkey_notification)

    def setup_focused_hotkey(self):
        self.f12_shortcut = QShortcut(QKeySequence("F12"), self)
        self.f12_shortcut.activated.connect(self.start_capture)

    def _show_startup_notification(self):
        from .core.hotkeys import get_default_hotkey
        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText("✨ MySnipaste 已启动")
        msg.setInformativeText(f"按 {hotkey_display} 开始截图\n点击托盘图标也可启动")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(3000, msg.close)
        msg.exec()
        logger.info("启动提示框已关闭")

    def _show_no_hotkey_notification(self):
        from .core.hotkeys import get_default_hotkey
        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText("MySnipaste 已启动，但全局快捷键不可用")
        msg.setInformativeText(
            f"快捷键 {hotkey_display} 可能被系统拦截或权限不足。\n\n"
            "解决方案：\n"
            "• 点击托盘图标截图（最可靠）\n"
            "• macOS: 授予辅助功能权限\n"
            "  系统偏好设置 -> 安全性与隐私 -> 辅助功能\n"
            "• 将应用切换到前台后使用快捷键\n\n"
            "注意：macOS 的某些快捷键可能被系统占用"
        )
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(5000, msg.close)
        msg.exec()
        logger.info("无快捷键启动提示已关闭")

    def setup_hotkeys(self):
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.start()

    def start_capture(self):
        if self.overlay is not None:
            if self.overlay.isVisible():
                logger.debug("截图覆盖层已存在，跳过")
                return
            # 覆盖层已关闭但还未销毁，清理以重新创建
            self.overlay.deleteLater()
            self.overlay = None

        logger.info("启动截图")
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

    def __del__(self):
        self.cleanup()
