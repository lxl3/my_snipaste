import math

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem, QGraphicsItem
from PySide6.QtGui import QPainter, QPen, QBrush, QFont, QPainterPath, QColor
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, Signal

from .items import ArrowItem, MosaicItem
from ..core.constants import (
    DEFAULT_ANNOTATION_COLOR, DEFAULT_LINE_WIDTH, MIN_DRAW_THRESHOLD,
    MIN_SELECTION_SIZE, ZOOM_FACTOR, ARROWHEAD_SIZE_BASE, ARROW_SPREAD_ANGLE,
)


class AnnotationView(QGraphicsView):
    annotation_added = Signal(object)

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setInteractive(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QGraphicsView { border: none; background: #2d2d2d; }")

        self.current_tool: str = "select"
        self.current_color: QColor = QColor(DEFAULT_ANNOTATION_COLOR)
        self.current_width: int = DEFAULT_LINE_WIDTH
        self._drawing: bool = False
        self._draw_start: QPointF | None = None
        self._current_item: QGraphicsItem | None = None
        self._items: list[QGraphicsItem] = []
        self.source_pixmap: QPixmap | None = None

    def set_tool(self, tool: str) -> None:
        self.current_tool = tool
        self.setDragMode(QGraphicsView.NoDrag)
        if tool == "select":
            self.setInteractive(True)
            self.setDragMode(QGraphicsView.RubberBandDrag)
        else:
            self.setInteractive(False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.current_tool != "select":
            self._drawing = True
            self._draw_start = self.mapToScene(event.pos())
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drawing and self._draw_start:
            current = self.mapToScene(event.pos())
            self._update_preview(current)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drawing and self._draw_start:
            self._drawing = False
            current = self.mapToScene(event.pos())
            self._finish_drawing(current)
            return
        super().mouseReleaseEvent(event)

    def _update_preview(self, current: QPointF) -> None:
        scene = self.scene()
        if self._current_item:
            scene.removeItem(self._current_item)
            self._current_item = None

        start = self._draw_start
        if self.current_tool == "rect":
            r = QRectF(start, current).normalized()
            item = QGraphicsRectItem(r)
            item.setPen(QPen(self.current_color, self.current_width))
        elif self.current_tool == "ellipse":
            r = QRectF(start, current).normalized()
            item = QGraphicsEllipseItem(r)
            item.setPen(QPen(self.current_color, self.current_width))
        elif self.current_tool == "arrow":
            item = ArrowItem(start, current, self.current_color, self.current_width)
        elif self.current_tool == "line":
            item = QGraphicsLineItem(QLineF(start, current))
            item.setPen(QPen(self.current_color, self.current_width))
        else:
            return
        scene.addItem(item)
        self._current_item = item

    def _finish_drawing(self, current: QPointF) -> None:
        if self._current_item:
            self._items.append(self._current_item)
            self.annotation_added.emit(self._current_item)
            self._current_item = None

    def wheelEvent(self, event) -> None:
        if event.modifiers() == Qt.ControlModifier:
            factor = ZOOM_FACTOR if event.angleDelta().y() > 0 else 1.0 / ZOOM_FACTOR
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)
