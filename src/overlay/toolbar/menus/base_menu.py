"""菜单 aboutToShow 状态同步基类

每个菜单子类实现 setup() 方法，在菜单弹出前同步工具状态和颜色/样式控件。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QPushButton, QMenu, QWidget

from ....core.theme import theme as _t


class MenuHandler:
    """菜单状态同步基类

    在 builder 构建完成后，通过 register_menu_setup() 注册到对应菜单。
    子类重写 setup() 方法实现特定菜单的状态同步逻辑。
    """

    def __init__(self, overlay) -> None:
        self.overlay = overlay

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        """菜单弹出前状态同步（子类重写）"""
        raise NotImplementedError

    # ─── 通用工具方法 ───

    def select_tool(self, tool_id: str, btn=None, icon_name: str | None = None) -> None:
        """选择工具并更新按钮状态"""
        self.overlay._on_tool_selected(tool_id)
        if btn:
            btn.setChecked(True)
        if tool_id == "text":
            self.overlay.setCursor(Qt.IBeamCursor)
        else:
            self.overlay.setCursor(Qt.CrossCursor)

    def update_check_state(self, menu: QMenu, selected_tool: str) -> None:
        """更新子菜单内工具按钮的 check 状态"""
        for action in menu.actions():
            widget = action.defaultWidget()
            if widget:
                for child in widget.findChildren(QToolButton):
                    tool_type = child.property("tool_type")
                    if tool_type:
                        child.setChecked(tool_type == selected_tool)

    def update_color_borders(self, menu: QMenu) -> None:
        """更新子菜单内颜色按钮边框"""
        current = self.overlay.current_color
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
                    border = (_t.qss("2px solid $color_btn_border_on")
                              if is_current else _t.qss("1px solid $color_btn_border"))
                    child.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")

    def update_submenu_state(self, menu: QMenu, tool_ids: list[str]) -> None:
        """更新子菜单状态（工具按钮勾选 + 颜色按钮边框）"""
        if self.overlay.current_tool in tool_ids:
            self.update_check_state(menu, self.overlay.current_tool)
        self.update_color_borders(menu)
