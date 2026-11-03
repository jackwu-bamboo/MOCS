# -*- coding: utf-8 -*-
"""在 qt-material 主题之上追加的自定义样式（与 C:\\work\\GitHub\\MOCS\\app\\styles.py 一致）。"""

THEME = "dark_teal.xml"
EXTRA = {
    "font_family": "Microsoft YaHei",
    "bold_font_family": "Microsoft YaHei",
}

CUSTOM_QSS = """
QFrame#Card {
    background-color: #16302e;
    border: 1px solid #1f4b45;
    border-radius: 8px;
}
QLabel#CardTitle {
    color: #7fd8c9;
    font-size: 13px;
    font-weight: bold;
}
QLabel#BigValue {
    font-size: 24px;
    font-weight: bold;
    color: #00e5c0;
}
QLabel#WarnText {
    color: #ff5252;
    font-weight: bold;
}
QLabel#HeaderTitle {
    font-size: 17px;
    font-weight: bold;
}
QLabel#Clock {
    color: #9fd8cf;
}
QListWidget#Sidebar {
    background-color: #0f2622;
    border: none;
    font-size: 15px;
    outline: 0;
}
QListWidget#Sidebar::item {
    height: 44px;
    padding-left: 14px;
    border-left: 3px solid transparent;
}
QListWidget#Sidebar::item:selected {
    border-left: 3px solid #00e5c0;
    background-color: #17423b;
    color: #ffffff;
}
QFrame#Header {
    background-color: #0f2622;
    border-bottom: 1px solid #1f4b45;
}
QTableWidget {
    background: #122623;
    alternate-background-color: #16302e;
    gridline-color: #1f4b45;
}
QHeaderView::section {
    background-color: #17423b;
    padding: 4px;
    border: none;
}
QListWidget#AlarmList {
    background: #122623;
    color: #ffb4a2;
}
QLabel#StepBadge {
    font-weight: bold;
}
QPushButton#StartButton {
    background-color: #00bfa5;
    color: #06231f;
    font-size: 15px;
    font-weight: bold;
    padding: 8px 24px;
}
QPushButton#StartButton:disabled {
    background-color: #2a4a45;
    color: #6b8a85;
}
QScrollArea#Sidebar {
    background-color: #0f2622;
    border: none;
}
QFrame#SideGroup {
    background-color: #16302e;
    border: 1px solid #1f4b45;
    border-radius: 8px;
}
QLabel#SideGroupHeader {
    background-color: #2e6da4;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    padding: 6px;
    border-radius: 6px;
}
QPushButton#SideBtn {
    background-color: #1b3a36;
    border: 1px solid #24544d;
    border-radius: 4px;
    padding: 7px 4px;
}
QPushButton#SideBtn:hover {
    background-color: #22554d;
}
QPushButton#SideBtn:disabled {
    color: #54655f;
    background-color: #122623;
}
QLabel#SideStat {
    font-size: 15px;
    font-weight: bold;
    color: #00e5c0;
}
"""

# 下拉列表弹出层的局部样式(优先级高于主题样式, 需逐个 combo.view() 设置)
COMBO_VIEW_QSS = """
QAbstractItemView {
    background-color: #122623;
    color: #cdeee8;
    border: 1px solid #1f4b45;
    outline: 0;
    padding: 2px;
}
QAbstractItemView::item {
    min-height: 26px;
    padding: 2px 10px;
    background-color: #122623;
    color: #cdeee8;
}
QAbstractItemView::item:hover,
QAbstractItemView::item:selected,
QAbstractItemView::item:selected:active,
QAbstractItemView::item:selected:!active,
QAbstractItemView::item:focus,
QAbstractItemView::item:checked {
    background-color: #1d4f47;
    color: #e6fffa;
    selection-background-color: #1d4f47;
    selection-color: #e6fffa;
}
"""

# 本程序专用: 分组框与日志框套用上级程序的卡片风格(深青绿底、青色标题)
APP_QSS = """
QGroupBox {
    background-color: #16302e;
    border: 1px solid #1f4b45;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #7fd8c9;
}
QPlainTextEdit {
    background-color: #0f2622;
    border: 1px solid #1f4b45;
    border-radius: 6px;
    color: #9fd8cf;
}
QLabel#Hint {
    color: #7fa39b;
}
QComboBox {
    min-width: 150px;
    min-height: 26px;
}
QComboBox QAbstractItemView {
    background-color: #122623;
    color: #cdeee8;
    border: 1px solid #1f4b45;
    selection-background-color: #17423b;
    selection-color: #7fd8c9;
    outline: 0;
    min-width: 170px;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 2px 10px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #1f5c52;
    color: #ffffff;
}
"""
