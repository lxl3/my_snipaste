import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

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
    hotkey: str = "cmd+shift+x"
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

    def save(self) -> None:
        path = _get_settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save settings: {e}", file=sys.stderr)

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
