"""Pin window context menu and action handlers mixin."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap

from ...core import qss_base
from ...core.i18n import _
from ...core.utils import create_emoji_icon
from ..common.glass_widget import GlassMenu


def _get_menu_style() -> str:
    return qss_base.menu_qss()


class PinWindowMenuMixin:
    """Context menu and action handlers.

    Subclass must provide:
    - _thumbnail_mode (bool)
    - _original_pixmap (QPixmap | None)
    - pixmap (QPixmap)
    - _toolbar_shown (bool)
    - _hide_toolbar(), _show_toolbar()
    - _enter_thumbnail_mode(), _exit_thumbnail_mode()
    - _crop(), _rotate_cw(), _rotate_ccw(), _flip_h(), _flip_v()
    - ctx (AppContext with .settings.pin_window_opacity, .settings.pin_window_topmost)
    - copy_requested (Signal), save_requested (Signal)
    - toggle_topmost_requested (Signal), opacity_changed (Signal)
    - close(), show(), setWindowFlags(), windowFlags()
    - QWidget: windowFlags(), setWindowFlags(), setWindowOpacity(), show(), close()
    """

    def contextMenuEvent(self, event) -> None:
        menu = GlassMenu(self)
        menu.setStyleSheet(_get_menu_style())

        show_toolbar_action = QAction(create_emoji_icon("🔧"), _("Show Toolbar"), self)
        show_toolbar_action.setCheckable(True)
        show_toolbar_action.setChecked(self._toolbar_shown)
        show_toolbar_action.triggered.connect(self._on_toggle_toolbar)
        menu.addAction(show_toolbar_action)

        menu.addSeparator()

        copy_action = QAction(create_emoji_icon("📋"), _("Copy"), self)
        copy_action.triggered.connect(self._on_copy)
        menu.addAction(copy_action)

        save_action = QAction(create_emoji_icon("💾"), _("Save As..."), self)
        save_action.triggered.connect(self._on_save_as)
        menu.addAction(save_action)

        menu.addSeparator()

        qrcode_action = QAction(create_emoji_icon("📱"), _("QR Code Recognition"), self)
        qrcode_action.triggered.connect(self._on_qrcode)
        menu.addAction(qrcode_action)

        ocr_action = QAction(create_emoji_icon("🔍"), _("OCR Text Recognition"), self)
        ocr_action.triggered.connect(self._on_ocr)
        menu.addAction(ocr_action)

        menu.addSeparator()

        crop_action = QAction(create_emoji_icon("✂️"), _("Crop to selection"), self)
        crop_action.triggered.connect(self._crop)
        menu.addAction(crop_action)

        menu.addSeparator()

        transform_menu = menu.addMenu(_("Image Transform"))
        transform_menu.setIcon(create_emoji_icon("🔄"))
        transform_menu.setStyleSheet(_get_menu_style())
        rotate_cw_act = QAction(create_emoji_icon("↻"), _("Rotate 90° Clockwise"), self)
        rotate_cw_act.triggered.connect(self._rotate_cw)
        transform_menu.addAction(rotate_cw_act)
        rotate_ccw_act = QAction(create_emoji_icon("↺"), _("Rotate 90° Counter-Clockwise"), self)
        rotate_ccw_act.triggered.connect(self._rotate_ccw)
        transform_menu.addAction(rotate_ccw_act)
        transform_menu.addSeparator()
        flip_h_act = QAction(create_emoji_icon("⇆"), _("Flip Horizontally"), self)
        flip_h_act.triggered.connect(self._flip_h)
        transform_menu.addAction(flip_h_act)
        flip_v_act = QAction(create_emoji_icon("⇅"), _("Flip Vertically"), self)
        flip_v_act.triggered.connect(self._flip_v)
        transform_menu.addAction(flip_v_act)

        close_action = QAction(create_emoji_icon("❌"), _("Close"), self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)

        menu.addSeparator()

        toggle_topmost_action = QAction(create_emoji_icon("📌"), _("Toggle Always on Top"), self)
        toggle_topmost_action.setCheckable(True)
        toggle_topmost_action.setChecked(self.isWindowTopMost())
        toggle_topmost_action.triggered.connect(self._on_toggle_topmost)
        menu.addAction(toggle_topmost_action)

        opacity_menu = menu.addMenu(_("Opacity"))
        opacity_menu.setIcon(create_emoji_icon("💧"))
        opacity_menu.setStyleSheet(_get_menu_style())
        for opacity in [30, 50, 70, 80, 90, 100]:
            opacity_action = QAction(f"{opacity}%", self)
            opacity_action.setCheckable(True)
            opacity_action.setChecked(self.ctx.settings.pin_window_opacity == opacity)
            opacity_action.triggered.connect(lambda checked, op=opacity: self._on_opacity_changed(op))
            opacity_menu.addAction(opacity_action)

        menu.addSeparator()

        thumbnail_action = QAction(create_emoji_icon("🔍"), _("Thumbnail Mode"), self)
        thumbnail_action.setCheckable(True)
        thumbnail_action.setChecked(self._thumbnail_mode)
        thumbnail_action.triggered.connect(self._on_thumbnail_mode_toggled)
        menu.addAction(thumbnail_action)

        menu.exec(event.globalPos())

    # ─── Action Handlers ──────────────────────────────────

    def _on_toggle_toolbar(self, checked: bool) -> None:
        if checked:
            self._show_toolbar()
        else:
            self._hide_toolbar()

    def _on_copy(self) -> None:
        self.copy_requested.emit(self._get_current_pixmap())
        from ...core.i18n import _
        from ..common.toast import ToastManager
        ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)

    def _on_save_as(self) -> None:
        self.save_requested.emit(self._get_current_pixmap(), False)
        from ...core.i18n import _
        from ..common.toast import ToastManager
        ToastManager.show(_("Saved"), "💾", "success", parent=self)

    def _on_toggle_topmost(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()
        s = self.ctx.settings
        s.pin_window_topmost = checked
        s.save()
        self.toggle_topmost_requested.emit(checked)

    def _on_opacity_changed(self, opacity: int) -> None:
        self.setWindowOpacity(opacity / 100.0)
        s = self.ctx.settings
        s.pin_window_opacity = opacity
        s.save()
        self.opacity_changed.emit(opacity)

    def _on_thumbnail_mode_toggled(self, checked: bool) -> None:
        if checked:
            self._enter_thumbnail_mode()
        else:
            self._exit_thumbnail_mode()

    def _get_current_pixmap(self) -> QPixmap:
        if self._thumbnail_mode and self._original_pixmap:
            return self._original_pixmap
        return self.pixmap

    def isWindowTopMost(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
