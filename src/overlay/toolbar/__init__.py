"""工具栏模块

提供声明式配置和构建器模式的工具栏实现。

使用方式:
    from .toolbar import OverlayToolbar  # 现有实现（兼容导入）
    from .toolbar.config import TOOLBAR_CONFIG  # 声明式配置
    from .toolbar.builder import ToolbarBuilder  # 构建器
"""

from .legacy import OverlayToolbar
from .config import TOOLBAR_CONFIG, ACTION_BUTTONS_CONFIG
from .builder import ToolbarBuilder

__all__ = ["OverlayToolbar", "TOOLBAR_CONFIG", "ACTION_BUTTONS_CONFIG", "ToolbarBuilder"]
