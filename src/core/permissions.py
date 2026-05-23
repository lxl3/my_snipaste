import platform
import subprocess
import sys

from .logger import setup_logger

logger = setup_logger("permissions")

_SCREEN_CAPTURE_WARNED = False

SETTINGS_URL_SCREEN = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
)
SETTINGS_URL_INPUT = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
)


def check_macos_accessibility() -> bool:
    """检查 macOS 环境（仅用于日志记录）"""
    if platform.system() != "Darwin":
        return True
    _log_permission_status()
    return True


def check_screen_recording_permission():
    """检测屏幕录制权限。

    返回三态:
      True  = 已授权
      False = 未授权（仅 macOS 14+ 可准确检测）
      None  = 无法判断（macOS 13-，走实际截图异常捕获）
    """
    if platform.system() != "Darwin":
        return True

    try:
        import ctypes
        import ctypes.util
        cg_path = ctypes.util.find_library("CoreGraphics")
        if not cg_path:
            return None
        cg = ctypes.cdll.LoadLibrary(cg_path)
        preflight = getattr(cg, "CGPreflightScreenCaptureAccess", None)
        if not preflight:
            _d("CGPreflightScreenCaptureAccess API 不可用（macOS 13-）")
            return None
        preflight.restype = ctypes.c_bool
        result = preflight()
        _d(f"CGPreflightScreenCaptureAccess → {result}")
        logger.info(f"屏幕录制权限: {result}")
        return result
    except Exception as e:
        _d(f"权限检测异常: {e}")
        logger.warning(f"权限检测失败: {e}")
        return None


def request_screen_recording_permission():
    """请求屏幕录制权限并打开系统设置页。

    返回 True 表示已授权，False 表示被拒绝/不可用。
    """
    if platform.system() != "Darwin":
        return True

    # macOS 14+ 原生请求 API
    try:
        import ctypes
        import ctypes.util
        cg_path = ctypes.util.find_library("CoreGraphics")
        if cg_path:
            cg = ctypes.cdll.LoadLibrary(cg_path)
            req = getattr(cg, "CGRequestScreenCaptureAccess", None)
            if req:
                req.restype = ctypes.c_bool
                granted = req()
                _d(f"CGRequestScreenCaptureAccess → {granted}")
                logger.info(f"权限请求结果: {granted}")
                if granted:
                    return True
    except Exception as e:
        _d(f"CGRequestScreenCaptureAccess 异常: {e}")

    # 打开系统设置
    _d("打开系统设置 → 屏幕录制")
    open_screen_recording_settings()
    return False


def request_input_monitoring_permission() -> bool:
    """请求输入监控权限 (macOS 14+)。

    返回 True 表示已授权或已弹出请求，False 表示不可用。
    """
    if platform.system() != "Darwin":
        return True
    try:
        import ctypes
        import ctypes.util
        cg_path = ctypes.util.find_library("CoreGraphics")
        if not cg_path:
            return False
        cg = ctypes.cdll.LoadLibrary(cg_path)
        req = getattr(cg, "CGRequestListenEventAccess", None)
        if not req:
            _d("CGRequestListenEventAccess API 不可用（macOS 13-）")
            return False
        req.restype = ctypes.c_bool
        granted = req()
        _d(f"CGRequestListenEventAccess → {granted}")
        logger.info(f"输入监控权限请求结果: {granted}")
        return granted
    except Exception as e:
        _d(f"CGRequestListenEventAccess 异常: {e}")
        return False


def open_screen_recording_settings():
    """打开系统设置的「屏幕录制」页面。"""
    try:
        subprocess.run(["open", SETTINGS_URL_SCREEN], check=True, timeout=5,
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception as e:
        _d(f"打开系统设置失败: {e}")
        logger.warning(f"打开系统设置失败: {e}")


def open_input_monitoring_settings():
    """打开系统设置的「输入监控」页面。"""
    try:
        subprocess.run(["open", SETTINGS_URL_INPUT], check=True, timeout=5,
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception as e:
        _d(f"打开输入监控设置失败: {e}")
        logger.warning(f"打开输入监控设置失败: {e}")


def show_permission_guide():
    """日志输出权限引导（仅一次）。"""
    global _SCREEN_CAPTURE_WARNED
    if _SCREEN_CAPTURE_WARNED:
        return
    _SCREEN_CAPTURE_WARNED = True
    logger.warning("=" * 60)
    logger.warning("  MySnipaste 需要「屏幕录制」权限")
    logger.warning("  系统设置 > 隐私与安全性 > 屏幕录制")
    logger.warning("  添加并授权 MySnipaste")
    logger.warning("=" * 60)


def _d(msg: str):
    """写入调试日志。"""
    import time as _t
    with open("/tmp/my_snipaste_permissions.log", "a") as f:
        f.write(f"[{_t.strftime('%H:%M:%S')}] {msg}\n")


def _log_permission_status():
    trusted = _check_ax_trusted()
    has_input = _check_input_monitoring()
    if not trusted:
        logger.info("辅助功能: 未授权（当前方案不需要此权限）")
    if not has_input:
        logger.info("输入监控: 未授权（当前方案不需要此权限）")
    if trusted and has_input:
        logger.info("macOS 权限齐全")


def _check_ax_trusted() -> bool:
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
    import ctypes.util
    import os
    path = ctypes.util.find_library(name)
    if path:
        return path
    fallback = f"/System/Library/Frameworks/{name}.framework/{name}"
    return fallback if os.path.exists(fallback) else None
