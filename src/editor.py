from __future__ import annotations

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QColorDialog,
    QSpinBox, QFileDialog, QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem,
    QGraphicsItem, QSizePolicy, QToolButton, QFrame, QMessageBox, QLabel,
    QGraphicsDropShadowEffect, QMenu, QWidgetAction,
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QFont, QIcon, QAction,
    QPainterPath, QPolygonF, QFontDatabase, QKeySequence,
    QClipboard, QBrush,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QLineF, QTimer, QEvent, QRect, QSize
from PySide6.QtSvg import QSvgRenderer

from .ocr_engine import extract_text
from .resources.icons.toolbar_icons import TOOLBAR_ICONS

class ArrowItem(QGraphicsLineItem):
    def __init__(self, start: QPointF, end: QPointF, color: QColor = QColor(255, 0, 0), width: float = 3):
        super().__init__()
        self.start = start
        self.end = end
        self.arrow_color = color
        self.arrow_width = width
        self.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setLine(QLineF(start, end))

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)

        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        angle = math.atan2(dy, dx)
        arrow_size = 12 + self.arrow_width * 2

        p1 = QPointF(
            self.end.x() - arrow_size * math.cos(angle - math.pi / 6),
            self.end.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            self.end.x() - arrow_size * math.cos(angle + math.pi / 6),
            self.end.y() - arrow_size * math.sin(angle + math.pi / 6),
        )

        painter.setBrush(self.arrow_color)
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygonF([self.end, p1, p2]))


