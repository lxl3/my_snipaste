import sys
import subprocess
import json

from PySide6.QtCore import Qt, Signal, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPixmap, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QTabBar, QTabWidget,
    QWidget, QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QCheckBox, QSlider, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QScrollArea, QGraphicsOpacityEffect,
)
from ..core.i18n import _, available_languages, load_translations
from .color_picker import get_color
from ..core.settings import AppSettings, get_settings
from ..core.constants import PRESET_COLORS
from ..core.logger import setup_logger
from ..core.theme import theme as _theme
from ..core import qss_base
from .theme_dialog import ThemeAwareDialog
from .title_bar import TitleBar
from .toggle_switch import ToggleSwitch
from .settings_card import SettingsCard

logger = setup_logger("settings_dialog")


class HotkeyRecorderWidget(QWidget):
    """Widget for recording keyboard shortcuts."""

    hotkey_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recording = False
        self._current_keys = set()
        self._hotkey = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._display = QLineEdit()
        self._display.setReadOnly(True)
        self._display.setPlaceholderText(_("Click 'Record' and press keys..."))
        layout.addWidget(self._display, 1)

        self._record_btn = QPushButton(_("Record"))
        self._record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self._record_btn)

        self._clear_btn = QPushButton(_("Clear"))
        self._clear_btn.clicked.connect(self._clear_hotkey)
        layout.addWidget(self._clear_btn)

    def set_hotkey(self, hotkey: str) -> None:
        """Set the displayed hotkey."""
        self._hotkey = hotkey
        self._display.setText(hotkey)

    def get_hotkey(self) -> str:
        """Get the current hotkey."""
        return self._hotkey

    def _toggle_recording(self) -> None:
        """Toggle recording mode."""
        self._recording = not self._recording
        if self._recording:
            self._record_btn.setText(_("Stop"))
            self._record_btn.setStyleSheet(qss_base.pushbutton_qss(
                bg="$accent",
                color="$text_accent"
            ))
            self._display.setText(_("Press keys..."))
            self._current_keys.clear()
            self.setFocus()
        else:
            self._stop_recording()

    def _stop_recording(self) -> None:
        """Stop recording and finalize the hotkey."""
        self._recording = False
        self._record_btn.setText(_("Record"))
        self._record_btn.setStyleSheet("")  # 恢复为 dialog QSS 默认样式

        if self._current_keys:
            hotkey = self._format_hotkey(self._current_keys)
            self._hotkey = hotkey
            self._display.setText(hotkey)
            self.hotkey_changed.emit(hotkey)
            logger.debug(f"Recorded hotkey: {hotkey}")

    def _clear_hotkey(self) -> None:
        """Clear the current hotkey."""
        self._hotkey = ""
        self._display.clear()
        self._current_keys.clear()
        self.hotkey_changed.emit("")

    def focusOutEvent(self, event: QEvent) -> None:
        if self._recording:
            self._stop_recording()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Capture key press during recording."""
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()

        # Ignore standalone modifier keys release
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        # Record modifiers
        modifiers = event.modifiers()
        self._current_keys.clear()

        if sys.platform == 'darwin':
            # On macOS: Qt.ControlModifier = Command (⌘), Qt.MetaModifier = Control (⌃)
            if modifiers & Qt.ControlModifier:
                self._current_keys.add('cmd')
            if modifiers & Qt.MetaModifier:
                self._current_keys.add('ctrl')
        else:
            if modifiers & Qt.ControlModifier:
                self._current_keys.add('ctrl')
            if modifiers & Qt.MetaModifier:
                self._current_keys.add('meta')
        if modifiers & Qt.ShiftModifier:
            self._current_keys.add('shift')
        if modifiers & Qt.AltModifier:
            self._current_keys.add('alt')

        # Record the main key
        key_name = self._key_to_string(key)
        if key_name:
            self._current_keys.add(key_name)
            # Show preview
            preview = self._format_hotkey(self._current_keys)
            self._display.setText(preview)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Finalize hotkey on key release."""
        if not self._recording:
            super().keyReleaseEvent(event)
            return

        # Auto-stop recording after releasing the key
        if self._current_keys and event.key() not in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            self._stop_recording()

    def _key_to_string(self, key: int) -> str:
        """Convert Qt key code to string representation."""
        # Function keys
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f'f{key - Qt.Key_F1 + 1}'

        # Letter keys
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key).lower()

        # Number keys
        if Qt.Key_0 <= key <= Qt.Key_9:
            return chr(key)

        # Special keys
        special_keys = {
            Qt.Key_Space: 'space',
            Qt.Key_Return: 'return',
            Qt.Key_Enter: 'enter',
            Qt.Key_Tab: 'tab',
            Qt.Key_Backspace: 'backspace',
            Qt.Key_Escape: 'esc',
        }
        return special_keys.get(key, '')

    def _format_hotkey(self, keys: set) -> str:
        """Format a set of keys into hotkey string."""
        if not keys:
            return ""

        # Order: modifiers first, then main key
        modifiers = []
        main_key = None

        for key in keys:
            if key in ('ctrl', 'shift', 'alt', 'cmd', 'meta'):
                modifiers.append(key)
            else:
                main_key = key

        # Sort modifiers for consistency
        modifier_order = {'ctrl': 0, 'shift': 1, 'alt': 2, 'cmd': 3, 'meta': 3}
        modifiers.sort(key=lambda x: modifier_order.get(x, 99))

        parts = modifiers
        if main_key:
            parts.append(main_key)

        return '+'.join(parts)


