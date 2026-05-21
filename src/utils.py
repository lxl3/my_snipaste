import io
import sys
import os

from PIL import Image
from PySide6.QtCore import Qt, QRect, QBuffer, QIODevice, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QImage, QPen
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QWidget
from .logger import setup_logger

logger = setup_logger("utils")


def capture_all_screens() -> QPixmap:
    screens = QApplication.screens()
    if len(screens) == 1:
        return _grab_and_fit(screens[0])

    total_rect = QRect()
    max_dpr = 1.0
    for screen in screens:
        total_rect = total_rect.united(screen.geometry())
        max_dpr = max(max_dpr, screen.devicePixelRatio())

    combined = QPixmap(total_rect.size())
    combined.setDevicePixelRatio(max_dpr)
    combined.fill(Qt.transparent)
    painter = QPainter(combined)
    for screen in screens:
        geo = screen.geometry()
        pixmap = _grab_and_fit(screen)
        painter.drawPixmap(geo.topLeft() - total_rect.topLeft(), pixmap)
    painter.end()
    return combined


def _grab_and_fit(screen) -> QPixmap:
    geo = screen.geometry()
    pixmap = screen.grabWindow(0)
    dpr = screen.devicePixelRatio()

    pixmap.setDevicePixelRatio(dpr)

    return pixmap


def qpixmap_to_pil(pixmap: QPixmap) -> Image.Image:
    qimage = pixmap.toImage()
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def qimage_to_pil(qimage: QImage) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    qimage.save(buffer, "PNG")
    return Image.open(io.BytesIO(buffer.data()))


def pil_to_qpixmap(pil_image: Image.Image) -> QPixmap:
    buffer = io.BytesIO()
    pil_image.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


