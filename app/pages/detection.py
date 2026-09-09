"""检测界面：电生理监测 / 电化学检测 / TEER 检测 / 明场成像。"""
import os
import time

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QPushButton,
                             QTabWidget, QVBoxLayout, QWidget)

from app.simulator import MEA_FS, MEA_WINDOW
from app.widgets import Card, CurvePlot, MeaPlot, ValueCard, ndarray_to_pixmap


class DetectionPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.latest_frame = None
        self.capture_dir = os.path.abspath("exports/images")
        self._loaded_for = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        tabs = QTabWidget()
        root.addWidget(tabs)
        tabs.addTab(self._mea_tab(), "电生理检测")
        tabs.addTab(self._echem_tab(), "电化学检测")
        tabs.addTab(self._teer_tab(), "TEER 检测")
        tabs.addTab(self._imaging_tab(), "明场拍照")
        self.tabs = tabs

        sim.mea_updated.connect(self.on_mea)
        sim.frame_updated.connect(self.on_frame)
        sim.states_updated.connect(self.refresh)
        sim.detection_toggled.connect(lambda *_: self.refresh())
        self.refresh()

    # ---- 4.1 电生理（MEA）----
    def _mea_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)

        left = Card("采集控制")
        self.mea_btn = QPushButton("开始采集")
        self.mea_btn.clicked.connect(lambda: self.sim.toggle_detection("MEA"))
        left.body.addWidget(self.mea_btn)
        left.body.addWidget(QLabel(f"采样率: {MEA_FS} Hz × 8 通道"))
        self.spike_card = ValueCard("Spike 数", "个/5s")
        self.rate_card = ValueCard("放电频率", "Hz")
        self.amp_card = ValueCard("信号幅值", "µV")
        left.body.addWidget(self.spike_card)
        left.body.addWidget(self.rate_card)
        left.body.addWidget(self.amp_card)
        left.body.addStretch(1)

        right = Card("实时波形 (多通道)")
        self.mea_plot = MeaPlot()
        right.body.addWidget(self.mea_plot)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    def on_mea(self, arr):
        self.mea_plot.set_data(arr)
        thr = 5.0 * np.std(arr, axis=1, keepdims=True)
        spikes = int(np.sum((arr[:, 1:] > thr) & (arr[:, :-1] <= thr)))
        p2p = float(np.max(arr) - np.min(arr))
        self.spike_card.set_value(str(spikes))
        self.rate_card.set_value(f"{spikes / MEA_WINDOW / arr.shape[0]:.2f}")
        self.amp_card.set_value(f"{p2p:.0f}")

    # ---- 4.2 电化学 ----
    def _echem_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        left = Card("实时检测值")
        self.echem_card = ValueCard("代谢物浓度", "mM")
        left.body.addWidget(self.echem_card)
        left.body.addWidget(QLabel("传感器类型: 待接入设备后配置"))
        left.body.addStretch(1)
        right = Card("浓度变化曲线")
        self.echem_plot = CurvePlot("电化学检测值 (mM)")
        self.echem_plot.add_series(self.sim.history["echem"], "#ba68c8", "浓度")
        right.body.addWidget(self.echem_plot)
        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    # ---- 4.3 TEER ----
    def _teer_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        left = Card("屏障完整性")
        self.teer_card = ValueCard("当前 TEER", "Ω·cm²")
        self.teer_warn = QLabel("")
        self.teer_warn.setObjectName("WarnText")
        self.teer_warn.setWordWrap(True)
        left.body.addWidget(self.teer_card)
        left.body.addWidget(self.teer_warn)
        left.body.addStretch(1)
        right = Card("TEER 变化曲线")
        self.teer_plot = CurvePlot("TEER (Ω·cm²)")
        self.teer_plot.add_series(self.sim.history["teer"], "#4dd0e1", "TEER")
        right.body.addWidget(self.teer_plot)
        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    # ---- 4.4 明场成像 ----
    def _imaging_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)

        left = Card("采集设置")
        form = QFormLayout()
        self.cap_interval = QDoubleSpinBox()
        self.cap_interval.setRange(1.0, 3600.0)
        self.cap_interval.setValue(10.0)
        self.cap_interval.setSuffix(" s")
        self.cap_path = QLineEdit(os.path.abspath("exports/images"))
        form.addRow("拍摄间隔", self.cap_interval)
        form.addRow("保存路径", self.cap_path)
        left.body.addLayout(form)

        self.b_capture = QPushButton("手动拍摄")
        self.b_capture.clicked.connect(self.capture_now)
        self.auto_box = QCheckBox("自动定时采集")
        self.auto_box.toggled.connect(self.toggle_auto)
        left.body.addWidget(self.b_capture)
        left.body.addWidget(self.auto_box)
        self.cam_btn = QPushButton("开启相机")
        self.cam_btn.clicked.connect(lambda: self.sim.toggle_detection("相机"))
        left.body.addWidget(self.cam_btn)
        self.image_list = QListWidget()
        left.body.addWidget(self.image_list, 1)

        right = Card("预览（相机开启后实时显示）")
        self.preview = QLabel("相机未开启")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(480, 360)
        self.preview.setStyleSheet("background:#0e211f; color:#8fa8a4;")
        right.body.addWidget(self.preview)

        self.cap_timer = QTimer(self)
        self.cap_timer.timeout.connect(self.capture_now)

        lay.addWidget(left)
        lay.addWidget(right, 1)
        return w

    def toggle_auto(self, on):
        if on:
            self.cap_timer.start(int(self.cap_interval.value() * 1000))
        else:
            self.cap_timer.stop()

    def capture_now(self):
        if not self.sim.detection_running.get("相机"):
            return
        img = self.sim.snapshot()
        if img is None:
            return
        path = self.cap_path.text().strip() or "exports/images"
        os.makedirs(path, exist_ok=True)
        name = time.strftime("%Y%m%d_%H%M%S") + ".png"
        full = os.path.join(path, name)
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(full)
            self.sim.log_image(full)
            self.image_list.insertItem(0, name)
            if self.image_list.count() > 100:
                self.image_list.takeItem(self.image_list.count() - 1)

    def on_frame(self, img):
        self.latest_frame = img
        self.preview.setPixmap(ndarray_to_pixmap(img).scaled(
            self.preview.size(), Qt.IgnoreAspectRatio, Qt.FastTransformation))

    # ---- 状态刷新 ----
    def refresh(self):
        sim = self.sim
        # 新实验参数应用后，同步成像间隔与保存路径
        exp_id = sim.exp_info.get("id")
        imaging = sim.exp_params.get("imaging")
        if imaging and self._loaded_for != exp_id:
            self._loaded_for = exp_id
            self.cap_interval.setValue(imaging["interval"])
            self.cap_path.setText(imaging["path"])
        # 启停按钮与 sim.detection_running 同步
        mea_on = sim.detection_running.get("MEA", False)
        self.mea_btn.setText("停止采集" if mea_on else "开始采集")
        cam_on = sim.detection_running.get("相机", False)
        self.cam_btn.setText("关闭相机" if cam_on else "开启相机")
        self.b_capture.setEnabled(cam_on)
        if not cam_on:
            self.auto_box.setChecked(False)
        self.echem_card.set_value(f"{sim.echem:.3f}")
        self.teer_card.set_value(f"{sim.teer:.0f}")
        if sim.teer < sim.teer_baseline * 0.6:
            self.teer_warn.setText("⚠ TEER 异常下降，屏障完整性可能受损")
        else:
            self.teer_warn.setText("")
