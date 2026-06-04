from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve
from PySide6.QtGui import QColor, QPainter

from ..core import qss_base


class ToastNotification(QWidget):
    """Toast 提示组件"""

    # 颜色方案
    COLORS = {
        "success": QColor(40, 167, 69, 242),  # rgba(40, 167, 69, 0.95)
        "info": QColor(0, 137, 123, 242),      # rgba(0, 137, 123, 0.95) 深青色
        "error": QColor(220, 53, 69, 242),     # rgba(220, 53, 69, 0.95)
    }

    def __init__(self, message: str, icon: str = "✓",
                 toast_type: str = "success", parent=None):
        super().__init__(parent)
        self.message = message
        self.icon = icon
        self.toast_type = toast_type
        self._hovered = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(qss_base.label_qss(font_size="18px", color="white"))
        layout.addWidget(icon_label)

        # 消息
        msg_label = QLabel(message)
        msg_label.setStyleSheet(qss_base.label_qss(font_size="14px", font_weight="500", color="white"))
        layout.addWidget(msg_label)

        self.adjustSize()

    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景色
        color = self.COLORS.get(self.toast_type, self.COLORS["info"])
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)

        # 绘制圆角矩形
        painter.drawRoundedRect(self.rect(), 8, 8)

    def enterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        super().leaveEvent(event)

    def is_hovered(self) -> bool:
        """是否被鼠标悬停"""
        return self._hovered


