import platform

from .logger import setup_logger

logger = setup_logger("permissions")


def check_macos_accessibility() -> bool:
    """检查 macOS 环境（仅用于日志记录）。

    macOS 上的全局快捷键已改用 Quartz CGEventSourceKeyState 轮询，
    不需要辅助功能或输入监控权限。
    """
    if platform.system() != "Darwin":
        return True

    _log_permission_status()
    return True


def _log_permission_status():
    """记录当前权限状态供调试参考。"""
    trusted = _check_ax_trusted()
    has_input = _check_input_monitoring()

    if not trusted:
        logger.info("辅助功能: 未授权（当前方案不需要此权限）")
    if not has_input:
        logger.info("输入监控: 未授权（当前方案不需要此权限）")
    if trusted and has_input:
        logger.info("macOS 权限齐全")


def _check_ax_trusted() -> bool:
    """检查辅助功能权限。出错时返回 False 避免崩溃。"""
    try:
        import ctypes
        lib_path = _find_framework("ApplicationServices")
        if not lib_path:
            return False
        lib = ctypes.cdll.LoadLibrary(lib_path)
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return False


def _check_input_monitoring() -> bool:
    """检查输入监控权限 (macOS 14+)。出错时返回 False。"""
    try:
        import ctypes
        lib_path = _find_framework("CoreGraphics")
        if not lib_path:
            return False
        cg = ctypes.cdll.LoadLibrary(lib_path)
        func = getattr(cg, "CGPreflightListenEventAccess", None)
        if func:
            func.restype = ctypes.c_bool
            func.argtypes = []
            return func()
        return False
    except Exception:
        return False


def _find_framework(name: str) -> str | None:
    """查找 macOS framework 路径。"""
    import ctypes.util
    import os
    path = ctypes.util.find_library(name)
    if path:
        return path
    fallback = f"/System/Library/Frameworks/{name}.framework/{name}"
    return fallback if os.path.exists(fallback) else None
