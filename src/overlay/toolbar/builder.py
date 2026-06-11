"""工具栏构建器

从声明式配置构建工具栏 UI。
支持所有控件类型：颜色按钮、宽度、字体、样式下拉、spinbox_group 等。
"""

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSpinBox,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from ...core import qss_base
from ...core.i18n import _
from ...core.theme_pkg import theme as _t
from ...core.utils import load_icon_from_svg
from ...resources.icons.toolbar_icons import TOOLBAR_ICONS
from .widgets import (
    ControlStyles,
    add_color_buttons_to_layout,
    add_font_controls_to_layout,
    add_separator,
    add_spinbox_group_to_layout,
    make_color_picker_btn,
)

# ─── 菜单样式 ───

def _popup_style() -> str:
    """子菜单弹出面板的毛玻璃背景"""
    try:
        bg_hex = _t.get("bg_toolbar", "#FFFFFFD7")
        r = int(bg_hex[1:3], 16)
        g = int(bg_hex[3:5], 16)
        b = int(bg_hex[5:7], 16)
        a = int(bg_hex[7:9], 16)
        top_a = min(a + 30, 255)
        bottom_a = max(a - 40, 0)
        gradient = (f"qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                    f" stop:0 rgba({r},{g},{b},{top_a}),"
                    f" stop:1 rgba({r},{g},{b},{bottom_a}))")
    except Exception:
        gradient = "$bg_toolbar"

    is_dark = _t.is_dark()
    if is_dark:
        border_top = "rgba(255,255,255,60)"
        border_bottom = "rgba(0,0,0,120)"
        border_main = "rgba(90,90,90,100)"
    else:
        border_top = "rgba(255,255,255,220)"
        border_bottom = "rgba(0,0,0,40)"
        border_main = "rgba(128,128,128,70)"

    return _t.qss(f"""
    QMenu {{
        background: {gradient};
        border: 1px solid {border_main};
        border-top: 2px solid {border_top};
        border-bottom: 2px solid {border_bottom};
        border-radius: 0px; padding: 4px;
    }}
    QMenu::item {{ background: transparent; padding: 0px; }}
""")


def _submenu_style() -> str:
    """Submenu 按钮样式"""
    is_dark = _t.is_dark()
    if is_dark:
        btn_bg = "rgba(255,255,255,0.03)"
        btn_hover_bg = "rgba(255,255,255,0.10)"
        btn_hover_border = "rgba(255,255,255,0.18)"
        btn_checked_bg = "rgba(32,127,240,0.20)"
        btn_checked_border = "$accent"
        btn_pressed_bg = "rgba(255,255,255,0.08)"
    else:
        btn_bg = "rgba(0,0,0,0.02)"
        btn_hover_bg = "rgba(128,128,128,0.12)"
        btn_hover_border = "rgba(128,128,128,0.20)"
        btn_checked_bg = "rgba(32,127,240,0.10)"
        btn_checked_border = "$accent"
        btn_pressed_bg = "rgba(128,128,128,0.20)"

    return _t.qss(f"""
    QToolButton {{
        color: $text_primary; background: {btn_bg};
        border: 1px solid transparent; border-radius: 3px;
        padding: 0px; margin: 0px;
    }}
    QToolButton:hover {{
        background: {btn_hover_bg}; border: 1px solid {btn_hover_border};
    }}
    QToolButton:checked {{
        background: {btn_checked_bg}; border: 1px solid {btn_checked_border};
    }}
    QToolButton:pressed {{ background: {btn_pressed_bg}; }}
""")