class ToastManager:
    """Toast 管理器 - 单例模式"""

    # Constants
    TOAST_SPACING = 10      # pixels between stacked toasts
    ENTRANCE_OFFSET = 50    # pixels to slide in from
    MAX_TOASTS = 3         # maximum number of toasts to display

    _instance = None

    def __init__(self):
        self._toasts: list[ToastNotification] = []
        self._parent = None
        self._timers: dict[ToastNotification, QTimer] = {}
        self._animations: dict[ToastNotification, QPropertyAnimation] = {}
        self._opacity_timers: dict[ToastNotification, list[QTimer]] = {}

    @classmethod
    def instance(cls):
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def show(cls, message: str, icon: str = "✓",
             toast_type: str = "success", duration: int = 2000,
             parent=None):
        """显示 Toast 提示"""
        manager = cls.instance()

        # Validate parent is still alive before using it
        actual_parent = None
        if parent:
            try:
                # Check if parent is still valid
                if parent.isVisible():
                    actual_parent = parent
                    manager._parent = parent
            except RuntimeError:
                # Parent already deleted, use None
                actual_parent = None

        # 创建 Toast
        toast = ToastNotification(message, icon, toast_type, actual_parent)
        manager._toasts.append(toast)

        # 限制最多 3 个
        if len(manager._toasts) > cls.MAX_TOASTS:
            oldest = manager._toasts.pop(0)
            manager._hide_toast(oldest, animated=False)

        # 显示 Toast
        manager._show_toast(toast, duration)

    def _show_toast(self, toast: ToastNotification, duration: int):
        """显示 Toast 并设置自动隐藏"""
        # Validate parent before using it
        valid_parent = False
        if self._parent:
            try:
                if self._parent.isVisible():
                    valid_parent = True
            except RuntimeError:
                # Parent already deleted
                self._parent = None
                valid_parent = False

        # Calculate position with stacking
        if valid_parent:
            parent_rect = self._parent.geometry()
            x = parent_rect.x() + (parent_rect.width() - toast.width()) // 2
            # Stack vertically: each toast offset by its height + spacing
            y_offset = (len(self._toasts) - 1) * (toast.height() + self.TOAST_SPACING)
            y = parent_rect.y() + 20 + y_offset
        else:
            # No parent - use screen center
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - toast.width()) // 2
            # Stack vertically
            y_offset = (len(self._toasts) - 1) * (toast.height() + self.TOAST_SPACING)
            y = 20 + y_offset

        # 进场动画：从上方滑入 + 淡入
        start_pos = QPoint(x, y - self.ENTRANCE_OFFSET)
        end_pos = QPoint(x, y)

        toast.move(start_pos)
        toast.setWindowOpacity(0.0)
        toast.show()

        # 位置动画
        anim = QPropertyAnimation(toast, b"pos")
        anim.setDuration(300)
        anim.setStartValue(start_pos)
        anim.setEndValue(end_pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._animations[toast] = anim

        # 透明度动画（通过定时器模拟）
        opacity_steps = 10
        opacity_timer = QTimer()
        step = [0]

        def update_opacity():
            try:
                # Check if toast still exists before accessing it
                if not toast or not toast.isVisible():
                    opacity_timer.stop()
                    return

                step[0] += 1
                toast.setWindowOpacity(step[0] / opacity_steps)
                if step[0] >= opacity_steps:
                    opacity_timer.stop()
            except RuntimeError:
                # Toast already deleted - stop timer
                opacity_timer.stop()

        opacity_timer.timeout.connect(update_opacity)
        opacity_timer.start(30)
        if toast not in self._opacity_timers:
            self._opacity_timers[toast] = []
        self._opacity_timers[toast].append(opacity_timer)

        # 自动隐藏定时器
        timer = QTimer()
        elapsed = [0]

        def check_hide():
            try:
                # Check if toast still exists before accessing it
                if not toast or not toast.isVisible():
                    timer.stop()
                    return

                if toast.is_hovered():
                    return
                elapsed[0] += 100
                if elapsed[0] >= duration:
                    timer.stop()
                    self._hide_toast(toast)
            except RuntimeError:
                # Toast already deleted - stop timer
                timer.stop()

        timer.timeout.connect(check_hide)
        timer.start(100)
        self._timers[toast] = timer

    def _hide_toast(self, toast: ToastNotification, animated: bool = True):
        """隐藏 Toast"""
        # Check if toast is already deleted
        try:
            if not toast:
                # Toast is None, just cleanup
                if toast in self._toasts:
                    self._toasts.remove(toast)
                return
        except RuntimeError:
            # Toast already deleted, just cleanup
            if toast in self._toasts:
                self._toasts.remove(toast)
            return

        if toast in self._timers:
            self._timers[toast].stop()
            del self._timers[toast]

        # Clean up opacity timers
        if toast in self._opacity_timers:
            for timer in self._opacity_timers[toast]:
                timer.stop()
            del self._opacity_timers[toast]

        # Clean up animations
        if toast in self._animations:
            self._animations[toast].stop()
            del self._animations[toast]

        if animated:
            # 淡出动画
            opacity_steps = 10
            opacity_timer = QTimer()
            step = [opacity_steps]

            def update_opacity():
                try:
                    # Check if toast still exists before accessing it
                    if not toast or not toast.isVisible():
                        opacity_timer.stop()
                        if toast in self._toasts:
                            self._toasts.remove(toast)
                        if toast in self._opacity_timers:
                            del self._opacity_timers[toast]
                        return

                    step[0] -= 1
                    toast.setWindowOpacity(step[0] / opacity_steps)
                    if step[0] <= 0:
                        opacity_timer.stop()
                        toast.close()
                        toast.deleteLater()
                        if toast in self._toasts:
                            self._toasts.remove(toast)
                        if toast in self._opacity_timers:
                            del self._opacity_timers[toast]
                except RuntimeError:
                    # Toast already deleted - stop timer and cleanup
                    opacity_timer.stop()
                    if toast in self._toasts:
                        self._toasts.remove(toast)
                    if toast in self._opacity_timers:
                        del self._opacity_timers[toast]

            opacity_timer.timeout.connect(update_opacity)
            opacity_timer.start(20)
            if toast not in self._opacity_timers:
                self._opacity_timers[toast] = []
            self._opacity_timers[toast].append(opacity_timer)
        else:
            try:
                toast.close()
                toast.deleteLater()
            except RuntimeError:
                # Toast already deleted - just cleanup
                pass
            finally:
                if toast in self._toasts:
                    self._toasts.remove(toast)
