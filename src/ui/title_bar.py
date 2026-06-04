"""统一 TitleBar 组件 — 无边框窗口的自定义标题栏，支持拖拽、最小化、关闭。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from ..core.theme import theme as _theme
from ..core import qss_base


class TitleBar(QWidget):
    """自定义无边框标题栏，支持拖拽移动窗口。

    默认样式由父对话框的 QSS 覆盖（如 TitleBar QLabel / TitleBar QPushButton），
    这里只设置基础透明无边框，确保即使是孤立使用也有可读外观。

    用法:
        title_bar = TitleBar(self, _("My Window"))
        title_bar = TitleBar(self, _("My Window"), show_minimize=True)
        title_bar = TitleBar(self, _("My Window"), height=44, close_size=28)
    """

    def __init__(
        self,
        parent: QWidget,
        title: str = "",
        show_minimize: bool = True,
        height: int = 32,
        title_size: str = "13px",
        title_weight: str = "600",
        close_size: int = 32,
        margins: tuple[int, int, int, int] = (12, 0, 4, 0),
    ) -> None:
        super().__init__(parent)
        self._drag_pos = None
        self.setFixedHeight(height)
        self.setAttribute(Qt.WA_StyledBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(2)

        # 标题（颜色由父 QSS 中的 TitleBar QLabel 覆盖）
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            _theme.qss(f"font-size: {title_size}; font-weight: {title_weight}; color: $text_primary;")
        )
        layout.addWidget(self._title_label)
        layout.addStretch()

        # 最小化按钮
        if show_minimize:
            self._min_btn = QPushButton("─")
            self._min_btn.setFixedSize(close_size, max(24, height - 8))
            self._min_btn.setFocusPolicy(Qt.NoFocus)
            self._min_btn.clicked.connect(parent.showMinimized)
            self._min_btn.setCursor(QCursor(Qt.PointingHandCursor))
            self._min_btn.setStyleSheet(self._btn_qss())
            layout.addWidget(self._min_btn)

        # 关闭按钮
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(close_size, max(24, height - 8))
        self._close_btn.setFocusPolicy(Qt.NoFocus)
        self._close_btn.clicked.connect(parent.close)
        self._close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._close_btn.setStyleSheet(self._btn_qss())
        layout.addWidget(self._close_btn)

    @staticmethod
    def _btn_qss() -> str:
        """TitleBar 按钮基础样式（无边框透明，hover 显示背景）。"""
        return _theme.qss("""
            QPushButton {
                background: transparent;
                border: none;
                color: $text_primary;
                font-size: 14px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background: $hover_bg;
            }
            QPushButton:pressed {
                background: $accent;
                color: $text_accent;
            }
        """)

    # ─── 窗口拖拽 ─────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            parent = self.parent()
            if parent is None:
                return
            delta = event.globalPosition().toPoint() - self._drag_pos
            parent.move(parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            event.accept()
