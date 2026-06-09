"""快捷键设置 Tab"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)

from .base_tab import BaseTab
from ..widgets.hotkey_recorder import HotkeyRecorderWidget
from ...settings_card import SettingsCard
from ....core.i18n import _
from ....core.settings import AppSettings


class HotkeysTab(BaseTab):
    """快捷键设置 Tab - 全局快捷键、编辑器工具快捷键"""

    tab_id = "hotkeys"
    tab_name = "Shortcuts"
    tab_icon = "keyboard"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._shortcut_widgets: dict[str, HotkeyRecorderWidget] = {}
        super().__init__(parent)

    def _build_ui(self):
        """构建快捷键设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_global_shortcuts_card(layout)
        self._build_editor_shortcuts_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_global_shortcuts_card(self, layout: QVBoxLayout) -> None:
        """全局快捷键卡片"""
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
            hotkey_row = QVBoxLayout()
            hotkey_row.setSpacing(4)

            row = QHBoxLayout()
            row.setSpacing(8)
            label_widget = QLabel(label + ":")
            if self._dialog:
                self._dialog._add_themed_widget(label_widget, "QLabel { color: $text_primary; font-size: 13px; }")
            label_widget.setMinimumWidth(150)
            rec = HotkeyRecorderWidget()
            self._shortcut_widgets[key] = rec
            row.addWidget(label_widget)
            row.addWidget(rec, 1)
            hotkey_row.addLayout(row)

            warn = QLabel("")
            if self._dialog:
                self._dialog._add_themed_widget(warn, "QLabel { color: $hotkey_conflict; font-size: 11px; }")
            warn.setVisible(False)
            hotkey_row.addWidget(warn)

            global_card.add_layout(hotkey_row)

        layout.addWidget(global_card)

    def _build_editor_shortcuts_card(self, layout: QVBoxLayout) -> None:
        """编辑器工具快捷键卡片"""
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
            hotkey_row = QHBoxLayout()
            hotkey_row.setSpacing(8)
            label_widget = QLabel(label + ":")
            if self._dialog:
                self._dialog._add_themed_widget(label_widget, "QLabel { color: $text_primary; font-size: 13px; }")
            label_widget.setMinimumWidth(150)
            rec = HotkeyRecorderWidget()
            self._shortcut_widgets[key] = rec
            hotkey_row.addWidget(label_widget)
            hotkey_row.addWidget(rec, 1)
            editor_card.add_layout(hotkey_row)

        layout.addWidget(editor_card)

    def get_shortcut_widgets(self) -> dict[str, HotkeyRecorderWidget]:
        """获取所有快捷键控件"""
        return self._shortcut_widgets

    def load_settings(self, settings: AppSettings):
        """加载设置"""
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
                widget.set_hotkey(getattr(settings, setting_attr, ""))

    def save_settings(self, settings: AppSettings):
        """保存设置"""
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
        for widget_key, setting_attr in shortcut_save_map.items():
            widget = self._shortcut_widgets.get(widget_key)
            if widget:
                val = widget.get_hotkey().strip().lower()
                setattr(settings, setting_attr, val)

    def reset_to_defaults(self):
        """重置为默认值"""
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

    def check_conflicts(self) -> list[str]:
        """检查快捷键冲突"""
        seen_values: dict[str, str] = {}
        conflicts: list[str] = []
        for widget_key, widget in self._shortcut_widgets.items():
            val = widget.get_hotkey().strip().lower()
            if val:
                if val in seen_values:
                    conflicts.append(f"'{widget_key}' and '{seen_values[val]}' both use '{val}'")
                else:
                    seen_values[val] = widget_key
        return conflicts
