"""Test internationalization (i18n) module."""

import json
import os
import tempfile

import pytest

from src.core.i18n import _, available_languages, current_language, load_translations


class TestLoadTranslations:
    def test_english_clears_translations(self):
        """Loading 'en' should clear translations (English = no translation needed)."""
        load_translations("zh_CN")  # load something first
        load_translations("en")
        assert _("任何文本") == "任何文本"  # falls back to original

    def test_chinese_loads_translations(self):
        """Loading 'zh_CN' should populate translations from the locale file."""
        load_translations("zh_CN")
        # A known key from the actual locale file
        translated = _("Capture Screenshot")
        assert translated != "Capture Screenshot"
        assert isinstance(translated, str) and len(translated) > 0

    def test_reload_clears_previous(self):
        """Loading a new language replaces old translations entirely."""
        load_translations("zh_CN")
        first = _("Capture Screenshot")
        assert first != "Capture Screenshot"
        load_translations("en")
        second = _("Capture Screenshot")
        assert second == "Capture Screenshot"  # back to original after clearing

    def test_missing_locale_file_does_not_crash(self):
        """Loading a language with no locale file silently keeps original texts."""
        load_translations("ja_JP")  # doesn't exist
        assert _("Capture Screenshot") == "Capture Screenshot"

    def test_corrupted_locale_file_does_not_crash(self, monkeypatch):
        """Loading a corrupted JSON file silently falls back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = os.path.join(tmpdir, "bad.json")
            with open(bad_file, "w") as f:
                f.write("{not valid json}")

            from src.core import i18n as i18n_mod

            monkeypatch.setattr(i18n_mod, "_locale_path", lambda lang: bad_file)
            load_translations("bad")
            assert _("Capture Screenshot") == "Capture Screenshot"
            assert current_language() == "bad"


class TestTranslate:
    def test_translate_found(self):
        """Existing key returns the translated value."""
        load_translations("zh_CN")
        result = _("Capture Screenshot")
        assert result != "Capture Screenshot"
        assert result == "截图" or len(result) > 0

    def test_translate_missing_returns_original(self):
        """Missing key returns the original text unchanged."""
        load_translations("zh_CN")
        result = _("ThisKeyDoesNotExist_42")
        assert result == "ThisKeyDoesNotExist_42"

    def test_translate_empty_string(self):
        """Empty string returns empty string."""
        load_translations("en")
        assert _("") == ""

    def test_translate_en_returns_original(self):
        """When language is 'en', all text is returned as-is."""
        load_translations("en")
        assert _("Capture Screenshot") == "Capture Screenshot"


class TestCurrentLanguage:
    def test_default_is_en(self):
        """Default language should be 'en'."""
        assert current_language() == "en"

    def test_updates_after_load(self):
        """current_language() reflects the last loaded language."""
        load_translations("zh_CN")
        assert current_language() == "zh_CN"
        load_translations("en")
        assert current_language() == "en"


class TestAvailableLanguages:
    def test_returns_list_of_tuples(self):
        langs = available_languages()
        assert isinstance(langs, list)
        for item in langs:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_contains_expected_languages(self):
        langs = available_languages()
        codes = {code for code, _ in langs}
        assert "en" in codes
        assert "zh_CN" in codes
        assert "zh_TW" in codes

    def test_first_is_english(self):
        """English should be the first listed language."""
        langs = available_languages()
        assert langs[0][0] == "en"
