"""主题系统包

整合主题管理器、QSS 生成器和视觉效果。

使用方式:
    from src.core.theme_pkg import theme, qss_base, GlassEffect

当前结构（渐进式迁移）:
    - theme: 从 core.theme 重新导出
    - qss_base: 从 core.qss_base 重新导出
    - GlassEffect: 从 core.glass_effect 重新导出

目标结构:
    theme_pkg/
    ├── __init__.py     # 统一导出
    ├── manager.py      # ThemeManager
    ├── tokens.py       # 设计令牌
    ├── qss.py          # QSS 生成器
    └── effects.py      # 视觉效果
"""

from ..theme import (
    theme,
    ThemeManager,
    LIGHT_TOKENS,
    DARK_TOKENS,
)
from ..qss_base import (
    groupbox_qss,
    lineedit_qss,
    spinbox_qss,
    pushbutton_qss,
    checkbox_qss,
    combobox_qss,
    label_qss,
    slider_qss,
)
from ..glass_effect import draw_glass_morphism

__all__ = [
    # Theme manager
    "theme",
    "ThemeManager",
    "LIGHT_TOKENS",
    "DARK_TOKENS",
    # QSS generators
    "groupbox_qss",
    "lineedit_qss",
    "spinbox_qss",
    "pushbutton_qss",
    "checkbox_qss",
    "combobox_qss",
    "label_qss",
    "slider_qss",
    # Effects
    "draw_glass_morphism",
]
