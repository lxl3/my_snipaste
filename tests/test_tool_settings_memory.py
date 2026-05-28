"""Tests for tool settings memory feature."""

import pytest
from src.core.settings import AppSettings


def test_default_last_tool():
    """Last tool defaults to 'select'."""
    settings = AppSettings()
    assert settings.last_tool == "select"


def test_default_tool_settings_empty():
    """Tool settings start empty."""
    settings = AppSettings()
    assert settings.tool_settings == {}


def test_get_tool_settings_returns_defaults_when_not_saved():
    """get_tool_settings returns defaults for unsaved tools."""
    settings = AppSettings()
    defaults = {"color": "#ff0000", "width": 5}
    result = settings.get_tool_settings("rect", defaults)
    assert result == defaults


def test_save_and_load_tool_settings(temp_settings_dir):
    """Tool settings can be saved and retrieved."""
    settings = AppSettings()

    # Save rectangle settings
    settings.save_tool_settings("rect", {
        "color": "#00ff00",
        "width": 8
    })

    # Retrieve settings
    rect_settings = settings.get_tool_settings("rect")
    assert rect_settings["color"] == "#00ff00"
    assert rect_settings["width"] == 8


def test_save_multiple_tools(temp_settings_dir):
    """Multiple tools can have independent settings."""
    settings = AppSettings()

    settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
    settings.save_tool_settings("arrow", {"color": "#0000ff", "width": 2})
    settings.save_tool_settings("text", {
        "font_family": "Arial",
        "font_size": 24,
        "bold": True,
        "italic": False,
        "color": "#000000"
    })

    rect = settings.get_tool_settings("rect")
    arrow = settings.get_tool_settings("arrow")
    text = settings.get_tool_settings("text")

    assert rect["color"] == "#ff0000"
    assert arrow["color"] == "#0000ff"
    assert text["font_size"] == 24


def test_overwrite_tool_settings(temp_settings_dir):
    """Saving tool settings again overwrites previous values."""
    settings = AppSettings()

    settings.save_tool_settings("rect", {"color": "#ff0000", "width": 3})
    settings.save_tool_settings("rect", {"color": "#00ff00", "width": 5})

    rect = settings.get_tool_settings("rect")
    assert rect["color"] == "#00ff00"
    assert rect["width"] == 5
