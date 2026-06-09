"""Settings dialog tabs.

每个 Tab 负责：
1. 构建自己的 UI (_build_ui)
2. 从 AppSettings 加载设置 (load_settings)
3. 将 UI 值保存到 AppSettings (save_settings)
4. 重置为默认值 (reset_to_defaults)
"""

from .base_tab import BaseTab
from .general_tab import GeneralTab
from .capture_tab import CaptureTab
from .ocr_tab import OcrTab
from .annotation_tab import AnnotationTab
from .advanced_tab import AdvancedTab
from .hotkeys_tab import HotkeysTab

__all__ = [
    "BaseTab",
    "GeneralTab",
    "CaptureTab",
    "OcrTab",
    "AnnotationTab",
    "AdvancedTab",
    "HotkeysTab",
]
