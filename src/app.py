import os
import platform
import subprocess
from threading import Thread

from PySide6.QtCore import QObject, Signal, Slot, Qt, QPoint, QTimer
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QPen, QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget, QFileDialog,
)
from .overlay import CaptureOverlay
from .ocr_engine import extract_text
from .utils import create_app_icon
from .logger import setup_logger

logger = setup_logger("app")


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

    # macOS 15+ 即使权限通过，全局热键对未签名进程也不生效
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

    # 尝试自动打开系统设置
    try:
        subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
    except Exception:
        pass

    return trusted and has_input and not is_sequoia


class PinWindow(QWidget):
    def __init__(self, pixmap: QPixmap, pos):
        super().__init__()
        self.pixmap = pixmap
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        dpr = pixmap.devicePixelRatio()
        w = int(pixmap.width() / dpr)
        h = int(pixmap.height() / dpr)
        self.resize(w, h)
        self.move(pos)

        self.setMouseTracking(True)
        self._dragging = False
        self._drag_pos = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap, self.pixmap.rect())

        pen = QPen(QColor(200, 200, 200, 100), 1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, event):
        self.close()

    def closeEvent(self, event):
        self.deleteLater()
        super().closeEvent(event)


class HotkeyListener(QObject):
    capture_signal = Signal()

    def __init__(self):
        super().__init__()
        self.listener = None
        self.running = False

    def start(self):
        self.running = True
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _listen(self):
        try:
            from pynput import keyboard

            def on_press(key):
                if not self.running:
                    return False
                try:
                    if key == keyboard.Key.f12:
                        self.capture_signal.emit()
                except Exception:
                    pass

            with keyboard.Listener(on_press=on_press) as self.listener:
                self.listener.join()
        except ImportError:
            logger.warning("pynput 未安装，全局快捷键不可用")
        except OSError as e:
            logger.error(f"快捷键监听失败（权限不足）: {e}")
        except Exception as e:
            logger.error(f"快捷键监听异常: {e}")

    def __del__(self):
        self.stop()


class SnipasteApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("MySnipaste")
        self.setOrganizationName("MySnipaste")
        self.setQuitOnLastWindowClosed(False)

        app_icon = create_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.overlay = None
        self.pin_windows = []

        self.setup_focused_hotkey()

        have_hotkey = check_macos_accessibility()
        self.setup_tray(have_hotkey)
        if have_hotkey:
            self.setup_hotkeys()
        else:
            logger.warning("辅助功能权限未授权，全局快捷键不可用")
        logger.info("MySnipaste 应用初始化完成")

        if have_hotkey:
            QTimer.singleShot(500, self._show_startup_notification)
        else:
            QTimer.singleShot(500, self._show_no_hotkey_notification)

    def setup_focused_hotkey(self):
        self.f12_shortcut = QShortcut(QKeySequence("F12"), self)
        self.f12_shortcut.activated.connect(self.start_capture)

    def setup_tray(self, have_hotkey=True):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon)
        if have_hotkey:
            self.tray_icon.setToolTip("MySnipaste - 按 F12 截屏")
        else:
            self.tray_icon.setToolTip("MySnipaste - 点击托盘图标截屏")

        ocr_action = QAction("OCR 剪贴板图片", self)
        ocr_action.triggered.connect(self.ocr_clipboard)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)

        if platform.system() == "Darwin":
            self.tray_icon.activated.connect(lambda r: self.start_capture())
            from PySide6.QtWidgets import QMenuBar
            self._menubar = QMenuBar()
            app_menu = self._menubar.addMenu("MySnipaste")
            app_menu.addAction(ocr_action)
            app_menu.addSeparator()
            app_menu.addAction(quit_action)
            logger.info("macOS 托盘已配置（单击触发截图 + 系统菜单栏）")
        else:
            menu = QMenu()
            capture_action = QAction("截屏 (F12)", self)
            capture_action.triggered.connect(self.start_capture)
            menu.addAction(capture_action)
            menu.addAction(ocr_action)
            menu.addSeparator()
            menu.addAction(quit_action)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(self._on_tray_activated)
            logger.info("Windows 托盘已配置（双击触发截图）")

        self.tray_icon.show()
        logger.info("系统托盘图标已显示")

    def _show_startup_notification(self):
        """显示启动通知"""
        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText("✨ MySnipaste 已启动")
        msg.setInformativeText("按 F12 开始截图\n点击托盘图标也可启动")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(3000, msg.close)
        msg.exec()
        logger.info("启动提示框已关闭")

    def _show_no_hotkey_notification(self):
        msg = QMessageBox()
        msg.setWindowTitle("MySnipaste")
        msg.setText("MySnipaste 已启动，但全局快捷键不可用")
        msg.setInformativeText(
            "macOS 限制了全局 F12 热键，即使授权也可能无效。\n\n"
            "解决方案：\n"
            "• 点击托盘图标截图\n"
            "• 将应用切换到前台后按 F12\n"
            "• 将应用打包为 .app 并签名以获得完整 F12 支持\n\n"
            "详见之前的权限设置引导。"
        )
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        QTimer.singleShot(5000, msg.close)
        msg.exec()
        logger.info("无快捷键启动提示已关闭")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.start_capture()

    def setup_hotkeys(self):
        self.hotkey_listener = HotkeyListener()
        self.hotkey_listener.capture_signal.connect(self.start_capture)
        self.hotkey_listener.start()

    def start_capture(self):
        if self.overlay is not None:
            logger.debug("截图覆盖层已存在，跳过")
            return

        logger.info("启动截图")
        self.overlay = CaptureOverlay()
        self.overlay.pin_requested.connect(self._on_pin)
        self.overlay.copy_requested.connect(self._on_copy)
        self.overlay.save_requested.connect(self._on_save)
        self.overlay.destroyed.connect(lambda: setattr(self, 'overlay', None))
        self.overlay.show()

    def _on_pin(self, pixmap: QPixmap, pos):
        win = PinWindow(pixmap, pos)
        win.destroyed.connect(lambda: self.pin_windows.remove(win) if win in self.pin_windows else None)
        self.pin_windows.append(win)
        win.show()

    def _on_copy(self, pixmap: QPixmap):
        self.clipboard().setPixmap(pixmap)

    def _on_save(self, pixmap: QPixmap):
        file_path, _ = QFileDialog.getSaveFileName(
            None, "保存截图", "截图.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*)",
        )
        if file_path:
            pixmap.save(file_path)
            if self.overlay:
                self.overlay.close()

    def ocr_clipboard(self):
        logger.info("开始 OCR 剪贴板图片")
        clipboard = self.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap is None or pixmap.isNull():
            logger.warning("剪贴板中没有图片")
            QMessageBox.information(
                None, "OCR 剪贴板",
                "剪贴板中没有图片。\n请先复制一张图片，然后再试。"
            )
            return

        text = extract_text(pixmap)
        if text:
            clipboard.setText(text)
            logger.info(f"OCR 识别成功，{len(text)} 个字符已复制到剪贴板")
            QMessageBox.information(
                None, "OCR 结果",
                f"文本已提取并复制到剪贴板：\n\n{text[:500]}"
            )
        else:
            logger.warning("OCR 识别结果为空")

    def cleanup(self):
        """清理资源，防止退出后托盘图标残留"""
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setToolTip("")
            self.tray_icon.setIcon(QIcon())
            self.tray_icon.setContextMenu(None)
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            del self.tray_icon

    def quit(self):
        logger.info("用户请求退出应用")
        self.cleanup()
        QTimer.singleShot(300, super().quit)

    def __del__(self):
        self.cleanup()
