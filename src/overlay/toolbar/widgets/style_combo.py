"""样式化 QComboBox"""

from PySide6.QtWidgets import QComboBox

from .controls import ControlStyles


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
