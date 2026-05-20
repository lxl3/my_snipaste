import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src import SnipasteApp


def main():
    # 启用高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = SnipasteApp(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()