import math
from PySide6.QtWidgets import QWidget, QApplication, QToolButton, QFrame, QHBoxLayout, QMenu, QWidgetAction, QLabel, QPushButton, QSpinBox, QVBoxLayout
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont, QCursor, QIcon, QPainterPath, QAction
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, Signal, QSize, QEvent

from .utils import capture_all_screens
from .resources.icons.toolbar_icons import TOOLBAR_ICONS


class CaptureOverlay(QWidget):
    pin_requested = Signal(object, object)
    copy_requested = Signal(object)
    save_requested = Signal(object)

    def __init__(self):
        super().__init__()

        self.total_geometry = QRect()
        for screen in QApplication.screens():
            self.total_geometry = self.total_geometry.united(screen.geometry())

        self.full_screenshot = capture_all_screens()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(self.total_geometry)
        self.setCursor(Qt.CrossCursor)

        self.is_selecting = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selection_rect = QRect()
        self.current_mouse_pos = QPoint()

        self._drag_mode = None
        self._drag_start_global = QPoint()
        self._drag_start_rect = QRect()

        self.current_tool = "select"
        self.current_color = QColor(255, 50, 50)
        self.current_width = 3
        self.annotations = []
        self._drawing = False
        self._draw_start = QPointF()
        self._draw_points = []
        self._preview_annotation = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabKeyboard()

        self._setup_toolbar()

    def _load_icon(self, name, color="#333333"):
        svg = TOOLBAR_ICONS.get(name, "")
        if svg:
            svg_data = svg.replace("currentColor", color)
            renderer = QSvgRenderer(svg_data.encode("utf-8"))
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            renderer.render(p)
            p.end()
            return QIcon(pm)
        return QIcon()

    def _setup_toolbar(self):
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName("overlayToolbar")
        self.toolbar.setStyleSheet("""
            #overlayToolbar { background: white; border: 1px solid #ccc; border-radius: 4px; }
            QToolButton { color: #333; background: transparent; border: none; border-radius: 3px; padding: 2px 4px; margin: 0px; min-width: 18px; min-height: 18px; }
            QToolButton:hover { background: #e8e8e8; }
            QToolButton:checked { background: #d0e4ff; }
        """)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(3, 2, 3, 2)
        toolbar_layout.setSpacing(1)

        def add_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet("color: #ddd; max-width: 1px;")
            sep.setFixedWidth(1)
            toolbar_layout.addWidget(sep)

        def add_menu_btn(icon_name, tooltip, menu_items, default_tool):
            btn = QToolButton()
            btn.setIcon(self._load_icon(icon_name))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(tooltip)
            btn.setPopupMode(QToolButton.InstantPopup)
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setStyleSheet("QToolButton::menu-indicator { image: none; }")
            menu = QMenu(self)
            for item_icon, item_tool in menu_items:
                icn = self._load_icon(item_icon)
                action = QAction(icn, "", self)
                action.setToolTip(item_tool)
                action.triggered.connect(lambda checked, t=item_tool, b=btn, ic=item_icon: self._select_tool(t, b, ic))
                menu.addAction(action)
            btn.setMenu(menu)
            toolbar_layout.addWidget(btn)
            return btn

        self._tool_btns = {}

        # Shape - with submenu
        shape_btn = add_menu_btn("rectangle", "形状（矩形/圆形）", [
            ("rectangle", "rect"),
            ("ellipse", "ellipse"),
        ], "rect")
        self._tool_btns["rect"] = shape_btn
        self._tool_btns["ellipse"] = shape_btn

        # Arrow - with submenu
        arrow_btn = add_menu_btn("arrow", "箭头（有箭头/无箭头）", [
            ("arrow", "arrow"),
            ("line", "line"),
        ], "arrow")
        self._tool_btns["arrow"] = arrow_btn
        self._tool_btns["line"] = arrow_btn

        # Pen - with color & width submenu
        pen_btn = QToolButton()
        pen_btn.setIcon(self._load_icon("pen"))
        pen_btn.setIconSize(QSize(16, 16))
        pen_btn.setToolTip("画笔")
        pen_btn.setPopupMode(QToolButton.InstantPopup)
        pen_btn.setCheckable(True)
        pen_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        pen_btn.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        pen_menu = QMenu(self)

        color_action = QWidgetAction(pen_menu)
        color_widget = QWidget()
        color_layout = QVBoxLayout(color_widget)
        color_layout.setContentsMargins(4, 4, 4, 4)
        color_layout.setSpacing(2)
        color_label = QLabel("颜色")
        color_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
        color_layout.addWidget(color_label)
        color_grid = QWidget()
        grid_layout = QHBoxLayout(color_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(2)
        colors = ["#ff3232", "#ff8c00", "#ffd700", "#32cd32", "#1e90ff", "#8a2be2", "#ffffff", "#000000"]
        for c in colors:
            cb = QPushButton()
            cb.setFixedSize(16, 16)
            cb.setStyleSheet(f"background: {c}; border: 1px solid #ccc; border-radius: 2px;")
            cb.clicked.connect(lambda checked, col=c: self._set_pen_color(col))
            grid_layout.addWidget(cb)
        color_layout.addWidget(color_grid)
        color_action.setDefaultWidget(color_widget)
        pen_menu.addAction(color_action)
        pen_menu.addSeparator()

        width_action = QWidgetAction(pen_menu)
        width_widget = QWidget()
        width_layout = QVBoxLayout(width_widget)
        width_layout.setContentsMargins(4, 4, 4, 4)
        width_layout.setSpacing(2)
        width_label = QLabel("粗细")
        width_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
        width_layout.addWidget(width_label)
        ws = QSpinBox()
        ws.setRange(1, 20)
        ws.setValue(self.current_width)
        ws.setButtonSymbols(QSpinBox.NoButtons)
        ws.valueChanged.connect(lambda v: self._set_width(v))
        width_layout.addWidget(ws)
        width_action.setDefaultWidget(width_widget)
        pen_menu.addAction(width_action)

        pen_btn.setMenu(pen_menu)
        pen_menu.aboutToShow.connect(lambda: self._select_tool("freehand"))
        toolbar_layout.addWidget(pen_btn)
        self._tool_btns["freehand"] = pen_btn

        # Mosaic
        mosaic_btn = QToolButton()
        mosaic_btn.setIcon(self._load_icon("mosaic"))
        mosaic_btn.setIconSize(QSize(16, 16))
        mosaic_btn.setToolTip("马赛克")
        mosaic_btn.setCheckable(True)
        mosaic_btn.clicked.connect(lambda: self._select_tool("mosaic"))
        toolbar_layout.addWidget(mosaic_btn)
        self._tool_btns["mosaic"] = mosaic_btn

        # Text
        text_btn = QToolButton()
        text_btn.setIcon(self._load_icon("text"))
        text_btn.setIconSize(QSize(16, 16))
        text_btn.setToolTip("文字")
        text_btn.setCheckable(True)
        text_btn.clicked.connect(lambda: self._select_tool("text"))
        toolbar_layout.addWidget(text_btn)
        self._tool_btns["text"] = text_btn

        # OCR
        ocr_btn = QToolButton()
        ocr_btn.setText("OCR")
        ocr_btn.setToolTip("文字识别")
        ocr_btn.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        ocr_btn.clicked.connect(self._on_ocr)
        toolbar_layout.addWidget(ocr_btn)

        add_sep()

        undo_btn = QToolButton()
        undo_btn.setIcon(self._load_icon("undo"))
        undo_btn.setIconSize(QSize(16, 16))
        undo_btn.setToolTip("撤销")
        undo_btn.clicked.connect(self._undo)
        toolbar_layout.addWidget(undo_btn)

        redo_btn = QToolButton()
        redo_btn.setIcon(self._load_icon("redo"))
        redo_btn.setIconSize(QSize(16, 16))
        redo_btn.setToolTip("重做")
        redo_btn.clicked.connect(self._redo)
        toolbar_layout.addWidget(redo_btn)

        add_sep()

        pin_btn = QToolButton()
        pin_btn.setIcon(self._load_icon("pin"))
        pin_btn.setIconSize(QSize(16, 16))
        pin_btn.setToolTip("悬浮（钉在桌面上）")
        pin_btn.clicked.connect(self._on_pin)
        toolbar_layout.addWidget(pin_btn)

        copy_btn = QToolButton()
        copy_btn.setIcon(self._load_icon("copy"))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setToolTip("复制到剪贴板")
        copy_btn.clicked.connect(self._on_copy)
        toolbar_layout.addWidget(copy_btn)

        save_btn = QToolButton()
        save_btn.setIcon(self._load_icon("save"))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setToolTip("保存到文件")
        save_btn.clicked.connect(self._on_save)
        toolbar_layout.addWidget(save_btn)

        self.toolbar.hide()
        self.toolbar.installEventFilter(self)
        for child in self.toolbar.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.setCursor(Qt.ArrowCursor)
        elif event.type() == QEvent.Leave:
            if self.selection_rect.isNull():
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        return super().eventFilter(obj, event)

    def _select_tool(self, tool_id, btn=None, icon_name=None):
        self.current_tool = tool_id
        for tid, b in self._tool_btns.items():
            b.setChecked(tid == tool_id)
        if btn:
            btn.setChecked(True)
            if icon_name:
                btn.setIcon(self._load_icon(icon_name))
        if tool_id in ("text",):
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def _set_pen_color(self, color_hex):
        self.current_color = QColor(color_hex)

    def _set_width(self, w):
        self.current_width = w

    def _undo(self):
        if self.annotations:
            self.annotations.pop()
            self.update()

    def _redo(self):
        pass

    def _render_annotated_pixmap(self) -> QPixmap:
        dpr = self.full_screenshot.devicePixelRatio()
        logical_rect = self.selection_rect
        physical_rect = QRect(
            int(logical_rect.x() * dpr), int(logical_rect.y() * dpr),
            int(logical_rect.width() * dpr), int(logical_rect.height() * dpr)
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
            t = ann["type"]
            if t == "rect":
                r = QRectF(ann["rect"]).translated(offset)
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(r)
            elif t == "ellipse":
                r = QRectF(ann["rect"]).translated(offset)
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(r)
            elif t == "arrow":
                start = ann["start"] + offset
                end = ann["end"] + offset
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.drawLine(start, end)
                arrow_size = 10 + ann["width"]
                angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                spread = math.pi / 6
                p1 = end - QPointF(arrow_size * math.cos(angle + spread), arrow_size * math.sin(angle + spread))
                p2 = end - QPointF(arrow_size * math.cos(angle - spread), arrow_size * math.sin(angle - spread))
                painter.drawLine(end, p1)
                painter.drawLine(end, p2)
            elif t == "line":
                start = ann["start"] + offset
                end = ann["end"] + offset
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.drawLine(start, end)
            elif t == "freehand":
                pts = [p + offset for p in ann["points"]]
                if len(pts) >= 2:
                    p = QPen(ann["color"], ann["width"])
                    painter.setPen(p)
                    path = QPainterPath()
                    path.moveTo(pts[0])
                    for pt in pts[1:]:
                        path.lineTo(pt)
                    painter.drawPath(path)
            elif t == "mosaic":
                dpr = self.full_screenshot.devicePixelRatio()
                r = QRectF(ann["rect"]).translated(offset).toRect()
                sel = self.selection_rect
                src_rect = QRect(
                    int((sel.x() + r.x()) * dpr),
                    int((sel.y() + r.y()) * dpr),
                    int(r.width() * dpr),
                    int(r.height() * dpr)
                )
                if src_rect.width() > 0 and src_rect.height() > 0:
                    src = self.full_screenshot.copy(src_rect)
                    small = src.scaled(max(src.width() // 8, 1), max(src.height() // 8, 1), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    blurred = small.scaled(src.width(), src.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
                    painter.drawPixmap(r, blurred, blurred.rect())
            elif t == "text":
                pos = ann["pos"] + offset
                p = QPen(ann["color"])
                painter.setPen(p)
                font = QFont("Segoe UI", ann["font_size"])
                painter.setFont(font)
                painter.drawText(pos.toPoint(), ann["text"])

        if self._preview_annotation:
            ann = self._preview_annotation
            t = ann["type"]
            if t == "rect":
                r = QRectF(ann["rect"]).translated(offset)
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(r)
            elif t == "ellipse":
                r = QRectF(ann["rect"]).translated(offset)
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(r)
            elif t == "arrow":
                start = ann["start"] + offset
                end = ann["end"] + offset
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.drawLine(start, end)
                arrow_size = 10 + ann["width"]
                angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                spread = math.pi / 6
                p1 = end - QPointF(arrow_size * math.cos(angle + spread), arrow_size * math.sin(angle + spread))
                p2 = end - QPointF(arrow_size * math.cos(angle - spread), arrow_size * math.sin(angle - spread))
                painter.drawLine(end, p1)
                painter.drawLine(end, p2)
            elif t == "line":
                start = ann["start"] + offset
                end = ann["end"] + offset
                p = QPen(ann["color"], ann["width"])
                painter.setPen(p)
                painter.drawLine(start, end)
            elif t == "mosaic":
                dpr = self.full_screenshot.devicePixelRatio()
                r = QRectF(ann["rect"]).translated(offset).toRect()
                sel = self.selection_rect
                src_rect = QRect(
                    int((sel.x() + r.x()) * dpr), int((sel.y() + r.y()) * dpr),
                    int(r.width() * dpr), int(r.height() * dpr)
                )
                if src_rect.width() > 0 and src_rect.height() > 0:
                    src = self.full_screenshot.copy(src_rect)
                    small = src.scaled(max(src.width() // 8, 1), max(src.height() // 8, 1), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    blurred = small.scaled(src.width(), src.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
                    painter.drawPixmap(r, blurred, blurred.rect())

    def _on_ocr(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        from .ocr_engine import extract_text
        text = extract_text(captured)
        if text:
            QApplication.clipboard().setText(text)

    def _on_pin(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        self.pin_requested.emit(captured, self._capture_pos())
        self.close()

    def _on_copy(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        self.copy_requested.emit(captured)
        self.close()

    def _on_save(self):
        if self.selection_rect.isNull():
            return
        captured = self._render_annotated_pixmap()
        self.save_requested.emit(captured)

    def _position_toolbar(self):
        rect = self.selection_rect
        if rect.isNull():
            self.toolbar.hide()
            return
        self.toolbar.adjustSize()
        tw = self.toolbar.width()
        th = self.toolbar.height()
        x = rect.right() - tw
        y = rect.bottom() + 8
        if y + th > self.height() - 10:
            y = rect.top() - th - 8
        if x < 10:
            x = rect.left()
        if x + tw > self.width() - 10:
            x = self.width() - tw - 10
        self.toolbar.move(x, y)
        self.toolbar.show()
        self.toolbar.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawPixmap(0, 0, self.full_screenshot)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

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

            pen = QPen(QColor(0, 120, 215), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            handles = self._get_all_handles(rect)
            for h_rect in handles:
                painter.fillRect(h_rect, QColor(0, 120, 215))
                painter.setPen(QPen(Qt.white, 1))
                painter.drawRect(h_rect)

            info_text = f"{rect.width()} x {rect.height()}"
            painter.setPen(Qt.white)
            info_font = QFont("Segoe UI", 12)
            painter.setFont(info_font)

            text_width = painter.fontMetrics().horizontalAdvance(info_text) + 20
            text_height = 28

            text_x = rect.x()
            text_y = rect.bottom() + 8
            if text_y + text_height > self.height() - 10:
                text_y = rect.top() - text_height - 8

            text_bg_rect = QRect(text_x, text_y, text_width, text_height)
            painter.fillRect(text_bg_rect, QColor(0, 0, 0, 180))
            painter.drawText(text_bg_rect, Qt.AlignCenter, info_text)

        if not (self.toolbar.isVisible() and self.toolbar.geometry().contains(self.current_mouse_pos)):
            coord_text = f"{self.current_mouse_pos.x()}, {self.current_mouse_pos.y()}"
            painter.setPen(Qt.white)
            coord_font = QFont("Segoe UI", 11)
            painter.setFont(coord_font)

            cx = self.current_mouse_pos.x()
            cy = self.current_mouse_pos.y()
            coord_w = 130
            coord_h = 24
            coord_rect = QRect(cx + 15, cy + 15, coord_w, coord_h)
            if coord_rect.right() > self.width() - 10:
                coord_rect.moveLeft(cx - coord_w - 15)
            if coord_rect.bottom() > self.height() - 10:
                coord_rect.moveTop(cy - coord_h - 15)

            painter.fillRect(coord_rect, QColor(0, 0, 0, 160))
            painter.drawText(coord_rect, Qt.AlignCenter, coord_text)

    def _get_all_handles(self, rect):
        size = 8
        half = size // 2
        r = rect
        return [
            QRect(r.left() - half, r.top() - half, size, size),
            QRect(r.right() - half, r.top() - half, size, size),
            QRect(r.left() - half, r.bottom() - half, size, size),
            QRect(r.right() - half, r.bottom() - half, size, size),
            QRect(r.center().x() - half, r.top() - half, size, size),
            QRect(r.center().x() - half, r.bottom() - half, size, size),
            QRect(r.left() - half, r.center().y() - half, size, size),
            QRect(r.right() - half, r.center().y() - half, size, size),
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

    def _capture_region(self, logical_rect: QRect) -> QPixmap:
        dpr = self.full_screenshot.devicePixelRatio()
        physical_rect = QRect(
            int(logical_rect.x() * dpr), int(logical_rect.y() * dpr),
            int(logical_rect.width() * dpr), int(logical_rect.height() * dpr)
        )
        captured = self.full_screenshot.copy(physical_rect)
        captured.setDevicePixelRatio(dpr)
        return captured

    def _capture_pos(self):
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

    def _sel_to_local(self, pos):
        return QPointF(pos - self.selection_rect.topLeft())

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self._drag_mode or not self.selection_rect.isNull():
                self.selection_rect = QRect()
                self._drag_mode = None
                self.annotations.clear()
                self.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
                return
            self.close()
            return
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if not self.selection_rect.isNull() and self.current_tool != "select":
                local = self._sel_to_local(QPointF(pos))
                self._drawing = True
                self._draw_start = local
                self._draw_points = [local]
                if self.current_tool == "text":
                    from PySide6.QtWidgets import QInputDialog
                    text, ok = QInputDialog.getText(None, "输入文字", "请输入文字:")
                    if ok and text:
                        self.annotations.append({
                            "type": "text",
                            "pos": local,
                            "text": text,
                            "color": QColor(self.current_color),
                            "font_size": 20,
                        })
                        self.update()
                    self._drawing = False
                return
            if not self.selection_rect.isNull():
                handle = self._handle_at_pos(pos)
                if handle:
                    self._drag_mode = ("resize", handle)
                    self._drag_start_global = event.globalPosition().toPoint()
                    self._drag_start_rect = QRect(self.selection_rect)
                    return
                if self.selection_rect.contains(pos):
                    self._drag_mode = ("move",)
                    self._drag_start_global = event.globalPosition().toPoint()
                    self._drag_start_rect = QRect(self.selection_rect)
                    return
            self.is_selecting = True
            self.toolbar.hide()
            self.annotations.clear()
            self.start_point = pos
            self.end_point = self.start_point
            self.selection_rect = QRect()
            self.current_tool = "select"
            for btn in self._tool_btns.values():
                btn.setChecked(False)
            self.update()

    def mouseMoveEvent(self, event):
        self.current_mouse_pos = event.position().toPoint()
        if self._drawing:
            local = self._sel_to_local(QPointF(self.current_mouse_pos))
            if self.current_tool == "freehand":
                self._draw_points.append(local)
                if self.annotations and self.annotations[-1]["type"] == "freehand":
                    self.annotations[-1]["points"] = list(self._draw_points)
                else:
                    self.annotations.append({
                        "type": "freehand",
                        "points": list(self._draw_points),
                        "color": QColor(self.current_color),
                        "width": self.current_width,
                    })
                self.update()
            else:
                dx = local.x() - self._draw_start.x()
                dy = local.y() - self._draw_start.y()
                if self.current_tool in ("rect", "ellipse"):
                    r = QRectF(self._draw_start, local).normalized()
                    self._preview_annotation = {
                        "type": self.current_tool,
                        "rect": r,
                        "color": QColor(self.current_color),
                        "width": self.current_width,
                    }
                elif self.current_tool in ("arrow", "line"):
                    if abs(dx) > 3 or abs(dy) > 3:
                        self._preview_annotation = {
                            "type": self.current_tool,
                            "start": QPointF(self._draw_start),
                            "end": QPointF(local),
                            "color": QColor(self.current_color),
                            "width": self.current_width,
                        }
                elif self.current_tool == "mosaic":
                    r = QRectF(self._draw_start, local).normalized()
                    if r.width() > 3 and r.height() > 3:
                        self._preview_annotation = {
                            "type": "mosaic",
                            "rect": r,
                        }
                self.update()
            return
        if self._drag_mode:
            delta = event.globalPosition().toPoint() - self._drag_start_global
            mode = self._drag_mode[0]
            if mode == "move":
                self.selection_rect = self._drag_start_rect.translated(delta)
                self._position_toolbar()
                self.update()
            elif mode == "resize":
                handle = self._drag_mode[1]
                r = QRect(self._drag_start_rect)
                if "left" in handle:
                    r.setLeft(self._drag_start_rect.left() + delta.x())
                if "right" in handle:
                    r.setRight(self._drag_start_rect.right() + delta.x())
                if "top" in handle:
                    r.setTop(self._drag_start_rect.top() + delta.y())
                if "bottom" in handle:
                    r.setBottom(self._drag_start_rect.bottom() + delta.y())
                self.selection_rect = r.normalized()
                self._position_toolbar()
                self.update()
            return
        if self.is_selecting:
            self.end_point = self.current_mouse_pos
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
        else:
            if not self.selection_rect.isNull():
                handle = self._handle_at_pos(self.current_mouse_pos)
                self.setCursor(self._cursor_for_handle(handle))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drawing:
                self._drawing = False
                if self._preview_annotation and self._preview_annotation["type"] != "freehand":
                    ann = self._preview_annotation
                    if ann["type"] in ("rect", "ellipse", "mosaic"):
                        if ann["rect"].width() > 3 and ann["rect"].height() > 3:
                            self.annotations.append(ann)
                    elif ann["type"] in ("arrow", "line"):
                        dx = ann["end"].x() - ann["start"].x()
                        dy = ann["end"].y() - ann["start"].y()
                        if abs(dx) > 3 or abs(dy) > 3:
                            self.annotations.append(ann)
                elif self.current_tool == "freehand":
                    if self.annotations and self.annotations[-1]["type"] == "freehand":
                        pts = self.annotations[-1]["points"]
                        if len(pts) < 2:
                            self.annotations.pop()
                self._preview_annotation = None
                self.update()
                return
            if self._drag_mode:
                self._drag_mode = None
                self._position_toolbar()
                return
            if self.is_selecting:
                self.is_selecting = False
                if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                    self._position_toolbar()
                else:
                    self.selection_rect = QRect()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._drawing:
                self._drawing = False
                return
            if not self.selection_rect.isNull():
                self.selection_rect = QRect()
                self._drag_mode = None
                self.annotations.clear()
                self.toolbar.hide()
                self.setCursor(Qt.CrossCursor)
                self.update()
            else:
                self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self.selection_rect.isNull():
                captured = self._render_annotated_pixmap()
                self.copy_requested.emit(captured)
                self.close()

    def closeEvent(self, event):
        self.releaseKeyboard()
        self.deleteLater()
        super().closeEvent(event)
