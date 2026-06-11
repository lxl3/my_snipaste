"""主题系统包

整合主题管理器、QSS 生成器和视觉效果。

使用方式:
    from src.core.theme_pkg import theme, ThemeManager
    from src.core.theme_pkg import pushbutton_qss, draw_glass_morphism

目标结构:
    theme_pkg/
    ├── __init__.py     # 统一导出
    ├── manager.py      # ThemeManager
    ├── tokens.py       # 设计令牌
    ├── qss.py          # QSS 生成器
    └── effects.py      # 视觉效果
"""

from ..theme import (  # noqa: I001 — must be first to avoid circular import with qss_base
    theme,
    ThemeManager,
    get,
    qss,
    LIGHT_TOKENS,
    DARK_TOKENS,
    ThemeMode,
    apply_dark_title_bar,
)
from ..qss_base import (
    pushbutton_qss,
    lineedit_qss,
    combobox_qss,
    spinbox_qss,
    checkbox_qss,
    groupbox_qss,
    slider_qss,
    scrollbar_qss,
    menu_qss,
    label_qss,
)
from ..glass_effect import (
    draw_glass_morphism,
    draw_glass_text,
)

__all__ = [
    # Theme manager
    "theme",
    "ThemeManager",
    "get",
    "qss",
    "LIGHT_TOKENS",
    "DARK_TOKENS",
    "ThemeMode",
    "apply_dark_title_bar",
    # QSS generators
    "pushbutton_qss",
    "lineedit_qss",
    "combobox_qss",
    "spinbox_qss",
    "checkbox_qss",
    "groupbox_qss",
    "slider_qss",
    "scrollbar_qss",
    "menu_qss",
    "label_qss",
    # Effects
    "draw_glass_morphism",
    "draw_glass_text",
]
