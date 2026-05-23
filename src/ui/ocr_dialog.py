"""OCR result dialog."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QWidget,
)


class OcrResultDialog(QDialog):
    """Minimal OCR result dialog with smart layout."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._setup_window()
        self._build_ui(text)
        self._drag_pos = None
        self._last_selected_text: str = ""

    def _setup_window(self) -> None:
        self.setWindowTitle("OCR 识别结果")
        self.setMinimumSize(450, 250)
        self.setMaximumSize(900, 700)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _build_ui(self, text: str) -> None:
        main_widget = QWidget(self)
        main_widget.setObjectName("mainCard")
        main_widget.setStyleSheet("#mainCard { background: #FFFFFF; border-radius: 16px; border: 1px solid #E5E7EB; }")

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header(text))
        layout.addWidget(self._build_content(text))
        layout.addWidget(self._build_footer())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.addWidget(main_widget)

        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        self._on_text_changed()

    def _build_header(self, text: str) -> QWidget:
        header = QWidget()
        header.setObjectName("header")
        header.setStyleSheet("""
            #header { background: #F9FAFB; border-bottom: 1px solid #E5E7EB;
                      border-top-left-radius: 16px; border-top-right-radius: 16px; padding: 16px 24px; }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)

        title_label = QLabel("识别完成")
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #111827; font-family: 'Segoe UI', 'PingFang SC', sans-serif;")

        self.char_count_label = QLabel()
        self.char_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.char_count_label.setStyleSheet("font-size: 12px; color: #6B7280; font-family: 'Consolas', 'Monaco', monospace;")
        self._update_char_count(text)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet("""
            QPushButton#closeBtn { background: transparent; color: #9CA3AF; border: none; border-radius: 14px; font-size: 14px; font-weight: bold; }
            QPushButton#closeBtn:hover { background: #E5E7EB; color: #374151; }
            QPushButton#closeBtn:pressed { background: #D1D5DB; }
        """)
        close_btn.clicked.connect(self.close_dialog_only)

        header_layout.addWidget(title_label)
        header_layout.addWidget(self.char_count_label)
        header_layout.addWidget(close_btn)
        return header

    def _build_content(self, text: str) -> QWidget:
        content_widget = QWidget()
        content_widget.setObjectName("content")
        content_widget.setStyleSheet("#content { background: #FFFFFF; padding: 20px 24px; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        hint_label = QLabel("您可以直接编辑或选择下方文本：")
        hint_label.setStyleSheet("color: #9CA3AF; font-size: 12px; margin-bottom: 8px;")
        content_layout.addWidget(hint_label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text if text else "(未检测到文字)")
        self.text_edit.setReadOnly(False)
        self.text_edit.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.text_edit.setFocusPolicy(Qt.StrongFocus)
        self.text_edit.setStyleSheet("""
            QTextEdit { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px;
                        font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace; font-size: 13px; color: #374151;
                        line-height: 1.6; selection-background-color: #3B82F6; selection-color: #FFFFFF; }
            QTextEdit:focus { border-color: #3B82F6; background: #FFFFFF; }
            QTextEdit:disabled { background: #F9FAFB; color: #9CA3AF; }
        """)
        self._adjust_text_edit_size(text)
        content_layout.addWidget(self.text_edit)
        return content_widget

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("footer")
        footer.setStyleSheet("""
            #footer { background: #F9FAFB; border-top: 1px solid #E5E7EB;
                      border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; padding: 16px 24px; }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self._copy_and_close_editor)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton { background: #111827; color: #FFFFFF; border: 1px solid #111827; border-radius: 8px;
                          padding: 10px 32px; font-size: 13px; font-weight: 600; }
            QPushButton:hover { background: #374151; border-color: #374151; }
            QPushButton:pressed { background: #030712; }
        """)
        footer_layout.addWidget(self.copy_btn)
        return footer

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(100, self.text_edit.setFocus)

    def close_dialog_only(self) -> None:
        # save selected text before closing
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())
        self.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)

    def _adjust_text_edit_size(self, text: str) -> None:
        if not text:
            self.text_edit.setFixedHeight(80)
            return

        line_count = text.count('\n') + 1
        char_count = len(text)

        # estimate height: ~22px per line + padding
        line_count = text.count('\n') + 1
        estimated_height = line_count * 22 + 40

        min_height = 100
        max_height = 450

        final_height = max(min_height, min(estimated_height, max_height))
        self.text_edit.setFixedHeight(final_height)

        # smart scrollbars
        if char_count < 150:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _update_char_count(self, text: str) -> None:
        if not text:
            self.char_count_label.setText("0 字符")
            return

        char_count = len(text)
        line_count = text.count('\n') + 1

        if char_count < 1000:
            self.char_count_label.setText(f"{char_count} 字符 · {line_count} 行")
        else:
            self.char_count_label.setText(f"{char_count / 1000:.1f}K 字符 · {line_count} 行")

    def _on_text_changed(self) -> None:
        text = self.text_edit.toPlainText()
        self._update_char_count(text)

    def _on_selection_changed(self) -> None:
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            self._last_selected_text = cursor.selectedText()
        # do NOT clear; keep selected text when focus is lost

    def _copy_and_close_editor(self) -> None:
        text = self._last_selected_text
        if not text:
            text = self.text_edit.toPlainText()

        if text:
            QApplication.clipboard().setText(text)
            self._show_copy_feedback("已复制")

        if self.parent():
            QTimer.singleShot(300, self.parent().close)
        QTimer.singleShot(300, self.accept)

    def _show_copy_feedback(self, message: str) -> None:
        original_text = self.copy_btn.text()
        self.copy_btn.setText(f"[OK] {message}")
        self.copy_btn.setEnabled(False)
