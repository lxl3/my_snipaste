"""Themed startup notification dialog for MySnipaste."""

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.i18n import _
from ...core.settings import AppSettings
from ...core.theme_pkg import theme as _t


def show_startup_notification(settings: AppSettings) -> None:
    """Show themed startup notification dialog with hotkey info."""
    hotkey_display = settings.hotkey.upper().replace('+', ' + ')
    settings_key = '⌘,' if sys.platform == 'darwin' else 'Ctrl+,'

    dialog = QDialog()
    dialog.setWindowTitle("MySnipaste")
    dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    dialog.setFixedSize(360, 260)
    dialog.setAttribute(Qt.WA_TranslucentBackground)

    main_container = QWidget(dialog)
    main_container.setObjectName("main_container")

    container_layout = QVBoxLayout(dialog)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.addWidget(main_container)

    layout = QVBoxLayout(main_container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    close_btn = QPushButton("×")
    close_btn.setObjectName("close_btn")
    close_btn.setFixedSize(28, 28)
    close_btn.clicked.connect(dialog.accept)
    close_btn.setCursor(Qt.PointingHandCursor)

    header = QWidget()
    header.setObjectName("header")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.addStretch()
    header_layout.addWidget(close_btn)
    layout.addWidget(header)

    content = QWidget()
    content.setObjectName("content")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(24, 0, 24, 24)
    content_layout.setSpacing(18)

    title = QLabel("MySnipaste")
    title.setObjectName("title")
    title.setAlignment(Qt.AlignCenter)
    content_layout.addWidget(title)

    cards_layout = QVBoxLayout()
    cards_layout.setSpacing(10)

    capture_card = QWidget()
    capture_card.setObjectName("card")
    capture_layout = QVBoxLayout(capture_card)
    capture_layout.setContentsMargins(16, 14, 16, 14)
    capture_layout.setSpacing(6)

    capture_title = QLabel("📸  " + _("Screenshot"))
    capture_title.setObjectName("card_title")
    capture_layout.addWidget(capture_title)
    capture_key = QLabel(hotkey_display)
    capture_key.setObjectName("card_key")
    capture_layout.addWidget(capture_key)
    cards_layout.addWidget(capture_card)

    settings_card = QWidget()
    settings_card.setObjectName("card")
    settings_layout = QVBoxLayout(settings_card)
    settings_layout.setContentsMargins(16, 14, 16, 14)
    settings_layout.setSpacing(6)

    settings_title = QLabel("⚙️  " + _("Settings"))
    settings_title.setObjectName("card_title")
    settings_layout.addWidget(settings_title)
    settings_key_label = QLabel(settings_key)
    settings_key_label.setObjectName("card_key")
    settings_layout.addWidget(settings_key_label)
    cards_layout.addWidget(settings_card)

    content_layout.addLayout(cards_layout)
    layout.addWidget(content, 1)

    # High contrast theme QSS template
    qss_tpl = """
        QDialog { background: transparent; }
        #main_container {
            background: $bg; border: 1px solid $border; border-radius: 16px;
        }
        #header { background: transparent; padding: 8px 8px 0 0; }
        #close_btn {
            background: transparent; border: none; color: $text_secondary;
            font-size: 22px; font-weight: 300; border-radius: 14px;
        }
        #close_btn:hover { background: $hover; color: $text_primary; }
        #content { background: transparent; }
        #title {
            font-size: 26px; font-weight: 900; color: $accent; letter-spacing: -0.8px;
        }
        #card {
            background: $card_bg; border: 2px solid $card_border; border-radius: 10px;
        }
        #card:hover { background: $card_hover; border-color: $accent; }
        #card_title { font-size: 15px; font-weight: 700; color: $text_primary; }
        #card_key {
            font-size: 18px; font-weight: 800; color: $accent;
            font-family: 'Consolas', 'SF Mono', 'Monaco', monospace; letter-spacing: 1.5px;
        }
    """

    def _build_qss() -> str:
        if _t.is_dark():
            vars_map = {
                'bg': '#1A1A1A', 'border': '#333333',
                'text_primary': '#FFFFFF', 'text_secondary': '#999999',
                'accent': _t.accent_color, 'hover': 'rgba(255, 255, 255, 0.08)',
                'card_bg': '#242424', 'card_border': '#333333', 'card_hover': '#2A2A2A',
            }
        else:
            vars_map = {
                'bg': '#FFFFFF', 'border': '#E5E5E5',
                'text_primary': '#000000', 'text_secondary': '#666666',
                'accent': _t.accent_color, 'hover': 'rgba(0, 0, 0, 0.05)',
                'card_bg': '#F8F8F8', 'card_border': '#E5E5E5', 'card_hover': '#F0F0F0',
            }
        result = qss_tpl
        for key, value in vars_map.items():
            result = result.replace(f'${key}', value)
        return result

    dialog.setStyleSheet(_build_qss())

    # Entrance animation
    dialog.setWindowOpacity(0)
    fade_in = QPropertyAnimation(dialog, b"windowOpacity")
    fade_in.setDuration(300)
    fade_in.setStartValue(0.0)
    fade_in.setEndValue(1.0)
    fade_in.setEasingCurve(QEasingCurve.OutCubic)
    fade_in.start()

    # Center on screen
    screen = QApplication.primaryScreen().geometry()
    dialog.move(screen.center().x() - dialog.width() // 2,
                screen.center().y() - dialog.height() // 2)

    # Theme update connection
    dialog_ref = [dialog]  # list to close over mutable ref

    def update_style():
        d = dialog_ref[0]
        if d is not None:
            d.setStyleSheet(_build_qss())

    _t.theme_changed.connect(update_style)

    def cleanup():
        dialog_ref[0] = None
        try:
            _t.theme_changed.disconnect(update_style)
        except (TypeError, RuntimeError):
            pass

    dialog.finished.connect(cleanup)

    QTimer.singleShot(3000, dialog.close)
    dialog.exec()
