import os
import platform
import subprocess

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
    """Check macOS permissions and return if Input Monitoring is granted.

    Returns:
        bool: True if on non-macOS or Input Monitoring granted, False otherwise
    """
    if platform.system() != "Darwin":
        return True

    status = get_permission_status()
    _log_permission_status_detailed(status)

    # Input Monitoring is critical for global hotkeys
    return status.get("input_monitoring", False)


def _macos_version() -> tuple[int, int] | None:
    try:
        v = platform.mac_ver()[0]
        parts = v.split(".")
        if len(parts) >= 2:
            return (int(parts[0]), int(parts[1]))
    except Exception:
        pass
    return None


def check_screen_recording_permission() -> bool | None:
    """Check Screen Recording permission (tri-state).

    Returns:
      True  = granted
      False = denied (macOS 14+ only)
      None  = unknown (macOS 13-, falls back to capture error)
    """
    if platform.system() != "Darwin":
        return True

    mac_ver = _macos_version()
    if mac_ver and mac_ver < (14, 0):
        logger.info(
            f"macOS {mac_ver[0]}.{mac_ver[1]} detected — "
            "Screen Recording permission API requires macOS 14+; "
            "will attempt capture directly"
        )
        return None

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
    logger.warning("  openSnipaste needs Screen Recording permission")
    logger.warning("  System Settings > Privacy & Security > Screen Recording")
    logger.warning("  Add and enable openSnipaste")
    logger.warning("=" * 60)


def get_permission_status() -> dict[str, bool]:
    """Get current permission status for all required permissions.

    Returns:
        dict: {"accessibility": bool, "input_monitoring": bool, "screen_recording": bool}
    """
    if platform.system() != "Darwin":
        return {
            "accessibility": True,
            "input_monitoring": True,
            "screen_recording": True,
        }

    return {
        "accessibility": _check_ax_trusted(),
        "input_monitoring": _check_input_monitoring(),
        "screen_recording": check_screen_recording_permission() or False,
    }


def _log_permission_status() -> None:
    """Deprecated: use _log_permission_status_detailed() instead."""
    status = get_permission_status()
    _log_permission_status_detailed(status)


def _log_permission_status_detailed(status: dict[str, bool]) -> None:
    """Log detailed permission status."""
    if status["input_monitoring"]:
        logger.info("✓ Input Monitoring 权限已授予（全局快捷键可用）")
    else:
        logger.warning("✗ Input Monitoring 权限未授予（全局快捷键不可用）")

    if status["screen_recording"]:
        logger.info("✓ Screen Recording 权限已授予")
    elif status["screen_recording"] is None:
        logger.info("• Screen Recording 权限状态未知（macOS 13-）")
    else:
        logger.warning("✗ Screen Recording 权限未授予")

    if not status["accessibility"]:
        logger.debug("• Accessibility 权限未授予（当前实现不需要）")

    if status["input_monitoring"] and status["screen_recording"]:
        logger.info("🎉 所有必需权限已就绪")


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
    path = ctypes.util.find_library(name)
    if path:
        return path
    fallback = f"/System/Library/Frameworks/{name}.framework/{name}"
    return fallback if os.path.exists(fallback) else None


def show_permission_dialog(parent=None) -> None:
    """Show a user-friendly permission status dialog with action buttons.

    Args:
        parent: Parent widget for the dialog (optional)
    """
    if platform.system() != "Darwin":
        return

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        status = get_permission_status()

        # Build status message
        lines = ["openSnipaste 需要以下权限才能正常工作：\n"]

        if status["input_monitoring"]:
            lines.append("✓ Input Monitoring（输入监控）- 已授予")
        else:
            lines.append("✗ Input Monitoring（输入监控）- 未授予")
            lines.append("  → 全局快捷键需要此权限")

        lines.append("")

        if status["screen_recording"]:
            lines.append("✓ Screen Recording（屏幕录制）- 已授予")
        elif status["screen_recording"] is None:
            lines.append("• Screen Recording（屏幕录制）- 状态未知")
        else:
            lines.append("✗ Screen Recording（屏幕录制）- 未授予")

        msg = QMessageBox(parent)
        msg.setWindowTitle("权限检查")
        msg.setText("\n".join(lines))

        if not status["input_monitoring"]:
            msg.setIcon(QMessageBox.Warning)
            msg.setInformativeText(
                "\n如何授予权限：\n"
                "1. 点击下方「打开系统设置」按钮\n"
                "2. 在「输入监控」中勾选 openSnipaste\n"
                "3. 完全退出并重启应用\n\n"
                "注意：直接点击窗口关闭按钮不会完全退出，\n"
                "请从托盘菜单选择「退出」。"
            )

            # Add "Open Settings" button
            open_btn = msg.addButton("打开系统设置", QMessageBox.ActionRole)
            open_btn.clicked.connect(open_input_monitoring_settings)
            msg.addButton("稍后处理", QMessageBox.RejectRole)
        else:
            msg.setIcon(QMessageBox.Information)
            msg.setInformativeText("\n所有必需权限已就绪 ✓")
            msg.addButton(QMessageBox.Ok)

        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        msg.exec()

    except ImportError:
        logger.warning("无法显示权限对话框：PySide6 未导入")
    except Exception as e:
        logger.error(f"显示权限对话框失败: {e}")
