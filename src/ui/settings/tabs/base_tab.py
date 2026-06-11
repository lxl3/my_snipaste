"""Base class for settings dialog tabs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

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
        self._dialog = getattr(self, '_dialog', None)
        self._build_ui()

    def _build_ui(self):
        """Build the tab UI. Override in subclasses."""
        layout = QVBoxLayout(self)
        self.setLayout(layout)

    def _create_scroll_area(self) -> tuple[QScrollArea, QWidget]:
        """创建滚动区域和内容容器"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        if self._dialog:
            vsb = scroll.verticalScrollBar()
            if vsb:
                self._dialog._add_themed_widget(vsb, """
                    QScrollBar:vertical {
                        width: 8px; background: transparent; border: none; margin: 0;
                    }
                    QScrollBar::handle:vertical {
                        background: $border; min-height: 30px; border-radius: 4px;
                    }
                    QScrollBar::handle:vertical:hover { background: $text_placeholder; }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; border: none; }
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
                """)

        content = QWidget()
        if self._dialog:
            self._dialog._add_themed_widget(scroll.viewport(), "background: $bg_primary;")
            self._dialog._add_themed_widget(content, "background: $bg_primary;")

        return scroll, content

    def load_settings(self, settings: AppSettings):
        """Load settings from AppSettings into UI widgets. Override in subclasses."""
        pass

    def save_settings(self, settings: AppSettings):
        """Save settings from UI widgets into AppSettings. Override in subclasses."""
        pass
