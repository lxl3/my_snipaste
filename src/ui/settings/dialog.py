"""设置对话框 - 模块化重构版本

使用独立的 Tab 模块替代内联代码，提高可维护性。
"""
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import qss_base
from ...core.i18n import _, load_translations
from ...core.logger import setup_logger
from ...core.settings import AppSettings, get_settings
from ...core.theme_pkg import theme as _theme
from ..theme_dialog import ThemeAwareDialog
from ..title_bar import TitleBar
from .tabs import (
    AdvancedTab,
    AnnotationTab,
    CaptureTab,
    GeneralTab,
    HotkeysTab,
    OcrTab,
)

logger = setup_logger("settings_dialog")


class SettingsDialog(ThemeAwareDialog):
    """Application settings dialog with modular tabs."""

    _instance: "SettingsDialog | None" = None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._settings: AppSettings = get_settings()
        self._tabs_instances: list = []
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        self.setWindowTitle(_("MySnipaste Settings"))
        self.setMinimumSize(520, 420)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAutoFillBackground(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_bar = TitleBar(self, _("MySnipaste Settings"))
        outer.addWidget(self._title_bar)

        content = QWidget()
        content.setObjectName("settingsContent")
        content.setAttribute(Qt.WA_StyledBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)

        self._tabs = QTabWidget()
        self._tabs.setAttribute(Qt.WA_StyledBackground)

        self._general_tab = GeneralTab(dialog=self)
        self._capture_tab = CaptureTab(dialog=self)
        self._annotation_tab = AnnotationTab(dialog=self)
        self._hotkeys_tab = HotkeysTab(dialog=self)
        self._ocr_tab = OcrTab(dialog=self)
        self._advanced_tab = AdvancedTab(dialog=self)

        self._tabs_instances = [
            self._general_tab,
            self._capture_tab,
            self._annotation_tab,
            self._hotkeys_tab,
            self._ocr_tab,
            self._advanced_tab,
        ]

        self._tabs.addTab(self._general_tab, _("General"))
        self._tabs.addTab(self._capture_tab, _("Capture"))
        self._tabs.addTab(self._annotation_tab, _("Annotation"))
        self._tabs.addTab(self._hotkeys_tab, _("Shortcuts"))
        self._tabs.addTab(self._ocr_tab, _("OCR"))
        self._tabs.addTab(self._advanced_tab, _("Advanced"))

        for i in range(self._tabs.count()):
            tab_widget = self._tabs.widget(i)
            if tab_widget:
                tab_widget.setAttribute(Qt.WA_StyledBackground)
        layout.addWidget(self._tabs)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(_("Search settings..."))
        self._search_input.textChanged.connect(self._filter_settings)
        layout.addWidget(self._search_input)

        btn_layout = QHBoxLayout()

        reset_btn = QPushButton(_("Reset to Defaults"))
        reset_btn.clicked.connect(self._reset_to_defaults)
        self._add_themed_widget(reset_btn, "color: $text_secondary;")
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        export_btn = QPushButton(_("Export..."))
        export_btn.clicked.connect(self._export_settings)
        btn_layout.addWidget(export_btn)

        import_btn = QPushButton(_("Import..."))
        import_btn.clicked.connect(self._import_settings)
        btn_layout.addWidget(import_btn)

        save_btn = QPushButton(_("Save"))
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        outer.addWidget(content, stretch=1)

        _theme.apply_to_widget(self)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """应用对话框样式表"""
        dialog_specific = _theme.qss("""
            QDialog {
                background: $bg_primary;
                border: 1px solid $border;
            }
            #settingsContent {
                background: $bg_primary;
            }
            TitleBar {
                background: $bg_secondary;
                border-bottom: 1px solid $border;
            }
            TitleBar QLabel {
                color: $text_primary;
                font-size: 13px;
                font-weight: 600;
            }
            TitleBar QPushButton {
                background: transparent;
                border: none;
                color: $text_primary;
                font-size: 14px;
                padding: 2px 8px;
                border-radius: 2px;
            }
            TitleBar QPushButton:hover {
                background: $hover_bg;
            }
            TitleBar QPushButton:pressed {
                background: $accent;
                color: $text_accent;
            }
            QTabWidget {
                background: $bg_primary;
            }
            QTabWidget::pane {
                border: 1px solid $border;
                border-radius: 4px;
                padding: 8px;
                background: $bg_primary;
            }
            QTabWidget QStackedWidget {
                background: $bg_primary;
            }
            QTabWidget QStackedWidget > QWidget {
                background: $bg_primary;
            }
            QTabBar {
                background: $bg_primary;
            }
            QTabBar::tab {
                padding: 6px 16px;
                margin: 1px;
                color: $text_primary;
                background: transparent;
            }
            QTabBar::tab:selected {
                background: $accent;
                color: $text_accent;
            }
            QTabBar::tab:hover:!selected {
                background: $hover_bg;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget { background: transparent; }
        """)
        shared = "".join([
            qss_base.groupbox_qss(),
            qss_base.lineedit_qss(),
            qss_base.spinbox_qss(),
            qss_base.pushbutton_qss(),
            qss_base.checkbox_qss(),
            qss_base.combobox_qss(),
            qss_base.label_qss(selector="QLabel"),
            qss_base.slider_qss(),
        ])
        self.setStyleSheet(dialog_specific + shared)

    def _on_before_theme_apply(self) -> None:
        """主题切换前的准备"""
        _theme.apply_to_widget(self._tabs)
        _tab_bar = self._tabs.findChild(QTabBar)
        if _tab_bar:
            _theme.apply_to_widget(_tab_bar)
        for i in range(self._tabs.count()):
            tab_widget = self._tabs.widget(i)
            if tab_widget:
                _theme.apply_to_widget(tab_widget)

    def _on_theme_changed(self, mode: str) -> None:
        """主题切换时重新应用样式"""
        # 先应用新 QSS（避免 super 中 unpolish/polish 使用旧样式导致闪烁）
        self._apply_styles()

        super()._on_theme_changed(mode)

        # 刷新所有包含 token 的内联样式
        for label in self.findChildren(QLabel):
            style = label.styleSheet()
            if style and '$' in style:
                label.setStyleSheet(_theme.qss(style))

        # 刷新 GeneralTab 的主题色按钮
        if hasattr(self._general_tab, '_update_accent_btn_style'):
            self._general_tab._update_accent_btn_style()

    def _load_settings(self) -> None:
        """从 settings 加载值到所有 Tab"""
        for tab in self._tabs_instances:
            tab.load_settings(self._settings)

    def _save_and_close(self) -> None:
        """保存设置并关闭"""
        conflicts = self._hotkeys_tab.check_conflicts()
        if conflicts:
            reply = QMessageBox.warning(
                self,
                _("Shortcut Conflict"),
                _("The following shortcuts conflict:\n\n{conflicts}\n\n"
                  "Do you want to save anyway?").format(conflicts="\n".join(conflicts)),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        for tab in self._tabs_instances:
            tab.save_settings(self._settings)

        self._settings.save()
        logger.info("Settings saved")

        if hasattr(self, '_on_saved_callback') and self._on_saved_callback:
            new_settings = AppSettings.reload()
            load_translations(new_settings.language)
            self._on_saved_callback(new_settings)

        self.accept()

    def _reset_to_defaults(self) -> None:
        """重置所有设置为默认值"""
        reply = QMessageBox.question(
            self,
            _("Reset to Defaults"),
            _("Are you sure you want to reset all settings to their default values?\n\n"
              "This action cannot be undone."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for tab in self._tabs_instances:
                tab.reset_to_defaults()
            logger.info("Settings reset to defaults")
            QMessageBox.information(self, _("Reset Complete"), _("Settings have been reset to default values."))

    def _filter_settings(self, text: str) -> None:
        """根据搜索文本过滤设置"""
        tab = self._tabs.currentWidget()
        if not tab:
            return
        text = text.strip().lower()
        for group in tab.findChildren(QGroupBox):
            if not text:
                group.show()
                continue
            title = group.title().lower()
            if text in title:
                group.show()
                continue
            found = False
            for label in group.findChildren(QLabel):
                if text in label.text().lower():
                    found = True
                    break
            if not found:
                for cb in group.findChildren(QCheckBox):
                    if text in cb.text().lower():
                        found = True
                        break
            group.setVisible(found)

    def _export_settings(self) -> None:
        """导出设置到 JSON 文件"""
        path, _selected = QFileDialog.getSaveFileName(
            self, _("Export Settings"),
            "mysnipaste_settings.json",
            _("JSON Files (*.json)")
        )
        if not path:
            return

        for tab in self._tabs_instances:
            tab.save_settings(self._settings)

        data = self._settings.__dict__.copy()
        data.pop('_path', None)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Settings exported to {path}")
            QMessageBox.information(self, _("Export"), _("Settings exported successfully."))
        except Exception as e:
            logger.error(f"Failed to export settings: {e}")
            QMessageBox.warning(self, _("Export Error"), _("Failed to export settings:\n{error}").format(error=e))

    def _import_settings(self) -> None:
        """从 JSON 文件导入设置"""
        path, _selected = QFileDialog.getOpenFileName(
            self, _("Import Settings"),
            "", _("JSON Files (*.json)")
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read import file: {e}")
            QMessageBox.warning(self, _("Import Error"),
                                _("Failed to read file:\n{error}").format(error=e))
            return

        if not isinstance(data, dict):
            QMessageBox.warning(self, _("Import Error"), _("Invalid settings file format."))
            return

        for key, value in data.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

        self._load_settings()

        logger.info(f"Settings imported from {path}")
        QMessageBox.information(self, _("Import"), _("Settings imported successfully.\nClick Save to apply them."))

    @classmethod
    def open_non_modal(cls, parent=None, on_saved=None) -> "SettingsDialog":
        """非模态方式打开设置对话框"""
        if cls._instance is not None:
            cls._instance.raise_()
            cls._instance.activateWindow()
            return cls._instance

        dialog = cls(parent)
        cls._instance = dialog
        dialog._on_saved_callback = on_saved
        dialog.destroyed.connect(lambda: setattr(cls, '_instance', None))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    @staticmethod
    def open(parent=None) -> AppSettings | None:
        """模态方式打开设置对话框"""
        dialog = SettingsDialog(parent)
        result = dialog.exec()
        if result == QDialog.Accepted:
            s = AppSettings.reload()
            load_translations(s.language)
            return s
        return None
