"""Screen color picker with magnifier view.

Opens a fullscreen transparent overlay showing a magnified pixel grid
at a fixed screen position.  Left-click anywhere copies the color under
the cursor to the clipboard and closes.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QColorDialog,
    QDialog,
    QLabel,
    QTabBar,
    QWidget,
)

from ..core.i18n import _
from ..core.logger import setup_logger
from ..core.utils import capture_all_screens

logger = setup_logger("color_picker")


def _retranslate_widget(w: QWidget) -> None:
    """Translate every text-carrying widget inside *w* using app i18n."""
    for child in w.findChildren(QAbstractButton):
        t = child.text()
        if t and _(t) != t:
            child.setText(_(t))
    for child in w.findChildren(QLabel):
        t = child.text()
        if t and _(t) != t:
            child.setText(_(t))
    for child in w.findChildren(QTabBar):
        for i in range(child.count()):
            t = child.tabText(i)
            if t and _(t) != t:
                child.setTabText(i, _(t))


class _TranslatedColorDialog(QColorDialog):
    """QColorDialog that auto-translates its UI in *showEvent*.

    Qt's built-in color dialog creates its child widgets lazily during
    the show sequence.  Translating before ``exec()`` misses them, but
    by *showEvent* every internal widget is guaranteed to exist.
    """

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _retranslate_widget(self)


def get_color(
    initial: QColor,
    parent,
    title: str,
) -> QColor:
    """Open a translated colour picker dialog.

    Unlike the plain ``QColorDialog``, this wrapper uses a subclass
    that translates every visible string (buttons, labels, tabs) via
    the app's ``_()`` function.
    """
    dlg = _TranslatedColorDialog(initial, parent)
    dlg.setWindowTitle(title)
    dlg.setOption(QColorDialog.DontUseNativeDialog)
    if dlg.exec() == QDialog.Accepted:
        return dlg.selectedColor()
    return QColor()

MAGNIFIER_SIZE = 11       # pixels to sample around cursor (odd number)
PIXEL_BASE = 10           # base pixel size at zoom=0
PIXEL_PER_ZOOM = 1        # extra pixels per zoom level
CROSSHAIR_COLOR = QColor(255, 255, 255)
CROSSHAIR_ALT = QColor(0, 0, 0)
INFO_BAR_HEIGHT = 28
OUTER_MARGIN = 8


class ScreenColorPicker(QWidget):
    """Fullscreen transparent overlay color picker.

    Left-click anywhere on screen → picks the color under the cursor,
    copies it to the clipboard, and closes.
    """

    color_selected = Signal(str)  # emits the selected hex color

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Fullscreen geometry (all monitors)
        self._total_geometry = QRect()
        for screen in QApplication.screens():
            self._total_geometry = self._total_geometry.united(screen.geometry())
        self.setGeometry(self._total_geometry)

        # Full screenshot at init time
        self._screenshot = capture_all_screens(include_cursor=False)
        self._zoom = 8  # default magnification factor
        self._mouse_pos = QCursor.pos()

        # Fixed scene origin (center-right of the screen)
        self._scene_origin = QPoint(
            self._total_geometry.center().x() + 60,
            self._total_geometry.center().y(),
        )
        self._recalc_layout()

        self.setCursor(Qt.CrossCursor)

        # Poll mouse position at ~60fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_mouse)
        self._timer.start(16)
        self.update()  # ensure first paint before user clicks

    # ── layout helpers ──────────────────────────────────────────────

    @property
    def _pixel_size(self) -> int:
        return PIXEL_BASE + self._zoom * PIXEL_PER_ZOOM

    @property
    def _grid_px(self) -> int:
        return MAGNIFIER_SIZE * self._pixel_size

    def _recalc_layout(self) -> None:
        """Recalculate sub-rectangles when zoom changes."""
        gp = self._grid_px

        # Center vertically, offset right from screen center
        half_scene = (gp + INFO_BAR_HEIGHT + OUTER_MARGIN * 2) // 2
        self._scene_origin.setY(self._total_geometry.center().y() - half_scene)

        self._grid_origin = QPoint(
            self._scene_origin.x() + OUTER_MARGIN,
            self._scene_origin.y() + OUTER_MARGIN,
        )
        self._info_rect = QRect(
            self._grid_origin.x(),
            self._grid_origin.y() + gp + 4,
            gp, INFO_BAR_HEIGHT,
        )

    # ── core logic ──────────────────────────────────────────────────

    def _pick_color(self) -> None:
        """Copy color at current cursor position and close."""
        mx, my = self._mouse_pos.x(), self._mouse_pos.y()
        dpr = self._screenshot.devicePixelRatio()
        sx = max(0, min(int(mx * dpr), self._screenshot.width() - 1))
        sy = max(0, min(int(my * dpr), self._screenshot.height() - 1))
        color = QColor(self._screenshot.toImage().pixel(sx, sy))
        hex_str = f"#{color.red():02X}{color.green():02X}{color.blue():02X}"

        QApplication.clipboard().setText(hex_str)
        logger.info(f"Color picker: copied {hex_str}")

        self.color_selected.emit(hex_str)
        self.close()

    def _poll_mouse(self) -> None:
        """Track cursor position and repaint."""
        pos = QCursor.pos()
        if pos != self._mouse_pos:
            self._mouse_pos = pos
            self.update()

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Semi-transparent dark overlay (matches CaptureOverlay pattern)
        # Colors are still read from the initial screenshot, never from this overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

        mx, my = self._mouse_pos.x(), self._mouse_pos.y()
        half = MAGNIFIER_SIZE // 2
        dpr = self._screenshot.devicePixelRatio()
        ps = self._pixel_size
        gp = self._grid_px

        # ── Dark backdrop behind the magnifier scene only ──
        scene_bg = QRect(
            self._scene_origin.x() - 4,
            self._scene_origin.y() - 4,
            gp + OUTER_MARGIN * 2 + 8,
            gp + INFO_BAR_HEIGHT + OUTER_MARGIN * 2 + 8,
        )
        painter.fillRect(scene_bg, QColor(30, 30, 30, 240))

        # Draw magnified pixel grid
        for gy in range(MAGNIFIER_SIZE):
            for gx in range(MAGNIFIER_SIZE):
                sx = int((mx - half + gx) * dpr)
                sy = int((my - half + gy) * dpr)
                sx = max(0, min(sx, self._screenshot.width() - 1))
                sy = max(0, min(sy, self._screenshot.height() - 1))

                color = QColor(self._screenshot.toImage().pixel(sx, sy))
                px = self._grid_origin.x() + gx * ps
                py = self._grid_origin.y() + gy * ps

                painter.fillRect(px, py, ps, ps, color)
                painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
                painter.drawRect(px, py, ps, ps)

        # Crosshair on center pixel
        cx = self._grid_origin.x() + half * ps + ps // 2
        cy = self._grid_origin.y() + half * ps + ps // 2
        ch_len = ps // 2 + 2

        center_sx = int(mx * dpr)
        center_sy = int(my * dpr)
        center_sx = max(0, min(center_sx, self._screenshot.width() - 1))
        center_sy = max(0, min(center_sy, self._screenshot.height() - 1))
        center_color = QColor(self._screenshot.toImage().pixel(center_sx, center_sy))
        luminance = (0.299 * center_color.red() + 0.587 * center_color.green()
                     + 0.114 * center_color.blue())
        cross_color = CROSSHAIR_ALT if luminance > 128 else CROSSHAIR_COLOR

        painter.setPen(QPen(cross_color, 2))
        painter.drawLine(cx - ch_len, cy, cx + ch_len, cy)
        painter.drawLine(cx, cy - ch_len, cx, cy + ch_len)

        # Outer border around grid
        grid_rect = QRect(self._grid_origin, QSize(gp, gp))
        painter.setPen(QPen(cross_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(grid_rect)

        # ── Info bar ──
        hex_str = f"#{center_color.red():02X}{center_color.green():02X}{center_color.blue():02X}"
        rgb_str = f"RGB({center_color.red()}, {center_color.green()}, {center_color.blue()})"

        info_bg = QRect(self._info_rect)
        painter.fillRect(info_bg, QColor(40, 40, 40, 230))
        painter.setPen(Qt.NoPen)
        painter.drawRect(info_bg)

        font = QFont("Consolas", 11, QFont.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()

        painter.setPen(Qt.white)
        painter.drawText(info_bg.adjusted(6, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, hex_str)

        minor_font = QFont("Consolas", 10)
        painter.setFont(minor_font)
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(info_bg.adjusted(0, 0, -6, 0), Qt.AlignVCenter | Qt.AlignRight, rgb_str)

        swatch_rect = QRect(info_bg.left() + fm.horizontalAdvance(hex_str) + 14,
                            info_bg.top() + 4, 20, info_bg.height() - 8)
        painter.fillRect(swatch_rect, center_color)
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(swatch_rect)

    # ── events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pick_color()
        elif event.button() == Qt.RightButton:
            self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._pick_color()

    def wheelEvent(self, event) -> None:
        """Scroll to change zoom level (4-20x)."""
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(20, self._zoom + 2)
        elif delta < 0:
            self._zoom = max(4, self._zoom - 2)
        self._recalc_layout()
        self.update()

    def closeEvent(self, event) -> None:
        """Clean up on close."""
        self._timer.stop()
        self.deleteLater()
        super().closeEvent(event)
