import json
import os
import tempfile

import pytest


@pytest.fixture
def temp_settings_dir():
    old = {}
    import src.core.settings as settings_mod

    old["dir"] = settings_mod._SETTINGS_DIR
    old["path"] = settings_mod._SETTINGS_PATH
    old["loaded"] = settings_mod._loaded

    with tempfile.TemporaryDirectory(prefix="opensnipaste_test_") as tmpdir:
        settings_mod._SETTINGS_DIR = tmpdir
        settings_mod._SETTINGS_PATH = os.path.join(tmpdir, "settings.json")
        settings_mod._loaded = None
        yield tmpdir

    settings_mod._SETTINGS_DIR = old["dir"]
    settings_mod._SETTINGS_PATH = old["path"]
    settings_mod._loaded = old["loaded"]


@pytest.fixture
def prefilled_settings(temp_settings_dir, request):
    import src.core.settings as settings_mod

    data = getattr(request, "param", {})
    path = os.path.join(temp_settings_dir, "settings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    settings_mod._loaded = None
    return temp_settings_dir
