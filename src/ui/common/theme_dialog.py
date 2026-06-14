"""主题感知对话框基类 — 封装标准 6 步主题刷新流程。

用法:
    class MyDialog(ThemeAwareDialog):
        def _build_stylesheet_qss(self) -> None:
            # 构建并应用对话框的 QSS
            self.setStyleSheet(_t.qss("..."))

        def _on_before_theme_apply(self) -> None:
            # [可选] 为特殊子控件单独设置 QPalette
            _t.apply_to_widget(self._special_widget)
"""

from PySide6.QtWidgets import QDialog, QScrollArea, QWidget

from ...core.logger import setup_logger
from ...core.theme_pkg import theme as _t

logger = setup_logger("theme_dialog")


class ThemeAwareDialog(QDialog):
    """带主题感知的对话框基类，封装标准 6 步主题刷新流程。

    子类职责:
        1. 重写 _build_stylesheet_qss() — 构建并应用对话框专属 QSS
        2. 可选重写 _on_before_theme_apply() — 为特殊子控件补充 QPalette
        3. 使用 _add_themed_widget() 注册需要动态刷新的子 widget
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._themed_widgets: list[tuple[QWidget, str]] = []
        _t.theme_changed.connect(self._on_theme_changed)

    # ─── 子类接口 ────────────────────────────────────────

    def _build_stylesheet_qss(self) -> None:
        """子类重写：构建并应用对话框专属 QSS。

        典型实现:
            def _build_stylesheet_qss(self) -> None:
                self.setStyleSheet(_t.qss("..."))
        """

    def _on_before_theme_apply(self) -> None:
        """子类可选重写：在主题应用前补充调色板设置。

        如 QTabBar 等内建子控件需要单独 apply_to_widget。
        """

    # ─── 主题注册 ────────────────────────────────────────

    def _add_themed_widget(self, widget: QWidget, style_template: str) -> None:
        """注册需要动态更新主题样式的 widget。"""
        self._themed_widgets.append((widget, style_template))
        widget.setStyleSheet(_t.qss(style_template))

    # ─── 主题刷新 ────────────────────────────────────────

    def _on_theme_changed(self, mode: str) -> None:
        """主题切换时刷新整个对话框的样式。"""
        logger.info(f"🎨 主题切换: {mode}，正在刷新 {type(self).__name__}...")

        # 步骤 0：设置 QPalette（比 QSS 更底层，更可靠）
        _t.apply_to_widget(self)
        self._on_before_theme_apply()

        # 步骤 1：直接构建并应用新样式表（不先清空，避免白色闪烁）
        # 后续的 unpolish/polish 已足够强制 Qt 清除缓存样式
        self._build_stylesheet_qss()

        # 步骤 3：更新所有保存的动态样式 widget
        for widget, style_template in self._themed_widgets:
            widget.setStyleSheet(_t.qss(style_template))

        # 步骤 4：强制 Qt 重新计算所有 widget 样式（包括子 widget）
        all_widgets = [self] + self.findChildren(QWidget)
        for w in all_widgets:
            w.style().unpolish(w)
            w.style().polish(w)

        # 步骤 5：单独修复 QScrollArea viewport 背景（QSS 级联对 viewport 不可靠）
        for sa in self.findChildren(QScrollArea):
            vp = sa.viewport()
            vp.setStyleSheet(_t.qss("background: $bg_primary;"))
            vp.style().unpolish(vp)
            vp.style().polish(vp)

        # 步骤 6：强制重绘整个对话框（确保背景色立即生效）
        self.update()
        self.repaint()

        logger.debug(f"✓ {type(self).__name__} 主题刷新完成")

    # ─── 清理 ────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """断开主题信号，防止悬浮引用。"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)
