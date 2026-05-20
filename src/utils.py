import io
import sys
import os

from PIL import Image
from PySide6.QtCore import Qt, QRect, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QImage, QPen
from PySide6.QtWidgets import QApplication


def capture_all_screens() -> QPixmap:
    screens = QApplication.screens()
    if len(screens) == 1:
        return _grab_and_fit(screens[0])

    total_rect = QRect()
    max_dpr = 1.0
    for screen in screens:
        total_rect = total_rect.united(screen.geometry())
        max_dpr = max(max_dpr, screen.devicePixelRatio())

    combined = QPixmap(total_rect.size())
    combined.setDevicePixelRatio(max_dpr)
    combined.fill(Qt.transparent)
    painter = QPainter(combined)
    for screen in screens:
        geo = screen.geometry()
        pixmap = _grab_and_fit(screen)
        painter.drawPixmap(geo.topLeft() - total_rect.topLeft(), pixmap)
    painter.end()
    return combined


def _grab_and_fit(screen) -> QPixmap:
    geo = screen.geometry()
    pixmap = screen.grabWindow(0)
    dpr = screen.devicePixelRatio()

    print(f"[诊断] 屏幕几何: {geo.width()}x{geo.height()}")
    print(f"[诊断] 截图尺寸: {pixmap.width()}x{pixmap.height()}")
    print(f"[诊断] DPR: {dpr}")
    print(f"[诊断] 截图 DPR: {pixmap.devicePixelRatio()}")

    pixmap.setDevicePixelRatio(dpr)
    print(f"[诊断] 设置后 DPR: {pixmap.devicePixelRatio()}")

    return pixmap


def qpixmap_to_pil(pixmap: QPixmap) -> Image.Image:
    qimage = pixmap.toImage()
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def qimage_to_pil(qimage: QImage) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    buffer = io.BytesIO()
    pil_image.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


def create_app_icon() -> QIcon:
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


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
