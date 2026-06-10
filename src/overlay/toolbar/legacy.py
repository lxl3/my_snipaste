"""工具栏旧版实现（迁移中）

OverlayToolbar 使用 ToolbarBuilder + TOOLBAR_CONFIG 构建菜单 UI，
保留动作按钮（undo/redo/crop/pin/save/copy/close）和动画/状态管理等
无法声明式化的逻辑。
"""

from PySide6.QtWidgets import (
    QWidget, QToolButton, QFrame, QHBoxLayout, QMenu,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import QSize, QPropertyAnimation, QAbstractAnimation

from ...ui.glass_widget import GlassFrame
from ...resources.icons.toolbar_icons import TOOLBAR_ICONS
from ...core.i18n import _
from ...core.utils import load_icon_from_svg
from ...core.logger import setup_logger
from ...core.theme import theme as _t

from .config import TOOLBAR_CONFIG
from .builder import ToolbarBuilder
from .menus.setup_handlers import (
    shape_setup,
    arrow_setup,
    pen_setup,
    highlighter_setup,
    mosaic_setup,
    magnifier_setup,
    text_setup,
    eraser_setup,
)

logger = setup_logger("overlay_toolbar")


def _toolbar_buttons_style() -> str:
    """工具栏按钮 QSS"""
    is_dark = _t.is_dark()
    if is_dark:
        btn_hover_bg = "rgba(255,255,255,10)"
        btn_hover_border = "rgba(255,255,255,15)"
        btn_checked_bg = "rgba(32,127,240,0.18)"
        btn_pressed_bg = "rgba(255,255,255,8)"
    else:
        btn_hover_bg = "rgba(128,128,128,25)"
        btn_hover_border = "rgba(128,128,128,15)"
        btn_checked_bg = "rgba(32,127,240,0.10)"
        btn_pressed_bg = "rgba(128,128,128,45)"

    return _t.qss(f"""
    #overlayToolbar {{
        border: none; background: transparent;
    }}
    QToolTip {{
        background: {"#2D2D2D" if is_dark else "#FFFFFF"};
        color: {"#CCCCCC" if is_dark else "#333333"};
        border: {"1px solid #555555" if is_dark else "1px solid #CCCCCC"};
        padding: 4px 8px; border-radius: 4px; font-size: 12px;
    }}
    QToolButton {{
        color: $text_primary; background: transparent;
        border: 1px solid transparent; border-radius: 4px;
        padding: 2px 4px; margin: 1px;
        min-width: 18px; min-height: 18px;
    }}
    QToolButton:hover {{
        background: {btn_hover_bg}; border: 1px solid {btn_hover_border};
    }}
    QToolButton:checked {{
        background: {btn_checked_bg}; border: 1px solid $accent;
    }}
    QToolButton:pressed {{ background: {btn_pressed_bg}; }}
""")


# ─── OverlayToolbar ───

class OverlayToolbar:
    """工具栏管理器

    使用 ToolbarBuilder + TOOLBAR_CONFIG 构建工具菜单，
    手动构建动作按钮（undo/redo/crop/pin/save/copy/close）。
    """

    def __init__(self, overlay, pin_window_mode: bool = False) -> None:
        self.overlay = overlay
        self.pin_window_mode = pin_window_mode
        self.toolbar: QFrame | None = None
        self._tool_btns: dict[str, QToolButton] = {}
        self._current_menu: QMenu | None = None
        self._undo_btn: QToolButton | None = None
        self._redo_btn: QToolButton | None = None
        self._anim: QPropertyAnimation | None = None
        self._builder: ToolbarBuilder | None = None

    # ─── 设置与构建 ───

    def setup(self) -> None:
        """构建整个工具栏"""
        self.toolbar = GlassFrame(self.overlay)
        self.toolbar.setObjectName("overlayToolbar")
        self.toolbar.setGlassRadius(6)
        self.toolbar.setGlassShadow(False)
        self.toolbar.setStyleSheet(_toolbar_buttons_style())
        self.toolbar.setGraphicsEffect(None)
        self.toolbar.setFixedSize(420, 32)

        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(0)

        # ── 使用 Builder 构建工具菜单 ──
        self._builder = ToolbarBuilder(self.overlay, TOOLBAR_CONFIG)

        # 注册各菜单 aboutToShow 回调
        self._register_menu_setups()

        # 构建工具菜单（返回 tool_btns）
        self._tool_btns = self._builder.build(toolbar_layout)

        # 填充菜单 extra（控件引用已就绪）并连接 aboutToShow
        self._fill_menu_extras()
        self._builder.connect_menu_setups()

        # ── 构建动作按钮 ──
        self._build_action_buttons(toolbar_layout)

        # ── 收尾 ──
        self.toolbar.hide()
        self.toolbar.installEventFilter(self.overlay)
        for child in self.toolbar.findChildren(QWidget):
            child.installEventFilter(self.overlay)

        _t.theme_changed.connect(self._refresh_icons)
        # toolbar 销毁时断开信号，防止旧实例残留导致访问已删除 C++ 对象
        self.toolbar.destroyed.connect(
            lambda: _t.theme_changed.disconnect(self._refresh_icons)
        )

    def _register_menu_setups(self) -> None:
        """为每个菜单注册 setup handler，传入额外控件引用"""
        b = self._builder

        # 后续通过 builder.get_menu_widgets(menu_id) 获取控件引用
        b.register_menu_setup("shape", shape_setup)
        b.register_menu_setup("arrow", arrow_setup,
                              extra={"arrow_style_combo": None})  # 将在构建后填充
        b.register_menu_setup("pen", pen_setup)
        b.register_menu_setup("highlighter", highlighter_setup)
        b.register_menu_setup("mosaic", mosaic_setup)
        b.register_menu_setup("magnifier", magnifier_setup)
        b.register_menu_setup("text", text_setup)
        b.register_menu_setup("eraser", eraser_setup)

    def _fill_menu_extras(self) -> None:
        """构建后填充菜单 extra dict（控件引用已创建）"""
        if not self._builder:
            return

        # arrow style combo
        arrow_widgets = self._builder.get_menu_widgets("arrow")
        if "arrow_style_combo" in arrow_widgets:
            extra = self._builder.get_menu_extra("arrow")
            extra["arrow_style_combo"] = arrow_widgets["arrow_style_combo"]

        # magnifier zoom spinbox
        magnifier_widgets = self._builder.get_menu_widgets("magnifier")
        if "zoom_spinbox" in magnifier_widgets:
            extra = self._builder.get_menu_extra("magnifier")
            extra["zoom_spinbox"] = magnifier_widgets["zoom_spinbox"]

        # mosaic/blur groups
        mosaic_widgets = self._builder.get_menu_widgets("mosaic")
        for group_key in ("blur_group", "mosaic_group"):
            if group_key in mosaic_widgets:
                extra = self._builder.get_menu_extra("mosaic")
                extra[group_key] = mosaic_widgets[group_key]

    # ─── 动作按钮（保持手动构建，含 pin_window_mode 逻辑） ───

    def _build_action_buttons(self, layout: QHBoxLayout) -> None:
        """构建 undo/redo/crop/pin/save/copy/close 等操作按钮"""
        # ── Undo / Redo ──
        self._add_sep(layout)
        self._undo_btn = self._make_action_btn("undo", _("Undo"), self.overlay._undo)
        self._undo_btn.setEnabled(False)
        self._undo_btn.setStyleSheet(_t.qss(
            "QToolButton:enabled { color: $text_primary; }"
            " QToolButton:disabled { color: $text_disabled; }"
        ))
        layout.addWidget(self._undo_btn)

        self._redo_btn = self._make_action_btn("redo", _("Redo"), self.overlay._redo)
        self._redo_btn.setEnabled(False)
        self._redo_btn.setStyleSheet(_t.qss(
            "QToolButton:enabled { color: $text_primary; }"
            " QToolButton:disabled { color: $text_disabled; }"
        ))
        layout.addWidget(self._redo_btn)

        # ── 分隔符 ──
        self._add_sep(layout)

        # ── Crop（仅覆盖层有 _crop 方法时）──
        if hasattr(self.overlay, '_crop'):
            btn = self._make_action_btn("crop", _("Crop to selection"), self.overlay._crop)
            layout.addWidget(btn)

        self._add_sep(layout)

        # ── 动作按钮 ──
        actions = []
        if not self.pin_window_mode:
            actions.append(("close", _("Close (Exit)"), self.overlay.close))
            actions.append(("pin", _("Pin (Stick to desktop)"), self.overlay.on_pin))

        actions += [
            ("save", _("Save to file"), self.overlay.on_save),
            ("copy", _("Copy to clipboard"), self.overlay.on_copy),
        ]

        if self.pin_window_mode:
            actions.append(("done", _("Done Editing"), self.overlay._on_done_editing))

        for icon, tooltip, fn in actions:
            btn = self._make_action_btn(icon, tooltip, fn)
            layout.addWidget(btn)

    def _make_action_btn(self, icon_name: str, tooltip: str, on_click) -> QToolButton:
        """辅助: 创建操作按钮"""
        btn = QToolButton()
        btn.setIcon(self._load_icon(icon_name))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        btn.setProperty("iconName", icon_name)
        btn.clicked.connect(on_click)
        return btn

    def _add_sep(self, layout: QHBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(_t.qss("color: $border_light; max-width: 1px;"))
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    # ─── 动画 ───

    def animate_show(self) -> None:
        """入场淡入动画"""
        if not self.toolbar or not self.toolbar.isVisible():
            return
        eff = QGraphicsOpacityEffect(self.toolbar)
        self.toolbar.setGraphicsEffect(eff)
        eff.setOpacity(0.0)
        self._anim = QPropertyAnimation(eff, b"opacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.finished.connect(lambda: self.toolbar.setGraphicsEffect(None))
        self._anim.finished.connect(lambda: setattr(self, '_anim', None))
        self._anim.start(QAbstractAnimation.DeleteWhenStopped)

    # ─── 图标与主题 ───

    def _load_icon(self, name: str, color: str = ""):
        if not color:
            color = _t.get("text_primary", "#333333")
        return load_icon_from_svg(TOOLBAR_ICONS.get(name, ""), color)

    def _refresh_icons(self) -> None:
        """主题切换时刷新图标"""
        if not self.toolbar:
            return
        try:
            self.toolbar.setStyleSheet(_toolbar_buttons_style())
            for btn in self.toolbar.findChildren(QToolButton):
                icon_name = btn.property("iconName")
                if icon_name:
                    btn.setIcon(self._load_icon(icon_name))
        except RuntimeError:
            pass

        # 刷新 undo/redo disabled 状态的样式
        try:
            for btn in (self._undo_btn, self._redo_btn):
                if btn:
                    btn.setStyleSheet(_t.qss(
                        "QToolButton:enabled { color: $text_primary; }"
                        " QToolButton:disabled { color: $text_disabled; }"
                    ))
        except RuntimeError:
            pass

        # 刷新 builder 创建的子控件样式（combo/spinbox 等）
        if self._builder:
            try:
                self._builder.refresh_widget_styles()
            except RuntimeError:
                pass

    # ─── 菜单管理 ───

    def close_menus(self) -> None:
        """关闭所有打开的子菜单"""
        if self._current_menu and self._current_menu.isVisible():
            self._current_menu.hide()
            self._current_menu = None
        for btn in self._tool_btns.values():
            btn.setChecked(False)

    # ─── Undo/Redo ───

    def update_undo_redo_state(self) -> None:
        """更新 undo/redo 按钮启用状态"""
        undo_enabled = len(self.overlay._undo_stack) > 0
        redo_enabled = len(self.overlay._redo_stack) > 0

        self._undo_btn.setEnabled(undo_enabled)
        self._redo_btn.setEnabled(redo_enabled)

        undo_color = _t.get("text_primary") if undo_enabled else _t.get("text_disabled")
        redo_color = _t.get("text_primary") if redo_enabled else _t.get("text_disabled")
        self._undo_btn.setIcon(self._load_icon("undo", undo_color))
        self._redo_btn.setIcon(self._load_icon("redo", redo_color))
