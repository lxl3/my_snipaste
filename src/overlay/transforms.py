"""Image transform mixin for CaptureOverlay (rotate, flip, crop)."""

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPixmap

from ..core.logger import setup_logger
from ..core.utils import pil_to_qpixmap, qpixmap_to_pil

logger = setup_logger("overlay_transforms")


class OverlayTransformsMixin:
    """Image rotation and flipping mixin for CaptureOverlay.

    Subclass must provide:
    - self.selection_rect (QRect)
    - self.full_screenshot (QPixmap)
    - self.annotations (list)
    - self.crop (CropMode)
    - self._deselect_annotation()
    - self.update()
    """

    def _crop(self) -> None:
        """Enter crop mode or execute crop if already active."""
        if self.selection_rect.isNull():
            return
        if self.crop.active and self.crop.rect and not self.crop.rect.isEmpty():
            self.crop.execute()
        else:
            self.crop.enter()

    # ── helpers ──────────────────────────────────────────────────

    def _full_logical_size(self):
        """Return (width, height) of full_screenshot in logical pixels."""
        dpr = self.full_screenshot.devicePixelRatio()
        return self.full_screenshot.width() / dpr, self.full_screenshot.height() / dpr

    def _transform_annotations(self, xform):
        """Apply callable *xform* to every annotation coordinate.

        *xform* receives (x, y) in logical image-space and returns (x', y').
        """
        sr = self.selection_rect
        for ann in self.annotations:
            t = ann.type
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                r = ann.rect
                nx, ny = xform(r.x() + sr.x(), r.y() + sr.y())
                ann.rect = QRectF(nx - sr.x(), ny - sr.y(), r.width(), r.height())
                if t in ("mosaic", "blur", "magnifier"):
                    ann._cached = None
            elif t in ("arrow", "line"):
                sx, sy = xform(ann.start.x() + sr.x(), ann.start.y() + sr.y())
                ex, ey = xform(ann.end.x() + sr.x(), ann.end.y() + sr.y())
                ann.start = QPointF(sx - sr.x(), sy - sr.y())
                ann.end = QPointF(ex - sr.x(), ey - sr.y())
            elif t == "freehand":
                new_pts = []
                for p in ann.points:
                    nx, ny = xform(p.x() + sr.x(), p.y() + sr.y())
                    new_pts.append(QPointF(nx - sr.x(), ny - sr.y()))
                ann.points = new_pts
                ann._path = None
            elif t in ("text", "number_marker"):
                nx, ny = xform(ann.pos.x() + sr.x(), ann.pos.y() + sr.y())
                ann.pos = QPointF(nx - sr.x(), ny - sr.y())

    # ── Rotate ───────────────────────────────────────────────────

    def _rotate_transform(self, angle: int) -> None:
        """Rotate the full screenshot by *angle* (±90)."""
        if self.selection_rect.isNull():
            return
        pil_img = qpixmap_to_pil(self.full_screenshot)
        dpr = self.full_screenshot.devicePixelRatio()
        old_w, old_h = self._full_logical_size()

        rotated = pil_img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
        new_pm = pil_to_qpixmap(rotated)
        new_pm.setDevicePixelRatio(dpr)
        self.full_screenshot = new_pm

        r_w = self.full_screenshot.width() / dpr
        r_h = self.full_screenshot.height() / dpr

        is_cw = (angle == -90)

        def xform_pt(x, y):
            if is_cw:
                return old_h - y, x
            else:
                return y, old_w - x

        self._transform_annotations(xform_pt)

        self.selection_rect = QRect(0, 0, round(r_w), round(r_h))
        self._deselect_annotation()
        self.update()

    def _rotate_cw(self) -> None:
        self._rotate_transform(-90)
        logger.info("Rotated clockwise")

    def _rotate_ccw(self) -> None:
        self._rotate_transform(90)
        logger.info("Rotated counter-clockwise")

    # ── Flip horizontal ──────────────────────────────────────────

    def _flip_h(self) -> None:
        """Flip screenshot and annotations horizontally."""
        if self.selection_rect.isNull():
            return
        pil_img = qpixmap_to_pil(self.full_screenshot)
        dpr = self.full_screenshot.devicePixelRatio()
        flipped = pil_img.transpose(0)
        new_pm = pil_to_qpixmap(flipped)
        new_pm.setDevicePixelRatio(dpr)
        self.full_screenshot = new_pm

        full_w, _ = self._full_logical_size()

        def xform(x, y):
            return full_w - x, y

        self._transform_annotations(xform)
        self._deselect_annotation()
        self.update()
        logger.info("Flipped horizontally")

    # ── Flip vertical ────────────────────────────────────────────

    def _flip_v(self) -> None:
        """Flip screenshot and annotations vertically."""
        if self.selection_rect.isNull():
            return
        pil_img = qpixmap_to_pil(self.full_screenshot)
        dpr = self.full_screenshot.devicePixelRatio()
        flipped = pil_img.transpose(1)
        new_pm = pil_to_qpixmap(flipped)
        new_pm.setDevicePixelRatio(dpr)
        self.full_screenshot = new_pm

        _, full_h = self._full_logical_size()

        def xform(x, y):
            return x, full_h - y

        self._transform_annotations(xform)
        self._deselect_annotation()
        self.update()
        logger.info("Flipped vertically")
