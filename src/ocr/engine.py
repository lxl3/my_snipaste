import os
import sys
import subprocess
import tempfile
import pytesseract
from PIL import Image
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

from ..core.utils import qpixmap_to_pil, qimage_to_pil
from ..core.logger import setup_logger

logger = setup_logger("ocr")

_tesseract_initialized = False


def ensure_tesseract_ready():
    global _tesseract_initialized
    if _tesseract_initialized:
        return True
    _tesseract_initialized = True
    return setup_bundled_tesseract()


def setup_bundled_tesseract():
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(sys.executable)
        tesseract_dir = os.path.join(base_dir, 'tesseract')

        if sys.platform == 'win32':
            tesseract_exe = os.path.join(tesseract_dir, 'tesseract.exe')
        else:
            tesseract_exe = os.path.join(tesseract_dir, 'tesseract')

        if os.path.exists(tesseract_exe):
            pytesseract.pytesseract.tesseract_cmd = tesseract_exe
            tesseract_data = os.path.join(tesseract_dir, 'tessdata')
            if os.path.exists(tesseract_data):
                os.environ['TESSDATA_PREFIX'] = tesseract_data
                logger.info(f"使用打包的 Tesseract: {tesseract_exe}")
                logger.info(f"语言包目录: {tesseract_data}")
            else:
                logger.warning(f"语言包目录不存在: {tesseract_data}")

            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract 版本: v{version}")
                return True
            except Exception as e:
                logger.error(f"打包的 Tesseract 无法运行: {e}")
                return False
        else:
            logger.warning(f"打包的 Tesseract 不存在: {tesseract_exe}")
            return _try_system_tesseract()
    else:
        return _try_system_tesseract()


def _try_system_tesseract():
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"使用系统 Tesseract v{version}")
        return True
    except Exception as e:
        logger.warning(f"系统 Tesseract 不可用: {e}")
        return False


def extract_text(pixmap_or_qimage) -> str:
    if not ensure_tesseract_ready():
        return ""

    if hasattr(pixmap_or_qimage, 'toImage'):
        pil_image = qpixmap_to_pil(pixmap_or_qimage)
    else:
        pil_image = qimage_to_pil(pixmap_or_qimage)

    try:
        text = pytesseract.image_to_string(pil_image, lang='eng+chi_sim')
        return text.strip()
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        return ""


class OcrWorker(QThread):
    """后台 OCR 工作线程（支持安全取消）"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pil_image):
        super().__init__()
        self.pil_image = pil_image
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if not ensure_tesseract_ready():
                self.error.emit("Tesseract OCR 引擎未就绪")
                return
            text = pytesseract.image_to_string(
                self.pil_image, lang='eng+chi_sim',
            )
            if not self._cancelled:
                self.finished.emit(text.strip())
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
