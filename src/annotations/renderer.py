"""Unified annotation renderer.

Draws a single ``Annotation`` onto a ``QPainter``, independent of whether
the host is an overlay widget or a pin window.  Effect annotations
(mosaic, blur, magnifier) require a *source provider* callback that
extracts the appropriate region from the underlying screenshot / pixmap.
"""

from __future__ import annotations

import math
from typing import Protocol

from PIL import ImageFilter
from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

from ..core.constants import ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, HANDLE_SIZE
from ..core.utils import pil_to_qpixmap, qpixmap_to_pil
from .models import Annotation

# ── Source provider protocol ──────────────────────────────────────


class SourceProvider(Protocol):
    """Protocol for providing source image data to effect renderers.

    Implementations map a local-coordinate rectangle to the corresponding
    region in the source image (full_screenshot for overlay, pixmap for
    pin_window).
    """

    def source_pixmap(self) -> QPixmap:
        """The full-resolution source image."""
        ...

    def local_to_source(self, local_rect: QRectF) -> QRect:
        """Convert a local-coord rectangle to a pixel rect in *source_pixmap*."""
        ...


# ── Renderer ──────────────────────────────────────────────────────


class AnnotationRenderer:
    """Stateless renderer for one annotation.

    Parameters
    ----------
    source:
        Optional source provider for effect annotations.  When ``None``,
        mosaic/blur/magnifier fall back to drawing a transparent rect.
    """

    def __init__(self, source: SourceProvider | None = None) -> None:
        self.source = source

    # ── public API ─────────────────────────────────────────────

    def draw(self, painter: QPainter, ann: Annotation,
             offset: QPointF = QPointF()) -> None:
        """Dispatch and draw *ann* on *painter*.

        *offset* is added to every coordinate (used by overlay for
        selection-relative → screen-space translation).
        """
        t = ann.type
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
        elif t == "text":
            self._draw_text(painter, ann, offset)
        elif t == "highlighter":
            self._draw_highlighter(painter, ann, offset)
        elif t == "number_marker":
            self._draw_number_marker(painter, ann, offset)
        elif t == "mosaic":
            self._draw_mosaic(painter, ann, offset)
        elif t == "blur":
            self._draw_blur(painter, ann, offset)
        elif t == "magnifier":
            self._draw_magnifier(painter, ann, offset)

    def draw_selection_indicator(self, painter: QPainter, ann: Annotation,
                                 offset: QPointF = QPointF()) -> None:
        """Bounding box + handles around a selected annotation."""
        if ann.type in ("arrow", "line"):
            self._draw_arrow_handles(painter, ann, offset)
            return
        local_bounds = ann.bounds()
        if local_bounds.isNull():
            return
        gb = local_bounds.translated(offset)
        # dashed blue bounding box
        painter.setPen(QPen(QColor(0, 120, 215), 1.5, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(gb)
        # 8 square handles
        half = HANDLE_SIZE // 2
        handles = [
            (gb.left(), gb.top()),
            (gb.right(), gb.top()),
            (gb.left(), gb.bottom()),
            (gb.right(), gb.bottom()),
            (gb.center().x(), gb.top()),
            (gb.center().x(), gb.bottom()),
            (gb.left(), gb.center().y()),
            (gb.right(), gb.center().y()),
        ]
        for hx, hy in handles:
            r = QRect(int(hx) - half, int(hy) - half, HANDLE_SIZE, HANDLE_SIZE)
            painter.fillRect(r, Qt.white)
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            painter.drawRect(r)

    # ── shape annotations ──────────────────────────────────────

    @staticmethod
    def _draw_rect(painter: QPainter, ann: Annotation,
                   offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset)
        painter.setPen(QPen(QColor(ann.color), ann.width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    @staticmethod
    def _draw_ellipse(painter: QPainter, ann: Annotation,
                      offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset)
        painter.setPen(QPen(QColor(ann.color), ann.width))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(r)

    # ── arrow / line ───────────────────────────────────────────

    @staticmethod
    def _draw_arrow(painter: QPainter, ann: Annotation,
                    offset: QPointF) -> None:
        start = QPointF(ann.start) + offset
        end = QPointF(ann.end) + offset
        width = ann.width
        color = QColor(ann.color)

        painter.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

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

        style = ann.arrow_style
        if style in ("solid", "solid_tail"):
            path = QPainterPath()
            path.moveTo(end)
            path.lineTo(p1)
            path.lineTo(p2)
            path.closeSubpath()
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
        else:
            painter.setPen(QPen(color, max(1, width), Qt.SolidLine,
                                Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            v = QPainterPath()
            v.moveTo(p1)
            v.lineTo(end)
            v.lineTo(p2)
            painter.drawPath(v)

        if style in ("solid_tail", "hollow_tail"):
            painter.setPen(QPen(color, max(1, width), Qt.SolidLine,
                                Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(p1, p2)

    @staticmethod
    def _draw_line(painter: QPainter, ann: Annotation,
                   offset: QPointF) -> None:
        start = QPointF(ann.start) + offset
        end = QPointF(ann.end) + offset
        painter.setPen(QPen(QColor(ann.color), ann.width,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

    # ── freehand ───────────────────────────────────────────────

    @staticmethod
    def _draw_freehand(painter: QPainter, ann: Annotation,
                       offset: QPointF) -> None:
        pts = ann.points or []
        if len(pts) < 2:
            return
        painter.setPen(QPen(QColor(ann.color), ann.width,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        path = ann._path
        if path is None or offset != QPointF():
            # build / rebuild if offset is non-zero
            path = QPainterPath()
            path.moveTo(pts[0])
            for i in range(1, len(pts)):
                path.lineTo(pts[i])
            if offset == QPointF():
                ann._path = QPainterPath(path)
        painter.drawPath(path.translated(offset))

    # ── text ───────────────────────────────────────────────────

    @staticmethod
    def _draw_text(painter: QPainter, ann: Annotation,
                   offset: QPointF) -> None:
        pos = QPointF(ann.pos) + offset
        painter.setFont(QFont(ann.font_family, ann.font_size))
        font = painter.font()
        font.setBold(ann.bold)
        font.setItalic(ann.italic)
        painter.setFont(font)
        painter.setPen(QColor(ann.color))
        fm = painter.fontMetrics()
        painter.drawText(QPointF(pos.x(), pos.y() + fm.ascent()), ann.text)

    # ── highlighter ────────────────────────────────────────────

    @staticmethod
    def _draw_highlighter(painter: QPainter, ann: Annotation,
                          offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset)
        c = QColor(ann.color)
        c.setAlphaF(0.3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawRoundedRect(r, ann.width / 2, ann.width / 2)

    # ── number marker ──────────────────────────────────────────

    @staticmethod
    def _draw_number_marker(painter: QPainter, ann: Annotation,
                            offset: QPointF) -> None:
        center = QPointF(ann.pos) + offset
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ann.color))
        painter.drawEllipse(center, ann.radius, ann.radius)

        font = painter.font()
        font.setPixelSize(ann.radius)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ann.text_color))
        fm = painter.fontMetrics()
        text = str(ann.number)
        tw = fm.horizontalAdvance(text)
        text_x = center.x() - tw / 2
        text_y = center.y() + fm.ascent() / 2
        painter.drawText(QPointF(text_x, text_y), text)

    # ── effect annotations (mosaic, blur, magnifier) ───────────

    def _draw_mosaic(self, painter: QPainter, ann: Annotation,
                     offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset).toRect()
        if r.isEmpty():
            return
        cached = ann._cached
        if cached is None:
            cached = self._render_mosaic(r, ann)
        if cached:
            painter.drawPixmap(r.topLeft(), cached)

    def _render_mosaic(self, display_rect: QRect, ann: Annotation) -> QPixmap | None:
        src = self.source
        if src is None:
            return None
        source_rect = src.local_to_source(QRectF(ann.rect))
        px = src.source_pixmap().copy(source_rect)
        dpr = px.devicePixelRatio()
        scale = ann.scale
        small = px.scaled(max(1, px.width() // scale),
                          max(1, px.height() // scale),
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        result = small.scaled(round(display_rect.width() * dpr),
                              round(display_rect.height() * dpr),
                              Qt.IgnoreAspectRatio, Qt.FastTransformation)
        ann._cached = result
        return result

    def _draw_blur(self, painter: QPainter, ann: Annotation,
                   offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset).toRect()
        if r.isEmpty():
            return
        cached = ann._cached
        if cached is None:
            cached = self._render_blur(r, ann)
        if cached:
            painter.drawPixmap(r.topLeft(), cached)

    def _render_blur(self, display_rect: QRect, ann: Annotation) -> QPixmap | None:
        src = self.source
        if src is None:
            return None
        source_rect = src.local_to_source(QRectF(ann.rect))
        px = src.source_pixmap().copy(source_rect)
        dpr = px.devicePixelRatio()
        pil_img = qpixmap_to_pil(px)
        blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=ann.blur_radius))
        result = pil_to_qpixmap(blurred)
        result.setDevicePixelRatio(dpr)
        ann._cached = result
        return result

    def _draw_magnifier(self, painter: QPainter, ann: Annotation,
                        offset: QPointF) -> None:
        r = QRectF(ann.rect).translated(offset).toRect()
        if r.isEmpty():
            return
        cached = ann._cached
        if cached is None:
            cached = self._render_magnifier(r, ann)
        if cached:
            painter.drawPixmap(r.topLeft(), cached)
        # border
        painter.setPen(QPen(QColor(0, 120, 215), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _render_magnifier(self, display_rect: QRect, ann: Annotation) -> QPixmap | None:
        src = self.source
        if src is None:
            return None
        zoom = ann.zoom
        local_rect = QRectF(ann.rect)
        center = local_rect.center()
        src_w = local_rect.width() / zoom
        src_h = local_rect.height() / zoom
        zoom_local_rect = QRectF(center.x() - src_w / 2, center.y() - src_h / 2, src_w, src_h)
        source_rect = src.local_to_source(zoom_local_rect)
        px = src.source_pixmap().copy(source_rect)
        dpr = px.devicePixelRatio()
        result = px.scaled(round(display_rect.width() * dpr),
                           round(display_rect.height() * dpr),
                           Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        ann._cached = result
        return result

    # ── arrow handle indicator (for selection display) ─────────

    @staticmethod
    def _draw_arrow_handles(painter: QPainter, ann: Annotation,
                            offset: QPointF) -> None:
        half = HANDLE_SIZE // 2
        sp = QPointF(ann.start) + offset
        ep = QPointF(ann.end) + offset
        for pt in (sp, ep):
            r = QRect(int(pt.x()) - half, int(pt.y()) - half,
                      HANDLE_SIZE, HANDLE_SIZE)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(Qt.white, 1.5))
            painter.drawRect(r)
