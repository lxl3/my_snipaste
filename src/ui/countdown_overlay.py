from PySide6.QtCore import Qt, QTimer, Signal, QRect
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
            logger.info("倒计时结束，隐藏窗口并准备截图")
            if self._timer:
                self._timer.stop()
            # 立即隐藏窗口
            self.hide()
            # 延迟 200ms 后发送信号，确保窗口完全消失
            QTimer.singleShot(200, self._emit_finished)
        else:
            # 触发重绘以更新显示的数字
            self.update()

    def _emit_finished(self) -> None:
        """延迟发送倒计时结束信号"""
        logger.info("发送 countdown_finished 信号")
        self.countdown_finished.emit()
        self.close()

    def paintEvent(self, event) -> None:
        """绘制倒计时界面"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 26))  # 10% opacity (255 * 0.10 = 26)

        # 绘制倒计时数字（带阴影效果）
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)

        # 先绘制黑色阴影（偏移 4px）
        shadow_rect = self.rect().adjusted(4, 4, 4, 4)
        painter.setPen(QColor(0, 0, 0, 200))
        painter.drawText(shadow_rect, Qt.AlignCenter, str(self._seconds_left))

        # 再绘制白色数字
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

    def _draw_text_with_outline(
        self,
        painter: QPainter,
        rect: QRect,
        flags: Qt.AlignmentFlag,
        text: str,
        text_color: QColor,
        outline_color: QColor,
        outline_width: int = 2
    ) -> None:
        """绘制带描边效果的文字

        使用 8 方向描边技术，确保文字在任何背景下都清晰可读（类似视频字幕）

        Args:
            painter: QPainter 对象
            rect: 绘制区域
            flags: 对齐方式（Qt.AlignCenter 等）
            text: 文字内容
            text_color: 文字颜色
            outline_color: 描边颜色
            outline_width: 描边宽度（像素）
        """
        # 8 个方向的偏移：上、下、左、右、左上、右上、左下、右下
        offsets = [
            (0, -outline_width),   # 上
            (0, outline_width),    # 下
            (-outline_width, 0),   # 左
            (outline_width, 0),    # 右
            (-outline_width, -outline_width),  # 左上
            (outline_width, -outline_width),   # 右上
            (-outline_width, outline_width),   # 左下
            (outline_width, outline_width),    # 右下
        ]

        # 先绘制 8 个方向的描边
        painter.setPen(outline_color)
        for dx, dy in offsets:
            outline_rect = rect.adjusted(dx, dy, dx, dy)
            painter.drawText(outline_rect, flags, text)

        # 最后绘制中心的文字
        painter.setPen(text_color)
        painter.drawText(rect, flags, text)
