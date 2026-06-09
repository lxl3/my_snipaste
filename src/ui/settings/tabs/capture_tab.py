"""截图设置 Tab"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QFileDialog
)

from .base_tab import BaseTab
from ..widgets.no_scroll_combo import NoScrollComboBox
from ...settings_card import SettingsCard
from ...toggle_switch import ToggleRow
from ....core.i18n import _
from ....core.settings import AppSettings


class CaptureTab(BaseTab):
    """截图设置 Tab - 自动保存、截图行为"""

    tab_id = "capture"
    tab_name = "Capture"
    tab_icon = "camera"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._auto_save_checkbox = None
        self._save_dir_input = None
        self._format_combo = None
        self._sound_checkbox = None
        self._cursor_checkbox = None
        self._delay_spin = None
        self._after_action_combo = None
        super().__init__(parent)

    def _build_ui(self):
        """构建截图设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_save_card(layout)
        self._build_behavior_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_save_card(self, layout: QVBoxLayout) -> None:
        """自动保存卡片"""
        save_card = SettingsCard(icon="💾", title=_("Auto Save"))

        self._auto_save_checkbox = ToggleRow(_("Auto save to directory"))
        self._auto_save_checkbox.toggled.connect(self._on_auto_save_toggle)
        save_card.add_widget(self._auto_save_checkbox)

        save_card.add_spacing(8)

        dir_row = QHBoxLayout()
        dir_label = QLabel(_("Directory:"))
        if self._dialog:
            self._dialog._add_themed_widget(dir_label, "QLabel { color: $text_primary; }")
        self._save_dir_input = QLineEdit()
        self._save_dir_input.setReadOnly(True)
        self._save_dir_input.setPlaceholderText(_("Select default save directory..."))
        browse_btn = QPushButton(_("Browse..."))
        browse_btn.clicked.connect(self._browse_save_dir)
        dir_row.addWidget(dir_label)
        dir_row.addWidget(self._save_dir_input, 1)
        dir_row.addWidget(browse_btn)
        save_card.add_layout(dir_row)

        format_row = QHBoxLayout()
        format_label = QLabel(_("Format:"))
        if self._dialog:
            self._dialog._add_themed_widget(format_label, "QLabel { color: $text_primary; }")
        self._format_combo = NoScrollComboBox()
        self._format_combo.setMinimumWidth(120)
        self._format_combo.addItems(["PNG", "JPEG"])
        format_row.addWidget(format_label)
        format_row.addStretch()
        format_row.addWidget(self._format_combo)
        save_card.add_layout(format_row)

        layout.addWidget(save_card)

    def _build_behavior_card(self, layout: QVBoxLayout) -> None:
        """截图行为卡片"""
        behavior_card = SettingsCard(icon="🎯", title=_("Capture Behavior"))

        self._sound_checkbox = ToggleRow(_("Play sound when capturing"))
        behavior_card.add_widget(self._sound_checkbox)

        self._cursor_checkbox = ToggleRow(_("Include mouse cursor"))
        behavior_card.add_widget(self._cursor_checkbox)

        behavior_card.add_spacing(8)

        delay_row = QHBoxLayout()
        delay_label = QLabel(_("Capture delay:"))
        if self._dialog:
            self._dialog._add_themed_widget(delay_label, "QLabel { color: $text_primary; }")
        self._delay_spin = QSpinBox()
        self._delay_spin.setRange(0, 10)
        self._delay_spin.setSuffix(_(" seconds"))
        self._delay_spin.setMinimumWidth(120)
        delay_row.addWidget(delay_label)
        delay_row.addStretch()
        delay_row.addWidget(self._delay_spin)
        behavior_card.add_layout(delay_row)

        after_row = QHBoxLayout()
        after_label = QLabel(_("After capture:"))
        if self._dialog:
            self._dialog._add_themed_widget(after_label, "QLabel { color: $text_primary; }")
        self._after_action_combo = NoScrollComboBox()
        self._after_action_combo.setMinimumWidth(180)
        self._after_action_combo.addItem(_("None (show editor)"), "none")
        self._after_action_combo.addItem(_("Auto copy to clipboard"), "copy")
        self._after_action_combo.addItem(_("Auto save to file"), "save")
        after_row.addWidget(after_label)
        after_row.addStretch()
        after_row.addWidget(self._after_action_combo)
        behavior_card.add_layout(after_row)

        layout.addWidget(behavior_card)

    def _browse_save_dir(self) -> None:
        """打开目录选择对话框"""
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
        """切换自动保存"""
        self._save_dir_input.setEnabled(checked)

    def load_settings(self, settings: AppSettings):
        """加载设置"""
        self._save_dir_input.setText(settings.auto_save_dir)
        fmt_idx = self._format_combo.findText(settings.auto_save_format.upper())
        if fmt_idx >= 0:
            self._format_combo.setCurrentIndex(fmt_idx)
        self._auto_save_checkbox.setChecked(bool(settings.auto_save_dir))

        self._sound_checkbox.setChecked(settings.capture_sound)
        self._cursor_checkbox.setChecked(settings.capture_cursor)
        self._delay_spin.setValue(settings.capture_delay)
        after_idx = self._after_action_combo.findData(settings.capture_after_action)
        if after_idx >= 0:
            self._after_action_combo.setCurrentIndex(after_idx)

    def save_settings(self, settings: AppSettings):
        """保存设置"""
        if self._auto_save_checkbox.isChecked():
            settings.auto_save_dir = self._save_dir_input.text().strip()
        else:
            settings.auto_save_dir = ""
        settings.auto_save_format = self._format_combo.currentText().lower()

        settings.capture_sound = self._sound_checkbox.isChecked()
        settings.capture_cursor = self._cursor_checkbox.isChecked()
        settings.capture_delay = self._delay_spin.value()
        settings.capture_after_action = self._after_action_combo.currentData()

    def reset_to_defaults(self):
        """重置为默认值"""
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
