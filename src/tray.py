import platform

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from .utils import create_app_icon
from .logger import setup_logger

logger = setup_logger("tray")


class TrayManager:
    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        self._menubar = None

    def setup(self, have_hotkey=True):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon)
        if have_hotkey:
            self.tray_icon.setToolTip("MySnipaste - 按 F12 截屏")
        else:
            self.tray_icon.setToolTip("MySnipaste - 点击托盘图标截屏")

        ocr_action = QAction("OCR 剪贴板图片", self.app)
        ocr_action.triggered.connect(self.app.ocr_clipboard)
        quit_action = QAction("退出", self.app)
        quit_action.triggered.connect(self.app.quit)

        if platform.system() == "Darwin":
            self.tray_icon.activated.connect(lambda r: self.app.start_capture())
            from PySide6.QtWidgets import QMenuBar
            self._menubar = QMenuBar()
            app_menu = self._menubar.addMenu("MySnipaste")
            app_menu.addAction(ocr_action)
            app_menu.addSeparator()
            app_menu.addAction(quit_action)
            logger.info("macOS 托盘已配置（单击触发截图 + 系统菜单栏）")
        else:
            menu = QMenu()
            capture_action = QAction("截屏 (F12)", self.app)
            capture_action.triggered.connect(self.app.start_capture)
            menu.addAction(capture_action)
            menu.addAction(ocr_action)
            menu.addSeparator()
            menu.addAction(quit_action)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            logger.info("Windows 托盘已配置（双击触发截图）")

        self.tray_icon.show()
        logger.info("系统托盘图标已显示")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.app.start_capture()

    def cleanup(self):
        if self.tray_icon:
            self.tray_icon.setToolTip("")
            self.tray_icon.setIcon(QIcon())
            self.tray_icon.setContextMenu(None)
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            self.tray_icon = None
