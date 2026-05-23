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
    """Log macOS permission status (informational only)."""
    if platform.system() != "Darwin":
        return True
    _log_permission_status()
    return True


def check_screen_recording_permission() -> bool | None:
    """Check Screen Recording permission (tri-state).

    Returns:
      True  = granted
      False = denied (macOS 14+ only)
      None  = unknown (macOS 13-, falls back to capture error)
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
            logger.debug("CGPreflightScreenCaptureAccess unavailable (macOS 13-)")
            return None
        preflight.restype = ctypes.c_bool
        result = preflight()
        logger.debug(f"CGPreflightScreenCaptureAccess → {result}")
        logger.info(f"screen recording permission: {result}")
        return result
    except Exception as e:
        logger.debug(f"permission check error: {e}")
        logger.warning(f"permission check failed: {e}")
        return None


def request_screen_recording_permission() -> bool:
    """Request Screen Recording permission."""
    if platform.system() != "Darwin":
        return True

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
                logger.debug(f"CGRequestScreenCaptureAccess → {granted}")
                logger.info(f"permission request result: {granted}")
                if granted:
                    return True
    except Exception as e:
        logger.debug(f"CGRequestScreenCaptureAccess error: {e}")

    logger.debug("open System Settings → Screen Recording")
    open_screen_recording_settings()
    return False


def request_input_monitoring_permission() -> bool:
    """Request Input Monitoring permission (macOS 14+)."""
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
            logger.debug("CGRequestListenEventAccess unavailable (macOS 13-)")
            return False
        req.restype = ctypes.c_bool
        granted = req()
        logger.debug(f"CGRequestListenEventAccess → {granted}")
        logger.info(f"input monitoring permission: {granted}")
        return granted
    except Exception as e:
        logger.debug(f"CGRequestListenEventAccess error: {e}")
        return False


def open_screen_recording_settings() -> None:
    """Open System Settings → Privacy & Security → Screen Recording."""
    try:
        subprocess.run(["open", SETTINGS_URL_SCREEN], check=True, timeout=5,
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception as e:
        logger.debug(f"open screen recording settings failed: {e}")
        logger.warning(f"open screen recording settings failed: {e}")


def open_input_monitoring_settings() -> None:
    """Open System Settings → Privacy & Security → Input Monitoring."""
    try:
        subprocess.run(["open", SETTINGS_URL_INPUT], check=True, timeout=5,
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception as e:
        logger.debug(f"open input monitoring settings failed: {e}")
        logger.warning(f"open input monitoring settings failed: {e}")


def show_permission_guide() -> None:
    """Log permission guidance (once)."""
    global _SCREEN_CAPTURE_WARNED
    if _SCREEN_CAPTURE_WARNED:
        return
    _SCREEN_CAPTURE_WARNED = True
    logger.warning("=" * 60)
    logger.warning("  MySnipaste needs Screen Recording permission")
    logger.warning("  System Settings > Privacy & Security > Screen Recording")
    logger.warning("  Add and enable MySnipaste")
    logger.warning("=" * 60)


def _log_permission_status() -> None:
    trusted = _check_ax_trusted()
    has_input = _check_input_monitoring()
    if not trusted:
        logger.info("accessibility: not granted (not required by current impl)")
    if not has_input:
        logger.info("input monitoring: not granted (not required by current impl)")
    if trusted and has_input:
        logger.info("macOS permissions all set")


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
