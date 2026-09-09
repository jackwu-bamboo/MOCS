"""设备模拟器：为界面开发提供仿真数据源。

接入真实硬件时，用基于 pymodbus / pyserial 的驱动类替换本模块，
并保持相同的信号接口（states_updated / mea_updated / frame_updated / alarm_raised）。
"""
import csv
import os
import random
import time
from collections import deque
from enum import Enum

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from app.exporter import export_experiment

DEVICE_NAMES = ["微泵控制器", "温控模块", "氧控模块", "MEA采集", "电化学", "TEER", "相机"]

# 可按需启停的在线检测模块
DETECTION_NAMES = ["MEA", "电化学", "TEER", "相机"]

MEA_CHANNELS = 8
MEA_FS = 250          # 采样率 Hz
MEA_WINDOW = 5.0      # 波形窗口长度 s
HISTORY_INTERVAL = 0.2  # 慢变量历史采样间隔 s


class ExpState(Enum):
    """实验状态机：未连接 → 已连接 → 运行中 ⇄ 已暂停 → 已结束。"""
    DISCONNECTED = "未连接"
    CONNECTED = "已连接"
    RUNNING = "运行中"
    PAUSED = "已暂停"
    FINISHED = "已结束"


class DeviceSimulator(QObject):
    states_updated = pyqtSignal()
    mea_updated = pyqtSignal(object)
    frame_updated = pyqtSignal(object)
    alarm_raised = pyqtSignal(str)
    exp_state_changed = pyqtSignal(object)
    detection_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = {name: False for name in DEVICE_NAMES}

        # 环境控制量
        self.temp_target = 37.0
        self.temp_lower, self.temp_upper = 35.0, 39.0
        self.temp_current = 36.5
        self.o2_target = 18.5
        self.o2_current = 20.9

        # 微泵（4 路）
        self.pumps = [
            {"id": i + 1, "running": False, "pressure": 5.0, "frequency": 1.0}
            for i in range(4)
        ]

        # 载物台位置 (mm)
        self.stage_pos = [0.0, 0.0, 0.0]

        # 检测量
        self.teer = 860.0
        self.teer_baseline = 860.0
        self.echem = 0.42
        self.spike_rate = 2.5
        self.damage_score = 8.0

        self.pump_log = deque(maxlen=200)
        self.alarms = deque(maxlen=50)
        self.history = {
            k: deque(maxlen=600)
            for k in ("temp", "temp_t", "o2", "o2_t", "teer", "echem", "score")
        }

        # MEA 波形缓冲
        self.mea_buf = np.zeros((MEA_CHANNELS, int(MEA_FS * MEA_WINDOW)))
        self.mea_frames = 0
        self._sample_count = 0

        # 明场图像仿真状态（类器官光斑）
        self._blobs = [
            (random.uniform(0.2, 0.8), random.uniform(0.2, 0.8), random.uniform(16, 28))
            for _ in range(5)
        ]
        self._frame = None
        self.image_count = 0

        # 在线检测启停（单一事实来源，UI 与本类通过 detection_toggled 同步）
        self.detection_running = {name: False for name in DETECTION_NAMES}

        # 实验日志：参数变更 / 已保存图像
        self.param_log = deque(maxlen=500)
        self.image_log = deque(maxlen=500)

        # 运行期数据落盘
        self.live_data_dir = None
        self._env_csv = None
        self._param_log_path = None
        self.last_export_path = None

        # 实验状态机
        self.exp_state = ExpState.DISCONNECTED
        self.exp_info = {"id": "", "name": "", "operator": "", "remark": ""}
        self.exp_params = {}
        self.exp_started_at = None
        self.exp_finished_at = None
        self.paused_at = None
        self.experiments = []  # 已结束实验记录

        self.timer = QTimer(self)
        self.timer.setInterval(int(HISTORY_INTERVAL * 1000))
        self.timer.timeout.connect(self._tick)
        self.mea_timer = QTimer(self)
        self.mea_timer.setInterval(100)
        self.mea_timer.timeout.connect(self._tick_mea)
        self.cam_timer = QTimer(self)
        self.cam_timer.setInterval(800)
        self.cam_timer.timeout.connect(self._tick_cam)

    # ---- 连接管理 ----
    def connect_all(self):
        for name in self.connected:
            self.connected[name] = True
        self.timer.start()
        self.mea_timer.start()
        self.cam_timer.start()
        self.raise_alarm("全部设备连接成功")
        self._set_exp_state(ExpState.CONNECTED)

    def disconnect_all(self):
        if self.exp_state in (ExpState.RUNNING, ExpState.PAUSED):
            self.raise_alarm("实验尚未结束，禁止断开设备；请先结束实验")
            return
        for name in self.connected:
            self.connected[name] = False
        for name in list(self.detection_running):
            if self.detection_running[name]:
                self.detection_running[name] = False
                self.detection_toggled.emit(name, False)
        self.timer.stop()
        self.mea_timer.stop()
        self.cam_timer.stop()
        self.raise_alarm("已断开全部设备连接")
        self._set_exp_state(ExpState.DISCONNECTED)

    def _set_exp_state(self, state):
        if self.exp_state is not state:
            self.exp_state = state
            self.exp_state_changed.emit(state)
        self.states_updated.emit()

    # ---- 实验管理 ----
    def next_exp_id(self):
        today = time.strftime("%Y%m%d")
        n = sum(1 for e in self.experiments if e["id"].startswith(f"EXP-{today}")) + 1
        return f"EXP-{today}-{n:03d}"

    def create_experiment(self, exp_id, name, operator="", remark=""):
        self.exp_info = {"id": exp_id.strip(), "name": name.strip(),
                         "operator": operator.strip(), "remark": remark.strip()}
        self.exp_params = {}
        self.exp_started_at = None
        self.exp_finished_at = None
        self.paused_at = None
        if self.exp_state is ExpState.FINISHED:
            self._set_exp_state(ExpState.CONNECTED)
        self.raise_alarm(f"实验 {self.exp_info['id']} 已建立，可在“外设控制”页调整培养参数")
        self.states_updated.emit()
        return True

    def start_experiment(self):
        if self.exp_state is not ExpState.CONNECTED or not self.exp_info.get("id"):
            return False
        # 新实验新数据：清空历史统计
        for d in self.history.values():
            d.clear()
        self.pump_log.clear()
        self.param_log.clear()
        self.image_log.clear()
        self.mea_frames = 0
        self.image_count = 0
        self.damage_score = 8.0
        # 快照启动时刻的培养参数（存入 experiment.json）
        self.exp_params = {
            "temp_target": self.temp_target,
            "temp_lower": self.temp_lower,
            "temp_upper": self.temp_upper,
            "o2_target": self.o2_target,
            "pumps": [dict(p) for p in self.pumps],
            "stage_pos": list(self.stage_pos),
        }
        # 运行期数据落盘目录
        self.live_data_dir = os.path.join("exports", self.exp_info["id"], "data")
        self.live_data_dir = os.path.join("exports", self.exp_info["id"], "data")
        os.makedirs(self.live_data_dir, exist_ok=True)
        self._env_csv = os.path.join(self.live_data_dir, "environment.csv")
        self._param_log_path = os.path.join(self.live_data_dir, "param_log.csv")
        with open(self._env_csv, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["timestamp_s", "temp_c", "o2_pct", "teer_ohm_cm2", "echem_mm"])
        with open(self._param_log_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["time", "param", "old", "new"])
        self.exp_started_at = time.time()
        self.exp_finished_at = None
        self.paused_at = None
        self._set_exp_state(ExpState.RUNNING)
        self.raise_alarm(f"实验 {self.exp_info['id']} 启动，环境数据自动落盘至 {self.live_data_dir}")
        return True

    def pause_experiment(self):
        """暂停实验：环境控制与数据记录冻结，恢复时补偿运行时长。"""
        if self.exp_state is not ExpState.RUNNING:
            return False
        self.paused_at = time.time()
        self.timer.stop()
        self.mea_timer.stop()
        self.cam_timer.stop()
        self._set_exp_state(ExpState.PAUSED)
        self.raise_alarm("实验已暂停：环境控制与数据记录暂停")
        return True

    def resume_experiment(self):
        if self.exp_state is not ExpState.PAUSED:
            return False
        if self.paused_at:
            self.exp_started_at += time.time() - self.paused_at
            self.paused_at = None
        self.timer.start()
        self.mea_timer.start()
        self.cam_timer.start()
        self._set_exp_state(ExpState.RUNNING)
        self.raise_alarm("实验继续运行")
        return True

    def finish_experiment(self):
        if self.exp_state not in (ExpState.RUNNING, ExpState.PAUSED):
            return False
        if self.paused_at:
            self.exp_started_at += time.time() - self.paused_at
            self.paused_at = None
        self.exp_finished_at = time.time()
        # 停止全部在线检测
        for name in list(self.detection_running):
            if self.detection_running[name]:
                self.detection_running[name] = False
                self.detection_toggled.emit(name, False)
        self.experiments.append({
            "id": self.exp_info["id"],
            "name": self.exp_info["name"],
            "started_at": self.exp_started_at,
            "finished_at": self.exp_finished_at,
            "params": dict(self.exp_params),
        })
        # 自动归档
        self.last_export_path = export_experiment(self)
        self._set_exp_state(ExpState.FINISHED)
        self.raise_alarm(f"实验 {self.exp_info['id']} 已结束，数据已归档")
        return True

    def reset_experiment(self):
        """新建下一个实验：清空实验信息与参数，回到已连接状态。"""
        self.exp_info = {"id": "", "name": "", "operator": "", "remark": ""}
        self.exp_params = {}
        self.exp_started_at = None
        self.exp_finished_at = None
        self.paused_at = None
        if self.exp_state is ExpState.FINISHED:
            self._set_exp_state(ExpState.CONNECTED)
        self.states_updated.emit()

    @property
    def unlocked(self):
        """实验建立后即解锁各功能模块（无需等待启动）。"""
        return bool(self.exp_info.get("id"))

    def exp_elapsed(self):
        if self.exp_started_at is None:
            return "--:--:--"
        end = self.exp_finished_at or self.paused_at or time.time()
        s = int(end - self.exp_started_at)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"

    def raise_alarm(self, msg):
        self.alarms.appendleft((time.strftime("%H:%M:%S"), msg))
        self.alarm_raised.emit(msg)

    # ---- 在线检测启停 ----
    def toggle_detection(self, name, on=None):
        """按需启停在线检测模块（实验运行中由总览页/检测页调用）。"""
        if name not in self.detection_running:
            return
        if on is None:
            on = not self.detection_running[name]
        if self.detection_running[name] == on:
            return
        self.detection_running[name] = on
        self.detection_toggled.emit(name, on)
        self.raise_alarm(f"在线检测[{name}] {'启动' if on else '停止'}")

    # ---- 运行期日志 ----
    def log_param_change(self, name, old, new):
        """记录运行中参数变更（时间、参数、旧值→新值），并追加落盘。"""
        row = (time.strftime("%Y-%m-%d %H:%M:%S"), name, str(old), str(new))
        self.param_log.appendleft(row)
        if self._param_log_path:
            try:
                with open(self._param_log_path, "a", newline="", encoding="utf-8-sig") as f:
                    csv.writer(f).writerow(row)
            except OSError:
                pass

    def log_image(self, path):
        """登记一张已保存图像（由检测页拍摄保存时调用）。"""
        self.image_log.appendleft((time.strftime("%Y-%m-%d %H:%M:%S"), path))
        self.image_count = len(self.image_log)
        self.states_updated.emit()

    # ---- 控制命令（后续替换为 Modbus / 串口指令）----
    def set_pump(self, idx, running=None, pressure=None, frequency=None):
        p = self.pumps[idx]
        if self.exp_state is ExpState.RUNNING:
            if pressure is not None and abs(pressure - p["pressure"]) > 1e-9:
                self.log_param_change(f"泵{p['id']} 气压", f"{p['pressure']:.1f} kPa", f"{pressure:.1f} kPa")
            if frequency is not None and abs(frequency - p["frequency"]) > 1e-9:
                self.log_param_change(f"泵{p['id']} 频率", f"{p['frequency']:.2f} Hz", f"{frequency:.2f} Hz")
        if pressure is not None:
            p["pressure"] = pressure
        if frequency is not None:
            p["frequency"] = frequency
        if running is not None and running != p["running"]:
            p["running"] = running
            self.pump_log.appendleft((
                time.strftime("%H:%M:%S"), p["id"],
                "启动" if running else "停止",
                f"{p['pressure']:.1f} kPa / {p['frequency']:.2f} Hz",
            ))
        self.states_updated.emit()

    def set_temp(self, target, lower, upper):
        if self.exp_state is ExpState.RUNNING:
            if abs(target - self.temp_target) > 1e-9:
                self.log_param_change("温度目标", f"{self.temp_target:.1f} ℃", f"{target:.1f} ℃")
            if abs(lower - self.temp_lower) > 1e-9 or abs(upper - self.temp_upper) > 1e-9:
                self.log_param_change("温度范围",
                                      f"{self.temp_lower:.1f}-{self.temp_upper:.1f} ℃",
                                      f"{lower:.1f}-{upper:.1f} ℃")
        self.temp_target = target
        self.temp_lower, self.temp_upper = lower, upper
        self.raise_alarm(f"温度设定更新: 目标 {target:.1f} ℃, 范围 {lower:.1f}-{upper:.1f} ℃")

    def set_o2(self, target):
        if self.exp_state is ExpState.RUNNING and abs(target - self.o2_target) > 1e-9:
            self.log_param_change("氧浓度目标", f"{self.o2_target:.1f} %", f"{target:.1f} %")
        self.o2_target = target
        self.raise_alarm(f"氧浓度设定更新: 目标 {target:.1f} %")

    def jog_stage(self, dx=0.0, dy=0.0, dz=0.0):
        self.stage_pos[0] += dx
        self.stage_pos[1] += dy
        self.stage_pos[2] += dz
        self.states_updated.emit()

    # ---- 定时刷新 ----
    def _tick(self):
        self.temp_current += (self.temp_target - self.temp_current) * 0.06 + random.uniform(-0.03, 0.03)
        self.o2_current += (self.o2_target - self.o2_current) * 0.05 + random.uniform(-0.08, 0.08)
        for p in self.pumps:
            if p["running"]:
                p["pressure"] += random.uniform(-0.06, 0.06)
        self.teer = max(120.0, self.teer - random.uniform(0.0, 0.4))
        self.echem = min(2.5, max(0.05, self.echem + random.uniform(-0.004, 0.006)))
        self.spike_rate = max(0.2, self.spike_rate + random.uniform(-0.06, 0.045))
        self.damage_score = min(100.0, self.damage_score + random.uniform(0.0, 0.04))
        if abs(self.temp_current - self.temp_target) > 0.8:
            self.raise_alarm(f"温度偏差过大: {self.temp_current:.2f} ℃ (目标 {self.temp_target:.1f} ℃)")
        if self.teer < self.teer_baseline * 0.6:
            self.raise_alarm(f"TEER 异常下降: {self.teer:.0f} Ω·cm²")
        h = self.history
        h["temp"].append(self.temp_current)
        h["temp_t"].append(self.temp_target)
        h["o2"].append(self.o2_current)
        h["o2_t"].append(self.o2_target)
        h["teer"].append(self.teer)
        h["echem"].append(self.echem)
        h["score"].append(self.damage_score)
        # 运行期环境数据落盘（TEER/电化学仅在对应检测开启时记录测量值）
        if self.exp_state is ExpState.RUNNING and self._env_csv:
            teer_v = f"{self.teer:.2f}" if self.detection_running["TEER"] else ""
            echem_v = f"{self.echem:.4f}" if self.detection_running["电化学"] else ""
            try:
                with open(self._env_csv, "a", newline="", encoding="utf-8-sig") as f:
                    csv.writer(f).writerow([
                        f"{time.time():.3f}",
                        f"{self.temp_current:.3f}",
                        f"{self.o2_current:.3f}",
                        teer_v, echem_v,
                    ])
            except OSError:
                pass
        self.states_updated.emit()

    def _tick_mea(self):
        if not self.detection_running.get("MEA"):
            return
        n = int(MEA_FS * 0.1)
        t = (np.arange(n) + self._sample_count) / MEA_FS
        self._sample_count += n
        for c in range(MEA_CHANNELS):
            sig = 6 + 3 * np.sin(2 * np.pi * (0.6 + 0.1 * c) * t + c) + np.random.normal(0, 1.2, n)
            hits = np.random.rand(n) < self.spike_rate / MEA_FS
            sig[hits] += np.random.uniform(25, 55, int(hits.sum()))
            self.mea_buf[c] = np.concatenate([self.mea_buf[c, n:], sig])
        self.mea_frames += 1
        self.mea_updated.emit(self.mea_buf.copy())

    def _tick_cam(self):
        if not self.detection_running.get("相机"):
            return
        img = np.full((480, 640, 1), 38, np.float32)
        img += np.random.normal(0, 4, (480, 640, 1)).astype(np.float32)
        img = np.repeat(np.clip(img, 0, 255).astype(np.uint8), 3, axis=2)
        for i, (x, y, r) in enumerate(self._blobs):
            c = (int(x * 640), int(y * 480))
            cv2.circle(img, c, int(r), (70 + 18 * i, 110 + 12 * i, 150), -1)
            cv2.circle(img, c, int(r), (190, 215, 235), 1)
        self._blobs = [
            (min(0.95, max(0.05, x + random.uniform(-0.002, 0.002))),
             min(0.95, max(0.05, y + random.uniform(-0.002, 0.002))),
             min(55.0, r + 0.03))
            for x, y, r in self._blobs
        ]
        self._frame = img
        self.frame_updated.emit(img)

    def snapshot(self):
        return None if self._frame is None else self._frame.copy()
