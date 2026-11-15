"""实验流程页：设备连接（用户选择串口后连接）。

培养参数在"温度控制"页调整。
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from serial.tools import list_ports

from app.simulator import DEVICE_NAMES
from app.widgets import Card, StatusCard

BADGE_STYLES = {
    "locked": ("#455a64", "#90a4ae", "等待上一步"),
    "active": ("#00e5c0", "#0f2622", "进行中"),
    "done": ("#00e676", "#0f2622", "已完成"),
}


class StepCard(Card):
    """带步骤徽章与状态标签的流程卡片。"""

    def __init__(self, no, title):
        super().__init__()
        header = QHBoxLayout()
        self.badge = QLabel(str(no))
        self.badge.setObjectName("StepBadge")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignCenter)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.badge)
        header.addWidget(t)
        header.addStretch(1)
        header.addWidget(self.status)
        self.body.addLayout(header)

        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 4, 0, 0)
        self.body.addWidget(self.content)

    def set_status(self, state):
        bg, fg, text = BADGE_STYLES[state]
        self.badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 12px; font-weight: bold;")
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {bg};")
        self.content.setEnabled(state != "locked")


class WorkflowPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(12)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self.step1 = StepCard(1, "设备连接")
        self._build_step1()
        root.addWidget(self.step1)

        status_card = Card("运行状态")
        self.run_label = QLabel("")
        self.run_label.setWordWrap(True)
        status_card.body.addWidget(self.run_label)
        root.addWidget(status_card)
        root.addStretch(1)

        sim.states_updated.connect(self.refresh)
        sim.exp_state_changed.connect(lambda _: self.refresh())
        self.refresh_ports()
        self.refresh()

    # ---- 步骤① 设备连接 ----
    def _build_step1(self):
        row = QHBoxLayout()
        self.dev_cards = {}
        for name in DEVICE_NAMES:
            card = StatusCard(name)
            self.dev_cards[name] = card
            row.addWidget(card)
        self.step1.content_lay.addLayout(row)

        # 恒温槽串口
        bath_row = QHBoxLayout()
        bath_row.addWidget(QLabel("恒温槽串口:"))
        self.bath_combo = QComboBox()
        self.bath_combo.setMinimumWidth(170)
        bath_row.addWidget(self.bath_combo, 1)
        self.btn_connect_bath = QPushButton("连接")
        self.btn_connect_bath.clicked.connect(self._connect_bath)
        bath_row.addWidget(self.btn_connect_bath)
        self.step1.content_lay.addLayout(bath_row)

        # 盒内温度传感器串口
        sensor_row = QHBoxLayout()
        sensor_row.addWidget(QLabel("传感器串口:"))
        self.sensor_combo = QComboBox()
        self.sensor_combo.setMinimumWidth(170)
        sensor_row.addWidget(self.sensor_combo, 1)
        self.btn_connect_sensor = QPushButton("连接")
        self.btn_connect_sensor.clicked.connect(self._connect_sensor)
        sensor_row.addWidget(self.btn_connect_sensor)
        self.step1.content_lay.addLayout(sensor_row)

        # 气体单元（STX）串口
        gas_row = QHBoxLayout()
        gas_row.addWidget(QLabel("气体单元串口:"))
        self.gas_combo = QComboBox()
        self.gas_combo.setMinimumWidth(170)
        gas_row.addWidget(self.gas_combo, 1)
        self.btn_connect_gas = QPushButton("连接")
        self.btn_connect_gas.clicked.connect(self._connect_gas)
        gas_row.addWidget(self.btn_connect_gas)
        self.step1.content_lay.addLayout(gas_row)

        # 刷新 + 断开 + 状态
        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新串口列表")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.btn_disconnect = QPushButton("断开设备")
        self.btn_disconnect.clicked.connect(self.sim.disconnect_all)
        self.check_label = QLabel("设备未连接")
        btns.addWidget(self.btn_refresh)
        btns.addWidget(self.btn_disconnect)
        btns.addStretch(1)
        btns.addWidget(self.check_label)
        self.step1.content_lay.addLayout(btns)

    # ---- 串口选择与连接 ----
    def refresh_ports(self):
        """枚举本机串口填入两个下拉框。"""
        for combo in (self.bath_combo, self.sensor_combo, self.gas_combo):
            combo.clear()
            for p in list_ports.comports():
                combo.addItem(f"{p.device}  {p.description}")

    def _selected_port(self, combo):
        text = combo.currentText()
        return text.split("  ")[0].strip() if text else ""

    def _connect_bath(self):
        port = self._selected_port(self.bath_combo)
        if port:
            self.sim.connect_bath(port)

    def _connect_sensor(self):
        port = self._selected_port(self.sensor_combo)
        if port:
            self.sim.connect_sensor(port)

    def _connect_gas(self):
        port = self._selected_port(self.gas_combo)
        if port:
            self.sim.connect_gas(port)

    # ---- 状态刷新 ----
    def refresh(self):
        sim = self.sim
        all_conn = all(sim.connected.values())

        for name, card in self.dev_cards.items():
            card.set_state(sim.connected.get(name, False))
        self.btn_connect_bath.setEnabled(not sim.connected.get("恒温槽", False))
        self.btn_connect_sensor.setEnabled(
            not sim.connected.get("盒内温度传感器", False))
        self.btn_connect_gas.setEnabled(not sim.connected.get("气体单元", False))
        self.btn_disconnect.setEnabled(any(sim.connected.values()))
        self.check_label.setText(
            f"已连接（{sim.connected_port}）" if sim.real_mode else "设备未连接")

        self.step1.set_status("done" if all_conn else "active")

        if all_conn:
            self.run_label.setText("设备已连接，可在“温度控制”页设定目标温度")
        else:
            self.run_label.setText("选择串口连接设备后，可在“温度控制”页设定目标温度")
