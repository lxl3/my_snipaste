"""截图覆盖层绘图渲染 Mixin。"""

import math

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF

from ..core.constants import (
    ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, MOSAIC_SCALE_FACTOR,
)


class OverlayRenderingMixin:
    """提供覆盖层上所有标注的绘制/渲染逻辑。

    子类必须提供:
    - self.full_screenshot (QPixmap)
    - self.selection_rect (QRect)
    - self.annotations (list)
    - self._preview_annotation (dict | None)
    - self.current_mouse_pos (QPoint)
    - self.current_color (QColor)
    - self.current_width (int)
    - self.total_geometry (QRect)
    - 标准 QWidget 方法: self.rect(), self.height(), self.width()
    """

    def _render_annotated_pixmap(self) -> QPixmap:
        """渲染选区内的完整标注快照。"""
        dpr = self.full_screenshot.devicePixelRatio()
        sel = self.selection_rect

        result = QPixmap(sel.size())
        result.setDevicePixelRatio(dpr)
        result.fill(Qt.transparent)

        p = QPainter(result)
        p.setRenderHint(QPainter.Antialiasing)
        physical_sel = QRect(
            round(sel.x() * dpr), round(sel.y() * dpr),
            round(sel.width() * dpr), round(sel.height() * dpr),
        )
        p.drawPixmap(result.rect(), self.full_screenshot, physical_sel)
        self._draw_annotations(p, sel.size(), QPoint(0, 0))
        p.end()
        return result

    def _draw_annotations(self, painter, sel_size, offset):
        """在 painter 上绘制 annotations + preview。"""
        for ann in self.annotations:
            self._draw_one_annotation(painter, ann, offset)
        if self._preview_annotation:
            self._draw_one_annotation(painter, self._preview_annotation, offset)

    def _draw_one_annotation(self, painter, ann, offset):
        t = ann["type"]
        if t == "rect":
            self._draw_rect(painter, ann, offset)
        elif t == "ellipse":
            self._draw_ellipse(painter, ann, offset)
        elif t == "arrow":
            self._draw_arrow(painter, ann, offset)
        elif t == "line":
            self._draw_line(painter, ann, offset)
        elif t == "freehand":
            self._draw_freehand(painter, ann, offset)
        elif t == "mosaic":
            self._draw_mosaic(painter, ann, offset)
        elif t == "text":
            self._draw_text(painter, ann, offset)

    def _draw_rect(self, painter, ann, offset):
        r = ann["rect"].translated(offset)
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _draw_ellipse(self, painter, ann, offset):
        r = ann["rect"].translated(offset)
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(r)

    def _draw_arrow(self, painter, ann, offset):
        start = ann["start"] + offset
        end = ann["end"] + offset
        width = ann["width"]
        painter.setPen(QPen(QColor(ann["color"]), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        base = ARROW_SIZE_BASE + width * 2
        p1 = QPointF(end.x() - ux * base + uy * base * math.tan(ARROW_SPREAD_ANGLE),
                     end.y() - uy * base - ux * base * math.tan(ARROW_SPREAD_ANGLE))
        p2 = QPointF(end.x() - ux * base - uy * base * math.tan(ARROW_SPREAD_ANGLE),
                     end.y() - uy * base + ux * base * math.tan(ARROW_SPREAD_ANGLE))
        path = QPainterPath()
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        painter.setBrush(QColor(ann["color"]))
        painter.drawPath(path)

    def _draw_line(self, painter, ann, offset):
        start = ann["start"] + offset
        end = ann["end"] + offset
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

    def _draw_freehand(self, painter, ann, offset):
        pts = ann["points"]
        if len(pts) < 2:
            return
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(pts[0] + offset)
        for i in range(1, len(pts)):
            path.lineTo(pts[i] + offset)
        painter.drawPath(path)

    def _draw_mosaic(self, painter, ann, offset):
        r = QRectF(ann["rect"]).translated(offset).toRect()
        if r.isEmpty():
            return
        dpr = self.full_screenshot.devicePixelRatio()
        scale = MOSAIC_SCALE_FACTOR
        px = QPixmap(r.size())
        px.fill(Qt.transparent)
        p2 = QPainter(px)
        src = QRect(
            round((r.x() + self.selection_rect.x()) * dpr),
            round((r.y() + self.selection_rect.y()) * dpr),
            round(r.width() * dpr),
            round(r.height() * dpr),
        )
        p2.drawPixmap(px.rect(), self.full_screenshot, src)
        p2.end()
        small = px.scaled(max(1, r.width() // scale), max(1, r.height() // scale),
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pixelated = small.scaled(r.width(), r.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter.drawPixmap(r.topLeft(), pixelated)

    def _draw_text(self, painter, ann, offset):
        pos = ann["pos"] + offset
        painter.setFont(QFont(ann["font_family"], ann["font_size"]))
        font = painter.font()
        font.setBold(ann["bold"])
        font.setItalic(ann["italic"])
        painter.setFont(font)
        painter.setPen(QColor(ann["color"]))
        painter.drawText(pos, ann["text"])
