"""颜色按钮控件"""

from PySide6.QtWidgets import QPushButton, QHBoxLayout

from ....core.theme import theme as _t


def make_color_button(color: str, is_recent: bool, current_color: str = "") -> QPushButton:
    """创建单个颜色按钮，根据是否选中显示不同边框"""
    if not isinstance(color, str):
        color = "#000000"
    btn = QPushButton()
    btn.setFixedSize(18, 18)
    btn.setProperty("color", color)

    is_current = current_color and color.lower() == current_color.lower()
    if is_current:
        border = _t.qss("2px solid $color_btn_border_on")
    elif is_recent:
        border = _t.qss("1px solid $color_btn_recent_border")
    else:
        border = _t.qss("1px solid $color_btn_border")

    btn.setStyleSheet(f"background: {color}; border: {border}; border-radius: 3px;")
    return btn


def add_color_buttons_to_layout(
    layout: QHBoxLayout,
    colors: list[str] | list[list[str]],
    target: str,
    current_color: str,
    on_color_selected: callable,
    include_picker: bool = True,
    recent_colors: list[str] | None = None,
) -> list[QPushButton]:
    """添加颜色预设按钮（含最近颜色和取色器）到布局
    支持一维（单行）或二维（多行）颜色数组。
    返回创建的按钮列表。
    """
    buttons = []
    rc = recent_colors or []

    # 最近颜色（最多3个）— 过滤非字符串脏数据
    for color in rc[:3]:
        if not isinstance(color, str):
            continue
        btn = make_color_button(color, is_recent=True, current_color=current_color)
        btn.clicked.connect(lambda checked, c=color: on_color_selected(c))
        layout.addWidget(btn)
        buttons.append(btn)

    if rc:
        from .controls import add_separator
        add_separator(layout)

    # 扁平化 2D -> 1D，使二维颜色列表也能正常渲染
    flat_colors: list[str] = []
    for c in colors:
        if isinstance(c, list):
            flat_colors.extend(c)
        else:
            flat_colors.append(c)

    # 预设颜色
    for color in flat_colors:
        btn = make_color_button(color, is_recent=False, current_color=current_color)
        btn.clicked.connect(lambda checked, c=color: on_color_selected(c))
        layout.addWidget(btn)
        buttons.append(btn)

    return buttons


def update_color_button_borders(buttons: list[QPushButton], current_color: str) -> None:
    """刷新颜色按钮边框"""
    if not current_color:
        return
    for btn in buttons:
        c = btn.property("color")
        if not c:
            continue
        is_current = c.lower() == current_color.lower()
        border = _t.qss("2px solid $color_btn_border_on") if is_current else _t.qss("1px solid $color_btn_border")
        btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")
