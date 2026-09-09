"""运行页：运行控制（启动/暂停/继续/结束）、实验信息、在线检测控制、
设备状态、温/氧曲线、微泵状态、报警信息。"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QListWidget,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QWidget)

from app.simulator import DEVICE_NAMES, DETECTION_NAMES, ExpState
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
        self.btn_start = QPushButton("启动培养")
        self.btn_start.setObjectName("StartButton")
        self.btn_start.clicked.connect(self.sim.start_experiment)
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_finish = QPushButton("结束实验")
        self.btn_finish.clicked.connect(self.sim.finish_experiment)
        for b in (self.btn_start, self.btn_pause, self.btn_finish):
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
        self.lbl_exp_name = QLabel("--")
        self.lbl_operator = QLabel("--")
        self.lbl_exp_state = QLabel("--")
        self.lbl_elapsed = QLabel("--:--:--")
        for text, lbl in [("实验编号: ", self.lbl_exp_id), ("名称: ", self.lbl_exp_name),
                          ("操作者: ", self.lbl_operator), ("状态: ", self.lbl_exp_state),
                          ("运行时长: ", self.lbl_elapsed)]:
            prefix = QLabel(text)
            prefix.setStyleSheet("color: #8fa8a4;")
            info_row.addWidget(prefix)
            info_row.addWidget(lbl)
            info_row.addSpacing(16)
        info_row.addStretch(1)
        info_card.body.addLayout(info_row)
        root.addWidget(info_card)

        # 在线检测控制（实验运行中按需启停）
        det_card = Card("在线检测控制")
        det_row = QHBoxLayout()
        self.det_btns = {}
        for name in DETECTION_NAMES:
            col = QVBoxLayout()
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            btn = QPushButton("启动")
            btn.clicked.connect(lambda _, n=name: self.sim.toggle_detection(n))
            col.addWidget(lbl)
            col.addWidget(btn)
            det_row.addLayout(col)
            self.det_btns[name] = btn
        det_row.addStretch(1)
        self.rec_label = QLabel("")
        self.rec_label.setStyleSheet("color: #8fa8a4;")
        det_row.addWidget(self.rec_label)
        det_card.body.addLayout(det_row)
        root.addWidget(det_card)

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
        self.o2_plot = CurvePlot("氧浓度 (%)")
        self.o2_plot.add_series(sim.history["o2"], "#64b5f6", "当前")
        self.o2_plot.add_series(sim.history["o2_t"], "#ffb74d", "目标", dashed=True)
        temp_card = Card()
        temp_card.body.addWidget(self.temp_plot)
        o2_card = Card()
        o2_card.body.addWidget(self.o2_plot)
        mid.addWidget(temp_card, 1)
        mid.addWidget(o2_card, 1)
        root.addLayout(mid, 1)

        bottom = QHBoxLayout()
        pump_card = Card("微泵运行状态")
        self.pump_table = QTableWidget(4, 4)
        self.pump_table.setHorizontalHeaderLabels(["泵编号", "状态", "气压 (kPa)", "频率 (Hz)"])
        self.pump_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pump_table.verticalHeader().setVisible(False)
        self.pump_table.setEditTriggers(QTableWidget.NoEditTriggers)
        pump_card.body.addWidget(self.pump_table)

        alarm_card = Card("异常报警信息")
        self.alarm_list = QListWidget()
        self.alarm_list.setObjectName("AlarmList")
        alarm_card.body.addWidget(self.alarm_list)
        bottom.addWidget(pump_card, 3)
        bottom.addWidget(alarm_card, 2)
        root.addLayout(bottom, 1)

        sim.states_updated.connect(self.refresh)
        sim.alarm_raised.connect(self.on_alarm)
        sim.detection_toggled.connect(lambda *_: self.refresh())
        sim.exp_state_changed.connect(lambda *_: self.refresh())
        self.refresh()

    def _toggle_pause(self):
        if self.sim.exp_state is ExpState.PAUSED:
            self.sim.resume_experiment()
        else:
            self.sim.pause_experiment()

    def on_alarm(self, msg):
        ts, _ = self.sim.alarms[0]
        self.alarm_list.insertItem(0, f"[{ts}] {msg}")
        if self.alarm_list.count() > 50:
            self.alarm_list.takeItem(self.alarm_list.count() - 1)

    def refresh(self):
        sim = self.sim
        st = sim.exp_state
        # 运行控制按钮
        configured = bool(sim.exp_info.get("id"))
        self.btn_start.setEnabled(
            sim.exp_state is ExpState.CONNECTED and configured)
        self.btn_pause.setText("继续" if st is ExpState.PAUSED else "暂停")
        self.btn_pause.setEnabled(st in (ExpState.RUNNING, ExpState.PAUSED))
        self.btn_finish.setEnabled(st in (ExpState.RUNNING, ExpState.PAUSED))
        if st is ExpState.RUNNING:
            self.run_hint.setText(f"运行中 {sim.exp_elapsed()}")
        elif st is ExpState.PAUSED:
            self.run_hint.setText("已暂停，环境控制与数据记录冻结")
        else:
            self.run_hint.setText("")

        # 在线检测启停按钮（实验建立后即可操作）
        active = sim.unlocked
        for name, btn in self.det_btns.items():
            on = sim.detection_running.get(name, False)
            btn.setText("■ 停止" if on else "▶ 启动")
            btn.setEnabled(active)
        if sim.exp_state is ExpState.RUNNING:
            self.rec_label.setText(f"数据落盘: {sim.live_data_dir}")
        elif sim.unlocked:
            self.rec_label.setText("实验未启动，环境数据暂不记录")
        else:
            self.rec_label.setText("未记录（实验未运行）")
        for name, card in self.dev_cards.items():
            card.set_state(sim.connected.get(name, False))
        info = sim.exp_info
        if info.get("id"):
            self.lbl_exp_id.setText(info["id"])
            self.lbl_exp_name.setText(info.get("name") or "--")
            self.lbl_operator.setText(info.get("operator") or "--")
        else:
            self.lbl_exp_id.setText("未建立实验，请前往“实验流程”页")
            self.lbl_exp_name.setText("--")
            self.lbl_operator.setText("--")
        self.lbl_exp_state.setText(sim.exp_state.value)
        self.lbl_elapsed.setText(sim.exp_elapsed())
        for i, p in enumerate(sim.pumps):
            values = [str(p["id"]), "运行" if p["running"] else "停止",
                      f"{p['pressure']:.2f}", f"{p['frequency']:.2f}"]
            for j, v in enumerate(values):
                it = self.pump_table.item(i, j)
                if it is None:
                    it = QTableWidgetItem()
                    self.pump_table.setItem(i, j, it)
                it.setText(v)
