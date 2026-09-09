"""温度控制页：目标温度 / 控制范围设定与温度变化曲线。"""
from PyQt5.QtWidgets import (QDoubleSpinBox, QFormLayout, QHBoxLayout, QPushButton,
                             QVBoxLayout, QWidget)

from app.widgets import Card, CurvePlot, ValueCard


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
        self.sp_low = QDoubleSpinBox()
        self.sp_low.setRange(20.0, 45.0)
        self.sp_low.setValue(sim.temp_lower)
        self.sp_high = QDoubleSpinBox()
        self.sp_high.setRange(25.0, 50.0)
        self.sp_high.setValue(sim.temp_upper)
        form.addRow("目标温度 (℃)", self.sp_target)
        form.addRow("控制下限 (℃)", self.sp_low)
        form.addRow("控制上限 (℃)", self.sp_high)
        b_apply = QPushButton("应用设定")
        b_apply.clicked.connect(self._apply)
        form.addRow(b_apply)
        left.body.addLayout(form)
        self.temp_now = ValueCard("当前温度", "℃")
        self.temp_goal = ValueCard("目标温度", "℃")
        left.body.addWidget(self.temp_now)
        left.body.addWidget(self.temp_goal)
        left.body.addStretch(1)

        right = Card("温度变化曲线")
        self.temp_plot = CurvePlot("温度 (℃)")
        self.temp_plot.add_series(sim.history["temp"], "#00e5c0", "当前")
        self.temp_plot.add_series(sim.history["temp_t"], "#ffb74d", "目标", dashed=True)
        right.body.addWidget(self.temp_plot)

        lay.addWidget(left)
        lay.addWidget(right, 1)

        sim.states_updated.connect(self.refresh)
        self.refresh()

    def _apply(self):
        self.sim.set_temp(self.sp_target.value(), self.sp_low.value(), self.sp_high.value())

    def refresh(self):
        self.temp_now.set_value(f"{self.sim.temp_current:.2f}")
        self.temp_goal.set_value(f"{self.sim.temp_target:.2f}")
