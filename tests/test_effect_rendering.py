"""Verify effect renderers (mosaic, blur, magnifier) produce correct-sized output
and correct content at both DPR=1 and DPR=2."""

import pytest
from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from src.annotations import Annotation, AnnotationRenderer
from src.annotations.renderer import SourceProvider


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication exists for Qt widget/pixmap tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _MockSource(SourceProvider):
    """Minimal source provider for testing."""

    def __init__(self, pixmap: QPixmap):
        self._pm = pixmap

    def source_pixmap(self) -> QPixmap:
        return self._pm

    def local_to_source(self, local_rect: QRectF) -> QRect:
        """Map logical annotation rect to physical source rect.
        QPixmap.copy(QRect) uses physical coordinates (confirmed on PySide6 6.9)."""
        dpr = self._pm.devicePixelRatio()
        return QRect(
            round(local_rect.x() * dpr),
            round(local_rect.y() * dpr),
            round(local_rect.width() * dpr),
            round(local_rect.height() * dpr),
        )


def _make_source(w: int, h: int, dpr: float) -> QPixmap:
    """Create a solid-colour pixmap at the given logical size and DPR."""
    phys_w = int(w * dpr)
    phys_h = int(h * dpr)
    pm = QPixmap(phys_w, phys_h)
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor(128, 128, 128))
    return pm


def _logical_size(pm: QPixmap) -> tuple[int, int]:
    """Return (logical_width, logical_height) accounting for devicePixelRatio."""
    dpr = pm.devicePixelRatio()
    return (pm.width() / dpr, pm.height() / dpr)


def _check_render_size(dpr: float) -> None:
    """Verify all three effect renderers produce display_rect-sized output."""
    logical_w, logical_h = 200, 150
    ann_rect = QRectF(10, 20, logical_w, logical_h)
    display_rect = ann_rect.toRect()
    source = _MockSource(_make_source(800, 600, dpr))
    renderer = AnnotationRenderer(source=source)

    # ── mosaic ──
    mosaic_ann = Annotation(type="mosaic", rect=ann_rect, scale=8)
    result = renderer._render_mosaic(display_rect, mosaic_ann)
    assert result is not None, f"_render_mosaic returned None at DPR={dpr}"
    lw, lh = _logical_size(result)
    assert lw == display_rect.width(), \
        f"mosaic width mismatch at DPR={dpr}: {lw} != {display_rect.width()}"
    assert lh == display_rect.height(), \
        f"mosaic height mismatch at DPR={dpr}: {lh} != {display_rect.height()}"

    # ── blur ──
    blur_ann = Annotation(type="blur", rect=ann_rect, blur_radius=5)
    result = renderer._render_blur(display_rect, blur_ann)
    assert result is not None, f"_render_blur returned None at DPR={dpr}"
    lw, lh = _logical_size(result)
    assert lw == display_rect.width(), \
        f"blur width mismatch at DPR={dpr}: {lw} != {display_rect.width()}"
    assert lh == display_rect.height(), \
        f"blur height mismatch at DPR={dpr}: {lh} != {display_rect.height()}"

    # ── magnifier ──
    mag_ann = Annotation(type="magnifier", rect=ann_rect, zoom=2.0)
    result = renderer._render_magnifier(display_rect, mag_ann)
    assert result is not None, f"_render_magnifier returned None at DPR={dpr}"
    lw, lh = _logical_size(result)
    assert lw == display_rect.width(), \
        f"magnifier width mismatch at DPR={dpr}: {lw} != {display_rect.width()}"
    assert lh == display_rect.height(), \
        f"magnifier height mismatch at DPR={dpr}: {lh} != {display_rect.height()}"


def test_render_size_dpr1(qapp) -> None:
    _check_render_size(1.0)


def test_render_size_dpr2(qapp) -> None:
    _check_render_size(2.0)


# ── Content correctness tests ──────────────────────────────────────


def _make_pattern_source(w: int, h: int, dpr: float) -> QPixmap:
    """Create a source pixmap with a red square at logical (50,50,100,100)."""
    phys_w = int(w * dpr)
    phys_h = int(h * dpr)
    pm = QPixmap(phys_w, phys_h)
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor(0, 0, 0))

    p = QPainter(pm)
    p.fillRect(QRectF(50, 50, 100, 100), QColor(255, 0, 0))
    p.end()
    return pm


def _check_mosaic_content(dpr: float) -> None:
    """Verify mosaic captures the correct source region."""
    ann_rect = QRectF(60, 60, 80, 80)
    display_rect = QRect(60, 60, 80, 80)
    source = _MockSource(_make_pattern_source(300, 300, dpr))
    renderer = AnnotationRenderer(source=source)

    result = renderer._render_mosaic(display_rect,
                                     Annotation(type="mosaic", rect=ann_rect, scale=4))
    assert result is not None


    img = result.toImage()
    red_pixels = 0
    total = img.width() * img.height()
    for x in range(img.width()):
        for y in range(img.height()):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() < 100:
                red_pixels += 1
    ratio = red_pixels / total
    assert ratio > 0.5, \
        f"Mosaic content wrong at DPR={dpr}: only {ratio:.1%} red pixels (expected >50%)"


def _check_magnifier_content(dpr: float) -> None:
    ann_rect = QRectF(50, 50, 100, 100)
    display_rect = QRect(50, 50, 100, 100)
    source = _MockSource(_make_pattern_source(300, 300, dpr))
    renderer = AnnotationRenderer(source=source)
    result = renderer._render_magnifier(display_rect,
                                        Annotation(type="magnifier", rect=ann_rect, zoom=4))
    assert result is not None

    img = result.toImage()
    red_pixels = 0
    total = img.width() * img.height()
    for x in range(img.width()):
        for y in range(img.height()):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() < 100:
                red_pixels += 1
    ratio = red_pixels / total
    assert ratio > 0.8, \
        f"Magnifier content wrong at DPR={dpr}: only {ratio:.1%} red pixels (expected >80%)"


def test_mosaic_content_dpr1(qapp) -> None:
    _check_mosaic_content(1.0)


def test_mosaic_content_dpr2(qapp) -> None:
    _check_mosaic_content(2.0)


def test_magnifier_content_dpr1(qapp) -> None:
    _check_magnifier_content(1.0)


def test_magnifier_content_dpr2(qapp) -> None:
    _check_magnifier_content(2.0)
