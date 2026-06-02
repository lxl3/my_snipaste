"""Window/element auto-detection under the cursor.

On Windows, uses Win32 ctypes to find the window handle under the cursor
and compute its rectangle. On other platforms, silently returns None
(no auto-detect).
"""

import platform
from PySide6.QtCore import QPoint, QRect
from ..core.logger import setup_logger

logger = setup_logger("window_detector")


def detect_window_under_cursor(cursor_pos: QPoint) -> QRect | None:
    """Return the screen rect of the window under *cursor_pos*, or None.

    Skips the desktop background (Progman / WorkerW) and the taskbar
    (Shell_TrayWnd).  Returns the window rectangle in logical (screen)
    coordinates.
    """
    if platform.system() != "Windows":
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    try:
        # ── Win32 type defs ──
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        # ── Get window under cursor ──
        hwnd = user32.WindowFromPoint(wintypes.POINT(cursor_pos.x(), cursor_pos.y()))
        if not hwnd:
            return None

        # ── Buffer for class name ──
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        cn = class_name.value

        # Skip desktop and taskbar
        if cn in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return None

        # ── Get extended frame bounds (handles DWM shadows) ──
        # Use DwmGetWindowAttribute for accurate bounds including shadow
        rect = wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9

        result = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
        if result != 0:  # S_OK
            # Fallback to GetWindowRect
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

        return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception as e:
        logger.debug(f"Window detection failed: {e}")
        return None
