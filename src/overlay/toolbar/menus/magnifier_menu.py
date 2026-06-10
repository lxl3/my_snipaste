"""放大镜菜单状态同步（含 zoom spinbox 同步）"""

from PySide6.QtWidgets import QToolButton, QMenu

from .base_menu import MenuHandler


class MagnifierMenuHandler(MenuHandler):
    """放大镜菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        if self.overlay.current_tool != "magnifier":
            self.select_tool("magnifier", btn, "magnifier")
        zoom_spinbox = (extra or {}).get("zoom_spinbox")
        if zoom_spinbox:
            zoom_spinbox.setValue(self.overlay.current_magnifier_zoom)
