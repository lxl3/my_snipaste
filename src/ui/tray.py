import platform
import subprocess

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QDialog, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout

from ..core.utils import create_app_icon
from ..core.logger import setup_logger, get_current_log_path, get_log_dir

logger = setup_logger("tray")


class TrayManager:
    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        self._menubar = None

    def setup(self, have_hotkey=True):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        from ..core.hotkeys import get_default_hotkey
        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon)
        if have_hotkey:
            self.tray_icon.setToolTip(f"MySnipaste - 按 {hotkey_display} 截屏")
        else:
            self.tray_icon.setToolTip("MySnipaste - 点击托盘图标截屏")

        ocr_action = QAction("OCR 剪贴板图片", self.app)
        ocr_action.triggered.connect(self.app.ocr_clipboard)

        log_dir_action = QAction("打开日志目录", self.app)
        log_dir_action.triggered.connect(self._open_log_dir)

        view_log_action = QAction("查看日志", self.app)
        view_log_action.triggered.connect(self._show_log_viewer)

        quit_action = QAction("退出", self.app)
        quit_action.triggered.connect(self.app.quit)

        if platform.system() == "Darwin":
            self.tray_icon.activated.connect(lambda r: self.app.start_capture())
            from PySide6.QtWidgets import QMenuBar
            self._menubar = QMenuBar()
            app_menu = self._menubar.addMenu("MySnipaste")
            app_menu.addAction(ocr_action)
            app_menu.addSeparator()
            app_menu.addAction(log_dir_action)
            app_menu.addAction(view_log_action)
            app_menu.addSeparator()
            app_menu.addAction(quit_action)
            logger.info("macOS 托盘已配置（单击触发截图 + 系统菜单栏）")
        else:
            menu = QMenu()
            capture_action = QAction(f"截屏 ({hotkey_display})", self.app)
            capture_action.triggered.connect(self.app.start_capture)
            menu.addAction(capture_action)
            menu.addAction(ocr_action)
            menu.addSeparator()
            menu.addAction(log_dir_action)
            menu.addAction(view_log_action)
            menu.addSeparator()
            menu.addAction(quit_action)

            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            logger.info("托盘菜单已配置")

        self.tray_icon.show()

    def _open_log_dir(self):
        log_dir = get_log_dir()
        try:
            subprocess.run(["open", log_dir], check=True)
            logger.info(f"已打开日志目录: {log_dir}")
        except Exception as e:
            logger.error(f"打开日志目录失败: {e}")

    def _show_log_viewer(self):
        path = get_current_log_path()
        if not path:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(None, "日志", "暂无日志文件")
            return

        dialog = QDialog(None)
        dialog.setWindowTitle("MySnipaste 日志")
        dialog.resize(700, 500)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            text_edit.setPlainText(content if content else "(空)")
        except Exception as e:
            text_edit.setPlainText(f"读取日志失败: {e}")

        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        open_btn = QPushButton("在 Finder 中打开", dialog)
        open_btn.clicked.connect(lambda: subprocess.run(["open", get_log_dir()]))
        btn_layout.addWidget(open_btn)
        close_btn = QPushButton("关闭", dialog)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.app.start_capture()

    def cleanup(self):
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
