import os
import sys
import pytesseract
from PIL import Image
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

from ..core.utils import qpixmap_to_pil, qimage_to_pil
from ..core.logger import setup_logger

logger = setup_logger("ocr")

# Tesseract 初始化状态
_tesseract_initialized = False


def ensure_tesseract_ready():
    """延迟初始化 Tesseract，只在首次使用时执行"""
    global _tesseract_initialized
    if _tesseract_initialized:
        return True

    _tesseract_initialized = True
    return setup_bundled_tesseract()


def setup_bundled_tesseract():
    """
    当程序通过 PyInstaller 打包运行时，自动配置打包的 Tesseract 路径。
    支持 Windows (.exe) 和 macOS (.app) 打包版本。
    """
    if getattr(sys, 'frozen', False):
        # 运行在 PyInstaller 打包的应用中
        base_dir = sys._MEIPASS
        tesseract_dir = os.path.join(base_dir, 'tesseract')

        # 根据平台选择可执行文件名
        if sys.platform == 'win32':
            tesseract_exe = os.path.join(tesseract_dir, 'tesseract.exe')
        else:  # macOS/Linux
            tesseract_exe = os.path.join(tesseract_dir, 'tesseract')

        if os.path.exists(tesseract_exe):
            # 设置 pytesseract 使用打包的 tesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_exe

            # 设置语言包目录
            tesseract_data = os.path.join(tesseract_dir, 'tessdata')
            if os.path.exists(tesseract_data):
                os.environ['TESSDATA_PREFIX'] = tesseract_data
                logger.info(f"使用打包的 Tesseract: {tesseract_exe}")
                logger.info(f"语言包目录: {tesseract_data}")
            else:
                logger.warning(f"语言包目录不存在: {tesseract_data}")

            # 验证 Tesseract 是否可用
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract 版本: v{version}")
                return True
            except Exception as e:
                logger.error(f"打包的 Tesseract 无法运行: {e}")
                return False
        else:
            logger.warning(f"打包的 Tesseract 不存在: {tesseract_exe}")
            # 尝试使用系统 Tesseract
            return _try_system_tesseract()
    else:
        # 开发模式：检查系统 tesseract 是否可用
        return _try_system_tesseract()


def _try_system_tesseract():
    """尝试使用系统安装的 Tesseract"""
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"使用系统 Tesseract v{version}")
        return True
    except Exception as e:
        logger.warning(f"系统 Tesseract 不可用: {e}")
        return False


def extract_text(pixmap_or_qimage) -> str:
    """对 QPixmap 或 QImage 执行 OCR，返回文本。"""
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
    """后台 OCR 工作线程"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pil_image: Image.Image):
        super().__init__()
        self.pil_image = pil_image

    def run(self):
        try:
            if not ensure_tesseract_ready():
                self.error.emit("Tesseract OCR 引擎未就绪")
                return
            text = pytesseract.image_to_string(
                self.pil_image, lang='eng+chi_sim',
            )
            self.finished.emit(text.strip())
        except Exception as e:
            self.error.emit(str(e))