class MosaicItem(QGraphicsRectItem):
    def __init__(self, source_pixmap: QPixmap, rect: QRectF, block_size: int = 8):
        super().__init__(rect)
        self.source_pixmap = source_pixmap
        self.block_size = block_size
        self.setPen(Qt.NoPen)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def paint(self, painter, option, widget):
        r = self.rect().toRect()
        if r.isEmpty():
            return

        dpr = self.source_pixmap.devicePixelRatio()
        src_rect = QRect(
            int(r.x() * dpr), int(r.y() * dpr),
            int(r.width() * dpr), int(r.height() * dpr),
        )

        section = self.source_pixmap.copy(src_rect)
        w = section.width()
        h = section.height()
        bs = max(1, self.block_size)
        small = section.scaled(
            max(1, w // bs), max(1, h // bs),
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
        )
        pixelated = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pixelated.setDevicePixelRatio(dpr)
        painter.drawPixmap(self.rect().topLeft(), pixelated)


class AnnotationView(QGraphicsView):
    annotation_added = Signal(object)

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setInteractive(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QGraphicsView { border: none; background: #2d2d2d; }")

        self.current_tool = "select"
        self.current_color = QColor(255, 50, 50)
        self.current_width = 3
        self.current_fill = Qt.transparent
        self.source_pixmap = None

        self.drawing_item = None
        self.start_point = QPointF()
        self.text_item = None

    def set_tool(self, tool: str):
        self.current_tool = tool
        if tool == "select":
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setInteractive(True)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setInteractive(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.current_tool != "select":
            self.start_point = self.mapToScene(event.pos())
            scene = self.scene()

            if self.current_tool == "rect":
                item = QGraphicsRectItem()
                item.setPen(QPen(self.current_color, self.current_width))
                if self.current_fill != Qt.transparent:
                    item.setBrush(QBrush(self.current_fill))
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "ellipse":
                item = QGraphicsEllipseItem()
                item.setPen(QPen(self.current_color, self.current_width))
                if self.current_fill != Qt.transparent:
                    item.setBrush(QBrush(self.current_fill))
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "line":
                item = QGraphicsLineItem()
                item.setPen(QPen(self.current_color, self.current_width,
                                 Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "arrow":
                self.drawing_item = {"start": self.start_point, "end": self.start_point}

            elif self.current_tool == "freehand":
                path = QPainterPath()
                path.moveTo(self.start_point)
                item = QGraphicsPathItem()
                item.setPath(path)
                item.setPen(QPen(self.current_color, self.current_width,
                                 Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "mosaic":
                item = QGraphicsRectItem()
                item.setPen(QPen(QColor(128, 128, 128, 200), 1, Qt.DashLine))
                scene.addItem(item)
                self.drawing_item = item

            elif self.current_tool == "text":
                item = QGraphicsTextItem()
                item.setDefaultTextColor(self.current_color)
                font = QFont("Segoe UI", 14)
                item.setFont(font)
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                item.setPos(self.start_point)
                scene.addItem(item)
                item.setPlainText("文字")
                item.setTextInteractionFlags(Qt.TextEditorInteraction)
                scene.setFocusItem(item)
                self.text_item = item
                self.annotation_added.emit(item)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_item and self.current_tool not in ("select", "arrow", "mosaic", "text"):
            pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_point, pos).normalized()

            if self.current_tool == "rect":
                if isinstance(self.drawing_item, QGraphicsRectItem):
                    self.drawing_item.setRect(rect)
            elif self.current_tool == "ellipse":
                if isinstance(self.drawing_item, QGraphicsEllipseItem):
                    self.drawing_item.setRect(rect)
            elif self.current_tool == "line":
                if isinstance(self.drawing_item, QGraphicsLineItem):
                    self.drawing_item.setLine(QLineF(self.start_point, pos))
            elif self.current_tool == "freehand":
                if isinstance(self.drawing_item, QGraphicsPathItem):
                    path = self.drawing_item.path()
                    path.lineTo(pos)
                    self.drawing_item.setPath(path)
        elif self.drawing_item and self.current_tool == "arrow":
            pos = self.mapToScene(event.pos())
            self.drawing_item["end"] = pos
        elif self.current_tool == "mosaic" and isinstance(self.drawing_item, QGraphicsRectItem):
            pos = self.mapToScene(event.pos())
            self.drawing_item.setRect(QRectF(self.start_point, pos).normalized())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.current_tool == "arrow" and self.drawing_item:
                pos = self.mapToScene(event.pos())
                item = ArrowItem(self.drawing_item["start"], pos,
                                 self.current_color, self.current_width)
                item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                item.setFlag(QGraphicsItem.ItemIsMovable, True)
                self.scene().addItem(item)
                self.drawing_item = None
                self.annotation_added.emit(item)

            elif self.current_tool == "text":
                pass

            elif self.current_tool == "mosaic" and self.drawing_item:
                pos = self.mapToScene(event.pos())
                mosaic_rect = QRectF(self.start_point, pos).normalized()
                # Remove preview rect
                self.scene().removeItem(self.drawing_item)
                self.drawing_item = None
                if mosaic_rect.width() > 5 and mosaic_rect.height() > 5 and self.source_pixmap:
                    item = MosaicItem(self.source_pixmap, mosaic_rect)
                    item.setFlag(QGraphicsItem.ItemIsSelectable, True)
                    item.setFlag(QGraphicsItem.ItemIsMovable, True)
                    self.scene().addItem(item)
                    self.annotation_added.emit(item)

            elif self.drawing_item and self.current_tool not in ("select",):
                item = self.drawing_item
                self.drawing_item = None
                self.annotation_added.emit(item)
            else:
                super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            scale_factor = 1.15
            if event.angleDelta().y() > 0:
                self.scale(scale_factor, scale_factor)
            else:
                self.scale(1 / scale_factor, 1 / scale_factor)
        else:
            super().wheelEvent(event)


class EditorWindow(QWidget):
    def __init__(self, pixmap: QPixmap, capture_pos=None):
        super().__init__()
        self.captured_pixmap = pixmap
        self.ocr_text = ""

        # 无边框窗口，保持在最上层
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("MySnipaste - 编辑器")

        screen = QApplication.primaryScreen().availableGeometry()
        max_w = screen.width() - 20
        max_h = screen.height() - 20
        self.setMinimumSize(100, 100)

        # 计算窗口尺寸（考虑 DPR）
        dpr = pixmap.devicePixelRatio()
        logical_width = int(pixmap.width() / dpr)
        logical_height = int(pixmap.height() / dpr)

        self.resize(
            min(logical_width, max_w),
            min(logical_height, max_h),
        )

        if capture_pos is not None:
            self.move(capture_pos.x(), capture_pos.y())
        else:
            self.move(
                (screen.width() - self.width()) // 2,
                (screen.height() - self.height()) // 2,
            )

        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem(self.captured_pixmap)
        self.pixmap_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.pixmap_item.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.scene.addItem(self.pixmap_item)

        border = QGraphicsRectItem(self.pixmap_item.boundingRect())
        border.setPen(QPen(QColor(10, 125, 255, 80), 2))
        border.setBrush(Qt.NoBrush)
        self.scene.addItem(border)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 2)
        self.pixmap_item.setGraphicsEffect(shadow)

        self.view = AnnotationView(self.scene)
        self.view.source_pixmap = self.captured_pixmap
        self.view.current_color = QColor(255, 50, 50)
        self.view.current_width = 3

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("floatingToolbar")
        toolbar.setFixedHeight(28)
        toolbar.setStyleSheet("""
            #floatingToolbar {
                background: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QToolButton {
                color: #333;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 1px 2px;
                margin: 0px;
                min-width: 18px;
                min-height: 18px;
            }
            QToolButton:hover {
                background: #e8e8e8;
                border-color: #ccc;
            }
            QToolButton:checked {
                background: #d0e4ff;
                color: #1a73e8;
            }

            QSpinBox {
                background: transparent;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px;
                font-size: 11px;
                max-width: 45px;
                min-height: 22px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(1, 1, 1, 1)
        toolbar_layout.setSpacing(0)

        self.tool_buttons = {}
        self._tool_group_map = {}  # maps sub-tool -> group button

        def _load_icon(name, color="#333333"):
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

        def _make_tool_btn(text, tooltip, tool_id, icon_name=None, checkable=True):
            btn = QToolButton()
            if icon_name:
                btn.setIcon(_load_icon(icon_name))
            else:
                btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setIconSize(QSize(16, 16))
            if checkable:
                btn.setCheckable(True)
            btn.clicked.connect(lambda: self._on_tool_selected(tool_id))
            self.tool_buttons[tool_id] = btn
            toolbar_layout.addWidget(btn)
            return btn

        def _make_menu_btn(text, tooltip, menu_items, default_tool, icon_name=None):
            btn = QToolButton()
            if icon_name:
                btn.setIcon(_load_icon(icon_name))
            else:
                btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setIconSize(QSize(16, 16))
            btn.setPopupMode(QToolButton.MenuButtonPopup)
            btn.setCheckable(True)

            menu = QMenu(self)
            for item_text, item_tool in menu_items:
                icn = _load_icon(icon_name or item_tool)
                action = QAction(icn, item_text, self)
                action.triggered.connect(lambda checked, t=item_tool, b=btn, txt=item_text: self._on_menu_tool(t, b, txt))
                menu.addAction(action)
                self._tool_group_map[item_tool] = btn
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setMenu(menu)

            first_action = menu.actions()[0]
            btn.setDefaultAction(first_action)
            self.tool_buttons[default_tool] = btn
            toolbar_layout.addWidget(btn)
            return btn

        # Shape - with submenu
        _make_menu_btn("", "形状（矩形/圆形）", [
            ("▭ 矩形", "rect"),
            ("○ 圆形", "ellipse"),
        ], "rect", "rectangle")

        # Arrow - with submenu
        _make_menu_btn("", "箭头（有箭头/无箭头）", [
            ("➜ 有箭头", "arrow"),
            ("─ 无箭头", "line"),
        ], "arrow", "arrow")

        # Pen - with color & width submenu
        pen_btn = QToolButton()
        pen_btn.setIcon(_load_icon("pen"))
        pen_btn.setIconSize(QSize(16, 16))
        pen_btn.setToolTip("画笔")
        pen_btn.setPopupMode(QToolButton.MenuButtonPopup)
        pen_btn.setCheckable(True)
        pen_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

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
            cb.setFixedSize(18, 18)
            cb.setStyleSheet(
                f"background: {c}; border: 1px solid #ccc; border-radius: 2px;"
            )
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
        ws.setValue(self.view.current_width)
        ws.setButtonSymbols(QSpinBox.NoButtons)
        ws.valueChanged.connect(lambda v: setattr(self.view, 'current_width', v))
        width_layout.addWidget(ws)
        width_action.setDefaultWidget(width_widget)
        pen_menu.addAction(width_action)

        pen_btn.setMenu(pen_menu)
        pen_btn.clicked.connect(lambda: self._on_tool_selected("freehand"))
        self.tool_buttons["freehand"] = pen_btn
        toolbar_layout.addWidget(pen_btn)

        # Mosaic
        _make_tool_btn("", "马赛克", "mosaic", "mosaic")

        # Text
        _make_tool_btn("", "文字", "text", "text")

        # OCR
        ocr_btn = QToolButton()
        ocr_btn.setText("OCR")
        ocr_btn.setToolTip("文字识别")
        ocr_btn.clicked.connect(self._do_ocr)
        toolbar_layout.addWidget(ocr_btn)

        toolbar_layout.addWidget(self._make_separator())

        self.undo_btn = QToolButton()
        self.undo_btn.setIcon(_load_icon("undo"))
        self.undo_btn.setIconSize(QSize(16, 16))
        self.undo_btn.setToolTip("撤销")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo)
        toolbar_layout.addWidget(self.undo_btn)

        self.redo_btn = QToolButton()
        self.redo_btn.setIcon(_load_icon("redo"))
        self.redo_btn.setIconSize(QSize(16, 16))
        self.redo_btn.setToolTip("反向撤销")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._redo)
        toolbar_layout.addWidget(self.redo_btn)

        toolbar_layout.addWidget(self._make_separator())

        cancel_btn = QToolButton()
        cancel_btn.setObjectName("closeBtn")
        cancel_btn.setIcon(_load_icon("close"))
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.setToolTip("取消（退出截图）")
        cancel_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(cancel_btn)

        pin_btn = QToolButton()
        pin_btn.setObjectName("pinBtn")
        pin_btn.setIcon(_load_icon("pin"))
        pin_btn.setIconSize(QSize(16, 16))
        pin_btn.setToolTip("悬浮（钉在桌面上）")
        pin_btn.clicked.connect(self._pin)
        toolbar_layout.addWidget(pin_btn)

        save_btn = QToolButton()
        save_btn.setObjectName("saveBtn")
        save_btn.setIcon(_load_icon("save"))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setToolTip("保存到文件")
        save_btn.clicked.connect(self._save_to_file)
        toolbar_layout.addWidget(save_btn)

        copy_btn = QToolButton()
        copy_btn.setIcon(_load_icon("copy"))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setToolTip("复制到剪贴板")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        toolbar_layout.addWidget(copy_btn)

        self.toolbar = toolbar

        self.toolbar.updateGeometry()
        QApplication.processEvents()
        toolbar_width = self.toolbar.sizeHint().width()
        self.toolbar.setFixedWidth(max(toolbar_width + 10, 480))

        self.view.annotation_added.connect(self._on_annotation_changed)
        layout.addWidget(self.view)

        self.undo_stack = []
        self.redo_stack = []
        self._window_dragging = False

        self.view.viewport().installEventFilter(self)

        self._position_toolbar()

        self.fit_in_view()

    def _position_toolbar(self):
        """工具栏作为独立窗口，右边界与截图右下角对齐（下方右对齐）"""
        self.toolbar.setParent(None)
        self.toolbar.setWindowFlags(
            Qt.ToolTip |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        window_rect = self.frameGeometry()
        x = window_rect.right() - self.toolbar.width()
        y = window_rect.bottom() + 8
        self.toolbar.move(x, y)
        self.toolbar.show()
        self.toolbar.raise_()

        self.toolbar.installEventFilter(self)
        for child in self.toolbar.findChildren(QWidget):
            child.installEventFilter(self)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(2, 2)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.toolbar.setGraphicsEffect(shadow)

    def _update_toolbar_position(self):
        """更新工具栏位置：右边界对齐截图右下角"""
        if self.toolbar.parent() is not None:
            return
        window_rect = self.frameGeometry()
        x = window_rect.right() - self.toolbar.width()
        y = window_rect.bottom() + 8
        self.toolbar.move(x, y)

    def _get_tool_name(self, tool_id: str) -> str:
        names = {
            "select": "选择",
            "rect": "矩形",
            "ellipse": "圆形",
            "arrow": "有箭头",
            "line": "无箭头",
            "freehand": "画笔",
            "mosaic": "马赛克",
            "text": "文字",
        }
        return names.get(tool_id, tool_id)

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #555;")
        sep.setFixedWidth(1)
        return sep

    def _on_menu_tool(self, tool: str, btn: QToolButton, text: str):
        """Handle selection from a menu button (shape/arrow)"""
        btn.setText(text.split(" ")[0] if " " in text else text)
        btn.setChecked(True)
        self.view.set_tool(tool)

    def _on_tool_selected(self, tool: str):
        self.view.set_tool(tool)
        for tid, btn in self.tool_buttons.items():
            if tid == tool:
                btn.setChecked(True)
            elif btn not in self._tool_group_map.values():
                btn.setChecked(False)
        # Check parent group button if applicable
        for parent_tool, group_btn in self._tool_group_map.items():
            group_btn.setChecked(False)
        if tool in self._tool_group_map:
            self._tool_group_map[tool].setChecked(True)

    def _set_pen_color(self, color_hex: str):
        self.view.current_color = QColor(color_hex)



    def eventFilter(self, obj, event):
        if obj is self.view.viewport():
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.close()
                return True

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._press_pos = event.globalPosition().toPoint()
                self._window_dragging = False
                return False

            elif event.type() == QEvent.MouseMove and event.buttons() == Qt.LeftButton:
                if self._window_dragging:
                    delta = event.globalPosition().toPoint() - self._drag_start_global
                    self.move(self._drag_start_window + delta)
                    return True

                if self.view.current_tool == "select":
                    distance = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
                    if distance > 10:
                        self._window_dragging = True
                        self._drag_start_global = self._press_pos
                        self._drag_start_window = self.pos()
                        self.toolbar.hide()
                return False

            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._window_dragging:
                    self._window_dragging = False
                    self.toolbar.show()
                    return True
                return False

            return False
        return super().eventFilter(obj, event)

    def _on_annotation_changed(self, item):
        if item is None:
            return
        self.undo_stack.append(item)
        self.redo_stack.clear()
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(False)

    def _undo(self):
        if not self.undo_stack:
            return
        item = self.undo_stack.pop()
        item.setVisible(False)
        self.redo_stack.append(item)
        self.undo_btn.setEnabled(len(self.undo_stack) > 0)
        self.redo_btn.setEnabled(True)
        self.scene.update()

    def _redo(self):
        if not self.redo_stack:
            return
        item = self.redo_stack.pop()
        item.setVisible(True)
        self.undo_stack.append(item)
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(len(self.redo_stack) > 0)
        self.scene.update()

    def _get_image_with_annotations(self) -> QPixmap:
        rect = self.scene.sceneRect()
        dpr = self.captured_pixmap.devicePixelRatio()
        phys_w = int(rect.width() * dpr)
        phys_h = int(rect.height() * dpr)
        pixmap = QPixmap(phys_w, phys_h)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        self.scene.render(painter, QRectF(0, 0, phys_w, phys_h), rect)
        painter.end()
        return pixmap

    def _do_ocr(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout

        self.ocr_text = extract_text(self.captured_pixmap)

        dialog = QDialog(self)
        dialog.setWindowTitle("OCR 结果")
        dialog.setMinimumSize(500, 300)

        dlg_layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(self.ocr_text if self.ocr_text else "(未检测到文字)")
        text_edit.setReadOnly(False)
        dlg_layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("复制到剪贴板")
        copy_btn.clicked.connect(lambda: self._copy_text(text_edit.toPlainText()))
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)

        dlg_layout.addLayout(btn_layout)
        dialog.exec()

    def _pin(self):
        self.toolbar.hide()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.show()

    def _copy_text(self, text: str):
        QApplication.clipboard().setText(text)

    def _copy_to_clipboard(self):
        pixmap = self._get_image_with_annotations()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
self, "保存截图", "截图.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*)",
        )
        if file_path:
            pixmap = self._get_image_with_annotations()
            pixmap.save(file_path)

    def fit_in_view(self):
        """调整视图以显示完整截图，但不放大"""
        scene_rect = self.scene.sceneRect()
        view_rect = self.view.viewport().rect()

        # 计算缩放比例
        x_ratio = view_rect.width() / scene_rect.width()
        y_ratio = view_rect.height() / scene_rect.height()
        ratio = min(x_ratio, y_ratio)

        # 只缩小不放大：如果计算出的比例 > 1，使用 1（原始尺寸）
        if ratio > 1.0:
            ratio = 1.0

        # 应用缩放
        self.view.resetTransform()
        self.view.scale(ratio, ratio)
        self.view.centerOn(self.pixmap_item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_toolbar_position()
        QTimer.singleShot(50, self.fit_in_view)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._update_toolbar_position()

    def closeEvent(self, event):
        if self.toolbar.parent() is None:
            self.toolbar.close()
        super().closeEvent(event)

