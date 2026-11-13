"""在 qt-material 主题之上追加的自定义样式。"""

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
QFrame#ModuleGroup {
    background-color: #112b28;
    border: 2px solid #2e6da4;
    border-radius: 6px;
}
QLabel#ModuleTitle {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
    padding: 4px;
}
QFrame#Collapsible {
    background-color: #16302e;
    border: 1px solid #3f8a57;
    border-radius: 4px;
}
QPushButton#CollapsibleToggle {
    color: #e6fffa;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 14px 6px 10px;
    border: none;
    text-align: left;
}
QPushButton#CollapsibleToggle:hover {
    background-color: #1d3f3a;
}
"""
