import math
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QSize, Signal
from PySide6.QtGui import QPixmap, QPainter, QAction, QColor, QPen, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QMenu, QApplication, QInputDialog, QLineEdit

from ..core.logger import setup_logger
from ..core.settings import get_settings
from ..core.i18n import _
from ..overlay.toolbar import OverlayToolbar
from ..core.constants import ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE

logger = setup_logger("pin_window")


class PinWindow(QWidget):
    """Floating pinned window with drop shadow, zoom, and annotation tools."""

    # Signals for communication with main application
    copy_requested = Signal(QPixmap)
    save_requested = Signal(QPixmap, bool)
    close_requested = Signal()
    toggle_topmost_requested = Signal(bool)
    opacity_changed = Signal(int)
    resize_requested = Signal(QSize)
    thumbnail_mode_toggled = Signal(bool)

    SHADOW = 4        # px shadow ring around the image
    MIN_WIDTH = 100
    MIN_HEIGHT = 100
    THUMBNAIL_SIZE = QSize(64, 64)

    def __init__(self, pixmap: QPixmap, pos) -> None:
        super().__init__()
        self.pixmap = pixmap
        self._dragging: bool = False
        self._drag_pos: QPoint | None = None
        self._resizing: bool = False
        self._resize_dir: str = ""
        self._thumbnail_mode: bool = False
        self._original_size: QSize | None = None
        self._original_pixmap: QPixmap | None = None
        self._resized_by_user: bool = False

        # --- Zoom ---
        self._zoom_factor = 1.0
        self._base_img_w = int(pixmap.width() / pixmap.devicePixelRatio())
        self._base_img_h = int(pixmap.height() / pixmap.devicePixelRatio())

        # --- Annotation state (same interface as CaptureOverlay) ---
        self.annotations: list[dict] = []
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._preview_annotation: dict | None = None
        self._drawing: bool = False
        self._draw_start: QPointF = QPointF()
        self._draw_points: list[QPointF] = []
        self._selected_annotation_index: int = -1

        # Tool state (matching overlay toolbar expectations)
        self.current_tool: str = "select"
        self.current_color: QColor = QColor("#ff0000")
        self.current_width: int = 3
        self.current_blur_radius: int = 10
        self.current_mosaic_scale: int = 8
        self.current_magnifier_zoom: int = 2
        self.eraser_size: int = 20
        self.text_font_family: str = "微软雅黑"
        self.text_font_size: int = 20
        self.text_bold: bool = False
        self.text_italic: bool = False
        self.text_color: QColor = QColor("#000000")

        # --- Toolbar ---
        self._toolbar_obj: OverlayToolbar | None = None
        self._toolbar_shown: bool = False
        self._toolbar_extra_height: int = 0

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Window = image logical size + shadow ring
        self._img_w = self._base_img_w
        self._img_h = self._base_img_h
        self.setFixedSize(self._img_w + self.SHADOW * 2,
                          self._img_h + self.SHADOW * 2)
        if pos is not None:
            self.move(pos.x(), pos.y())

        opacity = get_settings().pin_window_opacity
        self.setWindowOpacity(opacity / 100.0)

        self.setMouseTracking(True)

    # ─── Paint ───────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        s = self.SHADOW
        # Image area (fixed, doesn't change when toolbar is shown)
        img_rect = QRect(s, s, self._img_w, self._img_h)

        # --- Draw drop shadow in the outer ring (only at 1x zoom) ---
        if not self._resized_by_user and self._zoom_factor == 1.0:
            for i in range(s):
                alpha = max(0, 40 - i * 8)
                if alpha <= 0:
                    break
                offset = s - i
                r = img_rect.adjusted(-offset, -offset, offset, offset)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(135, 206, 250, alpha))
                painter.drawRoundedRect(r, 3, 3)

        # --- Draw toolbar dock background below the image ---
        if self._toolbar_shown and self._toolbar_extra_height > 0:
            dock_rect = QRect(s, s + self._img_h,
                              self._img_w, self._toolbar_extra_height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.white)
            painter.drawRect(dock_rect)
            # Thin top border for the dock
            painter.setPen(QPen(QColor("#ccc"), 1))
            painter.drawLine(dock_rect.topLeft(), dock_rect.topRight())

        # --- Draw the image (always within img_rect) ---
        # 使用 drawPixmap(target, source) 让 Qt 自动处理 DPI 缩放
        painter.drawPixmap(img_rect, self.pixmap)

        # --- Draw annotations on top (clipped to img_rect, scaled with zoom) ---
        painter.save()
        painter.setClipRect(img_rect)
        painter.translate(img_rect.topLeft())
        if self._zoom_factor != 1.0 and not self._resized_by_user:
            painter.scale(self._zoom_factor, self._zoom_factor)
        for ann in self.annotations:
            self._draw_annotation(painter, ann)
        if self._preview_annotation:
            self._draw_annotation(painter, self._preview_annotation)
        if 0 <= self._selected_annotation_index < len(self.annotations):
            self._draw_selection_indicator(painter, self.annotations[self._selected_annotation_index])
        painter.restore()

    # ─── Annotation Drawing ───────────────────────────────

    def _draw_annotation(self, painter: QPainter, ann: dict) -> None:
        t = ann["type"]
        if t == "rect":
            self._draw_rect(painter, ann)
        elif t == "ellipse":
            self._draw_ellipse(painter, ann)
        elif t == "arrow":
            self._draw_arrow(painter, ann)
        elif t == "line":
            self._draw_line(painter, ann)
        elif t == "freehand":
            self._draw_freehand(painter, ann)
        elif t == "text":
            self._draw_text_item(painter, ann)
        elif t == "highlighter":
            self._draw_highlighter(painter, ann)
        elif t == "number_marker":
            self._draw_number_marker(painter, ann)

    def _draw_rect(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

    def _draw_ellipse(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"]))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(r)

    def _draw_arrow(self, painter: QPainter, ann: dict) -> None:
        start = QPointF(*ann["start"])
        end = QPointF(*ann["end"])
        width = ann["width"]
        painter.setPen(QPen(QColor(ann["color"]), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        base = ARROW_SIZE_BASE + width * 2
        p1 = QPointF(end.x() - ux * base + uy * base * ARROW_SPREAD_ANGLE,
                     end.y() - uy * base - ux * base * ARROW_SPREAD_ANGLE)
        p2 = QPointF(end.x() - ux * base - uy * base * ARROW_SPREAD_ANGLE,
                     end.y() - uy * base + ux * base * ARROW_SPREAD_ANGLE)
        path = QPainterPath()
        path.moveTo(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        painter.setBrush(QColor(ann["color"]))
        painter.drawPath(path)

    def _draw_line(self, painter: QPainter, ann: dict) -> None:
        start = QPointF(*ann["start"])
        end = QPointF(*ann["end"])
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)

    def _draw_freehand(self, painter: QPainter, ann: dict) -> None:
        pts = [QPointF(*p) for p in ann["points"]]
        if len(pts) < 2:
            return
        painter.setPen(QPen(QColor(ann["color"]), ann["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(pts[0])
        for i in range(1, len(pts)):
            path.lineTo(pts[i])
        painter.drawPath(path)

    def _draw_text_item(self, painter: QPainter, ann: dict) -> None:
        pos = QPointF(*ann["pos"])
        painter.setFont(QFont(ann["font_family"], ann["font_size"]))
        font = painter.font()
        font.setBold(ann["bold"])
        font.setItalic(ann["italic"])
        painter.setFont(font)
        painter.setPen(QColor(ann["color"]))
        fm = painter.fontMetrics()
        painter.drawText(QPointF(pos.x(), pos.y() + fm.ascent()), ann["text"])

    def _draw_highlighter(self, painter: QPainter, ann: dict) -> None:
        r = QRectF(*ann["rect"])
        c = QColor(ann["color"])
        c.setAlphaF(0.3)
        hl_width = ann.get("width", 12)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawRoundedRect(r, hl_width / 2, hl_width / 2)

    def _draw_number_marker(self, painter: QPainter, ann: dict) -> None:
        center = QPointF(*ann["pos"])
        radius = ann.get("radius", 14)
        number = ann.get("number", 1)
        color = QColor(ann.get("color", "#207ff0"))
        text_color = QColor(ann.get("text_color", "#ffffff"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, radius, radius)
        font = painter.font()
        font.setPixelSize(radius)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        fm = painter.fontMetrics()
        text = str(number)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        text_x = center.x() - tw / 2
        text_y = center.y() + fm.ascent() / 2
        painter.drawText(QPointF(text_x, text_y), text)

    def _draw_selection_indicator(self, painter: QPainter, ann: dict) -> None:
        bounds = self._get_ann_bounds(ann)
        if bounds.isNull():
            return
        painter.setPen(QPen(QColor(0, 120, 215), 1.5, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(bounds)
        half = 4
        handles = [
            QRectF(bounds.left() - half, bounds.top() - half, 8, 8),
            QRectF(bounds.right() - half, bounds.top() - half, 8, 8),
            QRectF(bounds.left() - half, bounds.bottom() - half, 8, 8),
            QRectF(bounds.right() - half, bounds.bottom() - half, 8, 8),
        ]
        for h_rect in handles:
            painter.fillRect(h_rect, QColor(0, 120, 215))
            painter.setPen(QPen(Qt.white, 1))
            painter.drawRect(h_rect)

    def _get_ann_bounds(self, ann: dict) -> QRectF:
        t = ann["type"]
        if t in ("rect", "ellipse", "highlighter"):
            return QRectF(*ann["rect"])
        elif t in ("arrow", "line"):
            return QRectF(QPointF(*ann["start"]), QPointF(*ann["end"])).normalized()
        elif t == "freehand":
            pts = ann.get("points", [])
            if not pts:
                return QRectF()
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        elif t == "text":
            pos = QPointF(*ann["pos"])
            return QRectF(pos.x(), pos.y(), 1, 1)
        elif t == "number_marker":
            pos = QPointF(*ann["pos"])
            r = ann.get("radius", 14)
            return QRectF(pos.x() - r, pos.y() - r, r * 2, r * 2)
        return QRectF()

    # ─── Zoom ────────────────────────────────────────────

    def wheelEvent(self, event) -> None:
        """Handle mouse wheel for zooming with smooth scaling."""
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # 保存当前位置（防止 Qt 自动调整）
        current_pos = self.pos()

        # 同步当前实际尺寸（防止手动调整大小后状态不一致）
        actual_w = self.width() - self.SHADOW * 2
        actual_h = self.height() - self.SHADOW * 2

        if actual_w != self._img_w or actual_h != self._img_h:
            self._img_w = actual_w
            self._img_h = actual_h
            # 同步 zoom_factor
            if self._base_img_w > 0 and self._base_img_h > 0:
                self._zoom_factor = self._img_w / self._base_img_w

        old_width = self._img_w
        old_height = self._img_h

        # 调整缩放因子（使用更小的步长）
        if delta > 0:
            self._zoom_factor *= 1.05
        elif delta < 0:
            self._zoom_factor /= 1.05
        self._zoom_factor = max(0.1, min(5.0, self._zoom_factor))

        # 计算新尺寸
        new_img_w = max(1, int(self._base_img_w * self._zoom_factor))
        new_img_h = max(1, int(self._base_img_h * self._zoom_factor))

        # 避免尺寸相同时的无效更新
        if new_img_w == old_width and new_img_h == old_height:
            event.accept()
            return

        self._img_w = new_img_w
        self._img_h = new_img_h

        # 固定左上角位置，向右下缩放
        # 先改变大小，再确保位置不变
        self.setFixedSize(self._img_w + self.SHADOW * 2,
                          self._img_h + self.SHADOW * 2)
        # 强制恢复位置（防止 Qt 自动调整）
        self.move(current_pos)
        self.update()
        event.accept()

    # ─── Mouse Events for Drawing ────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        # Check resize first (works in any mode)
        resize_dir = self._get_resize_direction(event.position().toPoint())
        if resize_dir:
            self._resizing = True
            self._resize_dir = resize_dir
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_start_geometry = self.geometry()
            event.accept()
            return

        if self._toolbar_shown and self.current_tool not in ("select", ""):
            # Drawing mode: start annotation
            self._start_drawing(event)
            event.accept()
            return

        # Default: drag
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
        elif self._drawing and self._toolbar_shown:
            self._update_drawing(event)
            event.accept()
        else:
            resize_dir = self._get_resize_direction(event.position().toPoint())
            self._update_cursor(resize_dir)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drawing and self._toolbar_shown:
            self._finish_drawing()
            event.accept()
            return
        elif event.button() == Qt.LeftButton:
            self._dragging = False
            self._resizing = False
            event.accept()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._thumbnail_mode:
            self._exit_thumbnail_mode()
        else:
            self.close()

    # ─── Drawing Logic ───────────────────────────────────

    def _content_pos(self, event) -> QPointF:
        """Convert widget position to content-area coordinates."""
        return QPointF(event.position().x() - self.SHADOW,
                       event.position().y() - self.SHADOW)

    def _start_drawing(self, event) -> None:
        self._drawing = True
        pos = self._content_pos(event)
        self._draw_start = pos
        self._draw_points = [pos]

        t = self.current_tool
        if t == "text":
            self._finish_text(pos)
            self._drawing = False
        elif t == "number_marker":
            # Count existing number markers
            count = sum(1 for a in self.annotations if a["type"] == "number_marker") + 1
            ann = {
                "type": "number_marker",
                "pos": (pos.x(), pos.y()),
                "radius": 14,
                "number": count,
                "color": self.current_color.name(),
                "text_color": "#ffffff",
            }
            self._add_annotation(ann)
            self._drawing = False
        elif t in ("rect", "ellipse", "arrow", "line", "highlighter", "freehand"):
            # Preview will be updated in mouseMoveEvent
            pass

    def _update_drawing(self, event) -> None:
        pos = self._content_pos(event)
        t = self.current_tool

        if t in ("rect", "ellipse", "highlighter"):
            r = QRectF(self._draw_start, pos).normalized()
            self._preview_annotation = {
                "type": t,
                "rect": (r.x(), r.y(), r.width(), r.height()),
                "color": self.current_color.name(),
                "width": self.current_width if t not in ("highlighter",) else 12,
            }
        elif t in ("arrow", "line"):
            self._preview_annotation = {
                "type": t,
                "start": (self._draw_start.x(), self._draw_start.y()),
                "end": (pos.x(), pos.y()),
                "color": self.current_color.name(),
                "width": self.current_width,
            }
        elif t == "freehand":
            self._draw_points.append(pos)
            self._preview_annotation = {
                "type": "freehand",
                "points": [(p.x(), p.y()) for p in self._draw_points],
                "color": self.current_color.name(),
                "width": self.current_width,
            }
        self.update()

    def _finish_drawing(self) -> None:
        if self._preview_annotation is None:
            return
        ann = dict(self._preview_annotation)
        self._preview_annotation = None
        if ann["type"] in ("arrow", "line"):
            start = QPointF(ann["start"][0], ann["start"][1])
            end = QPointF(ann["end"][0], ann["end"][1])
            if (end - start).manhattanLength() < 5:
                return  # too short
        self._add_annotation(ann)
        self._drawing = False
        self._draw_points = []

    def _finish_text(self, pos: QPointF) -> None:
        text, ok = QInputDialog.getText(self, "输入文字", "文字内容:", QLineEdit.Normal, "")
        if ok and text.strip():
            ann = {
                "type": "text",
                "pos": (pos.x(), pos.y()),
                "text": text.strip(),
                "font_family": self.text_font_family,
                "font_size": self.text_font_size,
                "bold": self.text_bold,
                "italic": self.text_italic,
                "color": self.text_color.name(),
            }
            self._add_annotation(ann)

    def _add_annotation(self, ann: dict) -> None:
        self.annotations.append(ann)
        self._undo_stack.append({"type": "add", "ann": dict(ann), "index": len(self.annotations) - 1})
        self._redo_stack.clear()
        self.update()

    # ─── Toolbar Interface (called by OverlayToolbar) ────

    def _on_tool_selected(self, tool_id: str) -> None:
        self.current_tool = tool_id

    def _apply_property_to_selected(self, prop: str, value) -> None:
        if 0 <= self._selected_annotation_index < len(self.annotations):
            self.annotations[self._selected_annotation_index][prop] = value
            self.update()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        if action["type"] == "add":
            ann = self.annotations.pop(action["index"])
            self._redo_stack.append({"type": "remove", "ann": ann, "index": action["index"]})
        elif action["type"] == "remove":
            self.annotations.insert(action["index"], action["ann"])
            self._redo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        self._update_toolbar_undo_redo()
        self.update()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        if action["type"] == "add":
            self.annotations.append(action["ann"])
            self._undo_stack.append({"type": "remove", "ann": action["ann"], "index": len(self.annotations) - 1})
        elif action["type"] == "remove":
            self.annotations.insert(action["index"], action["ann"])
            self._undo_stack.append({"type": "add", "ann": action["ann"], "index": action["index"]})
        self._update_toolbar_undo_redo()
        self.update()

    def _update_toolbar_undo_redo(self) -> None:
        if self._toolbar_obj:
            self._toolbar_obj.update_undo_redo_state()

    def _on_ocr(self) -> None:
        # OCR not supported in pin window mode - ignored
        pass

    def _on_done_editing(self) -> None:
        """Called by toolbar 'Done' button. Hides the toolbar."""
        self._hide_toolbar()

    def on_pin(self) -> None:
        """Original pin action - not used in pin window mode since toolbar replaces it."""
        pass

    def on_save(self) -> None:
        """Save annotated pixmap - called by toolbar save button."""
        p = self._render_annotated_pixmap()
        self.save_requested.emit(p, True)

    def on_copy(self) -> None:
        """Copy annotated pixmap - called by toolbar copy button."""
        p = self._render_annotated_pixmap()
        self.copy_requested.emit(p)
        from ..ui.toast import ToastManager
        from ..core.i18n import _
        ToastManager.show(_("Copied to clipboard"), "✓", "success", parent=self)

    def _render_annotated_pixmap(self) -> QPixmap:
        """Render the original pixmap with all annotations baked in."""
        result = self.pixmap.copy()
        if not self.annotations:
            return result
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        # Map annotations from content coords to pixmap coords
        # Content area = (SHADOW..SHADOW+_img_w) in widget space
        # Pixmap is drawn at content_rect.topLeft() at the zoom-appropriate scale
        # Since annotations are in content-area coords and pixmap fills content area,
        # we need to scale annotations back to pixmap-native coords
        dpr = result.devicePixelRatio()
        logical_w = result.width() / dpr
        logical_h = result.height() / dpr
        sx = logical_w / self._img_w if self._img_w > 0 else 1.0
        sy = logical_h / self._img_h if self._img_h > 0 else 1.0
        painter.scale(sx, sy)
        for ann in self.annotations:
            self._draw_annotation(painter, ann)
        painter.end()
        return result

    def set_current_tool(self, tool_id: str) -> None:
        """Set current tool (used by toolbar)."""
        self.current_tool = tool_id

    # ─── Toolbar Show / Hide ─────────────────────────────

    def _show_toolbar(self) -> None:
        """Create and show the annotation toolbar below the image (right-aligned)."""
        if self._toolbar_obj is None:
            self._toolbar_obj = OverlayToolbar(self, pin_window_mode=True)
            self._toolbar_obj.setup()
            # Set tool buttons to reflect current state
            if self.current_tool in self._toolbar_obj._tool_btns:
                for tid, btn in self._toolbar_obj._tool_btns.items():
                    btn.setChecked(tid == self.current_tool)

        tb = self._toolbar_obj.toolbar
        tb.setParent(self)
        tb.adjustSize()

        s = self.SHADOW
        extra = tb.height() + 6  # toolbar height + gap
        self._toolbar_extra_height = extra
        # Expand window to make room for toolbar dock below the image
        self.setFixedSize(self._img_w + s * 2, self._img_h + s * 2 + extra)

        # Right-aligned in the dock, 4px gap below image
        tb_x = s + self._img_w - tb.width() - 2
        tb_y = s + self._img_h + 4
        tb.move(tb_x, tb_y)
        tb.show()
        tb.raise_()
        self._toolbar_shown = True
        self.update()

    def _hide_toolbar(self) -> None:
        """Hide the annotation toolbar and restore window size."""
        if self._toolbar_obj:
            self._toolbar_obj.close_menus()
            if self._toolbar_obj.toolbar:
                self._toolbar_obj.toolbar.hide()
        self._toolbar_shown = False
        self._toolbar_extra_height = 0
        s = self.SHADOW
        self.setFixedSize(self._img_w + s * 2, self._img_h + s * 2)
        self.current_tool = "select"
        self._preview_annotation = None
        self._drawing = False
        self.setCursor(Qt.ArrowCursor)
        self.update()

    # ─── Thumbnail Mode ──────────────────────────────────

    def _enter_thumbnail_mode(self) -> None:
        if not self._thumbnail_mode:
            self._original_size = self.size()
            self._original_pixmap = self.pixmap.copy()

            thumbnail_pixmap = self._original_pixmap.scaled(
                self.THUMBNAIL_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
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
            self.setFixedSize(self._img_w + self.SHADOW * 2,
                              self._img_h + self.SHADOW * 2)
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
            self.setFixedSize(self._img_w + self.SHADOW * 2,
                              self._img_h + self.SHADOW * 2)
            self.update()
            self._thumbnail_mode = False
            self._original_size = None
            self._original_pixmap = None

    def closeEvent(self, event) -> None:
        self._hide_toolbar()
        super().closeEvent(event)

    # ─── Resize / Drag ───────────────────────────────────

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
            # Don't override cursor in drawing mode
            return
        if direction in ['nw', 'se']:
            self.setCursor(Qt.SizeFDiagCursor)
        elif direction in ['ne', 'sw']:
            self.setCursor(Qt.SizeBDiagCursor)
        elif direction in ['n', 's']:
            self.setCursor(Qt.SizeVerCursor)
        elif direction in ['w', 'e']:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.CrossCursor if self._toolbar_shown and self.current_tool not in ("select", "") else Qt.ArrowCursor)

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

        self._resized_by_user = True
        self.setGeometry(new_geometry)
        self.update()
        self.setFixedSize(self.width(), self.height())

    # ─── Context Menu ────────────────────────────────────

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)

        # Show Toolbar (toggle)
        show_toolbar_action = QAction(_("Show Toolbar"), self)
        show_toolbar_action.setCheckable(True)
        show_toolbar_action.setChecked(self._toolbar_shown)
        show_toolbar_action.triggered.connect(self._on_toggle_toolbar)
        menu.addAction(show_toolbar_action)

        menu.addSeparator()

        copy_action = QAction(_("Copy"), self)
        copy_action.triggered.connect(self._on_copy)
        menu.addAction(copy_action)

        save_action = QAction(_("Save As..."), self)
        save_action.triggered.connect(self._on_save_as)
        menu.addAction(save_action)

        menu.addSeparator()

        close_action = QAction(_("Close"), self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)

        menu.addSeparator()

        toggle_topmost_action = QAction(_("Toggle Always on Top"), self)
        toggle_topmost_action.setCheckable(True)
        toggle_topmost_action.setChecked(self.isWindowTopMost())
        toggle_topmost_action.triggered.connect(self._on_toggle_topmost)
        menu.addAction(toggle_topmost_action)

        opacity_menu = menu.addMenu(_("Opacity"))
        for opacity in [30, 50, 70, 80, 90, 100]:
            opacity_action = QAction(f"{opacity}%", self)
            opacity_action.setCheckable(True)
            opacity_action.setChecked(get_settings().pin_window_opacity == opacity)
            opacity_action.triggered.connect(lambda checked, op=opacity: self._on_opacity_changed(op))
            opacity_menu.addAction(opacity_action)

        menu.addSeparator()

        thumbnail_action = QAction(_("Thumbnail Mode"), self)
        thumbnail_action.setCheckable(True)
        thumbnail_action.setChecked(self._thumbnail_mode)
        thumbnail_action.triggered.connect(self._on_thumbnail_mode_toggled)
        menu.addAction(thumbnail_action)

        menu.exec(event.globalPos())

    def _on_toggle_toolbar(self, checked: bool) -> None:
        if checked:
            self._show_toolbar()
        else:
            self._hide_toolbar()

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
