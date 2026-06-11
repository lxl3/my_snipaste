from __future__ import annotations
import sys
import math

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QGridLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPixmap, QPainter, QIcon

from resources.icons.toolbar_icons import TOOLBAR_ICONS


def get_icon_svg(name):
    return TOOLBAR_ICONS.get(name, "")

def create_icon_from_svg(svg_code: str, size: int = 24, color: str = "#cccccc"):
    """从 SVG 代码创建 QIcon"""
    svg_code = svg_code.replace("currentColor", color)
    renderer = QSvgRenderer()
    if not renderer.load(svg_code.encode('utf-8')):
        return QIcon()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG 图标库展示")
        self.resize(600, 400)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        grid = QGridLayout()
        grid.setSpacing(15)

        cols = 5
        row = 0
        col = 0

        for name, svg_code in TOOLBAR_ICONS.items():
            icon = create_icon_from_svg(svg_code, size=48, color="#ffffff")
            container = QWidget()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setAlignment(Qt.AlignCenter)

            btn = QToolButton()
            btn.setIcon(icon)
            btn.setIconSize(QPixmap(40, 40).size())
            btn.setFixedSize(60, 60)
            btn.setStyleSheet("""
                QToolButton {
                    background: blue;
                    border: 1px solid #555;
                    border-radius: 8px;
                }
                QToolButton:hover {
                    background: #505050;
                    border-color: #0078d4;
                }
            """)

            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #cccccc; font-size: 12px;")

            v_layout.addWidget(btn)
            v_layout.addWidget(label)

            grid.addWidget(container, row, col)

            col += 1
            if col >= cols:
                col = 0
                row += 1

        main_layout.addLayout(grid)
        main_layout.addStretch()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())
