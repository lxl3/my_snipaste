import sys
import pytesseract
from PIL import Image
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

from .utils import qpixmap_to_pil, qimage_to_pil


class OcrWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pil_image: Image.Image, lang: str = "eng+chi_sim"):
        super().__init__()
        self.pil_image = pil_image
        self.lang = lang

    def run(self):
        try:
            text = pytesseract.image_to_string(self.pil_image, lang=self.lang)
            self.finished.emit(text.strip())
        except Exception as e:
            self.error.emit(str(e))


def extract_text(pixmap_or_qimage, lang: str = "eng+chi_sim") -> str:
    try:
        if hasattr(pixmap_or_qimage, "toImage"):
            pil_image = qpixmap_to_pil(pixmap_or_qimage)
        else:
            pil_image = qimage_to_pil(pixmap_or_qimage)

        text = pytesseract.image_to_string(pil_image, lang=lang)
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        QMessageBox.critical(
            None,
            "未找到 Tesseract",
            "Tesseract OCR 引擎未安装。\n\n"
            "请安装它：\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  macOS: brew install tesseract\n\n"
            "然后将其添加到系统 PATH 中。",
        )
        return ""
    except Exception as e:
        QMessageBox.critical(
            None,
            "OCR 错误",
            f"文字提取失败：\n{str(e)}",
        )
        return ""
