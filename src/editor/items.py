import math

from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtGui import QPen, QPolygonF, QColor
from PySide6.QtCore import Qt, QRectF, QRect, QPointF

from ..core.constants import ARROWHEAD_SIZE_BASE, ARROW_SPREAD_ANGLE, MIN_DRAW_THRESHOLD


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
        extra = ARROWHEAD_SIZE_BASE + self.arrow_width * 2
        return QRectF(self.start, self.end).normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget):
        painter.setPen(QPen(self.arrow_color, self.arrow_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(self.start, self.end)

        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        base = ARROWHEAD_SIZE_BASE + self.arrow_width * 2
        angle = ARROW_SPREAD_ANGLE
        p1 = QPointF(
            self.end.x() - ux * base + uy * base * math.tan(angle),
            self.end.y() - uy * base - ux * base * math.tan(angle)
        )
        p2 = QPointF(
            self.end.x() - ux * base - uy * base * math.tan(angle),
            self.end.y() - uy * base + ux * base * math.tan(angle)
        )
        painter.setBrush(self.arrow_color)
        painter.setPen(Qt.NoPen)
        polygon = QPolygonF([self.end, p1, p2])
        painter.drawPolygon(polygon)


class MosaicItem(QGraphicsRectItem):
    def __init__(self, rect, pixmap):
        super().__init__(rect)
        self.mosaic_pixmap = pixmap
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def paint(self, painter, option, widget):
        painter.drawPixmap(self.rect().topLeft(), self.mosaic_pixmap)
