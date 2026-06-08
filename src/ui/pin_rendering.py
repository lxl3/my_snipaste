"""Pin window rendering mixin for annotations."""

import math
from PIL import ImageFilter

from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF

from ..core.constants import ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, MOSAIC_SCALE_FACTOR
from ..core.utils import qpixmap_to_pil, pil_to_qpixmap


class PinWindowRenderingMixin:
    """Rendering logic for pin window annotations.

    Subclass must provide:
    - self.pixmap (QPixmap)
    - self.annotations (list[dict])
    - self._zoom_factor (float)
    - self._selected_annotation_index (int)
    - self._base_img_w, self._base_img_h (int)
    """

    # ─── Annotation Drawing ───────────────────────────────

    def _draw_annotation(self, painter: QPainter, ann: dict) -> None:
        t = ann["type"]
        if t == "rect":
            self._draw_rect(painter, ann)
        elif t == "ellipse":
            self._draw_ellipse(painter, ann)
        elif t == "arrow":
            self._draw_arrow(painter, ann)
        elif t == "line":
            self._draw_line(painter, ann)
        elif t == "freehand":
            self._draw_freehand(painter, ann)
        elif t == "text":
            self._draw_text_item(painter, ann)
        elif t == "highlighter":
            self._draw_highlighter(painter, ann)
        elif t == "number_marker":
            self._draw_number_marker(painter, ann)
        elif t == "mosaic":
            self._draw_mosaic(painter, ann)
        elif t == "blur":
            self._draw_blur(painter, ann)
        elif t == "magnifier":
            self._draw_magnifier(painter, ann)

    def _draw_rect(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _draw_ellipse(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(r)

    def _draw_arrow(self, painter: QPainter, ann: dict) -> None:
        start = QPointF(*ann["start"])
        end = QPointF(*ann["end"])
        width = ann["width"]
        color = QColor(ann["color"])
        arrow_style = ann.get("arrow_style", "solid")

        # Draw shaft line
        painter.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

        # Calculate arrowhead geometry
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        base = ARROW_SIZE_BASE + width * 2
        spread = base * math.tan(ARROW_SPREAD_ANGLE)
        p1 = QPointF(end.x() - ux * base + uy * spread,
                     end.y() - uy * base - ux * spread)
        p2 = QPointF(end.x() - ux * base - uy * spread,
                     end.y() - uy * base + ux * spread)

        if arrow_style in ("solid", "solid_tail"):
            # Solid: filled triangle
            path = QPainterPath()
            path.moveTo(end)
            path.lineTo(p1)
            path.lineTo(p2)
            path.closeSubpath()
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
        else:
            # Hollow: outline V shape (no fill)
            painter.setPen(QPen(color, max(1, width), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            v_path = QPainterPath()
            v_path.moveTo(p1)
            v_path.lineTo(end)
            v_path.lineTo(p2)
            painter.drawPath(v_path)

        if arrow_style in ("solid_tail", "hollow_tail"):
            # With tail: perpendicular line at the arrow base (p1 → p2)
            painter.setPen(QPen(color, max(1, width), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(p1, p2)

    def _draw_line(self, painter: QPainter, ann: dict) -> None:
        start = QPointF(*ann["start"])
        end = QPointF(*ann["end"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

    def _draw_freehand(self, painter: QPainter, ann: dict) -> None:
        pts = [QPointF(*p) for p in ann["points"]]
        if len(pts) < 2:
            return
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(pts[0])
        for i in range(1, len(pts)):
            path.lineTo(pts[i])
        painter.drawPath(path)

    def _draw_text_item(self, painter: QPainter, ann: dict) -> None:
        # Support both tuple and QPointF formats
        pos_data = ann["pos"]
        if isinstance(pos_data, QPointF):
            pos = pos_data
        else:
            pos = QPointF(*pos_data)
        painter.setFont(QFont(ann["font_family"], ann["font_size"]))
        font = painter.font()
        font.setBold(ann["bold"])
        font.setItalic(ann["italic"])
        painter.setFont(font)
        painter.setPen(QColor(ann["color"]))
        fm = painter.fontMetrics()
        painter.drawText(QPointF(pos.x(), pos.y() + fm.ascent()), ann["text"])

    def _draw_highlighter(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        c = QColor(ann["color"])
        c.setAlphaF(0.3)
        hl_width = ann.get("width", 12)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawRoundedRect(r, hl_width / 2, hl_width / 2)

    def _draw_number_marker(self, painter: QPainter, ann: dict) -> None:
        center = QPointF(*ann["pos"])
        radius = ann.get("radius", 14)
        number = ann.get("number", 1)
        color = QColor(ann.get("color", "#207ff0"))
        text_color = QColor(ann.get("text_color", "#ffffff"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, radius, radius)
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

    def _draw_mosaic(self, painter: QPainter, ann: dict) -> None:
        """Draw mosaic effect by pixelating the region."""
        r = QRectF(*ann["rect"]).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            scale = ann.get("scale", MOSAIC_SCALE_FACTOR)
            dpr = self.pixmap.devicePixelRatio()

            # Extract region from pixmap
            src_rect = QRect(
                int(r.x() * dpr),
                int(r.y() * dpr),
                int(r.width() * dpr),
                int(r.height() * dpr)
            )
            px = self.pixmap.copy(src_rect)

            # Pixelate: scale down then scale up
            small_w = max(1, r.width() // scale)
            small_h = max(1, r.height() // scale)
            small = px.scaled(small_w, small_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            cached = small.scaled(r.width(), r.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

    def _draw_blur(self, painter: QPainter, ann: dict) -> None:
        """Draw blur effect using Gaussian blur."""
        r = QRectF(*ann["rect"]).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            radius = ann.get("radius", 10)
            dpr = self.pixmap.devicePixelRatio()

            # Extract region from pixmap
            src_rect = QRect(
                int(r.x() * dpr),
                int(r.y() * dpr),
                int(r.width() * dpr),
                int(r.height() * dpr)
            )
            px = self.pixmap.copy(src_rect)

            # Apply Gaussian blur via PIL
            pil_img = qpixmap_to_pil(px)
            blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=radius))
            cached = pil_to_qpixmap(blurred)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

    def _draw_magnifier(self, painter: QPainter, ann: dict) -> None:
        """Draw magnifier effect by zooming the region."""
        r = QRectF(*ann["rect"]).toRect()
        if r.isEmpty():
            return

        cached = ann.get("_cached")
        if cached is None:
            zoom = ann.get("zoom", 2)
            dpr = self.pixmap.devicePixelRatio()

            # Calculate source area (center of magnifier rect, smaller by zoom factor)
            center_x = r.center().x()
            center_y = r.center().y()
            src_w = r.width() / zoom
            src_h = r.height() / zoom

            src_rect = QRect(
                int((center_x - src_w / 2) * dpr),
                int((center_y - src_h / 2) * dpr),
                max(1, int(src_w * dpr)),
                max(1, int(src_h * dpr))
            )

            # Extract and scale up
            px = self.pixmap.copy(src_rect)
            cached = px.scaled(r.width(), r.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ann["_cached"] = cached

        painter.drawPixmap(r.topLeft(), cached)

        # Draw border
        painter.setPen(QPen(QColor("#207ff0"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _draw_selection_indicator(self, painter: QPainter, ann: dict) -> None:
        bounds = self._get_ann_bounds(ann)
        if bounds.isNull():
            return
        painter.setPen(QPen(QColor(0, 120, 215), 1.5, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(bounds)
        half = 4
        handles = [
            QRectF(bounds.left() - half, bounds.top() - half, 8, 8),
            QRectF(bounds.right() - half, bounds.top() - half, 8, 8),
            QRectF(bounds.left() - half, bounds.bottom() - half, 8, 8),
            QRectF(bounds.right() - half, bounds.bottom() - half, 8, 8),
        ]
        for h_rect in handles:
            painter.fillRect(h_rect, QColor(0, 120, 215))
            painter.setPen(QPen(Qt.white, 1))
            painter.drawRect(h_rect)

    def _get_ann_bounds(self, ann: dict) -> QRectF:
        t = ann["type"]
        if t in ("rect", "ellipse", "highlighter"):
            return QRectF(*ann["rect"])
        elif t in ("arrow", "line"):
            return QRectF(QPointF(*ann["start"]), QPointF(*ann["end"])).normalized()
        elif t == "freehand":
            pts = ann.get("points", [])
            if not pts:
                return QRectF()
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        elif t == "text":
            pos = QPointF(*ann["pos"])
            return QRectF(pos.x(), pos.y(), 1, 1)
        elif t == "number_marker":
            pos = QPointF(*ann["pos"])
            r = ann.get("radius", 14)
            return QRectF(pos.x() - r, pos.y() - r, r * 2, r * 2)
        return QRectF()
