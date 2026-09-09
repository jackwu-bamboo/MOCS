"""运行页：运行控制（启动/暂停/继续/结束）、实验信息、温度曲线、报警信息。"""
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QPushButton,
                             QVBoxLayout, QWidget)

from app.simulator import DEVICE_NAMES, ExpState
from app.widgets import Card, CurvePlot, StatusCard


class RunPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 运行控制条（与侧边栏运行组按钮同步，状态驱动可用性）
        run_card = Card("运行控制")
        run_row = QHBoxLayout()
        self.btn_start = QPushButton("启动")
        self.btn_start.setObjectName("StartButton")
        self.btn_start.clicked.connect(self._toggle_run)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self.sim.finish_experiment)
        for b in (self.btn_start, self.btn_stop):
            run_row.addWidget(b)
        run_row.addStretch(1)
        self.run_hint = QLabel("")
        self.run_hint.setStyleSheet("color: #8fa8a4;")
        run_row.addWidget(self.run_hint)
        run_card.body.addLayout(run_row)
        root.addWidget(run_card)

        # 实验信息栏
        info_card = Card("实验信息")
        info_row = QHBoxLayout()
        self.lbl_exp_id = QLabel("--")
        self.lbl_exp_state = QLabel("--")
        self.lbl_elapsed = QLabel("--:--:--")
        for text, lbl in [("实验编号: ", self.lbl_exp_id), ("状态: ", self.lbl_exp_state),
                          ("运行时长: ", self.lbl_elapsed)]:
            prefix = QLabel(text)
            prefix.setStyleSheet("color: #8fa8a4;")
            info_row.addWidget(prefix)
            info_row.addWidget(lbl)
            info_row.addSpacing(16)
        info_row.addStretch(1)
        info_card.body.addLayout(info_row)
        root.addWidget(info_card)

        dev_row = QHBoxLayout()
        self.dev_cards = {}
        for name in DEVICE_NAMES:
            card = StatusCard(name)
            self.dev_cards[name] = card
            dev_row.addWidget(card)
        root.addLayout(dev_row)

        mid = QHBoxLayout()
        self.temp_plot = CurvePlot("温度 (℃)")
        self.temp_plot.add_series(sim.history["temp"], "#00e5c0", "当前")
        self.temp_plot.add_series(sim.history["temp_t"], "#ffb74d", "目标", dashed=True)
        temp_card = Card()
        temp_card.body.addWidget(self.temp_plot)
        mid.addWidget(temp_card, 1)

        alarm_card = Card("异常报警信息")
        self.alarm_list = QListWidget()
        self.alarm_list.setObjectName("AlarmList")
        alarm_card.body.addWidget(self.alarm_list)
        mid.addWidget(alarm_card, 1)
        root.addLayout(mid, 1)

        sim.states_updated.connect(self.refresh)
        sim.states_updated.connect(self.temp_plot.update)
        sim.alarm_raised.connect(self.on_alarm)
        sim.exp_state_changed.connect(lambda *_: self.refresh())
        self.refresh()

    def _toggle_run(self):
        """空闲时启动培养。"""
        self.sim.start_experiment()

    def on_alarm(self, msg):
        ts, _ = self.sim.alarms[0]
        self.alarm_list.insertItem(0, f"[{ts}] {msg}")
        if self.alarm_list.count() > 50:
            self.alarm_list.takeItem(self.alarm_list.count() - 1)

    def refresh(self):
        sim = self.sim
        st = sim.exp_state
        # 运行控制按钮：启动（空闲）/ 停止（运行中）
        self.btn_start.setEnabled(st in (ExpState.CONNECTED, ExpState.FINISHED))
        self.btn_stop.setEnabled(st is ExpState.RUNNING)
        if st is ExpState.RUNNING:
            self.run_hint.setText(f"运行中 {sim.exp_elapsed()}")
        else:
            self.run_hint.setText("")

        for name, card in self.dev_cards.items():
            card.set_state(sim.connected.get(name, False))
        self.lbl_exp_id.setText(sim.exp_info.get("id") or "未开始（启动后自动生成编号）")
        self.lbl_exp_state.setText(sim.exp_state.value)
        self.lbl_elapsed.setText(sim.exp_elapsed())
