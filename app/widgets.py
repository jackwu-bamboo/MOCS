"""通用界面控件：卡片、状态灯、轻量曲线、多通道波形。"""
from collections import deque

import cv2
import numpy as np
from PyQt5.QtCore import QPointF, QRect, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

ACCENT = "#00e5c0"
DIM = "#8fa8a4"


def ndarray_to_pixmap(img):
    """OpenCV BGR 图像 → QPixmap。"""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


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
        x = w - r
        for d, color, label, dashed in reversed(self.series):
            if not label:
                continue
            tw = fm.horizontalAdvance(label)
            pen = QPen(color, 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(x - tw - 18, t - 8, x - tw - 6, t - 8)
            p.setPen(QPen(QColor(DIM)))
            p.drawText(x - tw, t - 4, label)
            x -= tw + 28


class MeaPlot(QWidget):
    """多通道电生理波形显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.setMinimumHeight(260)

    def set_data(self, arr):
        self.data = arr
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        l, t, r, b = 46, 8, 8, 8
        p.fillRect(self.rect(), QColor("#0e211f"))
        if self.data is None or self.data.size == 0:
            p.setPen(QPen(QColor(DIM)))
            p.drawText(self.rect(), Qt.AlignCenter, "等待数据...")
            return
        n_ch = self.data.shape[0]
        row_h = (h - t - b) / n_ch
        idx = np.linspace(0, self.data.shape[1] - 1, max(2, w - l - r)).astype(int)
        for c in range(n_ch):
            y0 = t + row_h * c + row_h / 2
            trace = self.data[c][idx]
            peak = max(1e-6, float(np.percentile(np.abs(trace), 99)))
            scale = row_h * 0.38 / peak
            pts = QPolygonF([QPointF(l + i, y0 - v * scale) for i, v in enumerate(trace)])
            p.setPen(QPen(QColor(0, 229, 192, 210) if c % 2 == 0 else QColor(64, 196, 255, 210), 1))
            p.drawPolyline(pts)
            p.setPen(QPen(QColor(DIM)))
            p.drawText(4, int(y0), f"CH{c + 1}")
