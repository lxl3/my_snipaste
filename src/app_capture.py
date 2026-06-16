import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMessageBox

from .core.app_helpers import mac_activate_app, show_dialog
from .core.i18n import _
from .core.logger import setup_logger
from .core.permissions import (
    check_screen_recording_permission,
    open_screen_recording_settings,
    show_permission_guide,
)
from .core.utils import ScreenCaptureError, capture_all_screens
from .overlay.widget import CaptureOverlay

logger = setup_logger("app_capture")


class SnipasteCaptureMixin:
    """Capture operations mixin for SnipasteApp.

    Subclass must provide:
    - self.overlay (CaptureOverlay | None)
    - self.countdown_overlay (CountdownOverlay | None)
    - self.settings (AppSettings)
    - self.ctx (AppContext)
    - self._on_pin(pixmap, pos)
    - self._on_copy(pixmap)
    - self._on_save(pixmap, has_annotations)
    - QApplication: beep(), clipboard()
    """

    def start_capture(self) -> None:
        logger.info("start_capture() 被调用")
        mac_activate_app()

        if self.countdown_overlay is not None:
            logger.info("倒计时进行中，忽略重复触发")
            return

        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        if self.settings.capture_sound:
            self._play_capture_sound()

        delay_seconds = self.settings.capture_delay
        if delay_seconds > 0:
            logger.info(f"截图延迟 {delay_seconds} 秒，显示倒计时")
            from .ui.common.countdown_overlay import CountdownOverlay

            self.countdown_overlay = CountdownOverlay(delay_seconds)
            self.countdown_overlay.countdown_finished.connect(self._do_capture)
            self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
            self.countdown_overlay.show()
            self.countdown_overlay.activateWindow()
            self.countdown_overlay.setFocus()
            return

        self._do_capture()

    def _on_countdown_cancelled(self) -> None:
        logger.info("延迟截图已取消")
        if self.countdown_overlay:
            self.countdown_overlay.close()
            self.countdown_overlay.deleteLater()
            self.countdown_overlay = None

    def _do_capture(self) -> None:
        if self.countdown_overlay:
            self.countdown_overlay = None

        if sys.platform == "darwin":
            perm = check_screen_recording_permission()
            logger.debug(f"权限检测结果: {perm}")
            if perm is False:
                show_permission_guide()
                open_screen_recording_settings()
                show_dialog(
                    QMessageBox.Warning, _("Permission Required"),
                    _("Screen Recording permission is required for openSnipaste.\n\n"
                      "In System Settings:\n"
                      "  1. Click the lock to unlock\n"
                      "  2. Click + and add openSnipaste\n"
                      "  3. Check the permission\n\n"
                      "Restart the app after granting permission.")
                )
                return

        logger.info("启动截图")
        try:
            self.overlay = CaptureOverlay(self.ctx)
        except ScreenCaptureError as e:
            logger.error(f"截屏失败: {e}")
            show_permission_guide()
            open_screen_recording_settings()
            show_dialog(
                QMessageBox.Critical, _("Capture Failed"),
                _("{error}\n\n"
                  "In System Settings:\n"
                  "  1. Click the lock to unlock\n"
                  "  2. Click + and add openSnipaste\n"
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
        self.overlay.destroyed.connect(self._on_overlay_destroyed)
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        QTimer.singleShot(50, lambda: self._grab_overlay_keyboard())

    def _grab_overlay_keyboard(self) -> None:
        if self.overlay:
            self.overlay.setFocus()
            self.overlay.grabKeyboard()

    def _on_overlay_destroyed(self) -> None:
        self.overlay = None

    def _start_delayed_capture(self) -> None:
        logger.info("延迟截图快捷键触发")
        mac_activate_app()

        if self.countdown_overlay is not None:
            logger.info("倒计时进行中，忽略重复触发")
            return

        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        from .ui.common.countdown_overlay import CountdownOverlay

        delay = 5
        self.countdown_overlay = CountdownOverlay(delay)
        self.countdown_overlay.countdown_finished.connect(self._do_capture)
        self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
        self.countdown_overlay.show()
        self.countdown_overlay.activateWindow()
        self.countdown_overlay.setFocus()

    def _capture_full_and_pin(self) -> None:
        logger.info("截图贴图快捷键触发")
        mac_activate_app()

        try:
            pixmap = capture_all_screens(include_cursor=self.settings.capture_cursor)
        except Exception:
            logger.exception("全屏截图失败")
            return

        cursor_pos = QCursor.pos()
        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        if screen_geo.contains(cursor_pos):
            pin_pos = cursor_pos
        else:
            pin_pos = screen_geo.center()

        self._on_pin(pixmap, pin_pos)

        try:
            from .ui.common.toast import ToastManager
            ToastManager.show(_("Screenshot pinned"), icon="📌", toast_type="info")
        except Exception:
            pass

    def _capture_full(self) -> None:
        logger.info("全屏截图快捷键触发")
        mac_activate_app()

        try:
            pixmap = capture_all_screens(include_cursor=self.settings.capture_cursor)
        except Exception:
            logger.exception("全屏截图失败")
            return

        self._on_copy(pixmap)

        try:
            from .ui.common.toast import ToastManager
            ToastManager.show(_("Full screen copied to clipboard"), icon="✓", toast_type="success")
        except Exception:
            pass

    def _play_capture_sound(self) -> None:
        try:
            if sys.platform == "win32":
                import threading
                import winsound

                def play_sound():
                    try:
                        sound_path = r"C:\Windows\Media\notify.wav"
                        if os.path.exists(sound_path):
                            flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NOWAIT
                            winsound.PlaySound(sound_path, flags)
                        else:
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass

                threading.Thread(target=play_sound, daemon=True).start()

            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(
                    ["afplay", "/System/Library/Sounds/Tink.aiff"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                self.beep()
        except Exception as e:
            logger.warning(f"播放截图声音失败: {e}")
            try:
                self.beep()
            except Exception:
                pass
