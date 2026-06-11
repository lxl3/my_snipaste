"""Crop mode for CaptureOverlay — state, interaction, and execution."""

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from ..core.i18n import _
from ..core.logger import setup_logger
from ..core.screenshot_history import ScreenshotHistory
from ..ui.common.toast import ToastManager

logger = setup_logger("crop_mode")


class CropMode:
    """Crop interaction state + logic, composed into CaptureOverlay.

    Expects ``overlay`` to provide:
    - selection_rect, total_geometry, full_screenshot, annotations
    - _sel_to_local(), _draw_annotations(), _position_toolbar()
    - pin_requested signal, close(), update(), setCursor()
    - toolbar (with .toolbar, .close_menus(), .animate_show())
    """

    HANDLE_SIZE = 8

    def __init__(self, overlay) -> None:
        self.overlay = overlay
        self.active: bool = False
        self.rect: QRectF | None = None
        self.dragging: bool = False
        self.start: QPointF = QPointF()
        self.handle: str = ""

    # ── Entry / exit ────────────────────────────────────────────

    def enter(self) -> None:
        """Enter crop mode."""
        self.active = True
        self.rect = None
        self.dragging = False
        self.handle = ""
        o = self.overlay
        o.toolbar.close_menus()
        o.toolbar.toolbar.hide()
        o.setCursor(Qt.CrossCursor)
        o.update()
        ToastManager.show(
            _("Drag to select area, double-click or Enter to confirm, Esc to cancel"),
            "✂", "info", parent=o, duration=3000,
        )

    def execute(self) -> None:
        """Execute crop: pin cropped area at original position and close overlay."""
        if not self.rect or self.rect.isEmpty():
            return

        x, y = self.rect.x(), self.rect.y()
        w, h = self.rect.width(), self.rect.height()

        if w <= 1 or h <= 1:
            self.exit()
            return

        o = self.overlay
        sr = o.selection_rect

        x = max(0, x)
        y = max(0, y)
        w = min(w, sr.width() - x)
        h = min(h, sr.height() - y)

        crop_screen_pos = o.total_geometry.topLeft() + sr.topLeft() + QPoint(int(x), int(y))

        dpr = o.full_screenshot.devicePixelRatio()
        phys = QRect(
            round((sr.x() + x) * dpr), round((sr.y() + y) * dpr),
            round(w * dpr), round(h * dpr),
        )
        cropped_pixmap = o.full_screenshot.copy(phys)
        cropped_pixmap.setDevicePixelRatio(dpr)

        new_w, new_h = int(w), int(h)
        crop_bounds = QRectF(0, 0, new_w, new_h)

        surviving = []
        for ann in o.annotations:
            t = ann.type
            ac = ann.clone()
            keep = False
            if t in ("rect", "ellipse", "mosaic", "highlighter", "blur", "magnifier"):
                r = ann.rect
                ro = QRectF(r.x() - x, r.y() - y, r.width(), r.height())
                keep = ro.intersects(crop_bounds)
                if keep:
                    ac.rect = ro
                if t in ("mosaic", "blur", "magnifier"):
                    ac._cached = None
            elif t in ("arrow", "line"):
                sp = QPointF(ann.start.x() - x, ann.start.y() - y)
                ep = QPointF(ann.end.x() - x, ann.end.y() - y)
                keep = crop_bounds.contains(sp) or crop_bounds.contains(ep)
                if keep:
                    ac.start = sp
                    ac.end = ep
            elif t == "freehand":
                pts = [QPointF(p.x() - x, p.y() - y) for p in ann.points]
                keep = any(crop_bounds.contains(p) for p in pts)
                if keep:
                    ac.points = pts
                ac._path = None
            elif t in ("text", "number_marker"):
                p = QPointF(ann.pos.x() - x, ann.pos.y() - y)
                keep = crop_bounds.contains(p)
                if keep:
                    ac.pos = p
            if keep:
                surviving.append(ac)

        result = QPixmap(cropped_pixmap.size())
        result.setDevicePixelRatio(dpr)
        result.fill(Qt.transparent)
        p = QPainter(result)
        p.drawPixmap(0, 0, cropped_pixmap)
        old = o.annotations
        o.annotations = surviving
        o._draw_annotations(p, result.size() / dpr, QPoint(0, 0))
        o.annotations = old
        p.end()

        try:
            ScreenshotHistory().add_screenshot(result, len(surviving) > 0)
        except Exception as e:
            logger.error(f"Failed to save screenshot to history: {e}")

        self._reset()
        o.pin_requested.emit(result, crop_screen_pos)
        o.close()
        logger.info("Cropped and pinned at (%d, %d), size %d × %d",
                     crop_screen_pos.x(), crop_screen_pos.y(), new_w, new_h)
        ToastManager.show(
            _("Cropped to {w} × {h}").format(w=new_w, h=new_h),
            "✂", "success", parent=None,
        )

    def exit(self) -> None:
        """Exit crop mode without cropping."""
        self._reset()
        o = self.overlay
        o.setCursor(Qt.ArrowCursor)
        o._position_toolbar()
        o.toolbar.toolbar.show()
        o.toolbar.animate_show()
        o.update()

    def _reset(self) -> None:
        self.active = False
        self.rect = None
        self.dragging = False
        self.handle = ""

    # ── Event dispatch ──────────────────────────────────────────

    def handle_mouse_press(self, pos: QPoint) -> None:
        local_pos = self.overlay._sel_to_local(pos)
        handle = self._get_handle(local_pos)
        if handle:
            self.handle = handle
            self.start = local_pos
            self.dragging = True
        else:
            self.rect = QRectF(local_pos, QSizeF(0, 0))
            self.start = local_pos
            self.dragging = True
            self.handle = ""

    def handle_mouse_move(self, pos: QPoint) -> None:
        local_pos = self.overlay._sel_to_local(pos)
        if self.dragging:
            if self.handle == "":
                self.rect = QRectF(self.start, local_pos).normalized()
            elif self.handle == "move":
                delta = local_pos - self.start
                self.rect.translate(delta)
                self.start = local_pos
            else:
                self._resize(local_pos)
        else:
            self._update_cursor(self._get_handle(local_pos))
        self.overlay.update()

    def handle_mouse_release(self) -> None:
        self.dragging = False
        self.handle = ""

    def handle_mouse_double_click(self, pos: QPoint) -> bool:
        """Returns True if event was consumed."""
        if not self.rect:
            return False
        local_pos = self.overlay._sel_to_local(pos)
        if self.rect.contains(local_pos):
            self.execute()
            return True
        return False

    def handle_escape(self) -> bool:
        """Returns True if event was consumed."""
        if not self.active:
            return False
        self.exit()
        return True

    def handle_enter(self) -> bool:
        """Returns True if event was consumed."""
        if not self.active:
            return False
        if self.rect and not self.rect.isEmpty():
            self.execute()
        else:
            self.exit()
        return True

    # ── Painting ────────────────────────────────────────────────

    def paint(self, painter: QPainter, sel_rect: QRect) -> None:
        """Draw crop-mode dimming, border, and handles over *sel_rect*."""
        if not self.active or sel_rect.isNull():
            return
        if not self.rect or self.rect.isEmpty():
            return

        sr = sel_rect
        cs = QRectF(
            self.rect.x() + sr.x(), self.rect.y() + sr.y(),
            self.rect.width(), self.rect.height(),
        )
        ry = int(self.rect.y())
        rh = int(self.rect.height())
        # top strip
        painter.fillRect(sr.x(), sr.y(), sr.width(), ry, QColor(0, 0, 0, 120))
        # bottom strip
        painter.fillRect(sr.x(), int(cs.bottom()), sr.width(),
                         int(sr.height() - ry - rh), QColor(0, 0, 0, 120))
        # left strip
        painter.fillRect(sr.x(), int(cs.y()), int(self.rect.x()),
                         rh, QColor(0, 0, 0, 120))
        # right strip
        painter.fillRect(int(cs.right()), int(cs.y()),
                         int(sr.width() - self.rect.x() - self.rect.width()),
                         rh, QColor(0, 0, 0, 120))
        painter.setPen(QPen(Qt.white, 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(cs)
        self._draw_handles(painter, cs)

    # ── Handle helpers ──────────────────────────────────────────

    def _get_handle(self, pos: QPointF) -> str:
        if not self.rect or self.rect.isEmpty():
            return ""
        hs = self.HANDLE_SIZE
        r = self.rect
        handles = {
            "nw": QRectF(r.left() - hs / 2, r.top() - hs / 2, hs, hs),
            "ne": QRectF(r.right() - hs / 2, r.top() - hs / 2, hs, hs),
            "sw": QRectF(r.left() - hs / 2, r.bottom() - hs / 2, hs, hs),
            "se": QRectF(r.right() - hs / 2, r.bottom() - hs / 2, hs, hs),
        }
        for name, hr in handles.items():
            if hr.contains(pos):
                return name
        if r.contains(pos):
            return "move"
        return ""

    def _update_cursor(self, handle: str) -> None:
        cursors = {
            "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
            "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
            "move": Qt.SizeAllCursor,
        }
        self.overlay.setCursor(cursors.get(handle, Qt.CrossCursor))

    def _resize(self, pos: QPointF) -> None:
        if not self.rect:
            return
        r = self.rect
        if self.handle == "nw":
            r.setTopLeft(pos)
        elif self.handle == "ne":
            r.setTopRight(pos)
        elif self.handle == "sw":
            r.setBottomLeft(pos)
        elif self.handle == "se":
            r.setBottomRight(pos)
        self.rect = r.normalized()

    def _draw_handles(self, painter: QPainter, rect: QRectF) -> None:
        hs = self.HANDLE_SIZE
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(Qt.white)
        corners = [
            (rect.left() - hs / 2, rect.top() - hs / 2),
            (rect.right() - hs / 2, rect.top() - hs / 2),
            (rect.left() - hs / 2, rect.bottom() - hs / 2),
            (rect.right() - hs / 2, rect.bottom() - hs / 2),
        ]
        for x, y in corners:
            painter.fillRect(int(x), int(y), hs, hs, Qt.white)
            painter.drawRect(int(x), int(y), hs, hs)
