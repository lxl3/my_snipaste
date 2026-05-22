"""截图覆盖层绘图渲染 Mixin。"""

import math

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF

from .constants import (
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
        logical_rect = self.selection_rect
        physical_rect = QRect(
            round(logical_rect.x() * dpr), round(logical_rect.y() * dpr),
            round(logical_rect.width() * dpr), round(logical_rect.height() * dpr),
        )
        pm = self.full_screenshot.copy(physical_rect)
        pm.setDevicePixelRatio(dpr)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_annotations(painter, logical_rect.size(), QPointF(0, 0))
        painter.end()
        return pm

    def _draw_annotations(self, painter, view_size, offset):
        """绘制所有标注和预览标注。"""
        for ann in self.annotations:
            self._draw_annotation(painter, ann, offset)
        if self._preview_annotation:
            self._draw_annotation(painter, self._preview_annotation, offset)

    def _draw_annotation(self, painter, ann, offset):
        """根据标注类型分发绘制。"""
        t = ann["type"]
        if t in ("rect", "ellipse"):
            r = QRectF(ann["rect"]).translated(offset)
            painter.setPen(QPen(ann["color"], ann["width"]))
            painter.setBrush(Qt.NoBrush)
            if t == "rect":
                painter.drawRect(r)
            else:
                painter.drawEllipse(r)
        elif t in ("arrow", "line"):
            start = ann["start"] + offset
            end = ann["end"] + offset
            painter.setPen(QPen(ann["color"], ann["width"]))
            painter.drawLine(start, end)
            if t == "arrow":
                self._draw_arrowhead(painter, start, end, ann["width"])
        elif t == "freehand":
            pts = [p + offset for p in ann["points"]]
            if len(pts) >= 2:
                painter.setPen(QPen(ann["color"], ann["width"]))
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                painter.drawPath(path)
        elif t == "mosaic":
            self._draw_mosaic(painter, ann, offset)
        elif t == "text":
            self._draw_text(painter, ann, offset)

    def _draw_arrowhead(self, painter, start, end, width):
        """绘制箭头头部三角。"""
        arrow_size = ARROW_SIZE_BASE + width
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        p1 = end - QPointF(
            arrow_size * math.cos(angle + ARROW_SPREAD_ANGLE),
            arrow_size * math.sin(angle + ARROW_SPREAD_ANGLE),
        )
        p2 = end - QPointF(
            arrow_size * math.cos(angle - ARROW_SPREAD_ANGLE),
            arrow_size * math.sin(angle - ARROW_SPREAD_ANGLE),
        )
        painter.drawLine(end, p1)
        painter.drawLine(end, p2)

    def _draw_mosaic(self, painter, ann, offset):
        """绘制马赛克效果。"""
        dpr = self.full_screenshot.devicePixelRatio()
        r = QRectF(ann["rect"]).translated(offset).toRect()
        sel = self.selection_rect
        src_rect = QRect(
            round((sel.x() + ann["rect"].x()) * dpr),
            round((sel.y() + ann["rect"].y()) * dpr),
            round(ann["rect"].width() * dpr),
            round(ann["rect"].height() * dpr),
        )
        if src_rect.width() > 0 and src_rect.height() > 0:
            src = self.full_screenshot.copy(src_rect)
            small = src.scaled(
                max(src.width() // MOSAIC_SCALE_FACTOR, 1),
                max(src.height() // MOSAIC_SCALE_FACTOR, 1),
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
            )
            blurred = small.scaled(
                src.width(), src.height(),
                Qt.IgnoreAspectRatio, Qt.FastTransformation,
            )
            painter.drawPixmap(r, blurred, blurred.rect())

    def _draw_text(self, painter, ann, offset):
        """绘制文本标注。"""
        pos = ann["pos"] + offset
        painter.setPen(QPen(ann["color"]))
        font = QFont(ann.get("font_family", "Segoe UI"), ann.get("font_size", 20))
        font.setBold(ann.get("bold", False))
        font.setItalic(ann.get("italic", False))
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_pos = pos.toPoint() + QPoint(4, fm.ascent() + 2)
        painter.drawText(text_pos, ann["text"])

    def _draw_size_info(self, painter, rect):
        """绘制选区尺寸信息标签。"""
        info_text = f"{rect.width()} x {rect.height()}"
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 12))
        text_width = painter.fontMetrics().horizontalAdvance(info_text) + 20
        text_height = 28
        text_x = rect.x()
        text_y = rect.bottom() + 8
        if text_y + text_height > self.height() - 10:
            text_y = rect.top() - text_height - 8
        painter.fillRect(QRect(text_x, text_y, text_width, text_height), QColor(0, 0, 0, 180))
        painter.drawText(QRect(text_x, text_y, text_width, text_height), Qt.AlignCenter, info_text)

    def _draw_coord_tooltip(self, painter):
        """绘制鼠标坐标提示。"""
        coord_text = f"{self.current_mouse_pos.x()}, {self.current_mouse_pos.y()}"
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 11))
        cx, cy = self.current_mouse_pos.x(), self.current_mouse_pos.y()
        coord_w, coord_h = 130, 24
        coord_rect = QRect(cx + 15, cy + 15, coord_w, coord_h)
        if coord_rect.right() > self.width() - 10:
            coord_rect.moveLeft(cx - coord_w - 15)
        if coord_rect.bottom() > self.height() - 10:
            coord_rect.moveTop(cy - coord_h - 15)
        painter.fillRect(coord_rect, QColor(0, 0, 0, 160))
        painter.drawText(coord_rect, Qt.AlignCenter, coord_text)
