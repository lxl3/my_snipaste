"""Base class for settings dialog tabs."""

from PySide6.QtWidgets import QWidget, QVBoxLayout

from ....core.settings import AppSettings


class BaseTab(QWidget):
    """Base class for all settings tabs.

    Each tab is responsible for:
    1. Building its own UI (_build_ui)
    2. Loading settings from AppSettings (load_settings)
    3. Saving settings to AppSettings (save_settings)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the tab UI. Override in subclasses."""
        layout = QVBoxLayout(self)
        self.setLayout(layout)

    def load_settings(self, settings: AppSettings):
        """Load settings from AppSettings into UI widgets. Override in subclasses."""
        pass

    def save_settings(self, settings: AppSettings):
        """Save settings from UI widgets into AppSettings. Override in subclasses."""
        pass
