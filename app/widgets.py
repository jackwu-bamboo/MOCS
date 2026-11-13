"""通用界面控件：卡片、状态灯、轻量曲线。"""
from collections import deque

from PyQt5.QtCore import QPointF, QRect, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton,
                             QVBoxLayout, QWidget)

ACCENT = "#00e5c0"
DIM = "#8fa8a4"


class Card(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, 10, 12, 12)
        self.body.setSpacing(6)
        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self.body.addWidget(t)


class CollapsibleSection(QFrame):
    """可展开条目：点击标题展开/收起内容。"""

    def __init__(self, title, expanded=False, parent=None):
        super().__init__(parent)
        self.setObjectName("Collapsible")
        self.toggle = QToolButton()
        self.toggle.setObjectName("CollapsibleToggle")
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setFixedHeight(34)
        self.toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.toggled.connect(self._on_toggled)
        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(10, 2, 10, 10)
        self.content_lay.setSpacing(6)
        self.content.setVisible(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.toggle)
        lay.addWidget(self.content)
        self.toggle.setChecked(expanded)

    def _on_toggled(self, on):
        self.toggle.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.content.setVisible(on)

    def add_widget(self, widget, stretch=0):
        self.content_lay.addWidget(widget, stretch)


class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.on = False
        self.setFixedSize(14, 14)

    def set_on(self, on):
        self.on = on
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#00e676") if self.on else QColor("#5a6b68"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 10, 10)


class StatusCard(Card):
    def __init__(self, name):
        super().__init__()
        row = QHBoxLayout()
        self.dot = StatusDot()
        lbl = QLabel(name)
        self.state = QLabel("离线")
        self.state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.dot)
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(self.state)
        self.body.addLayout(row)

    def set_state(self, on):
        self.dot.set_on(on)
        self.state.setText("在线" if on else "离线")


class ValueCard(Card):
    def __init__(self, title, unit=""):
        super().__init__(title)
        self.value = QLabel("--")
        self.value.setObjectName("BigValue")
        self.unit_label = QLabel(unit)
        self.unit_label.setStyleSheet(f"color: {DIM};")
        row = QHBoxLayout()
        row.addWidget(self.value)
        row.addWidget(self.unit_label)
        row.addStretch(1)
        self.body.addLayout(row)

    def set_value(self, text):
        self.value.setText(text)


class CurvePlot(QWidget):
    """轻量级历史曲线控件（QPainter 实现，避免引入 pyqtgraph 等额外依赖）。"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.series = []  # (deque, QColor, label, dashed)
        self.setMinimumHeight(150)

    def add_series(self, data, color, label="", dashed=False):
        self.series.append((data, QColor(color), label, dashed))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        l, t, r, b = 48, 22, 10, 8
        p.fillRect(self.rect(), QColor("#0e211f"))
        p.setPen(QPen(QColor("#1d3f3a"), 1))
        for i in range(5):
            y = t + (h - t - b) * i / 4
            p.drawLine(l, int(y), w - r, int(y))
        for i in range(9):
            x = l + (w - l - r) * i / 8
            p.drawLine(int(x), t, int(x), h - b)

        p.setPen(QPen(QColor(DIM)))
        p.drawText(6, 14, self.title)
        vals = [v for d, *_ in self.series for v in d]
        if len(vals) < 2:
            p.drawText(self.rect(), Qt.AlignCenter, "等待数据...")
            return
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.15
        lo, hi = lo - pad, hi + pad

        def xy(i, v, n):
            return (l + (w - l - r) * i / (n - 1),
                    t + (h - t - b) * (1 - (v - lo) / (hi - lo)))

        for d, color, label, dashed in self.series:
            n = len(d)
            if n < 2:
                continue
            pen = QPen(color, 1.7)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawPolyline(QPolygonF([QPointF(*xy(i, v, n)) for i, v in enumerate(d)]))

        fm = p.fontMetrics()
        p.setPen(QPen(QColor(DIM)))
        p.drawText(QRect(2, t, l - 6, 20), Qt.AlignRight | Qt.AlignVCenter, f"{hi:.1f}")
        p.drawText(QRect(2, h - b - 20, l - 6, 20), Qt.AlignRight | Qt.AlignVCenter, f"{lo:.1f}")
        # 图例 + 各序列最新值
        x = w - r
        for d, color, label, dashed in reversed(self.series):
            if not label:
                continue
            text = f"{label} {d[-1]:.1f}" if len(d) else label
            tw = fm.horizontalAdvance(text)
            pen = QPen(color, 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(x - tw - 18, t - 8, x - tw - 6, t - 8)
            p.setPen(QPen(QColor(DIM)))
            p.drawText(x - tw, t - 4, text)
            x -= tw + 28
