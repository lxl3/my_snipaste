from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from ..core.logger import setup_logger

logger = setup_logger("pin_window")


class PinWindow(QWidget):
    """贴图悬浮窗口，带居中投影阴影效果。"""

    SHADOW_SIZE = 6  # 阴影宽度（像素）

    def __init__(self, pixmap: QPixmap, pos):
        super().__init__()
        self.pixmap = pixmap
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        padding = self.SHADOW_SIZE
        bw = int(pixmap.width() / pixmap.devicePixelRatio()) + padding * 2
        bh = int(pixmap.height() / pixmap.devicePixelRatio()) + padding * 2
        self.setFixedSize(bw, bh)

        if pos is not None:
            self.move(pos.x(), pos.y())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        padding = self.SHADOW_SIZE
        margin = 1
        content_rect = self.rect().adjusted(padding, padding, -padding, -padding)
        shadow_color = QColor(40, 120, 255)

        for i in range(padding):
            alpha = max(0, 80 - i * 10)
            if alpha <= 0:
                break
            offset = padding - margin - i
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha))
            painter.drawRoundedRect(
                content_rect.adjusted(-offset, -offset, offset, offset),
                4 + i, 4 + i,
            )

        painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
        painter.setBrush(Qt.white)
        painter.drawRoundedRect(content_rect, 4, 4)

        dpr = self.pixmap.devicePixelRatio()
        src = QRect(
            0, 0,
            int(content_rect.width() * dpr),
            int(content_rect.height() * dpr),
        )
        painter.drawPixmap(content_rect, self.pixmap, src)

    def mouseDoubleClickEvent(self, event):
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, "_dragging") and self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
