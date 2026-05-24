import sys
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
    QCheckBox, QSlider, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout,
)
from ..core.i18n import _, available_languages, load_translations
from ..core.settings import AppSettings, get_settings
from ..core.constants import PRESET_COLORS
from ..core.logger import setup_logger

logger = setup_logger("settings_dialog")


class SettingsDialog(QDialog):
    """Application settings dialog with tabs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings: AppSettings = get_settings()
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        self.setWindowTitle(_("MySnipaste Settings"))
        self.setMinimumSize(520, 420)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), _("General"))
        self._tabs.addTab(self._build_ocr_tab(), _("OCR"))
        self._tabs.addTab(self._build_annotation_tab(), _("Annotation"))
        layout.addWidget(self._tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton(_("Save"))
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }
            QTabBar::tab { padding: 6px 16px; margin: 1px; }
            QTabBar::tab:selected { background: #f0f0f0; border-bottom: 2px solid #0078d4; }
            QGroupBox { font-weight: 600; border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 12px; padding: 16px 12px 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QLineEdit { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; }
            QLineEdit:focus { border-color: #0078d4; }
            QSpinBox { padding: 4px; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton { padding: 6px 20px; border: 1px solid #ccc; border-radius: 4px; background: #fafafa; }
            QPushButton:hover { background: #e8e8e8; }
            QPushButton:pressed { background: #d0d0d0; }
        """)

    # ─── General Tab ───

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Hotkey
        hotkey_group = QGroupBox(_("Global Hotkey"))
        hotkey_layout = QFormLayout(hotkey_group)
        self._hotkey_input = QLineEdit()
        self._hotkey_input.setPlaceholderText("e.g. cmd+shift+x, f12, ctrl+alt+s")
        hotkey_layout.addRow(_("Shortcut:"), self._hotkey_input)
        hint = QLabel(_("Use + between keys. Supported: ctrl, shift, alt, cmd, f1-f12, a-z"))
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hotkey_layout.addRow("", hint)
        layout.addWidget(hotkey_group)

        # Language
        lang_group = QGroupBox(_("Language"))
        lang_layout = QFormLayout(lang_group)
        self._lang_combo = QComboBox()
        for code, label in available_languages():
            self._lang_combo.addItem(label, code)
        lang_layout.addRow(self._lang_combo)
        layout.addWidget(lang_group)

        # Launch at startup (macOS only)
        if sys.platform == "darwin":
            startup_group = QGroupBox(_("Startup"))
            startup_layout = QVBoxLayout(startup_group)
            self._launch_checkbox = QCheckBox(_("Launch MySnipaste at login"))
            startup_layout.addWidget(self._launch_checkbox)
            layout.addWidget(startup_group)

        # Auto-save
        save_group = QGroupBox(_("Auto Save"))
        save_layout = QFormLayout(save_group)
        self._auto_save_checkbox = QCheckBox(_("Auto save to directory"))
        save_layout.addRow(self._auto_save_checkbox)

        dir_row = QHBoxLayout()
        self._save_dir_input = QLineEdit()
        self._save_dir_input.setReadOnly(True)
        self._save_dir_input.setPlaceholderText(_("Select default save directory..."))
        browse_btn = QPushButton(_("Browse..."))
        browse_btn.clicked.connect(self._browse_save_dir)
        dir_row.addWidget(self._save_dir_input)
        dir_row.addWidget(browse_btn)
        save_layout.addRow(_("Directory:"), dir_row)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["PNG", "JPEG"])
        save_layout.addRow(_("Format:"), self._format_combo)

        self._auto_save_checkbox.toggled.connect(self._on_auto_save_toggle)
        layout.addWidget(save_group)

        layout.addStretch()
        return tab

    def _on_auto_save_toggle(self, checked: bool) -> None:
        self._save_dir_input.setEnabled(checked)

    def _browse_save_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, _("Select Save Directory"))
        if path:
            self._save_dir_input.setText(path)

    # ─── OCR Tab ───

    def _build_ocr_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        group = QGroupBox(_("OCR Engine"))
        form = QFormLayout(group)

        self._ocr_lang_input = QLineEdit()
        self._ocr_lang_input.setPlaceholderText("e.g. eng, chi_sim, eng+chi_sim")
        lang_hint = QLabel(
            _("Language codes separated by +.\n"
              "Common: eng, chi_sim, jpn, fra, deu, spa\n"
              "Run 'tesseract --list-langs' to see installed.")
        )
        lang_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow(_("Languages:"), self._ocr_lang_input)
        form.addRow("", lang_hint)
        layout.addWidget(group)

        # Test button
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        test_btn = QPushButton(_("Test OCR"))
        test_btn.clicked.connect(self._test_ocr)
        test_layout.addWidget(test_btn)
        layout.addLayout(test_layout)

        layout.addStretch()
        return tab

    def _test_ocr(self) -> None:
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            QMessageBox.information(self, _("OCR Test"),
                                    _("Tesseract v{version} is ready.\nLanguage: {lang}").format(
                                        version=version, lang=self._ocr_lang_input.text() or 'eng+chi_sim'))
        except Exception as e:
            QMessageBox.warning(self, _("OCR Test"), _("Tesseract not available:\n{error}").format(error=e))

    # ─── Annotation Tab ───

    def _build_annotation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        group = QGroupBox(_("Default Annotation Style"))
        form = QFormLayout(group)

        self._color_combo = QComboBox()
        for c in PRESET_COLORS:
            pix = QPixmap(16, 16)
            pix.fill(QColor(c))
            self._color_combo.addItem(f"  {c}", c)
            self._color_combo.setItemIcon(self._color_combo.count() - 1, QIcon(pix))
        form.addRow(_("Color:"), self._color_combo)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        form.addRow(_("Line Width:"), self._width_spin)

        self._font_combo = QComboBox()
        self._font_combo.addItems(["Segoe UI", "Arial", "Helvetica", "PingFang SC", "Microsoft YaHei"])
        self._font_combo.setEditable(True)
        form.addRow(_("Font:"), self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 72)
        form.addRow(_("Font Size:"), self._font_size_spin)

        layout.addWidget(group)

        # Pin window
        pin_group = QGroupBox(_("Pin Window"))
        pin_layout = QFormLayout(pin_group)
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_label = QLabel("100%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        slider_row = QHBoxLayout()
        slider_row.addWidget(self._opacity_slider)
        slider_row.addWidget(self._opacity_label)
        pin_layout.addRow(_("Opacity:"), slider_row)
        layout.addWidget(pin_group)

        # Log level
        adv_group = QGroupBox(_("Advanced"))
        adv_form = QFormLayout(adv_group)
        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        adv_form.addRow(_("Log Level:"), self._log_level_combo)
        layout.addWidget(adv_group)

        layout.addStretch()
        return tab

    # ─── Load / Save ───

    def _load_settings(self) -> None:
        s = self._settings
        self._hotkey_input.setText(s.hotkey)
        self._ocr_lang_input.setText(s.ocr_language)

        idx = self._color_combo.findData(s.default_color)
        if idx >= 0:
            self._color_combo.setCurrentIndex(idx)
        self._width_spin.setValue(s.default_line_width)
        self._font_combo.setCurrentText(s.default_font_family)
        self._font_size_spin.setValue(s.default_font_size)

        self._save_dir_input.setText(s.auto_save_dir)
        fmt_idx = self._format_combo.findText(s.auto_save_format.upper())
        if fmt_idx >= 0:
            self._format_combo.setCurrentIndex(fmt_idx)
        self._auto_save_checkbox.setChecked(bool(s.auto_save_dir))

        lang_idx = self._lang_combo.findData(s.language)
        if lang_idx >= 0:
            self._lang_combo.setCurrentIndex(lang_idx)

        if hasattr(self, '_launch_checkbox'):
            self._launch_checkbox.setChecked(s.launch_at_startup)

        self._opacity_slider.setValue(s.pin_window_opacity)
        log_idx = self._log_level_combo.findText(s.log_level)
        if log_idx >= 0:
            self._log_level_combo.setCurrentIndex(log_idx)

    def _save_and_close(self) -> None:
        s = self._settings
        s.hotkey = self._hotkey_input.text().strip() or s.hotkey
        s.ocr_language = self._ocr_lang_input.text().strip() or "eng+chi_sim"

        s.default_color = self._color_combo.currentData() or PRESET_COLORS[0]
        s.default_line_width = self._width_spin.value()
        s.default_font_family = self._font_combo.currentText()
        s.default_font_size = self._font_size_spin.value()

        if self._auto_save_checkbox.isChecked():
            s.auto_save_dir = self._save_dir_input.text().strip()
        else:
            s.auto_save_dir = ""
        s.auto_save_format = self._format_combo.currentText().lower()

        s.language = self._lang_combo.currentData() or "zh_CN"

        if hasattr(self, '_launch_checkbox'):
            s.launch_at_startup = self._launch_checkbox.isChecked()
            self._apply_launch_at_startup(s.launch_at_startup)

        s.pin_window_opacity = self._opacity_slider.value()
        s.log_level = self._log_level_combo.currentText()

        s.save()
        logger.info("Settings saved")
        self.accept()

    def _apply_launch_at_startup(self, enable: bool) -> None:
        if sys.platform != "darwin":
            return
        try:
            if enable:
                subprocess.run([
                    "osascript", "-e",
                    f'tell application "System Events" to make login item '
                    f'with properties {{path:"{sys.executable}", hidden:false, name:"MySnipaste"}}'
                ], capture_output=True, timeout=5)
            else:
                subprocess.run([
                    "osascript", "-e",
                    'tell application "System Events" to delete login item "MySnipaste"'
                ], capture_output=True, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to update login item: {e}")

    @staticmethod
    def open(parent=None) -> AppSettings | None:
        dialog = SettingsDialog(parent)
        result = dialog.exec()
        if result == QDialog.Accepted:
            s = AppSettings.reload()
            load_translations(s.language)
            return s
        return None



