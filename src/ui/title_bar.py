"""统一 TitleBar 组件 — 无边框窗口的自定义标题栏，支持拖拽、最小化、关闭。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..core.theme_pkg import theme as _theme


class TitleBar(QWidget):
    """自定义无边框标题栏，支持拖拽移动窗口。

    自动跟随主题切换（暗色/亮色），关闭销毁时断开信号连接。

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
        enable_drag: bool = True,
    ) -> None:
        super().__init__(parent)
        self._drag_pos = None
        self._enable_drag = enable_drag
        self.setFixedHeight(height)
        self.setAttribute(Qt.WA_StyledBackground)

        # 保存参数供主题刷新时重写 QSS 使用
        self._title_size = title_size
        self._title_weight = title_weight

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(2)

        # 标题
        self._title_label = QLabel(title)
        layout.addWidget(self._title_label)
        layout.addStretch()

        # 最小化按钮
        if show_minimize:
            self._min_btn = QPushButton("─")
            self._min_btn.setFixedSize(close_size, max(24, height - 8))
            self._min_btn.setFocusPolicy(Qt.NoFocus)
            self._min_btn.clicked.connect(parent.showMinimized)
            self._min_btn.setCursor(QCursor(Qt.PointingHandCursor))
            layout.addWidget(self._min_btn)

        # 关闭按钮
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(close_size, max(24, height - 8))
        self._close_btn.setFocusPolicy(Qt.NoFocus)
        self._close_btn.clicked.connect(parent.close)
        self._close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(self._close_btn)

        # 首次应用主题 QSS
        self._refresh_style()

        # 监听主题切换
        _theme.theme_changed.connect(self._on_theme_changed)

    # ─── 主题感知 ───────────────────────────────────────

    def _refresh_style(self) -> None:
        """根据当前主题重新生成标题和按钮的 QSS。"""
        self._title_label.setStyleSheet(
            _theme.qss(
                f"font-size: {self._title_size}; "
                f"font-weight: {self._title_weight}; "
                f"color: $text_primary;"
            )
        )
        btn_qss = self._btn_qss()
        if hasattr(self, '_min_btn'):
            self._min_btn.setStyleSheet(btn_qss)
        self._close_btn.setStyleSheet(btn_qss)

    def _on_theme_changed(self, mode: str) -> None:
        """主题切换时刷新 TitleBar 内联 QSS。"""
        self._refresh_style()

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

    # ─── 生命周期 ───────────────────────────────────────

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True) -> None:
        """断开主题信号连接后销毁。"""
        try:
            _theme.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)

    # ─── 窗口拖拽 ─────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if self._enable_drag and event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._enable_drag and event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            parent = self.parent()
            if parent is None:
                return
            delta = event.globalPosition().toPoint() - self._drag_pos
            parent.move(parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._enable_drag and event.button() == Qt.LeftButton:
            self._drag_pos = None
            event.accept()
