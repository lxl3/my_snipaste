import math

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem, QGraphicsItem
from PySide6.QtGui import QPainter, QPen, QBrush, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, Signal

from .editor_items import ArrowItem, MosaicItem


class AnnotationView(QGraphicsView):
    annotation_added = Signal(object)

    def __init__(self, scene, parent=None):
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

        self.current_tool = "select"
        self.current_color = QColor(255, 50, 50)
        self.current_width = 3
        self.current_fill = Qt.transparent
        self.source_pixmap = None
        self.drawing_item = None
        self.start_point = QPointF()
        self.text_item = None

    def set_tool(self, tool):
        self.current_tool = tool
        if tool == "select":
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setInteractive(True)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setInteractive(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_tool != "select":
            self.start_point = self.mapToScene(event.pos())
            scene = self.scene()

            if self.current_tool == "rect":
                item = QGraphicsRectItem()
                item.setPen(QPen(self.current_color, self.current_width))
                if self.current_fill != Qt.transparent:
                    item.setBrush(QBrush(self.current_fill))
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "ellipse":
                item = QGraphicsEllipseItem()
                item.setPen(QPen(self.current_color, self.current_width))
                if self.current_fill != Qt.transparent:
                    item.setBrush(QBrush(self.current_fill))
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "line":
                item = QGraphicsLineItem()
                item.setPen(QPen(self.current_color, self.current_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "arrow":
                self.drawing_item = {"start": self.start_point, "end": self.start_point}

            elif self.current_tool == "freehand":
                path = QPainterPath()
                path.moveTo(self.start_point)
                item = QGraphicsPathItem()
                item.setPath(path)
                item.setPen(QPen(self.current_color, self.current_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "mosaic":
                item = QGraphicsRectItem()
                item.setPen(QPen(QColor(128, 128, 128, 200), 1, Qt.DashLine))
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "text":
                item = QGraphicsTextItem()
                item.setDefaultTextColor(self.current_color)
                item.setFont(QFont("Segoe UI", 14))
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                item.setPos(self.start_point)
                scene.addItem(item)
                item.setPlainText("文字")
                item.setTextInteractionFlags(Qt.TextEditorInteraction)
                scene.setFocusItem(item)
                self.text_item = item
                self.annotation_added.emit(item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_item and self.current_tool not in ("select", "arrow", "mosaic", "text"):
            pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_point, pos).normalized()
            if self.current_tool == "rect" and isinstance(self.drawing_item, QGraphicsRectItem):
                self.drawing_item.setRect(rect)
            elif self.current_tool == "ellipse" and isinstance(self.drawing_item, QGraphicsEllipseItem):
                self.drawing_item.setRect(rect)
            elif self.current_tool == "line" and isinstance(self.drawing_item, QGraphicsLineItem):
                self.drawing_item.setLine(QLineF(self.start_point, pos))
            elif self.current_tool == "freehand" and isinstance(self.drawing_item, QGraphicsPathItem):
                path = self.drawing_item.path()
                path.lineTo(pos)
                self.drawing_item.setPath(path)
        elif self.drawing_item and self.current_tool == "arrow":
            self.drawing_item["end"] = self.mapToScene(event.pos())
        elif self.current_tool == "mosaic" and isinstance(self.drawing_item, QGraphicsRectItem):
            self.drawing_item.setRect(QRectF(self.start_point, self.mapToScene(event.pos())).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if self.current_tool == "arrow" and self.drawing_item:
            pos = self.mapToScene(event.pos())
            item = ArrowItem(self.drawing_item["start"], pos, self.current_color, self.current_width)
            item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
            self.scene().addItem(item)
            self.drawing_item = None
            self.annotation_added.emit(item)

        elif self.current_tool == "mosaic" and self.drawing_item:
            pos = self.mapToScene(event.pos())
            mosaic_rect = QRectF(self.start_point, pos).normalized()
            self.scene().removeItem(self.drawing_item)
            self.drawing_item = None
            if mosaic_rect.width() > 5 and mosaic_rect.height() > 5 and self.source_pixmap:
                item = MosaicItem(self.source_pixmap, mosaic_rect)
                item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
                self.scene().addItem(item)
                self.annotation_added.emit(item)

        elif self.drawing_item and self.current_tool != "select":
            item = self.drawing_item
            self.drawing_item = None
            self.annotation_added.emit(item)
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            scale = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(scale, scale)
        else:
            super().wheelEvent(event)
