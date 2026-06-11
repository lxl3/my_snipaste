"""形状菜单状态同步"""

from PySide6.QtWidgets import QMenu, QToolButton

from .base_menu import MenuHandler


class ShapeMenuHandler(MenuHandler):
    """矩形/椭圆菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        if self.overlay.current_tool not in tool_ids:
            self.select_tool("rect", btn, "rectangle")
        self.update_submenu_state(menu, tool_ids)
