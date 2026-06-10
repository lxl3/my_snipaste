"""带标签的 SpinBox 分组（用于模糊/马赛克/放大镜等）"""

from PySide6.QtWidgets import QLabel, QSpinBox, QWidget, QHBoxLayout

from ....core.theme import theme as _t
from ....core.i18n import _
from .controls import ControlStyles


def add_spinbox_group_to_layout(
    layout: QHBoxLayout,
    label: str,
    range_min: int,
    range_max: int,
    value: int,
    width: int = 45,
    on_changed: callable = None,
) -> QSpinBox:
    """添加 标签 + SpinBox 组合到布局，返回创建的 SpinBox"""
    group = QWidget()
    group_layout = QHBoxLayout(group)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(2)

    label_widget = QLabel(_(label))
    label_widget.setStyleSheet(ControlStyles().label_qss())
    group_layout.addWidget(label_widget)

    spinbox = QSpinBox()
    spinbox.setRange(range_min, range_max)
    spinbox.setValue(value)
    spinbox.setFixedWidth(width)
    spinbox.setStyleSheet(ControlStyles().spinbox_qss())
    if on_changed:
        spinbox.valueChanged.connect(on_changed)
    group_layout.addWidget(spinbox)

    layout.addWidget(group)
    return spinbox
