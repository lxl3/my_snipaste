import os
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QAction, QCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFileDialog, QWidget, QMenuBar, QMainWindow,
)

from .overlay.widget import CaptureOverlay
from .ocr.engine import extract_text
from .core.i18n import _, load_translations
from .core.utils import create_app_icon, ScreenCaptureError, capture_all_screens
from .core.logger import setup_logger, apply_log_level
from .core.settings import AppSettings, get_settings
from .core.theme import theme as theme_manager
from .core import qss_base
from .core.hotkeys import MultiHotkeyListener
from .core.permissions import (
    check_macos_accessibility,
    check_screen_recording_permission,
    open_screen_recording_settings,
    request_screen_recording_permission,
    show_permission_guide,
    show_permission_dialog,
)
from .ui.pin_window import PinWindow
from .ui.color_picker import ScreenColorPicker
from .ui.tray import TrayManager
from .ui.settings_dialog import SettingsDialog
from .ui.countdown_overlay import CountdownOverlay
from .core.screenshot_history import ScreenshotHistory

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
    msg.setAttribute(Qt.WA_StyledBackground)
    msg.setStyleSheet(
        theme_manager.qss("""
            QMessageBox {
                background: $bg_primary;
                color: $text_primary;
            }
            QMessageBox QLabel {
                color: $text_primary;
            }
        """)
        + qss_base.pushbutton_qss(selector="QMessageBox QPushButton")
    )
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
        self.hotkey_listener: MultiHotkeyListener | None = None
        self.startup_message: QMessageBox | None = None  # 保存启动提示框引用以支持主题切换

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
        theme_manager.set_mode(self.settings.theme)
        # 加载自定义主题色
        if self.settings.accent_color:
            theme_manager.set_accent_color(self.settings.accent_color)
        theme_manager.apply_to_app(self)

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
        })
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.ocr_signal.connect(self.ocr_clipboard)
        self.hotkey_listener.delay_capture_signal.connect(self._start_delayed_capture)
        self.hotkey_listener.pin_capture_signal.connect(self._capture_full_and_pin)
        self.hotkey_listener.full_capture_signal.connect(self._capture_full)
        self.hotkey_listener.color_picker_signal.connect(self._open_color_picker)

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
            QTimer.singleShot(300, self._show_startup_notification)
        else:
            QTimer.singleShot(300, self._show_permission_required_notification)

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
        from .core.theme import theme as _t
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve

        hotkey_display = get_default_hotkey().upper().replace('+', ' + ')

        if sys.platform == 'darwin':
            settings_key = '⌘,'
        else:
            settings_key = 'Ctrl+,'

        dialog = QDialog()
        dialog.setWindowTitle("MySnipaste")
        dialog.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        dialog.setFixedSize(360, 260)
        dialog.setAttribute(Qt.WA_TranslucentBackground)

        # Main container for rounded corners
        main_container = QWidget(dialog)
        main_container.setObjectName("main_container")

        container_layout = QVBoxLayout(dialog)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(main_container)

        layout = QVBoxLayout(main_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(dialog.accept)
        close_btn.setCursor(Qt.PointingHandCursor)

        # Header
        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        # Content
        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 0, 24, 24)
        content_layout.setSpacing(18)

        # Title
        title = QLabel("MySnipaste")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)

        # Cards
        cards_layout = QVBoxLayout()
        cards_layout.setSpacing(10)

        # Screenshot card
        capture_card = QWidget()
        capture_card.setObjectName("card")
        capture_layout = QVBoxLayout(capture_card)
        capture_layout.setContentsMargins(16, 14, 16, 14)
        capture_layout.setSpacing(6)

        capture_title = QLabel("📸  " + _("Screenshot"))
        capture_title.setObjectName("card_title")
        capture_layout.addWidget(capture_title)

        capture_key = QLabel(hotkey_display)
        capture_key.setObjectName("card_key")
        capture_layout.addWidget(capture_key)

        cards_layout.addWidget(capture_card)

        # Settings card
        settings_card = QWidget()
        settings_card.setObjectName("card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        settings_layout.setSpacing(6)

        settings_title = QLabel("⚙️  " + _("Settings"))
        settings_title.setObjectName("card_title")
        settings_layout.addWidget(settings_title)

        settings_key_label = QLabel(settings_key)
        settings_key_label.setObjectName("card_key")
        settings_layout.addWidget(settings_key_label)

        cards_layout.addWidget(settings_card)

        content_layout.addLayout(cards_layout)
        layout.addWidget(content, 1)

        # Crisp, high-contrast theme
        qss_tpl = """
            QDialog {
                background: transparent;
            }

            #main_container {
                background: $bg;
                border: 1px solid $border;
                border-radius: 16px;
            }

            #header {
                background: transparent;
                padding: 8px 8px 0 0;
            }

            #close_btn {
                background: transparent;
                border: none;
                color: $text_secondary;
                font-size: 22px;
                font-weight: 300;
                border-radius: 14px;
            }

            #close_btn:hover {
                background: $hover;
                color: $text_primary;
            }

            #content {
                background: transparent;
            }

            #title {
                font-size: 26px;
                font-weight: 900;
                color: $accent;
                letter-spacing: -0.8px;
            }

            #card {
                background: $card_bg;
                border: 2px solid $card_border;
                border-radius: 10px;
            }

            #card:hover {
                background: $card_hover;
                border-color: $accent;
            }

            #card_title {
                font-size: 15px;
                font-weight: 700;
                color: $text_primary;
            }

            #card_key {
                font-size: 18px;
                font-weight: 800;
                color: $accent;
                font-family: 'Consolas', 'SF Mono', 'Monaco', monospace;
                letter-spacing: 1.5px;
            }
        """

        # High contrast colors (使用主题系统的 accent 颜色)
        if _t.is_dark():
            theme_vars = {
                'bg': '#1A1A1A',
                'border': '#333333',
                'text_primary': '#FFFFFF',
                'text_secondary': '#999999',
                'accent': _t.accent_color,
                'hover': 'rgba(255, 255, 255, 0.08)',
                'card_bg': '#242424',
                'card_border': '#333333',
                'card_hover': '#2A2A2A',
            }
        else:
            theme_vars = {
                'bg': '#FFFFFF',
                'border': '#E5E5E5',
                'text_primary': '#000000',
                'text_secondary': '#666666',
                'accent': _t.accent_color,
                'hover': 'rgba(0, 0, 0, 0.05)',
                'card_bg': '#F8F8F8',
                'card_border': '#E5E5E5',
                'card_hover': '#F0F0F0',
            }

        styled_qss = qss_tpl
        for key, value in theme_vars.items():
            styled_qss = styled_qss.replace(f'${key}', value)

        dialog.setStyleSheet(styled_qss)

        # Entrance animation
        dialog.setWindowOpacity(0)
        fade_in = QPropertyAnimation(dialog, b"windowOpacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()

        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        dialog.move(
            screen.center().x() - dialog.width() // 2,
            screen.center().y() - dialog.height() // 2
        )

        self.startup_message = dialog

        def update_startup_style():
            if self.startup_message:
                if _t.is_dark():
                    theme_vars_updated = {
                        'bg': '#1A1A1A',
                        'border': '#333333',
                        'text_primary': '#FFFFFF',
                        'text_secondary': '#999999',
                        'accent': _t.accent_color,
                        'hover': 'rgba(255, 255, 255, 0.08)',
                        'card_bg': '#242424',
                        'card_border': '#333333',
                        'card_hover': '#2A2A2A',
                    }
                else:
                    theme_vars_updated = {
                        'bg': '#FFFFFF',
                        'border': '#E5E5E5',
                        'text_primary': '#000000',
                        'text_secondary': '#666666',
                        'accent': _t.accent_color,
                        'hover': 'rgba(0, 0, 0, 0.05)',
                        'card_bg': '#F8F8F8',
                        'card_border': '#E5E5E5',
                        'card_hover': '#F0F0F0',
                    }

                updated_qss = qss_tpl
                for key, value in theme_vars_updated.items():
                    updated_qss = updated_qss.replace(f'${key}', value)
                self.startup_message.setStyleSheet(updated_qss)

        _t.theme_changed.connect(update_startup_style)

        def cleanup():
            if self.startup_message:
                try:
                    _t.theme_changed.disconnect(update_startup_style)
                except (TypeError, RuntimeError):
                    pass
                self.startup_message = None
            logger.info("启动提示框已关闭")

        dialog.finished.connect(cleanup)

        QTimer.singleShot(3000, dialog.close)
        dialog.exec()

    def _show_permission_required_notification(self) -> None:
        """Show permission dialog when Input Monitoring permission is not granted."""
        _mac_activate_app()
        show_permission_dialog()

    def start_capture(self) -> None:
        logger.info("start_capture() 被调用")
        _mac_activate_app()

        # 防止倒计时进行中重复触发截图
        if self.countdown_overlay is not None:
            logger.info("倒计时进行中，忽略重复触发")
            return

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
            self.countdown_overlay.activateWindow()  # 激活窗口
            self.countdown_overlay.setFocus()  # 设置焦点以接收键盘输入
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
        # 清理倒计时覆盖层引用（倒计时已结束）
        if self.countdown_overlay:
            self.countdown_overlay = None

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
        self.overlay.destroyed.connect(self._on_overlay_destroyed)
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        # 延迟抓取键盘，确保窗口完全显示后再执行
        QTimer.singleShot(50, lambda: self._grab_overlay_keyboard())

    def _grab_overlay_keyboard(self) -> None:
        """抓取 overlay 键盘焦点，确保键盘事件被正确接收。"""
        if self.overlay:
            self.overlay.setFocus()
            self.overlay.grabKeyboard()

    def _on_overlay_destroyed(self) -> None:
        """截图覆盖层关闭后的清理工作。"""
        self.overlay = None

    def _on_pin(self, pixmap: QPixmap, pos) -> None:
        win = PinWindow(pixmap, pos)
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
                settings = get_settings()
                settings.pin_window_opacity = opacity
                settings.save()

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

    def _start_delayed_capture(self) -> None:
        """Trigger a delayed screenshot (always shows countdown)."""
        logger.info("延迟截图快捷键触发")
        _mac_activate_app()

        if self.countdown_overlay is not None:
            logger.info("倒计时进行中，忽略重复触发")
            return

        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        # Use a default 5-second delay for this hotkey
        delay = 5
        self.countdown_overlay = CountdownOverlay(delay)
        self.countdown_overlay.countdown_finished.connect(self._do_capture)
        self.countdown_overlay.countdown_cancelled.connect(self._on_countdown_cancelled)
        self.countdown_overlay.show()
        self.countdown_overlay.activateWindow()
        self.countdown_overlay.setFocus()

    def _capture_full_and_pin(self) -> None:
        """Capture full screen and pin directly without selection UI."""
        logger.info("截图贴图快捷键触发")
        _mac_activate_app()

        try:
            pixmap = capture_all_screens(include_cursor=self.settings.capture_cursor)
        except Exception:
            logger.exception("全屏截图失败")
            return

        # Pin at cursor position or screen center
        cursor_pos = QCursor.pos()
        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry()
        if screen_geo.contains(cursor_pos):
            pin_pos = cursor_pos
        else:
            pin_pos = screen_geo.center()

        self._on_pin(pixmap, pin_pos)

        # Brief toast notification
        try:
            from .ui.toast import ToastManager
            ToastManager.show(_("Screenshot pinned"), icon="📌", toast_type="info")
        except Exception:
            pass

    def _capture_full(self) -> None:
        """Capture full screen and copy to clipboard without selection UI."""
        logger.info("全屏截图快捷键触发")
        _mac_activate_app()

        try:
            pixmap = capture_all_screens(include_cursor=self.settings.capture_cursor)
        except Exception:
            logger.exception("全屏截图失败")
            return

        self._on_copy(pixmap)

        try:
            from .ui.toast import ToastManager
            ToastManager.show(_("Full screen copied to clipboard"), icon="✓", toast_type="success")
        except Exception:
            pass

    def _open_color_picker(self) -> None:
        """Open the screen color picker tool."""
        logger.info("Color picker hotkey triggered")
        _mac_activate_app()
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
            from .ui.toast import ToastManager
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
        theme_manager.set_mode(self.settings.theme)
        theme_manager.set_accent_color(self.settings.accent_color)
        theme_manager.apply_to_app(self)
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


