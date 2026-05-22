import platform
import subprocess

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from .logger import setup_logger

logger = setup_logger("permissions")


def check_macos_accessibility() -> bool:
    """检查并引导 macOS 辅助功能/输入监控权限。

    注意：macOS 15+ 上直接调用 AXIsProcessTrusted() 会触发 SIGTRAP，
    所以采用折中方案：仅检查输入监控权限，如果缺失则弹窗引导。
    即使检查返回 False，热键仍可能正常使用（取决于用户是否已授权）。
    """
    if platform.system() != "Darwin":
        return True

    has_input = _check_input_monitoring()

    if has_input:
        logger.info("macOS 输入监控权限已授权")
        return True

    _show_permission_dialog()
    return False


def _check_input_monitoring() -> bool:
    """检查输入监控权限 (macOS 14+)，出错时返回 True 避免误判。"""
    try:
        import ctypes
        lib_path = _find_framework("CoreGraphics")
        if not lib_path:
            return True
        cg = ctypes.cdll.LoadLibrary(lib_path)
        func = getattr(cg, "CGPreflightListenEventAccess", None)
        if func:
            func.restype = ctypes.c_bool
            func.argtypes = []
            result = func()
            logger.info(f"CGPreflightListenEventAccess = {result}")
            return result
        return True
    except Exception as e:
        logger.warning(f"检查输入监控权限异常: {e}")
        return True


def _find_framework(name: str) -> str | None:
    """查找 macOS framework 路径。"""
    import ctypes.util
    path = ctypes.util.find_library(name)
    if path:
        return path
    fallback = f"/System/Library/Frameworks/{name}.framework/{name}"
    import os
    if os.path.exists(fallback):
        return fallback
    return None


def _show_permission_dialog():
    """显示权限引导对话框。"""
    info = (
        "MySnipaste 需要「输入监控」权限来监听全局快捷键。\n\n"
        "请按以下步骤操作：\n"
        "1. 打开「系统设置」→「隐私与安全性」\n"
        "2. 找到「输入监控」，点击右侧「+」\n"
        "3. 添加「终端」或「iTerm2」\n"
        "4. 授权后重启应用\n\n"
        "提示：即使不授权，点击托盘图标也可以截图。"
    )

    msg = QMessageBox()
    msg.setWindowTitle("需要权限")
    msg.setText("MySnipaste 需要输入监控权限")
    msg.setInformativeText(info)
    msg.setIcon(QMessageBox.Warning)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.exec()

    try:
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_InputMonitoring"
        ])
    except Exception:
        pass
