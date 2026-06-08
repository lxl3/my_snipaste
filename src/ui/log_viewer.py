"""日志查看器对话框 - Big Sur 风格毛玻璃设计

参考 frosted_glass_demo.py 实现，直接在 self.rect() 绘制，无嵌套结构。
"""

import os
import platform
import subprocess

from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
)
from PySide6.QtGui import QPainter

from ..core.i18n import _
from ..core import qss_base
from ..core.theme import theme as _t
from ..core.glass_effect import draw_glass_morphism
from ..core.logger import get_log_dir, get_current_log_path


class LogViewerDialog(QDialog):
    """日志查看器 - 非模态、毛玻璃效果"""

    _instance: "LogViewerDialog | None" = None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(700, 450)
        self.resize(800, 550)

        self._drag_pos = QPoint()

        self._build_ui()
        self._load_log()

        _t.theme_changed.connect(self._on_theme_changed)

    def _build_ui(self) -> None:
        # 确保子控件背景透明
        self.setStyleSheet("""
            QWidget#titleBar, QWidget#footer { background: transparent; }
            QLabel { background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(44)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 8, 0)

        title_label = QLabel(_("MySnipaste Log"))
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

        title_bar.mousePressEvent = self._on_title_press
        title_bar.mouseMoveEvent = self._on_title_move

        layout.addWidget(title_bar)

        # 日志内容
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self._text_edit.setStyleSheet(_t.qss("""
            QTextEdit {
                border: none;
                border-top: 1px solid $border;
                border-bottom: 1px solid $border;
                padding: 12px 16px;
                font-family: "Consolas", "SF Mono", "Monaco", "Menlo", monospace;
                font-size: 12px;
                color: $text_primary;
                background: transparent;
                selection-background-color: $accent;
                selection-color: $text_accent;
            }
        """) + qss_base.scrollbar_qss())
        layout.addWidget(self._text_edit, 1)

        # 底部按钮栏
        footer = QWidget()
        footer.setObjectName("footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.setSpacing(12)

        self._path_label = QLabel()
        self._path_label.setStyleSheet(_t.qss("font-size: 11px; color: $text_secondary;"))
        footer_layout.addWidget(self._path_label, 1)

        refresh_btn = QPushButton(_("Refresh"))
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(qss_base.pushbutton_qss(
            padding="6px 16px",
            border="1px solid $border",
            border_radius="6px",
            bg="transparent",
            color="$text_primary",
            hover_bg="$hover_bg",
            font_size="13px",
        ))
        refresh_btn.clicked.connect(self._load_log)
        footer_layout.addWidget(refresh_btn)

        open_label = _("Open in Explorer") if platform.system() == "Windows" else _("Open in Finder")
        open_btn = QPushButton(open_label)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setStyleSheet(qss_base.pushbutton_qss(
            padding="6px 16px",
            border="1px solid $border",
            border_radius="6px",
            bg="transparent",
            color="$text_primary",
            hover_bg="$hover_bg",
            font_size="13px",
        ))
        open_btn.clicked.connect(self._open_log_dir)
        footer_layout.addWidget(open_btn)

        close_btn2 = QPushButton(_("Close"))
        close_btn2.setCursor(Qt.PointingHandCursor)
        close_btn2.setStyleSheet(qss_base.pushbutton_qss(
            padding="6px 20px",
            border="none",
            border_radius="6px",
            bg="$accent",
            color="$text_accent",
            hover_bg="$accent_hover",
            font_size="13px",
            font_weight="500",
        ))
        close_btn2.clicked.connect(self.close)
        footer_layout.addWidget(close_btn2)

        layout.addWidget(footer)

    def _load_log(self) -> None:
        path = get_current_log_path()
        if not path:
            self._text_edit.setPlainText(_("No log files yet"))
            self._path_label.setText("")
            return

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self._text_edit.setPlainText(content if content else _("(empty)"))
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self._text_edit.setPlainText(_("Failed to read log: {error}").format(error=e))

        self._path_label.setText(path)

    def _open_log_dir(self) -> None:
        log_dir = get_log_dir()
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", log_dir], check=True)
            elif platform.system() == "Windows":
                os.startfile(log_dir)
            else:
                subprocess.run(["xdg-open", log_dir], check=True)
        except Exception:
            pass

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
            draw_shadow=True,
        )

    def _on_theme_changed(self, _mode: str) -> None:
        self._title_label.setStyleSheet(_t.qss("font-size: 14px; font-weight: 600; color: $text_primary;"))
        self._path_label.setStyleSheet(_t.qss("font-size: 11px; color: $text_secondary;"))
        self.update()

    def closeEvent(self, event) -> None:
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        LogViewerDialog._instance = None
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_W:
            self.close()
        else:
            super().keyPressEvent(event)

    @classmethod
    def show_viewer(cls, parent=None) -> "LogViewerDialog":
        if cls._instance is not None:
            cls._instance.raise_()
            cls._instance.activateWindow()
            cls._instance._load_log()
            return cls._instance

        dialog = cls(parent)
        cls._instance = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog
