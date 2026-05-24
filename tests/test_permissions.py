import platform

import pytest

from src.core.permissions import (
    check_macos_accessibility,
    check_screen_recording_permission,
    open_input_monitoring_settings,
    open_screen_recording_settings,
    request_input_monitoring_permission,
    request_screen_recording_permission,
    show_permission_guide,
)


class TestNonMacOS:
    @pytest.fixture(autouse=True)
    def non_mac(self, monkeypatch):
        monkeypatch.setattr(platform, "system", lambda: "Linux")

    def test_check_accessibility_returns_true(self):
        assert check_macos_accessibility() is True

    def test_check_screen_recording_returns_true(self):
        assert check_screen_recording_permission() is True

    def test_request_screen_recording_returns_true(self):
        assert request_screen_recording_permission() is True

    def test_request_input_monitoring_returns_true(self):
        assert request_input_monitoring_permission() is True

    def test_open_screen_recording_settings_no_error(self):
        open_screen_recording_settings()

    def test_open_input_monitoring_settings_no_error(self):
        open_input_monitoring_settings()

    def test_show_permission_guide_no_error(self):
        show_permission_guide()


class TestShowPermissionGuide:
    def test_does_not_warn_twice(self):
        show_permission_guide()
        # second call should be a no-op (global flag)
        show_permission_guide()
