from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget, QApplication

from ..core.i18n import _
from ..core.logger import setup_logger

logger = setup_logger("countdown_overlay")


class CountdownOverlay(QWidget):
    """全屏倒计时覆盖层"""

    countdown_finished = Signal()  # 倒计时结束
    countdown_cancelled = Signal()  # 用户取消

    def __init__(self, seconds: int):
        super().__init__()
        self._seconds_left = seconds
        self._timer: QTimer | None = None

        # 设置窗口属性：无边框、置顶、工具窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        # 设置为全屏覆盖所有显示器
        screen = QApplication.primaryScreen()
        if screen:
            virtual_geometry = screen.virtualGeometry()
            self.setGeometry(virtual_geometry)

        # 初始化定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_countdown)
        self._timer.start(1000)  # 每秒触发一次

        logger.info(f"CountdownOverlay 初始化，倒计时 {seconds} 秒")

    def _update_countdown(self) -> None:
        """每秒更新倒计时"""
        self._seconds_left -= 1
        logger.debug(f"倒计时：{self._seconds_left} 秒")

        if self._seconds_left <= 0:
            # 倒计时结束
            logger.info("倒计时结束，发送 countdown_finished 信号")
            if self._timer:
                self._timer.stop()
            self.countdown_finished.emit()
            self.close()
        else:
            # 触发重绘以更新显示的数字
            self.update()

    def paintEvent(self, event) -> None:
        """绘制倒计时界面"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 153))  # 60% opacity (255 * 0.6 = 153)

        # 绘制倒计时数字
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self._seconds_left))

        # 绘制提示文本 "按 ESC 取消"
        hint_font = QFont("Arial", 24)
        painter.setFont(hint_font)
        painter.setPen(QColor(255, 255, 255, 204))  # 80% opacity (255 * 0.8 = 204)

        # 提示文本位于倒计时数字下方 40px
        hint_rect = self.rect().adjusted(0, 80, 0, 0)
        painter.drawText(hint_rect, Qt.AlignHCenter | Qt.AlignTop,
                        _("Press ESC to cancel"))

    def keyPressEvent(self, event) -> None:
        """处理键盘事件"""
        if event.key() == Qt.Key_Escape:
            logger.info("用户按 ESC 取消倒计时")
            if self._timer:
                self._timer.stop()
            self.countdown_cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """窗口关闭时清理资源"""
        if self._timer:
            self._timer.stop()
            self._timer = None
        logger.debug("CountdownOverlay 已关闭")
        super().closeEvent(event)
