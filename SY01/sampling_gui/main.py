# -*- coding: utf-8 -*-
"""SY-01B 注射泵手动测试台入口。

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
    from PyQt5.QtCore import qInstallMessageHandler
    qInstallMessageHandler(_qt_message_handler)

    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    try:
        from qt_material import apply_stylesheet
        apply_stylesheet(app, theme="light_blue.xml")
    except Exception:
        pass

    from main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
