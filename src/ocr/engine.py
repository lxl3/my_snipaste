import os
import sys
import subprocess
import tempfile
import shutil
import pytesseract
from PIL import Image
from PySide6.QtCore import QThread, Signal

from ..core.i18n import _
from ..core.utils import qpixmap_to_pil, qimage_to_pil
from ..core.logger import setup_logger
from ..core.settings import get_settings

logger = setup_logger("ocr")

_tesseract_initialized: bool = False


def ensure_tesseract_ready() -> bool:
    global _tesseract_initialized
    if _tesseract_initialized:
        return True
    _tesseract_initialized = True
    return setup_bundled_tesseract()


def setup_bundled_tesseract() -> bool:
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


def _try_system_tesseract() -> bool:
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"使用系统 Tesseract v{version}")
        return True
    except Exception as e:
        logger.warning(f"系统 Tesseract 不可用: {e}")
        return False


def extract_text(pixmap_or_qimage, ocr_lang: str | None = None) -> str:
    """Run OCR on a QPixmap or QImage and return the recognized text."""
    if not ensure_tesseract_ready():
        return ""

    if hasattr(pixmap_or_qimage, 'toImage'):
        pil_image = qpixmap_to_pil(pixmap_or_qimage)
    else:
        pil_image = qimage_to_pil(pixmap_or_qimage)

    try:
        if ocr_lang is None:
            ocr_lang = get_settings().ocr_language
        text = pytesseract.image_to_string(pil_image, lang=ocr_lang)
        return text.strip()
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        return ""


class OcrWorker(QThread):
    """后台 OCR 工作线程，可安全取消（终止 tesseract 子进程而非线程）"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pil_image: Image.Image, ocr_lang: str | None = None) -> None:
        super().__init__()
        self.pil_image = pil_image
        self._proc: subprocess.Popen | None = None
        self._cancelled: bool = False
        self._ocr_lang: str = ocr_lang or get_settings().ocr_language

    def cancel(self) -> None:
        self._cancelled = True
        if self._proc:
            self._proc.kill()

    def run(self) -> None:
        tmp_dir = None
        try:
            if not ensure_tesseract_ready():
                self.error.emit(_("Tesseract OCR engine is not ready"))
                return

            tmp_dir = tempfile.mkdtemp(prefix="mysnipaste_ocr_")
            input_path = os.path.join(tmp_dir, "input.png")
            self.pil_image.save(input_path, format="PNG")

            output_base = os.path.join(tmp_dir, "output")
            tess_cmd = pytesseract.pytesseract.tesseract_cmd
            self._proc = subprocess.Popen(
                [tess_cmd, input_path, output_base, "-l", self._ocr_lang],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

            try:
                self._proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
                self._proc = None
                if not self._cancelled:
                    self.error.emit(_("OCR timed out"))
                return

            output_path = output_base + ".txt"
            text = ""
            if os.path.exists(output_path):
                with open(output_path, encoding="utf-8") as f:
                    text = f.read().strip()

            if not self._cancelled:
                self.finished.emit(text)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
        finally:
            self._proc = None
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
