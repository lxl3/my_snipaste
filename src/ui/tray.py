import platform
import subprocess

from PySide6.QtGui import QAction, QIcon, QCursor
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QDialog, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout

from ..core.utils import create_app_icon
from ..core.logger import setup_logger, get_current_log_path, get_log_dir

logger = setup_logger("tray")


class TrayManager(QObject):
    settings_requested = Signal()
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.tray_icon: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None

    def setup(self, have_hotkey: bool = True) -> None:
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

        menu = QMenu()
        capture_action = QAction(f"Capture ({hotkey_display})", self.app)
        capture_action.triggered.connect(self.app.start_capture)
        menu.addAction(capture_action)
        menu.addSeparator()

        ocr_menu_action = QAction("OCR Clipboard Image", self.app)
        ocr_menu_action.triggered.connect(self.app.ocr_clipboard)
        menu.addAction(ocr_menu_action)
        menu.addSeparator()

        settings_action = QAction("Settings...", self.app)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()

        log_dir_action = QAction("Open Log Directory", self.app)
        log_dir_action.triggered.connect(self._open_log_dir)
        menu.addAction(log_dir_action)

        view_log_action = QAction("View Log", self.app)
        view_log_action.triggered.connect(self._show_log_viewer)
        menu.addAction(view_log_action)
        menu.addSeparator()

        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self._menu = menu

        if platform.system() == "Darwin":
            # macOS: left-click shows menu (standard tray behavior)
            self.tray_icon.activated.connect(self._on_tray_mac)
        else:
            # Other platforms: double-click captures
            self.tray_icon.activated.connect(self._on_tray_activated)
        logger.info("Tray menu configured")

        self.tray_icon.show()

    def _open_log_dir(self) -> None:
        log_dir = get_log_dir()
        try:
            subprocess.run(["open", log_dir], check=True)
            logger.info(f"已打开日志目录: {log_dir}")
        except Exception as e:
            logger.error(f"打开日志目录失败: {e}")

    def _show_log_viewer(self) -> None:
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

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.app.start_capture()

    def _on_tray_mac(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            return  # right-click: context menu handled by OS
        # left-click or double-click: show menu (Capture is the first item)
        if self._menu:
            self._menu.popup(QCursor.pos())

    def _open_settings(self) -> None:
        self.settings_requested.emit()

    def cleanup(self) -> None:
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