class SettingsDialog(ThemeAwareDialog):
    """Application settings dialog with tabs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings: AppSettings = get_settings()
        self._build_ui()
        self._load_settings()

    def _create_themed_label(self, text: str = "", **style_kwargs) -> QLabel:
        """创建一个主题感知的 label，自动响应主题切换

        Args:
            text: label 文字
            **style_kwargs: 传递给 qss_base.label_qss() 的样式参数

        Returns:
            QLabel: 配置好的 label
        """
        label = QLabel(text)
        # 构建样式模板（使用 token 变量，以便主题切换时替换）
        style_parts = []
        for key, value in style_kwargs.items():
            # 处理下划线转连字符（font_size -> font-size）
            css_key = key.replace('_', '-')
            style_parts.append(f"{css_key}: {value};")
        style_template = "QLabel { " + " ".join(style_parts) + " }"

        # 如果没有指定颜色，默认使用主题色
        if 'color' not in style_kwargs:
            style_template = f"QLabel {{ color: $text_primary; {' '.join(style_parts)} }}"

        # 注册到主题系统
        self._add_themed_widget(label, style_template)
        return label

    def _build_ui(self) -> None:
        self.setWindowTitle(_("MySnipaste Settings"))
        self.setMinimumSize(520, 420)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAutoFillBackground(True)
        # 无边框窗口：自定义标题栏代替原生标题栏（支持暗色模式）
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

        # 外层布局：标题栏 + 内容区域（零边距）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 自定义标题栏
        self._title_bar = TitleBar(self, _("MySnipaste Settings"))
        outer.addWidget(self._title_bar)

        # 内容容器（保留原始边距），QSS 提供主题背景
        content = QWidget()
        content.setObjectName("settingsContent")
        content.setAttribute(Qt.WA_StyledBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        self._tabs.setAttribute(Qt.WA_StyledBackground)
        # QTabWidget 背景由 QSS 控制（不设 autoFillBackground，避免 palette 与 QSS 冲突）
        self._tabs.addTab(self._build_general_tab(), _("General"))
        self._tabs.addTab(self._build_capture_tab(), _("Capture"))
        self._tabs.addTab(self._build_annotation_tab(), _("Annotation"))
        self._tabs.addTab(self._build_hotkeys_tab(), _("Shortcuts"))
        self._tabs.addTab(self._build_ocr_tab(), _("OCR"))
        self._tabs.addTab(self._build_advanced_tab(), _("Advanced"))
        # Tab 页背景由 QSS 控制（不使用 autoFillBackground，因为它依赖 palette
        # 且隐藏页不会随主题切换重绘，导致切换主题后其它 tab 背景残留旧颜色）
        for i in range(self._tabs.count()):
            tab_widget = self._tabs.widget(i)
            if tab_widget:
                tab_widget.setAttribute(Qt.WA_StyledBackground)
        layout.addWidget(self._tabs)

        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(_("Search settings..."))
        self._search_input.textChanged.connect(self._filter_settings)
        layout.addWidget(self._search_input)

        btn_layout = QHBoxLayout()

        reset_btn = QPushButton(_("Reset to Defaults"))
        reset_btn.clicked.connect(self._reset_to_defaults)
        self._add_themed_widget(reset_btn, "color: $text_secondary;")
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        export_btn = QPushButton(_("Export..."))
        export_btn.clicked.connect(self._export_settings)
        btn_layout.addWidget(export_btn)

        import_btn = QPushButton(_("Import..."))
        import_btn.clicked.connect(self._import_settings)
        btn_layout.addWidget(import_btn)

        save_btn = QPushButton(_("Save"))
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        outer.addWidget(content, stretch=1)

        _theme.apply_to_widget(self)
        self._build_stylesheet_qss()

    def _build_stylesheet_qss(self) -> None:
        """用主题 token 构建 QSS 并应用，确保暗/亮模式都正确。"""
        # 对话框专属样式（不会在其他地方复用的）
        self._apply_styles()

    def _apply_styles(self) -> None:
        """应用对话框样式表"""
        dialog_specific = _theme.qss("""
            QDialog {
                background: $bg_primary;
                border: 1px solid $border;
            }
            #settingsContent {
                background: $bg_primary;
            }
            TitleBar {
                background: $bg_secondary;
                border-bottom: 1px solid $border;
            }
            TitleBar QLabel {
                color: $text_primary;
                font-size: 13px;
                font-weight: 600;
            }
            TitleBar QPushButton {
                background: transparent;
                border: none;
                color: $text_primary;
                font-size: 14px;
                padding: 2px 8px;
                border-radius: 2px;
            }
            TitleBar QPushButton:hover {
                background: $hover_bg;
            }
            TitleBar QPushButton:pressed {
                background: $accent;
                color: $text_accent;
            }
            QTabWidget {
                background: $bg_primary;
            }
            QTabWidget::pane {
                border: 1px solid $border;
                border-radius: 4px;
                padding: 8px;
                background: $bg_primary;
            }
            QTabWidget QStackedWidget {
                background: $bg_primary;
            }
            QTabWidget QStackedWidget > QWidget {
                background: $bg_primary;
            }
            QTabBar {
                background: $bg_primary;
            }
            QTabBar::tab {
                padding: 6px 16px;
                margin: 1px;
                color: $text_primary;
                background: transparent;
            }
            QTabBar::tab:selected {
                background: $accent;
                color: $text_accent;
            }
            QTabBar::tab:hover:!selected {
                background: $hover_bg;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget { background: transparent; }
        """)
        # 通用 widget 样式（通过 qss_base 共享）
        shared = "".join([
            qss_base.groupbox_qss(),
            qss_base.lineedit_qss(),
            qss_base.spinbox_qss(),
            qss_base.pushbutton_qss(),
            qss_base.checkbox_qss(),
            qss_base.combobox_qss(),
            qss_base.label_qss(),
            qss_base.slider_qss(),
        ])
        self.setStyleSheet(dialog_specific + shared)

    def _on_before_theme_apply(self) -> None:
        """为 TabWidget、QTabBar 及其页面单独设置 QPalette。"""
        _theme.apply_to_widget(self._tabs)
        _tab_bar = self._tabs.findChild(QTabBar)
        if _tab_bar:
            _theme.apply_to_widget(_tab_bar)
        for i in range(self._tabs.count()):
            tab_widget = self._tabs.widget(i)
            if tab_widget:
                _theme.apply_to_widget(tab_widget)

    def _on_theme_changed(self, mode: str) -> None:
        """主题切换时重新应用样式（刷新token值）

        所有需要主题更新的 widget（包括 scroll viewport 和 content）
        现在都通过 _add_themed_widget 注册，基类会自动更新它们。
        """
        # 基类统一处理所有注册的 themed widgets
        super()._on_theme_changed(mode)

        # 额外处理：刷新所有使用 inline styles 的 QLabel
        # （这些 label 可能在 tab 构建时直接设置了样式，未通过 _add_themed_widget 注册）
        for label in self.findChildren(QLabel):
            style = label.styleSheet()
            # 只处理包含 token 的样式（避免影响无样式或固定样式的 label）
            if style and '$' in style:
                label.setStyleSheet(_theme.qss(style))

    # ─── General Tab ───

    def _build_general_tab(self) -> QWidget:
        """通用设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ⌨️ 全局快捷键卡片
        hotkey_card = SettingsCard(icon="⌨️", title=_("Global Hotkey"))
        self._hotkey_recorder = HotkeyRecorderWidget()
        hotkey_card.add_widget(self._hotkey_recorder)
        hint = QLabel(_("Click 'Record' and press your desired key combination"))
        hint.setStyleSheet(qss_base.label_qss(color="$text_placeholder", font_size="11px"))
        hotkey_card.add_widget(hint)
        layout.addWidget(hotkey_card)

        # 🌐 语言卡片
        lang_card = SettingsCard(icon="🌐", title=_("Language"))
        self._lang_combo = QComboBox()
        self._lang_combo.setMinimumWidth(200)
        for code, label in available_languages():
            self._lang_combo.addItem(label, code)
        lang_card.add_widget(self._lang_combo)
        layout.addWidget(lang_card)

        # 🎨 主题卡片
        theme_card = SettingsCard(icon="🎨", title=_("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.setMinimumWidth(200)
        self._theme_combo.addItem(_("Light"), "light")
        self._theme_combo.addItem(_("Dark"), "dark")
        self._theme_combo.addItem(_("Follow System"), "system")
        self._theme_combo.currentIndexChanged.connect(self._on_theme_preview)
        theme_card.add_widget(self._theme_combo)
        hint_theme = QLabel(_("Changes are previewed immediately"))
        hint_theme.setStyleSheet(qss_base.label_qss(color="$text_placeholder", font_size="11px"))
        theme_card.add_widget(hint_theme)
        layout.addWidget(theme_card)

        # macOS-specific settings
        if sys.platform == "darwin":
            # 🔒 权限卡片
            perm_card = SettingsCard(icon="🔒", title=_("Permissions"))

            from ..core.permissions import get_permission_status

            status = get_permission_status()

            # Input Monitoring
            input_label = QLabel()
            if status["input_monitoring"]:
                input_label.setText("✓ " + _("Input Monitoring: Granted"))
                input_label.setStyleSheet(qss_base.label_qss(color="#4CAF50", font_weight="600"))
            else:
                input_label.setText("✗ " + _("Input Monitoring: Not Granted"))
                input_label.setStyleSheet(qss_base.label_qss(color="#E53935", font_weight="600"))
            perm_card.add_widget(input_label)

            # Screen Recording
            screen_label = QLabel()
            if status["screen_recording"]:
                screen_label.setText("✓ " + _("Screen Recording: Granted"))
                screen_label.setStyleSheet(qss_base.label_qss(color="#4CAF50"))
            elif status["screen_recording"] is None:
                screen_label.setText("• " + _("Screen Recording: Unknown"))
                screen_label.setStyleSheet(qss_base.label_qss(color="$text_placeholder"))
            else:
                screen_label.setText("✗ " + _("Screen Recording: Not Granted"))
                screen_label.setStyleSheet(qss_base.label_qss(color="#E53935"))
            perm_card.add_widget(screen_label)

            perm_card.add_spacing(8)

            # Open settings button
            self._open_perm_btn = QPushButton(_("Open System Settings"))
            # 不含 setStyleSheet — 由 dialog QSS 统一控制
            self._open_perm_btn.clicked.connect(self._open_permission_settings)
            perm_card.add_widget(self._open_perm_btn)

            layout.addWidget(perm_card)

            # 🚀 启动卡片
            startup_card = SettingsCard(icon="🚀", title=_("Startup"))
            startup_row = QHBoxLayout()
            startup_label = QLabel(_("Launch at login"))
            startup_label.setStyleSheet(qss_base.label_qss())
            self._launch_checkbox = ToggleSwitch()
            startup_row.addWidget(startup_label)
            startup_row.addStretch()
            startup_row.addWidget(self._launch_checkbox)
            startup_card.add_layout(startup_row)
            layout.addWidget(startup_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_general())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画（首次显示时）
        self._setup_fade_in_animation(tab)

        return tab

    def _create_scroll_area(self) -> tuple[QScrollArea, QWidget]:
        """创建配置好的滚动区域和内容容器

        Returns:
            (scroll, content): 滚动区域和内容容器widget
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 将滚动条 QSS 直接应用到 scrollbar 控件（而非依赖父控件 QSS 级联），
        # 解决 Windows windowsvista 样式下滚动条颜色不跟随主题的问题
        vsb = scroll.verticalScrollBar()
        if vsb:
            self._add_themed_widget(vsb, """
                QScrollBar::handle:vertical {
                    background: $border;
                    min-height: 30px;
                    border-radius: 4px;
                }
                QScrollBar::handle:vertical:hover {
                    background: $text_placeholder;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                    border: none;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)

        # 内容容器
        content = QWidget()

        # 注册 viewport 和 content 到主题系统（使用 token 模板）
        self._add_themed_widget(scroll.viewport(), "background: $bg_primary;")
        self._add_themed_widget(content, "background: $bg_primary;")

        return scroll, content

    def _setup_fade_in_animation(self, widget: QWidget):
        """为 widget 设置淡入动画（在 showEvent 时触发）

        注意：已禁用，因为与 QTabWidget 的 tab 切换机制冲突。
        保留方法签名以避免修改所有调用处。
        """
        # 淡入动画已禁用 - 与 QTabWidget 不兼容
        pass

    # ─── Capture Tab ───

    def _build_capture_tab(self) -> QWidget:
        """截图设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 💾 自动保存卡片
        save_card = SettingsCard(icon="💾", title=_("Auto Save"))

        # Toggle 行
        auto_save_row = QHBoxLayout()
        auto_save_label = QLabel(_("Auto save to directory"))
        auto_save_label.setStyleSheet(qss_base.label_qss())
        self._auto_save_checkbox = ToggleSwitch()
        self._auto_save_checkbox.toggled.connect(self._on_auto_save_toggle)
        auto_save_row.addWidget(auto_save_label)
        auto_save_row.addStretch()
        auto_save_row.addWidget(self._auto_save_checkbox)
        save_card.add_layout(auto_save_row)

        save_card.add_spacing(8)

        # 目录选择行
        dir_row = QHBoxLayout()
        dir_label = QLabel(_("Directory:"))
        dir_label.setStyleSheet(qss_base.label_qss())
        self._save_dir_input = QLineEdit()
        self._save_dir_input.setReadOnly(True)
        self._save_dir_input.setPlaceholderText(_("Select default save directory..."))
        browse_btn = QPushButton(_("Browse..."))
        # 不含 setStyleSheet — 由 dialog QSS 中的 qss_base.pushbutton_qss() 统一控制
        browse_btn.clicked.connect(self._browse_save_dir)
        dir_row.addWidget(dir_label)
        dir_row.addWidget(self._save_dir_input, 1)
        dir_row.addWidget(browse_btn)
        save_card.add_layout(dir_row)

        # 格式行
        format_row = QHBoxLayout()
        format_label = QLabel(_("Format:"))
        format_label.setStyleSheet(qss_base.label_qss())
        self._format_combo = QComboBox()
        self._format_combo.setMinimumWidth(120)
        self._format_combo.addItems(["PNG", "JPEG"])
        format_row.addWidget(format_label)
        format_row.addStretch()
        format_row.addWidget(self._format_combo)
        save_card.add_layout(format_row)

        layout.addWidget(save_card)

        # 🎯 截图行为卡片
        behavior_card = SettingsCard(icon="🎯", title=_("Capture Behavior"))

        # 播放声音
        sound_row = QHBoxLayout()
        sound_label = QLabel(_("Play sound when capturing"))
        sound_label.setStyleSheet(qss_base.label_qss())
        self._sound_checkbox = ToggleSwitch()
        sound_row.addWidget(sound_label)
        sound_row.addStretch()
        sound_row.addWidget(self._sound_checkbox)
        behavior_card.add_layout(sound_row)

        # 包含光标
        cursor_row = QHBoxLayout()
        cursor_label = QLabel(_("Include mouse cursor"))
        cursor_label.setStyleSheet(qss_base.label_qss())
        self._cursor_checkbox = ToggleSwitch()
        cursor_row.addWidget(cursor_label)
        cursor_row.addStretch()
        cursor_row.addWidget(self._cursor_checkbox)
        behavior_card.add_layout(cursor_row)

        behavior_card.add_spacing(8)

        # 截图延迟
        delay_row = QHBoxLayout()
        delay_label = QLabel(_("Capture delay:"))
        delay_label.setStyleSheet(qss_base.label_qss())
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 10)
        self._delay_spin.setSuffix(_(" seconds"))
        self._delay_spin.setMinimumWidth(120)
        delay_row.addWidget(delay_label)
        delay_row.addStretch()
        delay_row.addWidget(self._delay_spin)
        behavior_card.add_layout(delay_row)

        # 截图后操作
        after_row = QHBoxLayout()
        after_label = QLabel(_("After capture:"))
        after_label.setStyleSheet(qss_base.label_qss())
        self._after_action_combo = QComboBox()
        self._after_action_combo.setMinimumWidth(180)
        self._after_action_combo.addItem(_("None (show editor)"), "none")
        self._after_action_combo.addItem(_("Auto copy to clipboard"), "copy")
        self._after_action_combo.addItem(_("Auto save to file"), "save")
        after_row.addWidget(after_label)
        after_row.addStretch()
        after_row.addWidget(self._after_action_combo)
        behavior_card.add_layout(after_row)

        layout.addWidget(behavior_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_capture())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画
        self._setup_fade_in_animation(tab)

        return tab

    def _browse_save_dir(self) -> None:
        """Open directory browser for auto-save location."""
        current_dir = self._save_dir_input.text() or ""
        directory = QFileDialog.getExistingDirectory(
            self,
            _("Select Save Directory"),
            current_dir
        )
        if directory:
            self._save_dir_input.setText(directory)
            self._auto_save_checkbox.setChecked(True)

    def _on_auto_save_toggle(self, checked: bool) -> None:
        """Enable/disable save directory input based on checkbox."""
        self._save_dir_input.setEnabled(checked)

    # ─── OCR Tab ───

    def _build_ocr_tab(self) -> QWidget:
        """OCR 设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 🔍 OCR引擎卡片
        ocr_card = SettingsCard(icon="🔍", title=_("OCR Engine"))

        # 语言输入行
        lang_row = QHBoxLayout()
        lang_label = QLabel(_("Languages:"))
        lang_label.setStyleSheet(qss_base.label_qss())
        self._ocr_lang_input = QLineEdit()
        self._ocr_lang_input.setPlaceholderText(_("e.g. eng, chi_sim, eng+chi_sim"))
        lang_row.addWidget(lang_label)
        lang_row.addWidget(self._ocr_lang_input, 1)
        ocr_card.add_layout(lang_row)

        # 提示文字
        lang_hint = QLabel(
            _("Language codes separated by +.\n"
              "Common: eng, chi_sim, jpn, fra, deu, spa\n"
              "Run 'tesseract --list-langs' to see installed.")
        )
        lang_hint.setStyleSheet(qss_base.label_qss(color="$text_placeholder", font_size="11px"))
        ocr_card.add_widget(lang_hint)

        ocr_card.add_spacing(8)

        # 测试按钮
        test_btn = QPushButton(_("Test OCR"))
        # 不含 setStyleSheet — 由 dialog QSS 统一控制
        test_btn.clicked.connect(self._test_ocr)
        ocr_card.add_widget(test_btn)

        layout.addWidget(ocr_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_ocr())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画
        self._setup_fade_in_animation(tab)

        return tab

    def _test_ocr(self) -> None:
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            QMessageBox.information(self, _("OCR Test"),
                                    _("Tesseract v{version} is ready.\nLanguage: {lang}").format(
                                        version=version, lang=self._ocr_lang_input.text() or 'eng+chi_sim'))
        except Exception as e:
            QMessageBox.warning(self, _("OCR Test"), _("Tesseract not available:\n{error}").format(error=e))

    def _pick_custom_color(self) -> None:
        """Open color picker dialog for custom color selection."""
        current_color = QColor(self._color_combo.currentData() or PRESET_COLORS[0])
        color = get_color(current_color, self, _("Select Custom Color"))

        if color.isValid():
            hex_color = color.name()
            # Check if this color already exists in the combo box
            existing_idx = self._color_combo.findData(hex_color)

            if existing_idx >= 0:
                # Color already exists, select it
                self._color_combo.setCurrentIndex(existing_idx)
            else:
                # Add new custom color to the combo box
                pix = QPixmap(16, 16)
                pix.fill(color)
                self._color_combo.addItem(f"  {hex_color} (custom)", hex_color)
                self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
                self._color_combo.setCurrentIndex(self._color_combo.count() - 1)

            logger.debug(f"Custom color selected: {hex_color}")

    def _on_theme_preview(self) -> None:
        """Preview theme when combo box changes."""
        theme_mode = self._theme_combo.currentData()
        if theme_mode:
            logger.info(f"👁️ 主题预览切换: {theme_mode}")
            _theme.set_mode(theme_mode)
            # set_mode 已通过 theme_changed 信号同步触发 _on_theme_changed
            # （DirectConnection，同一线程），不需要再手动调用。
            # 全局调色板更新：确保对话框外控件（pin_window 等）同步
            _theme.apply_to_app(QApplication.instance())

    def _open_permission_settings(self) -> None:
        """Open macOS System Settings for permissions."""
        from ..core.permissions import open_input_monitoring_settings
        open_input_monitoring_settings()
        QMessageBox.information(
            self,
            _("Permission Settings"),
            _("System Settings opened.\n\n"
              "Please enable Input Monitoring and Screen Recording permissions,\n"
              "then restart MySnipaste for changes to take effect.")
        )

    def _reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        reply = QMessageBox.question(
            self,
            _("Reset to Defaults"),
            _("Are you sure you want to reset all settings to their default values?\n\n"
              "This action cannot be undone."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Create a new AppSettings instance with default values
            defaults = AppSettings()

            # Update UI with default values
            self._hotkey_recorder.set_hotkey(defaults.hotkey)
            self._ocr_lang_input.setText(defaults.ocr_language)

            idx = self._color_combo.findData(defaults.default_color)
            if idx >= 0:
                self._color_combo.setCurrentIndex(idx)
            self._width_spin.setValue(defaults.default_line_width)
            self._font_combo.setCurrentText(defaults.default_font_family)
            self._font_size_spin.setValue(defaults.default_font_size)

            self._save_dir_input.clear()
            self._auto_save_checkbox.setChecked(False)
            fmt_idx = self._format_combo.findText(defaults.auto_save_format.upper())
            if fmt_idx >= 0:
                self._format_combo.setCurrentIndex(fmt_idx)

            # Capture behavior settings
            self._sound_checkbox.setChecked(defaults.capture_sound)
            self._cursor_checkbox.setChecked(defaults.capture_cursor)
            self._delay_spin.setValue(defaults.capture_delay)
            after_idx = self._after_action_combo.findData(defaults.capture_after_action)
            if after_idx >= 0:
                self._after_action_combo.setCurrentIndex(after_idx)

            lang_idx = self._lang_combo.findData(defaults.language)
            if lang_idx >= 0:
                self._lang_combo.setCurrentIndex(lang_idx)

            if hasattr(self, '_launch_checkbox'):
                self._launch_checkbox.setChecked(defaults.launch_at_startup)

            self._opacity_slider.setValue(defaults.pin_window_opacity)
            log_idx = self._log_level_combo.findText(defaults.log_level)
            if log_idx >= 0:
                self._log_level_combo.setCurrentIndex(log_idx)

            # ─── Reset shortcuts to defaults ───
            shortcut_reset_map = {
                "capture": "hotkey",
                "ocr": "hotkey_ocr",
                "delay_capture": "hotkey_delay",
                "pin_capture": "hotkey_pin",
            "full_capture": "hotkey_full",
            "color_picker": "hotkey_color_picker",
            "shortcut_rect": "shortcut_rect",
                "shortcut_ellipse": "shortcut_ellipse",
                "shortcut_arrow": "shortcut_arrow",
                "shortcut_line": "shortcut_line",
                "shortcut_pen": "shortcut_pen",
                "shortcut_text": "shortcut_text",
                "shortcut_highlighter": "shortcut_highlighter",
                "shortcut_blur": "shortcut_blur",
                "shortcut_number_marker": "shortcut_number_marker",
                "shortcut_select": "shortcut_select",
            }
            for widget_key, setting_attr in shortcut_reset_map.items():
                widget = self._shortcut_widgets.get(widget_key)
                if widget:
                    widget.set_hotkey(getattr(defaults, setting_attr, ""))

            logger.info("Settings reset to defaults")
            QMessageBox.information(self, _("Reset Complete"), _("Settings have been reset to default values."))

    # ─── Settings Search ───

    def _filter_settings(self, text: str) -> None:
        """Filter QGroupBox widgets in the current tab by search text."""
        tab = self._tabs.currentWidget()
        if not tab:
            return
        text = text.strip().lower()
        for group in tab.findChildren(QGroupBox):
            if not text:
                group.show()
                continue
            # Check group title
            title = group.title().lower()
            if text in title:
                group.show()
                continue
            # Check child label/checkbox text
            found = False
            for label in group.findChildren(QLabel):
                if text in label.text().lower():
                    found = True
                    break
            if not found:
                for cb in group.findChildren(QCheckBox):
                    if text in cb.text().lower():
                        found = True
                        break
            group.setVisible(found)

    # ─── Export / Import ───

    def _export_settings(self) -> None:
        """Export current settings to a JSON file."""
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("Export Settings"),
            "mysnipaste_settings.json",
            _("JSON Files (*.json)")
        )
        if not path:
            return

        # Gather current widget values into a dict
        data: dict = {}
        s = self._settings

        # General
        data["hotkey"] = self._hotkey_recorder.get_hotkey() or s.hotkey
        data["language"] = self._lang_combo.currentData() or "zh_CN"
        data["theme"] = self._theme_combo.currentData() or "light"
        if hasattr(self, "_launch_checkbox"):
            data["launch_at_startup"] = self._launch_checkbox.isChecked()

        # Capture
        data["auto_save_dir"] = self._save_dir_input.text().strip() if self._auto_save_checkbox.isChecked() else ""
        data["auto_save_format"] = self._format_combo.currentText().lower()
        data["capture_sound"] = self._sound_checkbox.isChecked()
        data["capture_cursor"] = self._cursor_checkbox.isChecked()
        data["capture_delay"] = self._delay_spin.value()
        data["capture_after_action"] = self._after_action_combo.currentData()

        # Annotation
        data["default_color"] = self._color_combo.currentData() or PRESET_COLORS[0]
        data["default_line_width"] = self._width_spin.value()
        data["default_font_family"] = self._font_combo.currentText()
        data["default_font_size"] = self._font_size_spin.value()

        # Shortcuts
        shortcut_keys = [
            "hotkey", "hotkey_ocr", "hotkey_delay", "hotkey_pin",
            "hotkey_full", "hotkey_color_picker",
            "shortcut_rect", "shortcut_ellipse", "shortcut_arrow",
            "shortcut_line", "shortcut_pen", "shortcut_text",
            "shortcut_highlighter", "shortcut_blur",
            "shortcut_number_marker", "shortcut_select",
        ]
        for sk in shortcut_keys:
            data[sk] = getattr(s, sk, "")

        # OCR
        data["ocr_language"] = self._ocr_lang_input.text().strip() or "eng+chi_sim"

        # Advanced
        data["pin_window_opacity"] = self._opacity_slider.value()
        data["log_level"] = self._log_level_combo.currentText()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Settings exported to {path}")
            QMessageBox.information(self, _("Export"), _("Settings exported successfully."))
        except Exception as e:
            logger.error(f"Failed to export settings: {e}")
            QMessageBox.warning(self, _("Export Error"), _("Failed to export settings:\n{error}").format(error=e))

    def _import_settings(self) -> None:
        """Import settings from a JSON file and update UI."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, _("Import Settings"),
            "", _("JSON Files (*.json)")
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read import file: {e}")
            QMessageBox.warning(self, _("Import Error"),
                                _("Failed to read file:\n{error}").format(error=e))
            return

        if not isinstance(data, dict):
            QMessageBox.warning(self, _("Import Error"), _("Invalid settings file format."))
            return

        # Apply loaded values to widgets
        s = self._settings

        # General
        if "hotkey" in data:
            self._hotkey_recorder.set_hotkey(str(data["hotkey"]))
        if "language" in data:
            idx = self._lang_combo.findData(data["language"])
            if idx >= 0:
                self._lang_combo.setCurrentIndex(idx)
        if "theme" in data:
            tidx = self._theme_combo.findData(data["theme"])
            if tidx >= 0:
                self._theme_combo.setCurrentIndex(tidx)
        if hasattr(self, "_launch_checkbox") and "launch_at_startup" in data:
            self._launch_checkbox.setChecked(bool(data["launch_at_startup"]))

        # Capture
        if "auto_save_dir" in data and data["auto_save_dir"]:
            self._save_dir_input.setText(str(data["auto_save_dir"]))
            self._auto_save_checkbox.setChecked(True)
        else:
            self._save_dir_input.clear()
            self._auto_save_checkbox.setChecked(False)
        if "auto_save_format" in data:
            fidx = self._format_combo.findText(str(data["auto_save_format"]).upper())
            if fidx >= 0:
                self._format_combo.setCurrentIndex(fidx)
        if "capture_sound" in data:
            self._sound_checkbox.setChecked(bool(data["capture_sound"]))
        if "capture_cursor" in data:
            self._cursor_checkbox.setChecked(bool(data["capture_cursor"]))
        if "capture_delay" in data:
            self._delay_spin.setValue(int(data["capture_delay"]))
        if "capture_after_action" in data:
            aidx = self._after_action_combo.findData(data["capture_after_action"])
            if aidx >= 0:
                self._after_action_combo.setCurrentIndex(aidx)

        # Annotation
        if "default_color" in data:
            cidx = self._color_combo.findData(data["default_color"])
            if cidx >= 0:
                self._color_combo.setCurrentIndex(cidx)
        if "default_line_width" in data:
            self._width_spin.setValue(int(data["default_line_width"]))
        if "default_font_family" in data:
            self._font_combo.setCurrentText(str(data["default_font_family"]))
        if "default_font_size" in data:
            self._font_size_spin.setValue(int(data["default_font_size"]))

        # Shortcuts
        shortcut_keys = {
            "capture": "hotkey", "ocr": "hotkey_ocr",
            "delay_capture": "hotkey_delay", "pin_capture": "hotkey_pin",
            "full_capture": "hotkey_full", "color_picker": "hotkey_color_picker",
            "shortcut_rect": "shortcut_rect", "shortcut_ellipse": "shortcut_ellipse",
            "shortcut_arrow": "shortcut_arrow", "shortcut_line": "shortcut_line",
            "shortcut_pen": "shortcut_pen", "shortcut_text": "shortcut_text",
            "shortcut_highlighter": "shortcut_highlighter",
            "shortcut_blur": "shortcut_blur",
            "shortcut_number_marker": "shortcut_number_marker",
            "shortcut_select": "shortcut_select",
        }
        for widget_key, attr in shortcut_keys.items():
            if attr in data:
                widget = self._shortcut_widgets.get(widget_key)
                if widget:
                    widget.set_hotkey(str(data[attr]))

        # OCR
        if "ocr_language" in data:
            self._ocr_lang_input.setText(str(data["ocr_language"]))

        # Advanced
        if "pin_window_opacity" in data:
            self._opacity_slider.setValue(int(data["pin_window_opacity"]))
        if "log_level" in data:
            lidx = self._log_level_combo.findText(str(data["log_level"]))
            if lidx >= 0:
                self._log_level_combo.setCurrentIndex(lidx)

        logger.info(f"Settings imported from {path}")
        QMessageBox.information(self, _("Import"), _("Settings imported successfully.\nClick Save to apply them."))

    # ─── Per-Tab Reset ───

    def _reset_tab_general(self) -> None:
        """Reset General tab settings to defaults."""
        defaults = AppSettings()
        self._hotkey_recorder.set_hotkey(defaults.hotkey)
        lidx = self._lang_combo.findData(defaults.language)
        if lidx >= 0:
            self._lang_combo.setCurrentIndex(lidx)
        tidx = self._theme_combo.findData("light")
        if tidx >= 0:
            self._theme_combo.setCurrentIndex(tidx)
        if hasattr(self, "_launch_checkbox"):
            self._launch_checkbox.setChecked(defaults.launch_at_startup)

    def _reset_tab_capture(self) -> None:
        """Reset Capture tab settings to defaults."""
        defaults = AppSettings()
        self._save_dir_input.clear()
        self._auto_save_checkbox.setChecked(False)
        fidx = self._format_combo.findText(defaults.auto_save_format.upper())
        if fidx >= 0:
            self._format_combo.setCurrentIndex(fidx)
        self._sound_checkbox.setChecked(defaults.capture_sound)
        self._cursor_checkbox.setChecked(defaults.capture_cursor)
        self._delay_spin.setValue(defaults.capture_delay)
        aidx = self._after_action_combo.findData(defaults.capture_after_action)
        if aidx >= 0:
            self._after_action_combo.setCurrentIndex(aidx)

    def _reset_tab_annotation(self) -> None:
        """Reset Annotation tab settings to defaults."""
        defaults = AppSettings()
        cidx = self._color_combo.findData(defaults.default_color)
        if cidx >= 0:
            self._color_combo.setCurrentIndex(cidx)
        self._width_spin.setValue(defaults.default_line_width)
        self._font_combo.setCurrentText(defaults.default_font_family)
        self._font_size_spin.setValue(defaults.default_font_size)

    def _reset_tab_hotkeys(self) -> None:
        """Reset Shortcuts tab settings to defaults."""
        defaults = AppSettings()
        shortcut_map = {
            "capture": "hotkey", "ocr": "hotkey_ocr",
            "delay_capture": "hotkey_delay", "pin_capture": "hotkey_pin",
            "full_capture": "hotkey_full", "color_picker": "hotkey_color_picker",
            "shortcut_rect": "shortcut_rect", "shortcut_ellipse": "shortcut_ellipse",
            "shortcut_arrow": "shortcut_arrow", "shortcut_line": "shortcut_line",
            "shortcut_pen": "shortcut_pen", "shortcut_text": "shortcut_text",
            "shortcut_highlighter": "shortcut_highlighter",
            "shortcut_blur": "shortcut_blur",
            "shortcut_number_marker": "shortcut_number_marker",
            "shortcut_select": "shortcut_select",
        }
        for widget_key, attr in shortcut_map.items():
            widget = self._shortcut_widgets.get(widget_key)
            if widget:
                widget.set_hotkey(getattr(defaults, attr, ""))

    def _reset_tab_ocr(self) -> None:
        """Reset OCR tab settings to defaults."""
        defaults = AppSettings()
        self._ocr_lang_input.setText(defaults.ocr_language)

    def _reset_tab_advanced(self) -> None:
        """Reset Advanced tab settings to defaults."""
        defaults = AppSettings()
        self._opacity_slider.setValue(defaults.pin_window_opacity)
        lidx = self._log_level_combo.findText(defaults.log_level)
        if lidx >= 0:
            self._log_level_combo.setCurrentIndex(lidx)

    # ─── Annotation Tab ───

    def _build_annotation_tab(self) -> QWidget:
        """标注设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 🎨 默认标注样式卡片
        style_card = SettingsCard(icon="🎨", title=_("Default Annotation Style"))

        # 颜色选择行
        color_row_layout = QHBoxLayout()
        color_label = QLabel(_("Color:"))
        color_label.setStyleSheet(qss_base.label_qss())
        self._color_combo = QComboBox()
        self._color_combo.setMinimumWidth(150)
        for c in PRESET_COLORS:
            pix = QPixmap(16, 16)
            pix.fill(QColor(c))
            self._color_combo.addItem(f"  {c}", c)
            self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
        self._custom_color_btn = QPushButton(_("Custom..."))
        # 不含 setStyleSheet — 由 dialog QSS 统一控制
        self._custom_color_btn.clicked.connect(self._pick_custom_color)
        color_row_layout.addWidget(color_label)
        color_row_layout.addStretch()
        color_row_layout.addWidget(self._color_combo)
        color_row_layout.addWidget(self._custom_color_btn)
        style_card.add_layout(color_row_layout)

        # 线宽行
        width_row = QHBoxLayout()
        width_label = QLabel(_("Line Width:"))
        width_label.setStyleSheet(qss_base.label_qss())
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setMinimumWidth(100)
        width_row.addWidget(width_label)
        width_row.addStretch()
        width_row.addWidget(self._width_spin)
        style_card.add_layout(width_row)

        # 字体行
        font_row = QHBoxLayout()
        font_label = QLabel(_("Font:"))
        font_label.setStyleSheet(qss_base.label_qss())
        self._font_combo = QComboBox()
        self._font_combo.setMinimumWidth(180)
        self._font_combo.addItems(["Segoe UI", "Arial", "Helvetica", "PingFang SC", "Microsoft YaHei"])
        self._font_combo.setEditable(True)
        font_row.addWidget(font_label)
        font_row.addStretch()
        font_row.addWidget(self._font_combo)
        style_card.add_layout(font_row)

        # 字号行
        font_size_row = QHBoxLayout()
        font_size_label = QLabel(_("Font Size:"))
        font_size_label.setStyleSheet(qss_base.label_qss())
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 72)
        self._font_size_spin.setMinimumWidth(100)
        font_size_row.addWidget(font_size_label)
        font_size_row.addStretch()
        font_size_row.addWidget(self._font_size_spin)
        style_card.add_layout(font_size_row)

        layout.addWidget(style_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_annotation())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画
        self._setup_fade_in_animation(tab)

        return tab

    # ─── Advanced Tab ───

    def _build_advanced_tab(self) -> QWidget:
        """高级设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 📌 Pin窗口卡片
        pin_card = SettingsCard(icon="📌", title=_("Pin Window"))

        # 不透明度滑块行
        opacity_row = QHBoxLayout()
        opacity_label_text = QLabel(_("Opacity:"))
        opacity_label_text.setStyleSheet(qss_base.label_qss())
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setStyleSheet(qss_base.slider_qss())
        self._opacity_label = QLabel("100%")
        self._opacity_label.setStyleSheet(qss_base.label_qss(font_weight="600"))
        self._opacity_label.setMinimumWidth(50)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(opacity_label_text)
        opacity_row.addWidget(self._opacity_slider, 1)
        opacity_row.addWidget(self._opacity_label)
        pin_card.add_layout(opacity_row)

        hint_opacity = QLabel(_("Controls the opacity of pinned screenshots"))
        hint_opacity.setStyleSheet(qss_base.label_qss(color="$text_placeholder", font_size="11px"))
        pin_card.add_widget(hint_opacity)

        layout.addWidget(pin_card)

        # 📋 日志卡片
        log_card = SettingsCard(icon="📋", title=_("Logging"))

        # 日志级别行
        log_row = QHBoxLayout()
        log_label = QLabel(_("Log Level:"))
        log_label.setStyleSheet(qss_base.label_qss())
        self._log_level_combo = QComboBox()
        self._log_level_combo.setMinimumWidth(150)
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_row.addWidget(log_label)
        log_row.addStretch()
        log_row.addWidget(self._log_level_combo)
        log_card.add_layout(log_row)

        hint_log = QLabel(_("Higher levels show fewer messages"))
        hint_log.setStyleSheet(qss_base.label_qss(color="$text_placeholder", font_size="11px"))
        log_card.add_widget(hint_log)

        layout.addWidget(log_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_advanced())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画
        self._setup_fade_in_animation(tab)

        return tab

    # ─── Shortcuts Tab ───

    def _build_hotkeys_tab(self) -> QWidget:
        """快捷键设置 Tab - 现代卡片布局"""
        # 主容器
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域和内容容器
        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        # 内容布局
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Store all shortcut recorder widgets for load/save/conflict-check
        self._shortcut_widgets: dict[str, HotkeyRecorderWidget] = {}

        # ⌨️ 全局快捷键卡片
        global_card = SettingsCard(icon="⌨️", title=_("Global Shortcuts"))

        global_items = [
            ("capture", _("Capture Screenshot")),
            ("ocr", _("OCR Clipboard")),
            ("delay_capture", _("Delayed Screenshot")),
            ("pin_capture", _("Capture && Pin")),
            ("full_capture", _("Full Screen Capture")),
            ("color_picker", _("Screen Color Picker")),
        ]

        for key, label in global_items:
            # 快捷键行
            hotkey_row = QVBoxLayout()
            hotkey_row.setSpacing(4)

            # 标签 + 录制器
            row = QHBoxLayout()
            row.setSpacing(8)
            label_widget = QLabel(label + ":")
            label_widget.setStyleSheet(qss_base.label_qss(font_size="13px"))
            label_widget.setMinimumWidth(150)
            rec = HotkeyRecorderWidget()
            self._shortcut_widgets[key] = rec
            row.addWidget(label_widget)
            row.addWidget(rec, 1)
            hotkey_row.addLayout(row)

            # 冲突警告（初始隐藏）
            warn = QLabel("")
            warn.setStyleSheet(qss_base.label_qss(color="$hotkey_conflict", font_size="11px"))
            warn.setVisible(False)
            hotkey_row.addWidget(warn)

            global_card.add_layout(hotkey_row)

        layout.addWidget(global_card)

        # 📝 编辑器工具快捷键卡片
        editor_card = SettingsCard(icon="📝", title=_("Editor Tool Shortcuts"))

        editor_items = [
            ("shortcut_rect", _("Rectangle Tool"), "R"),
            ("shortcut_ellipse", _("Ellipse Tool"), "E"),
            ("shortcut_arrow", _("Arrow Tool"), "A"),
            ("shortcut_line", _("Line Tool"), "L"),
            ("shortcut_pen", _("Pen Tool"), "P"),
            ("shortcut_text", _("Text Tool"), "T"),
            ("shortcut_highlighter", _("Highlighter Tool"), "H"),
            ("shortcut_blur", _("Blur Tool"), "B"),
            ("shortcut_number_marker", _("Number Marker Tool"), "N"),
            ("shortcut_select", _("Select Tool"), "V"),
        ]

        for key, label, default in editor_items:
            # 快捷键行
            hotkey_row = QHBoxLayout()
            hotkey_row.setSpacing(8)
            label_widget = QLabel(label + ":")
            label_widget.setStyleSheet(qss_base.label_qss(font_size="13px"))
            label_widget.setMinimumWidth(150)
            rec = HotkeyRecorderWidget()
            self._shortcut_widgets[key] = rec
            hotkey_row.addWidget(label_widget)
            hotkey_row.addWidget(rec, 1)
            editor_card.add_layout(hotkey_row)

        layout.addWidget(editor_card)

        # 底部重置按钮
        layout.addStretch()
        reset_btn = QPushButton(_("Reset Tab"))
        reset_btn.clicked.connect(lambda: self._reset_tab_hotkeys())
        self._add_themed_widget(reset_btn, """
            QPushButton { padding: 6px 20px; border: 1px solid $border;
                border-radius: 4px; background: transparent;
                color: $text_secondary; font-size: 11px; }
            QPushButton:hover { background: $hover_bg; }
            QPushButton:pressed { background: $bg_primary; }
        """)
        layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        scroll.setWidget(content)

        # 淡入动画
        self._setup_fade_in_animation(tab)

        return tab

    # ─── Load / Save ───

    def _load_settings(self) -> None:
        s = self._settings
        self._hotkey_recorder.set_hotkey(s.hotkey)
        self._ocr_lang_input.setText(s.ocr_language)

        idx = self._color_combo.findData(s.default_color)
        if idx >= 0:
            self._color_combo.setCurrentIndex(idx)
        self._width_spin.setValue(s.default_line_width)
        self._font_combo.setCurrentText(s.default_font_family)
        self._font_size_spin.setValue(s.default_font_size)

        self._save_dir_input.setText(s.auto_save_dir)
        fmt_idx = self._format_combo.findText(s.auto_save_format.upper())
        if fmt_idx >= 0:
            self._format_combo.setCurrentIndex(fmt_idx)
        self._auto_save_checkbox.setChecked(bool(s.auto_save_dir))

        # Capture behavior settings
        self._sound_checkbox.setChecked(s.capture_sound)
        self._cursor_checkbox.setChecked(s.capture_cursor)
        self._delay_spin.setValue(s.capture_delay)
        after_idx = self._after_action_combo.findData(s.capture_after_action)
        if after_idx >= 0:
            self._after_action_combo.setCurrentIndex(after_idx)

        lang_idx = self._lang_combo.findData(s.language)
        if lang_idx >= 0:
            self._lang_combo.setCurrentIndex(lang_idx)

        theme_idx = self._theme_combo.findData(s.theme)
        if theme_idx >= 0:
            self._theme_combo.setCurrentIndex(theme_idx)

        if hasattr(self, '_launch_checkbox'):
            self._launch_checkbox.setChecked(s.launch_at_startup)

        self._opacity_slider.setValue(s.pin_window_opacity)
        log_idx = self._log_level_combo.findText(s.log_level)
        if log_idx >= 0:
            self._log_level_combo.setCurrentIndex(log_idx)

        # ─── Load shortcut settings ───
        shortcut_keys = {
            "capture": "hotkey",
            "ocr": "hotkey_ocr",
            "delay_capture": "hotkey_delay",
            "pin_capture": "hotkey_pin",
            "full_capture": "hotkey_full",
            "color_picker": "hotkey_color_picker",
            "shortcut_rect": "shortcut_rect",
            "shortcut_ellipse": "shortcut_ellipse",
            "shortcut_arrow": "shortcut_arrow",
            "shortcut_line": "shortcut_line",
            "shortcut_pen": "shortcut_pen",
            "shortcut_text": "shortcut_text",
            "shortcut_highlighter": "shortcut_highlighter",
            "shortcut_blur": "shortcut_blur",
            "shortcut_number_marker": "shortcut_number_marker",
            "shortcut_select": "shortcut_select",
        }
        for widget_key, setting_attr in shortcut_keys.items():
            widget = self._shortcut_widgets.get(widget_key)
            if widget:
                widget.set_hotkey(getattr(s, setting_attr, ""))

    def _save_and_close(self) -> None:
        s = self._settings
        s.hotkey = self._hotkey_recorder.get_hotkey() or s.hotkey
        s.ocr_language = self._ocr_lang_input.text().strip() or "eng+chi_sim"

        s.default_color = self._color_combo.currentData() or PRESET_COLORS[0]
        s.default_line_width = self._width_spin.value()
        s.default_font_family = self._font_combo.currentText()
        s.default_font_size = self._font_size_spin.value()

        if self._auto_save_checkbox.isChecked():
            s.auto_save_dir = self._save_dir_input.text().strip()
        else:
            s.auto_save_dir = ""
        s.auto_save_format = self._format_combo.currentText().lower()

        # Capture behavior settings
        s.capture_sound = self._sound_checkbox.isChecked()
        s.capture_cursor = self._cursor_checkbox.isChecked()
        s.capture_delay = self._delay_spin.value()
        s.capture_after_action = self._after_action_combo.currentData()

        s.language = self._lang_combo.currentData() or "zh_CN"
        s.theme = self._theme_combo.currentData() or "light"

        if hasattr(self, '_launch_checkbox'):
            s.launch_at_startup = self._launch_checkbox.isChecked()
            self._apply_launch_at_startup(s.launch_at_startup)

        s.pin_window_opacity = self._opacity_slider.value()
        s.log_level = self._log_level_combo.currentText()

        # ─── Save shortcut settings with conflict detection ───
        shortcut_save_map = {
            "capture": "hotkey",
            "ocr": "hotkey_ocr",
            "delay_capture": "hotkey_delay",
            "pin_capture": "hotkey_pin",
                "full_capture": "hotkey_full",
                "color_picker": "hotkey_color_picker",
                "shortcut_rect": "shortcut_rect",
            "shortcut_ellipse": "shortcut_ellipse",
            "shortcut_arrow": "shortcut_arrow",
            "shortcut_line": "shortcut_line",
            "shortcut_pen": "shortcut_pen",
            "shortcut_text": "shortcut_text",
            "shortcut_highlighter": "shortcut_highlighter",
            "shortcut_blur": "shortcut_blur",
            "shortcut_number_marker": "shortcut_number_marker",
            "shortcut_select": "shortcut_select",
        }
        # Check for conflicts before saving
        seen_values: dict[str, str] = {}
        conflicts: list[str] = []
        for widget_key, setting_attr in shortcut_save_map.items():
            widget = self._shortcut_widgets.get(widget_key)
            if widget:
                val = widget.get_hotkey().strip().lower()
                if val:
                    if val in seen_values:
                        conflicts.append(f"'{widget_key}' and '{seen_values[val]}' both use '{val}'")
                    else:
                        seen_values[val] = widget_key
                    setattr(s, setting_attr, val)

        if conflicts:
            reply = QMessageBox.warning(
                self,
                _("Shortcut Conflict"),
                _("The following shortcuts conflict:\n\n{conflicts}\n\n"
                  "Do you want to save anyway?").format(conflicts="\n".join(conflicts)),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return  # Don't close, let user fix conflicts

        s.save()
        logger.info("Settings saved")
        self.accept()

    def _apply_launch_at_startup(self, enable: bool) -> None:
        if sys.platform != "darwin":
            return

        # Get the application bundle path (.app) on macOS
        # When running from PyInstaller bundle, we need the .app path, not the executable
        import os
        app_path = sys.executable

        # If running from a .app bundle, find the .app directory
        if hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle
            # executable is inside MySnipaste.app/Contents/MacOS/MySnipaste
            # We need MySnipaste.app
            parts = app_path.split('/')
            try:
                app_idx = next(i for i, part in enumerate(parts) if part.endswith('.app'))
                app_path = '/'.join(parts[:app_idx + 1])
            except StopIteration:
                logger.warning(f"Could not find .app in path: {app_path}")
                return

        logger.debug(f"Using app path for login item: {app_path}")

        try:
            if enable:
                subprocess.run([
                    "osascript", "-e",
                    f'tell application "System Events" to make login item '
                    f'with properties {{path:"{app_path}", hidden:false, name:"MySnipaste"}}'
                ], capture_output=True, timeout=5, check=False)
                logger.info(f"Added login item: {app_path}")
            else:
                subprocess.run([
                    "osascript", "-e",
                    'tell application "System Events" to delete login item "MySnipaste"'
                ], capture_output=True, timeout=5, check=False)
                logger.info("Removed login item")
        except Exception as e:
            logger.warning(f"Failed to update login item: {e}")

    @staticmethod
    def open(parent=None) -> AppSettings | None:
        dialog = SettingsDialog(parent)
        result = dialog.exec()
        if result == QDialog.Accepted:
            s = AppSettings.reload()
            load_translations(s.language)
            return s
        return None



