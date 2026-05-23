import io
import sys
import os
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QRect, QRectF, QSize, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QImage, QPen, QScreen
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


def capture_all_screens() -> QPixmap:
    screens: list[QScreen] = QApplication.screens()
    if len(screens) == 1:
        return _grab_and_fit(screens[0])

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



def qpixmap_to_pil(pixmap: QPixmap) -> "PILImage":
    qimage = pixmap.toImage()
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def qimage_to_pil(qimage: QImage) -> "PILImage":
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def pil_to_qpixmap(pil_image: "PILImage") -> QPixmap:
    buffer = io.BytesIO()
    pil_image.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


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
