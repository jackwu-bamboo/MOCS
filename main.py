"""多器官芯片培养盒集成控制软件 - 入口。"""
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from qt_material import apply_stylesheet

from app.main_window import MainWindow
from app.styles import CUSTOM_QSS


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_teal.xml", extra={
        "font_family": "Microsoft YaHei",
        "bold_font_family": "Microsoft YaHei",
    })
    app.setStyleSheet(app.styleSheet() + CUSTOM_QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
