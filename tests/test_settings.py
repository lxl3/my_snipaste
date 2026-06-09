import json
import os

from src.core.hotkeys import get_default_hotkey
from src.core.settings import AppSettings, get_settings


class TestAppSettingsDefaults:
    def test_default_hotkey(self):
        s = AppSettings()
        assert s.hotkey == get_default_hotkey()

    def test_default_ocr_language(self):
        s = AppSettings()
        assert s.ocr_language == "eng+chi_sim"

    def test_default_color(self):
        s = AppSettings()
        assert s.default_color == "#ff3232"

    def test_default_line_width(self):
        s = AppSettings()
        assert s.default_line_width == 3

    def test_default_auto_save_empty(self):
        s = AppSettings()
        assert s.auto_save_dir == ""

    def test_default_log_level(self):
        s = AppSettings()
        assert s.log_level == "DEBUG"

    def test_default_pin_opacity(self):
        s = AppSettings()
        assert s.pin_window_opacity == 100

    # ── 新增字段默认值测试 ──

    def test_default_font_family(self):
        assert AppSettings().default_font_family == "Segoe UI"

    def test_default_font_size(self):
        assert AppSettings().default_font_size == 20

    def test_default_language(self):
        assert AppSettings().language == "zh_CN"

    def test_default_auto_save_format(self):
        assert AppSettings().auto_save_format == "png"

    def test_default_launch_at_startup(self):
        assert AppSettings().launch_at_startup is False

    def test_default_save_window_position(self):
        assert AppSettings().save_window_position is True

    def test_default_capture_sound(self):
        assert AppSettings().capture_sound is False

    def test_default_capture_delay(self):
        assert AppSettings().capture_delay == 0

    def test_default_capture_cursor(self):
        assert AppSettings().capture_cursor is False

    def test_default_capture_after_action(self):
        assert AppSettings().capture_after_action == "none"

    def test_default_toast_enabled(self):
        assert AppSettings().enable_toast is True

    def test_default_toast_duration(self):
        assert AppSettings().toast_duration == 2000

    def test_default_show_hotkey_tip(self):
        assert AppSettings().show_hotkey_tip is True

    def test_default_theme(self):
        assert AppSettings().theme == "light"

    def test_default_accent_color(self):
        assert AppSettings().accent_color == ""

    def test_default_last_tool(self):
        assert AppSettings().last_tool == "select"

    def test_default_max_recent_colors(self):
        assert AppSettings().max_recent_colors == 5

    def test_default_recent_colors_empty(self):
        assert AppSettings().recent_colors == []

    def test_default_tool_settings_empty(self):
        assert AppSettings().tool_settings == {}

    # ── 全局快捷键扩展默认值 ──

    def test_default_hotkey_ocr(self):
        assert AppSettings().hotkey_ocr == "ctrl+shift+t"

    def test_default_hotkey_delay(self):
        assert AppSettings().hotkey_delay == "ctrl+shift+d"

    def test_default_hotkey_pin(self):
        assert AppSettings().hotkey_pin == "ctrl+shift+p"

    def test_default_hotkey_full(self):
        assert AppSettings().hotkey_full == "ctrl+shift+f"

    def test_default_hotkey_color_picker(self):
        assert AppSettings().hotkey_color_picker == "ctrl+shift+c"

    # ── 编辑器内工具快捷键默认值 ──

    def test_default_shortcut_rect(self):
        assert AppSettings().shortcut_rect == "r"

    def test_default_shortcut_ellipse(self):
        assert AppSettings().shortcut_ellipse == "e"

    def test_default_shortcut_arrow(self):
        assert AppSettings().shortcut_arrow == "a"

    def test_default_shortcut_line(self):
        assert AppSettings().shortcut_line == "l"

    def test_default_shortcut_pen(self):
        assert AppSettings().shortcut_pen == "p"

    def test_default_shortcut_text(self):
        assert AppSettings().shortcut_text == "t"

    def test_default_shortcut_highlighter(self):
        assert AppSettings().shortcut_highlighter == "h"

    def test_default_shortcut_blur(self):
        assert AppSettings().shortcut_blur == "b"

    def test_default_shortcut_number_marker(self):
        assert AppSettings().shortcut_number_marker == "n"

    def test_default_shortcut_select(self):
        assert AppSettings().shortcut_select == "v"

    def test_default_shortcut_grid(self):
        assert AppSettings().shortcut_grid == "g"


class TestAppSettingsSaveLoad:
    def test_save_and_load_roundtrip(self, temp_settings_dir):
        s = AppSettings(hotkey="ctrl+shift+a", ocr_language="eng")
        s.save()

        loaded = AppSettings.load()
        assert loaded.hotkey == "ctrl+shift+a"
        assert loaded.ocr_language == "eng"
        assert isinstance(loaded.default_line_width, int)

    def test_load_returns_cached_instance(self, temp_settings_dir):
        first = AppSettings.load()
        second = AppSettings.load()
        assert first is second

    def test_reload_clears_cache(self, temp_settings_dir):
        s = AppSettings(hotkey="alt+1")
        s.save()
        AppSettings.load()

        # change file behind the scenes
        path = os.path.join(temp_settings_dir, "settings.json")
        with open(path, "r+") as f:
            data = json.load(f)
            data["hotkey"] = "alt+2"
            f.seek(0)
            json.dump(data, f)
            f.truncate()

        reloaded = AppSettings.reload()
        assert reloaded.hotkey == "alt+2"

    def test_load_missing_file_returns_defaults(self, temp_settings_dir):
        s = AppSettings.load()
        assert s.hotkey == get_default_hotkey()

    def test_load_corrupted_json_returns_defaults(self, temp_settings_dir):
        path = os.path.join(temp_settings_dir, "settings.json")
        with open(path, "w") as f:
            f.write("{not valid json}")

        s = AppSettings.load()
        assert s.hotkey == get_default_hotkey()

    def test_load_extra_keys_are_filtered(self, temp_settings_dir):
        path = os.path.join(temp_settings_dir, "settings.json")
        with open(path, "w") as f:
            json.dump({"hotkey": "f1", "nonexistent_key": "should_be_ignored"}, f)

        s = AppSettings.load()
        assert s.hotkey == "f1"
        assert not hasattr(s, "nonexistent_key")

    def test_save_creates_directory(self, temp_settings_dir):
        s = AppSettings()
        nested = os.path.join(temp_settings_dir, "subdir", "settings.json")
        import src.core.settings as settings_mod

        settings_mod._SETTINGS_PATH = nested
        s.save()
        assert os.path.exists(nested)


class TestGetSettings:
    def test_get_settings_returns_app_settings(self):
        s = get_settings()
        assert isinstance(s, AppSettings)
