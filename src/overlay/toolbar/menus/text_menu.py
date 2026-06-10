"""文字菜单状态同步"""

from PySide6.QtWidgets import QToolButton, QMenu

from .base_menu import MenuHandler


class TextMenuHandler(MenuHandler):
    """文字菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        if self.overlay.current_tool != "text":
            self.select_tool("text")
