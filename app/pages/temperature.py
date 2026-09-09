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
        self.sp_target = QDoubleSpinBox()
        self.sp_target.setRange(25.0, 45.0)
        self.sp_target.setDecimals(1)
        self.sp_target.setValue(sim.temp_target)
        form.addRow("目标温度 (℃)", self.sp_target)
        b_apply = QPushButton("应用设定")
        b_apply.clicked.connect(self._apply)
        form.addRow(b_apply)
        left.body.addLayout(form)
        self.temp_now = ValueCard("当前温度", "℃")
        self.temp_goal = ValueCard("目标温度", "℃")
        left.body.addWidget(self.temp_now)
        left.body.addWidget(self.temp_goal)
        left.body.addStretch(1)
        lay.addWidget(left)
        lay.addStretch(1)

        sim.states_updated.connect(self.refresh)
        self.refresh()

    def _apply(self):
        self.sim.set_temp(self.sp_target.value())

    def refresh(self):
        self.temp_now.set_value(f"{self.sim.temp_current:.2f}")
        self.temp_goal.set_value(f"{self.sim.temp_target:.2f}")
