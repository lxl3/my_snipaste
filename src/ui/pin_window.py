from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from ..core.logger import setup_logger
from ..core.settings import get_settings

logger = setup_logger("pin_window")


class PinWindow(QWidget):
    """Floating pinned window with pre-rendered shadow."""

    SHADOW_SIZE = 6

    def __init__(self, pixmap: QPixmap, pos) -> None:
        super().__init__()
        self.pixmap = pixmap
        self._dragging: bool = False
        self._drag_pos: QPoint | None = None
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        padding = self.SHADOW_SIZE
        bw = int(pixmap.width() / pixmap.devicePixelRatio()) + padding * 2
        bh = int(pixmap.height() / pixmap.devicePixelRatio()) + padding * 2
        self.setFixedSize(bw, bh)

        self._shadow_pixmap = self._render_shadow(bw, bh)

        opacity = get_settings().pin_window_opacity
        self.setWindowOpacity(opacity / 100.0)

        if pos is not None:
            self.move(pos.x(), pos.y())

    def _render_shadow(self, w: int, h: int) -> QPixmap:
        pm = QPixmap(QSize(w, h))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        padding = self.SHADOW_SIZE
        margin = 1
        content_rect = pm.rect().adjusted(padding, padding, -padding, -padding)
        shadow_color = QColor(40, 120, 255)

        for i in range(padding):
            alpha = max(0, 80 - i * 10)
            if alpha <= 0:
                break
            offset = padding - margin - i
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha))
            p.drawRoundedRect(
                content_rect.adjusted(-offset, -offset, offset, offset),
                4 + i, 4 + i,
            )

        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.setBrush(Qt.white)
        p.drawRoundedRect(content_rect, 4, 4)
        p.end()
        return pm

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._shadow_pixmap)

        padding = self.SHADOW_SIZE
        content_rect = self.rect().adjusted(padding, padding, -padding, -padding)
        dpr = self.pixmap.devicePixelRatio()
        src = QRect(
            0, 0,
            int(content_rect.width() * dpr),
            int(content_rect.height() * dpr),
        )
        painter.drawPixmap(content_rect, self.pixmap, src)

    def mouseDoubleClickEvent(self, event) -> None:
        self.close()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = True
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
