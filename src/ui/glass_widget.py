"""玻璃态 Widget 组件 - Big Sur 风格

提供开箱即用的毛玻璃效果 QWidget/QFrame/QMenu，用于：
- 工具栏
- 悬浮面板
- 自定义弹窗
- 右键菜单
等需要玻璃态背景的场景。
"""

from PySide6.QtWidgets import QFrame, QMenu
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QRectF, QRect

from ..core.glass_effect import draw_glass_morphism
from ..core.theme import theme as _t


class GlassFrame(QFrame):
    """玻璃态 QFrame - Big Sur 风格

    自动绘制毛玻璃背景，无需手动实现 paintEvent。

    用法：
        toolbar = GlassFrame(parent)
        toolbar.setGlassRadius(6)
        toolbar.setGlassShadow(False)
        # 然后正常添加子控件和布局

    特点：
    - 自动跟随主题切换（亮色/暗色模式）
    - 可自定义圆角、投影强度
    - 半透明背景，需要父 widget 设置 WA_TranslucentBackground
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)  # 禁用默认背景，使用自定义绘制

        # 玻璃效果参数
        self._glass_radius = 8
        self._glass_shadow = False
        self._glass_shadow_intensity = 1.0
        self._glass_bg_opacity = None  # None = 使用默认值

        # 监听主题变化
        _t.theme_changed.connect(self._on_theme_changed)

    def setGlassRadius(self, radius: float):
        """设置圆角半径"""
        self._glass_radius = radius
        self.update()

    def setGlassShadow(self, enabled: bool):
        """设置是否绘制外部投影"""
        self._glass_shadow = enabled
        self.update()

    def setGlassShadowIntensity(self, intensity: float):
        """设置投影强度 (0.0-2.0)"""
        self._glass_shadow_intensity = intensity
        self.update()

    def setGlassOpacity(self, top: int, mid: int, bottom: int):
        """设置背景透明度 (0-255)

        Args:
            top: 顶部透明度
            mid: 中部透明度
            bottom: 底部透明度
        """
        self._glass_bg_opacity = (top, mid, bottom)
        self.update()

    def paintEvent(self, event):
        """绘制 Big Sur 毛玻璃背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        is_dark = _t.is_dark()

        # 绘制毛玻璃效果
        draw_glass_morphism(
            painter,
            QRectF(rect),
            radius=self._glass_radius,
            is_dark=is_dark,
            draw_shadow=self._glass_shadow,
            bg_opacity=self._glass_bg_opacity,
            shadow_intensity=self._glass_shadow_intensity,
        )

        # 调用父类 paintEvent 以绘制子控件
        super().paintEvent(event)

    def _on_theme_changed(self, _mode: str):
        """主题切换时重绘"""
        self.update()

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        """清理信号连接"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)


class GlassMenu(QMenu):
    """玻璃态 QMenu - Big Sur 风格

    右键菜单/下拉菜单的毛玻璃效果版本。

    用法：
        menu = GlassMenu(parent)
        # 或
        menu = GlassMenu("菜单标题", parent)
        menu.addAction("选项 1")
        menu.addAction("选项 2")
        menu.exec(position)

    特点：
    - 自动跟随主题切换
    - Big Sur 风格毛玻璃背景
    - 柔和投影效果
    - 自动处理半透明背景
    """

    def __init__(self, *args, **kwargs):
        """支持 QMenu 的两种构造方式：
        - GlassMenu(parent=None)
        - GlassMenu(title: str, parent=None)
        """
        super().__init__(*args, **kwargs)

        # 强制使用自定义样式（不使用系统原生菜单）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )

        # 设置菜单项样式（使用 QSS 实现玻璃效果）
        self._apply_menu_style()

        # 菜单显示前强制刷新样式（解决系统托盘覆盖问题）
        self.aboutToShow.connect(self._on_about_to_show)

        # 监听主题变化
        _t.theme_changed.connect(self._on_theme_changed)

    def _on_about_to_show(self):
        """菜单显示前强制刷新样式"""
        self._apply_menu_style()
        self.update()

    def _apply_menu_style(self):
        """应用菜单项样式（根据主题调整文字颜色）"""
        from ..core import qss_base
        is_dark = _t.is_dark()

        # 根据主题调整颜色（玻璃质感 + 清晰可读）
        if is_dark:
            # 暗色模式：深色半透明背景 + 浅色文字
            bg_top = "rgba(50, 50, 50, 200)"
            bg_bottom = "rgba(40, 40, 40, 180)"
            text_color = "rgba(240, 240, 240, 255)"
            separator_color = "rgba(255, 255, 255, 0.1)"
            border_top = "rgba(255, 255, 255, 100)"
            border_main = "rgba(255, 255, 255, 80)"
        else:
            # 亮色模式：白色半透明背景 + 深色文字
            bg_top = "rgba(255, 255, 255, 220)"
            bg_bottom = "rgba(245, 245, 245, 200)"
            text_color = "rgba(40, 40, 40, 255)"
            separator_color = "rgba(0, 0, 0, 0.1)"
            border_top = "rgba(255, 255, 255, 180)"
            border_main = "rgba(200, 200, 200, 120)"

        # 使用 QSS 渐变实现玻璃效果（更可靠）
        style = _t.qss(f"""
            QMenu {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {bg_top}, stop:1 {bg_bottom});
                border: 1px solid {border_main};
                border-top: 2px solid {border_top};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 12px 8px 8px;
                color: {text_color};
                border-radius: 4px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background: $accent;
                color: $text_accent;
            }}
            QMenu::separator {{
                height: 1px;
                background: {separator_color};
                margin: 6px 10px;
            }}
            QMenu::icon {{
                padding-left: 6px;
            }}
        """)
        self.setStyleSheet(style)

    def paintEvent(self, event):
        """QSS 已处理背景，直接调用父类绘制菜单项"""
        super().paintEvent(event)

    def _on_theme_changed(self, _mode: str):
        """主题切换时重绘"""
        self._apply_menu_style()
        self.update()

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        """清理信号连接"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)
