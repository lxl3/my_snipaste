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

        # 设置窗口透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置焦点策略以接收键盘输入
        self.setFocusPolicy(Qt.StrongFocus)

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
        """绘制倒计时界面（无背景，使用描边技术）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # 不再绘制背景 - 完全透明，用户可以看清屏幕内容

        # 绘制倒计时数字（带 8 方向描边效果）
        font = QFont("Arial", 120, QFont.Bold)
        painter.setFont(font)

        self._draw_text_with_outline(
            painter,
            self.rect(),
            Qt.AlignCenter,
            str(self._seconds_left),
            QColor(255, 255, 255),      # 白色文字
            QColor(0, 0, 0),            # 纯黑色描边（不透明，避免重影）
            outline_width=3             # 3px 描边（大号文字）
        )

        # 绘制提示文本 "按 ESC 取消"（带描边效果）
        hint_font = QFont("Arial", 24)
        painter.setFont(hint_font)

        # 提示文本位于倒计时数字下方 80px
        hint_rect = self.rect().adjusted(0, 80, 0, 0)

        self._draw_text_with_outline(
            painter,
            hint_rect,
            Qt.AlignHCenter | Qt.AlignTop,
            _("Press ESC to cancel"),
            QColor(255, 255, 255),       # 白色文字
            QColor(0, 0, 0),             # 纯黑色描边
            outline_width=1              # 1px 描边（最细描边，完全消除重影）
        )

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

        使用 4 方向描边技术（上下左右），确保文字在任何背景下都清晰可读，避免对角线方向重叠造成重影

        Args:
            painter: QPainter 对象
            rect: 绘制区域
            flags: 对齐方式（Qt.AlignCenter 等）
            text: 文字内容
            text_color: 文字颜色
            outline_color: 描边颜色
            outline_width: 描边宽度（像素）
        """
        # 4 个方向的偏移：上、下、左、右（避免对角线重叠造成重影）
        offsets = [
            (0, -outline_width),   # 上
            (0, outline_width),    # 下
            (-outline_width, 0),   # 左
            (outline_width, 0),    # 右
        ]

        # 先绘制 8 个方向的描边
        painter.setPen(outline_color)
        for dx, dy in offsets:
            outline_rect = rect.adjusted(dx, dy, dx, dy)
            painter.drawText(outline_rect, flags, text)

        # 最后绘制中心的文字
        painter.setPen(text_color)
        painter.drawText(rect, flags, text)
