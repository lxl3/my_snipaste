import math
from PySide6.QtWidgets import QWidget, QApplication, QToolButton, QFrame, QHBoxLayout, QMenu, QWidgetAction, QLabel, QPushButton, QSpinBox, QVBoxLayout, QLineEdit
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
        self._drag_start_pos = QPointF()
        self._drag_start_rect = QRect()

        self.current_tool = "select"
        self.current_color = QColor(255, 50, 50)
        self.current_width = 3
        self.annotations = []
        self._redo_stack = []  # 用于存储被撤销的操作
        self._drawing = False
        self._draw_start = QPointF()
        self._draw_points = []
        self._preview_annotation = None

        # 保存画笔菜单控件的引用，用于更新状态
        self._color_buttons = []
        self._width_spinbox = None

        # 文本输入控件
        self._text_editor = None
        self._text_editor_pos = None

        # 文本样式设置
        self.text_font_family = "Segoe UI"
        self.text_font_size = 20
        self.text_bold = False
        self.text_italic = False
        self.text_color = QColor(255, 50, 50)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabKeyboard()

        self._setup_toolbar()

    def _load_icon(self, name, color="#333333"):
        svg = TOOLBAR_ICONS.get(name, "")
        if svg:
            svg_data = svg.replace("currentColor", color)
            renderer = QSvgRenderer(svg_data.encode("utf-8"))
            # 使用更高分辨率（48x48）以支持高DPI显示
            size = 48
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            # 启用抗锯齿以获得更清晰的渲染效果
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            renderer.render(p)
            p.end()
            # 设置设备像素比，让Qt自动处理DPI缩放
            dpr = QApplication.primaryScreen().devicePixelRatio()
            pm.setDevicePixelRatio(dpr)
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

            # 使用水平布局的容器
            widget_action = QWidgetAction(menu)
            container = QWidget()
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(4, 4, 4, 4)
            h_layout.setSpacing(4)

            # 为每个菜单项创建按钮并横向排列
            for item_icon, item_tool in menu_items:
                tool_btn = QToolButton()
                tool_btn.setIcon(self._load_icon(item_icon))
                tool_btn.setIconSize(QSize(18, 18))
                tool_btn.setToolTip(item_tool)
                tool_btn.setCheckable(True)
                tool_btn.setProperty("tool_type", item_tool)  # 保存工具类型
                tool_btn.setStyleSheet("""
                    QToolButton {
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        padding: 1px;
                        background: white;
                    }
                    QToolButton:hover { background: #e8e8e8; }
                    QToolButton:checked {
                        background: #d0e4ff;
                        border: 2px solid #0078d4;
                    }
                """)
                tool_btn.clicked.connect(lambda checked, t=item_tool, b=btn, ic=item_icon, menu_obj=menu:
                    self._toggle_or_select_tool(t, b, ic, menu_obj)
                )
                h_layout.addWidget(tool_btn)

            widget_action.setDefaultWidget(container)
            menu.addAction(widget_action)
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
        # 添加再次点击取消功能
        shape_menu = shape_btn.menu()
        shape_menu.aboutToShow.connect(lambda: self._check_and_cancel_tool(["rect", "ellipse"], shape_menu))

        # Arrow - with submenu
        arrow_btn = add_menu_btn("arrow", "箭头（有箭头/无箭头）", [
            ("arrow", "arrow"),
            ("line", "line"),
        ], "arrow")
        self._tool_btns["arrow"] = arrow_btn
        self._tool_btns["line"] = arrow_btn
        # 添加再次点击取消功能
        arrow_menu = arrow_btn.menu()
        arrow_menu.aboutToShow.connect(lambda: self._check_and_cancel_tool(["arrow", "line"], arrow_menu))

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

        # 使用水平布局的容器
        pen_action = QWidgetAction(pen_menu)
        pen_container = QWidget()
        container_layout = QHBoxLayout(pen_container)
        container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.setSpacing(8)

        # 颜色部分（垂直布局内容）
        color_widget = QWidget()
        color_layout = QVBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(2)
        color_label = QLabel("颜色")
        color_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
        color_layout.addWidget(color_label)
        color_grid = QWidget()
        grid_layout = QHBoxLayout(color_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(2)
        colors = ["#ff3232", "#ff8c00", "#ffd700", "#32cd32", "#1e90ff", "#8a2be2", "#ffffff", "#000000"]
        self._color_buttons = []
        for c in colors:
            cb = QPushButton()
            cb.setFixedSize(16, 16)
            cb.setProperty("color", c)  # 保存颜色值
            # 检查是否是当前颜色
            is_current = (c.lower() == self.current_color.name().lower())
            border = "2px solid #0078d4" if is_current else "1px solid #ccc"
            cb.setStyleSheet(f"background: {c}; border: {border}; border-radius: 2px;")
            cb.clicked.connect(lambda checked, col=c, btn=cb: self._set_pen_color(col, btn))
            grid_layout.addWidget(cb)
            self._color_buttons.append(cb)
        color_layout.addWidget(color_grid)

        # 粗细部分（垂直布局内容）
        width_widget = QWidget()
        width_layout = QVBoxLayout(width_widget)
        width_layout.setContentsMargins(0, 0, 0, 0)
        width_layout.setSpacing(2)
        width_label = QLabel("粗细")
        width_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
        width_layout.addWidget(width_label)
        self._width_spinbox = QSpinBox()
        self._width_spinbox.setRange(1, 20)
        self._width_spinbox.setValue(self.current_width)
        self._width_spinbox.setButtonSymbols(QSpinBox.UpDownArrows)
        self._width_spinbox.valueChanged.connect(lambda v: self._set_width(v))
        width_layout.addWidget(self._width_spinbox)

        # 添加到水平容器
        container_layout.addWidget(color_widget)
        container_layout.addWidget(width_widget)

        pen_action.setDefaultWidget(pen_container)
        pen_menu.addAction(pen_action)

        pen_btn.setMenu(pen_menu)
        pen_menu.aboutToShow.connect(lambda: self._check_and_cancel_tool(["freehand"], pen_menu) or self._select_tool("freehand"))
        toolbar_layout.addWidget(pen_btn)
        self._tool_btns["freehand"] = pen_btn

        # Mosaic
        mosaic_btn = QToolButton()
        mosaic_btn.setIcon(self._load_icon("mosaic"))
        mosaic_btn.setIconSize(QSize(16, 16))
        mosaic_btn.setToolTip("马赛克")
        mosaic_btn.setCheckable(True)
        mosaic_btn.clicked.connect(lambda: self._toggle_tool("mosaic"))
        toolbar_layout.addWidget(mosaic_btn)
        self._tool_btns["mosaic"] = mosaic_btn

        # Text
        # Text - with font options submenu
        text_btn = QToolButton()
        text_btn.setIcon(self._load_icon("text"))
        text_btn.setIconSize(QSize(16, 16))
        text_btn.setToolTip("文字")
        text_btn.setCheckable(True)
        text_btn.setPopupMode(QToolButton.InstantPopup)
        text_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        text_btn.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        text_menu = QMenu(self)

        # 文字菜单的水平布局容器
        text_action = QWidgetAction(text_menu)
        text_container = QWidget()
        text_main_layout = QHBoxLayout(text_container)
        text_main_layout.setContentsMargins(6, 6, 6, 6)
        text_main_layout.setSpacing(6)
        text_main_layout.setAlignment(Qt.AlignCenter)

        # 字体选择
        from PySide6.QtWidgets import QComboBox
        self._font_combo = QComboBox()
        self._font_combo.addItems(["Segoe UI", "Arial", "微软雅黑", "宋体", "黑体", "楷体"])
        self._font_combo.setCurrentText(self.text_font_family)
        self._font_combo.setFixedWidth(100)
        self._font_combo.currentTextChanged.connect(self._set_text_font)
        text_main_layout.addWidget(self._font_combo)

        # 字号
        self._font_size_spinbox = QSpinBox()
        self._font_size_spinbox.setRange(8, 72)
        self._font_size_spinbox.setValue(self.text_font_size)
        self._font_size_spinbox.setFixedWidth(100)
        self._font_size_spinbox.setButtonSymbols(QSpinBox.UpDownArrows)
        self._font_size_spinbox.valueChanged.connect(self._set_text_size)
        text_main_layout.addWidget(self._font_size_spinbox)

        # 样式按钮（加粗、斜体）
        self._bold_btn = QPushButton("B")
        self._bold_btn.setFixedSize(20, 20)
        self._bold_btn.setCheckable(True)
        self._bold_btn.setStyleSheet("""
            QPushButton { font-weight: bold; border: 1px solid #ccc; border-radius: 2px; background: white; }
            QPushButton:hover { background: #e8e8e8; }
            QPushButton:checked { background: #d0e4ff; border: 2px solid #0078d4; }
        """)
        self._bold_btn.clicked.connect(self._toggle_bold)
        text_main_layout.addWidget(self._bold_btn)

        self._italic_btn = QPushButton("I")
        self._italic_btn.setFixedSize(20, 20)
        self._italic_btn.setCheckable(True)
        self._italic_btn.setStyleSheet("""
            QPushButton { font-style: italic; border: 1px solid #ccc; border-radius: 2px; background: white; }
            QPushButton:hover { background: #e8e8e8; }
            QPushButton:checked { background: #d0e4ff; border: 2px solid #0078d4; }
        """)
        self._italic_btn.clicked.connect(self._toggle_italic)
        text_main_layout.addWidget(self._italic_btn)

        # 取色器按钮（放在最前面）
        from PySide6.QtWidgets import QColorDialog
        color_picker_btn = QPushButton("🎨")
        color_picker_btn.setFixedSize(20, 20)
        color_picker_btn.setStyleSheet("""
            QPushButton { border: 1px solid #ccc; border-radius: 2px; background: white; font-size: 14px; }
            QPushButton:hover { background: #e8e8e8; }
        """)
        color_picker_btn.clicked.connect(self._open_color_picker)
        text_main_layout.addWidget(color_picker_btn)

        # 颜色选择（分成两排，更小的按钮）
        color_container = QWidget()
        color_grid_layout = QVBoxLayout(color_container)
        color_grid_layout.setContentsMargins(0, 0, 0, 0)
        color_grid_layout.setSpacing(2)

        colors = [
            ["#000000", "#ffffff", "#ff3232", "#ff8c00", "#ffd700"],
            ["#32cd32", "#1e90ff", "#8a2be2", "#ff69b4", "#808080"]
        ]
        self._text_color_buttons = []

        for row_colors in colors:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            for c in row_colors:
                cb = QPushButton()
                cb.setFixedSize(16, 16)
                cb.setProperty("color", c)
                is_current = (c.lower() == self.text_color.name().lower())
                border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                cb.setStyleSheet(f"background: {c}; border: {border}; border-radius: 2px;")
                cb.clicked.connect(lambda checked, col=c: self._set_text_color(col))
                row_layout.addWidget(cb)
                self._text_color_buttons.append(cb)

            color_grid_layout.addWidget(row_widget)

        text_main_layout.addWidget(color_container)

        # 添加到菜单


        text_action.setDefaultWidget(text_container)
        text_menu.addAction(text_action)
        text_btn.setMenu(text_menu)
        text_menu.aboutToShow.connect(lambda: self._check_and_cancel_tool(["text"], text_menu) or self._select_tool("text"))
        toolbar_layout.addWidget(text_btn)
        self._tool_btns["text"] = text_btn

        # OCR
        ocr_btn = QToolButton()
        ocr_btn.setIcon(self._load_icon("OCR"))
        ocr_btn.setIconSize(QSize(16, 16))
        ocr_btn.setToolTip("文字识别")
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

        close_btn = QToolButton()
        close_btn.setIcon(self._load_icon("close"))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setToolTip("关闭（退出截图）")
        close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(close_btn)

        pin_btn = QToolButton()
        pin_btn.setIcon(self._load_icon("pin"))
        pin_btn.setIconSize(QSize(16, 16))
        pin_btn.setToolTip("悬浮（钉在桌面上）")
        pin_btn.clicked.connect(self._on_pin)
        toolbar_layout.addWidget(pin_btn)

        save_btn = QToolButton()
        save_btn.setIcon(self._load_icon("save"))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setToolTip("保存到文件")
        save_btn.clicked.connect(self._on_save)
        toolbar_layout.addWidget(save_btn)

        copy_btn = QToolButton()
        copy_btn.setIcon(self._load_icon("copy"))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setToolTip("复制到剪贴板")
        copy_btn.clicked.connect(self._on_copy)
        toolbar_layout.addWidget(copy_btn)

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

    def _toggle_or_select_tool(self, tool_id, btn=None, icon_name=None, menu_obj=None):
        """切换或选择工具：如果已选中则取消，否则选中"""
        if self.current_tool == tool_id:
            # 已选中，取消选择
            self._select_tool("select")
            if menu_obj:
                menu_obj.close()
        else:
            # 未选中，选择该工具
            self._select_tool(tool_id, btn, icon_name)
            if menu_obj:
                self._update_submenu_check_state(menu_obj, tool_id)
                menu_obj.close()

    def _check_and_cancel_tool(self, tool_ids, menu_obj):
        """检查当前工具是否在给定的工具列表中，如果是则取消并关闭菜单"""
        if self.current_tool in tool_ids:
            # 使用 QTimer 延迟关闭菜单，避免菜单还没显示就关闭
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, menu_obj.close)
            self._select_tool("select")
            return True
        return False

    def _toggle_tool(self, tool_id):
        """切换工具：如果已选中则取消，否则选中"""
        if self.current_tool == tool_id:
            self._select_tool("select")
        else:
            self._select_tool(tool_id)

    def _update_submenu_check_state(self, menu, selected_tool):
        """更新子菜单中按钮的选中状态"""
        for action in menu.actions():
            widget = action.defaultWidget()
            if widget:
                # 遍历容器中的所有按钮
                for child in widget.findChildren(QToolButton):
                    tool_type = child.property("tool_type")
                    if tool_type:
                        child.setChecked(tool_type == selected_tool)

    def _set_pen_color(self, color_hex, clicked_btn=None):
        self.current_color = QColor(color_hex)
        # 更新所有颜色按钮的边框，突出显示当前选中的颜色
        for btn in self._color_buttons:
            c = btn.property("color")
            if c:
                is_current = (c.lower() == color_hex.lower())
                border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 2px;")

    def _set_width(self, w):
        self.current_width = w

    def _set_text_font(self, font_family):
        """设置文字字体"""
        self.text_font_family = font_family

    def _set_text_size(self, size):
        """设置文字大小"""
        self.text_font_size = size

    def _toggle_bold(self):
        """切换加粗"""
        self.text_bold = self._bold_btn.isChecked()

    def _toggle_italic(self):
        """切换斜体"""
        self.text_italic = self._italic_btn.isChecked()

    def _set_text_color(self, color_hex):
        """设置文字颜色"""
        self.text_color = QColor(color_hex)
        # 更新颜色按钮边框
        for btn in self._text_color_buttons:
            c = btn.property("color")
            if c:
                is_current = (c.lower() == color_hex.lower())
                border = "2px solid #0078d4" if is_current else "1px solid #ccc"
                btn.setStyleSheet(f"background: {c}; border: {border}; border-radius: 2px;")

    def _open_color_picker(self):
        """打开取色器"""
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self.text_color, self, "选择文字颜色")
        if color.isValid():
            self._set_text_color(color.name())

    def _undo(self):
        """撤销最后一个操作"""
        if self.annotations:
            # 将最后一个annotation移到redo栈
            last_annotation = self.annotations.pop()
            self._redo_stack.append(last_annotation)
            self.update()

    def _redo(self):
        """重做上一个被撤销的操作"""
        if self._redo_stack:
            # 从redo栈中取出并恢复到annotations
            annotation = self._redo_stack.pop()
            self.annotations.append(annotation)
            self.update()

    def _adjust_text_editor_size(self):
        """根据文本内容调整编辑器大小，保持左边位置不变"""
        if not self._text_editor:
            return

        text = self._text_editor.text()
        fm = self._text_editor.fontMetrics()
        # 计算文本宽度，加上左右padding(4px * 2)和边框(1px * 2)
        if text:
            text_width = fm.horizontalAdvance(text)
            width = text_width + 14  # padding(8) + border(2) + 光标空间(4)
        else:
            width = 10  # 空文本时的初始宽度
        height = fm.height() + 6  # 文字高度 + padding

        # 先记住当前位置
        current_pos = self._text_editor_window_pos if hasattr(self, '_text_editor_window_pos') else self._text_editor.pos()
        # 调整大小
        self._text_editor.setFixedSize(max(width, 10), height)
        # 重新设置位置，确保左边不动
        self._text_editor.move(current_pos)

    def _finish_text_input(self):
        """完成文本输入"""
        if not self._text_editor:
            return

        # 避免重复调用
        if self._text_editor_pos is None:
            return

        text = self._text_editor.text().strip()
        if text:
            self.annotations.append({
                "type": "text",
                "pos": self._text_editor_pos,
                "text": text,
                "color": QColor(self.text_color),
                "font_family": self.text_font_family,
                "font_size": self.text_font_size,
                "bold": self.text_bold,
                "italic": self.text_italic,
            })
            self._redo_stack.clear()  # 添加新操作后清空redo栈
            self.update()

        # 清理编辑器（先断开信号避免重复触发）
        self._text_editor.textChanged.disconnect()
        self._text_editor.returnPressed.disconnect()
        self._text_editor.editingFinished.disconnect()
        self._text_editor.hide()
        self._text_editor.deleteLater()
        self._text_editor = None
        self._text_editor_pos = None
        # 重新捕获键盘
        self.grabKeyboard()

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
                r = QRectF(ann["rect"]).translated(offset).toRect()  # r是绘制目标位置
                sel = self.selection_rect
                # 从full_screenshot复制时，使用原始的ann["rect"]（相对选区）加上选区偏移
                src_rect = QRect(
                    round((sel.x() + ann["rect"].x()) * dpr),
                    round((sel.y() + ann["rect"].y()) * dpr),
                    round(ann["rect"].width() * dpr),
                    round(ann["rect"].height() * dpr)
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
                # 应用字体样式
                font_family = ann.get("font_family", "Segoe UI")
                font_size = ann.get("font_size", 20)
                font = QFont(font_family, font_size)
                font.setBold(ann.get("bold", False))
                font.setItalic(ann.get("italic", False))
                painter.setFont(font)
                # 使用boundingRect来获取文本高度，确保与编辑器位置一致
                fm = painter.fontMetrics()
                # 向下偏移字体上升高度，让文本顶部对齐编辑器顶部
                text_pos = pos.toPoint() + QPoint(4, fm.ascent() + 2)
                painter.drawText(text_pos, ann["text"])

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
                r = QRectF(ann["rect"]).translated(offset).toRect()  # r是绘制目标位置
                sel = self.selection_rect
                # 从full_screenshot复制时，使用原始的ann["rect"]（相对选区）加上选区偏移
                src_rect = QRect(
                    round((sel.x() + ann["rect"].x()) * dpr), round((sel.y() + ann["rect"].y()) * dpr),
                    round(ann["rect"].width() * dpr), round(ann["rect"].height() * dpr)
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

        # 使用后台线程进行 OCR，避免阻塞 UI
        from .ocr_engine import OcrWorker
        from .utils import qpixmap_to_pil

        pil_image = qpixmap_to_pil(captured)
        self._ocr_worker = OcrWorker(pil_image)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()

        # 显示可取消的处理提示
        from PySide6.QtWidgets import QMessageBox
        self._ocr_progress = QMessageBox(self)
        self._ocr_progress.setWindowTitle("OCR 识别中")
        self._ocr_progress.setText("正在识别文字，请稍候...")
        self._ocr_progress.setStandardButtons(QMessageBox.Cancel)
        self._ocr_progress.setWindowModality(Qt.NonModal)  # 非模态，不阻塞主窗口
        self._ocr_progress.rejected.connect(self._cancel_ocr)
        self._ocr_progress.show()

    def _cancel_ocr(self):
        """取消OCR操作"""
        if hasattr(self, '_ocr_worker') and self._ocr_worker.isRunning():
            self._ocr_worker.terminate()  # 强制终止线程
            self._ocr_worker.wait(1000)  # 等待最多1秒
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()

    def _on_ocr_finished(self, text):
        # 清理进度对话框
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()
            self._ocr_progress.deleteLater()
            delattr(self, '_ocr_progress')

        # 清理worker
        if hasattr(self, '_ocr_worker'):
            self._ocr_worker.deleteLater()
            delattr(self, '_ocr_worker')

        if text:
            QApplication.clipboard().setText(text)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "OCR 完成",
                f"已识别文字并复制到剪贴板\n\n{text[:200]}"
            )
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "OCR 结果",
                "未识别到文字"
            )

    def _on_ocr_error(self, error_msg):
        # 清理进度对话框
        if hasattr(self, '_ocr_progress'):
            self._ocr_progress.close()
            self._ocr_progress.deleteLater()
            delattr(self, '_ocr_progress')

        # 清理worker
        if hasattr(self, '_ocr_worker'):
            self._ocr_worker.deleteLater()
            delattr(self, '_ocr_worker')

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            self, "OCR 错误",
            f"文字识别失败：\n{error_msg}"
        )

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
        # 禁用抗锯齿以提高性能
        # painter.setRenderHint(QPainter.Antialiasing)

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
            round(logical_rect.x() * dpr), round(logical_rect.y() * dpr),
            round(logical_rect.width() * dpr), round(logical_rect.height() * dpr)
        )
        captured = self.full_screenshot.copy(physical_rect)
        captured.setDevicePixelRatio(dpr)
        return captured

    def _capture_pos(self):
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

    def _sel_to_local(self, pos):
        return QPointF(pos - self.selection_rect.topLeft())

    def mousePressEvent(self, event):
        # 如果有活动的文本编辑器，先完成输入
        if self._text_editor and not self._text_editor.geometry().contains(event.position().toPoint()):
            self._finish_text_input()

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
                    # 如果已有编辑器在，先完成之前的输入
                    if self._text_editor:
                        self._finish_text_input()

                    # 创建内嵌的文本编辑器
                    self._text_editor_pos = local
                    self._text_editor = QLineEdit(self)
                    # 应用文字样式设置
                    font = QFont(self.text_font_family, self.text_font_size)
                    font.setBold(self.text_bold)
                    font.setItalic(self.text_italic)
                    self._text_editor.setFont(font)
                    # 保存编辑器位置，用于调整大小时保持左边不动
                    self._text_editor_window_pos = self.selection_rect.topLeft() + local.toPoint()
                    # 设置样式
                    self._text_editor.setStyleSheet("""
                        QLineEdit {
                            background: transparent;
                            border: 1px solid white;
                            padding: 2px 4px;
                            color: %s;
                        }
                    """ % self.text_color.name())
                    # 设置光标宽度，让它更明显
                    self._text_editor.setCursorPosition(0)
                    # 设置位置
                    self._text_editor.move(self._text_editor_window_pos)
                    # 初始宽度设置为较小的大小
                    self._text_editor.setMinimumWidth(10)
                    self._text_editor.setAttribute(Qt.WA_DeleteOnClose)
                    # 连接文本变化信号，自动调整大小
                    self._text_editor.textChanged.connect(self._adjust_text_editor_size)
                    # 初始调整大小
                    self._adjust_text_editor_size()
                    # 释放键盘捕获，让编辑器接收输入
                    self.releaseKeyboard()
                    self._text_editor.show()
                    self._text_editor.setFocus()
                    # 连接完成信号
                    self._text_editor.returnPressed.connect(self._finish_text_input)
                    self._text_editor.editingFinished.connect(self._finish_text_input)
                    self._drawing = False
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
                # 第一次移动时创建新annotation，后续移动时更新它
                if len(self._draw_points) == 2:
                    # 刚开始画（第二个点），创建新annotation
                    self.annotations.append({
                        "type": "freehand",
                        "points": list(self._draw_points),
                        "color": QColor(self.current_color),
                        "width": self.current_width,
                    })
                    self._redo_stack.clear()  # 添加新操作后清空redo栈
                elif len(self._draw_points) > 2:
                    # 继续画，更新当前annotation
                    if self.annotations and self.annotations[-1]["type"] == "freehand":
                        self.annotations[-1]["points"] = list(self._draw_points)
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
            current_pos = event.position()
            delta = current_pos - self._drag_start_pos

            mode = self._drag_mode[0]
            if mode == "move":
                # 使用浮点计算，只在最后转换为整数
                new_x = self._drag_start_rect.x() + delta.x()
                new_y = self._drag_start_rect.y() + delta.y()
                self.selection_rect = QRect(
                    int(new_x), int(new_y),
                    self._drag_start_rect.width(), self._drag_start_rect.height()
                )
                self._position_toolbar()
                self.update()
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
                            self._redo_stack.clear()  # 添加新操作后清空redo栈
                    elif ann["type"] in ("arrow", "line"):
                        dx = ann["end"].x() - ann["start"].x()
                        dy = ann["end"].y() - ann["start"].y()
                        if abs(dx) > 3 or abs(dy) > 3:
                            self.annotations.append(ann)
                            self._redo_stack.clear()  # 添加新操作后清空redo栈
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
            # 如果正在编辑文本，取消输入
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
