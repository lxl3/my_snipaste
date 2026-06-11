"""通用设置 Tab"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QApplication,
)

from .base_tab import BaseTab
from ..widgets.no_scroll_combo import NoScrollComboBox
from ...settings_card import SettingsCard
from ...toggle_switch import ToggleRow
from ....core.i18n import _, available_languages
from ....core.settings import AppSettings
from ....core.theme_pkg import theme as _theme
from ....core.logger import setup_logger
from ...color_picker import get_color
from PySide6.QtGui import QColor

logger = setup_logger("general_tab")


class GeneralTab(BaseTab):
    """通用设置 Tab - 语言、主题、权限、启动"""

    tab_id = "general"
    tab_name = "General"
    tab_icon = "gear"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._accent_btn = None
        self._theme_combo = None
        self._lang_combo = None
        self._launch_checkbox = None
        super().__init__(parent)

    def _build_ui(self):
        """构建通用设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_language_card(layout)
        self._build_theme_card(layout)

        if sys.platform == "darwin":
            self._build_permissions_card(layout)
            self._build_startup_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_language_card(self, layout: QVBoxLayout) -> None:
        """语言卡片"""
        lang_card = SettingsCard(icon="🌐", title=_("Language"))
        self._lang_combo = NoScrollComboBox()
        self._lang_combo.setMinimumWidth(200)
        for code, label in available_languages():
            self._lang_combo.addItem(label, code)
        lang_card.add_widget(self._lang_combo)
        layout.addWidget(lang_card)

    def _build_theme_card(self, layout: QVBoxLayout) -> None:
        """主题卡片"""
        theme_card = SettingsCard(icon="🎨", title=_("Theme"))

        mode_row = QHBoxLayout()
        mode_label = QLabel(_("Mode:"))
        if self._dialog:
            self._dialog._add_themed_widget(mode_label, "QLabel { color: $text_primary; }")
        self._theme_combo = NoScrollComboBox()
        self._theme_combo.setMinimumWidth(200)
        self._theme_combo.addItem(_("Light"), "light")
        self._theme_combo.addItem(_("Dark"), "dark")
        self._theme_combo.addItem(_("Follow System"), "system")
        self._theme_combo.currentIndexChanged.connect(self._on_theme_preview)
        mode_row.addWidget(mode_label)
        mode_row.addStretch()
        mode_row.addWidget(self._theme_combo)
        theme_card.add_layout(mode_row)

        theme_card.add_spacing(8)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        accent_label = QLabel(_("Accent Color:"))
        if self._dialog:
            self._dialog._add_themed_widget(accent_label, "QLabel { color: $text_primary; }")
        self._accent_btn = QPushButton()
        self._accent_btn.setFixedSize(32, 32)
        self._accent_btn.setCursor(Qt.PointingHandCursor)
        self._accent_btn.setToolTip(_("Click to select accent color"))
        self._accent_btn.clicked.connect(self._on_accent_color_click)
        self._accent_reset_btn = QPushButton(_("Default"))
        self._accent_reset_btn.setFixedWidth(70)
        self._accent_reset_btn.clicked.connect(self._on_accent_reset)
        accent_row.addWidget(accent_label)
        accent_row.addStretch()
        accent_row.addWidget(self._accent_btn)
        accent_row.addWidget(self._accent_reset_btn)
        theme_card.add_layout(accent_row)

        hint_theme = QLabel(_("Changes are previewed immediately"))
        if self._dialog:
            self._dialog._add_themed_widget(hint_theme, "QLabel { color: $text_placeholder; font-size: 11px; }")
        theme_card.add_widget(hint_theme)
        layout.addWidget(theme_card)

    def _build_permissions_card(self, layout: QVBoxLayout) -> None:
        """macOS 权限卡片"""
        from ....core.permissions import get_permission_status

        perm_card = SettingsCard(icon="🔒", title=_("Permissions"))
        status = get_permission_status()

        input_label = QLabel()
        if status["input_monitoring"]:
            input_label.setText("✓ " + _("Input Monitoring: Granted"))
            input_label.setStyleSheet("color: #4CAF50; font-weight: 600;")
        else:
            input_label.setText("✗ " + _("Input Monitoring: Not Granted"))
            input_label.setStyleSheet("color: #E53935; font-weight: 600;")
        perm_card.add_widget(input_label)

        screen_label = QLabel()
        if status["screen_recording"]:
            screen_label.setText("✓ " + _("Screen Recording: Granted"))
            screen_label.setStyleSheet("color: #4CAF50;")
        elif status["screen_recording"] is None:
            screen_label.setText("• " + _("Screen Recording: Unknown"))
            if self._dialog:
                self._dialog._add_themed_widget(screen_label, "QLabel { color: $text_placeholder; }")
        else:
            screen_label.setText("✗ " + _("Screen Recording: Not Granted"))
            screen_label.setStyleSheet("color: #E53935;")
        perm_card.add_widget(screen_label)

        perm_card.add_spacing(8)

        open_perm_btn = QPushButton(_("Open System Settings"))
        open_perm_btn.clicked.connect(self._open_permission_settings)
        perm_card.add_widget(open_perm_btn)

        layout.addWidget(perm_card)

    def _build_startup_card(self, layout: QVBoxLayout) -> None:
        """启动卡片"""
        startup_card = SettingsCard(icon="🚀", title=_("Startup"))
        self._launch_checkbox = ToggleRow(_("Launch at login"))
        startup_card.add_widget(self._launch_checkbox)
        layout.addWidget(startup_card)

    def _on_theme_preview(self) -> None:
        """主题预览"""
        theme_mode = self._theme_combo.currentData()
        if theme_mode:
            logger.info(f"主题预览切换: {theme_mode}")
            _theme.set_mode(theme_mode)
            _theme.apply_to_app(QApplication.instance())
            self._update_accent_btn_style()

    def _on_accent_color_click(self) -> None:
        """选择主题色"""
        current = QColor(_theme.accent_color)
        new_color = get_color(current, self, _("Select Accent Color"))
        if new_color.isValid():
            hex_color = new_color.name()
            if self._dialog:
                self._dialog._settings.accent_color = hex_color
            _theme.set_accent_color(hex_color)
            _theme.apply_to_app(QApplication.instance())
            self._update_accent_btn_style()
            logger.info(f"自定义主题色: {hex_color}")

    def _on_accent_reset(self) -> None:
        """重置主题色"""
        if self._dialog:
            self._dialog._settings.accent_color = ""
        _theme.set_accent_color("")
        _theme.apply_to_app(QApplication.instance())
        self._update_accent_btn_style()
        logger.info("主题色恢复默认")

    def _update_accent_btn_style(self) -> None:
        """更新主题色按钮样式"""
        if not self._accent_btn:
            return
        color = _theme.accent_color
        border = _theme.get("border")
        self._accent_btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border: 2px solid {border};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: {color};
            }}
        """)

    def _open_permission_settings(self) -> None:
        """打开 macOS 系统设置"""
        from ....core.permissions import open_input_monitoring_settings
        open_input_monitoring_settings()
        QMessageBox.information(
            self,
            _("Permission Settings"),
            _("System Settings opened.\n\n"
              "Please enable Input Monitoring and Screen Recording permissions,\n"
              "then restart MySnipaste for changes to take effect.")
        )

    def load_settings(self, settings: AppSettings):
        """加载设置"""
        lang_idx = self._lang_combo.findData(settings.language)
        if lang_idx >= 0:
            self._lang_combo.setCurrentIndex(lang_idx)

        theme_idx = self._theme_combo.findData(settings.theme)
        if theme_idx >= 0:
            self._theme_combo.setCurrentIndex(theme_idx)

        if settings.accent_color:
            _theme.set_accent_color(settings.accent_color)
        self._update_accent_btn_style()

        if self._launch_checkbox:
            self._launch_checkbox.setChecked(settings.launch_at_startup)

    def save_settings(self, settings: AppSettings):
        """保存设置"""
        settings.language = self._lang_combo.currentData() or "zh_CN"
        settings.theme = self._theme_combo.currentData() or "light"

        if self._launch_checkbox:
            settings.launch_at_startup = self._launch_checkbox.isChecked()

    def reset_to_defaults(self):
        """重置为默认值"""
        defaults = AppSettings()
        lidx = self._lang_combo.findData(defaults.language)
        if lidx >= 0:
            self._lang_combo.setCurrentIndex(lidx)
        tidx = self._theme_combo.findData("light")
        if tidx >= 0:
            self._theme_combo.setCurrentIndex(tidx)
        if self._launch_checkbox:
            self._launch_checkbox.setChecked(defaults.launch_at_startup)

        # Reset accent color to default
        if self._dialog:
            self._dialog._settings.accent_color = ""
        _theme.set_accent_color("")
        _theme.apply_to_app(QApplication.instance())
        self._update_accent_btn_style()
