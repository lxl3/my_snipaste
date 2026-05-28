from PySide6.QtWidgets import (
    QWidget, QApplication, QToolButton, QFrame, QHBoxLayout, QMenu,
    QWidgetAction, QPushButton, QSpinBox, QVBoxLayout,
    QComboBox, QColorDialog,
)
from PySide6.QtGui import QColor, QIcon
from PySide6.QtCore import Qt, QPoint, QSize

from ..resources.icons.toolbar_icons import TOOLBAR_ICONS
from ..core.i18n import _
from ..core.utils import load_icon_from_svg
from ..core.constants import (
    PRESET_COLORS, TEXT_PRESET_COLORS, ICON_SIZE_SMALL, ICON_SIZE_MENU,
    ICON_SIZE_BTN, DEFAULT_ANNOTATION_COLOR, DEFAULT_LINE_WIDTH,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE,
)
from ..core.logger import setup_logger
from ..core.settings import get_settings

logger = setup_logger("overlay_toolbar")

SUBMENU_STYLE = """
    QToolButton {
        border: 1px solid #ccc;
        padding: 2px;
        background: white;
    }
    QToolButton:hover { background: #e8e8e8; }
    QToolButton:checked {
        background: #207ff0;
        color: white;
        border: 2px solid #1a6acc;
    }
"""

TOOLBAR_STYLE = """
    #overlayToolbar { background: white; border: 1px solid #ccc; }
    QToolButton { color: #333; background: transparent; border: none; padding: 2px 4px; margin: 0px; min-width: 18px; min-height: 18px; }
    QToolButton:hover { background: #e8e8e8; }
    QToolButton:checked { background: #207ff0; color: white; }
"""


