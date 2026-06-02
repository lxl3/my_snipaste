import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

from .hotkeys import get_default_hotkey

_SETTINGS_DIR: str = ""
_SETTINGS_PATH: str = ""
_loaded: "AppSettings | None" = None


def _get_settings_dir() -> str:
    global _SETTINGS_DIR
    if not _SETTINGS_DIR:
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        elif sys.platform == "win32":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.expanduser("~/.config")
        _SETTINGS_DIR = os.path.join(base, "MySnipaste")
    return _SETTINGS_DIR


def _get_settings_path() -> str:
    global _SETTINGS_PATH
    if not _SETTINGS_PATH:
        _SETTINGS_PATH = os.path.join(_get_settings_dir(), "settings.json")
    return _SETTINGS_PATH


@dataclass
class AppSettings:
    hotkey: str = field(default_factory=get_default_hotkey)
    ocr_language: str = "eng+chi_sim"
    default_color: str = "#ff3232"
    default_line_width: int = 3
    default_font_family: str = "Segoe UI"
    default_font_size: int = 20
    auto_save_dir: str = ""
    auto_save_format: str = "png"
    launch_at_startup: bool = False
    log_level: str = "DEBUG"
    save_window_position: bool = True
    pin_window_opacity: int = 100
    language: str = "zh_CN"

    # Capture behavior settings
    capture_sound: bool = False
    capture_delay: int = 0  # seconds, 0-10
    capture_cursor: bool = False
    capture_after_action: str = "none"  # none, copy, save

    # UX 优化配置
    # 颜色记忆
    recent_colors: list[str] = field(default_factory=list)
    max_recent_colors: int = 5

    # 工具设置记忆
    last_tool: str = "select"
    tool_settings: dict[str, dict] = field(default_factory=dict)

    # Toast 提示
    enable_toast: bool = True
    toast_duration: int = 2000

    # 快捷键帮助
    show_hotkey_tip: bool = True

    # ─── 全局快捷键扩展 (5.1) ───
    hotkey_ocr: str = "ctrl+shift+t"  # OCR 剪贴板
    hotkey_delay: str = "ctrl+shift+d"  # 延迟截图
    hotkey_pin: str = "ctrl+shift+p"  # 固定窗口截图
    hotkey_full: str = "ctrl+shift+f"  # 全屏截图
    hotkey_color_picker: str = "ctrl+shift+c"  # 屏幕取色

    # ─── 编辑器内工具快捷键 (5.2) ───
    shortcut_rect: str = "r"
    shortcut_ellipse: str = "e"
    shortcut_arrow: str = "a"
    shortcut_line: str = "l"
    shortcut_pen: str = "p"
    shortcut_text: str = "t"
    shortcut_highlighter: str = "h"
    shortcut_blur: str = "b"
    shortcut_number_marker: str = "n"
    shortcut_select: str = "v"
    shortcut_grid: str = "g"

    # 主题设置
    theme: str = "light"  # "light", "dark", "system"

    # Pin 窗口设置
    pin_window_geometry: str = ""  # Stores "x,y,width,height" as string

    def save(self) -> None:
        path = _get_settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save settings: {e}", file=sys.stderr)

    def add_recent_color(self, color: str) -> None:
        """添加颜色到最近使用列表"""
        # 去重：如果已存在则移除
        if color in self.recent_colors:
            self.recent_colors.remove(color)

        # 插入到开头
        self.recent_colors.insert(0, color)

        # 限制最多 5 个
        if len(self.recent_colors) > self.max_recent_colors:
            self.recent_colors = self.recent_colors[:self.max_recent_colors]

        self.save()

    def get_tool_settings(self, tool: str) -> dict:
        """获取工具设置"""
        return self.tool_settings.get(tool, {})

    def save_tool_settings(self, tool: str, settings: dict) -> None:
        """保存工具设置"""
        self.tool_settings[tool] = settings
        self.save()

    @staticmethod
    def load() -> "AppSettings":
        global _loaded
        if _loaded is not None:
            return _loaded
        path = _get_settings_path()
        if not os.path.exists(path):
            _loaded = AppSettings()
            return _loaded
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            valid_keys = {f.name for f in AppSettings.__dataclass_fields__.values() if f.init}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            _loaded = AppSettings(**filtered)
        except Exception as e:
            print(f"Failed to load settings: {e}", file=sys.stderr)
            _loaded = AppSettings()
        return _loaded

    @staticmethod
    def reload() -> "AppSettings":
        global _loaded
        _loaded = None
        return AppSettings.load()


def get_settings() -> AppSettings:
    return AppSettings.load()
