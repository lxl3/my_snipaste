"""共享 QSS 基线 — 集中管理通用 widget 样式，消除各文件重复。

用法:
    from ..core.qss_base import pushbutton_qss, lineedit_qss
    btn.setStyleSheet(pushbutton_qss())
    # 或自定义: pushbutton_qss(padding="4px 12px")
"""

from typing import Optional

from .theme import theme as _theme


# ─── 基础控件 ────────────────────────────────────────


def pushbutton_qss(
    padding: str = "6px 20px",
    border: str = "1px solid $border",
    border_radius: str = "4px",
    bg: str = "$bg_secondary",
    color: str = "$text_primary",
    hover_bg: str = "$hover_bg",
    pressed_bg: str = "$bg_primary",
    font_weight: str = "",
    font_size: str = "",
    selector: str = "QPushButton",
) -> str:
    """通用 QPushButton 样式。

    Args:
        selector: CSS 选择器，默认 "QPushButton"，可用于子选择器如 "QMessageBox QPushButton"
    """
    font_part = ""
    if font_weight or font_size:
        parts = []
        if font_weight:
            parts.append(f"font-weight: {font_weight}")
        if font_size:
            parts.append(f"font-size: {font_size}")
        font_part = "; " + "; ".join(parts)
    return _theme.qss(f"""
        {selector} {{
            padding: {padding};
            border: {border};
            border-radius: {border_radius};
            background: {bg};
            color: {color};{font_part}
        }}
        {selector}:hover {{
            background: {hover_bg};
        }}
        {selector}:pressed {{
            background: {pressed_bg};
        }}
    """)


def lineedit_qss(
    padding: str = "4px 8px",
    border: str = "1px solid $border",
    border_radius: str = "4px",
    bg: str = "$bg_input",
    color: str = "$text_primary",
    focus_border: str = "$accent",
    readonly_bg: str = "$bg_secondary",
    placeholder_color: str = "$text_placeholder",
) -> str:
    """通用 QLineEdit 样式。"""
    return _theme.qss(f"""
        QLineEdit {{
            padding: {padding};
            border: {border};
            border-radius: {border_radius};
            background: {bg};
            color: {color};
        }}
        QLineEdit:focus {{
            border-color: {focus_border};
        }}
        QLineEdit[readOnly="true"] {{
            background: {readonly_bg};
        }}
        QLineEdit::placeholder {{
            color: {placeholder_color};
        }}
    """)


def combobox_qss(
    padding: str = "4px 8px",
    border: str = "1px solid $border",
    border_radius: str = "4px",
    bg: str = "$bg_input",
    color: str = "$text_primary",
    arrow_color: str = "$text_primary",
    menu_bg: str = "$bg_input",
    menu_color: str = "$text_primary",
    menu_selection_bg: str = "$accent",
    menu_selection_color: str = "$text_accent",
) -> str:
    """通用 QComboBox 样式。"""
    return _theme.qss(f"""
        QComboBox {{
            padding: {padding};
            border: {border};
            border-radius: {border_radius};
            background: {bg};
            color: {color};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {arrow_color};
            margin-right: 5px;
        }}
        QComboBox QAbstractItemView {{
            background: {menu_bg};
            color: {menu_color};
            selection-background-color: {menu_selection_bg};
            selection-color: {menu_selection_color};
            border: 1px solid {border};
            outline: none;
        }}
    """)


def spinbox_qss(
    padding: str = "4px",
    border: str = "1px solid $border",
    border_radius: str = "4px",
    bg: str = "$bg_input",
    color: str = "$text_primary",
    arrow_color: str = "$text_primary",
    btn_bg: str = "transparent",
) -> str:
    """通用 QSpinBox 样式。"""
    return _theme.qss(f"""
        QSpinBox {{
            padding: {padding};
            border: {border};
            border-radius: {border_radius};
            background: {bg};
            color: {color};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            border: none;
            background: {btn_bg};
            width: 16px;
        }}
        QSpinBox::up-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {arrow_color};
            margin-bottom: 2px;
        }}
        QSpinBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {arrow_color};
            margin-top: 2px;
        }}
    """)


