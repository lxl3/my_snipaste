from PySide6.QtCore import Qt, QPoint, QSize, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QAction
from PySide6.QtWidgets import QWidget, QMenu, QApplication

from ..core.logger import setup_logger
from ..core.settings import get_settings

logger = setup_logger("pin_window")


class PinWindow(QWidget):
    """Floating pinned window with pre-rendered shadow."""

    # Signals for communication with main application
    copy_requested = Signal(QPixmap)
    save_requested = Signal(QPixmap, bool)
    close_requested = Signal()
    toggle_topmost_requested = Signal(bool)
    opacity_changed = Signal(int)
    resize_requested = Signal(QSize)
    thumbnail_mode_toggled = Signal(bool)

    SHADOW_SIZE = 6
    MIN_WIDTH = 100
    MIN_HEIGHT = 100
    THUMBNAIL_SIZE = QSize(64, 64)

    def __init__(self, pixmap: QPixmap, pos) -> None:
        super().__init__()
        self.pixmap = pixmap
        self._dragging: bool = False
        self._drag_pos: QPoint | None = None
        self._resizing: bool = False
        self._resize_dir: str = ""  # 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'
        self._thumbnail_mode: bool = False
        self._original_size: QSize | None = None
        self._original_pixmap: QPixmap | None = None
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Load saved geometry if available
        settings = get_settings()
        if settings.pin_window_geometry:
            try:
                x, y, w, h = map(int, settings.pin_window_geometry.split(','))
                self.setGeometry(x, y, w, h)
            except (ValueError, AttributeError):
                # Fallback to default positioning if saved geometry is invalid
                padding = self.SHADOW_SIZE
                bw = int(pixmap.width() / pixmap.devicePixelRatio()) + padding * 2
                bh = int(pixmap.height() / pixmap.devicePixelRatio()) + padding * 2
                self.setFixedSize(bw, bh)
                if pos is not None:
                    self.move(pos.x(), pos.y())
        else:
            padding = self.SHADOW_SIZE
            bw = int(pixmap.width() / pixmap.devicePixelRatio()) + padding * 2
            bh = int(pixmap.height() / pixmap.devicePixelRatio()) + padding * 2
            self.setFixedSize(bw, bh)
            if pos is not None:
                self.move(pos.x(), pos.y())

        self._shadow_pixmap = self._render_shadow(self.width(), self.height())

        opacity = get_settings().pin_window_opacity
        self.setWindowOpacity(opacity / 100.0)

    def _render_shadow(self, w: int, h: int) -> QPixmap:
        pm = QPixmap(QSize(w, h))
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        padding = self.SHADOW_SIZE
        margin = 1
        content_rect = pm.rect().adjusted(padding, padding, -padding, -padding)
        shadow_color = QColor(40, 120, 255)

        for i in range(padding):
            alpha = max(0, 80 - i * 10)
            if alpha <= 0:
                break
            offset = padding - margin - i
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(shadow_color.red(), shadow_color.green(), shadow_color.blue(), alpha))
            p.drawRoundedRect(
                content_rect.adjusted(-offset, -offset, offset, offset),
                4 + i, 4 + i,
            )

        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.setBrush(Qt.white)
        p.drawRoundedRect(content_rect, 4, 4)
        p.end()
        return pm

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._shadow_pixmap)

        padding = self.SHADOW_SIZE
        content_rect = self.rect().adjusted(padding, padding, -padding, -padding)

        scaled = self.pixmap.scaled(
            content_rect.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = content_rect.x() + (content_rect.width() - scaled.width()) // 2
        y = content_rect.y() + (content_rect.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._thumbnail_mode:
            self._exit_thumbnail_mode()
        else:
            self.close()

    def _enter_thumbnail_mode(self) -> None:
        """Enter thumbnail mode - shrink window to 64x64."""
        if not self._thumbnail_mode:
            self._original_size = self.size()
            self._original_pixmap = self.pixmap.copy()
            
            # Scale pixmap to thumbnail size
            thumbnail_pixmap = self._original_pixmap.scaled(
                self.THUMBNAIL_SIZE, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.pixmap = thumbnail_pixmap
            
            # Update window size
            padding = self.SHADOW_SIZE
            bw = thumbnail_pixmap.width() + padding * 2
            bh = thumbnail_pixmap.height() + padding * 2
            self.setFixedSize(bw, bh)
            
            # Update shadow
            self._update_shadow()
            
            self._thumbnail_mode = True

    def _exit_thumbnail_mode(self) -> None:
        if self._thumbnail_mode and self._original_size and self._original_pixmap:
            self.pixmap = self._original_pixmap
            
            padding = self.SHADOW_SIZE
            bw = self._original_pixmap.width() + padding * 2
            bh = self._original_pixmap.height() + padding * 2
            self.setFixedSize(bw, bh)
            
            self._update_shadow()
            
            self._thumbnail_mode = False
            self._original_size = None
            self._original_pixmap = None

    def closeEvent(self, event) -> None:
        """Save window geometry when closing."""
        from ..core.settings import get_settings
        settings = get_settings()
        geometry = self.geometry()
        settings.pin_window_geometry = f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}"
        settings.save()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            resize_dir = self._get_resize_direction(event.position().toPoint())
            if resize_dir:
                self._resizing = True
                self._resize_dir = resize_dir
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
                event.accept()
                return
            
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = True
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._resize_dir:
            self._handle_resize(event.globalPosition().toPoint())
            event.accept()
        elif self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            resize_dir = self._get_resize_direction(event.position().toPoint())
            self._update_cursor(resize_dir)

    def _get_resize_direction(self, pos: QPoint) -> str:
        border_width = 5
        rect = self.rect()
        x, y = pos.x(), pos.y()
        
        left = x < border_width
        right = x > rect.width() - border_width
        top = y < border_width
        bottom = y > rect.height() - border_width
        
        if left and top:
            return 'nw'
        elif right and top:
            return 'ne'
        elif left and bottom:
            return 'sw'
        elif right and bottom:
            return 'se'
        elif left:
            return 'w'
        elif right:
            return 'e'
        elif top:
            return 'n'
        elif bottom:
            return 's'
        return ""

    def _update_cursor(self, direction: str) -> None:
        if direction in ['nw', 'se']:
            self.setCursor(Qt.SizeFDiagCursor)
        elif direction in ['ne', 'sw']:
            self.setCursor(Qt.SizeBDiagCursor)
        elif direction in ['n', 's']:
            self.setCursor(Qt.SizeVerCursor)
        elif direction in ['w', 'e']:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _handle_resize(self, global_pos: QPoint) -> None:
        dx = global_pos.x() - self._resize_start_pos.x()
        dy = global_pos.y() - self._resize_start_pos.y()
        
        new_geometry = self._resize_start_geometry
        
        if 'w' in self._resize_dir:
            new_left = self._resize_start_geometry.left() + dx
            if self._resize_start_geometry.right() - new_left >= self.MIN_WIDTH:
                new_geometry.setLeft(new_left)
            else:
                new_geometry.setLeft(self._resize_start_geometry.right() - self.MIN_WIDTH)
                
        if 'e' in self._resize_dir:
            new_right = self._resize_start_geometry.right() + dx
            if new_right - self._resize_start_geometry.left() >= self.MIN_WIDTH:
                new_geometry.setRight(new_right)
            else:
                new_geometry.setRight(self._resize_start_geometry.left() + self.MIN_WIDTH)
                
        if 'n' in self._resize_dir:
            new_top = self._resize_start_geometry.top() + dy
            if self._resize_start_geometry.bottom() - new_top >= self.MIN_HEIGHT:
                new_geometry.setTop(new_top)
            else:
                new_geometry.setTop(self._resize_start_geometry.bottom() - self.MIN_HEIGHT)
                
        if 's' in self._resize_dir:
            new_bottom = self._resize_start_geometry.bottom() + dy
            if new_bottom - self._resize_start_geometry.top() >= self.MIN_HEIGHT:
                new_geometry.setBottom(new_bottom)
            else:
                new_geometry.setBottom(self._resize_start_geometry.top() + self.MIN_HEIGHT)
        
        self.setGeometry(new_geometry)
        self._update_shadow()

    def _update_shadow(self) -> None:
        """Update shadow pixmap when window size changes."""
        padding = self.SHADOW_SIZE
        bw = self.width()
        bh = self.height()
        self._shadow_pixmap = self._render_shadow(bw, bh)
        self.update()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        
        copy_action = QAction("复制到剪贴板", self)
        copy_action.triggered.connect(self._on_copy)
        menu.addAction(copy_action)
        
        save_action = QAction("另存为...", self)
        save_action.triggered.connect(self._on_save_as)
        menu.addAction(save_action)
        
        menu.addSeparator()
        
        close_action = QAction("关闭窗口", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        
        menu.addSeparator()
        
        toggle_topmost_action = QAction("切换置顶状态", self)
        toggle_topmost_action.setCheckable(True)
        toggle_topmost_action.setChecked(self.isWindowTopMost())
        toggle_topmost_action.triggered.connect(self._on_toggle_topmost)
        menu.addAction(toggle_topmost_action)
        
        opacity_menu = menu.addMenu("调整不透明度")
        for opacity in [30, 50, 70, 80, 90, 100]:
            opacity_action = QAction(f"{opacity}%", self)
            opacity_action.setCheckable(True)
            opacity_action.setChecked(get_settings().pin_window_opacity == opacity)
            opacity_action.triggered.connect(lambda checked, op=opacity: self._on_opacity_changed(op))
            opacity_menu.addAction(opacity_action)
        
        menu.addSeparator()
        
        thumbnail_action = QAction("缩略图模式", self)
        thumbnail_action.setCheckable(True)
        thumbnail_action.setChecked(self._thumbnail_mode)
        thumbnail_action.triggered.connect(self._on_thumbnail_mode_toggled)
        menu.addAction(thumbnail_action)
        
        menu.exec(event.globalPos())

    def _on_copy(self) -> None:
        self.copy_requested.emit(self._get_current_pixmap())
        from ..ui.toast import ToastManager
        from ..core.i18n import _
        ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)

    def _on_save_as(self) -> None:
        self.save_requested.emit(self._get_current_pixmap(), False)
        from ..ui.toast import ToastManager
        from ..core.i18n import _
        ToastManager.show(_("Saved"), "💾", "success", parent=self)

    def _on_toggle_topmost(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()
        settings = get_settings()
        settings.pin_window_topmost = checked
        settings.save()
        self.toggle_topmost_requested.emit(checked)

    def _on_opacity_changed(self, opacity: int) -> None:
        self.setWindowOpacity(opacity / 100.0)
        settings = get_settings()
        settings.pin_window_opacity = opacity
        settings.save()
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
