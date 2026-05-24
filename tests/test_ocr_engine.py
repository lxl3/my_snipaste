import sys

from src.ocr.engine import ensure_tesseract_ready, setup_bundled_tesseract


class TestSetupBundledTesseract:
    def test_unfrozen_calls_system_tesseract(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        result = setup_bundled_tesseract()
        assert result is not None

    def test_frozen_no_meipass_falls_back_and_fails(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        if hasattr(sys, "_MEIPASS"):
            monkeypatch.delattr(sys, "_MEIPASS")
        import src.ocr.engine as ocr_engine

        monkeypatch.setattr(ocr_engine, "_try_system_tesseract", lambda: False)
        result = setup_bundled_tesseract()
        assert result is False


class TestEnsureTesseractReady:
    def test_returns_bool(self):
        result = ensure_tesseract_ready()
        assert isinstance(result, bool)

    def test_idempotent(self):
        first = ensure_tesseract_ready()
        second = ensure_tesseract_ready()
        assert first == second
