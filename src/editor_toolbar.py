from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QToolButton, QMenu, QWidget,
    QLabel, QPushButton, QSpinBox, QWidgetAction,
)
from PySide6.QtGui import QAction, QColor
from PySide6.QtCore import Qt, QSize

from .resources.icons.toolbar_icons import TOOLBAR_ICONS
from .utils import load_icon_from_svg
from .constants import TOOLBAR_HEIGHT, PRESET_COLORS


class EditorToolbar:
    def __init__(self, editor):
        self.editor = editor
        self.toolbar = None
        self.tool_buttons = {}
        self._tool_group_map = {}

    def setup(self):
        self.toolbar = QFrame()
        self.toolbar.setObjectName("floatingToolbar")
        self.toolbar.setFixedHeight(TOOLBAR_HEIGHT)
        self.toolbar.setStyleSheet("""
            #floatingToolbar { background: white; border: 1px solid #ccc; border-radius: 4px; }
            QToolButton { color: #333; background: transparent; border: 1px solid transparent; border-radius: 3px; padding: 1px 2px; margin: 0px; min-width: 18px; min-height: 18px; }
            QToolButton:hover { background: #e8e8e8; border-color: #ccc; }
            QToolButton:checked { background: #d0e4ff; color: #1a73e8; }
            QSpinBox { background: transparent; color: #333; border: 1px solid #ccc; border-radius: 3px; padding: 2px; font-size: 11px; max-width: 45px; min-height: 22px; }
            QSpinBox::up-button, QSpinBox::down-button { width: 0px; }
        """)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(1, 1, 1, 1)
        toolbar_layout.setSpacing(0)

        self._build_shape_menu(toolbar_layout)
        self._build_arrow_menu(toolbar_layout)
        self._build_pen_menu(toolbar_layout)
        self._build_simple_btn(toolbar_layout, "", "马赛克", "mosaic", "mosaic")
        self._build_simple_btn(toolbar_layout, "", "文字", "text", "text")
        self._build_ocr_btn(toolbar_layout)
        toolbar_layout.addWidget(self._make_separator())
        self._build_undo_btn(toolbar_layout)
        self._build_redo_btn(toolbar_layout)
        toolbar_layout.addWidget(self._make_separator())
        self._build_action_btns(toolbar_layout)

    def _load_icon(self, name, color="#333333"):
        return load_icon_from_svg(TOOLBAR_ICONS.get(name, ""), color, size=16)

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #555;")
        sep.setFixedWidth(1)
        return sep

    def _build_shape_menu(self, layout):
        btn = QToolButton()
        btn.setIcon(self._load_icon("rectangle"))
        btn.setToolTip("形状（矩形/圆形）")
        btn.setIconSize(QSize(16, 16))
        btn.setPopupMode(QToolButton.MenuButtonPopup)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

        menu = QMenu()
        for text, tool in [("▭ 矩形", "rect"), ("○ 圆形", "ellipse")]:
            action = QAction(self._load_icon(tool), text)
            action.triggered.connect(lambda checked, t=tool, b=btn, txt=text: self._on_menu_tool(t, b, txt))
            menu.addAction(action)
            self._tool_group_map[tool] = btn
        btn.setMenu(menu)
        btn.setDefaultAction(menu.actions()[0])
        self.tool_buttons["rect"] = btn
        layout.addWidget(btn)

    def _build_arrow_menu(self, layout):
        btn = QToolButton()
        btn.setIcon(self._load_icon("arrow"))
        btn.setToolTip("箭头（有箭头/无箭头）")
        btn.setIconSize(QSize(16, 16))
        btn.setPopupMode(QToolButton.MenuButtonPopup)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

        menu = QMenu()
        for text, tool in [("➜ 有箭头", "arrow"), ("─ 无箭头", "line")]:
            action = QAction(self._load_icon(tool), text)
            action.triggered.connect(lambda checked, t=tool, b=btn, txt=text: self._on_menu_tool(t, b, txt))
            menu.addAction(action)
            self._tool_group_map[tool] = btn
        btn.setMenu(menu)
        btn.setDefaultAction(menu.actions()[0])
        self.tool_buttons["arrow"] = btn
        layout.addWidget(btn)

    def _build_pen_menu(self, layout):
        btn = QToolButton()
        btn.setIcon(self._load_icon("pen"))
        btn.setToolTip("画笔")
        btn.setIconSize(QSize(16, 16))
        btn.setPopupMode(QToolButton.MenuButtonPopup)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

        menu = QMenu()
        color_widget = QWidget()
        color_layout = QVBoxLayout(color_widget)
        color_layout.setContentsMargins(4, 4, 4, 4)
        color_layout.setSpacing(2)
        color_layout.addWidget(QLabel("颜色"))
        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(2)
        for c in PRESET_COLORS:
            cb = QPushButton()
            cb.setFixedSize(18, 18)
            cb.setStyleSheet(f"background: {c}; border: 1px solid #ccc; border-radius: 2px;")
            cb.clicked.connect(lambda checked, col=c: self._set_pen_color(col))
            grid_layout.addWidget(cb)
        color_layout.addWidget(grid)
        menu.addAction(self._make_widget_action(color_widget))
        menu.addSeparator()

        width_widget = QWidget()
        width_layout = QVBoxLayout(width_widget)
        width_layout.setContentsMargins(4, 4, 4, 4)
        width_layout.setSpacing(2)
        width_layout.addWidget(QLabel("粗细"))
        ws = QSpinBox()
        ws.setRange(1, 20)
        ws.setValue(self.editor.view.current_width)
        ws.setButtonSymbols(QSpinBox.NoButtons)
        ws.valueChanged.connect(lambda v: setattr(self.editor.view, 'current_width', v))
        width_layout.addWidget(ws)
        menu.addAction(self._make_widget_action(width_widget))

        btn.setMenu(menu)
        btn.clicked.connect(lambda: self._on_tool_selected("freehand"))
        self.tool_buttons["freehand"] = btn
        layout.addWidget(btn)

    def _make_widget_action(self, widget):
        action = QWidgetAction(None)
        action.setDefaultWidget(widget)
        return action

    def _build_simple_btn(self, layout, text, tooltip, tool_id, icon_name=None):
        btn = QToolButton()
        if icon_name:
            btn.setIcon(self._load_icon(icon_name))
        else:
            btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setIconSize(QSize(16, 16))
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._on_tool_selected(tool_id))
        self.tool_buttons[tool_id] = btn
        layout.addWidget(btn)

    def _build_ocr_btn(self, layout):
        btn = QToolButton()
        btn.setText("OCR")
        btn.setToolTip("文字识别")
        btn.clicked.connect(self.editor._do_ocr)
        layout.addWidget(btn)

    def _build_undo_btn(self, layout):
        self.editor.undo_btn = QToolButton()
        self.editor.undo_btn.setIcon(self._load_icon("undo"))
        self.editor.undo_btn.setIconSize(QSize(16, 16))
        self.editor.undo_btn.setToolTip("撤销")
        self.editor.undo_btn.setEnabled(False)
        self.editor.undo_btn.clicked.connect(self.editor._undo)
        layout.addWidget(self.editor.undo_btn)

    def _build_redo_btn(self, layout):
        self.editor.redo_btn = QToolButton()
        self.editor.redo_btn.setIcon(self._load_icon("redo"))
        self.editor.redo_btn.setIconSize(QSize(16, 16))
        self.editor.redo_btn.setToolTip("重做")
        self.editor.redo_btn.setEnabled(False)
        self.editor.redo_btn.clicked.connect(self.editor._redo)
        layout.addWidget(self.editor.redo_btn)

    def _build_action_btns(self, layout):
        for icon, tooltip, fn in [
            ("close", "取消（退出截图）", self.editor.close),
            ("pin", "悬浮（钉在桌面上）", self.editor.pin),
            ("save", "保存到文件", self.editor.save_to_file),
            ("copy", "复制到剪贴板", self.editor.copy_to_clipboard),
        ]:
            btn = QToolButton()
            btn.setIcon(self._load_icon(icon))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(tooltip)
            btn.clicked.connect(fn)
            layout.addWidget(btn)

    def _on_menu_tool(self, tool, btn, text):
        btn.setText(text.split(" ")[0] if " " in text else text)
        btn.setChecked(True)
        self.editor.view.set_tool(tool)

    def _on_tool_selected(self, tool):
        self.editor.view.set_tool(tool)
        for tid, btn in self.tool_buttons.items():
            if tid == tool:
                btn.setChecked(True)
            elif btn not in self._tool_group_map.values():
                btn.setChecked(False)
        for parent_tool, group_btn in self._tool_group_map.items():
            group_btn.setChecked(False)
        if tool in self._tool_group_map:
            self._tool_group_map[tool].setChecked(True)

    def _set_pen_color(self, color_hex):
        self.editor.view.current_color = QColor(color_hex)
