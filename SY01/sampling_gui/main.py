# -*- coding: utf-8 -*-
"""SY-01B 自动采样和分发控制模块 · 程序入口。

用法:
    python main.py
依赖见上级目录 requirements.txt (PyQt5 + qt-material + pyserial)。
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _QtMaterialLogFilter(logging.Filter):
    def filter(self, record):
        return "must be imported after" not in record.getMessage()


def _qt_message_handler(_mode, _context, message):
    if "qt.svg" in message or "icon:/" in message:
        return
    print(message)


def main():
    logging.getLogger().addFilter(_QtMaterialLogFilter())
    from PyQt5.QtCore import Qt, qInstallMessageHandler
    from PyQt5.QtWidgets import QApplication
    qInstallMessageHandler(_qt_message_handler)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)

    from qt_material import apply_stylesheet
    from styles import APP_QSS, CUSTOM_QSS, EXTRA, THEME
    apply_stylesheet(app, theme=THEME, extra=EXTRA)
    app.setStyleSheet(app.styleSheet() + CUSTOM_QSS + APP_QSS)

    from main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
