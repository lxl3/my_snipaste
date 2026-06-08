"""OCR 识别进度对话框 - 玻璃效果设计"""

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QWidget, QGraphicsOpacityEffect
from PySide6.QtGui import QPainter, QColor, QLinearGradient

from ..core.i18n import _
from ..core.theme import theme as _t
from ..core.glass_effect import draw_glass_morphism


class OcrProgressDialog(QDialog):
    """OCR 识别进度对话框 - 玻璃效果设计，与工具栏风格统一"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 180)
        self.setModal(True)

        self._start_time = None
        self._pulse_phase = 0

        self._build_ui()
        self._setup_animations()
        self._setup_timer()

    def _build_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 主容器（用于绘制玻璃背景）
        self._container = QWidget()
        self._container.setObjectName("glassContainer")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(16)

        # 标题
        self._title_label = QLabel(_("Recognizing Text"))
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(_t.qss("""
            font-size: 15px;
            font-weight: 600;
            color: $text_primary;
        """))
        container_layout.addWidget(self._title_label)

        # 脉冲进度指示器容器
        self._pulse_container = QWidget()
        self._pulse_container.setFixedHeight(4)
        container_layout.addWidget(self._pulse_container)

        # 状态文字
        self._status_label = QLabel(_("Please wait..."))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(_t.qss("""
            font-size: 12px;
            color: $text_secondary;
        """))
        container_layout.addWidget(self._status_label)

        # 时间显示
        self._time_label = QLabel("00:00")
        self._time_label.setAlignment(Qt.AlignCenter)
        self._time_label.setStyleSheet(_t.qss("""
            font-size: 11px;
            color: $text_placeholder;
            font-variant-numeric: tabular-nums;
        """))
        container_layout.addWidget(self._time_label)

        container_layout.addSpacing(8)

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
        container_layout.addWidget(self._cancel_btn)

        layout.addWidget(self._container)

        # 监听主题变化
        _t.theme_changed.connect(self._refresh_style)

    def _setup_animations(self):
        """设置入场动画"""
        # 透明度动画
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

    def _setup_timer(self):
        """设置定时器"""
        # 时间更新定时器
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(1000)

        # 脉冲动画定时器
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start(30)  # ~33fps

    def _update_time(self):
        """更新时间显示"""
        if self._start_time is None:
            import time
            self._start_time = time.time()
            return

        import time
        elapsed = int(time.time() - self._start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}")

        # 超过 10 秒更新状态提示
        if elapsed > 10 and elapsed % 5 == 0:
            self._status_label.setText(_("Still recognizing... ({elapsed}s)").format(elapsed=elapsed))

    def _update_pulse(self):
        """更新脉冲动画"""
        self._pulse_phase += 0.05
        self._pulse_container.update()

    def paintEvent(self, event):
        """绘制玻璃效果背景（Big Sur 风格）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        is_dark = _t.is_dark()

        # 使用通用 Big Sur 毛玻璃效果
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=8,
            is_dark=is_dark,
            draw_shadow=False,  # 禁用阴影避免透明窗口拖动残影
        )

        # 绘制脉冲进度条（在 pulse_container 区域）
        if self._pulse_container:
            pulse_rect = self._pulse_container.geometry()
            pulse_x = pulse_rect.x()
            pulse_y = pulse_rect.y()
            pulse_w = pulse_rect.width()
            pulse_h = pulse_rect.height()

            # 脉冲波形（正弦波移动）- 暗色模式增强对比度
            import math
            accent = QColor(_t.get("accent", "#007AFF"))

            # 暗色模式使用更高的基础亮度和更大的波动范围
            if is_dark:
                base_alpha = 80      # 暗色：更高的基础亮度
                wave_alpha = 160     # 暗色：更大的波动范围
            else:
                base_alpha = 40      # 亮色：较低的基础亮度
                wave_alpha = 180     # 亮色：较大的波动范围

            for i in range(pulse_w):
                progress = (i / pulse_w + self._pulse_phase) % 1.0
                intensity = (math.sin(progress * math.pi * 2) + 1) / 2  # 0-1
                alpha = int(intensity * wave_alpha + base_alpha)
                color = QColor(accent.red(), accent.green(), accent.blue(), alpha)
                painter.setPen(color)
                painter.drawLine(pulse_x + i, pulse_y, pulse_x + i, pulse_y + pulse_h)

    def showEvent(self, event):
        """显示时播放入场动画"""
        super().showEvent(event)
        self._fade_in.start()

    def _refresh_style(self, _mode: str):
        """主题切换时刷新样式"""
        self.update()

    def closeEvent(self, event):
        """关闭时清理"""
        try:
            _t.theme_changed.disconnect(self._refresh_style)
        except (TypeError, RuntimeError):
            pass
        if hasattr(self, '_time_timer'):
            self._time_timer.stop()
        if hasattr(self, '_pulse_timer'):
            self._pulse_timer.stop()
        super().closeEvent(event)
