from PySide6.QtCore import Qt, QTimer, QEvent, QPoint
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QWidget,
)
from ..core.i18n import _


class _TitleBar(QWidget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)

        title = QLabel(_("Recognition Result"))
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(lambda: self.window().close())
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #9CA3AF; border: none; border-radius: 14px; font-size: 14px;
            }
            QPushButton:hover { background: #F3F4F6; color: #374151; }
            QPushButton:pressed { background: #E5E7EB; }
        """)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(close_btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            win = self.window()
            self._drag_pos = event.globalPosition().toPoint() - win.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            win = self.window()
            win.move(event.globalPosition().toPoint() - self._drag_pos)


class OcrResultDialog(QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(460, 260)
        self.setMaximumSize(920, 700)

        self._last_selected_text: str = ""

        self._build_ui(text)

        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        self._on_text_changed()
        QTimer.singleShot(0, self.text_edit.setFocus)

    def _build_ui(self, text: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet("""
            #card {
                background: #FFFFFF;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_layout.addWidget(_TitleBar(self.windowTitle(), self))
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
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border: none;
                border-top: 1px solid #F3F4F6;
                border-bottom: 1px solid #F3F4F6;
                padding: 16px 20px;
                font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
                font-size: 14px;
                color: #111827;
                background: #FFFFFF;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
            }
            QTextEdit:focus {
                background: #FAFBFC;
            }
        """)
        self._adjust_text_edit_size(text)
        return self.text_edit

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 10, 20, 10)
        footer.setSpacing(12)

        self.char_count_label = QLabel()
        self.char_count_label.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        footer.addWidget(self.char_count_label)
        footer.addStretch()

        self.copy_btn = QPushButton(_("Copy Text"))
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 22px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #1D4ED8; }
            QPushButton:pressed { background: #1E40AF; }
        """)
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
