from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from .logger import setup_logger

logger = setup_logger("pin_window")


class PinWindow(QWidget):
    """贴图悬浮窗口，带居中投影阴影效果。"""

    SHADOW_SIZE = 16  # 阴影宽度（像素）

    def __init__(self, pixmap: QPixmap, pos):
        super().__init__()
        self.pixmap = pixmap
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        dpr = pixmap.devicePixelRatio()
        self._content_w = int(pixmap.width() / dpr)
        self._content_h = int(pixmap.height() / dpr)

        s = self.SHADOW_SIZE
        self.resize(self._content_w + 2 * s, self._content_h + 2 * s)
        self.move(pos.x() - s, pos.y() - s)

        self.setMouseTracking(True)
        self._dragging = False
        self._drag_pos = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        s = self.SHADOW_SIZE

        # ——— 绘制投影阴影 ———
        # 从内容边缘向窗口边缘绘制多层半透明圆角矩形叠加，
        # 最暗层紧贴内容 → 最亮层在窗口边缘，形成模糊阴影效果
        for i in range(s, 0, -1):
            t = i / s  # 1 在最内层（内容边缘），→0 在最外层（窗口边缘）
            alpha = int(45 * t * t)  # 平方衰减，过渡柔和
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(40, 120, 255, alpha))
            # 矩形从 (i, i) 到 (width-i, height-i)，随 i 增大向内收缩
            painter.drawRoundedRect(
                i, i,
                self.width() - 2 * i,
                self.height() - 2 * i,
                4, 4,
            )

        # ——— 绘制内容 ———
        painter.drawPixmap(
            s, s, self._content_w, self._content_h,
            self.pixmap,
        )

        # ——— 内容区域边框（半透明白色描边） ———
        pen = QPen(QColor(255, 255, 255, 120), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(s - 1, s - 1, self._content_w + 2, self._content_h + 2, 2, 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.deleteLater()
        super().closeEvent(event)
