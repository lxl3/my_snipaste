"""OCR 测试结果对话框 - Big Sur 风格毛玻璃设计

参考 frosted_glass_demo.py 实现，直接在 self.rect() 绘制，无嵌套结构。
"""

from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
)
from PySide6.QtGui import QPainter

from ..core.i18n import _
from ..core import qss_base
from ..core.theme import theme as _t
from ..core.glass_effect import draw_glass_morphism


class OcrTestDialog(QDialog):
    """OCR 测试结果对话框 - 毛玻璃效果"""

    def __init__(self, success: bool, message: str, details: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(380, 200)

        self._success = success
        self._message = message
        self._details = details
        self._drag_pos = QPoint()

        self._build_ui()
        _t.theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        # 确保子控件背景透明（不影响按钮样式）
        self.setStyleSheet("""
            QWidget#titleBar, QWidget#content, QWidget#footer { background: transparent; }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(14, 0, 6, 0)

        title_label = QLabel(_("OCR Test"))
        title_label.setStyleSheet(_t.qss("font-size: 13px; font-weight: 600; color: $text_primary;"))
        self._title_label = title_label
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(_t.qss("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                color: $text_secondary;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: $hover_bg;
                color: $text_primary;
            }
        """))
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)

        title_bar.mousePressEvent = self._on_title_press
        title_bar.mouseMoveEvent = self._on_title_move

        layout.addWidget(title_bar)

        # 内容区域
        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 8)
        content_layout.setSpacing(8)

        # 状态图标和消息
        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)

        # 圆形图标（跟随主题色）
        icon_label = QLabel("✓" if self._success else "!")
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label = icon_label
        self._apply_icon_style()
        status_layout.addWidget(icon_label)

        message_label = QLabel(self._message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(_t.qss("font-size: 14px; color: $text_primary; font-weight: 500;"))
        self._message_label = message_label
        status_layout.addWidget(message_label, 1)

        content_layout.addLayout(status_layout)

        # 详细信息
        if self._details:
            details_label = QLabel(self._details)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_secondary;"))
            self._details_label = details_label
            content_layout.addWidget(details_label)

        content_layout.addStretch()
        layout.addWidget(content, 1)

        # 底部按钮
        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 14)
        footer_layout.addStretch()

        close_btn = QPushButton(_("OK"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet(qss_base.pushbutton_qss(
            padding="6px 20px",
            border="none",
            border_radius="6px",
            bg="$accent",
            color="$text_accent",
            hover_bg="$accent_hover",
            font_size="13px",
            font_weight="500",
        ))
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)

        layout.addWidget(footer)

    def _apply_icon_style(self) -> None:
        if self._success:
            bg_color = _t.get("accent")
        else:
            bg_color = "#E53935"
        self._icon_label.setStyleSheet(f"""
            QLabel {{
                background: {bg_color};
                color: white;
                font-size: 18px;
                font-weight: bold;
                border-radius: 18px;
            }}
        """)

    # ─── 拖拽 ───────────────────────────────────────────────

    def _on_title_press(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _on_title_move(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    # ─── 绘制 ───────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        draw_glass_morphism(
            painter,
            QRectF(self.rect()),
            radius=12,
            is_dark=_t.is_dark(),
            draw_shadow=False,  # 不画阴影：阴影向外扩展超出窗口边界会被裁剪，且多层黑色在边缘处累积形成黑边
        )

    def _on_theme_changed(self, _mode: str) -> None:
        self._apply_icon_style()
        self._title_label.setStyleSheet(_t.qss("font-size: 13px; font-weight: 600; color: $text_primary;"))
        self._message_label.setStyleSheet(_t.qss("font-size: 14px; color: $text_primary; font-weight: 500;"))
        if hasattr(self, '_details_label'):
            self._details_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_secondary;"))
        self.update()

    def closeEvent(self, event) -> None:
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.close()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def show_result(success: bool, message: str, details: str = "", parent=None) -> None:
        dialog = OcrTestDialog(success, message, details, parent)
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - dialog.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog.height()) // 2
            dialog.move(x, y)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
