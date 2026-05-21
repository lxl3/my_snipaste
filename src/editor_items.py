import math

from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtGui import QPen, QPolygonF, QColor
from PySide6.QtCore import Qt, QRectF, QRect, QPointF


class ArrowItem(QGraphicsItem):
    def __init__(self, start, end, color=QColor(255, 0, 0), width=3):
        super().__init__()
        self.start = start
        self.end = end
        self.arrow_color = color
        self.arrow_width = width
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def boundingRect(self):
        extra = 12 + self.arrow_width * 2
        return QRectF(self.start, self.end).normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget):
        painter.setPen(QPen(self.arrow_color, self.arrow_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(self.start, self.end)

        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        angle = math.atan2(dy, dx)
        arrow_size = 12 + self.arrow_width * 2
        p1 = self.end - QPointF(arrow_size * math.cos(angle - math.pi / 6), arrow_size * math.sin(angle - math.pi / 6))
        p2 = self.end - QPointF(arrow_size * math.cos(angle + math.pi / 6), arrow_size * math.sin(angle + math.pi / 6))
        painter.setBrush(self.arrow_color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([self.end, p1, p2]))


class MosaicItem(QGraphicsRectItem):
    def __init__(self, source_pixmap, rect, block_size=8):
        super().__init__(rect)
        self.source_pixmap = source_pixmap
        self.block_size = block_size
        self.setPen(Qt.NoPen)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def paint(self, painter, option, widget):
        r = self.rect().toRect()
        if r.isEmpty():
            return
        dpr = self.source_pixmap.devicePixelRatio()
        src_rect = QRect(int(r.x() * dpr), int(r.y() * dpr), int(r.width() * dpr), int(r.height() * dpr))
        section = self.source_pixmap.copy(src_rect)
        w, h = section.width(), section.height()
        bs = max(1, self.block_size)
        small = section.scaled(max(1, w // bs), max(1, h // bs), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pixelated = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pixelated.setDevicePixelRatio(dpr)
        painter.drawPixmap(self.rect().topLeft(), pixelated)
