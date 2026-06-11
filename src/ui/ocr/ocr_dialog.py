"""OCR 识别结果对话框 - Big Sur 风格毛玻璃设计

参考 frosted_glass_demo.py 实现，直接在 self.rect() 绘制，无嵌套结构。
"""

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import qss_base
from ...core.i18n import _
from ...core.theme_pkg import draw_glass_morphism
from ...core.theme_pkg import theme as _t


class OcrResultDialog(QDialog):
    """OCR 结果对话框 - 毛玻璃效果，参考 frosted_glass_demo 实现"""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(460, 260)
        self.setMaximumSize(920, 700)

        self._drag_pos = QPoint()
        self._last_selected_text: str = ""

        self._build_ui(text)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        self._on_text_changed()
        QTimer.singleShot(0, self.text_edit.setFocus)

        _t.theme_changed.connect(self._on_theme_changed)
        self.setMouseTracking(True)

    def _build_ui(self, text: str) -> None:
        # 确保子控件背景透明
        self.setStyleSheet("""
            QWidget#titleBar, QWidget#footer { background: transparent; }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏区域
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(44)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 8, 0)

        title_label = QLabel(_("Recognition Result"))
        title_label.setStyleSheet(_t.qss("font-size: 14px; font-weight: 600; color: $text_primary;"))
        self._title_label = title_label
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(_t.qss("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 18px;
                color: $text_secondary;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: $hover_bg;
                color: $text_primary;
            }
        """))
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)

        # 启用标题栏拖拽
        title_bar.mousePressEvent = self._on_title_press
        title_bar.mouseMoveEvent = self._on_title_move
        self._title_bar = title_bar

        layout.addWidget(title_bar)

        # 文本编辑区
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text if text else _("(no text detected)"))
        self.text_edit.setReadOnly(False)
        self.text_edit.setTabChangesFocus(True)
        self.text_edit.installEventFilter(self)
        self.text_edit.setStyleSheet(_t.qss("""
            QTextEdit {
                border: none;
                border-top: 1px solid $border;
                border-bottom: 1px solid $border;
                padding: 16px 20px;
                font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
                font-size: 14px;
                color: $text_primary;
                background: transparent;
                selection-background-color: $accent;
                selection-color: $text_accent;
            }
        """) + qss_base.scrollbar_qss())
        self._adjust_text_edit_size(text)
        layout.addWidget(self.text_edit, 1)

        # 底部栏
        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 14)
        footer_layout.setSpacing(12)

        self.char_count_label = QLabel()
        self.char_count_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_placeholder;"))
        self._char_count_label = self.char_count_label
        footer_layout.addWidget(self.char_count_label)
        footer_layout.addStretch()

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
        footer_layout.addWidget(self.copy_btn)

        layout.addWidget(footer)

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
        QTimer.singleShot(300, self.close)

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
            self.close()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Return:
            self._copy_and_close()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_W:
            self.close()
        else:
            super().keyPressEvent(event)

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

        # 直接在整个窗口绘制毛玻璃效果
        draw_glass_morphism(
            painter,
            QRectF(self.rect()),
            radius=12,
            is_dark=_t.is_dark(),
            draw_shadow=True,
        )

    def _on_theme_changed(self, _mode: str) -> None:
        self._title_label.setStyleSheet(_t.qss("font-size: 14px; font-weight: 600; color: $text_primary;"))
        self._char_count_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_placeholder;"))
        self.update()

    def closeEvent(self, event) -> None:
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)
