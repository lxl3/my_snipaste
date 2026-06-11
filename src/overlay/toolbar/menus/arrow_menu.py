"""箭头菜单状态同步（含样式下拉框同步）"""

from PySide6.QtWidgets import QMenu, QToolButton

from .base_menu import MenuHandler


class ArrowMenuHandler(MenuHandler):
    """箭头/线菜单弹出前状态同步"""

    def setup(self, menu: QMenu, btn: QToolButton | None,
              tool_ids: list[str], extra: dict | None = None) -> None:
        if self.overlay.current_tool not in tool_ids:
            self.select_tool("arrow", btn, "arrow")
        self.update_submenu_state(menu, tool_ids)

        arrow_combo = (extra or {}).get("arrow_style_combo")
        if arrow_combo:
            idx = getattr(self.overlay, '_selected_annotation_idx', None)
            if idx is not None and 0 <= idx < len(self.overlay.annotations):
                ann = self.overlay.annotations[idx]
                if ann.type == "arrow":
                    saved = ann.arrow_style
                    if saved in ("solid", "hollow", "solid_tail", "hollow_tail"):
                        self.overlay.current_arrow_style = saved

            current_style = self.overlay.current_arrow_style
            for i in range(arrow_combo.count()):
                if arrow_combo.itemData(i) == current_style:
                    arrow_combo.setCurrentIndex(i)
                    break
