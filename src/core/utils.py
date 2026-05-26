import sys
import os
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QImage, QPen, QScreen, QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from .logger import setup_logger

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = setup_logger("utils")

ICON_RENDER_SIZE = 48


def load_icon_from_svg(svg_content: str, color: str = "#333333", size: int = ICON_RENDER_SIZE) -> QIcon:
    """将 SVG 字符串渲染为 QIcon，支持颜色替换和高 DPI。"""
    if not svg_content:
        from PySide6.QtGui import QIcon
        return QIcon()
    svg_data = svg_content.replace("currentColor", color)
    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(p)
    p.end()
    dpr = QApplication.primaryScreen().devicePixelRatio()
    pm.setDevicePixelRatio(dpr)
    from PySide6.QtGui import QIcon
    return QIcon(pm)


def capture_all_screens(include_cursor: bool = False) -> QPixmap:
    screens: list[QScreen] = QApplication.screens()
    cursor_pos = QCursor.pos() if include_cursor else None

    if len(screens) == 1:
        pixmap = _grab_and_fit(screens[0])
        if include_cursor and cursor_pos is not None:
            _draw_cursor(pixmap, cursor_pos, screens[0].geometry().topLeft())
        return pixmap

    total_rect = QRect()
    max_dpr = 1.0
    for screen in screens:
        total_rect = total_rect.united(screen.geometry())
        max_dpr = max(max_dpr, screen.devicePixelRatio())

    combined = QPixmap(QSize(int(total_rect.width() * max_dpr), int(total_rect.height() * max_dpr)))
    combined.setDevicePixelRatio(max_dpr)
    combined.fill(Qt.transparent)
    painter = QPainter(combined)
    for screen in screens:
        geo = screen.geometry()
        pixmap = _grab_and_fit(screen)
        if pixmap.isNull():
            painter.end()
            raise ScreenCaptureError(
                f"屏幕 {screen.name()} 截图失败，请检查屏幕录制权限。"
            )
        painter.drawPixmap(geo.topLeft() - total_rect.topLeft(), pixmap)
    painter.end()

    if include_cursor and cursor_pos is not None:
        _draw_cursor(combined, cursor_pos, total_rect.topLeft())

    return combined


class ScreenCaptureError(RuntimeError):
    """Raised when screen capture fails (e.g. missing permission)."""


def _grab_and_fit(screen: "QScreen") -> QPixmap:
    geo = screen.geometry()
    pixmap = screen.grabWindow(0)
    logger.debug(f"_grab_and_fit({screen.name()}): isNull={pixmap.isNull()} "
         f"w={pixmap.width()} h={pixmap.height()} "
         f"expected=({geo.width()}x{geo.height()})")
    if pixmap.isNull() or pixmap.width() <= 1 or pixmap.height() <= 1:
        logger.error(f"截屏失败: grabWindow 返回无效 pixmap (屏幕 {screen.name()})")
        raise ScreenCaptureError(
            "屏幕截图失败。请检查「系统设置 > 隐私与安全性 > 屏幕录制」中是否已授予权限。"
        )
    dpr = screen.devicePixelRatio()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def _draw_cursor(pixmap: QPixmap, cursor_pos: QPoint, offset: QPoint = QPoint(0, 0)) -> None:
    """Draw a cursor icon on the pixmap at the given position."""
    from PySide6.QtGui import QPolygon, QLinearGradient

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # Calculate cursor position relative to pixmap
    local_x = cursor_pos.x() - offset.x()
    local_y = cursor_pos.y() - offset.y()

    # Standard arrow cursor shape (similar to Windows default)
    scale = 1.2
    arrow_points = [
        QPoint(int(0 * scale), int(0 * scale)),
        QPoint(int(0 * scale), int(20 * scale)),
        QPoint(int(7 * scale), int(15 * scale)),
        QPoint(int(11 * scale), int(25 * scale)),
        QPoint(int(14 * scale), int(23 * scale)),
        QPoint(int(10 * scale), int(13 * scale)),
        QPoint(int(19 * scale), int(13 * scale)),
    ]

    translated_points = [QPoint(local_x + p.x(), local_y + p.y()) for p in arrow_points]
    polygon = QPolygon(translated_points)

    # Draw shadow (offset slightly for depth)
    shadow_offset = 2
    shadow_points = [QPoint(p.x() + shadow_offset, p.y() + shadow_offset) for p in translated_points]
    shadow_polygon = QPolygon(shadow_points)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 100))  # Semi-transparent black shadow
    painter.drawPolygon(shadow_polygon)

    # Draw black outline
    painter.setPen(QPen(QColor(0, 0, 0), 2))
    painter.setBrush(Qt.NoBrush)
    painter.drawPolygon(polygon)

    # Fill with gradient for a more modern look
    gradient = QLinearGradient(local_x, local_y, local_x + 10, local_y + 15)
    gradient.setColorAt(0, QColor(255, 255, 255))  # White at top
    gradient.setColorAt(1, QColor(220, 220, 220))  # Light gray at bottom
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawPolygon(polygon)

    # Add inner highlight for shine effect
    painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
    painter.drawLine(
        QPoint(local_x + 1, local_y + 1),
        QPoint(local_x + 1, local_y + int(18 * scale))
    )

    painter.end()



def qpixmap_to_pil(pixmap: QPixmap) -> "PILImage":
    return qimage_to_pil(pixmap.toImage())


def qimage_to_pil(qimage: QImage) -> "PILImage":
    qimage = qimage.convertToFormat(QImage.Format_RGBA8888)
    ptr = qimage.constBits()
    if not isinstance(ptr, memoryview):
        ptr.setsize(qimage.sizeInBytes())
    return Image.frombuffer("RGBA", (qimage.width(), qimage.height()), bytes(ptr))


def pil_to_qpixmap(pil_image: "PILImage") -> QPixmap:
    from PIL.ImageQt import ImageQt
    return QPixmap.fromImage(ImageQt(pil_image))


def create_app_icon() -> QIcon:
    """加载应用图标（优先使用自定义图标，回退到程序生成）

    Returns:
        QIcon: 应用图标对象
    """
    icon_sizes = [256, 128, 48, 32, 16]
    icon = QIcon()

    for size in icon_sizes:
        icon_path = resource_path(f"assets/icons/icon-{size}.png")
        if os.path.exists(icon_path):
            icon.addFile(icon_path)

    if not icon.isNull():
        return icon
    ico_path = resource_path("icon.ico")
    if os.path.exists(ico_path):
        return QIcon(ico_path)

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(0, 120, 215))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 10, 10)
    painter.setPen(QPen(Qt.white, 4))
    painter.setFont(QFont("Arial", 28, QFont.Bold))
    painter.drawText(QRect(4, 4, 56, 56), Qt.AlignCenter, "S")
    painter.end()
    return QIcon(pixmap)


def _get_app_dir() -> str:
    """Return the application root directory (works in dev and packaged mode)."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    import builtins
    if getattr(sys, "frozen", False) or getattr(builtins, "__compiled__", False):
        return os.path.dirname(sys.executable)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def resource_path(relative_path: str) -> str:
    return os.path.join(_get_app_dir(), relative_path)
