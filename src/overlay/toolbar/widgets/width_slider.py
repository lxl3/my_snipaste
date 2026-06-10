"""样式化宽度滑块 (QSpinBox)"""

from PySide6.QtWidgets import QSpinBox

from .controls import ControlStyles


def make_width_spinbox(
    range_min: int,
    range_max: int,
    value: int,
    width: int = 50,
    on_changed: callable = None,
) -> QSpinBox:
    """创建样式化的宽度 QSpinBox"""
    spinbox = QSpinBox()
    spinbox.setRange(range_min, range_max)
    spinbox.setValue(value)
    spinbox.setFixedWidth(width)
    spinbox.setStyleSheet(ControlStyles().spinbox_qss())
    if on_changed:
        spinbox.valueChanged.connect(on_changed)
    return spinbox
