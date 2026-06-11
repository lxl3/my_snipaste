"""Toggle Switch 组件 - 现代开关控件

基于 QCheckBox 自定义绘制，带平滑滑动动画。
用于设置页面代替传统的 CheckBox。
"""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from ...core.theme_pkg import theme as _t


class ToggleSwitch(QCheckBox):
    """现代 Toggle Switch 组件

    尺寸：48x28px
    滑块：24px 直径圆形
    开启状态：深青色背景
    关闭状态：灰色背景
    动画：200ms 平滑滑动

    用法：
        toggle = ToggleSwitch()
        toggle.setChecked(True)
        toggle.toggled.connect(lambda checked: print(checked))
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.PointingHandCursor)

        # 滑块位置动画（0.0 = 左侧，1.0 = 右侧）
        self._slider_position = 0.0
        self._animation = QPropertyAnimation(self, b"slider_position", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

        # 监听选中状态变化
        self.toggled.connect(self._on_toggled)

        # 监听主题变化
        _t.theme_changed.connect(self._on_theme_changed)

    def _on_toggled(self, checked: bool):
        """选中状态变化时触发动画"""
        self._animation.stop()
        self._animation.setStartValue(self._slider_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def _on_theme_changed(self, mode: str):
        """主题切换时重绘"""
        self.update()

    @Property(float)
    def slider_position(self):
        return self._slider_position

    @slider_position.setter
    def slider_position(self, pos: float):
        self._slider_position = pos
        self.update()

    def paintEvent(self, event):
        """自定义绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 尺寸
        width = self.width()
        height = self.height()
        track_radius = height // 2
        slider_diameter = 24
        # 背景轨道颜色（根据状态和动画位置混合）
        if self.isEnabled():
            if self.isChecked():
                # 开启状态：深青色
                bg_color = QColor(_t.get("accent", "#00897B"))
            else:
                # 关闭状态：灰色
                is_dark = _t.is_dark()
                bg_color = QColor("#999999" if not is_dark else "#555555")

            # 根据动画位置混合颜色（提供渐变过渡效果）
            if 0 < self._slider_position < 1:
                if self.isChecked():
                    # 正在开启：从灰到青
                    gray = QColor("#999999" if not _t.is_dark() else "#555555")
                    accent = QColor(_t.get("accent", "#00897B"))
                    bg_color = self._blend_colors(gray, accent, self._slider_position)
                else:
                    # 正在关闭：从青到灰
                    gray = QColor("#999999" if not _t.is_dark() else "#555555")
                    accent = QColor(_t.get("accent", "#00897B"))
                    bg_color = self._blend_colors(accent, gray, 1.0 - self._slider_position)
        else:
            # 禁用状态
            bg_color = QColor(_t.get("accent_disabled", "#AAAAAA"))

        # 绘制背景轨道
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(0, 0, width, height, track_radius, track_radius)

        # 计算滑块位置（左侧留 2px，右侧留 2px）
        slider_x_min = 2
        slider_x_max = width - slider_diameter - 2
        slider_x = slider_x_min + (slider_x_max - slider_x_min) * self._slider_position
        slider_y = (height - slider_diameter) // 2

        # 绘制滑块阴影（底部暗影）
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(shadow_color)
        painter.drawEllipse(int(slider_x + 1), int(slider_y + 2), slider_diameter, slider_diameter)

        # 绘制滑块
        slider_color = QColor("#FFFFFF")
        painter.setBrush(slider_color)
        painter.setPen(QPen(QColor(0, 0, 0, 20), 1))
        painter.drawEllipse(int(slider_x), int(slider_y), slider_diameter, slider_diameter)

    def _blend_colors(self, color1: QColor, color2: QColor, ratio: float) -> QColor:
        """混合两个颜色（ratio: 0.0=color1, 1.0=color2）"""
        r = int(color1.red() + (color2.red() - color1.red()) * ratio)
        g = int(color1.green() + (color2.green() - color1.green()) * ratio)
        b = int(color1.blue() + (color2.blue() - color1.blue()) * ratio)
        a = int(color1.alpha() + (color2.alpha() - color1.alpha()) * ratio)
        return QColor(r, g, b, a)

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        """清理主题信号连接"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)


class ToggleRow(QWidget):
    """整行可点击的开关组件

    包含标签和开关，点击行内任意位置都能切换状态。
    Hover 时显示背景高亮，提示用户整行可点击。

    用法：
        row = ToggleRow("启用自动保存")
        row.toggled.connect(lambda checked: print(checked))
        row.setChecked(True)
    """

    toggled = Signal(bool)

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._label = QLabel(text)
        color = _t.get("text_primary")
        self._label.setStyleSheet(f"color: {color};")
        self._toggle = ToggleSwitch()

        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._toggle)

        self._toggle.toggled.connect(self.toggled.emit)
        _t.theme_changed.connect(self._on_theme_changed)
        self._apply_style()

    def _apply_style(self, hover: bool = False):
        if hover:
            bg = _t.get("bg_hover", "#E5E5E5" if not _t.is_dark() else "#3A3A3A")
        else:
            bg = "transparent"
        self.setStyleSheet(f"ToggleRow {{ background: {bg}; border-radius: 6px; }}")

    def _on_theme_changed(self, mode: str):
        # 强制刷新标签颜色
        color = _t.get("text_primary")
        self._label.setStyleSheet(f"color: {color};")
        self._apply_style()

    def enterEvent(self, event):
        self._apply_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(hover=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle.setChecked(not self._toggle.isChecked())
        super().mousePressEvent(event)

    def isChecked(self) -> bool:
        return self._toggle.isChecked()

    def setChecked(self, checked: bool):
        self._toggle.setChecked(checked)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._toggle.setEnabled(enabled)
        self._label.setEnabled(enabled)

    def label(self) -> QLabel:
        return self._label

    def toggle(self) -> ToggleSwitch:
        return self._toggle

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)
