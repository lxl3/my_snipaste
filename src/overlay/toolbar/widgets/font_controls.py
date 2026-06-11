"""字体控件 - 字体选择、字号、加粗/斜体"""

from PySide6.QtWidgets import QPushButton, QComboBox, QSpinBox, QHBoxLayout

from ....core.theme_pkg import theme as _t
from ....core import qss_base


def make_font_combo(
    current_font: str = "Segoe UI",
    width: int = 100,
    families: list[str] = None,
    on_changed: callable = None,
) -> QComboBox:
    """创建字体选择下拉框"""
    combo = QComboBox()
    combo.addItems(families or ["Segoe UI", "Arial", "微软雅黑", "宋体", "黑体", "楷体"])
    combo.setCurrentText(current_font)
    combo.setFixedWidth(width)
    combo.setStyleSheet(qss_base.combobox_qss(
        bg="$bg_toolbar_alt", padding="3px 6px", border_radius="3px",
        font_size="12px",
    ))
    if on_changed:
        combo.currentTextChanged.connect(on_changed)
    return combo


def make_font_size_spinbox(
    current_size: int = 24,
    range_min: int = 8,
    range_max: int = 72,
    width: int = 50,
    on_changed: callable = None,
) -> QSpinBox:
    """创建字号调节 SpinBox"""
    spinbox = QSpinBox()
    spinbox.setRange(range_min, range_max)
    spinbox.setValue(current_size)
    spinbox.setFixedWidth(width)
    spinbox.setStyleSheet(qss_base.spinbox_qss(
        bg="$bg_toolbar_alt", border_radius="3px",
        color="$text_primary", arrow_color="$text_primary",
    ))
    if on_changed:
        spinbox.valueChanged.connect(on_changed)
    return spinbox


def make_bold_button(
    checked: bool = False,
    on_toggled: callable = None,
) -> QPushButton:
    """创建加粗按钮 (B)"""
    btn = QPushButton("B")
    btn.setFixedSize(20, 20)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setStyleSheet(_t.qss(
        "QPushButton { font-weight: bold; border: 1px solid $border; background: transparent; }"
        "QPushButton:hover { background: $hover_bg; }"
        "QPushButton:checked { background: rgba(32,127,240,0.10); color: $accent; border: 1px solid $accent; }"
    ))
    if on_toggled:
        btn.clicked.connect(on_toggled)
    return btn


def make_italic_button(
    checked: bool = False,
    on_toggled: callable = None,
) -> QPushButton:
    """创建斜体按钮 (I)"""
    btn = QPushButton("I")
    btn.setFixedSize(20, 20)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setStyleSheet(_t.qss(
        "QPushButton { font-style: italic; border: 1px solid $border; background: transparent; }"
        "QPushButton:hover { background: $hover_bg; }"
        "QPushButton:checked { background: rgba(32,127,240,0.10); color: $accent; border: 1px solid $accent; }"
    ))
    if on_toggled:
        btn.clicked.connect(on_toggled)
    return btn


def add_font_controls_to_layout(
    layout: QHBoxLayout,
    font_family: str = "Segoe UI",
    font_size: int = 24,
    bold: bool = False,
    italic: bool = False,
    on_font_changed: callable = None,
    on_size_changed: callable = None,
    on_bold_toggled: callable = None,
    on_italic_toggled: callable = None,
) -> dict:
    """一次性添加所有字体控件到布局，返回控件字典"""
    font_combo = make_font_combo(
        current_font=font_family,
        on_changed=on_font_changed,
    )
    layout.addWidget(font_combo)

    size_spinbox = make_font_size_spinbox(
        current_size=font_size,
        on_changed=on_size_changed,
    )
    layout.addWidget(size_spinbox)

    bold_btn = make_bold_button(
        checked=bold,
        on_toggled=on_bold_toggled,
    )
    layout.addWidget(bold_btn)

    italic_btn = make_italic_button(
        checked=italic,
        on_toggled=on_italic_toggled,
    )
    layout.addWidget(italic_btn)

    return {
        "font_combo": font_combo,
        "size_spinbox": size_spinbox,
        "bold_btn": bold_btn,
        "italic_btn": italic_btn,
    }
