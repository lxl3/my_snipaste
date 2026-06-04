from PySide6.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QWidget, QGraphicsOpacityEffect,
)
from PySide6.QtGui import QPainter, QColor, QLinearGradient
from ..core.i18n import _
from ..core import qss_base
from ..core.theme import theme as _t
from .title_bar import TitleBar


class OcrResultDialog(QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 确保移动时正确更新
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setMinimumSize(460, 260)
        self.setMaximumSize(920, 700)

        self._last_selected_text: str = ""

        self._build_ui(text)
        self._setup_entrance_animation()

        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        self._on_text_changed()
        QTimer.singleShot(0, self.text_edit.setFocus)

        # 监听主题变化
        _t.theme_changed.connect(self._on_theme_changed)

    def _build_ui(self, text: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("card")
        # Glass effect background will be drawn in paintEvent
        card.setAttribute(Qt.WA_StyledBackground, False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_layout.addWidget(TitleBar(
            self, title=_("Recognition Result"), show_minimize=False,
            height=44, title_size="14px", close_size=28,
            margins=(16, 0, 8, 0),
        ))
        card_layout.addWidget(self._build_content(text), 1)
        card_layout.addLayout(self._build_footer())

        root.addWidget(card)

        self._card = card

    def _build_content(self, text: str) -> QTextEdit:
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text if text else _("(no text detected)"))
        self.text_edit.setReadOnly(False)
        self.text_edit.setTabChangesFocus(True)
        self.text_edit.installEventFilter(self)
        # 组合 QTextEdit 样式 + 滚动条样式
        text_edit_style = """
            QTextEdit {
                border: none;
                border-top: 1px solid palette(mid);
                border-bottom: 1px solid palette(mid);
                padding: 16px 20px;
                font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
                font-size: 14px;
                color: palette(text);
                background: palette(base);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
            QTextEdit:focus {
                background: palette(alternate-base);
            }
        """
        self.text_edit.setStyleSheet(text_edit_style + qss_base.scrollbar_qss())
        self._adjust_text_edit_size(text)
        return self.text_edit

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 10, 20, 10)
        footer.setSpacing(12)

        self.char_count_label = QLabel()
        self.char_count_label.setStyleSheet(qss_base.label_qss(font_size="12px", color="palette(mid)"))
        footer.addWidget(self.char_count_label)
        footer.addStretch()

        self.copy_btn = QPushButton(_("Copy Text"))
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet(qss_base.pushbutton_qss(
            padding="7px 22px",
            border="none",
            border_radius="6px",
            bg="$accent",
            color="$text_accent",
            hover_bg="$accent_hover",
            pressed_bg="$accent_hover",
            font_size="13px",
            font_weight="500"
        ))
        self.copy_btn.clicked.connect(self._copy_and_close)
        footer.addWidget(self.copy_btn)

        return footer

    def _adjust_text_edit_size(self, text: str) -> None:
        if not text:
            self.text_edit.setFixedHeight(100)
            return
        n = text.count("\n") + 1
        h = max(120, min(n * 22 + 32, 400))
        self.text_edit.setFixedHeight(h)
        if len(text) < 150:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _update_char_count(self, text: str) -> None:
        c = len(text)
        n = text.count("\n") + 1 if text else 0
        if c < 1000:
            self.char_count_label.setText(_("{count} chars · {lines} lines").format(count=c, lines=n))
        else:
            self.char_count_label.setText(_("{count}K chars · {lines} lines").format(count=c / 1000, lines=n))

    def _on_text_changed(self) -> None:
        self._update_char_count(self.text_edit.toPlainText())

    def _on_selection_changed(self) -> None:
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            self._last_selected_text = cursor.selectedText()

    def _copy_and_close(self) -> None:
        text = self._last_selected_text or self.text_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
        if self.parent():
            QTimer.singleShot(300, self.parent().close)
        QTimer.singleShot(300, self.accept)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.text_edit and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_C and (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
                text = self.text_edit.textCursor().selectedText() or self.text_edit.toPlainText()
                if text:
                    QApplication.clipboard().setText(text)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.accept()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Return:
            self._copy_and_close()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_W:
            self.accept()
        else:
            super().keyPressEvent(event)

    def _setup_entrance_animation(self) -> None:
        """设置入场动画（淡入）"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(250)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event) -> None:
        """显示时播放入场动画"""
        super().showEvent(event)
        if hasattr(self, '_fade_in'):
            self._fade_in.start()

    def paintEvent(self, event) -> None:
        """绘制玻璃效果背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 清除整个窗口背景（解决残影）
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # 获取card widget的位置和大小（相对于dialog）
        rect = self._card.geometry()

        # 构造渐变背景（模拟工具栏玻璃效果）
        try:
            bg_hex = _t.get("bg_toolbar", "#FFFFFFD7")
            r = int(bg_hex[1:3], 16)
            g = int(bg_hex[3:5], 16)
            b = int(bg_hex[5:7], 16)
            a = int(bg_hex[7:9], 16) if len(bg_hex) == 9 else 215

            top_a = min(a + 25, 255)
            bottom_a = max(a - 35, 0)

            # 渐变使用相对于rect的坐标
            gradient = QLinearGradient(rect.x(), rect.y(), rect.x(), rect.y() + rect.height())
            gradient.setColorAt(0, QColor(r, g, b, top_a))
            gradient.setColorAt(1, QColor(r, g, b, bottom_a))
            painter.setBrush(gradient)
        except Exception:
            painter.setBrush(QColor(_t.get("bg_toolbar", "#FFFFFFD7")))

        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 12, 12)

        # 边框高光（顶部亮，底部暗）
        is_dark = _t.is_dark()
        if is_dark:
            top_color = QColor(255, 255, 255, 60)
            bottom_color = QColor(0, 0, 0, 120)
            border_color = QColor(90, 90, 90, 100)
        else:
            top_color = QColor(255, 255, 255, 220)
            bottom_color = QColor(0, 0, 0, 40)
            border_color = QColor(128, 128, 128, 70)

        # 主边框
        painter.setPen(border_color)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 12, 12)

        # 顶部高光 - 使用rect的坐标
        painter.setPen(top_color)
        painter.drawLine(rect.x() + 12, rect.y(), rect.x() + rect.width() - 12, rect.y())
        painter.drawLine(rect.x() + 12, rect.y() + 1, rect.x() + rect.width() - 12, rect.y() + 1)

        # 底部阴影 - 使用rect的坐标
        painter.setPen(bottom_color)
        painter.drawLine(rect.x() + 12, rect.y() + rect.height() - 1,
                        rect.x() + rect.width() - 12, rect.y() + rect.height() - 1)

    def _on_theme_changed(self, _mode: str) -> None:
        """主题切换时刷新"""
        self.update()

    def closeEvent(self, event) -> None:
        """关闭时清理"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)
