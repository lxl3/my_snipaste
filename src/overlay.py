import math

from PySide6.QtWidgets import QWidget, QApplication, QLineEdit, QMessageBox
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, Signal, QEvent

from .utils import capture_all_screens
from .overlay_toolbar import OverlayToolbar
from .ocr_mixin import OcrMixin
from .constants import (
    DEFAULT_ANNOTATION_COLOR, SELECTION_BORDER_COLOR, DIM_OVERLAY_COLOR,
    HANDLE_SIZE, MIN_SELECTION_SIZE, MIN_DRAW_THRESHOLD, TOOLBAR_MARGIN,
    ARROW_SIZE_BASE, ARROW_SPREAD_ANGLE, MOSAIC_SCALE_FACTOR,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_LINE_WIDTH,
)
from .logger import setup_logger

logger = setup_logger("overlay")


class CaptureOverlay(QWidget, OcrMixin):
    pin_requested = Signal(object, object)
    copy_requested = Signal(object)
    save_requested = Signal(object)

    def __init__(self):
        super().__init__()

        self.total_geometry = QRect()
        for screen in QApplication.screens():
            self.total_geometry = self.total_geometry.united(screen.geometry())

        logger.info(f"初始化截图覆盖层，屏幕区域: {self.total_geometry}")
        self.full_screenshot = capture_all_screens()
        logger.debug(f"截图尺寸: {self.full_screenshot.width()}x{self.full_screenshot.height()}")

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(self.total_geometry)
        self.setCursor(Qt.CrossCursor)
        self.grabKeyboard()

        self.is_selecting = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selection_rect = QRect()
        self.current_mouse_pos = QPoint()

        self._drag_mode = None
        self._drag_start_pos = QPointF()
        self._drag_start_rect = QRect()

        self.current_tool = "select"
        self.current_color = QColor(DEFAULT_ANNOTATION_COLOR)
        self.current_width = DEFAULT_LINE_WIDTH
        self.annotations = []
        self._redo_stack = []
        self._drawing = False
        self._draw_start = QPointF()
        self._draw_points = []
        self._preview_annotation = None

        self._text_editor = None
        self._text_editor_pos = None

        self.text_font_family = DEFAULT_FONT_FAMILY
        self.text_font_size = DEFAULT_FONT_SIZE
        self.text_bold = False
        self.text_italic = False
        self.text_color = QColor(DEFAULT_ANNOTATION_COLOR)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.toolbar = OverlayToolbar(self)
        self.toolbar.setup()

    # ─── Selection helpers ───

    def _capture_pos(self):
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

    def _sel_to_local(self, pos):
        return QPointF(pos - self.selection_rect.topLeft())

    def _get_all_handles(self, rect):
        half = HANDLE_SIZE // 2
        r = rect
        return [
            QRect(r.left() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.left() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.center().x() - half, r.top() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.center().x() - half, r.bottom() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.left() - half, r.center().y() - half, HANDLE_SIZE, HANDLE_SIZE),
            QRect(r.right() - half, r.center().y() - half, HANDLE_SIZE, HANDLE_SIZE),
        ]

    def _handle_at_pos(self, pos):
        handles = self._get_all_handles(self.selection_rect)
        names = ["top-left", "top-right", "bottom-left", "bottom-right",
                 "top-center", "bottom-center", "left-center", "right-center"]
        for h_rect, name in zip(handles, names):
            if h_rect.contains(pos):
                return name
        return None

    def _cursor_for_handle(self, handle_name):
        if not handle_name:
            return Qt.ArrowCursor if self.selection_rect.contains(self.current_mouse_pos) else Qt.CrossCursor
        mapping = {
            "top-left": Qt.SizeFDiagCursor, "bottom-right": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor, "bottom-left": Qt.SizeBDiagCursor,
            "top-center": Qt.SizeVerCursor, "bottom-center": Qt.SizeVerCursor,
            "left-center": Qt.SizeHorCursor, "right-center": Qt.SizeHorCursor,
        }
        return mapping.get(handle_name, Qt.ArrowCursor)

    # ─── Rendering ───

    def _render_annotated_pixmap(self) -> QPixmap:
        dpr = self.full_screenshot.devicePixelRatio()
        logical_rect = self.selection_rect
        physical_rect = QRect(
            round(logical_rect.x() * dpr), round(logical_rect.y() * dpr),
            round(logical_rect.width() * dpr), round(logical_rect.height() * dpr)
        )
        pm = self.full_screenshot.copy(physical_rect)
        pm.setDevicePixelRatio(dpr)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_annotations(painter, logical_rect.size(), QPointF(0, 0))
        painter.end()
        return pm

    def _draw_annotations(self, painter, view_size, offset):
        for ann in self.annotations:
            self._draw_annotation(painter, ann, offset)
        if self._preview_annotation:
            self._draw_annotation(painter, self._preview_annotation, offset)

    def _draw_annotation(self, painter, ann, offset):
        t = ann["type"]
        if t in ("rect", "ellipse"):
            r = QRectF(ann["rect"]).translated(offset)
            p = QPen(ann["color"], ann["width"])
            painter.setPen(p)
            painter.setBrush(Qt.NoBrush)
            if t == "rect":
                painter.drawRect(r)
            else:
                painter.drawEllipse(r)
        elif t in ("arrow", "line"):
            start = ann["start"] + offset
            end = ann["end"] + offset
            painter.setPen(QPen(ann["color"], ann["width"]))
            painter.drawLine(start, end)
            if t == "arrow":
                self._draw_arrowhead(painter, start, end, ann["width"])
        elif t == "freehand":
            pts = [p + offset for p in ann["points"]]
            if len(pts) >= 2:
                painter.setPen(QPen(ann["color"], ann["width"]))
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                painter.drawPath(path)
        elif t == "mosaic":
            self._draw_mosaic(painter, ann, offset)
        elif t == "text":
            self._draw_text(painter, ann, offset)

    def _draw_arrowhead(self, painter, start, end, width):
        arrow_size = ARROW_SIZE_BASE + width
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        p1 = end - QPointF(arrow_size * math.cos(angle + ARROW_SPREAD_ANGLE), arrow_size * math.sin(angle + ARROW_SPREAD_ANGLE))
        p2 = end - QPointF(arrow_size * math.cos(angle - ARROW_SPREAD_ANGLE), arrow_size * math.sin(angle - ARROW_SPREAD_ANGLE))
        painter.drawLine(end, p1)
        painter.drawLine(end, p2)

    def _draw_mosaic(self, painter, ann, offset):
        dpr = self.full_screenshot.devicePixelRatio()
        r = QRectF(ann["rect"]).translated(offset).toRect()
        sel = self.selection_rect
        src_rect = QRect(
            round((sel.x() + ann["rect"].x()) * dpr),
            round((sel.y() + ann["rect"].y()) * dpr),
            round(ann["rect"].width() * dpr),
            round(ann["rect"].height() * dpr)
        )
        if src_rect.width() > 0 and src_rect.height() > 0:
            src = self.full_screenshot.copy(src_rect)
            small = src.scaled(max(src.width() // MOSAIC_SCALE_FACTOR, 1), max(src.height() // MOSAIC_SCALE_FACTOR, 1), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = small.scaled(src.width(), src.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
            painter.drawPixmap(r, blurred, blurred.rect())

    def _draw_text(self, painter, ann, offset):
        pos = ann["pos"] + offset
        painter.setPen(QPen(ann["color"]))
        font = QFont(ann.get("font_family", "Segoe UI"), ann.get("font_size", 20))
        font.setBold(ann.get("bold", False))
        font.setItalic(ann.get("italic", False))
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_pos = pos.toPoint() + QPoint(4, fm.ascent() + 2)
        painter.drawText(text_pos, ann["text"])

    # ─── Actions ───

    def _on_ocr(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        from .ocr_engine import OcrWorker
        from .utils import qpixmap_to_pil
        pil_image = qpixmap_to_pil(captured)
        self._ocr_worker = OcrWorker(pil_image)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()
        self._show_ocr_progress(self._cancel_ocr)

    def _on_ocr_finished(self, text):
        self._cleanup_ocr()
        if text:
            from .utils import OcrResultDialog
            OcrResultDialog(text, self).exec()
        else:
            QMessageBox.warning(self, "OCR 结果", "未识别到文字")

    def _on_ocr_error(self, error_msg):
        self._cleanup_ocr()
        QMessageBox.critical(self, "OCR 错误", f"文字识别失败：\n{error_msg}")

    def on_pin(self):
        if self.selection_rect.isNull():
            return
        self.pin_requested.emit(self._render_annotated_pixmap(), self._capture_pos())
        self.close()

    def on_copy(self):
        if self.selection_rect.isNull():
            return
        self.copy_requested.emit(self._render_annotated_pixmap())
        self.close()

    def on_save(self):
        if self.selection_rect.isNull():
            return
        self.save_requested.emit(self._render_annotated_pixmap())

    # ─── Undo / Redo ───

    def _undo(self):
        if self.annotations:
            self._redo_stack.append(self.annotations.pop())
            self.toolbar.update_undo_redo_state()
            self.update()

    def _redo(self):
        if self._redo_stack:
            self.annotations.append(self._redo_stack.pop())
            self.toolbar.update_undo_redo_state()
            self.update()

    def _try_erase_annotation(self, pos):
        local = self._sel_to_local(QPointF(pos))
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            t = ann["type"]
            if t in ("rect", "ellipse", "mosaic"):
                if QRectF(ann["rect"]).contains(local):
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t in ("arrow", "line"):
                if self._point_to_segment_distance(local, ann["start"], ann["end"]) < 10:
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return
            elif t == "freehand":
                pts = ann["points"]
                for j in range(len(pts) - 1):
                    if self._point_to_segment_distance(local, pts[j], pts[j + 1]) < 10:
                        self._redo_stack.append(self.annotations.pop(i))
                        self.toolbar.update_undo_redo_state()
                        self.update()
                        return
            elif t == "text":
                font = QFont(ann.get("font_family", "Segoe UI"), ann.get("font_size", 20))
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                fm = self.fontMetrics()
                text_w = fm.horizontalAdvance(ann["text"]) + 8
                text_h = fm.height() + 4
                text_rect = QRectF(ann["pos"].x(), ann["pos"].y(), text_w, text_h)
                if text_rect.contains(local):
                    self._redo_stack.append(self.annotations.pop(i))
                    self.toolbar.update_undo_redo_state()
                    self.update()
                    return

    def _point_to_segment_distance(self, point, p1, p2):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return math.hypot(point.x() - p1.x(), point.y() - p1.y())
        t = max(0, min(1, ((point.x() - p1.x()) * dx + (point.y() - p1.y()) * dy) / length_sq))
        proj_x = p1.x() + t * dx
        proj_y = p1.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

    # ─── Text editing ───

    def _adjust_text_editor_size(self):
        if not self._text_editor:
            return
        text = self._text_editor.text()
        fm = self._text_editor.fontMetrics()
        width = fm.horizontalAdvance(text) + 14 if text else 10
        height = fm.height() + 6
        current_pos = getattr(self, '_text_editor_window_pos', self._text_editor.pos())
        self._text_editor.setFixedSize(max(width, 10), height)
        self._text_editor.move(current_pos)

    def _finish_text_input(self):
        if not self._text_editor or self._text_editor_pos is None:
            return
        text = self._text_editor.text().strip()
        if text:
            self.annotations.append({
                "type": "text", "pos": self._text_editor_pos, "text": text,
                "color": QColor(self.text_color), "font_family": self.text_font_family,
                "font_size": self.text_font_size, "bold": self.text_bold,
                "italic": self.text_italic,
            })
            self._redo_stack.clear()
            self.toolbar.update_undo_redo_state()
            self.update()

        self._text_editor.textChanged.disconnect()
        self._text_editor.returnPressed.disconnect()
        self._text_editor.editingFinished.disconnect()
        self._text_editor.hide()
        self._text_editor.deleteLater()
        self._text_editor = None
        self._text_editor_pos = None
        self.grabKeyboard()

    # ─── Toolbar positioning ───

    def _position_toolbar(self):
        rect = self.selection_rect
        if rect.isNull():
            self.toolbar.toolbar.hide()
            return
        self.toolbar.toolbar.adjustSize()
        tw = self.toolbar.toolbar.width()
        th = self.toolbar.toolbar.height()
        x = rect.right() - tw
        y = rect.bottom() + 8
        if y + th > self.height() - 10:
            y = rect.top() - th - 8
        if x < 10:
            x = rect.left()
        if x + tw > self.width() - 10:
            x = self.width() - tw - 10
        self.toolbar.toolbar.move(x, y)
        self.toolbar.toolbar.show()
        self.toolbar.toolbar.raise_()

    # ─── Painting ───

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.full_screenshot)
        painter.fillRect(self.rect(), DIM_OVERLAY_COLOR)

        rect = self.selection_rect
        if not rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            dpr = self.full_screenshot.devicePixelRatio()
            physical_rect = QRect(
                int(rect.x() * dpr), int(rect.y() * dpr),
                int(rect.width() * dpr), int(rect.height() * dpr)
            )
            painter.drawPixmap(rect, self.full_screenshot, physical_rect)
            self._draw_annotations(painter, rect.size(), rect.topLeft())

            painter.setPen(QPen(SELECTION_BORDER_COLOR, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            for h_rect in self._get_all_handles(rect):
                painter.fillRect(h_rect, SELECTION_BORDER_COLOR)
                painter.setPen(QPen(Qt.white, 1))
                painter.drawRect(h_rect)

            self._draw_size_info(painter, rect)

        if not (self.toolbar.toolbar.isVisible() and self.toolbar.toolbar.geometry().contains(self.current_mouse_pos)):
            self._draw_coord_tooltip(painter)

    def _draw_size_info(self, painter, rect):
        info_text = f"{rect.width()} x {rect.height()}"
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 12))
        text_width = painter.fontMetrics().horizontalAdvance(info_text) + 20
        text_height = 28
        text_x = rect.x()
        text_y = rect.bottom() + 8
        if text_y + text_height > self.height() - 10:
            text_y = rect.top() - text_height - 8
        painter.fillRect(QRect(text_x, text_y, text_width, text_height), QColor(0, 0, 0, 180))
        painter.drawText(QRect(text_x, text_y, text_width, text_height), Qt.AlignCenter, info_text)

    def _draw_coord_tooltip(self, painter):
        coord_text = f"{self.current_mouse_pos.x()}, {self.current_mouse_pos.y()}"
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 11))
        cx, cy = self.current_mouse_pos.x(), self.current_mouse_pos.y()
        coord_w, coord_h = 130, 24
        coord_rect = QRect(cx + 15, cy + 15, coord_w, coord_h)
        if coord_rect.right() > self.width() - 10:
            coord_rect.moveLeft(cx - coord_w - 15)
        if coord_rect.bottom() > self.height() - 10:
            coord_rect.moveTop(cy - coord_h - 15)
        painter.fillRect(coord_rect, QColor(0, 0, 0, 160))
        painter.drawText(coord_rect, Qt.AlignCenter, coord_text)

    # ─── Event handling ───

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.setCursor(Qt.ArrowCursor)
        elif event.type() == QEvent.Leave:
            self.setCursor(Qt.ArrowCursor if not self.selection_rect.isNull() else Qt.CrossCursor)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if self._text_editor and not self._text_editor.geometry().contains(event.position().toPoint()):
            self._finish_text_input()

        if event.button() == Qt.RightButton:
            if self._drag_mode or not self.selection_rect.isNull():
                self.selection_rect = QRect()
                self._drag_mode = None
                self.annotations.clear()
                self.toolbar.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
                return
            self.close()
            return

        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if not self.selection_rect.isNull() and self.current_tool == "eraser":
                self._try_erase_annotation(pos)
                return
            if not self.selection_rect.isNull() and self.current_tool != "select":
                self._start_drawing(pos)
                return
            if not self.selection_rect.isNull():
                handle = self._handle_at_pos(pos)
                if handle:
                    self._drag_mode = ("resize", handle)
                    self._drag_start_pos = event.position()
                    self._drag_start_rect = QRect(self.selection_rect)
                    return
                if self.selection_rect.contains(pos):
                    self._drag_mode = ("move",)
                    self._drag_start_pos = event.position()
                    self._drag_start_rect = QRect(self.selection_rect)
                    return
            self._start_selection(pos)

    def _start_drawing(self, pos):
        local = self._sel_to_local(QPointF(pos))
        self._drawing = True
        self._draw_start = local
        self._draw_points = [local]
        if self.current_tool == "text":
            if self._text_editor:
                self._finish_text_input()
            self._text_editor_pos = local
            self._text_editor = QLineEdit(self)
            font = QFont(self.text_font_family, self.text_font_size)
            font.setBold(self.text_bold)
            font.setItalic(self.text_italic)
            self._text_editor.setFont(font)
            self._text_editor_window_pos = self.selection_rect.topLeft() + local.toPoint()
            self._text_editor.setStyleSheet(f"""
                QLineEdit {{
                    background: transparent; border: 1px solid white; padding: 2px 4px;
                    color: {self.text_color.name()};
                }}
            """)
            self._text_editor.move(self._text_editor_window_pos)
            self._text_editor.setMinimumWidth(10)
            self._text_editor.setAttribute(Qt.WA_DeleteOnClose)
            self._text_editor.textChanged.connect(self._adjust_text_editor_size)
            self._adjust_text_editor_size()
            self.releaseKeyboard()
            self._text_editor.show()
            self._text_editor.setFocus()
            self._text_editor.returnPressed.connect(self._finish_text_input)
            self._text_editor.editingFinished.connect(self._finish_text_input)
            self._drawing = False

    def _start_selection(self, pos):
        self.is_selecting = True
        self.toolbar.toolbar.hide()
        self.annotations.clear()
        self.start_point = pos
        self.end_point = self.start_point
        self.selection_rect = QRect()
        self.current_tool = "select"
        for btn in self.toolbar._tool_btns.values():
            btn.setChecked(False)
        self.update()

    def mouseMoveEvent(self, event):
        self.current_mouse_pos = event.position().toPoint()
        if self._drawing:
            self._update_drawing()
            return
        if self._drag_mode:
            self._update_drag(event.position())
            return
        if self.is_selecting:
            self.end_point = self.current_mouse_pos
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
        elif not self.selection_rect.isNull():
            handle = self._handle_at_pos(self.current_mouse_pos)
            self.setCursor(self._cursor_for_handle(handle))
            self.update()

    def _update_drawing(self):
        local = self._sel_to_local(QPointF(self.current_mouse_pos))
        if self.current_tool == "freehand":
            self._draw_points.append(local)
            if len(self._draw_points) == 2:
                self.annotations.append({
                    "type": "freehand", "points": list(self._draw_points),
                    "color": QColor(self.current_color), "width": self.current_width,
                })
                self._redo_stack.clear()
                self.toolbar.update_undo_redo_state()
            elif len(self._draw_points) > 2 and self.annotations and self.annotations[-1]["type"] == "freehand":
                self.annotations[-1]["points"] = list(self._draw_points)
        else:
            dx = local.x() - self._draw_start.x()
            dy = local.y() - self._draw_start.y()
            if self.current_tool in ("rect", "ellipse"):
                self._preview_annotation = {
                    "type": self.current_tool, "rect": QRectF(self._draw_start, local).normalized(),
                    "color": QColor(self.current_color), "width": self.current_width,
                }
            elif self.current_tool in ("arrow", "line") and (abs(dx) > MIN_DRAW_THRESHOLD or abs(dy) > MIN_DRAW_THRESHOLD):
                self._preview_annotation = {
                    "type": self.current_tool, "start": QPointF(self._draw_start),
                    "end": QPointF(local), "color": QColor(self.current_color), "width": self.current_width,
                }
            elif self.current_tool == "mosaic":
                r = QRectF(self._draw_start, local).normalized()
                if r.width() > MIN_DRAW_THRESHOLD and r.height() > MIN_DRAW_THRESHOLD:
                    self._preview_annotation = {"type": "mosaic", "rect": r}
        self.update()

    def _update_drag(self, current_pos):
        delta = current_pos - self._drag_start_pos
        mode = self._drag_mode[0]
        if mode == "move":
            self.selection_rect = QRect(
                int(self._drag_start_rect.x() + delta.x()), int(self._drag_start_rect.y() + delta.y()),
                self._drag_start_rect.width(), self._drag_start_rect.height()
            )
        elif mode == "resize":
            handle = self._drag_mode[1]
            r = QRect(self._drag_start_rect)
            if "left" in handle:
                r.setLeft(int(self._drag_start_rect.left() + delta.x()))
            if "right" in handle:
                r.setRight(int(self._drag_start_rect.right() + delta.x()))
            if "top" in handle:
                r.setTop(int(self._drag_start_rect.top() + delta.y()))
            if "bottom" in handle:
                r.setBottom(int(self._drag_start_rect.bottom() + delta.y()))
            self.selection_rect = r.normalized()
        self._position_toolbar()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._drawing:
            self._finish_drawing()
            return
        if self._drag_mode:
            self._drag_mode = None
            self._position_toolbar()
            return
        if self.is_selecting:
            self.is_selecting = False
            if self.selection_rect.width() > MIN_SELECTION_SIZE and self.selection_rect.height() > MIN_SELECTION_SIZE:
                self._position_toolbar()
            else:
                self.selection_rect = QRect()

    def _finish_drawing(self):
        self._drawing = False
        if self._preview_annotation and self._preview_annotation["type"] != "freehand":
            ann = self._preview_annotation
            if ann["type"] in ("rect", "ellipse", "mosaic") and ann["rect"].width() > MIN_DRAW_THRESHOLD and ann["rect"].height() > MIN_DRAW_THRESHOLD:
                self.annotations.append(ann)
                self._redo_stack.clear()
                self.toolbar.update_undo_redo_state()
            elif ann["type"] in ("arrow", "line"):
                dx = ann["end"].x() - ann["start"].x()
                dy = ann["end"].y() - ann["start"].y()
                if abs(dx) > MIN_DRAW_THRESHOLD or abs(dy) > MIN_DRAW_THRESHOLD:
                    self.annotations.append(ann)
                    self._redo_stack.clear()
                    self.toolbar.update_undo_redo_state()
        elif self.current_tool == "freehand" and self.annotations and self.annotations[-1]["type"] == "freehand":
            if len(self.annotations[-1]["points"]) < 2:
                self.annotations.pop()
        self._preview_annotation = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._text_editor:
                self._text_editor.hide()
                self._text_editor.deleteLater()
                self._text_editor = None
                self._text_editor_pos = None
                self.grabKeyboard()
                return
            if self._drawing:
                self._drawing = False
                return
            if self.current_tool == "eraser":
                self.toolbar._select_tool("select")
                return
            if not self.selection_rect.isNull():
                self.selection_rect = QRect()
                self._drag_mode = None
                self.annotations.clear()
                self.toolbar.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
            else:
                self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self.selection_rect.isNull():
                self.copy_requested.emit(self._render_annotated_pixmap())
                self.close()

    def closeEvent(self, event):
        logger.debug("关闭截图覆盖层")
        self.releaseKeyboard()
        self.deleteLater()
        super().closeEvent(event)
