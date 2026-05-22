"""截图覆盖层绘图渲染 Mixin。"""

import math

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize

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
        """从截图中抠出选区，再画上标注。

        重要：高 DPI 显示器需要手动转换坐标
        - selection_rect 是逻辑坐标（屏幕坐标）
        - full_screenshot 的物理尺寸 = 逻辑尺寸 × devicePixelRatio
        - 必须用物理坐标从 full_screenshot 中 copy，否则会复制错误的区域
        """
        logical_rect = self.selection_rect
        if logical_rect.isNull():
            return QPixmap()

        # 获取设备像素比（高 DPI 显示器 > 1.0）
        dpr = self.full_screenshot.devicePixelRatio()

        # 将逻辑坐标转换为物理坐标
        physical_rect = QRect(
            int(logical_rect.x() * dpr),
            int(logical_rect.y() * dpr),
            int(logical_rect.width() * dpr),
            int(logical_rect.height() * dpr)
        )

        # 使用物理坐标复制
        result = self.full_screenshot.copy(physical_rect)

        # 设置结果的 DPR，确保显示时正确缩放
        result.setDevicePixelRatio(dpr)

        # 在结果上绘制标注（使用逻辑坐标）
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)

        # 标注是相对于选区左上角的逻辑坐标，offset 为 (0, 0)
        self._draw_annotations(painter, logical_rect.size(), QPoint(0, 0))
        painter.end()

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

        # ann["rect"] 是相对选区左上角的局部坐标 → 全局坐标 = 局部 + 选区偏移
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
        # drawText(QPointF, text) 将 y 坐标作为基线，需要加上 ascent 使文本顶部对齐点击位置
        fm = painter.fontMetrics()
        painter.drawText(QPointF(pos.x(), pos.y() + fm.ascent()), ann["text"])
