"""取色器按钮"""

from PySide6.QtWidgets import QPushButton

from ....core.theme_pkg import theme as _t


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
