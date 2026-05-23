"""Overlay rendering mixin for annotations."""

import math

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize

from ..core.constants import (
    ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, MOSAIC_SCALE_FACTOR,
)


class OverlayRenderingMixin:
    """Rendering logic for all annotation types.

    Subclass must provide:
    - self.selection_rect (QRectF)
    - self.full_screenshot (QPixmap)
    - self.annotations (list[dict])
    - self._preview_annotation (dict | None)

    Mixin expects host QWidget methods: rect(), height(), width()
    """

    def _render_annotated_pixmap(self) -> QPixmap:
        """Crop selection from screenshot and draw annotations.

        High DPI note: coordinate conversion is manual.
        - selection_rect is in logical (screen) coords
        - full_screenshot physical size = logical size × devicePixelRatio
        - must copy from full_screenshot in physical coords
        """
        logical_rect = self.selection_rect
        if logical_rect.isNull():
            return QPixmap()

        dpr = screen.devicePixelRatio()

        phys_rect = QRect(
            int(stream_rect.x() * dpr),
            int(stream_rect.y() * dpr),
            int(stream_rect.width() * dpr),
            int(stream_rect.height() * dpr),
        )

        cropped = screenshot.copy(phys_rect)
        cropped.setDevicePixelRatio(dpr)

        self._draw_annotations(painter, cropped.size() / dpr, QPointF(0, 0))

        # annotations use logical coords relative to selection top-left; offset = (0,0)
        self._draw_annotations(painter, logical_rect.size(), QPoint(0, 0))
        painter.end()

        return result

    def _draw_annotations(self, painter, sel_size, offset):
        """Draw annotations + preview on painter."""
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

        # ann["rect"] is local to selection top-left → global = local + offset
        local_rect = QRectF(ann["rect"])
        global_x = round((local_rect.x() + self.selection_rect.x()) * dpr)
        global_y = round((local_rect.y() + self.selection_rect.y()) * dpr)

        px = QPixmap(r.size())
        px.fill(Qt.transparent)
        p2 = QPainter(px)
        src = QRect(
            global_x, global_y,
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
        # drawText(QPointF, text) uses y as baseline; add ascent to align top with click point
        fm = painter.fontMetrics()
        painter.drawText(QPointF(pos.x(), pos.y() + fm.ascent()), ann["text"])
