import os
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QFileDialog, QWidget, QMenuBar, QMainWindow,
)

from .overlay.widget import CaptureOverlay
from .ocr.engine import extract_text
from .core.i18n import _, load_translations
from .core.utils import create_app_icon, ScreenCaptureError
from .core.logger import setup_logger, apply_log_level
from .core.settings import AppSettings, get_settings
from .core.hotkeys import HotkeyListener
from .core.permissions import (
    check_macos_accessibility,
    check_screen_recording_permission,
    open_screen_recording_settings,
    request_screen_recording_permission,
    show_permission_guide,
    show_permission_dialog,
)
from .ui.pin_window import PinWindow
from .ui.tray import TrayManager
from .ui.settings_dialog import SettingsDialog
from .ui.countdown_overlay import CountdownOverlay

logger = setup_logger("app")


def _show_dialog(icon: QMessageBox.Icon, title: str, text: str) -> None:
    """Show an always-on-top dialog to ensure visibility."""
    _mac_activate_app()
    msg = QMessageBox()
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.exec()


def _mac_activate_app() -> None:
    """macOS: bring app to foreground (needed for tray app)."""
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
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("MySnipaste")
        self.setOrganizationName("MySnipaste")
        self.setQuitOnLastWindowClosed(False)

        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.overlay: CaptureOverlay | None = None
        self.countdown_overlay: CountdownOverlay | None = None
        self.pin_windows: list = []
        self.settings: AppSettings = get_settings()
        load_translations(self.settings.language)

        apply_log_level(self.settings.log_level)

        self.setup_focused_hotkey()

        self.hotkey_listener = HotkeyListener(self.settings.hotkey)
        self.hotkey_listener.capture_signal.connect(self.start_capture)

        have_hotkey = check_macos_accessibility()

        self.tray = TrayManager(self)
        self.tray.setup(have_hotkey)
        self.tray.settings_requested.connect(self._open_settings)

        if have_hotkey:
            self.hotkey_listener.start()
            logger.info("全局快捷键已启动")
        else:
            logger.warning("Input Monitoring 权限未授予，全局快捷键不可用")

        self.aboutToQuit.connect(self.cleanup)
        logger.info("MySnipaste 应用初始化完成")
        if sys.platform == "darwin":
            self._setup_macos_menu()

        if have_hotkey:
            QTimer.singleShot(500, self._show_startup_notification)
        else:
            QTimer.singleShot(500, self._show_permission_required_notification)

    def setup_focused_hotkey(self) -> None:
        self.f12_shortcut = QShortcut(QKeySequence("F12"), self)
        self.f12_shortcut.activated.connect(self.start_capture)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.setContext(Qt.ApplicationShortcut)
        self.settings_shortcut.activated.connect(self._open_settings)

    def _setup_macos_menu(self) -> None:
        self._menu_widget = QWidget()
        self._menu_widget.setAttribute(Qt.WA_DontShowOnScreen, True)
        self._menubar = QMenuBar(self._menu_widget)
        app_menu = self._menubar.addMenu("MySnipaste")
        pref = app_menu.addAction(_("Preferences..."))
        pref.setMenuRole(QAction.PreferencesRole)
        pref.triggered.connect(self._open_settings)
        app_menu.addSeparator()
        quit_act = app_menu.addAction(_("Quit"))
        quit_act.setMenuRole(QAction.QuitRole)
        quit_act.triggered.connect(self.quit)

    def _show_startup_notification(self) -> None:
        from .core.hotkeys import get_default_hotkey
        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        # Platform-specific settings shortcut display
        if sys.platform == 'darwin':
            settings_key = '⌘,'
        else:
            settings_key = 'Ctrl+,'

        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText(_("MySnipaste Started"))
        msg.setInformativeText(
            _("Press {hotkey} to capture\nPress {settings_key} to open Settings").format(
                hotkey=hotkey_display,
                settings_key=settings_key
            )
        )
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(3000, msg.close)
        msg.exec()
        logger.info("启动提示框已关闭")

    def _show_permission_required_notification(self) -> None:
        """Show permission dialog when Input Monitoring permission is not granted."""
        _mac_activate_app()
        show_permission_dialog()

    def start_capture(self) -> None:
        logger.info("start_capture() 被调用")
        _mac_activate_app()
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        # Play capture sound immediately (before delay)
        if self.settings.capture_sound:
            self._play_capture_sound()

        # Check capture delay setting
        delay_seconds = self.settings.capture_delay
        if delay_seconds > 0:
            logger.info(f"截图延迟 {delay_seconds} 秒，显示倒计时")
            self.countdown_overlay = CountdownOverlay(delay_seconds)
            self.countdown_overlay.countdown_finished.connect(self._do_capture)
            self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
            self.countdown_overlay.show()
            return

        self._do_capture()

    def _on_countdown_cancelled(self) -> None:
        """倒计时被用户取消"""
        logger.info("延迟截图已取消")
        if self.countdown_overlay:
            self.countdown_overlay.close()
            self.countdown_overlay.deleteLater()
            self.countdown_overlay = None

    def _do_capture(self) -> None:
        """Execute the actual screen capture."""
        # macOS: check screen recording permission
        if sys.platform == "darwin":
            perm = check_screen_recording_permission()
            logger.debug(f"权限检测结果: {perm}")
            if perm is False:
                show_permission_guide()
                open_screen_recording_settings()
                _show_dialog(
                    QMessageBox.Warning, _("Permission Required"),
                    _("Screen Recording permission is required for MySnipaste.\n\n"
                      "In System Settings:\n"
                      "  1. Click the lock to unlock\n"
                      "  2. Click + and add MySnipaste\n"
                      "  3. Check the permission\n\n"
                      "Restart the app after granting permission.")
                )
                return

        logger.info("启动截图")
        try:
            self.overlay = CaptureOverlay()
        except ScreenCaptureError as e:
            logger.error(f"截屏失败: {e}")
            show_permission_guide()
            open_screen_recording_settings()
            _show_dialog(
                QMessageBox.Critical, _("Capture Failed"),
                _("{error}\n\n"
                  "In System Settings:\n"
                  "  1. Click the lock to unlock\n"
                  "  2. Click + and add MySnipaste\n"
                  "  3. Check the permission\n\n"
                  "Restart the app after granting permission.").format(error=e)
            )
            return
        except Exception as e:
            logger.exception(f"截图异常: {e}")
            return
        self.overlay.pin_requested.connect(self._on_pin)
        self.overlay.copy_requested.connect(self._on_copy)
        self.overlay.save_requested.connect(self._on_save)
        self.overlay.destroyed.connect(lambda: setattr(self, 'overlay', None))
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()

    def _on_pin(self, pixmap: QPixmap, pos) -> None:
        win = PinWindow(pixmap, pos)
        win.destroyed.connect(lambda: self.pin_windows.remove(win) if win in self.pin_windows else None)
        self.pin_windows.append(win)
        win.show()

    def _on_copy(self, pixmap: QPixmap) -> None:
        self.clipboard().setPixmap(pixmap)

    def _on_save(self, pixmap: QPixmap) -> None:
        s = self.settings
        default_name = _("Screenshot_{time}.{fmt}").format(time=datetime.now().strftime('%Y%m%d_%H%M%S'), fmt=s.auto_save_format)
        default_dir = s.auto_save_dir or ""
        default_path = os.path.join(default_dir, default_name) if default_dir else default_name

        # 记住最后使用的目录（仅在未配置自动保存目录时）
        last_save_dir = getattr(self, '_last_save_dir', "")
        if not s.auto_save_dir and last_save_dir:
            default_path = os.path.join(last_save_dir, default_name) if last_save_dir else default_name

        # Use overlay as parent to ensure proper modal behavior
        parent = self.overlay if self.overlay else None
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            parent, _("Save Screenshot"), default_path,
            _("PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)"),
        )
        if file_path:
            pixmap.save(file_path)
            logger.info(f"截图已保存到: {file_path}")
            # 记住最后使用的目录（仅在未配置自动保存目录时）
            if not s.auto_save_dir:
                self._last_save_dir = os.path.dirname(file_path) or ""
            # Close overlay after successful save
            if self.overlay:
                logger.debug("保存完成，关闭截图界面")
                self.overlay.close()
        else:
            logger.debug("用户取消保存，保持截图界面打开")

    def ocr_clipboard(self) -> None:
        logger.info("开始 OCR 剪贴板图片")
        clipboard = self.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap is None or pixmap.isNull():
            logger.warning("剪贴板中没有图片")
            QMessageBox.information(
                None, _("OCR Clipboard"),
                _("No image in clipboard.\nPlease copy an image first.")
            )
            return

        text = extract_text(pixmap)
        if text:
            clipboard.setText(text)
            logger.info(f"OCR 识别成功，{len(text)} 个字符已复制到剪贴板")
            QMessageBox.information(
                None, _("OCR Result"),
                _("Text extracted and copied to clipboard:\n\n{text}").format(text=text[:500])
            )
        else:
            logger.warning("OCR 识别结果为空")

    def _open_settings(self) -> None:
        result = SettingsDialog.open(None)
        if result is not None:
            self.settings = result
            logger.info(f"设置已更新，准备切换快捷键: {self.settings.hotkey}")
            # Load translations for new language
            load_translations(self.settings.language)
            # Update tray to reflect new language settings
            self.tray.cleanup()
            self.tray = TrayManager(self)
            have_hotkey = check_macos_accessibility()  # Re-check permission status
            self.tray.setup(have_hotkey)
            self.tray.settings_requested.connect(self._open_settings)
            # Stop the old listener (now waits for thread to exit)
            self.hotkey_listener.stop()
            # Small delay to ensure clean transition
            QTimer.singleShot(100, self._restart_hotkey)

    def _restart_hotkey(self) -> None:
        logger.info(f"重启快捷键监听器，新快捷键: {self.settings.hotkey}")
        self.hotkey_listener = HotkeyListener(self.settings.hotkey)
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.start()
        logger.info(f"快捷键监听器已重启: {self.settings.hotkey}")

    def _play_capture_sound(self) -> None:
        """Play capture sound (platform-specific)."""
        try:
            if sys.platform == "win32":
                # Windows: Use thread to play sound without any blocking
                import threading
                import winsound

                def play_sound():
                    try:
                        sound_path = r"C:\Windows\Media\notify.wav"
                        if os.path.exists(sound_path):
                            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NOWAIT)
                        else:
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except:
                        pass

                # Play in separate thread for zero blocking
                threading.Thread(target=play_sound, daemon=True).start()

            elif sys.platform == "darwin":
                # macOS: Play system sound asynchronously (non-blocking)
                import subprocess
                subprocess.Popen(
                    ["afplay", "/System/Library/Sounds/Tink.aiff"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux/other: fallback to QApplication.beep()
                self.beep()
        except Exception as e:
            logger.warning(f"播放截图声音失败: {e}")
            try:
                self.beep()
            except:
                pass

    def cleanup(self) -> None:
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        if hasattr(self, 'countdown_overlay') and self.countdown_overlay:
            self.countdown_overlay.close()
            self.countdown_overlay = None
        if hasattr(self, 'tray'):
            self.tray.cleanup()
        if hasattr(self, '_menu_widget'):
            self._menu_widget.deleteLater()
            self._menu_widget = None
        if hasattr(self, '_menubar'):
            self._menubar = None

    def quit(self) -> None:
        logger.info("用户请求退出应用")
        self.cleanup()
        QTimer.singleShot(300, super().quit)


