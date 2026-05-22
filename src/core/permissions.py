import platform
import subprocess

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from .logger import setup_logger

logger = setup_logger("permissions")


def check_macos_input_permission() -> bool:
    """检查 macOS 输入监听权限。macOS 14+ 需要「输入监控」权限接收全局键盘事件。"""
    if platform.system() != "Darwin":
        return True

    try:
        import ctypes
        import ctypes.util
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        for name in ("CGPreflightListenEventAccess",):
            func = getattr(cg, name, None)
            if func:
                func.restype = ctypes.c_bool
                func.argtypes = []
                if not func():
                    return False
        return True
    except Exception as e:
        logger.warning(f"检查输入监控权限失败: {e}")
        return True


def check_macos_accessibility() -> bool:
    """检查 macOS 辅助功能和输入监控权限，未授权时弹窗引导用户设置。"""
    if platform.system() != "Darwin":
        return True

    mac_ver = platform.mac_ver()[0]
    is_sequoia = mac_ver.startswith("15.") if mac_ver else False

    trusted = False
    has_input = True
    try:
        import ctypes
        import ctypes.util
        lib_path = ctypes.util.find_library("ApplicationServices")
        if lib_path:
            lib = ctypes.cdll.LoadLibrary(lib_path)
            trusted = bool(lib.AXIsProcessTrusted())
        has_input = check_macos_input_permission()
    except Exception as e:
        logger.warning(f"检查权限失败: {e}")
        return True

    if trusted and has_input and not is_sequoia:
        return True

    parts = []
    if not trusted:
        parts.append("辅助功能")
    if not has_input:
        parts.append("输入监控")
    if is_sequoia and (trusted and has_input):
        parts.append("应用签名")

    title = "需要权限"
    text = f"MySnipaste 需要「{'」和「'.join(parts)}」权限"
    info = (
        "macOS 限制了全局快捷键监听，请按以下步骤操作：\n\n"
        "1. 打开「系统设置」→「隐私与安全性」\n"
    )
    if not trusted:
        info += "2. 找到「辅助功能」，点击右侧「+」添加 MySnipaste\n"
    if not has_input:
        info += "3. 找到「输入监控」，点击右侧「+」添加 MySnipaste\n"
    if is_sequoia:
        info += (
            "4. macOS 15+ 需要应用签名：\n"
            "   • 将应用打包为 .app 并使用开发者证书签名\n"
            "   • 或使用其他快捷键（如 ⌘+Shift+S）绕过系统限制\n"
        )
    info += "\n授权后请重启应用。"

    msg = QMessageBox()
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setInformativeText(info)
    msg.setIcon(QMessageBox.Warning)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
    msg.exec()

    try:
        subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
    except Exception:
        pass

    return trusted and has_input and not is_sequoia
