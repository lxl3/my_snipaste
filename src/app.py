# ruff: noqa: I001 — import order matters: qss_base after theme_pkg avoids circular import
import os
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenuBar,
    QMessageBox,
    QWidget,
)

from .app_capture import SnipasteCaptureMixin
from .core.app_helpers import mac_activate_app
from .core.context import AppContext, init_context
from .core.hotkeys import MultiHotkeyListener
from .core.i18n import _, load_translations
from .core.logger import apply_log_level, setup_logger
from .core.permissions import (
    check_macos_accessibility,
    show_permission_dialog,
)
from .core.screenshot_history import ScreenshotHistory
from .core.settings import AppSettings, get_settings
from .core.theme_pkg import theme as _t
from .core.utils import create_app_icon
from .ocr.engine import extract_text
from .overlay.widget import CaptureOverlay
from .ui.common.color_picker import ScreenColorPicker
from .ui.common.countdown_overlay import CountdownOverlay
from .ui.pin.pin_window import PinWindow
from .ui.common.startup_dialog import show_startup_notification
from .ui.settings import SettingsDialog
from .ui.tray import TrayManager

logger = setup_logger("app")


class SnipasteApp(QApplication, SnipasteCaptureMixin):
    def __init__(self, argv: list[str]) -> None:
        # macOS 默认不在菜单中显示图标，需要显式启用
        if sys.platform == "darwin":
            QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)
        super().__init__(argv)
        self.setApplicationName("MySnipaste")
        self.setOrganizationName("MySnipaste")
        self.setQuitOnLastWindowClosed(False)

        # 阶段 1: 最小化初始化 - 只设置必要的内容
        logger.info("MySnipaste 启动 - 阶段 1: 基础设置")

        self.overlay: CaptureOverlay | None = None
        self.countdown_overlay: CountdownOverlay | None = None
        self.pin_windows: list = []
        self.settings: AppSettings = get_settings()
        self.ctx: AppContext = init_context(AppContext(settings=self.settings, theme=_t))
        self.hotkey_listener: MultiHotkeyListener | None = None
        apply_log_level(self.settings.log_level)

        # 立即创建托盘图标（最快速度显示）
        self.tray = TrayManager(self)
        self.tray.setup(False)  # 先假设没有快捷键，稍后更新
        self.tray.settings_requested.connect(self._open_settings)
        logger.info("托盘图标已显示")

        # 阶段 2: 异步加载重量级组件
        QTimer.singleShot(0, self._async_init)

        self.aboutToQuit.connect(self.cleanup)

    def _async_init(self) -> None:
        """异步初始化重量级组件，避免阻塞托盘显示"""
        logger.info("MySnipaste 启动 - 阶段 2: 异步加载组件")

        # 加载翻译文件
        load_translations(self.settings.language)

        # 初始化主题（必须在任何 UI 组件创建前）
        _t.set_mode(self.settings.theme)
        # 加载自定义主题色
        if self.settings.accent_color:
            _t.set_accent_color(self.settings.accent_color)
        _t.apply_to_app(self)

        # 设置应用图标
        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        # 设置焦点快捷键（F12, Ctrl+,）
        self.setup_focused_hotkey()

        # macOS 菜单设置
        if sys.platform == "darwin":
            self._setup_macos_menu()

        # 检查权限并初始化全局快捷键
        have_hotkey = check_macos_accessibility()

        # 初始化多热键监听器（支持多个全局快捷键组合）
        self.hotkey_listener = MultiHotkeyListener()
        self.hotkey_listener.set_hotkeys({
            "capture": self.settings.hotkey,
            "ocr": self.settings.hotkey_ocr,
            "delay_capture": self.settings.hotkey_delay,
            "pin_capture": self.settings.hotkey_pin,
            "full_capture": self.settings.hotkey_full,
            "color_picker": self.settings.hotkey_color_picker,
            "settings": "ctrl+,",
        })
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.ocr_signal.connect(self.ocr_clipboard)
        self.hotkey_listener.delay_capture_signal.connect(self._start_delayed_capture)
        self.hotkey_listener.pin_capture_signal.connect(self._capture_full_and_pin)
        self.hotkey_listener.full_capture_signal.connect(self._capture_full)
        self.hotkey_listener.color_picker_signal.connect(self._open_color_picker)
        self.hotkey_listener.settings_signal.connect(self._open_settings)

        if have_hotkey:
            self.hotkey_listener.start()
            logger.info("全局快捷键已启动")
            # 更新托盘图标状态
            self.tray.setup(True)
        else:
            logger.warning("Input Monitoring 权限未授予，全局快捷键不可用")

        logger.info("MySnipaste 应用初始化完成")

        # 阶段 3: 显示启动提示框
        if have_hotkey:
            QTimer.singleShot(300, lambda: show_startup_notification(self.settings))
        else:
            QTimer.singleShot(300, self._show_permission_required_notification)

    def setup_focused_hotkey(self) -> None:
        self.f12_shortcut = QShortcut(QKeySequence("F12"), self)
        self.f12_shortcut.activated.connect(self.start_capture)

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



    def _show_permission_required_notification(self) -> None:
        """Show permission dialog when Input Monitoring permission is not granted."""
        mac_activate_app()
        show_permission_dialog()

    def _on_pin(self, pixmap: QPixmap, pos) -> None:
        win = PinWindow(pixmap, pos, self.ctx)
        win.destroyed.connect(lambda: self.pin_windows.remove(win) if win in self.pin_windows else None)

        # Connect signals from PinWindow to app handlers
        win.copy_requested.connect(self._on_copy)
        win.save_requested.connect(self._on_save)
        win.close_requested.connect(win.close)
        win.toggle_topmost_requested.connect(self._on_toggle_topmost)
        win.opacity_changed.connect(self._on_opacity_changed)

        self.pin_windows.append(win)
        win.show()

    def _on_copy(self, pixmap: QPixmap) -> None:
        self.clipboard().setPixmap(pixmap)

    def _on_save(self, pixmap: QPixmap, has_annotations: bool = False) -> None:
        s = self.settings
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = _("Screenshot_{time}.{fmt}").format(time=ts, fmt=s.auto_save_format)
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

            # Save to history after successful file save
            try:
                ScreenshotHistory().add_screenshot(pixmap, has_annotations)
            except Exception as e:
                logger.error(f"Failed to save screenshot to history: {e}")

            # 记住最后使用的目录（仅在未配置自动保存目录时）
            if not s.auto_save_dir:
                self._last_save_dir = os.path.dirname(file_path) or ""
            # Close overlay after successful save
            if self.overlay:
                logger.debug("保存完成，关闭截图界面")
                self.overlay.close()
        else:
            logger.debug("用户取消保存，保持截图界面打开")

    def _on_toggle_topmost(self, checked: bool) -> None:
        """Toggle window topmost state for all pin windows."""
        for win in self.pin_windows:
            if win.isVisible():
                flags = win.windowFlags()
                if checked:
                    win.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
                else:
                    win.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
                win.show()  # Need to show again after changing window flags

    def _on_opacity_changed(self, opacity: int) -> None:
        """Change opacity for all pin windows."""
        for win in self.pin_windows:
            if win.isVisible():
                win.setWindowOpacity(opacity / 100.0)
                # Update settings to persist the change
                s = self.ctx.settings
                s.pin_window_opacity = opacity
                s.save()

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

        text = extract_text(pixmap, self.settings.ocr_language)
        if text:
            clipboard.setText(text)
            logger.info(f"OCR 识别成功，{len(text)} 个字符已复制到剪贴板")
            QMessageBox.information(
                None, _("OCR Result"),
                _("Text extracted and copied to clipboard:\n\n{text}").format(text=text[:500])
            )
        else:
            logger.warning("OCR 识别结果为空")

    def _open_color_picker(self) -> None:
        """Open the screen color picker tool."""
        logger.info("Color picker hotkey triggered")
        mac_activate_app()
        if hasattr(self, '_color_picker') and self._color_picker:
            try:
                self._color_picker.close()
            except Exception:
                pass
        self._color_picker = ScreenColorPicker()
        self._color_picker.color_selected.connect(self._on_color_picked)
        self._color_picker.destroyed.connect(lambda: setattr(self, '_color_picker', None))
        self._color_picker.show()

    def _on_color_picked(self, hex_color: str) -> None:
        """Handle color picked from screen color picker."""
        try:
            from .ui.common.toast import ToastManager
            ToastManager.show(_("Copied: {color}").format(color=hex_color), icon="🎨", toast_type="success")
        except Exception:
            pass

    def _open_settings(self) -> None:
        try:
            # 非模态方式打开设置，不阻塞截图功能
            SettingsDialog.open_non_modal(
                parent=None,
                on_saved=self._on_settings_saved
            )
        except Exception:
            logger.exception("settings error")

    def _on_settings_saved(self, new_settings: AppSettings) -> None:
        """设置保存后的回调处理。"""
        self.settings = new_settings
        logger.info(f"设置已更新，准备切换快捷键: {self.settings.hotkey}")
        load_translations(self.settings.language)
        # 重新应用主题和自定义主题色
        _t.set_mode(self.settings.theme)
        _t.set_accent_color(self.settings.accent_color)
        _t.apply_to_app(self)
        have_hotkey = check_macos_accessibility()
        self.tray.refresh_menu_text(have_hotkey)
        if self.hotkey_listener:
            self.hotkey_listener.set_hotkeys({
                "capture": self.settings.hotkey,
                "ocr": self.settings.hotkey_ocr,
                "delay_capture": self.settings.hotkey_delay,
                "pin_capture": self.settings.hotkey_pin,
                "full_capture": self.settings.hotkey_full,
                "color_picker": self.settings.hotkey_color_picker,
            })

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


