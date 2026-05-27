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

        logger.info(f"CountdownOverlay 初始化，倒计时 {seconds} 秒")
