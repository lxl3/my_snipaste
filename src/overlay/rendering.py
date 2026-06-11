"""Overlay rendering mixin — delegates to the unified AnnotationRenderer."""

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QPainter, QPixmap

from ..annotations import AnnotationRenderer


class _OverlaySourceProvider:
    """SourceProvider that renders effects from full_screenshot + selection_rect."""

    def __init__(self):
        self.screenshot: QPixmap | None = None
        self.selection_rect: QRectF = QRectF()

    def source_pixmap(self) -> QPixmap:
        return self.screenshot

    def local_to_source(self, local_rect: QRectF) -> QRect:
        dpr = self.screenshot.devicePixelRatio() if self.screenshot else 1.0
        return QRect(
            round((local_rect.x() + self.selection_rect.x()) * dpr),
            round((local_rect.y() + self.selection_rect.y()) * dpr),
            round(local_rect.width() * dpr),
            round(local_rect.height() * dpr),
        )


class OverlayRenderingMixin:
    """Rendering mixin that uses AnnotationRenderer internally.

    Subclass must provide:
    - self.selection_rect (QRectF)
    - self.full_screenshot (QPixmap)
    - self.annotations (list[Annotation])
    - self._preview_annotation (Annotation | None)

    Mixin expects host QWidget methods: rect(), height(), width()
    """

    def __init__(self) -> None:
        self._overlay_source = _OverlaySourceProvider()
        self._renderer = AnnotationRenderer(source=self._overlay_source)

    def _sync_renderer_source(self) -> None:
        """Keep source provider in sync with current overlay state."""
        self._overlay_source.screenshot = self.full_screenshot
        self._overlay_source.selection_rect = self.selection_rect

    def _draw_annotations(self, painter: QPainter, sel_size, offset) -> None:
        """Draw annotations + preview on painter."""
        self._sync_renderer_source()
        editing_idx = getattr(self, '_editing_annotation_idx', None)
        for idx, ann in enumerate(self.annotations):
            if editing_idx is not None and idx == editing_idx:
                continue
            self._renderer.draw(painter, ann, QPointF(offset))
        if self._preview_annotation:
            self._renderer.draw(painter, self._preview_annotation, QPointF(offset))

    def _render_annotated_pixmap(self) -> QPixmap:
        """Crop selection from screenshot and draw annotations."""
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

        self._sync_renderer_source()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_annotations(painter, logical_rect.size(), QPoint(0, 0))
        painter.end()

        return result

    def _draw_one_annotation(self, painter: QPainter, ann, offset) -> None:
        """Legacy entry point — delegates to AnnotationRenderer."""
        self._sync_renderer_source()
        self._renderer.draw(painter, ann, QPointF(offset))

    def _draw_selection_indicator(self, painter: QPainter, ann, offset) -> None:
        """Draw bounding box + handles around a selected annotation."""
        self._sync_renderer_source()
        self._renderer.draw_selection_indicator(painter, ann, QPointF(offset))
