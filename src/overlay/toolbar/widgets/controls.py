"""通用控件工具 - 分隔符、取色器按钮、样式化 ComboBox/SpinBox"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QPushButton, QHBoxLayout, QComboBox, QSpinBox,
)

from ....core.theme import theme as _t
from ....core import qss_base


class ControlStyles:
    """生成工具栏子菜单控件的样式表（QComboBox/QSpinBox/QPushButton/QLabel）"""

    def __init__(self):
        is_dark = _t.is_dark()

        if is_dark:
            self.bg = "rgba(255,255,255,0.08)"
            self.bg_hover = "rgba(255,255,255,0.12)"
            self.border = "rgba(255,255,255,0.15)"
            self.border_focus = "rgba(32,127,240,0.6)"
            self.text_color = "#EEEEEE"
            self.button_bg = "rgba(255,255,255,0.12)"
            self.button_hover_bg = "rgba(255,255,255,0.18)"
            self.arrow_color = "#EEEEEE"
        else:
            self.bg = "rgba(0,0,0,0.04)"
            self.bg_hover = "rgba(0,0,0,0.08)"
            self.border = "rgba(0,0,0,0.15)"
            self.border_focus = "rgba(32,127,240,0.6)"
            self.text_color = "#222222"
            self.button_bg = "rgba(0,0,0,0.08)"
            self.button_hover_bg = "rgba(0,0,0,0.12)"
            self.arrow_color = "#333333"

    def label_qss(self) -> str:
        return f"QLabel {{ {qss_base.label_qss(color=self.text_color, font_size='12px')} }}"

    def combo_qss(self) -> str:
        return _t.qss(f"""
        QComboBox {{
            color: {self.text_color}; background: {self.bg};
            border: 1px solid {self.border}; border-radius: 2px;
            padding: 2px 4px; min-height: 16px; font-size: 12px;
        }}
        QComboBox:hover {{ background: {self.bg_hover}; border: 1px solid {self.border_focus}; }}
        QComboBox:focus {{ border: 1px solid {self.border_focus}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {self.arrow_color};
            margin-right: 4px;
        }}
        QComboBox QAbstractItemView {{
            background: $bg_menu; color: $text_primary;
            border: 1px solid {self.border};
            selection-background-color: $accent;
            selection-color: $text_accent; outline: none;
        }}
        """)

    def spinbox_qss(self) -> str:
        return _t.qss(f"""
        QSpinBox {{
            color: {self.text_color}; background: {self.bg};
            border: 1px solid {self.border}; border-radius: 2px;
            padding: 2px 4px; min-height: 16px; font-size: 12px;
        }}
        QSpinBox:hover {{ background: {self.bg_hover}; border: 1px solid {self.border_focus}; }}
        QSpinBox:focus {{ border: 1px solid {self.border_focus}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background: {self.button_bg}; border: none; width: 18px;
            border-radius: 3px; margin: 1px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background: {self.button_hover_bg};
        }}
        QSpinBox::up-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {self.arrow_color};
            margin-bottom: 1px;
        }}
        QSpinBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {self.arrow_color};
            margin-top: 1px;
        }}
        """)


def add_separator(layout: QHBoxLayout) -> None:
    """添加竖直分隔线"""
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setStyleSheet(_t.qss("color: $border_light;"))
    sep.setFixedWidth(1)
    layout.addWidget(sep)


def make_color_picker_btn(on_click: callable) -> QPushButton:
    """创建取色器按钮（🎨）"""
    btn = QPushButton("🎨")
    btn.setFixedSize(20, 20)
    btn.setStyleSheet(_t.qss(
        "QPushButton { border: 1px solid $border; background: transparent; font-size: 12px; }"
        "QPushButton:hover { background: $hover_bg; }"
    ))
    btn.clicked.connect(on_click)
    return btn


def make_styled_combo(
    width: int = 85,
    style_items: list[tuple] = None,
    on_changed: callable = None,
) -> QComboBox:
    """创建样式化的 QComboBox

    style_items: [(data, icon_name, label), ...]
    """
    combo = QComboBox()
    combo.setFixedWidth(width)
    combo.setStyleSheet(ControlStyles().combo_qss())

    if style_items:
        for data, icon_name, label in style_items:
            combo.addItem(label, data)

    if on_changed:
        combo.currentIndexChanged.connect(on_changed)

    return combo


def make_styled_spinbox(
    range_min: int,
    range_max: int,
    value: int,
    width: int = 50,
    on_changed: callable = None,
) -> QSpinBox:
    """创建样式化的 QSpinBox"""
    spinbox = QSpinBox()
    spinbox.setRange(range_min, range_max)
    spinbox.setValue(value)
    spinbox.setFixedWidth(width)
    spinbox.setStyleSheet(ControlStyles().spinbox_qss())
    if on_changed:
        spinbox.valueChanged.connect(on_changed)
    return spinbox
