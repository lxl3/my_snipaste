"""通用控件工具 - 样式表生成 / 分隔符"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout

from ....core.theme_pkg import theme as _t
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
