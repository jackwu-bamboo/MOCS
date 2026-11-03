# -*- coding: utf-8 -*-
"""分配阀可视化组件：圆盘布局 + 角色标签，点击端口发出转动请求。"""
import math

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from port_config import role_color

LOGICAL = 420.0


class ValveWidget(QWidget):
    port_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 380)
        self.port_count = 10
        self.port_roles = {}      # 端口号 -> 角色名
        self.current_port = 1

    def set_config(self, port_count: int, mapping):
        self.port_count = max(2, int(port_count))
        self.port_roles = {}
        for role, port in mapping.items():
            p = int(port)
            if 1 <= p <= self.port_count and p not in self.port_roles:
                self.port_roles[p] = role
        if self.current_port > self.port_count:
            self.current_port = 1
        self.update()

    def set_current(self, port: int):
        self.current_port = max(1, min(self.port_count, int(port)))
        self.update()

    def role_of(self, port: int):
        return self.port_roles.get(int(port))

    # ---------- 几何 ----------
    def _radius(self):
        return LOGICAL * 0.355

    def _port_pos(self, port: int) -> QPointF:
        ang = math.radians(-90.0 + (port - 1) * 360.0 / self.port_count)
        r = self._radius()
        return QPointF(LOGICAL / 2 + r * math.cos(ang), LOGICAL / 2 + r * math.sin(ang))

    def _to_logical(self, x: float, y: float):
        s = min(self.width(), self.height()) / LOGICAL
        ox = (self.width() - LOGICAL * s) / 2
        oy = (self.height() - LOGICAL * s) / 2
        return (x - ox) / s, (y - oy) / s

    # ---------- 交互 ----------
    def mousePressEvent(self, e):
        lx, ly = self._to_logical(e.pos().x(), e.pos().y())
        for i in range(1, self.port_count + 1):
            pos = self._port_pos(i)
            if math.hypot(lx - pos.x(), ly - pos.y()) <= 24:
                self.port_clicked.emit(i)
                return

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        s = min(self.width(), self.height()) / LOGICAL
        p.translate((self.width() - LOGICAL * s) / 2, (self.height() - LOGICAL * s) / 2)
        p.scale(s, s)
        c = QPointF(LOGICAL / 2, LOGICAL / 2)
        R = self._radius()

        p.setPen(QPen(QColor("#94a3b8"), 3))
        p.setBrush(QColor("#e2e8f0"))
        p.drawEllipse(c, R, R)
        p.setPen(QPen(QColor("#e0f2fe"), 3))
        p.setBrush(QColor("#0284c7"))
        p.drawEllipse(c, LOGICAL * 0.125, LOGICAL * 0.125)

        self._draw_center_text(p, c)
        p.setPen(QPen(QColor("#facc15"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(c, self._port_pos(self.current_port))

        for i in range(1, self.port_count + 1):
            self._draw_port(p, i)
        p.end()

    def _draw_center_text(self, p, c):
        f = QFont("Microsoft YaHei")
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(c.x() - 60, c.y() - 30, 120, 32),
                   Qt.AlignHCenter | Qt.AlignVCenter, "")
        f2 = QFont("Microsoft YaHei")
        f2.setPixelSize(13)
        p.setFont(f2)
        p.drawText(QRectF(c.x() - 60, c.y() + 2, 120, 26),
                   Qt.AlignHCenter | Qt.AlignVCenter, f"Port {self.current_port}")

    def _draw_port(self, p, port: int):
        pos = self._port_pos(port)
        role = self.port_roles.get(port)
        color = role_color(role) if role else "#64748b"
        active = (port == self.current_port)

        p.setPen(QPen(QColor("#facc15") if active else QColor("#ffffff"),
                      4 if active else 2))
        p.setBrush(QColor(color))
        r = 12 if active else 10
        p.drawEllipse(pos, r, r)

        f = QFont("Microsoft YaHei")
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r),
                   Qt.AlignCenter, str(port))

        if role:
            self._draw_role_label(p, port, role, color)

    def _draw_role_label(self, p, port: int, role: str, color: str):
        ang_deg = -90.0 + (port - 1) * 360.0 / self.port_count
        rad = math.radians(ang_deg)
        lr = self._radius() + 30
        x = LOGICAL / 2 + lr * math.cos(rad)
        y = LOGICAL / 2 + lr * math.sin(rad)

        a = (ang_deg + 90) % 360
        if 45 <= a <= 135:
            align, rect_x = Qt.AlignLeft, x - 10
        elif 225 <= a <= 315:
            align, rect_x = Qt.AlignRight, x - 130
        else:
            align, rect_x = Qt.AlignHCenter, x - 60
        rect = QRectF(rect_x, y - 10, 120, 20)

        f = QFont("Microsoft YaHei")
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(rect, align | Qt.AlignVCenter, role)


def QRectF(x, y, w, h):
    from PyQt5.QtCore import QRectF
    return QRectF(x, y, w, h)