def checkbox_qss(
    indicator_size: str = "16px",
    border: str = "1px solid $border",
    accent: str = "$accent",
    bg: str = "$bg_input",
    color: str = "$text_primary",
) -> str:
    """通用 QCheckBox 样式。"""
    return _theme.qss(f"""
        QCheckBox {{
            color: {color};
        }}
        QCheckBox::indicator {{
            width: {indicator_size};
            height: {indicator_size};
        }}
        QCheckBox::indicator:unchecked {{
            border: {border};
            border-radius: 3px;
            background: {bg};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {accent};
            border-radius: 3px;
            background: {accent};
        }}
    """)


def groupbox_qss(
    border: str = "1px solid $border",
    border_radius: str = "6px",
    title_color: str = "$text_primary",
    font_weight: str = "600",
) -> str:
    """通用 QGroupBox 样式。"""
    return _theme.qss(f"""
        QGroupBox {{
            font-weight: {font_weight};
            border: {border};
            border-radius: {border_radius};
            margin-top: 12px;
            padding: 16px 12px 12px;
            background: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 4px;
            color: {title_color};
        }}
    """)


def slider_qss(
    groove_height: str = "6px",
    groove_bg: str = "$border",
    handle_size: str = "14px",
    handle_color: str = "$accent",
    border_radius: str = "3px",
) -> str:
    """通用 QSlider（水平）样式。"""
    margin = f"-{(int(handle_size.replace('px', '')) - int(groove_height.replace('px', ''))) // 2}px 0"
    return _theme.qss(f"""
        QSlider::groove:horizontal {{
            height: {groove_height};
            background: {groove_bg};
            border-radius: {border_radius};
        }}
        QSlider::handle:horizontal {{
            background: {handle_color};
            width: {handle_size};
            height: {handle_size};
            margin: {margin};
            border-radius: {int(handle_size.replace('px', '')) // 2}px;
        }}
        QSlider::sub-page:horizontal {{
            background: {handle_color};
            border-radius: {border_radius};
        }}
    """)


def scrollbar_qss(
    width: str = "8px",
    handle_bg: str = "$border",
    handle_hover_bg: str = "$text_placeholder",
    handle_min: str = "30px",
    border_radius: str = "4px",
) -> str:
    """通用 QScrollBar（垂直 + 水平）样式。"""
    return _theme.qss(f"""
        QScrollBar:vertical {{
            width: {width};
            background: transparent;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {handle_bg};
            min-height: {handle_min};
            border-radius: {border_radius};
        }}
        QScrollBar::handle:vertical:hover {{
            background: {handle_hover_bg};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            height: {width};
            background: transparent;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {handle_bg};
            min-width: {handle_min};
            border-radius: {border_radius};
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {handle_hover_bg};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
            border: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """)


def menu_qss(
    bg: str = "$bg_menu",
    border: str = "1px solid $border",
    border_radius: str = "6px",
    item_padding: str = "8px 12px 8px 8px",
    item_color: str = "$text_primary",
    item_border_radius: str = "4px",
    selected_bg: str = "$accent",
    selected_color: str = "$text_accent",
    separator_color: str = "$border",
    separator_margin: str = "6px 10px",
    icon_padding: str = "6px",
) -> str:
    """通用 QMenu 样式（普通弹出菜单）。"""
    return _theme.qss(f"""
        QMenu {{
            background: {bg};
            border: {border};
            border-radius: {border_radius};
            padding: 6px;
        }}
        QMenu::item {{
            padding: {item_padding};
            color: {item_color};
            border-radius: {item_border_radius};
        }}
        QMenu::item:selected {{
            background: {selected_bg};
            color: {selected_color};
        }}
        QMenu::separator {{
            height: 1px;
            background: {separator_color};
            margin: {separator_margin};
        }}
        QMenu::icon {{
            padding-left: {icon_padding};
        }}
    """)


def label_qss(
    color: str = "$text_primary",
    font_size: str = "",
    font_weight: str = "",
) -> str:
    """通用 QLabel 样式。"""
    parts = [f"color: {color}"]
    if font_size:
        parts.append(f"font-size: {font_size}")
    if font_weight:
        parts.append(f"font-weight: {font_weight}")
    return "; ".join(parts) + ";"
