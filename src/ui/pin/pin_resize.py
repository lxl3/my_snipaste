"""Pin window resize helpers and thumbnail mode mixin."""

from PySide6.QtCore import QPoint, QSize, Qt


class PinWindowResizeMixin:
    """Window resize and thumbnail mode methods.

    Subclass must provide:
    - MIN_WIDTH, MIN_HEIGHT (int)
    - _resize_start_pos (QPoint)
    - _resize_start_geometry (QRect)
    - _resize_dir (str)
    - _resized_by_user (bool)
    - _toolbar_shown (bool)
    - current_tool (str)
    - _thumbnail_mode (bool)
    - _original_size (QSize | None)
    - _original_pixmap (QPixmap | None)
    - _hide_toolbar()
    - pixmap (QPixmap)
    - _img_w, _img_h (int)
    - _base_img_w, _base_img_h (int)
    - _zoom_factor (float)
    - SHADOW (int)
    - QWidget: setCursor(), setFixedSize(), setGeometry(), update(), size(), rect()
    """

    THUMBNAIL_SIZE = QSize(64, 64)

    # ─── Resize Helpers ───────────────────────────────────

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
        if self._toolbar_shown and self.current_tool not in ("select", ""):
            return
        cursors = {
            'nw': Qt.SizeFDiagCursor, 'se': Qt.SizeFDiagCursor,
            'ne': Qt.SizeBDiagCursor, 'sw': Qt.SizeBDiagCursor,
            'n': Qt.SizeVerCursor, 's': Qt.SizeVerCursor,
            'w': Qt.SizeHorCursor, 'e': Qt.SizeHorCursor,
        }
        if direction in cursors:
            self.setCursor(cursors[direction])
        else:
            self.setCursor(
                Qt.CrossCursor if self._toolbar_shown and self.current_tool not in ("select", "") else Qt.ArrowCursor
            )

    def _handle_resize(self, global_pos: QPoint) -> None:
        dx = global_pos.x() - self._resize_start_pos.x()
        dy = global_pos.y() - self._resize_start_pos.y()
        geo = self._resize_start_geometry
        if 'w' in self._resize_dir:
            new_left = geo.left() + dx
            if geo.right() - new_left >= self.MIN_WIDTH:
                geo.setLeft(new_left)
            else:
                geo.setLeft(geo.right() - self.MIN_WIDTH)
        if 'e' in self._resize_dir:
            new_right = geo.right() + dx
            if new_right - geo.left() >= self.MIN_WIDTH:
                geo.setRight(new_right)
            else:
                geo.setRight(geo.left() + self.MIN_WIDTH)
        if 'n' in self._resize_dir:
            new_top = geo.top() + dy
            if geo.bottom() - new_top >= self.MIN_HEIGHT:
                geo.setTop(new_top)
            else:
                geo.setTop(geo.bottom() - self.MIN_HEIGHT)
        if 's' in self._resize_dir:
            new_bottom = geo.bottom() + dy
            if new_bottom - geo.top() >= self.MIN_HEIGHT:
                geo.setBottom(new_bottom)
            else:
                geo.setBottom(geo.top() + self.MIN_HEIGHT)
        self._resized_by_user = True
        self.setGeometry(geo)
        self.update()
        self.setFixedSize(self.width(), self.height())

    # ─── Thumbnail Mode ───────────────────────────────────

    def _enter_thumbnail_mode(self) -> None:
        if not self._thumbnail_mode:
            self._original_size = self.size()
            self._original_pixmap = self.pixmap.copy()
            thumbnail_pixmap = self._original_pixmap.scaled(
                self.THUMBNAIL_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self.pixmap = thumbnail_pixmap
            w = int(thumbnail_pixmap.width() / thumbnail_pixmap.devicePixelRatio())
            h = int(thumbnail_pixmap.height() / thumbnail_pixmap.devicePixelRatio())
            self._img_w = w
            self._img_h = h
            self._base_img_w = w
            self._base_img_h = h
            self._zoom_factor = 1.0
            self._hide_toolbar()
            self.setFixedSize(self._img_w + self.SHADOW * 2, self._img_h + self.SHADOW * 2)
            self.update()
            self._thumbnail_mode = True

    def _exit_thumbnail_mode(self) -> None:
        if self._thumbnail_mode and self._original_size and self._original_pixmap:
            self.pixmap = self._original_pixmap
            w = int(self._original_pixmap.width() / self._original_pixmap.devicePixelRatio())
            h = int(self._original_pixmap.height() / self._original_pixmap.devicePixelRatio())
            self._img_w = w
            self._img_h = h
            self._base_img_w = w
            self._base_img_h = h
            self._zoom_factor = 1.0
            self.setFixedSize(self._img_w + self.SHADOW * 2, self._img_h + self.SHADOW * 2)
            self.update()
            self._thumbnail_mode = False
            self._original_size = None
            self._original_pixmap = None
