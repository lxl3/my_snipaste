import sys

from src.core.hotkeys import DEFAULT_HOTKEY, get_default_hotkey


class TestDefaultHotkey:
    def test_darwin_default(self):
        assert DEFAULT_HOTKEY["darwin"] == "cmd+shift+x"

    def test_win32_default(self):
        assert DEFAULT_HOTKEY["win32"] == "f12"

    def test_linux_default(self):
        assert DEFAULT_HOTKEY["linux"] == "f12"

    def test_get_default_returns_platform_specific(self, monkeypatch):
        for platform, expected in [("darwin", "cmd+shift+x"), ("win32", "f12"), ("linux", "f12")]:
            monkeypatch.setattr(sys, "platform", platform)
            assert get_default_hotkey() == expected

    def test_get_default_unknown_platform_falls_back(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "unknown")
        assert get_default_hotkey() == "f12"


class TestParseHotkey:
    def _make_listener(self, hotkey):
        from src.core.hotkeys import _PynputListener

        return _PynputListener(hotkey)

    def test_parse_simple_modifier(self):
        listener = self._make_listener("cmd+shift+x")
        keys = listener._parse_hotkey()
        assert len(keys) == 3

    def test_parse_ctrl(self):
        listener = self._make_listener("ctrl+c")
        keys = listener._parse_hotkey()
        assert len(keys) == 2

    def test_parse_function_key(self):
        listener = self._make_listener("f12")
        keys = listener._parse_hotkey()
        assert len(keys) == 1

    def test_parse_with_alt(self):
        listener = self._make_listener("alt+shift+f1")
        keys = listener._parse_hotkey()
        assert len(keys) == 3


class TestNormalize:
    def _make_listener(self):
        from src.core.hotkeys import _PynputListener

        return _PynputListener("ctrl+shift+x")

    def test_normalize_ctrl(self):
        from pynput import keyboard

        listener = self._make_listener()
        assert listener._normalize(keyboard.Key.ctrl_l) is keyboard.Key.ctrl_l
        assert listener._normalize(keyboard.Key.ctrl_r) is keyboard.Key.ctrl_l

    def test_normalize_shift(self):
        from pynput import keyboard

        listener = self._make_listener()
        assert listener._normalize(keyboard.Key.shift_r) is keyboard.Key.shift_l

    def test_normalize_alt(self):
        from pynput import keyboard

        listener = self._make_listener()
        assert listener._normalize(keyboard.Key.alt_r) is keyboard.Key.alt_l

    def test_normalize_cmd(self):
        from pynput import keyboard

        listener = self._make_listener()
        assert listener._normalize(keyboard.Key.cmd_r) is keyboard.Key.cmd

    def test_normalize_other_key_unchanged(self):
        from pynput import keyboard

        listener = self._make_listener()
        key = keyboard.KeyCode.from_char("a")
        assert listener._normalize(key) == key

    def test_normalize_ctrl_letter(self):
        """Ctrl+A (ASCII 0x01) ~ Ctrl+Z (ASCII 0x1A) → 对应小写字母"""
        from pynput import keyboard

        listener = self._make_listener()
        for i, expected_char in enumerate("abcdefghijklmnopqrstuvwxyz"):
            ctrl_char = chr(0x01 + i)  # 0x01 = Ctrl+A, 0x02 = Ctrl+B, ...
            key = keyboard.KeyCode.from_char(ctrl_char)
            result = listener._normalize(key)
            assert result.char == expected_char, (
                f"Ctrl+{chr(0x41 + i)} (0x{0x01 + i:02x}) "
                f"expected '{expected_char}', got '{result.char}'"
            )
