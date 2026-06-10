"""画笔菜单状态同步"""

from PySide6.QtWidgets import QToolButton, QMenu

from .base_menu import MenuHandler


class PenMenuHandler(MenuHandler):
    """画笔菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        self.select_tool("freehand")
