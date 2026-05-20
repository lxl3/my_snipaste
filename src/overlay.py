from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRect, QPoint, Signal

from .utils import capture_all_screens


class CaptureOverlay(QWidget):
    capture_completed = Signal(object, object)  # pixmap, global_top_left
    capture_cancelled = Signal()

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

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabKeyboard()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.drawPixmap(0, 0, self.full_screenshot)

        overlay_color = QColor(0, 0, 0, 140)
        painter.fillRect(self.rect(), overlay_color)

        rect = self.selection_rect
        if not rect.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 将逻辑坐标转换为物理坐标以从截图中取出正确区域
            dpr = self.full_screenshot.devicePixelRatio()
            physical_rect = QRect(
                int(rect.x() * dpr),
                int(rect.y() * dpr),
                int(rect.width() * dpr),
                int(rect.height() * dpr)
            )
            painter.drawPixmap(rect, self.full_screenshot, physical_rect)

            pen = QPen(QColor(0, 120, 215), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            for i in range(4):
                handle_rect = self._get_handle_rect(rect, i)
                painter.fillRect(handle_rect, QColor(0, 120, 215))
                painter.setPen(QPen(Qt.white, 1))
                painter.drawRect(handle_rect)

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

    def _get_handle_rect(self, rect, corner_index):
        size = 8
        half = size // 2
        corners = [
            QPoint(rect.left(), rect.top()),
            QPoint(rect.right(), rect.top()),
            QPoint(rect.left(), rect.bottom()),
            QPoint(rect.right(), rect.bottom()),
        ]
        pt = corners[corner_index]
        return QRect(pt.x() - half, pt.y() - half, size, size)

    def _capture_region(self, logical_rect: QRect) -> QPixmap:
        """将逻辑坐标转换为物理坐标并截取区域"""
        dpr = self.full_screenshot.devicePixelRatio()

        # 将逻辑坐标转换为物理坐标
        physical_rect = QRect(
            int(logical_rect.x() * dpr),
            int(logical_rect.y() * dpr),
            int(logical_rect.width() * dpr),
            int(logical_rect.height() * dpr)
        )

        print(f"[诊断] 逻辑选区: {logical_rect.x()},{logical_rect.y()} {logical_rect.width()}x{logical_rect.height()}")
        print(f"[诊断] 物理选区: {physical_rect.x()},{physical_rect.y()} {physical_rect.width()}x{physical_rect.height()}")

        # 从物理坐标截取
        captured = self.full_screenshot.copy(physical_rect)
        # 保持 DPR
        captured.setDevicePixelRatio(dpr)
        return captured

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting = True
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.selection_rect = QRect()
            self.update()

    def mouseMoveEvent(self, event):
        self.current_mouse_pos = event.position().toPoint()
        if self.is_selecting:
            self.end_point = self.current_mouse_pos
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
        else:
            self.update()

    def _capture_pos(self):
        """返回选区在屏幕上的全局坐标（左上角）"""
        return self.total_geometry.topLeft() + self.selection_rect.topLeft()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_selecting = False
            if self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                captured = self._capture_region(self.selection_rect)
                self.capture_completed.emit(captured, self._capture_pos())
            else:
                self.capture_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.capture_cancelled.emit()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not self.selection_rect.isNull():
                captured = self._capture_region(self.selection_rect)
                self.capture_completed.emit(captured, self._capture_pos())

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)
