import os

import pytest

from src.core.utils import ScreenCaptureError, _get_app_dir, resource_path


class TestScreenCaptureError:
    def test_is_runtime_error(self):
        assert issubclass(ScreenCaptureError, RuntimeError)

    def test_can_be_raised_with_message(self):
        with pytest.raises(ScreenCaptureError, match="test error"):
            raise ScreenCaptureError("test error")

    def test_can_be_caught_as_runtime_error(self):
        try:
            raise ScreenCaptureError("capture failed")
        except RuntimeError:
            pass


class TestGetAppDir:
    def test_returns_string(self):
        path = _get_app_dir()
        assert isinstance(path, str)
        assert os.path.isabs(path)

    def test_ends_with_project_root(self):
        path = _get_app_dir()
        assert path.endswith("opensnipaste")

    def test_not_frozen_in_test(self):
        path = _get_app_dir()
        assert "src" not in os.path.basename(path)


class TestResourcePath:
    def test_returns_absolute_path(self):
        path = resource_path("assets/icons/icon-256.png")
        assert os.path.isabs(path)

    def test_appends_to_app_dir(self):
        app_dir = _get_app_dir()
        path = resource_path("some/file.txt")
        assert path == os.path.join(app_dir, "some/file.txt")

    def test_preserves_trailing_path(self):
        path = resource_path("foo/bar/baz.txt")
        assert path.endswith("foo/bar/baz.txt")
