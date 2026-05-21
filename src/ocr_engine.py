import os
import sys
import pytesseract
from PIL import Image
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

from .utils import qpixmap_to_pil, qimage_to_pil


def setup_bundled_tesseract():
    """
    当程序通过 PyInstaller 打包运行时，自动配置打包的 Tesseract 路径。
    PyInstaller onefile 模式会将文件解压到 sys._MEIPASS 临时目录。
    """
    if getattr(sys, 'frozen', False):
        # 运行在 PyInstaller 打包的 exe 中
        base_dir = sys._MEIPASS
        tesseract_dir = os.path.join(base_dir, 'tesseract')
        tesseract_exe = os.path.join(tesseract_dir, 'tesseract.exe')

        if os.path.exists(tesseract_exe):
            # 设置 pytesseract 使用打包的 tesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_exe

            # 设置 TESSDATA_PREFIX 环境变量
            tessdata_dir = os.path.join(tesseract_dir, 'tessdata')
            if os.path.exists(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir

            return True
        else:
            # 打包的 tesseract 不存在，尝试从网络下载
            return _download_tesseract_runtime(tesseract_dir)
    return False


def _download_tesseract_runtime(target_dir):
    """
    运行时下载 Tesseract（当打包版本不存在时）。
    下载到一个持久化目录，避免每次启动都下载。
    """
    import urllib.request
    import tempfile
    import subprocess

    # 使用用户本地 AppData 目录作为持久化存储
    local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~/.local'))
    runtime_dir = os.path.join(local_appdata, 'MySnipaste', 'tesseract_runtime')
    tesseract_exe = os.path.join(runtime_dir, 'tesseract.exe')

    if os.path.exists(tesseract_exe):
        pytesseract.pytesseract.tesseract_cmd = tesseract_exe
        tessdata_dir = os.path.join(runtime_dir, 'tessdata')
        if os.path.exists(tessdata_dir):
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
        return True

    # 检查系统是否已安装 Tesseract
    system_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in system_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tessdata_dir = os.path.join(os.path.dirname(path), 'tessdata')
            if os.path.exists(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
            return True

    # 系统未安装，尝试下载
    try:
        os.makedirs(runtime_dir, exist_ok=True)

        download_url = (
            "https://github.com/tesseract-ocr/tesseract/releases/"
            "download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
        )

        temp_installer = os.path.join(tempfile.gettempdir(), 'tesseract_install.exe')
        urllib.request.urlretrieve(download_url, temp_installer)

        # 运行静默安装
        result = subprocess.run(
            [temp_installer, '/VERYSILENT', '/SUPPRESSMSGBOXES',
             f'/DIR={runtime_dir}', '/NORESTART', '/NOICONS'],
            capture_output=True, timeout=120
        )

        # 清理安装文件
        if os.path.exists(temp_installer):
            os.remove(temp_installer)

        if os.path.exists(tesseract_exe):
            pytesseract.pytesseract.tesseract_cmd = tesseract_exe
            tessdata_dir = os.path.join(runtime_dir, 'tessdata')
            if os.path.exists(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
            return True

    except Exception:
        pass

    return False


# 模块加载时自动配置打包的 tesseract
setup_bundled_tesseract()


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