class ToolbarBuilder:
    """从配置构建工具栏控件"""

    def __init__(self, overlay, config: list[dict]):
        self.overlay = overlay
        self.config = config
        self._tool_btns: dict[str, QToolButton] = {}
        self._menus: dict[str, QMenu] = {}
        self._menu_btns: dict[str, QToolButton] = {}
        self._menu_tools: dict[str, list[str]] = {}
        # 存储每个菜单的 menu_id → (handler_fn, extra_dict)
        self._menu_setups: dict[str, tuple[Callable, dict]] = {}
        # 存储各菜单的附加控件引用（供 handlers 的 extra 使用）
        self._menu_widgets: dict[str, dict] = {}

    def build(self, parent_layout: QHBoxLayout) -> dict[str, QToolButton]:
        """构建所有工具按钮，返回工具按钮字典"""
        for item in self.config:
            if item.get("type") == "separator":
                add_separator(parent_layout)
            elif "single_tool" in item:
                self._build_single_tool(parent_layout, item)
            elif "action" in item and "tools" not in item:
                self._build_action_button(parent_layout, item)
            elif "tools" in item:
                self._build_tool_menu(parent_layout, item)

        return self._tool_btns

    def register_menu_setup(self, menu_id: str, handler: Callable, extra: dict = None) -> None:
        """注册菜单 aboutToShow handler，extra 是传给 handler 的额外控件引用"""
        self._menu_setups[menu_id] = (handler, extra or {})

    def get_menu_extra(self, menu_id: str) -> dict:
        """获取某菜单的 extra 字典（可用于外部修改后注册）"""
        handler, extra = self._menu_setups.get(menu_id, (None, {}))
        return extra

    def get_menu_widgets(self, menu_id: str) -> dict:
        """获取某菜单的控件引用字典"""
        return self._menu_widgets.setdefault(menu_id, {})

    def connect_menu_setups(self) -> None:
        """构建完成后统一连接菜单 aboutToShow"""
        for menu_id, menu in self._menus.items():
            if menu_id in self._menu_setups:
                handler, extra = self._menu_setups[menu_id]
                btn = self._menu_btns.get(menu_id)
                tool_ids = self._menu_tools.get(menu_id, [])
                menu.aboutToShow.connect(
                    lambda m=menu, h=handler, e=extra, b=btn, t=tool_ids:
                        h(self.overlay, m, b, t, e)
                )

    def _load_icon(self, name: str, color: str = ""):
        if not color:
            color = _t.get("text_primary", "#333333")
        return load_icon_from_svg(TOOLBAR_ICONS.get(name, ""), color)

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
        """构建动作按钮（如 OCR、undo、redo 等）"""
        btn = QToolButton()
        btn.setIcon(self._load_icon(config["icon"]))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(_(config["tooltip"]))
        btn.setProperty("iconName", config["icon"])

        action = config["action"]
        if action == "ocr":
            btn.clicked.connect(self.overlay._on_ocr)
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
        menu.setStyleSheet(_popup_style())

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
                self._add_style_combo(menu_layout, tool, config)
            else:
                self._add_tool_button(menu_layout, tool, btn, menu)

        # 添加选项控件
        self._build_options(menu_layout, config)

        menu_action.setDefaultWidget(container)
        menu.addAction(menu_action)

        # 连接信号 — 点击主按钮打开/切换菜单
        # 传入含 implicit 工具的完整列表，保证隐式工具菜单也能互斥
        all_tool_ids = [t["id"] for t in config.get("tools", [])]
        btn.clicked.connect(lambda: self._toggle_menu(menu, btn, tool_ids, all_tool_ids))

        layout.addWidget(btn)

        # 注册所有子工具到同一个按钮
        for tool in config.get("tools", []):
            self._tool_btns[tool["id"]] = btn
        self._menus[config["id"]] = menu
        self._menu_btns[config["id"]] = btn
        self._menu_tools[config["id"]] = tool_ids

        # 如果配置了 menu_width，固定菜单宽度
        if "menu_width" in config:
            container.setFixedWidth(config["menu_width"])

    def _build_options(self, layout: QHBoxLayout, config: dict) -> None:
        """根据配置选项构建控件"""
        font_added = False
        for opt in config.get("options", []):
            opt_type = opt["type"]

            if opt_type == "separator":
                add_separator(layout)

            elif opt_type == "color_picker":
                btn = make_color_picker_btn(
                    lambda: self._open_color_picker(config["id"])
                )
                layout.addWidget(btn)

            elif opt_type == "color_buttons":
                current_color = self.overlay.current_color.name()
                add_color_buttons_to_layout(
                    layout,
                    colors=opt["colors"],
                    target=opt.get("target", ""),
                    current_color=current_color,
                    on_color_selected=lambda c, t=opt.get("target"): self._set_color(c, t),
                    recent_colors=self.overlay.ctx.settings.recent_colors,
                )

            elif opt_type == "width_spinbox":
                self._add_width_spinbox(layout, opt)

            elif opt_type in ("font_combo", "font_size_spinbox", "bold_button", "italic_button"):
                if not font_added:
                    font_added = True
                    self._rebuild_text_options(layout, config)

            elif opt_type == "spinbox_group":
                spinbox = add_spinbox_group_to_layout(
                    layout,
                    label=opt.get("label", ""),
                    range_min=opt["range"][0],
                    range_max=opt["range"][1],
                    value=getattr(self.overlay, opt.get("property", ""), opt["range"][0]),
                    width=opt.get("width", 45),
                    on_changed=lambda v, p=opt.get("property"): (
                        setattr(self.overlay, p, v),
                        self.overlay._apply_property_to_selected(p, v)
                    ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
                )
                wid = opt.get("id", opt.get("property", ""))
                if wid:
                    self.get_menu_widgets(config["id"])[wid] = spinbox
                    # 存储容器引用（spinbox 的父 widget），供 setup handler 显隐切换
                    container = spinbox.parentWidget()
                    if container:
                        group_key = f"{wid}_group"
                        self.get_menu_widgets(config["id"])[group_key] = container

            elif opt_type == "magnifier_zoom":
                self._add_magnifier_zoom(layout, config)

    def _rebuild_text_options(self, layout: QHBoxLayout, config: dict) -> None:
        """批量添加文字工具选项（font_combo + font_size + bold + italic + color）"""

        has_font = any(o["type"] == "font_combo" for o in config.get("options", []))
        if not has_font:
            return

        controls = add_font_controls_to_layout(
            layout,
            font_family=getattr(self.overlay, 'text_font_family', "Segoe UI"),
            font_size=getattr(self.overlay, 'text_font_size', 24),
            bold=getattr(self.overlay, 'text_bold', False),
            italic=getattr(self.overlay, 'text_italic', False),
            on_font_changed=lambda f: (
                setattr(self.overlay, 'text_font_family', f),
                self.overlay._apply_property_to_selected("font_family", f)
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
            on_size_changed=lambda s: (
                setattr(self.overlay, 'text_font_size', s),
                self.overlay._apply_property_to_selected("font_size", s)
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
            on_bold_toggled=lambda: (
                setattr(self.overlay, 'text_bold', controls["bold_btn"].isChecked()),
                self.overlay._apply_property_to_selected("bold", controls["bold_btn"].isChecked())
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
            on_italic_toggled=lambda: (
                setattr(self.overlay, 'text_italic', controls["italic_btn"].isChecked()),
                self.overlay._apply_property_to_selected("italic", controls["italic_btn"].isChecked())
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
        )

        self._menu_widgets.setdefault(config["id"], {}).update(controls)

    def _add_magnifier_zoom(self, layout: QHBoxLayout, config: dict) -> None:
        """为放大镜添加 zoom spinbox（带 Zoom: 标签）"""
        opts = next((o for o in config.get("options", []) if o["type"] == "magnifier_zoom"), {})
        zoom_label = QLabel(_("Zoom:"))
        zoom_label.setStyleSheet(ControlStyles().label_qss())
        layout.addWidget(zoom_label)

        spinbox = QSpinBox()
        spinbox.setRange(*opts.get("range", (2, 8)))
        spinbox.setValue(getattr(self.overlay, 'current_magnifier_zoom', 4))
        spinbox.setFixedWidth(opts.get("width", 55))
        spinbox.setStyleSheet(ControlStyles().spinbox_qss())
        spinbox.valueChanged.connect(
            lambda v: (
                setattr(self.overlay, 'current_magnifier_zoom', v),
                self.overlay._apply_property_to_selected("magnifier_zoom", v)
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
        )
        layout.addWidget(spinbox)

        self.get_menu_widgets(config["id"])["zoom_spinbox"] = spinbox

    def _connect_visible_when(self, config: dict, main_btn, menu) -> None:
        """连接 visible_when 子工具切换（如 mosaic/blur 显隐 spinbox_group）"""
        widgets = self._menu_widgets.get(config["id"], {})
        if not widgets:
            return

        for opt in config.get("options", []):
            visible_when = opt.get("visible_when")
            wid = opt.get("id")
            if visible_when and wid and wid in widgets:
                # 找到对应的子工具按钮，连接 checked 信号
                for tool in config.get("tools", []):
                    if tool["id"] == visible_when:
                        # 用 QToolButton 的 clicked 信号来切换
                        for action in menu.actions():
                            w = action.defaultWidget()
                            if w:
                                for child in w.findChildren(QToolButton):
                                    if child.property("tool_type") == visible_when:
                                        child.clicked.connect(
                                            lambda checked=None, sw=widgets[wid], sv=visible_when: (
                                                sw.setVisible(True)
                                            )
                                        )

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
        btn.setStyleSheet(_submenu_style())

        btn.clicked.connect(
            lambda: self._on_tool_selected(tool["id"], main_btn, tool["icon"], menu)
        )
        layout.addWidget(btn)

    def _add_style_combo(self, layout, tool: dict, config: dict) -> None:
        """添加样式下拉框，并将 combo 引用存入 _menu_widgets"""
        combo = QComboBox()
        combo.setFixedWidth(tool.get("width", 85))
        combo.setStyleSheet(qss_base.combobox_qss(
            bg="$bg_toolbar_alt", padding="3px 6px", border_radius="3px",
            font_size="12px",
        ))
        for style_key, icon_name, label in tool["styles"]:
            icon = self._load_icon(icon_name)
            combo.addItem(icon, _(label), style_key)

        def on_changed(idx):
            style_key = combo.itemData(idx)
            self.overlay.current_arrow_style = style_key
            if hasattr(self.overlay, '_apply_property_to_selected'):
                self.overlay._apply_property_to_selected("arrow_style", style_key)
            if self.overlay.current_tool != tool["id"]:
                self._select_tool(tool["id"])

        combo.currentIndexChanged.connect(on_changed)
        layout.addWidget(combo)

        # 存储 combo 引用供 setup handler 使用
        self.get_menu_widgets(config["id"])["arrow_style_combo"] = combo

    def _add_width_spinbox(self, layout, opt: dict) -> None:
        """添加粗细 SpinBox"""
        spinbox = QSpinBox()
        spinbox.setRange(*opt["range"])
        spinbox.setValue(self.overlay.current_width)
        spinbox.setFixedWidth(opt.get("width", 50))
        spinbox.setStyleSheet(ControlStyles().spinbox_qss())
        spinbox.valueChanged.connect(
            lambda v: (
                setattr(self.overlay, 'current_width', v),
                self.overlay._apply_property_to_selected("width", v)
            ) if hasattr(self.overlay, '_apply_property_to_selected') else None,
        )
        layout.addWidget(spinbox)

    # ─── 工具选择 ───

    def _hide_all_menus(self) -> None:
        """隐藏所有弹出菜单"""
        for menu in self._menus.values():
            menu.hide()

    def _uncheck_all_tools(self) -> None:
        """取消所有工具按钮的选中态，保证互斥"""
        seen = set()
        for btn in self._tool_btns.values():
            if id(btn) not in seen:
                seen.add(id(btn))
                btn.setChecked(False)

    def _select_tool(self, tool_id: str) -> None:
        self._hide_all_menus()
        self._uncheck_all_tools()
        btn = self._tool_btns.get(tool_id)
        if btn:
            btn.setChecked(True)
        self.overlay.current_tool = tool_id

    def _on_tool_selected(self, tool_id: str, main_btn, icon_name: str, menu) -> None:
        self._hide_all_menus()
        self._uncheck_all_tools()
        main_btn.setChecked(True)
        main_btn.setIcon(self._load_icon(icon_name))
        self.overlay.current_tool = tool_id
        menu.hide()

    def _toggle_menu(self, menu, btn, tool_ids: list, all_tool_ids: list = None) -> None:
        if menu.isVisible():
            menu.hide()
        else:
            self._hide_all_menus()
            target = tool_ids or all_tool_ids or []
            if self.overlay.current_tool not in target and target:
                self._select_tool(target[0])
            else:
                # Qt auto-toggle 可能已取消勾选，恢复选中态
                btn.setChecked(True)
            pos = btn.mapToGlobal(btn.rect().bottomLeft())
            menu.popup(pos)

    # ─── 颜色 ───

    def _open_color_picker(self, tool_id: str) -> None:
        from ...ui.common.color_picker import get_color
        color = get_color(self.overlay.current_color, self.overlay)
        if color.isValid():
            self.overlay.current_color = color

    def _set_color(self, color: str, target: str = None) -> None:
        from PySide6.QtGui import QColor
        if not isinstance(color, str):
            return
        qc = QColor(color)
        if not qc.isValid():
            return
        self.overlay.current_color = qc
        if hasattr(self.overlay, '_apply_property_to_selected') and target:
            self.overlay._apply_property_to_selected("color", color)
        self.overlay.ctx.settings.add_recent_color(color)

    # ─── 公共访问 ───

    def get_menu(self, menu_id: str) -> QMenu | None:
        return self._menus.get(menu_id)

    def get_tool_buttons(self) -> dict[str, QToolButton]:
        return self._tool_btns

    def refresh_widget_styles(self) -> None:
        """主题切换时刷新所有已注册子控件的 QSS（combo/spinbox 等）"""
        combo_qss = qss_base.combobox_qss(
            bg="$bg_toolbar_alt", padding="3px 6px", border_radius="3px",
            font_size="12px",
        )
        spinbox_qss = qss_base.spinbox_qss(
            bg="$bg_toolbar_alt", border_radius="3px",
            color="$text_primary", arrow_color="$text_primary",
        )
        for menu_id, widgets in self._menu_widgets.items():
            for name, widget in widgets.items():
                if isinstance(widget, QComboBox):
                    widget.setStyleSheet(combo_qss)
                elif isinstance(widget, QSpinBox):
                    widget.setStyleSheet(spinbox_qss)
