"""禁用滚轮选择的 QComboBox"""
from PySide6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """禁用滚轮选择的 QComboBox，避免误触"""

    def wheelEvent(self, event):
        event.ignore()
