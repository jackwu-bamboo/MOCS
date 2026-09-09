"""外设控制页：微泵 / 温度 / 氧浓度 / 位置对准（含明场图像）。"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout,
                             QHeaderView, QLabel, QPushButton, QSpinBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.widgets import Card, CurvePlot, ValueCard, ndarray_to_pixmap

# 视场宽度标定值（mm）：640 px × 0.002 mm/px，接入真实相机后按实际标定修改
FOV_MM = 1.28


class ControlPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.tabs.addTab(self._pump_tab(), "微泵控制")
        self.tabs.addTab(self._temp_tab(), "温度控制")
        self.tabs.addTab(self._o2_tab(), "氧浓度控制")
        self.tabs.addTab(self._stage_tab(), "位置对准")
        sim.states_updated.connect(self.refresh)
        sim.frame_updated.connect(self.on_frame)
        self.refresh()

    # ---- 微泵 ----
    def _pump_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)

        left = Card("控制参数")
        form = QFormLayout()
        self.pump_no = QSpinBox()
        self.pump_no.setRange(1, 4)
        self.pressure = QDoubleSpinBox()
        self.pressure.setRange(0.0, 100.0)
        self.pressure.setDecimals(1)
        self.pressure.setSingleStep(0.5)
        self.freq = QDoubleSpinBox()
        self.freq.setRange(0.0, 20.0)
        self.freq.setDecimals(2)
        self.freq.setSingleStep(0.1)
        form.addRow("泵编号", self.pump_no)
        form.addRow("气压 (kPa)", self.pressure)
        form.addRow("频率 (Hz)", self.freq)
        btns = QHBoxLayout()
        b_start = QPushButton("启动")
        b_stop = QPushButton("停止")
        b_apply = QPushButton("应用参数")
        btns.addWidget(b_start)
        btns.addWidget(b_stop)
        btns.addWidget(b_apply)
        form.addRow(btns)
        left.body.addLayout(form)
        b_start.clicked.connect(lambda: self.sim.set_pump(self.pump_no.value() - 1, running=True))
        b_stop.clicked.connect(lambda: self.sim.set_pump(self.pump_no.value() - 1, running=False))
        b_apply.clicked.connect(lambda: self.sim.set_pump(
            self.pump_no.value() - 1,
            pressure=self.pressure.value(),
            frequency=self.freq.value()))

        right = Card("运行状态 / 历史记录")
        self.run_state = QLabel("停止")
        self.run_state.setObjectName("BigValue")
        self.act_p = QLabel("--")
        self.act_f = QLabel("--")
        st = QFormLayout()
        st.addRow("运行状态:", self.run_state)
        st.addRow("实际气压:", self.act_p)
        st.addRow("实际频率:", self.act_f)
        self.pump_hist = QTableWidget(0, 4)
        self.pump_hist.setHorizontalHeaderLabels(["时间", "泵", "动作", "参数"])
        self.pump_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pump_hist.verticalHeader().setVisible(False)
        self.pump_hist.setEditTriggers(QTableWidget.NoEditTriggers)
        right.body.addLayout(st)
        right.body.addWidget(self.pump_hist)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    # ---- 温度 ----
    def _temp_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)

        left = Card("温度设定")
        form = QFormLayout()
        self.temp_target = QDoubleSpinBox()
        self.temp_target.setRange(25.0, 45.0)
        self.temp_target.setDecimals(1)
        self.temp_target.setValue(self.sim.temp_target)
        self.temp_low = QDoubleSpinBox()
        self.temp_low.setRange(20.0, 45.0)
        self.temp_low.setValue(self.sim.temp_lower)
        self.temp_high = QDoubleSpinBox()
        self.temp_high.setRange(25.0, 50.0)
        self.temp_high.setValue(self.sim.temp_upper)
        form.addRow("目标温度 (℃)", self.temp_target)
        form.addRow("控制下限 (℃)", self.temp_low)
        form.addRow("控制上限 (℃)", self.temp_high)
        b_apply = QPushButton("应用设定")
        b_apply.clicked.connect(lambda: self.sim.set_temp(
            self.temp_target.value(), self.temp_low.value(), self.temp_high.value()))
        form.addRow(b_apply)
        left.body.addLayout(form)
        self.temp_now = ValueCard("当前温度", "℃")
        self.temp_goal = ValueCard("目标温度", "℃")
        left.body.addWidget(self.temp_now)
        left.body.addWidget(self.temp_goal)
        left.body.addStretch(1)

        right = Card("温度变化曲线")
        self.temp_plot = CurvePlot("温度 (℃)")
        self.temp_plot.add_series(self.sim.history["temp"], "#00e5c0", "当前")
        self.temp_plot.add_series(self.sim.history["temp_t"], "#ffb74d", "目标", dashed=True)
        right.body.addWidget(self.temp_plot)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    # ---- 氧浓度 ----
    def _o2_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)

        left = Card("氧浓度设定")
        form = QFormLayout()
        self.o2_target = QDoubleSpinBox()
        self.o2_target.setRange(1.0, 95.0)
        self.o2_target.setDecimals(1)
        self.o2_target.setValue(self.sim.o2_target)
        form.addRow("目标氧浓度 (%)", self.o2_target)
        b_apply = QPushButton("应用设定")
        b_apply.clicked.connect(lambda: self.sim.set_o2(self.o2_target.value()))
        form.addRow(b_apply)
        left.body.addLayout(form)
        self.o2_now = ValueCard("当前氧浓度", "%")
        self.o2_goal = ValueCard("目标氧浓度", "%")
        left.body.addWidget(self.o2_now)
        left.body.addWidget(self.o2_goal)
        left.body.addStretch(1)

        right = Card("氧浓度变化趋势")
        self.o2_plot = CurvePlot("氧浓度 (%)")
        self.o2_plot.add_series(self.sim.history["o2"], "#64b5f6", "当前")
        self.o2_plot.add_series(self.sim.history["o2_t"], "#ffb74d", "目标", dashed=True)
        right.body.addWidget(self.o2_plot)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    # ---- 位置对准 ----
    def _stage_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        self._stage_widget = w

        left = Card("点动控制 / 位置信息 (mm)")
        grid = QGridLayout()
        btns = {
            (0, 1): ("↑ Y+", (0, 0.1, 0)),
            (2, 1): ("↓ Y-", (0, -0.1, 0)),
            (1, 0): ("← X-", (-0.1, 0, 0)),
            (1, 2): ("→ X+", (0.1, 0, 0)),
            (1, 1): ("回零", None),
        }
        for (r, c), (text, delta) in btns.items():
            b = QPushButton(text)
            if delta is None:
                b.clicked.connect(lambda: self._zero_stage())
            else:
                b.clicked.connect(lambda _, d=delta: self.sim.jog_stage(*d))
            b.setMinimumSize(64, 40)
            grid.addWidget(b, r, c)
        left.body.addLayout(grid)
        self.pos_labels = [QLabel("0.000") for _ in range(3)]
        form = QFormLayout()
        for axis, lbl in zip("XYZ", self.pos_labels):
            form.addRow(f"{axis} 轴", lbl)
        left.body.addLayout(form)
        left.body.addStretch(1)

        right = Card("明场图像 (位置对准)")
        self.preview = QLabel("在“检测控制”中开启相机后显示图像")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(480, 360)
        self.preview.setStyleSheet("background:#0e211f; color:#8fa8a4;")
        self.preview.mousePressEvent = self._on_preview_click
        right.body.addWidget(self.preview)
        hint = QLabel("点击图像任意位置，可将该点移至视野中心（像素-位移标定待接入相机后确认）")
        hint.setStyleSheet("color: #8fa8a4;")
        hint.setWordWrap(True)
        right.body.addWidget(hint)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    def on_frame(self, img):
        """明场图像刷新（仅在位置对准页可见时更新，节省开销）。"""
        if not hasattr(self, "_stage_widget") or self.tabs.currentWidget() is not self._stage_widget:
            return
        self.preview.setPixmap(ndarray_to_pixmap(img).scaled(
            self.preview.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation))

    def _on_preview_click(self, ev):
        """点击图像将对应样本点移至视野中心。"""
        if not self.sim.detection_running.get("相机"):
            return
        w, h = self.preview.width(), self.preview.height()
        if w <= 0 or h <= 0:
            return
        fx = ev.x() / w - 0.5
        fy = ev.y() / h - 0.5
        self.sim.jog_stage(dx=fx * FOV_MM, dy=-fy * FOV_MM)

    def _zero_stage(self):
        self.sim.stage_pos = [0.0, 0.0, 0.0]
        self.sim.states_updated.emit()

    def refresh(self):
        p = self.sim.pumps[self.pump_no.value() - 1]
        self.run_state.setText("运行中" if p["running"] else "停止")
        self.act_p.setText(f"{p['pressure']:.2f} kPa")
        self.act_f.setText(f"{p['frequency']:.2f} Hz")
        self.pump_hist.setRowCount(len(self.sim.pump_log))
        for i, row in enumerate(self.sim.pump_log):
            for j, v in enumerate(row):
                it = self.pump_hist.item(i, j)
                if it is None:
                    it = QTableWidgetItem()
                    self.pump_hist.setItem(i, j, it)
                it.setText(str(v))
        self.temp_now.set_value(f"{self.sim.temp_current:.2f}")
        self.temp_goal.set_value(f"{self.sim.temp_target:.2f}")
        self.o2_now.set_value(f"{self.sim.o2_current:.2f}")
        self.o2_goal.set_value(f"{self.sim.o2_target:.2f}")
        for axis, lbl in zip(self.sim.stage_pos, self.pos_labels):
            lbl.setText(f"{axis:.3f}")
