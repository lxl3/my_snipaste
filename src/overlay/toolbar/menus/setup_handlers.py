"""菜单 aboutToShow 状态同步回调

每个 handler 签名: fn(overlay, menu, btn, tool_ids, extra)
从 legacy.py 各 _build_*_menu 方法的 aboutToShow 回调提取。

extra 是一个 dict，由 OverlayToolbar 在注册时提供，包含各菜单需要
的额外控件引用（如 arrow_style_combo、zoom_spinbox 等）。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QPushButton, QMenu

from ....core.theme import theme as _t


# ─── 工具状态同步 ───

def select_tool(overlay, tool_id: str, btn=None, icon_name: str | None = None) -> None:
    """选择工具并更新按钮状态（图标在构建时已设置，不需重载）"""
    overlay._on_tool_selected(tool_id)
    if btn:
        btn.setChecked(True)
    if tool_id == "text":
        overlay.setCursor(Qt.IBeamCursor)
    else:
        overlay.setCursor(Qt.CrossCursor)


def update_submenu_check_state(menu: QMenu, selected_tool: str) -> None:
    """更新子菜单内工具按钮的 check 状态"""
    for action in menu.actions():
        widget = action.defaultWidget()
        if widget:
            for child in widget.findChildren(QToolButton):
                tool_type = child.property("tool_type")
                if tool_type:
                    child.setChecked(tool_type == selected_tool)


def update_submenu_color_borders(menu: QMenu, overlay) -> None:
    """更新子菜单内颜色按钮边框"""
    current = overlay.current_color
    if not current:
        return
    current_hex = current.name().lower()
    for action in menu.actions():
        widget = action.defaultWidget()
        if widget:
            for child in widget.findChildren(QPushButton):
                c = child.property("color")
                if not c:
                    continue
                is_current = c.lower() == current_hex
                border = _t.qss("2px solid $color_btn_border_on") if is_current else _t.qss("1px solid $color_btn_border")
                child.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")


def update_submenu_state(menu: QMenu, tool_ids: list[str], overlay) -> None:
    """更新子菜单状态（工具按钮勾选 + 颜色按钮边框）"""
    if overlay.current_tool in tool_ids:
        update_submenu_check_state(menu, overlay.current_tool)
    update_submenu_color_borders(menu, overlay)


# ─── 菜单 Setup Handlers ───

def shape_setup(overlay, menu, btn, tool_ids, extra=None):
    """形状菜单弹出前状态同步"""
    if overlay.current_tool not in tool_ids:
        select_tool(overlay, "rect", btn, "rectangle")
    update_submenu_state(menu, tool_ids, overlay)


def arrow_setup(overlay, menu, btn, tool_ids, extra=None):
    """箭头菜单弹出前状态同步（含样式下拉框同步）"""
    if overlay.current_tool not in tool_ids:
        select_tool(overlay, "arrow", btn, "arrow")
    update_submenu_state(menu, tool_ids, overlay)

    arrow_combo = (extra or {}).get("arrow_style_combo")
    if arrow_combo:
        idx = getattr(overlay, '_selected_annotation_idx', None)
        if idx is not None and 0 <= idx < len(overlay.annotations):
            ann = overlay.annotations[idx]
            if ann.get("type") == "arrow":
                saved = ann.get("arrow_style", "solid")
                if saved in ("solid", "hollow", "solid_tail", "hollow_tail"):
                    overlay.current_arrow_style = saved

        current_style = overlay.current_arrow_style
        for i in range(arrow_combo.count()):
            if arrow_combo.itemData(i) == current_style:
                arrow_combo.setCurrentIndex(i)
                break


def pen_setup(overlay, menu, btn, tool_ids, extra=None):
    """画笔菜单弹出前状态同步"""
    select_tool(overlay, "freehand")


def highlighter_setup(overlay, menu, btn, tool_ids, extra=None):
    """高亮笔菜单弹出前状态同步"""
    if overlay.current_tool not in tool_ids:
        select_tool(overlay, "highlighter", btn, "highlighter")
    update_submenu_state(menu, tool_ids, overlay)


def mosaic_setup(overlay, menu, btn, tool_ids, extra=None):
    """马赛克菜单弹出前状态同步（含 blur/mosaic 控件显隐）"""
    if overlay.current_tool not in tool_ids:
        select_tool(overlay, "mosaic", btn, "mosaic")
    update_submenu_state(menu, tool_ids, overlay)

    blur_group = extra.get("blur_group") if extra else None
    mosaic_group = extra.get("mosaic_group") if extra else None
    is_blur = overlay.current_tool == "blur"
    if blur_group:
        blur_group.setVisible(is_blur)
    if mosaic_group:
        mosaic_group.setVisible(not is_blur)


def magnifier_setup(overlay, menu, btn, tool_ids, extra=None):
    """放大镜菜单弹出前状态同步"""
    if overlay.current_tool != "magnifier":
        select_tool(overlay, "magnifier", btn, "magnifier")
    zoom_spinbox = (extra or {}).get("zoom_spinbox")
    if zoom_spinbox:
        zoom_spinbox.setValue(overlay.current_magnifier_zoom)


def text_setup(overlay, menu, btn, tool_ids, extra=None):
    """文字菜单弹出前状态同步"""
    if overlay.current_tool != "text":
        select_tool(overlay, "text")


def eraser_setup(overlay, menu, btn, tool_ids, extra=None):
    """橡皮擦菜单弹出前状态同步"""
    if overlay.current_tool not in tool_ids:
        select_tool(overlay, "eraser_dot", btn, "eraser_dot")
    update_submenu_state(menu, tool_ids, overlay)
