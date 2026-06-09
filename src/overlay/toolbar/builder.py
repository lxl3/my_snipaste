"""工具栏构建器

从声明式配置构建工具栏 UI。
"""
from typing import Callable

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QToolButton, QFrame, QHBoxLayout, QMenu,
    QWidgetAction, QPushButton, QSpinBox, QComboBox, QLabel,
)

from ...core.i18n import _
from ...core.utils import load_icon_from_svg
from ...core.theme import theme as _t
from ...core.settings import get_settings
from ...resources.icons.toolbar_icons import TOOLBAR_ICONS


class ToolbarBuilder:
    """从配置构建工具栏控件"""

    def __init__(self, overlay, config: list[dict]):
        self.overlay = overlay
        self.config = config
        self._tool_btns: dict[str, QToolButton] = {}
        self._menus: dict[str, QMenu] = {}

    def build(self, parent_layout: QHBoxLayout) -> dict[str, QToolButton]:
        """构建所有工具按钮，返回工具按钮字典"""
        for item in self.config:
            if item.get("type") == "separator":
                self._add_separator(parent_layout)
            elif "single_tool" in item:
                self._build_single_tool(parent_layout, item)
            elif "action" in item and "tools" not in item:
                self._build_action_button(parent_layout, item)
            elif "tools" in item:
                self._build_tool_menu(parent_layout, item)

        return self._tool_btns

    def _load_icon(self, name: str, color: str = ""):
        if not color:
            color = _t.get("text_primary", "#333333")
        return load_icon_from_svg(TOOLBAR_ICONS.get(name, ""), color)

    def _add_separator(self, layout: QHBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(_t.qss("color: $border_light; max-width: 1px;"))
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _build_single_tool(self, layout: QHBoxLayout, config: dict) -> None:
        """构建单一工具按钮（无子菜单）"""
        btn = QToolButton()
        btn.setIcon(self._load_icon(config["icon"]))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(_(config["tooltip"]))
        btn.setCheckable(True)
        btn.setProperty("iconName", config["icon"])

        tool_id = config["single_tool"]
        btn.clicked.connect(lambda: self._select_tool(tool_id))

        layout.addWidget(btn)
        self._tool_btns[tool_id] = btn

    def _build_action_button(self, layout: QHBoxLayout, config: dict) -> None:
        """构建动作按钮（如 OCR、undo、redo）"""
        btn = QToolButton()
        btn.setIcon(self._load_icon(config["icon"]))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(_(config["tooltip"]))
        btn.setProperty("iconName", config["icon"])

        action = config["action"]
        if action == "ocr":
            btn.clicked.connect(self.overlay._do_ocr)
        elif action == "undo":
            btn.clicked.connect(self.overlay._on_undo)
        elif action == "redo":
            btn.clicked.connect(self.overlay._on_redo)

        layout.addWidget(btn)

        if config.get("stateful"):
            if action == "undo":
                self.overlay._undo_btn = btn
            elif action == "redo":
                self.overlay._redo_btn = btn

    def _build_tool_menu(self, layout: QHBoxLayout, config: dict) -> None:
        """构建带子菜单的工具按钮"""
        tool_ids = [t["id"] for t in config.get("tools", []) if not t.get("implicit")]

        btn = QToolButton()
        btn.setIcon(self._load_icon(config["icon"]))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(_(config["tooltip"]))
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        btn.setProperty("iconName", config["icon"])

        menu = QMenu(self.overlay)
        menu.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)

        # 构建菜单内容
        menu_action = QWidgetAction(menu)
        container = QWidget()
        menu_layout = QHBoxLayout(container)
        menu_layout.setContentsMargins(2, 2, 2, 2)
        menu_layout.setSpacing(2)
        menu_layout.setAlignment(Qt.AlignVCenter)

        # 添加子工具按钮
        for tool in config.get("tools", []):
            if tool.get("implicit"):
                continue
            if tool.get("type") == "style_combo":
                self._add_style_combo(menu_layout, tool, btn, menu)
            else:
                self._add_tool_button(menu_layout, tool, btn, menu)

        # 添加选项控件
        for opt in config.get("options", []):
            if opt["type"] == "separator":
                self._add_menu_separator(menu_layout)
            elif opt["type"] == "color_picker":
                self._add_color_picker(menu_layout, config["id"])
            elif opt["type"] == "color_buttons":
                self._add_color_buttons(menu_layout, opt)
            elif opt["type"] == "width_spinbox":
                self._add_width_spinbox(menu_layout, opt)

        menu_action.setDefaultWidget(container)
        menu.addAction(menu_action)

        # 连接信号
        btn.clicked.connect(lambda: self._toggle_menu(menu, btn, tool_ids))

        layout.addWidget(btn)

        # 注册所有子工具到同一个按钮
        for tool in config.get("tools", []):
            self._tool_btns[tool["id"]] = btn
        self._menus[config["id"]] = menu

    def _add_tool_button(self, layout, tool: dict, main_btn, menu) -> None:
        """添加子工具按钮"""
        btn = QToolButton()
        btn.setIcon(self._load_icon(tool["icon"]))
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(18, 18)
        btn.setToolTip(_(tool["tooltip"]))
        btn.setProperty("iconName", tool["icon"])
        btn.setCheckable(True)
        btn.setProperty("tool_type", tool["id"])

        btn.clicked.connect(
            lambda: self._on_tool_selected(tool["id"], main_btn, tool["icon"], menu)
        )
        layout.addWidget(btn)

    def _add_style_combo(self, layout, tool: dict, main_btn, menu) -> None:
        """添加样式下拉框"""
        combo = QComboBox()
        combo.setFixedWidth(tool.get("width", 85))
        for style_key, icon_name, label in tool["styles"]:
            icon = self._load_icon(icon_name)
            combo.addItem(icon, _(label), style_key)

        def on_changed(idx):
            style_key = combo.itemData(idx)
            self.overlay.current_arrow_style = style_key
            if self.overlay.current_tool != tool["id"]:
                self._select_tool(tool["id"])

        combo.currentIndexChanged.connect(on_changed)
        layout.addWidget(combo)

    def _add_menu_separator(self, layout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(_t.qss("color: $border_light;"))
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _add_color_picker(self, layout, tool_id: str) -> None:
        btn = QPushButton("🎨")
        btn.setFixedSize(20, 20)
        btn.setStyleSheet(_t.qss(
            "QPushButton { border: 1px solid $border; background: transparent; font-size: 12px; }"
            "QPushButton:hover { background: $hover_bg; }"
        ))
        btn.clicked.connect(lambda: self._open_color_picker(tool_id))
        layout.addWidget(btn)

    def _add_color_buttons(self, layout, opt: dict) -> None:
        settings = get_settings()
        colors = opt["colors"]

        for color in settings.recent_colors[:3]:
            btn = self._make_color_button(color, is_recent=True)
            btn.clicked.connect(lambda c=color: self._set_color(c, opt.get("target")))
            layout.addWidget(btn)

        if settings.recent_colors:
            self._add_menu_separator(layout)

        for color in colors:
            btn = self._make_color_button(color, is_recent=False)
            btn.clicked.connect(lambda c=color: self._set_color(c, opt.get("target")))
            layout.addWidget(btn)

    def _make_color_button(self, color: str, is_recent: bool) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(18, 18)
        btn.setProperty("color", color)

        is_current = color.lower() == self.overlay.current_color.name().lower()
        if is_current:
            border = _t.qss("2px solid $color_btn_border_on")
        elif is_recent:
            border = _t.qss("1px solid $color_btn_recent_border")
        else:
            border = _t.qss("1px solid $color_btn_border")

        btn.setStyleSheet(f"background: {color}; border: {border}; border-radius: 3px;")
        return btn

    def _add_width_spinbox(self, layout, opt: dict) -> None:
        spinbox = QSpinBox()
        spinbox.setRange(*opt["range"])
        spinbox.setValue(self.overlay.current_width)
        spinbox.setFixedWidth(opt.get("width", 50))
        spinbox.valueChanged.connect(lambda v: setattr(self.overlay, 'current_width', v))
        layout.addWidget(spinbox)

    def _select_tool(self, tool_id: str) -> None:
        self.overlay.current_tool = tool_id

    def _on_tool_selected(self, tool_id: str, main_btn, icon_name: str, menu) -> None:
        self._select_tool(tool_id)
        main_btn.setIcon(self._load_icon(icon_name))
        menu.hide()

    def _toggle_menu(self, menu, btn, tool_ids: list) -> None:
        if menu.isVisible():
            menu.hide()
        else:
            if self.overlay.current_tool not in tool_ids and tool_ids:
                self._select_tool(tool_ids[0])
            pos = btn.mapToGlobal(btn.rect().bottomLeft())
            menu.popup(pos)

    def _open_color_picker(self, tool_id: str) -> None:
        from ...ui.color_picker import get_color
        color = get_color(self.overlay.current_color, self.overlay)
        if color.isValid():
            self.overlay.current_color = color

    def _set_color(self, color: str, target: str = None) -> None:
        from PySide6.QtGui import QColor
        self.overlay.current_color = QColor(color)
