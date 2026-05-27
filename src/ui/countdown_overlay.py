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

    def closeEvent(self, event) -> None:
        """窗口关闭时清理资源"""
        if self._timer:
            self._timer.stop()
            self._timer = None
        logger.debug("CountdownOverlay 已关闭")
        super().closeEvent(event)
