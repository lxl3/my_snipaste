"""日志查看器对话框 - Big Sur 风格毛玻璃设计"""

import os
import platform
import subprocess

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QWidget, QGraphicsOpacityEffect, QLabel,
)
from PySide6.QtGui import QPainter

from ..core.i18n import _
from ..core import qss_base
from ..core.theme import theme as _t
from ..core.glass_effect import draw_glass_morphism
from ..core.logger import get_log_dir, get_current_log_path
from .title_bar import TitleBar


class LogViewerDialog(QDialog):
    """日志查看器 - 非模态、毛玻璃效果、自定义标题栏"""

    _instance: "LogViewerDialog | None" = None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(700, 450)
        self.resize(800, 550)

        self._build_ui()
        self._setup_entrance_animation()
        self._load_log()

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
            self, title=_("MySnipaste Log"), show_minimize=False,
            height=44, title_size="14px", close_size=28,
            margins=(16, 0, 8, 0),
        ))

        # 日志内容
        card_layout.addWidget(self._build_content(), 1)

        # 底部按钮
        card_layout.addLayout(self._build_footer())

        root.addWidget(card)
        self._card = card

    def _build_content(self) -> QTextEdit:
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.NoWrap)

        text_style = """
            QTextEdit {
                border: none;
                border-top: 1px solid palette(mid);
                border-bottom: 1px solid palette(mid);
                padding: 12px 16px;
                font-family: "Consolas", "SF Mono", "Monaco", "Menlo", monospace;
                font-size: 12px;
                color: palette(text);
                background: palette(base);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
        """
        self._text_edit.setStyleSheet(text_style + qss_base.scrollbar_qss())
        return self._text_edit

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 12, 20, 12)
        footer.setSpacing(12)

        # 日志路径提示
        self._path_label = QLabel()
        self._path_label.setStyleSheet(qss_base.label_qss(font_size="11px", color="$text_secondary"))
        footer.addWidget(self._path_label, 1)

        # 刷新按钮
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
        footer.addWidget(refresh_btn)

        # 打开目录按钮
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
        footer.addWidget(open_btn)

        # 关闭按钮
        close_btn = QPushButton(_("Close"))
        close_btn.setCursor(Qt.PointingHandCursor)
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

    def _load_log(self) -> None:
        """加载日志内容"""
        path = get_current_log_path()
        if not path:
            self._text_edit.setPlainText(_("No log files yet"))
            self._path_label.setText("")
            return

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self._text_edit.setPlainText(content if content else _("(empty)"))
            # 滚动到底部
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self._text_edit.setPlainText(_("Failed to read log: {error}").format(error=e))

        self._path_label.setText(path)

    def _open_log_dir(self) -> None:
        """打开日志目录"""
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

    def _setup_entrance_animation(self) -> None:
        """入场淡入动画"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_fade_in'):
            self._fade_in.start()

    def paintEvent(self, event) -> None:
        """绘制毛玻璃背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self._card.geometry()
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=12,
            is_dark=_t.is_dark(),
            draw_shadow=True,
            shadow_intensity=0.6,
        )

    def _on_theme_changed(self, _mode: str) -> None:
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
        """显示日志查看器（单例模式）"""
        if cls._instance is not None:
            cls._instance.raise_()
            cls._instance.activateWindow()
            cls._instance._load_log()  # 刷新内容
            return cls._instance

        dialog = cls(parent)
        cls._instance = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog
