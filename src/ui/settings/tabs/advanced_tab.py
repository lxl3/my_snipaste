"""高级设置 Tab"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
)

from .base_tab import BaseTab
from ..widgets.no_scroll_combo import NoScrollComboBox
from ...settings_card import SettingsCard
from ....core.i18n import _
from ....core.settings import AppSettings
from ....core import qss_base


class AdvancedTab(BaseTab):
    """高级设置 Tab - Pin 窗口、日志"""

    tab_id = "advanced"
    tab_name = "Advanced"
    tab_icon = "settings"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._opacity_slider = None
        self._opacity_label = None
        self._log_level_combo = None
        super().__init__(parent)

    def _build_ui(self):
        """构建高级设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_pin_card(layout)
        self._build_log_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_pin_card(self, layout: QVBoxLayout) -> None:
        """Pin 窗口卡片"""
        pin_card = SettingsCard(icon="📌", title=_("Pin Window"))

        opacity_row = QHBoxLayout()
        opacity_label_text = QLabel(_("Opacity:"))
        if self._dialog:
            self._dialog._add_themed_widget(opacity_label_text, "QLabel { color: $text_primary; }")
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setStyleSheet(qss_base.slider_qss())
        self._opacity_label = QLabel("100%")
        if self._dialog:
            self._dialog._add_themed_widget(self._opacity_label, "QLabel { color: $text_primary; font-weight: 600; }")
        self._opacity_label.setMinimumWidth(50)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(opacity_label_text)
        opacity_row.addWidget(self._opacity_slider, 1)
        opacity_row.addWidget(self._opacity_label)
        pin_card.add_layout(opacity_row)

        hint_opacity = QLabel(_("Controls the opacity of pinned screenshots"))
        if self._dialog:
            self._dialog._add_themed_widget(hint_opacity, "QLabel { color: $text_placeholder; font-size: 11px; }")
        pin_card.add_widget(hint_opacity)

        layout.addWidget(pin_card)

    def _build_log_card(self, layout: QVBoxLayout) -> None:
        """日志卡片"""
        log_card = SettingsCard(icon="📋", title=_("Logging"))

        log_row = QHBoxLayout()
        log_label = QLabel(_("Log Level:"))
        if self._dialog:
            self._dialog._add_themed_widget(log_label, "QLabel { color: $text_primary; }")
        self._log_level_combo = NoScrollComboBox()
        self._log_level_combo.setMinimumWidth(150)
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_row.addWidget(log_label)
        log_row.addStretch()
        log_row.addWidget(self._log_level_combo)
        log_card.add_layout(log_row)

        hint_log = QLabel(_("Higher levels show fewer messages"))
        if self._dialog:
            self._dialog._add_themed_widget(hint_log, "QLabel { color: $text_placeholder; font-size: 11px; }")
        log_card.add_widget(hint_log)

        layout.addWidget(log_card)

    def load_settings(self, settings: AppSettings):
        """加载设置"""
        self._opacity_slider.setValue(settings.pin_window_opacity)
        log_idx = self._log_level_combo.findText(settings.log_level)
        if log_idx >= 0:
            self._log_level_combo.setCurrentIndex(log_idx)

    def save_settings(self, settings: AppSettings):
        """保存设置"""
        settings.pin_window_opacity = self._opacity_slider.value()
        settings.log_level = self._log_level_combo.currentText()

        from ....core.logger import apply_log_level
        apply_log_level(settings.log_level)

    def reset_to_defaults(self):
        """重置为默认值"""
        defaults = AppSettings()
        self._opacity_slider.setValue(defaults.pin_window_opacity)
        lidx = self._log_level_combo.findText(defaults.log_level)
        if lidx >= 0:
            self._log_level_combo.setCurrentIndex(lidx)
