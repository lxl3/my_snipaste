"""Settings Card 组件 - 设置页面卡片容器

现代卡片式布局，带图标、标题、玻璃态背景和 hover 效果。
用于设置页面的各个设置组。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

from ..core.theme import theme as _t
from ..core import qss_base


class SettingsCard(QWidget):
    """设置卡片组件

    特点：
    - 8px 圆角
    - 20px 内边距
    - $bg_secondary 背景
    - 图标 + 标题
    - Hover 阴影效果

    用法：
        card = SettingsCard(icon="⌨️", title="全局快捷键")
        card.add_row(label, widget)
        card.add_widget(widget)
    """

    def __init__(self, icon: str = "", title: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # 主布局
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(20, 20, 20, 20)
        self._main_layout.setSpacing(16)

        # 保存 label 引用以便主题切换时更新
        self._icon_label = None
        self._title_label = None

        # 标题行（图标 + 标题）
        if icon or title:
            header = QHBoxLayout()
            header.setSpacing(10)

            if icon:
                self._icon_label = QLabel(icon)
                self._icon_label.setStyleSheet(qss_base.label_qss(
                    font_size="20px",
                    color=_t.get("text_primary")
                ))
                header.addWidget(self._icon_label)

            if title:
                self._title_label = QLabel(title)
                self._title_label.setStyleSheet(qss_base.label_qss(
                    font_size="15px",
                    font_weight="600",
                    color=_t.get("text_primary")
                ))
                header.addWidget(self._title_label)

            header.addStretch()
            self._main_layout.addLayout(header)

        # 内容布局（用户添加控件的地方）
        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(12)
        self._main_layout.addLayout(self._content_layout)

        # 应用样式
        self._apply_style()

        # Hover 阴影效果
        self._shadow_effect = QGraphicsDropShadowEffect(self)
        self._shadow_effect.setBlurRadius(0)
        self._shadow_effect.setXOffset(0)
        self._shadow_effect.setYOffset(2)
        self._shadow_effect.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(self._shadow_effect)

        # 监听主题变化
        _t.theme_changed.connect(self._on_theme_changed)

    def add_widget(self, widget: QWidget):
        """添加一个控件到卡片内容区"""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        """添加一个布局到卡片内容区"""
        self._content_layout.addLayout(layout)

    def add_row(self, label_widget: QWidget, control_widget: QWidget):
        """添加一行（标签 + 控件）到卡片内容区"""
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(label_widget)
        row.addStretch()
        row.addWidget(control_widget)
        self._content_layout.addLayout(row)

    def add_spacing(self, spacing: int):
        """添加垂直间距"""
        self._content_layout.addSpacing(spacing)

    def _apply_style(self):
        """应用卡片样式"""
        style = _t.qss(f"""
            SettingsCard {{
                background: $bg_secondary;
                border: 1px solid $border_light;
                border-radius: 8px;
            }}
        """)
        self.setStyleSheet(style)

    def _on_theme_changed(self, mode: str):
        """主题切换时重新应用样式（简化版，避免与父 widget 重复刷新）"""
        # 重新应用卡片背景样式
        self._apply_style()

        # 更新图标和标题的颜色
        if self._icon_label:
            self._icon_label.setStyleSheet(qss_base.label_qss(
                font_size="20px",
                color=_t.get("text_primary")
            ))
        if self._title_label:
            self._title_label.setStyleSheet(qss_base.label_qss(
                font_size="15px",
                font_weight="600",
                color=_t.get("text_primary")
            ))

        # 注意：不调用 unpolish/polish，因为父 dialog 的 _on_theme_changed
        # 会遍历所有子 widget 并统一刷新，避免重复操作导致延迟

    def enterEvent(self, event):
        """鼠标进入时增强阴影"""
        self._shadow_effect.setBlurRadius(12)
        self._shadow_effect.setColor(QColor(_t.get("shadow", "#0000003C")))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开时移除阴影"""
        self._shadow_effect.setBlurRadius(0)
        self._shadow_effect.setColor(QColor(0, 0, 0, 0))
        super().leaveEvent(event)

    def destroy(self, destroyWindow: bool = True, destroySubWindows: bool = True):
        """清理主题信号连接"""
        try:
            _t.theme_changed.disconnect(self._on_theme_changed)
        except (TypeError, RuntimeError):
            pass
        return super().destroy(destroyWindow, destroySubWindows)