class OverlayToolbar:
    def __init__(self, overlay) -> None:
        self.overlay = overlay
        self.toolbar: QFrame | None = None
        self._tool_btns: dict[str, QToolButton] = {}
        self._color_buttons: list[QPushButton] = []
        self._width_spinbox: QSpinBox | None = None
        self._current_menu: QMenu | None = None
        self._shape_color_buttons: list[QPushButton] = []
        self._arrow_color_buttons: list[QPushButton] = []
        self._text_color_buttons: list[QPushButton] = []
        self._font_combo: QComboBox | None = None
        self._font_size_spinbox: QSpinBox | None = None
        self._bold_btn: QPushButton | None = None
        self._italic_btn: QPushButton | None = None
        self._undo_btn: QToolButton | None = None
        self._redo_btn: QToolButton | None = None

    def setup(self) -> None:
        self.toolbar = QFrame(self.overlay)
        self.toolbar.setObjectName("overlayToolbar")
        self.toolbar.setStyleSheet(TOOLBAR_STYLE)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(0)

        def add_sep() -> None:
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet("color: #ddd; max-width: 1px;")
            sep.setFixedWidth(1)
            toolbar_layout.addWidget(sep)

        self._build_shape_menu(toolbar_layout)
        self._build_arrow_menu(toolbar_layout)
        self._build_pen_menu(toolbar_layout)
        self._build_mosaic_btn(toolbar_layout)
        self._build_text_menu(toolbar_layout)
        self._build_eraser_menu(toolbar_layout)
        self._build_ocr_btn(toolbar_layout)
        add_sep()
        self._build_undo_btn(toolbar_layout)
        self._build_redo_btn(toolbar_layout)
        add_sep()
        self._build_action_btns(toolbar_layout)

        self.toolbar.hide()
        self.toolbar.installEventFilter(self.overlay)
        for child in self.toolbar.findChildren(QWidget):
            child.installEventFilter(self.overlay)

    def _load_icon(self, name: str, color: str = "#333333") -> QIcon:
        return load_icon_from_svg(TOOLBAR_ICONS.get(name, ""), color)

    def _make_submenu_btn(self, btn_icon: str, btn_tooltip: str, parent_layout, tool_ids=None):
        btn = QToolButton()
        btn.setIcon(self._load_icon(btn_icon))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(btn_tooltip)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        menu = QMenu(self.overlay)
        menu.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        if tool_ids:
            btn.clicked.connect(lambda: self._toggle_or_open_menu(menu, btn, tool_ids))
        else:
            btn.clicked.connect(lambda: self._toggle_menu(menu, btn))
        parent_layout.addWidget(btn)
        return btn, menu

    def _add_tool_buttons_to_submenu(self, layout, items: list[tuple[str, str]], main_btn, menu) -> None:
        for item_icon, item_tool in items:
            tool_btn = QToolButton()
            tool_btn.setIcon(self._load_icon(item_icon))
            tool_btn.setIconSize(QSize(20, 20))
            tool_btn.setFixedSize(24, 24)
            tool_btn.setToolTip(item_tool)
            tool_btn.setCheckable(True)
            tool_btn.setProperty("tool_type", item_tool)
            tool_btn.setStyleSheet(SUBMENU_STYLE)
            tool_btn.clicked.connect(
                lambda checked, t=item_tool, b=main_btn, ic=item_icon, m=menu:
                self._toggle_or_select_tool(t, b, ic, m)
            )
            layout.addWidget(tool_btn)

    def _add_color_buttons_to_submenu(self, layout, colors: list[str], target_list: list, set_color_fn) -> None:
        settings = get_settings()

        # Add recent colors (max 3) at the front
        recent_count = 0
        for color in settings.recent_colors[:3]:
            cb = self._make_color_button(color, is_recent=True)
            cb.clicked.connect(lambda checked, col=color: set_color_fn(col))
            layout.addWidget(cb)
            target_list.append(cb)
            recent_count += 1

        # Add separator if there are recent colors
        if recent_count > 0:
            self._add_separator(layout)

        # Add preset colors
        for c in colors:
            cb = self._make_color_button(c, is_recent=False)
            cb.clicked.connect(lambda checked, col=c: set_color_fn(col))
            layout.addWidget(cb)
            target_list.append(cb)

    def _make_color_button(self, color: str, is_recent: bool = False) -> QPushButton:
        """Create a color button with visual distinction for recent colors"""
        btn = QPushButton()
        btn.setFixedSize(18, 18)
        btn.setProperty("color", color)

        is_current = (color.lower() == self.overlay.current_color.name().lower())

        if is_recent:
            # Recent colors have a slightly different style with opacity
            if is_current:
                border = "2px solid #0078d4"
            else:
                border = "1px solid #999"
            btn.setStyleSheet(f"background: {color}; border: {border}; border-radius: 3px; opacity: 0.9;")
        else:
            # Preset colors have standard style with rounded corners
            if is_current:
                border = "2px solid #0078d4"
            else:
                border = "1px solid #ccc"
            btn.setStyleSheet(f"background: {color}; border: {border}; border-radius: 3px;")

        return btn

    def _add_separator(self, layout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #ddd;")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _add_color_picker_btn(self, layout, open_fn) -> None:
        btn = QPushButton("🎨")
        btn.setFixedSize(20, 20)
        btn.setStyleSheet(
            "QPushButton { border: 1px solid #ccc;  background: white; font-size: 12px; }"
            "QPushButton:hover { background: #e8e8e8; }"
        )
        btn.clicked.connect(lambda: open_fn())
        layout.addWidget(btn)

    def _build_shape_menu(self, toolbar_layout) -> None:
        shape_btn, shape_menu = self._make_submenu_btn("rectangle", _("Shape (Rectangle / Ellipse)"), toolbar_layout, ["rect", "ellipse"])
        shape_action = QWidgetAction(shape_menu)
        shape_container = QWidget()
        shape_layout = QHBoxLayout(shape_container)
        shape_layout.setContentsMargins(3, 3, 3, 3)
        shape_layout.setSpacing(3)

        self._add_tool_buttons_to_submenu(shape_layout, [("rectangle", "rect"), ("ellipse", "ellipse")], shape_btn, shape_menu)
        self._add_separator(shape_layout)
        self._add_color_picker_btn(shape_layout, self._open_shape_color_picker)
        self._add_color_buttons_to_submenu(shape_layout, PRESET_COLORS, self._shape_color_buttons, self._set_shape_color)

        shape_action.setDefaultWidget(shape_container)
        shape_menu.addAction(shape_action)

        def _setup():
            if self.overlay.current_tool not in ["rect", "ellipse"]:
                self._select_tool("rect", shape_btn, "rectangle")
            self._update_submenu_state(shape_menu, ["rect", "ellipse"])
        shape_menu.aboutToShow.connect(_setup)

        self._tool_btns["rect"] = shape_btn
        self._tool_btns["ellipse"] = shape_btn

    def _build_arrow_menu(self, toolbar_layout) -> None:
        arrow_btn, arrow_menu = self._make_submenu_btn("arrow", _("Arrow (Arrow / Line)"), toolbar_layout, ["arrow", "line"])
        arrow_action = QWidgetAction(arrow_menu)
        arrow_container = QWidget()
        arrow_layout = QHBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(3, 3, 3, 3)
        arrow_layout.setSpacing(3)

        self._add_tool_buttons_to_submenu(arrow_layout, [("arrow", "arrow"), ("line", "line")], arrow_btn, arrow_menu)
        self._add_separator(arrow_layout)
        self._add_color_picker_btn(arrow_layout, self._open_shape_color_picker)
        self._add_color_buttons_to_submenu(arrow_layout, PRESET_COLORS, self._arrow_color_buttons, self._set_shape_color)

        arrow_action.setDefaultWidget(arrow_container)
        arrow_menu.addAction(arrow_action)

        def _setup():
            if self.overlay.current_tool not in ["arrow", "line"]:
                self._select_tool("arrow", arrow_btn, "arrow")
            self._update_submenu_state(arrow_menu, ["arrow", "line"])
        arrow_menu.aboutToShow.connect(_setup)

        self._tool_btns["arrow"] = arrow_btn
        self._tool_btns["line"] = arrow_btn

    def _build_pen_menu(self, toolbar_layout) -> None:
        pen_btn, pen_menu = self._make_submenu_btn("pen", _("Pen"), toolbar_layout, ["freehand"])
        pen_action = QWidgetAction(pen_menu)
        pen_container = QWidget()
        container_layout = QHBoxLayout(pen_container)
        container_layout.setContentsMargins(3, 3, 3, 3)
        container_layout.setSpacing(4)

        self._add_color_buttons_to_submenu(container_layout, PRESET_COLORS, self._color_buttons, self._set_pen_color)
        self._add_separator(container_layout)

        self._width_spinbox = QSpinBox()
        self._width_spinbox.setRange(1, 20)
        self._width_spinbox.setValue(self.overlay.current_width)
        self._width_spinbox.setFixedWidth(50)
        self._width_spinbox.setButtonSymbols(QSpinBox.UpDownArrows)
        self._width_spinbox.valueChanged.connect(lambda v: setattr(self.overlay, 'current_width', v))
        container_layout.addWidget(self._width_spinbox)

        pen_action.setDefaultWidget(pen_container)
        pen_menu.addAction(pen_action)

        def _setup():
            self._select_tool("freehand")
        pen_menu.aboutToShow.connect(_setup)

        self._tool_btns["freehand"] = pen_btn

    def _build_mosaic_btn(self, toolbar_layout) -> None:
        mosaic_btn = QToolButton()
        mosaic_btn.setIcon(self._load_icon("mosaic"))
        mosaic_btn.setIconSize(QSize(16, 16))
        mosaic_btn.setToolTip(_("Mosaic"))
        mosaic_btn.setCheckable(True)
        mosaic_btn.clicked.connect(lambda: (self._close_current_menu(), self._toggle_tool("mosaic")))
        toolbar_layout.addWidget(mosaic_btn)
        self._tool_btns["mosaic"] = mosaic_btn

    def _build_text_menu(self, toolbar_layout) -> None:
        text_btn, text_menu = self._make_submenu_btn("text", _("Text"), toolbar_layout, ["text"])
        text_action = QWidgetAction(text_menu)
        text_container = QWidget()
        text_main_layout = QHBoxLayout(text_container)
        text_main_layout.setContentsMargins(3, 3, 3, 3)
        text_main_layout.setSpacing(4)
        text_main_layout.setAlignment(Qt.AlignCenter)

        self._font_combo = QComboBox()
        self._font_combo.addItems(["Segoe UI", "Arial", "微软雅黑", "宋体", "黑体", "楷体"])
        self._font_combo.setCurrentText(self.overlay.text_font_family)
        self._font_combo.setFixedWidth(100)
        self._font_combo.currentTextChanged.connect(self._set_text_font)
        text_main_layout.addWidget(self._font_combo)

        self._font_size_spinbox = QSpinBox()
        self._font_size_spinbox.setRange(8, 72)
        self._font_size_spinbox.setValue(self.overlay.text_font_size)
        self._font_size_spinbox.setFixedWidth(100)
        self._font_size_spinbox.setButtonSymbols(QSpinBox.UpDownArrows)
        self._font_size_spinbox.valueChanged.connect(self._set_text_size)
        text_main_layout.addWidget(self._font_size_spinbox)

        self._bold_btn = QPushButton("B")
        self._bold_btn.setFixedSize(20, 20)
        self._bold_btn.setCheckable(True)
        self._bold_btn.setStyleSheet(
            "QPushButton { font-weight: bold; border: 1px solid #ccc;  background: white; }"
            "QPushButton:hover { background: #e8e8e8; }"
            "QPushButton:checked { background: #207ff0; color: white; border: 2px solid #1a6acc; }"
        )
        self._bold_btn.clicked.connect(self._toggle_bold)
        text_main_layout.addWidget(self._bold_btn)

        self._italic_btn = QPushButton("I")
        self._italic_btn.setFixedSize(20, 20)
        self._italic_btn.setCheckable(True)
        self._italic_btn.setStyleSheet(
            "QPushButton { font-style: italic; border: 1px solid #ccc;  background: white; }"
            "QPushButton:hover { background: #e8e8e8; }"
            "QPushButton:checked { background: #207ff0; color: white; border: 2px solid #1a6acc; }"
        )
        self._italic_btn.clicked.connect(self._toggle_italic)
        text_main_layout.addWidget(self._italic_btn)

        self._add_separator(text_main_layout)
        self._add_color_picker_btn(text_main_layout, self._open_color_picker)
        self._add_color_buttons_to_submenu(text_main_layout, PRESET_COLORS, self._text_color_buttons, self._set_text_color)
        text_action.setDefaultWidget(text_container)
        text_menu.addAction(text_action)

        def _setup():
            self._select_tool("text")
        text_menu.aboutToShow.connect(_setup)

        self._tool_btns["text"] = text_btn

    def _build_eraser_menu(self, toolbar_layout) -> None:
        eraser_btn, eraser_menu = self._make_submenu_btn("eraser", _("Eraser (Dot Erase / Fill Erase)"), toolbar_layout, ["eraser_dot", "eraser_fill"])
        eraser_action = QWidgetAction(eraser_menu)
        eraser_container = QWidget()
        eraser_layout = QHBoxLayout(eraser_container)
        eraser_layout.setContentsMargins(6, 4, 6, 4)
        eraser_layout.setSpacing(6)

        for icon_key, tool_id, tooltip in [
            ("eraser_dot", "eraser_dot", _("Dot Erase")),
            ("eraser_fill", "eraser_fill", _("Fill Erase")),
        ]:
            tool_btn = QToolButton()
            tool_btn.setIcon(self._load_icon(icon_key))
            tool_btn.setIconSize(QSize(20, 20))
            tool_btn.setFixedSize(28, 28)
            tool_btn.setToolTip(tooltip)
            tool_btn.setCheckable(True)
            tool_btn.setProperty("tool_type", tool_id)
            tool_btn.setStyleSheet(SUBMENU_STYLE)
            # keep tool active, do not revert to select
            tool_btn.clicked.connect(
                lambda checked, t=tool_id, b=eraser_btn, ic=icon_key, m=eraser_menu:
                self._select_eraser_subtool(t, b, ic, m)
            )
            eraser_layout.addWidget(tool_btn)

        eraser_action.setDefaultWidget(eraser_container)
        eraser_menu.addAction(eraser_action)

        def _setup():
            if self.overlay.current_tool not in ["eraser_dot", "eraser_fill"]:
                self._select_tool("eraser_dot", eraser_btn, "eraser")
            self._update_submenu_state(eraser_menu, ["eraser_dot", "eraser_fill"])
        eraser_menu.aboutToShow.connect(_setup)

        self._tool_btns["eraser_dot"] = eraser_btn

    def _select_eraser_subtool(self, tool_id: str, btn, icon_name: str, menu_obj) -> None:
        self._select_tool(tool_id, btn, icon_name)
        self._update_submenu_check_state(menu_obj, tool_id)

    def _build_ocr_btn(self, toolbar_layout) -> None:
        ocr_btn = QToolButton()
        ocr_btn.setIcon(self._load_icon("OCR"))
        ocr_btn.setIconSize(QSize(16, 16))
        ocr_btn.setToolTip(_("Text Recognition"))
        ocr_btn.clicked.connect(lambda: (self._close_current_menu(), self.overlay._on_ocr()))
        toolbar_layout.addWidget(ocr_btn)

    def _build_undo_btn(self, toolbar_layout) -> None:
        self._undo_btn = QToolButton()
        self._undo_btn.setIcon(self._load_icon("undo"))
        self._undo_btn.setIconSize(QSize(16, 16))
        self._undo_btn.setToolTip(_("Undo"))
        self._undo_btn.clicked.connect(self.overlay._undo)
        self._undo_btn.setEnabled(False)
        self._undo_btn.setStyleSheet("QToolButton:enabled { opacity: 1.0; } QToolButton:disabled { opacity: 0.3; }")
        toolbar_layout.addWidget(self._undo_btn)

    def _build_redo_btn(self, toolbar_layout) -> None:
        self._redo_btn = QToolButton()
        self._redo_btn.setIcon(self._load_icon("redo"))
        self._redo_btn.setIconSize(QSize(16, 16))
        self._redo_btn.setToolTip(_("Redo"))
        self._redo_btn.clicked.connect(self.overlay._redo)
        self._redo_btn.setEnabled(False)
        self._redo_btn.setStyleSheet("QToolButton:enabled { opacity: 1.0; } QToolButton:disabled { opacity: 0.3; }")
        toolbar_layout.addWidget(self._redo_btn)

    def _build_action_btns(self, toolbar_layout) -> None:
        for icon, tooltip, fn in [
            ("close", _("Close (Exit)"), self.overlay.close),
            ("pin", _("Pin (Stick to desktop)"), self.overlay.on_pin),
            ("save", _("Save to file"), self.overlay.on_save),
            ("copy", _("Copy to clipboard"), self.overlay.on_copy),
        ]:
            btn = QToolButton()
            btn.setIcon(self._load_icon(icon))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(tooltip)
            btn.clicked.connect(fn)
            toolbar_layout.addWidget(btn)

    def _select_tool(self, tool_id: str, btn=None, icon_name: str | None = None) -> None:
        # Use the overlay's method to ensure settings are saved/restored
        self.overlay._on_tool_selected(tool_id)

        # Update UI
        if btn:
            btn.setChecked(True)
            if icon_name:
                btn.setIcon(self._load_icon(icon_name))
        if tool_id == "text":
            self.overlay.setCursor(Qt.IBeamCursor)
        else:
            self.overlay.setCursor(Qt.CrossCursor)

    def _toggle_or_select_tool(self, tool_id: str, btn=None, icon_name: str | None = None, menu_obj=None) -> None:
        if self.overlay.current_tool == tool_id:
            self._select_tool("select")
        else:
            self._select_tool(tool_id, btn, icon_name)
            if menu_obj:
                self._update_submenu_check_state(menu_obj, tool_id)

    def _toggle_tool(self, tool_id: str) -> None:
        if self.overlay.current_tool == tool_id:
            self._select_tool("select")
        else:
            self._select_tool(tool_id)

    def _close_current_menu(self) -> None:
        if self._current_menu and self._current_menu.isVisible():
            self._current_menu.hide()
            self._current_menu = None
        for tid, b in self._tool_btns.items():
            b.setChecked(False)

    def _toggle_or_open_menu(self, menu, button, tool_ids: list[str]) -> None:
        """Sub-menu main button: if tool active, switch to select; otherwise open menu."""
        if self.overlay.current_tool in tool_ids:
            self._select_tool("select")
            if menu.isVisible():
                menu.hide()
            button.setChecked(False)
            self._current_menu = None
        else:
            self._toggle_menu(menu, button)

    def _toggle_menu(self, menu, button) -> None:
        if self._current_menu and self._current_menu != menu and self._current_menu.isVisible():
            self._current_menu.hide()
        for tid, b in self._tool_btns.items():
            if b != button:
                b.setChecked(False)
        if menu.isVisible():
            menu.hide()
            button.setChecked(False)
            self._current_menu = None
        else:
            button.setChecked(True)
            pos = button.mapToGlobal(QPoint(0, button.height()))
            menu.popup(pos)
            self._current_menu = menu

    def _update_submenu_check_state(self, menu, selected_tool: str) -> None:
        for action in menu.actions():
            widget = action.defaultWidget()
            if widget:
                for child in widget.findChildren(QToolButton):
                    tool_type = child.property("tool_type")
                    if tool_type:
                        child.setChecked(tool_type == selected_tool)

    def _update_submenu_state(self, menu, tool_ids: list[str]) -> None:
        if self.overlay.current_tool in tool_ids:
            self._update_submenu_check_state(menu, self.overlay.current_tool)
        for action in menu.actions():
            widget = action.defaultWidget()
            if widget:
                for child in widget.findChildren(QPushButton):
                    c = child.property("color")
                    if c:
                        is_current = (c.lower() == self.overlay.current_color.name().lower())
                        border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                        # Check if this is a recent color button (has opacity)
                        btn_style = child.styleSheet()
                        if "opacity: 0.9" in btn_style:
                            # Recent color button
                            if not is_current:
                                border = "1px solid #999"
                            child.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px; opacity: 0.9;")
                        else:
                            # Preset color button
                            child.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")

    def _set_pen_color(self, color_hex: str) -> None:
        self._set_shape_color(color_hex)

    def _set_shape_color(self, color_hex: str) -> None:
        self.overlay.current_color = QColor(color_hex)

        # Add to recent colors
        settings = get_settings()
        settings.add_recent_color(color_hex)

        # Update button borders for all color buttons
        all_buttons = []
        for lst in [self._color_buttons, self._shape_color_buttons, self._arrow_color_buttons]:
            all_buttons.extend(lst)
        for btn in all_buttons:
            c = btn.property("color")
            if c:
                is_current = (c.lower() == color_hex.lower())
                border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                # Check if this button is a recent color button (has opacity)
                btn_style = btn.styleSheet()
                if "opacity: 0.9" in btn_style:
                    # Recent color button
                    if not is_current:
                        border = "1px solid #999"
                    btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px; opacity: 0.9;")
                else:
                    # Preset color button
                    btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")

    def _open_shape_color_picker(self) -> None:
        color = QColorDialog.getColor(self.overlay.current_color, self.overlay, _("Select Color"))
        if color.isValid():
            self._set_shape_color(color.name())
            # Color is already added to recent in _set_shape_color

    def _set_text_font(self, font_family: str) -> None:
        self.overlay.text_font_family = font_family

    def _set_text_size(self, size: int) -> None:
        self.overlay.text_font_size = size

    def _toggle_bold(self) -> None:
        self.overlay.text_bold = self._bold_btn.isChecked()

    def _toggle_italic(self) -> None:
        self.overlay.text_italic = self._italic_btn.isChecked()

    def _set_text_color(self, color_hex: str) -> None:
        self.overlay.text_color = QColor(color_hex)

        # Add to recent colors
        settings = get_settings()
        settings.add_recent_color(color_hex)

        # Update button borders with proper styling for recent vs preset colors
        for btn in self._text_color_buttons:
            c = btn.property("color")
            if c:
                is_current = (c.lower() == color_hex.lower())
                border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                # Check if this is a recent color button
                btn_style = btn.styleSheet()
                if "opacity: 0.9" in btn_style:
                    # Recent color button
                    if not is_current:
                        border = "1px solid #999"
                    btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px; opacity: 0.9;")
                else:
                    # Preset color button
                    btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 3px;")

    def _open_color_picker(self) -> None:
        color = QColorDialog.getColor(self.overlay.text_color, self.overlay, _("Select Text Color"))
        if color.isValid():
            self._set_text_color(color.name())
            # Color is already added to recent in _set_text_color

    def update_undo_redo_state(self) -> None:
        self._undo_btn.setEnabled(len(self.overlay.annotations) > 0)
        self._redo_btn.setEnabled(len(self.overlay._redo_stack) > 0)
