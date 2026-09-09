"""设备模拟器（精简版）：仅提供温控模块的仿真数据源。

接入真实硬件时，用基于 pymodbus / pyserial 的驱动类替换本模块，
并保持相同的信号接口（states_updated / alarm_raised / exp_state_changed）。
"""
import csv
import os
import random
import time
from collections import deque
from enum import Enum

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from app.exporter import export_experiment

DEVICE_NAMES = ["温控模块"]

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
    alarm_raised = pyqtSignal(str)
    exp_state_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = {name: False for name in DEVICE_NAMES}

        # 温度控制量
        self.temp_target = 37.0
        self.temp_lower, self.temp_upper = 35.0, 39.0
        self.temp_current = 36.5

        self.alarms = deque(maxlen=50)
        self.param_log = deque(maxlen=500)
        self.history = {
            k: deque(maxlen=600) for k in ("temp", "temp_t")
        }

        # 实验状态机
        self.exp_state = ExpState.DISCONNECTED
        self.exp_info = {"id": "", "name": "", "operator": "", "remark": ""}
        self.exp_params = {}
        self.exp_started_at = None
        self.exp_finished_at = None
        self.paused_at = None
        self.experiments = []  # 已结束实验记录
        self.last_export_path = None

        # 运行期数据落盘
        self.live_data_dir = None
        self._temp_csv = None
        self._param_log_path = None

        self.timer = QTimer(self)
        self.timer.setInterval(int(HISTORY_INTERVAL * 1000))
        self.timer.timeout.connect(self._tick)

    # ---- 连接管理 ----
    def connect_all(self):
        for name in self.connected:
            self.connected[name] = True
        self.timer.start()
        self.raise_alarm("温控模块连接成功")
        self._set_exp_state(ExpState.CONNECTED)

    def disconnect_all(self):
        if self.exp_state in (ExpState.RUNNING, ExpState.PAUSED):
            self.raise_alarm("实验尚未结束，禁止断开设备；请先结束实验")
            return
        for name in self.connected:
            self.connected[name] = False
        self.timer.stop()
        self.raise_alarm("已断开设备连接")
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
        self.raise_alarm(f"实验 {self.exp_info['id']} 已建立，可在“温度控制”页调整培养参数")
        self.states_updated.emit()
        return True

    def start_experiment(self):
        if self.exp_state is not ExpState.CONNECTED or not self.exp_info.get("id"):
            return False
        # 新实验新数据：清空历史统计
        for d in self.history.values():
            d.clear()
        self.param_log.clear()
        # 快照启动时刻的培养参数（存入 experiment.json）
        self.exp_params = {
            "temp_target": self.temp_target,
            "temp_lower": self.temp_lower,
            "temp_upper": self.temp_upper,
        }
        # 运行期数据落盘目录
        self.live_data_dir = os.path.join("exports", self.exp_info["id"], "data")
        os.makedirs(self.live_data_dir, exist_ok=True)
        self._temp_csv = os.path.join(self.live_data_dir, "temperature.csv")
        self._param_log_path = os.path.join(self.live_data_dir, "param_log.csv")
        with open(self._temp_csv, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["timestamp_s", "temp_c"])
        with open(self._param_log_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["time", "param", "old", "new"])
        self.exp_started_at = time.time()
        self.exp_finished_at = None
        self.paused_at = None
        self._set_exp_state(ExpState.RUNNING)
        self.raise_alarm(f"实验 {self.exp_info['id']} 启动，温度数据自动落盘至 {self.live_data_dir}")
        return True

    def pause_experiment(self):
        """暂停实验：温控与数据记录冻结，恢复时补偿运行时长。"""
        if self.exp_state is not ExpState.RUNNING:
            return False
        self.paused_at = time.time()
        self.timer.stop()
        self._set_exp_state(ExpState.PAUSED)
        self.raise_alarm("实验已暂停：温度控制与数据记录暂停")
        return True

    def resume_experiment(self):
        if self.exp_state is not ExpState.PAUSED:
            return False
        if self.paused_at:
            self.exp_started_at += time.time() - self.paused_at
            self.paused_at = None
        self.timer.start()
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
        """新建下一个实验：清空实验信息，回到已连接状态。"""
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

    # ---- 控制命令（后续替换为 Modbus / 串口指令）----
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

    # ---- 定时刷新 ----
    def _tick(self):
        self.temp_current += (self.temp_target - self.temp_current) * 0.06 + random.uniform(-0.03, 0.03)
        if abs(self.temp_current - self.temp_target) > 0.8:
            self.raise_alarm(f"温度偏差过大: {self.temp_current:.2f} ℃ (目标 {self.temp_target:.1f} ℃)")
        h = self.history
        h["temp"].append(self.temp_current)
        h["temp_t"].append(self.temp_target)
        # 运行期温度数据落盘
        if self.exp_state is ExpState.RUNNING and self._temp_csv:
            try:
                with open(self._temp_csv, "a", newline="", encoding="utf-8-sig") as f:
                    csv.writer(f).writerow([f"{time.time():.3f}", f"{self.temp_current:.3f}"])
            except OSError:
                pass
        self.states_updated.emit()
