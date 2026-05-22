from PySide6.QtWidgets import (
    QWidget, QApplication, QToolButton, QFrame, QHBoxLayout, QMenu,
    QWidgetAction, QPushButton, QSpinBox, QVBoxLayout,
    QComboBox, QColorDialog,
)
from PySide6.QtGui import QColor, QIcon, QFontDatabase
from PySide6.QtCore import Qt, QPoint, QSize, QObject

from ..resources.icons.toolbar_icons import TOOLBAR_ICONS
from ..core.utils import load_icon_from_svg
from ..core.constants import (
    PRESET_COLORS, TEXT_PRESET_COLORS, ICON_SIZE_SMALL, ICON_SIZE_MENU,
    ICON_SIZE_BTN, DEFAULT_ANNOTATION_COLOR, DEFAULT_LINE_WIDTH,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE,
)
from ..core.logger import setup_logger

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
    QToolButton[arrow="true"]::menu-indicator {
        subcontrol-position: right center;
        subcontrol-origin: padding;
        width: 0px;
    }
"""


class OverlayToolbar(QObject):
    """截图覆盖层顶端的浮动工具栏"""

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.toolbar = None
        self._tool_btns = {}
        self._submenu_widgets = []
        self._color_picker_btn = None
        self._width_spinbox = None
        self._font_combo = None
        self._font_size_spin = None
        self._bold_btn = None
        self._italic_btn = None
        self._undo_btn = None
        self._redo_btn = None

    def setup(self):
        self.toolbar = QFrame(self.overlay)
        self.toolbar.setObjectName("overlayToolbar")
        self.toolbar.setFixedHeight(54)
        self.toolbar.setStyleSheet("""
            #overlayToolbar {
                background: white;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
        """)
        self.toolbar.setAttribute(Qt.WA_ShowWithoutActivating)
        self.toolbar.setFocusPolicy(Qt.NoFocus)
        self.toolbar.hide()

        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        tools = [
            ("select", "选择"),
            ("rect", "矩形"),
            ("ellipse", "圆形"),
            ("arrow", "箭头"),
            ("line", "线条"),
            ("freehand", "画笔"),
            ("mosaic", "马赛克"),
            ("text", "文字"),
            ("eraser", "橡皮擦"),
        ]
        for tool_id, label in tools:
            if tool_id == "arrow":
                self._add_submenu_btn(layout, "arrow", "箭头",
                    self._build_arrow_menu)
            elif tool_id == "line":
                self._add_submenu_btn(layout, "line", "线条",
                    self._build_line_menu)
            elif tool_id == "freehand":
                self._add_submenu_btn(layout, "freehand", "画笔",
                    self._build_pen_menu)
            elif tool_id == "text":
                self._add_submenu_btn(layout, "text", "文字",
                    self._build_text_menu)
            elif tool_id == "eraser":
                self._add_submenu_btn(layout, "eraser", "擦除",
                    self._build_eraser_menu)
            else:
                self._add_tool_btn(layout, tool_id, label)

        layout.addWidget(self._make_separator())

        self._color_picker_btn = self._make_color_btn()
        layout.addWidget(self._color_picker_btn)

        self._undo_btn = self._make_undo_btn()
        layout.addWidget(self._undo_btn)
        self._redo_btn = self._make_redo_btn()
        layout.addWidget(self._redo_btn)

        self._width_spinbox = self._make_width_spin()
        layout.addWidget(self._width_spinbox)

        layout.addWidget(self._make_separator())

        self.toolbar.installEventFilter(self.overlay)
        for child in self.toolbar.findChildren(QWidget):
            child.installEventFilter(self.overlay)

    def _make_tool_btn(self, tool_id, color=None, size=ICON_SIZE_BTN) -> QToolButton:
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon = load_icon_from_svg(TOOLBAR_ICONS.get(tool_id, ""), color or "#333333", size)
        btn.setIcon(icon)
        btn.setIconSize(QSize(size, size))
        btn.setFixedSize(36, 36)
        btn.setCheckable(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent; border-radius: 6px;
                background: transparent; padding: 2px; margin: 0px;
            }
            QToolButton:hover { background: #e8e8e8; }
            QToolButton:checked { background: #d0e4ff; border-color: #207ff0; }
        """)
        return btn

    def _add_tool_btn(self, layout, tool_id, label):
        btn = self._make_tool_btn(tool_id)
        btn.setToolTip(label)
        btn.clicked.connect(lambda checked, t=tool_id: self.overlay._on_tool_selected(t))
        layout.addWidget(btn)
        self._tool_btns[tool_id] = btn

    def _make_submenu_btn(self, tool_id, color=None, size=ICON_SIZE_BTN, tool_ids=None) -> QToolButton:
        btn = QToolButton()
        btn.setProperty("arrow", True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon = load_icon_from_svg(TOOLBAR_ICONS.get(tool_id, ""), color or "#333333", size)
        btn.setIcon(icon)
        btn.setIconSize(QSize(size, size))
        btn.setFixedSize(36, 36)
        btn.setCheckable(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(SUBMENU_STYLE)
        if tool_ids:
            btn.setProperty("tool_ids", tool_ids)
        return btn

    def _toggle_or_open_menu(self, menu, button, tool_ids):
        """子菜单主按钮：当前有子工具激活时切换回 select，否则打开菜单"""
        if not isinstance(tool_ids, (list, tuple)):
            tool_ids = [tool_ids]
        any_active = any(
            self._tool_btns.get(tid, button).isChecked()
            for tid in tool_ids
        )
        if any_active:
            self.overlay._on_tool_selected("select")
        else:
            menu.exec(button.mapToGlobal(QPoint(0, button.height())))

    def _add_submenu_btn(self, layout, tool_id, label, build_menu_fn):
        menu = QMenu(self.overlay)
        menu.setStyleSheet("""
            QMenu {
                background: white; border: 1px solid #ccc; border-radius: 4px;
                padding: 4px;
            }
        """)
        build_menu_fn(menu)

        # 确定关联 tool_ids
        tool_ids = []
        if tool_id == "arrow":
            tool_ids = ["arrow", "arrow_noline"]
        elif tool_id == "line":
            tool_ids = ["line", "line_noline"]
        elif tool_id == "eraser":
            tool_ids = ["eraser_dot", "eraser_fill"]
        elif tool_id in ("freehand", "text"):
            tool_ids = [tool_id]

        btn = self._make_submenu_btn(tool_id, tool_ids=tool_ids)
        btn.setToolTip(label)
        btn.clicked.connect(lambda checked, m=menu, b=btn, tids=tool_ids: self._toggle_or_open_menu(m, b, tids))
        btn.setMenu(menu)
        layout.addWidget(btn)
        self._tool_btns[tool_id] = btn

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #ddd; margin: 4px 2px;")
        sep.setFixedWidth(1)
        return sep

    def _make_color_btn(self) -> QToolButton:
        btn = QToolButton()
        btn.setFixedSize(36, 36)
        btn.setToolTip("颜色")
        color = self.overlay.current_color
        btn.setStyleSheet(f"""
            QToolButton {{
                border: 2px solid #ccc; border-radius: 18px;
                background: {color.name()}; padding: 0px; margin: 0px;
            }}
            QToolButton:hover {{ border-color: #207ff0; }}
        """)
        btn.clicked.connect(self._on_color_picker)
        return btn

    def _on_color_picker(self):
        color = QColorDialog.getColor(self.overlay.current_color, None, "选择颜色")
        if color.isValid():
            self.overlay._on_color_changed(color)

    def _make_undo_btn(self) -> QToolButton:
        btn = self._make_tool_btn("undo")
        btn.setToolTip("撤销 (Ctrl+Z)")
        btn.clicked.connect(self.overlay._undo)
        return btn

    def _make_redo_btn(self) -> QToolButton:
        btn = self._make_tool_btn("redo")
        btn.setToolTip("重做 (Ctrl+Y)")
        btn.clicked.connect(self.overlay._redo)
        return btn

    def _make_width_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 20)
        spin.setValue(self.overlay.current_width)
        spin.setFixedWidth(48)
        spin.setFocusPolicy(Qt.NoFocus)
        spin.setStyleSheet("""
            QSpinBox {
                background: #f5f5f5; border: 1px solid #ccc; border-radius: 4px;
                padding: 2px; font-size: 12px;
            }
        """)
        spin.valueChanged.connect(self.overlay._on_width_changed)
        return spin

    def _make_font_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(False)
        combo.setFixedWidth(120)
        combo.setFocusPolicy(Qt.NoFocus)
        combo.setStyleSheet("""
            QComboBox {
                background: white; border: 1px solid #ccc; border-radius: 4px;
                padding: 2px 4px; font-size: 11px;
            }
        """)
        db = QFontDatabase()
        families = db.families()
        common = ["Arial", "Segoe UI", "Microsoft YaHei", "SimHei",
                   "PingFang SC", "Helvetica Neue", "Times New Roman",
                   "Courier New", "Consolas", "Verdana", "Georgia"]
        seen = set()
        for f in common + families:
            if f not in seen:
                combo.addItem(f)
                seen.add(f)
        index = combo.findText(DEFAULT_FONT_FAMILY)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.currentTextChanged.connect(self.overlay._on_font_family_changed)
        return combo

    def _make_font_size_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(8, 120)
        spin.setValue(DEFAULT_FONT_SIZE)
        spin.setFixedWidth(48)
        spin.setFocusPolicy(Qt.NoFocus)
        spin.setStyleSheet("""
            QSpinBox {
                background: #f5f5f5; border: 1px solid #ccc; border-radius: 4px;
                padding: 2px; font-size: 12px;
            }
        """)
        spin.valueChanged.connect(self.overlay._on_font_size_changed)
        return spin

    def update_undo_redo_state(self):
        if self._undo_btn:
            self._undo_btn.setEnabled(len(self.overlay.annotations) > 0)
        if self._redo_btn:
            self._redo_btn.setEnabled(len(self.overlay._redo_stack) > 0)

    def _build_shape_menu(self, menu):
        shape_ids = ["rect", "ellipse"]
        shape_names = ["矩形", "圆形"]
        for sid, sname in zip(shape_ids, shape_names):
            btn = self._make_tool_btn(sid, size=ICON_SIZE_MENU)
            btn.setText(sname)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setFixedSize(72, 28)
            btn.clicked.connect(lambda checked, t=sid: self.overlay._on_tool_selected(t))
            action = QWidgetAction(menu)
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(2, 1, 2, 1)
            wl.addWidget(btn)
            action.setDefaultWidget(w)
            menu.addAction(action)

    def _build_arrow_menu(self, menu):
        arrow_variants = [
            ("arrow", "有箭头"),
            ("arrow_noline", "无箭头"),
        ]
        for tid, tname in arrow_variants:
            btn = self._make_tool_btn(tid, size=ICON_SIZE_MENU)
            btn.setText(tname)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setFixedSize(80, 28)
            btn.clicked.connect(lambda checked, t=tid: self.overlay._on_tool_selected(t))
            action = QWidgetAction(menu)
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(2, 1, 2, 1)
            wl.addWidget(btn)
            action.setDefaultWidget(w)
            menu.addAction(action)

    def _build_line_menu(self, menu):
        line_variants = [
            ("line", "有箭头"),
            ("line_noline", "无箭头"),
        ]
        for tid, tname in line_variants:
            btn = self._make_tool_btn(tid, size=ICON_SIZE_MENU)
            btn.setText(tname)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setFixedSize(80, 28)
            btn.clicked.connect(lambda checked, t=tid: self.overlay._on_tool_selected(t))
            action = QWidgetAction(menu)
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(2, 1, 2, 1)
            wl.addWidget(btn)
            action.setDefaultWidget(w)
            menu.addAction(action)

    def _build_pen_menu(self, menu):
        colors = PRESET_COLORS
        action = QWidgetAction(menu)
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(4, 2, 4, 2)
        wl.setSpacing(4)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(4)
        for c in colors:
            cb = QPushButton()
            cb.setFixedSize(20, 20)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background: {c}; border: 2px solid #ddd; border-radius: 10px;
                }}
                QPushButton:hover {{ border-color: #207ff0; }}
                QPushButton:checked {{ border-color: #207ff0; border-width: 3px; }}
            """)
            cb.setCheckable(True)
            cb.clicked.connect(lambda checked, col=c: self.overlay._on_color_changed(QColor(col)))
            grid_layout.addWidget(cb)
        wl.addLayout(grid_layout)

        spin = QSpinBox()
        spin.setRange(1, 20)
        spin.setValue(self.overlay.current_width)
        spin.setPrefix("粗细: ")
        spin.setFixedWidth(100)
        spin.valueChanged.connect(self.overlay._on_width_changed)
        wl.addWidget(spin)

        action.setDefaultWidget(w)
        menu.addAction(action)

    def _build_text_menu(self, menu):
        action = QWidgetAction(menu)
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(4, 2, 4, 2)
        wl.setSpacing(4)

        self._font_combo = self._make_font_combo()
        wl.addWidget(self._font_combo)

        size_row = QHBoxLayout()
        self._font_size_spin = self._make_font_size_spin()
        size_row.addWidget(self._font_size_spin)

        self._bold_btn = QPushButton("B")
        self._bold_btn.setCheckable(True)
        self._bold_btn.setFixedSize(28, 28)
        self._bold_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; border: 1px solid #ccc; border-radius: 4px;
                background: white;
            }
            QPushButton:checked { background: #207ff0; color: white; }
        """)
        self._bold_btn.clicked.connect(lambda: self.overlay._on_bold_toggled(self._bold_btn.isChecked()))
        size_row.addWidget(self._bold_btn)

        self._italic_btn = QPushButton("I")
        self._italic_btn.setCheckable(True)
        self._italic_btn.setFixedSize(28, 28)
        self._italic_btn.setStyleSheet("""
            QPushButton {
                font-style: italic; font-weight: bold; border: 1px solid #ccc; border-radius: 4px;
                background: white;
            }
            QPushButton:checked { background: #207ff0; color: white; }
        """)
        self._italic_btn.clicked.connect(lambda: self.overlay._on_italic_toggled(self._italic_btn.isChecked()))
        size_row.addWidget(self._italic_btn)

        wl.addLayout(size_row)

        colors_layout = QHBoxLayout()
        colors_layout.setSpacing(4)
        for row_colors in TEXT_PRESET_COLORS:
            for c in row_colors:
                cb = QPushButton()
                cb.setFixedSize(20, 20)
                cb.setStyleSheet(f"""
                    QPushButton {{
                        background: {c}; border: 2px solid #ddd; border-radius: 10px;
                    }}
                    QPushButton:hover {{ border-color: #207ff0; }}
                """)
                cb.clicked.connect(lambda checked, col=c: self.overlay._on_color_changed(QColor(col)))
                colors_layout.addWidget(cb)
        wl.addLayout(colors_layout)

        action.setDefaultWidget(w)
        menu.addAction(action)

    def _build_eraser_menu(self, menu):
        eraser_variants = [
            ("eraser_dot", "点擦除"),
            ("eraser_fill", "填充擦除"),
        ]
        for tid, tname in eraser_variants:
            btn = self._make_tool_btn(tid, size=ICON_SIZE_MENU)
            btn.setText(tname)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setFixedSize(80, 28)
            btn.clicked.connect(lambda checked, t=tid: self.overlay._on_tool_selected(t))
            action = QWidgetAction(menu)
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(2, 1, 2, 1)
            wl.addWidget(btn)
            action.setDefaultWidget(w)
            menu.addAction(action)


