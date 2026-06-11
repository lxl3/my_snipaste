from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..core import qss_base
from ..core.theme_pkg import draw_glass_morphism
from ..core.theme_pkg import theme as _t


class ToastNotification(QWidget):
    """Toast 提示组件 - 玻璃态设计"""

    # 图标背景颜色方案（用于圆形图标容器）
    ICON_COLORS = {
        "success": ("#28A745", "#20803A"),  # 绿色渐变
        "info": ("#00897B", "#00695C"),     # 深青渐变
        "error": ("#DC3545", "#A82835"),    # 红色渐变
    }

    def __init__(self, message: str, icon: str = "✓",
                 toast_type: str = "success", parent=None):
        super().__init__(parent)
        self.message = message
        self.icon = icon
        self.toast_type = toast_type

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # 左侧弹性空间（让内容居中）
        layout.addStretch()

        # 图标容器（圆形背景）
        self._icon_container = QWidget()
        self._icon_container.setFixedSize(28, 28)
        icon_label = QLabel(icon, self._icon_container)
        icon_label.setStyleSheet(qss_base.label_qss(font_size="16px", color="white"))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setGeometry(0, 0, 28, 28)
        layout.addWidget(self._icon_container)

        # 消息
        msg_label = QLabel(message)
        msg_label.setStyleSheet(qss_base.label_qss(
            font_size="13px",
            font_weight="500",
            color=_t.get("text_primary")
        ))
        layout.addWidget(msg_label)

        # 右侧弹性空间（让内容居中）
        layout.addStretch()

        self.adjustSize()
        self.setMinimumWidth(220)

    def paintEvent(self, event):
        """绘制玻璃态背景（Big Sur 风格）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        is_dark = _t.is_dark()

        # 1. 使用通用 Big Sur 毛玻璃效果绘制主背景
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=10,
            is_dark=is_dark,
            draw_shadow=False,  # Toast 不需要外部投影（已有淡入动画）
        )

        # 2. 绘制图标圆形背景（渐变）- 根据实际图标容器位置
        icon_pos = self._icon_container.pos()
        icon_rect = QRect(icon_pos.x(), icon_pos.y(), 28, 28)

        # info/success 类型使用主题色，其他类型使用预设颜色
        if self.toast_type in ("info", "success"):
            accent = _t.accent_color
            # 生成渐变色：顶部为主题色，底部稍暗
            color_top = accent
            c = QColor(accent)
            h, s, lightness, a = c.getHslF()
            darker = QColor.fromHslF(h, s, max(lightness - 0.08, 0.1), a)
            color_bottom = darker.name()
        else:
            color_top, color_bottom = self.ICON_COLORS.get(self.toast_type, self.ICON_COLORS["success"])

        icon_gradient = QLinearGradient(icon_rect.topLeft(), icon_rect.bottomLeft())
        icon_gradient.setColorAt(0, QColor(color_top))
        icon_gradient.setColorAt(1, QColor(color_bottom))
        painter.setBrush(icon_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(icon_rect)


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

        # 进场动画：缩放 + 淡入 + 轻微上移（玻璃态优雅动画）
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        # 最终位置（稍微下移一点作为起始位置）
        start_y = y + 20
        end_pos = QPoint(x, y)

        toast.move(x, start_y)

        # 使用 QGraphicsOpacityEffect 处理透明度
        opacity_effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(0.0)
        toast.show()

        # 位置动画（轻微上移）
        pos_anim = QPropertyAnimation(toast, b"pos")
        pos_anim.setDuration(400)
        pos_anim.setStartValue(QPoint(x, start_y))
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.OutCubic)
        pos_anim.start()

        # 透明度动画（淡入）
        opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
        opacity_anim.setDuration(350)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.OutQuad)
        opacity_anim.start()

        # 缩放动画（通过调整几何尺寸模拟）
        original_size = toast.size()
        scale_start = QSize(int(original_size.width() * 0.92), int(original_size.height() * 0.92))

        # 先缩小再恢复正常大小
        toast.resize(scale_start)
        geometry_anim = QPropertyAnimation(toast, b"size")
        geometry_anim.setDuration(400)
        geometry_anim.setStartValue(scale_start)
        geometry_anim.setEndValue(original_size)
        geometry_anim.setEasingCurve(QEasingCurve.OutBack)
        geometry_anim.start()

        # 保存动画引用
        self._animations[toast] = (pos_anim, opacity_anim, geometry_anim)

        # 自动隐藏定时器（简化逻辑，不检查hover）
        timer = QTimer()
        timer.setSingleShot(True)  # 只触发一次
        timer.timeout.connect(lambda: self._hide_toast(toast))
        timer.start(duration)
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
            anims = self._animations[toast]
            # anims 是元组 (pos_anim, opacity_anim, geometry_anim)
            if isinstance(anims, tuple):
                for anim in anims:
                    if anim:
                        anim.stop()
            else:
                anims.stop()
            del self._animations[toast]

        if animated:
            # 淡出动画（使用 QGraphicsOpacityEffect）
            try:
                opacity_effect = toast.graphicsEffect()
                if opacity_effect:
                    fade_out = QPropertyAnimation(opacity_effect, b"opacity")
                    fade_out.setDuration(200)
                    fade_out.setStartValue(1.0)
                    fade_out.setEndValue(0.0)
                    fade_out.setEasingCurve(QEasingCurve.InQuad)

                    def on_finished():
                        try:
                            if toast in self._toasts:
                                self._toasts.remove(toast)
                            toast.close()
                            toast.deleteLater()
                        except (RuntimeError, AttributeError):
                            pass

                    fade_out.finished.connect(on_finished)
                    fade_out.start()

                    # 保存动画引用防止被垃圾回收
                    self._animations[toast] = fade_out
                else:
                    # Fallback：没有opacity effect，直接关闭
                    if toast in self._toasts:
                        self._toasts.remove(toast)
                    toast.close()
                    toast.deleteLater()
            except (RuntimeError, AttributeError):
                if toast in self._toasts:
                    self._toasts.remove(toast)
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
