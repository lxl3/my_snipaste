import json
import os

from src.core.settings import AppSettings, get_settings


class TestAppSettingsDefaults:
    def test_default_hotkey(self):
        s = AppSettings()
        assert s.hotkey == "cmd+shift+x"

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
        assert s.hotkey == "cmd+shift+x"

    def test_load_corrupted_json_returns_defaults(self, temp_settings_dir):
        path = os.path.join(temp_settings_dir, "settings.json")
        with open(path, "w") as f:
            f.write("{not valid json}")

        s = AppSettings.load()
        assert s.hotkey == "cmd+shift+x"

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
