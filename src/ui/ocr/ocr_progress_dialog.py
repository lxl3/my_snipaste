"""OCR 识别进度对话框 - Big Sur 风格毛玻璃设计

参考 frosted_glass_demo.py 实现，直接在 self.rect() 绘制，无嵌套结构。
"""

import math
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from ...core.i18n import _
from ...core.theme_pkg import draw_glass_morphism
from ...core.theme_pkg import theme as _t


class OcrProgressDialog(QDialog):
    """OCR 识别进度对话框 - 毛玻璃效果"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 180)
        self.setModal(True)

        self._start_time = None
        self._pulse_phase = 0
        self._drag_pos = QPoint()

        self._build_ui()
        self._setup_timer()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        self._title_label = QLabel(_("Recognizing Text"))
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(_t.qss("font-size: 15px; font-weight: 600; color: $text_primary;"))
        layout.addWidget(self._title_label)

        # 脉冲进度指示器容器
        self._pulse_container = QWidget()
        self._pulse_container.setFixedHeight(4)
        layout.addWidget(self._pulse_container)

        # 状态文字
        self._status_label = QLabel(_("Please wait..."))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_secondary;"))
        layout.addWidget(self._status_label)

        # 时间显示
        self._time_label = QLabel("00:00")
        self._time_label.setAlignment(Qt.AlignCenter)
        self._time_label.setStyleSheet(_t.qss("font-size: 11px; color: $text_placeholder;"))
        layout.addWidget(self._time_label)

        layout.addSpacing(8)

        # 取消按钮
        self._cancel_btn = QPushButton(_("Cancel"))
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(_t.qss("""
            QPushButton {
                background: rgba(128, 128, 128, 0.15);
                color: $text_primary;
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(128, 128, 128, 0.25);
                border: 1px solid rgba(128, 128, 128, 0.3);
            }
            QPushButton:pressed {
                background: rgba(128, 128, 128, 0.35);
            }
        """))
        self._cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self._cancel_btn)

        _t.theme_changed.connect(self._refresh_style)

    def _setup_timer(self):
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(1000)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(30)

    def _update_time(self):
        if self._start_time is None:
            self._start_time = time.time()
            return

        elapsed = int(time.time() - self._start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}")

        if elapsed > 10 and elapsed % 5 == 0:
            self._status_label.setText(_("Still recognizing... ({elapsed}s)").format(elapsed=elapsed))

    def _update_pulse(self):
        self._pulse_phase += 0.05
        self._pulse_container.update()
        self.update()  # 触发 paintEvent 重绘脉冲

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        is_dark = _t.is_dark()

        # 毛玻璃背景
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=8,
            is_dark=is_dark,
            draw_shadow=True,
        )

        # 绘制脉冲进度条
        if self._pulse_container:
            pulse_rect = self._pulse_container.geometry()
            pulse_x = pulse_rect.x()
            pulse_y = pulse_rect.y()
            pulse_w = pulse_rect.width()
            pulse_h = pulse_rect.height()

            accent = QColor(_t.get("accent", "#007AFF"))

            if is_dark:
                base_alpha = 80
                wave_alpha = 160
            else:
                base_alpha = 40
                wave_alpha = 180

            for i in range(pulse_w):
                progress = (i / pulse_w + self._pulse_phase) % 1.0
                intensity = (math.sin(progress * math.pi * 2) + 1) / 2
                alpha = int(intensity * wave_alpha + base_alpha)
                color = QColor(accent.red(), accent.green(), accent.blue(), alpha)
                painter.setPen(color)
                painter.drawLine(pulse_x + i, pulse_y, pulse_x + i, pulse_y + pulse_h)

    def _refresh_style(self, _mode: str):
        self._title_label.setStyleSheet(_t.qss("font-size: 15px; font-weight: 600; color: $text_primary;"))
        self._status_label.setStyleSheet(_t.qss("font-size: 12px; color: $text_secondary;"))
        self._time_label.setStyleSheet(_t.qss("font-size: 11px; color: $text_placeholder;"))
        self.update()

    def closeEvent(self, event):
        try:
            _t.theme_changed.disconnect(self._refresh_style)
        except (TypeError, RuntimeError):
            pass
        if hasattr(self, '_time_timer'):
            self._time_timer.stop()
        if hasattr(self, '_pulse_timer'):
            self._pulse_timer.stop()
        super().closeEvent(event)
