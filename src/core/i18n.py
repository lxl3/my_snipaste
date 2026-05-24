import json
import os
import sys

_translations: dict[str, str] = {}
_current_lang: str = "en"


def load_translations(lang: str) -> None:
    global _translations, _current_lang
    _current_lang = lang
    _translations.clear()

    if lang == "en":
        return

    path = _locale_path(lang)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                _translations.update(json.load(f))
        except Exception:
            pass


def _(text: str) -> str:
    return _translations.get(text, text)


def current_language() -> str:
    return _current_lang


def _locale_path(lang: str) -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "resources", "locales", f"{lang}.json")


def available_languages() -> list[tuple[str, str]]:
    return [
        ("en", "English"),
        ("zh_CN", "简体中文"),
        ("zh_TW", "繁體中文"),
    ]
