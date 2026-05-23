from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QToolButton, QMenu, QWidget,
    QLabel, QPushButton, QSpinBox, QWidgetAction,
)
from PySide6.QtGui import QAction, QColor
from PySide6.QtCore import Qt, QSize

from ..resources.icons.toolbar_icons import TOOLBAR_ICONS
from ..core.utils import load_icon_from_svg
from ..core.constants import TOOLBAR_HEIGHT, PRESET_COLORS


class EditorToolbar:
    def __init__(self, editor) -> None:
        self.editor = editor
        self.toolbar: QFrame | None = None
        self.tool_buttons: dict[str, QToolButton] = {}
        self._tool_group_map: dict = {}

    def setup(self) -> None:
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

        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(1)

        tools = [
            ("select", "选择"), ("rect", "矩形"), ("ellipse", "圆形"),
            ("arrow", "箭头"), ("line", "线条"), ("freehand", "画笔"),
            ("mosaic", "马赛克"), ("text", "文字"),
        ]
        for tool_id, label in tools:
            btn = self._make_tool_btn(tool_id)
            btn.setToolTip(label)
            btn.clicked.connect(lambda checked, t=tool_id: self.editor.view.set_tool(t))
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool_clicked(t, btn))
            layout.addWidget(btn)
            self.tool_buttons[tool_id] = btn

        layout.addWidget(self._make_separator())
        self.undo_btn = self._make_undo_btn()
        layout.addWidget(self.undo_btn)
        self.redo_btn = self._make_redo_btn()
        layout.addWidget(self.redo_btn)

    def _make_tool_btn(self, tool_id) -> QToolButton:
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon = load_icon_from_svg(TOOLBAR_ICONS.get(tool_id, ""), "#333333", size=16)
        btn.setIcon(icon)
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(22, 22)
        btn.setCheckable(True)
        return btn

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #ddd;")
        sep.setFixedWidth(1)
        return sep

    def _make_undo_btn(self) -> QToolButton:
        btn = QToolButton()
        btn.setText("↩")
        btn.setToolTip("撤销 (Ctrl+Z)")
        btn.setFixedSize(22, 22)
        btn.clicked.connect(self.editor._undo)
        btn.setEnabled(False)
        return btn

    def _make_redo_btn(self) -> QToolButton:
        btn = QToolButton()
        btn.setText("↪")
        btn.setToolTip("重做 (Ctrl+Y)")
        btn.setFixedSize(22, 22)
        btn.clicked.connect(self.editor._redo)
        btn.setEnabled(False)
        return btn

    def _on_tool_clicked(self, tool_id: str, btn) -> None:
        for tid, b in self.tool_buttons.items():
            b.setChecked(tid == tool_id)

    def update_undo_redo_state(self) -> None:
        if hasattr(self, 'undo_btn') and self.undo_btn:
            self.undo_btn.setEnabled(bool(self.editor.undo_stack))
        if hasattr(self, 'redo_btn') and self.redo_btn:
            self.redo_btn.setEnabled(bool(self.editor.redo_stack))
