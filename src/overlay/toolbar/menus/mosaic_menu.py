"""马赛克菜单状态同步（含 blur/mosaic 控件显隐）"""

from PySide6.QtWidgets import QToolButton, QMenu

from .base_menu import MenuHandler


class MosaicMenuHandler(MenuHandler):
    """马赛克/模糊菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        if self.overlay.current_tool not in tool_ids:
            self.select_tool("mosaic", btn, "mosaic")
        self.update_submenu_state(menu, tool_ids)

        if extra:
            blur_group = extra.get("blur_group")
            mosaic_group = extra.get("mosaic_group")
            is_blur = self.overlay.current_tool == "blur"
            if blur_group:
                blur_group.setVisible(is_blur)
            if mosaic_group:
                mosaic_group.setVisible(not is_blur)
