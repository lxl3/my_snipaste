"""Overlay rendering mixin for annotations."""

import math

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize

from PIL import ImageFilter

from ..core.constants import (
    ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, MOSAIC_SCALE_FACTOR,
    HANDLE_SIZE, DEFAULT_LINE_WIDTH,
)
from ..core.utils import qpixmap_to_pil, pil_to_qpixmap


class OverlayRenderingMixin:
    """Rendering logic for all annotation types.

    Subclass must provide:
    - self.selection_rect (QRectF)
    - self.full_screenshot (QPixmap)
    - self.annotations (list[dict])
    - self._preview_annotation (dict | None)

    Mixin expects host QWidget methods: rect(), height(), width()
    """

    def _draw_annotations(self, painter: QPainter, sel_size, offset) -> None:
        """Draw annotations + preview on painter."""
        for ann in self.annotations:
            self._draw_one_annotation(painter, ann, offset)
        if self._preview_annotation:
            self._draw_one_annotation(painter, self._preview_annotation, offset)

    def _render_annotated_pixmap(self) -> QPixmap:
        """Crop selection from screenshot and draw annotations.

        High DPI note: coordinate conversion is manual.
        - selection_rect is in logical (screen) coords
        - full_screenshot physical size = logical size x devicePixelRatio
        - must copy from full_screenshot in physical coords
        """
        logical_rect = self.selection_rect
        if logical_rect.isNull():
            return QPixmap()

        dpr = self.full_screenshot.devicePixelRatio()

        physical_rect = QRect(
            int(logical_rect.x() * dpr),
            int(logical_rect.y() * dpr),
            int(logical_rect.width() * dpr),
            int(logical_rect.height() * dpr),
        )

        result = self.full_screenshot.copy(physical_rect)
        result.setDevicePixelRatio(dpr)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_annotations(painter, logical_rect.size(), QPoint(0, 0))
        painter.end()

        return result

    def _draw_one_annotation(self, painter: QPainter, ann: dict, offset) -> None:
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
        elif t == "highlighter":
            self._draw_highlighter(painter, ann, offset)
        elif t == "blur":
            self._draw_blur(painter, ann, offset)
        elif t == "number_marker":
            self._draw_number_marker(painter, ann, offset)
        elif t == "magnifier":
            self._draw_magnifier(painter, ann, offset)
        elif t == "text":
            self._draw_text(painter, ann, offset)

    def _draw_rect(self, painter: QPainter, ann: dict, offset) -> None:
        r = ann["rect"].translated(offset)
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _draw_ellipse(self, painter: QPainter, ann: dict, offset) -> None:
        r = ann["rect"].translated(offset)
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(r)

    def _draw_arrow(self, painter: QPainter, ann: dict, offset) -> None:
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

    def _draw_line(self, painter: QPainter, ann: dict, offset) -> None:
        start = ann["start"] + offset
        end = ann["end"] + offset
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

    def _draw_freehand(self, painter: QPainter, ann: dict, offset) -> None:
        pts = ann["points"]
        if len(pts) < 2:
            return
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        path = ann.get("_path")
        if path is None:
            path = QPainterPath()
            path.moveTo(pts[0])
            for i in range(1, len(pts)):
                path.lineTo(pts[i])
            ann["_path"] = QPainterPath(path)
        painter.drawPath(path.translated(offset))

    def _draw_mosaic(self, painter: QPainter, ann: dict, offset) -> None:
        r = QRectF(ann["rect"]).translated(offset).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            dpr = self.full_screenshot.devicePixelRatio()
            scale = ann.get("scale", MOSAIC_SCALE_FACTOR)

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
            cached = small.scaled(r.width(), r.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

    def _draw_text(self, painter: QPainter, ann: dict, offset) -> None:
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

    def _draw_highlighter(self, painter: QPainter, ann: dict, offset) -> None:
        r = QRectF(ann["rect"]).translated(offset)
        c = QColor(ann["color"])
        c.setAlphaF(0.3)  # Semi-transparent
        hl_width = ann.get("width", 12)  # thick by default
        # Use a thick rounded pen for highlighter effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawRoundedRect(r, hl_width / 2, hl_width / 2)

    def _draw_blur(self, painter: QPainter, ann: dict, offset) -> None:
        r = QRectF(ann["rect"]).translated(offset).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            dpr = self.full_screenshot.devicePixelRatio()
            radius = ann.get("radius", 10)

            local_rect = QRectF(ann["rect"])
            global_x = round((local_rect.x() + self.selection_rect.x()) * dpr)
            global_y = round((local_rect.y() + self.selection_rect.y()) * dpr)

            # Capture the source region
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

            # Apply Gaussian blur via PIL
            pil_img = qpixmap_to_pil(px)
            blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=radius))
            cached = pil_to_qpixmap(blurred)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

    def _draw_number_marker(self, painter: QPainter, ann: dict, offset) -> None:
        center = ann["pos"] + offset
        radius = ann.get("radius", 14)
        number = ann.get("number", 1)
        color = QColor(ann.get("color", "#207ff0"))
        text_color = QColor(ann.get("text_color", "#ffffff"))

        # Draw filled circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, radius, radius)

        # Draw number text centered in circle
        font = painter.font()
        font.setPixelSize(radius)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        fm = painter.fontMetrics()
        text = str(number)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        text_x = center.x() - tw / 2
        text_y = center.y() + fm.ascent() / 2
        painter.drawText(QPointF(text_x, text_y), text)

    def _draw_magnifier(self, painter: QPainter, ann: dict, offset) -> None:
        r = QRectF(ann["rect"]).translated(offset).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            dpr = self.full_screenshot.devicePixelRatio()
            zoom = ann.get("zoom", 2)

            local_rect = QRectF(ann["rect"])
            center_x = local_rect.center().x()
            center_y = local_rect.center().y()

            # Source area in logical coords = magnifier area / zoom
            src_logical_w = r.width() / zoom
            src_logical_h = r.height() / zoom

            # Source area in device pixels (full_screenshot coordinates)
            src_pixel_x = round((center_x - src_logical_w / 2 + self.selection_rect.x()) * dpr)
            src_pixel_y = round((center_y - src_logical_h / 2 + self.selection_rect.y()) * dpr)
            src_pixel_w = max(1, round(src_logical_w * dpr))
            src_pixel_h = max(1, round(src_logical_h * dpr))

            # Extract native-resolution source at 1/zoom size
            src = QRect(src_pixel_x, src_pixel_y, src_pixel_w, src_pixel_h)
            px = QPixmap(src.size())
            px.fill(Qt.transparent)
            p2 = QPainter(px)
            p2.drawPixmap(px.rect(), self.full_screenshot, src)
            p2.end()

            # Smoothly scale up to magnifier display size
            cached = px.scaled(r.width(), r.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

        # Draw border around magnifier
        painter.setPen(QPen(QColor(0, 120, 215), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    # ─── Selection indicator ───

    def _draw_selection_indicator(self, painter: QPainter, ann: dict, offset) -> None:
        """Draw bounding box + handles around a selected annotation."""
        if ann["type"] in ("arrow", "line"):
            self._draw_arrow_handles(painter, ann, offset)
            return
        local_bounds = self._get_annotation_bounds_local(ann)
        if local_bounds.isNull():
            return
        # Convert local → global coords
        global_bounds = local_bounds.translated(offset)
        # Dashed blue bounding box
        painter.setPen(QPen(QColor(0, 120, 215), 1.5, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(global_bounds)
        # 8 square handles (4 corners + 4 edge midpoints)
        half = HANDLE_SIZE // 2
        handles = [
            QRect(int(global_bounds.left()) - half, int(global_bounds.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.right()) - half, int(global_bounds.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.left()) - half, int(global_bounds.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.right()) - half, int(global_bounds.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.center().x()) - half, int(global_bounds.top()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.center().x()) - half, int(global_bounds.bottom()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.left()) - half, int(global_bounds.center().y()) - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(int(global_bounds.right()) - half, int(global_bounds.center().y()) - half, HANDLE_SIZE, HANDLE_SIZE),
        ]
        for h_rect in handles:
            painter.fillRect(h_rect, Qt.white)
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            painter.drawRect(h_rect)

    def _draw_arrow_handles(self, painter: QPainter, ann: dict, offset) -> None:
        """Draw only 2 outline handles at arrow/line start and end."""
        half = HANDLE_SIZE // 2
        sp = QPointF(ann["start"]) + QPointF(offset)
        ep = QPointF(ann["end"]) + QPointF(offset)
        for pt in (sp, ep):
            rect = QRect(int(pt.x()) - half, int(pt.y()) - half, HANDLE_SIZE, HANDLE_SIZE)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(Qt.white, 1.5))
            painter.drawRect(rect)
