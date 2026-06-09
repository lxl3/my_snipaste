"""标注设置 Tab"""
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox
)

from .base_tab import BaseTab
from ..widgets.no_scroll_combo import NoScrollComboBox
from ...settings_card import SettingsCard
from ...color_picker import get_color
from ....core.i18n import _
from ....core.settings import AppSettings
from ....core.constants import PRESET_COLORS
from ....core.logger import setup_logger

logger = setup_logger("annotation_tab")


class AnnotationTab(BaseTab):
    """标注设置 Tab - 颜色、线宽、字体"""

    tab_id = "annotation"
    tab_name = "Annotation"
    tab_icon = "pen"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._color_combo = None
        self._width_spin = None
        self._font_combo = None
        self._font_size_spin = None
        super().__init__(parent)

    def _build_ui(self):
        """构建标注设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_style_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_style_card(self, layout: QVBoxLayout) -> None:
        """默认标注样式卡片"""
        style_card = SettingsCard(icon="🎨", title=_("Default Annotation Style"))

        color_row_layout = QHBoxLayout()
        color_label = QLabel(_("Color:"))
        if self._dialog:
            self._dialog._add_themed_widget(color_label, "QLabel { color: $text_primary; }")
        self._color_combo = NoScrollComboBox()
        self._color_combo.setMinimumWidth(150)
        for c in PRESET_COLORS:
            pix = QPixmap(16, 16)
            pix.fill(QColor(c))
            self._color_combo.addItem(f"  {c}", c)
            self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
        custom_color_btn = QPushButton(_("Custom..."))
        custom_color_btn.clicked.connect(self._pick_custom_color)
        color_row_layout.addWidget(color_label)
        color_row_layout.addStretch()
        color_row_layout.addWidget(self._color_combo)
        color_row_layout.addWidget(custom_color_btn)
        style_card.add_layout(color_row_layout)

        width_row = QHBoxLayout()
        width_label = QLabel(_("Line Width:"))
        if self._dialog:
            self._dialog._add_themed_widget(width_label, "QLabel { color: $text_primary; }")
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setMinimumWidth(100)
        width_row.addWidget(width_label)
        width_row.addStretch()
        width_row.addWidget(self._width_spin)
        style_card.add_layout(width_row)

        font_row = QHBoxLayout()
        font_label = QLabel(_("Font:"))
        if self._dialog:
            self._dialog._add_themed_widget(font_label, "QLabel { color: $text_primary; }")
        self._font_combo = NoScrollComboBox()
        self._font_combo.setMinimumWidth(180)
        self._font_combo.addItems(["Segoe UI", "Arial", "Helvetica", "PingFang SC", "Microsoft YaHei"])
        self._font_combo.setEditable(True)
        font_row.addWidget(font_label)
        font_row.addStretch()
        font_row.addWidget(self._font_combo)
        style_card.add_layout(font_row)

        font_size_row = QHBoxLayout()
        font_size_label = QLabel(_("Font Size:"))
        if self._dialog:
            self._dialog._add_themed_widget(font_size_label, "QLabel { color: $text_primary; }")
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 72)
        self._font_size_spin.setMinimumWidth(100)
        font_size_row.addWidget(font_size_label)
        font_size_row.addStretch()
        font_size_row.addWidget(self._font_size_spin)
        style_card.add_layout(font_size_row)

        layout.addWidget(style_card)

    def _pick_custom_color(self) -> None:
        """打开颜色选择器选择自定义颜色"""
        current_color = QColor(self._color_combo.currentData() or PRESET_COLORS[0])
        color = get_color(current_color, self, _("Select Custom Color"))

        if color.isValid():
            hex_color = color.name()
            existing_idx = self._color_combo.findData(hex_color)

            if existing_idx >= 0:
                self._color_combo.setCurrentIndex(existing_idx)
            else:
                pix = QPixmap(16, 16)
                pix.fill(color)
                self._color_combo.addItem(f"  {hex_color} (custom)", hex_color)
                self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
                self._color_combo.setCurrentIndex(self._color_combo.count() - 1)

            logger.debug(f"Custom color selected: {hex_color}")

    def load_settings(self, settings: AppSettings):
        """加载设置"""
        idx = self._color_combo.findData(settings.default_color)
        if idx >= 0:
            self._color_combo.setCurrentIndex(idx)
        else:
            if settings.default_color:
                pix = QPixmap(16, 16)
                pix.fill(QColor(settings.default_color))
                self._color_combo.addItem(f"  {settings.default_color} (custom)", settings.default_color)
                self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
                self._color_combo.setCurrentIndex(self._color_combo.count() - 1)
        self._width_spin.setValue(settings.default_line_width)
        self._font_combo.setCurrentText(settings.default_font_family)
        self._font_size_spin.setValue(settings.default_font_size)

    def save_settings(self, settings: AppSettings):
        """保存设置"""
        new_color = self._color_combo.currentData() or PRESET_COLORS[0]
        new_width = self._width_spin.value()
        new_font_family = self._font_combo.currentText()
        new_font_size = self._font_size_spin.value()

        if (new_color != settings.default_color or new_width != settings.default_line_width or
            new_font_family != settings.default_font_family or new_font_size != settings.default_font_size):
            settings.tool_settings = {}
            logger.info("标注默认设置已更改，清除工具记忆")

        settings.default_color = new_color
        settings.default_line_width = new_width
        settings.default_font_family = new_font_family
        settings.default_font_size = new_font_size

    def reset_to_defaults(self):
        """重置为默认值"""
        defaults = AppSettings()
        cidx = self._color_combo.findData(defaults.default_color)
        if cidx >= 0:
            self._color_combo.setCurrentIndex(cidx)
        self._width_spin.setValue(defaults.default_line_width)
        self._font_combo.setCurrentText(defaults.default_font_family)
        self._font_size_spin.setValue(defaults.default_font_size)
