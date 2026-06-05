"""OCR 测试结果对话框 - Big Sur 风格毛玻璃设计"""

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QWidget, QGraphicsOpacityEffect, QLabel,
)
from PySide6.QtGui import QPainter

from ..core.i18n import _
from ..core import qss_base
from ..core.theme import theme as _t
from ..core.glass_effect import draw_glass_morphism
from .title_bar import TitleBar


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

        self._build_ui()
        self._setup_entrance_animation()

        _t.theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("card")
        card.setAttribute(Qt.WA_StyledBackground, False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 标题栏
        card_layout.addWidget(TitleBar(
            self, title=_("OCR Test"), show_minimize=False,
            height=40, title_size="13px", close_size=24,
            margins=(14, 0, 6, 0),
        ))

        # 内容区域
        card_layout.addWidget(self._build_content(), 1)

        # 底部按钮
        card_layout.addLayout(self._build_footer())

        root.addWidget(card)
        self._card = card

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 8)
        layout.setSpacing(8)

        # 状态图标和消息
        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)

        icon_label = QLabel("✅" if self._success else "⚠️")
        icon_label.setStyleSheet("font-size: 28px;")
        status_layout.addWidget(icon_label)

        message_label = QLabel(self._message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(qss_base.label_qss(
            font_size="14px",
            color="$text_primary",
            font_weight="500",
        ))
        status_layout.addWidget(message_label, 1)

        layout.addLayout(status_layout)

        # 详细信息
        if self._details:
            details_label = QLabel(self._details)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(qss_base.label_qss(
                font_size="12px",
                color="$text_secondary",
            ))
            layout.addWidget(details_label)

        layout.addStretch()
        return content

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 8, 20, 14)
        footer.addStretch()

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
        footer.addWidget(close_btn)

        return footer

    def _setup_entrance_animation(self) -> None:
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_fade_in'):
            self._fade_in.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self._card.geometry()
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=12,
            is_dark=_t.is_dark(),
            draw_shadow=True,
            shadow_intensity=0.5,
        )

    def _on_theme_changed(self, _mode: str) -> None:
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
        """显示 OCR 测试结果"""
        dialog = OcrTestDialog(success, message, details, parent)
        # 居中于父窗口
        if parent:
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - dialog.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog.height()) // 2
            dialog.move(x, y)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
