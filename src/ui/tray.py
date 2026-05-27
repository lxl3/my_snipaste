import os
import platform
import subprocess

from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QDialog, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout

from ..core.i18n import _
from ..core.utils import create_app_icon
from ..core.logger import setup_logger, get_current_log_path, get_log_dir
from ..core.hotkeys import get_default_hotkey

logger = setup_logger("tray")


class TrayManager(QObject):
    settings_requested = Signal()
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.tray_icon: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._capture_action: QAction | None = None
        self._ocr_action: QAction | None = None
        self._settings_action: QAction | None = None
        self._check_perm_action: QAction | None = None
        self._log_dir_action: QAction | None = None
        self._view_log_action: QAction | None = None
        self._quit_action: QAction | None = None

    def setup(self, have_hotkey: bool = True) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon)
        if have_hotkey:
            self.tray_icon.setToolTip(_("MySnipaste - Press {hotkey} to capture").format(hotkey=hotkey_display))
        else:
            self.tray_icon.setToolTip(_("MySnipaste - Click tray icon to capture"))

        menu = QMenu()
        self._capture_action = QAction(_("Capture ({hotkey})").format(hotkey=hotkey_display), self.app)
        self._capture_action.triggered.connect(self.app.start_capture)
        menu.addAction(self._capture_action)
        menu.addSeparator()

        self._ocr_action = QAction(_("OCR Clipboard Image"), self.app)
        self._ocr_action.triggered.connect(self.app.ocr_clipboard)
        menu.addAction(self._ocr_action)
        menu.addSeparator()

        self._settings_action = QAction(_("Settings..."), self.app)
        self._settings_action.triggered.connect(self._open_settings)
        menu.addAction(self._settings_action)
        menu.addSeparator()

        if platform.system() == "Darwin":
            self._check_perm_action = QAction(_("Check Permissions"), self.app)
            self._check_perm_action.triggered.connect(self._check_permissions)
            menu.addAction(self._check_perm_action)
            menu.addSeparator()
        else:
            self._check_perm_action = None

        self._log_dir_action = QAction(_("Open Log Directory"), self.app)
        self._log_dir_action.triggered.connect(self._open_log_dir)
        menu.addAction(self._log_dir_action)

        self._view_log_action = QAction(_("View Log"), self.app)
        self._view_log_action.triggered.connect(self._show_log_viewer)
        menu.addAction(self._view_log_action)
        menu.addSeparator()

        self._quit_action = QAction(_("Quit"), self.app)
        self._quit_action.triggered.connect(self.app.quit)
        menu.addAction(self._quit_action)

        self.tray_icon.setContextMenu(menu)
        self._menu = menu

        if platform.system() == "Darwin":
            self.tray_icon.activated.connect(self._on_tray_mac)
        else:
            self.tray_icon.activated.connect(self._on_tray_activated)
        logger.info("Tray menu configured")

        self.tray_icon.show()

    def refresh_menu_text(self, have_hotkey: bool = True) -> None:
        hotkey_display = self.app.settings.hotkey.upper().replace('+', ' + ')
        if self._capture_action:
            self._capture_action.setText(_("Capture ({hotkey})").format(hotkey=hotkey_display))
        if self._ocr_action:
            self._ocr_action.setText(_("OCR Clipboard Image"))
        if self._settings_action:
            self._settings_action.setText(_("Settings..."))
        if self._check_perm_action:
            self._check_perm_action.setText(_("Check Permissions"))
        if self._log_dir_action:
            self._log_dir_action.setText(_("Open Log Directory"))
        if self._view_log_action:
            self._view_log_action.setText(_("View Log"))
        if self._quit_action:
            self._quit_action.setText(_("Quit"))
        if self.tray_icon:
            self.tray_icon.setToolTip(
                _("MySnipaste - Press {hotkey} to capture").format(hotkey=hotkey_display)
                if have_hotkey
                else _("MySnipaste - Click tray icon to capture")
            )

    def _open_log_dir(self) -> None:
        log_dir = get_log_dir()
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", log_dir], check=True)
            elif platform.system() == "Windows":
                os.startfile(log_dir)
            else:
                subprocess.run(["xdg-open", log_dir], check=True)
            logger.info(f"已打开日志目录: {log_dir}")
        except Exception as e:
            logger.error(f"打开日志目录失败: {e}")

    def _show_log_viewer(self) -> None:
        path = get_current_log_path()
        if not path:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(None, _("Log"), _("No log files yet"))
            return

        dialog = QDialog(None)
        dialog.setWindowTitle(_("MySnipaste Log"))
        dialog.resize(700, 500)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            text_edit.setPlainText(content if content else _("(empty)"))
        except Exception as e:
            text_edit.setPlainText(_("Failed to read log: {error}").format(error=e))

        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        open_label = _("Open in Explorer") if platform.system() == "Windows" else _("Open in Finder")
        open_btn = QPushButton(open_label, dialog)
        open_btn.clicked.connect(lambda: self._open_log_dir())
        btn_layout.addWidget(open_btn)
        close_btn = QPushButton(_("Close"), dialog)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.app.start_capture()

    def _on_tray_mac(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # macOS: show menu on any click (left, right, or double-click)
        if self._menu and reason != QSystemTrayIcon.ActivationReason.Unknown:
            self._menu.popup(QCursor.pos())

    def _open_settings(self) -> None:
        self.settings_requested.emit()

    def _check_permissions(self) -> None:
        """Show permission status dialog (macOS only)."""
        from ..core.permissions import show_permission_dialog
        show_permission_dialog()

    def cleanup(self) -> None:
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
