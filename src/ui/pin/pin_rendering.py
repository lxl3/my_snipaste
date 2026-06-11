"""Pin window rendering mixin — delegates to the unified AnnotationRenderer."""

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QPainter, QPixmap

from ...annotations import AnnotationRenderer


class _PinSourceProvider:
    """SourceProvider that renders effects directly from self.pixmap."""

    def __init__(self, host=None):
        self._host = host

    def source_pixmap(self) -> QPixmap | None:
        return self._host.pixmap if self._host else None

    def local_to_source(self, local_rect: QRectF) -> QRect:
        """Map logical annotation rect to physical source rect for QPixmap.copy()."""
        src = self._host.pixmap if self._host else None
        dpr = src.devicePixelRatio() if src else 1.0
        return QRect(
            round(local_rect.x() * dpr),
            round(local_rect.y() * dpr),
            round(local_rect.width() * dpr),
            round(local_rect.height() * dpr),
        )


class PinWindowRenderingMixin:
    """Rendering mixin that uses AnnotationRenderer internally.

    Subclass must provide:
    - self.pixmap (QPixmap)
    - self.annotations (list[dict])
    - self._zoom_factor (float)
    - self._selected_annotation_index (int)
    - self._base_img_w, self._base_img_h (int)
    """

    def __init__(self) -> None:
        self._pin_source = _PinSourceProvider(host=self)
        self._renderer = AnnotationRenderer(source=self._pin_source)

    # ─── Public API (called by PinWindow) ──────────────────

    def _draw_annotation(self, painter: QPainter, ann) -> None:
        """Draw a single annotation using the unified renderer."""
        self._renderer.draw(painter, ann)

    def _draw_selection_indicator(self, painter: QPainter, ann) -> None:
        """Draw bounding box + handles around a selected annotation."""
        self._renderer.draw_selection_indicator(painter, ann)

    def _render_annotated_pixmap(self) -> QPixmap:
        """Render all annotations onto a copy of the pixmap."""
        result = QPixmap(self.pixmap)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        for ann in self.annotations:
            self._renderer.draw(painter, ann)
        painter.end()
        result.setDevicePixelRatio(self.pixmap.devicePixelRatio())
        return result

    def _get_ann_bounds(self, ann) -> QRectF:
        """Get bounding rectangle of an annotation."""
        return ann.bounds()
