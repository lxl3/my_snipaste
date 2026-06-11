"""OCR 设置 Tab"""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from ....core.i18n import _
from ....core.settings import AppSettings
from ...common.settings_card import SettingsCard
from .base_tab import BaseTab


class OcrTab(BaseTab):
    """OCR 设置 Tab - 语言、引擎测试"""

    tab_id = "ocr"
    tab_name = "OCR"
    tab_icon = "text"

    def __init__(self, parent=None, dialog=None):
        self._dialog = dialog
        self._ocr_lang_input = None
        super().__init__(parent)

    def _build_ui(self):
        """构建 OCR 设置 UI"""
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll, content = self._create_scroll_area()
        tab_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._build_ocr_card(layout)

        layout.addStretch()
        scroll.setWidget(content)

    def _build_ocr_card(self, layout: QVBoxLayout) -> None:
        """OCR 引擎卡片"""
        ocr_card = SettingsCard(icon="🔍", title=_("OCR Engine"))

        lang_row = QHBoxLayout()
        lang_label = QLabel(_("Languages:"))
        if self._dialog:
            self._dialog._add_themed_widget(lang_label, "QLabel { color: $text_primary; }")
        self._ocr_lang_input = QLineEdit()
        self._ocr_lang_input.setPlaceholderText(_("e.g. eng, chi_sim, eng+chi_sim"))
        lang_row.addWidget(lang_label)
        lang_row.addWidget(self._ocr_lang_input, 1)
        ocr_card.add_layout(lang_row)

        lang_hint = QLabel(
            _("Language codes separated by +.\n"
              "Common: eng, chi_sim, jpn, fra, deu, spa\n"
              "Run 'tesseract --list-langs' to see installed.")
        )
        if self._dialog:
            self._dialog._add_themed_widget(lang_hint, "QLabel { color: $text_placeholder; font-size: 11px; }")
        ocr_card.add_widget(lang_hint)

        ocr_card.add_spacing(8)

        test_btn = QPushButton(_("Test OCR"))
        test_btn.clicked.connect(self._test_ocr)
        ocr_card.add_widget(test_btn)

        layout.addWidget(ocr_card)

    def _test_ocr(self) -> None:
        """测试 OCR 引擎"""
        from ...ocr_test_dialog import OcrTestDialog
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            lang = self._ocr_lang_input.text() or 'eng+chi_sim'
            OcrTestDialog.show_result(
                success=True,
                message=_("Tesseract is ready"),
                details=_("Version: {version}\nLanguage: {lang}").format(version=version, lang=lang),
                parent=self,
            )
        except Exception as e:
            OcrTestDialog.show_result(
                success=False,
                message=_("Tesseract not available"),
                details=str(e),
                parent=self,
            )

    def load_settings(self, settings: AppSettings):
        """加载设置"""
        self._ocr_lang_input.setText(settings.ocr_language)

    def save_settings(self, settings: AppSettings):
        """保存设置"""
        settings.ocr_language = self._ocr_lang_input.text().strip() or "eng+chi_sim"

    def reset_to_defaults(self):
        """重置为默认值"""
        defaults = AppSettings()
        self._ocr_lang_input.setText(defaults.ocr_language)
