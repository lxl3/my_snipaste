"""工具栏主类

OverlayToolbar 使用 ToolbarBuilder + TOOLBAR_CONFIG 构建菜单 UI，
手动构建动作按钮（undo/redo/crop/pin/save/copy/close）并管理动画/状态。
"""

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, QSize
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QMenu,
    QToolButton,
    QWidget,
)

from ...core.i18n import _
from ...core.theme_pkg import theme as _t
from ...core.utils import load_icon_from_svg
from ...resources.icons.toolbar_icons import TOOLBAR_ICONS
from ...ui.glass_widget import GlassFrame
from .builder import ToolbarBuilder
from .config import TOOLBAR_CONFIG
from .menus.arrow_menu import ArrowMenuHandler
from .menus.eraser_menu import EraserMenuHandler
from .menus.highlighter_menu import HighlighterMenuHandler
from .menus.magnifier_menu import MagnifierMenuHandler
from .menus.mosaic_menu import MosaicMenuHandler
from .menus.pen_menu import PenMenuHandler
from .menus.shape_menu import ShapeMenuHandler
from .menus.text_menu import TextMenuHandler

# ─── 工具栏按钮样式 ───

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
        background: transparent;
        color: $text_secondary;
        border: none;
        padding: 0px;
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


# ─── Menu Handler 注册表 ───

_MENU_HANDLERS: dict[str, type] = {
    "shape": ShapeMenuHandler,
    "arrow": ArrowMenuHandler,
    "pen": PenMenuHandler,
    "highlighter": HighlighterMenuHandler,
    "mosaic": MosaicMenuHandler,
    "magnifier": MagnifierMenuHandler,
    "text": TextMenuHandler,
    "eraser": EraserMenuHandler,
}


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

        # 注册各菜单 aboutToShow 回调（实例化各 MenuHandler）
        self._menu_handlers = {
            mid: cls(self.overlay) for mid, cls in _MENU_HANDLERS.items()
        }
        for menu_id, handler in self._menu_handlers.items():
            self._builder.register_menu_setup(
                menu_id,
                lambda overlay, menu, btn, tool_ids, extra, h=handler:
                    h.setup(menu, btn, tool_ids, extra)
            )

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
        self.toolbar.destroyed.connect(
            lambda: _t.theme_changed.disconnect(self._refresh_icons)
        )

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

    # ─── 动作按钮 ───

    def _build_action_buttons(self, layout: QHBoxLayout) -> None:
        """构建 undo/redo/crop/pin/save/copy/close 等操作按钮"""
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

        self._add_sep(layout)

        if hasattr(self.overlay, '_crop'):
            btn = self._make_action_btn("crop", _("Crop to selection"), self.overlay._crop)
            layout.addWidget(btn)

        self._add_sep(layout)

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

        try:
            for btn in (self._undo_btn, self._redo_btn):
                if btn:
                    btn.setStyleSheet(_t.qss(
                        "QToolButton:enabled { color: $text_primary; }"
                        " QToolButton:disabled { color: $text_disabled; }"
                    ))
        except RuntimeError:
            pass

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
