"""温度控制页：目标温度设定与实时温度显示。"""
from PyQt5.QtWidgets import (QDoubleSpinBox, QFormLayout, QHBoxLayout, QPushButton,
                             QVBoxLayout, QWidget)

from app.widgets import Card, ValueCard


class TemperaturePage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        lay = QHBoxLayout()
        root.addLayout(lay)

        left = Card("温度设定")
        form = QFormLayout()

        # 恒温槽温度设定
        self.sp_bath = QDoubleSpinBox()
        self.sp_bath.setRange(-20.0, 50.0)
        self.sp_bath.setDecimals(1)
        self.sp_bath.setValue(sim.temp_target)
        b_bath = QPushButton("应用")
        b_bath.clicked.connect(self._apply_bath)
        form.addRow("恒温槽温度 (℃)", self._spin_with_btn(self.sp_bath, b_bath))

        left.body.addLayout(form)
        self.temp_now = ValueCard("当前温度(恒温槽)", "℃")
        self.temp_box = ValueCard("盒内温度(传感器)", "℃")
        left.body.addWidget(self.temp_now)
        left.body.addWidget(self.temp_box)
        left.body.addStretch(1)
        lay.addWidget(left)
        lay.addStretch(1)

        sim.states_updated.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _spin_with_btn(spin, btn):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(spin, 1)
        h.addWidget(btn)
        return w

    def _apply_bath(self):
        self.sim.set_bath_temp(self.sp_bath.value())

    def refresh(self):
        self.temp_now.set_value(
            f"{self.sim.temp_current:.2f}" if self.sim.real_mode else "--")
        self.temp_box.set_value(
            f"{self.sim.box_temp:.2f}" if self.sim.box_temp is not None else "--")
