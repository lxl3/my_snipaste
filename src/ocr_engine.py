import sys
import pytesseract
from PIL import Image
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

from .utils import qpixmap_to_pil, qimage_to_pil


def check_tesseract_langs():
    """检查 Tesseract 可用的语言"""
    try:
        langs = pytesseract.get_languages()
        return langs
    except:
        return []


def get_optimal_lang():
    """获取最优的语言设置"""
    available_langs = check_tesseract_langs()

    # 优先使用中英文
    if 'chi_sim' in available_langs and 'eng' in available_langs:
        return 'eng+chi_sim'
    elif 'chi_sim' in available_langs:
        return 'chi_sim'
    elif 'eng' in available_langs:
        return 'eng'
    else:
        return None


class OcrWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pil_image: Image.Image, lang: str = None):
        super().__init__()
        self.pil_image = pil_image
        self.lang = lang if lang else get_optimal_lang()

    def run(self):
        try:
            if self.lang is None:
                self.error.emit("未找到可用的语言包")
                return
            text = pytesseract.image_to_string(self.pil_image, lang=self.lang)
            self.finished.emit(text.strip())
        except Exception as e:
            self.error.emit(str(e))


def extract_text(pixmap_or_qimage, lang: str = None) -> str:
    try:
        if hasattr(pixmap_or_qimage, "toImage"):
            pil_image = qpixmap_to_pil(pixmap_or_qimage)
        else:
            pil_image = qimage_to_pil(pixmap_or_qimage)

        # 自动检测最优语言
        if lang is None:
            lang = get_optimal_lang()
            if lang is None:
                QMessageBox.warning(
                    None,
                    "语言包缺失",
                    "未检测到任何 Tesseract 语言包。\n\n"
                    "请安装语言包：\n"
                    "1. 下载中文语言包 chi_sim.traineddata\n"
                    "   https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata\n\n"
                    "2. 将文件放到 Tesseract 的 tessdata 目录\n"
                    "   (通常在 C:\\Program Files\\Tesseract-OCR\\tessdata)\n\n"
                    "3. 重启程序",
                )
                return ""

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
            "安装时请勾选 Additional Language Data 选项以安装中文支持。",
        )
        return ""
    except pytesseract.TesseractError as e:
        error_msg = str(e)
        if "chi_sim" in error_msg or "language" in error_msg.lower():
            QMessageBox.warning(
                None,
                "语言包缺失",
                "中文语言包未安装。\n\n"
                "请下载并安装：\n"
                "1. 下载 chi_sim.traineddata\n"
                "   https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata\n\n"
                "2. 放到 Tesseract tessdata 目录\n"
                "   (C:\\Program Files\\Tesseract-OCR\\tessdata)\n\n"
                f"详细错误：{error_msg}",
            )
        else:
            QMessageBox.critical(
                None,
                "OCR 错误",
                f"文字提取失败：\n{error_msg}",
            )
        return ""
    except Exception as e:
        QMessageBox.critical(
            None,
            "OCR 错误",
            f"文字提取失败：\n{str(e)}",
        )
        return ""