def create_app_icon() -> QIcon:
    """加载应用图标（优先使用自定义图标，回退到程序生成）

    Returns:
        QIcon: 应用图标对象
    """
    # 尝试加载自定义 PNG 图标（系统托盘推荐）
    icon_sizes = [256, 128, 48, 32, 16]
    icon = QIcon()

    for size in icon_sizes:
        icon_path = resource_path(f"assets/icons/icon-{size}.png")
        if os.path.exists(icon_path):
            icon.addFile(icon_path)

    # 如果自定义图标加载成功，返回
    if not icon.isNull():
        return icon

    # 如果 PNG 都不存在，尝试 ICO
    ico_path = resource_path("icon.ico")
    if os.path.exists(ico_path):
        return QIcon(ico_path)

    # 回退：生成默认图标
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(0, 120, 215))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 10, 10)
    painter.setPen(QPen(Qt.white, 4))
    painter.setFont(QFont("Arial", 28, QFont.Bold))
    painter.drawText(QRect(4, 4, 56, 56), Qt.AlignCenter, "S")
    painter.end()
    return QIcon(pixmap)


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class OcrResultDialog(QDialog):
    """OCR 结果对话框 - 现代极简风格 + 智能排版"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR 识别结果")
        self.setMinimumSize(450, 250)
        self.setMaximumSize(900, 700)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 设置窗口属性：圆角、阴影、无边框，不在任务栏显示
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 主容器
        main_widget = QWidget(self)
        main_widget.setObjectName("mainCard")
        main_widget.setStyleSheet("""
            #mainCard {
                background: #FFFFFF;
                border-radius: 16px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Header 区域
        header = QWidget()
        header.setObjectName("header")
        header.setStyleSheet("""
            #header {
                background: #F9FAFB;
                border-bottom: 1px solid #E5E7EB;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
                padding: 16px 24px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        
        title_label = QLabel("✨ 识别完成")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #111827;
            font-family: 'Segoe UI', 'PingFang SC', sans-serif;
        """)
        
        self.char_count_label = QLabel()
        self.char_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.char_count_label.setStyleSheet("""
            font-size: 12px;
            color: #6B7280;
            font-family: 'Consolas', 'Monaco', monospace;
        """)
        self._update_char_count(text)
        
        # 关闭按钮（X）
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet("""
            QPushButton#closeBtn {
                background: transparent;
                color: #9CA3AF;
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#closeBtn:hover {
                background: #E5E7EB;
                color: #374151;
            }
            QPushButton#closeBtn:pressed {
                background: #D1D5DB;
            }
        """)
        close_btn.clicked.connect(self.close_dialog_only)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.char_count_label)
        header_layout.addWidget(close_btn)
        layout.addWidget(header)
        
        # 2. Content 区域
        content_widget = QWidget()
        content_widget.setObjectName("content")
        content_widget.setStyleSheet("""
            #content {
                background: #FFFFFF;
                padding: 20px 24px;
            }
        """)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        hint_label = QLabel("您可以直接编辑或选择下方文本：")
        hint_label.setStyleSheet("""
            color: #9CA3AF;
            font-size: 12px;
            margin-bottom: 8px;
        """)
        content_layout.addWidget(hint_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text if text else "(未检测到文字)")
        self.text_edit.setReadOnly(False)
        self.text_edit.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.text_edit.setFocusPolicy(Qt.StrongFocus)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: #F3F4F6;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                color: #374151;
                line-height: 1.6;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
            }
            QTextEdit:focus {
                border-color: #3B82F6;
                background: #FFFFFF;
            }
            QTextEdit:disabled {
                background: #F9FAFB;
                color: #9CA3AF;
            }
        """)
        self._adjust_text_edit_size(text)
        content_layout.addWidget(self.text_edit)
        layout.addWidget(content_widget)
        
        # 3. Footer 区域
        footer = QWidget()
        footer.setObjectName("footer")
        footer.setStyleSheet("""
            #footer {
                background: #F9FAFB;
                border-top: 1px solid #E5E7EB;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
                padding: 16px 24px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)
        
        footer_layout.addStretch()
        
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self._copy_and_close_editor)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #111827;
                color: #FFFFFF;
                border: 1px solid #111827;
                border-radius: 8px;
                padding: 10px 32px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #374151;
                border-color: #374151;
            }
            QPushButton:pressed {
                background: #030712;
            }
        """)
        
        footer_layout.addWidget(self.copy_btn)
        layout.addWidget(footer)
        
        # 设置主布局
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.addWidget(main_widget)
        
        # 监听文本变化
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed()
        
        # 保存最后的选中文本（防止点击按钮时失去焦点导致选区丢失）
        self._last_selected_text = ""
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        
        # 窗口拖拽支持 (因为去掉了标题栏)
        self._drag_pos = None

    def showEvent(self, event):
        """对话框显示时自动聚焦到文本编辑区"""
        super().showEvent(event)
        QTimer.singleShot(100, self.text_edit.setFocus)

    def close_dialog_only(self):
        """只关闭对话框，不关闭截图编辑器"""
        # 保存当前选中文本，防止关闭时被清空
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText())
        self.accept()

    def mousePressEvent(self, event):
        # 不accept，让事件传播到子控件（QTextEdit需要接收事件）
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def keyPressEvent(self, event):
        """处理键盘事件：Esc关闭"""
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)

    def _adjust_text_edit_size(self, text: str):
        """根据文本内容调整文本编辑区域大小"""
        if not text:
            self.text_edit.setFixedHeight(80)
            return

        line_count = text.count('\n') + 1
        char_count = len(text)
        
        # 估算高度：每行约 22px + padding
        estimated_height = line_count * 22 + 40
        
        # 最小高度 100px，最大高度 450px
        min_height = 100
        max_height = 450
        
        final_height = max(min_height, min(estimated_height, max_height))
        self.text_edit.setFixedHeight(final_height)
        
        # 智能滚动条
        if char_count < 150:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _update_char_count(self, text: str):
        """更新字符数统计"""
        if not text:
            self.char_count_label.setText("0 字符")
            return

        char_count = len(text)
        line_count = text.count('\n') + 1

        if char_count < 1000:
            self.char_count_label.setText(f"{char_count} 字符 · {line_count} 行")
        else:
            self.char_count_label.setText(f"{char_count / 1000:.1f}K 字符 · {line_count} 行")

    def _on_text_changed(self):
        """文本变化时的处理"""
        text = self.text_edit.toPlainText()
        self._update_char_count(text)

    def _on_selection_changed(self):
        """保存选中文本，防止失去焦点时选区丢失"""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            self._last_selected_text = cursor.selectedText()
        # 不清空！失去焦点时保留最后的选中文本

    def _copy_and_close_editor(self):
        """复制文本（优先选中内容），然后关闭截图编辑器"""
        text = self._last_selected_text
        if not text:
            text = self.text_edit.toPlainText()
        
        if text:
            QApplication.clipboard().setText(text)
            self._show_copy_feedback("已复制")
        
        # 关闭父窗口（截图编辑器）
        if self.parent():
            QTimer.singleShot(300, lambda: self.parent().close())
        QTimer.singleShot(300, self.accept)
            
    def _show_copy_feedback(self, message: str):
        """显示复制成功的微交互反馈"""
        original_text = self.copy_btn.text()
        self.copy_btn.setText(f"✅ {message}")
        self.copy_btn.setEnabled(False)
        # 不再恢复文字，因为对话框很快会关闭
