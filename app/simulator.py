"""温控模块设备层：真实 Modbus RTU 驱动 + 模拟仿真双模式。

自动连接流程参考 ThermostaticModule C# Demo：
应用启动即后台扫描串口，读 0x701 校验值匹配 0x0F0F（从站 0x42）即连接成功；
未发现设备时可回退模拟模式。真实模式下温度读数/设定/系统开关均走 Modbus 寄存器。
"""
import csv
import os
import random
import time
from collections import deque
from enum import Enum

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from app.exporter import export_experiment
from app.thermo_device import ThermoModbusDriver

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

        # 设备连接：优先自动连接真实温控模块（Modbus RTU），失败可回退模拟模式
        self.real_mode = False
        self.connected_port = ""

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

        # 温控模块驱动：启动即自动扫描串口（参考 ThermostaticModule 的连接流程）
        self.real_mode = False
        self.connected_port = ""
        self._scan_fallback = False
        self.driver = ThermoModbusDriver(self)
        self.driver.state_changed.connect(self._on_device_state)
        self.driver.temperature_read.connect(self._on_device_temp)
        self.driver.start_scan()

        self.timer = QTimer(self)
        self.timer.setInterval(int(HISTORY_INTERVAL * 1000))
        self.timer.timeout.connect(self._tick)

        # 运行期数据落盘
        self.live_data_dir = None
        self._temp_csv = None
        self._param_log_path = None

        # 温控模块驱动：启动即自动扫描串口连接（参照 ThermostaticModule）；
        # 未发现真实设备时可回退模拟模式
        self.real_mode = False
        self.connected_port = ""
        self._scan_fallback = False
        self.driver = ThermoModbusDriver(self)
        self.driver.state_changed.connect(self._on_device_state)
        self.driver.temperature_read.connect(self._on_device_temp)
        self.driver.error.connect(lambda m: self.raise_alarm(f"温控模块通信错误: {m}"))
        self.driver.start_scan()

        self.timer = QTimer(self)
        self.timer.setInterval(int(HISTORY_INTERVAL * 1000))
        self.timer.timeout.connect(self._tick)

    # ---- 连接管理 ----
    def connect_all(self):
        """连接设备：优先使用已连接的真实设备；否则后台扫描串口，失败则进入模拟模式。"""
        if self.driver.is_connected:
            self._connect_real()
            return
        self._scan_fallback = True
        self.raise_alarm("正在自动扫描串口连接温控模块...")
        self.driver.start_scan()

    def _on_device_state(self, connected, port):
        if connected:
            self.connected["温控模块"] = True
            self.real_mode = True
            self.connected_port = port
            self.timer.start()
            self.raise_alarm(f"温控模块连接成功（{port}，Modbus RTU 0x42）")
            if self.exp_state is ExpState.DISCONNECTED:
                self._set_exp_state(ExpState.CONNECTED)
            return
        # 断开或扫描失败
        if self.real_mode or self.connected.get("温控模块"):
            self.real_mode = False
            self.connected["温控模块"] = False
            self.connected_port = ""
            if self.exp_state in (ExpState.RUNNING, ExpState.PAUSED):
                self.raise_alarm("温控模块连接断开，实验自动暂停")
                self.pause_experiment()
            elif self.exp_state is ExpState.CONNECTED:
                self.timer.stop()
                self._set_exp_state(ExpState.DISCONNECTED)
                self.raise_alarm("温控模块连接已断开")
        elif self._scan_fallback:
            self._scan_fallback = False
            self.raise_alarm("未发现温控设备，已进入模拟模式")
            self._connect_simulated()
        else:
            self.raise_alarm("未发现温控设备，请检查设备接线后点击“连接设备”重试")

    def _on_device_temp(self, temp):
        """真实设备温度读数（后台线程经信号队列进入 GUI 线程）。"""
        if self.real_mode:
            self.temp_current = temp
            self.states_updated.emit()

    def _connect_simulated(self):
        for name in self.connected:
            self.connected[name] = True
        self.real_mode = False
        self.timer.start()
        self.raise_alarm("模拟模式：温度数据由仿真生成")
        self._set_exp_state(ExpState.CONNECTED)

    def disconnect_all(self):
        if self.exp_state in (ExpState.RUNNING, ExpState.PAUSED):
            self.raise_alarm("实验尚未结束，禁止断开设备；请先结束实验")
            return
        for name in self.connected:
            self.connected[name] = False
        self.timer.stop()
        if self.real_mode:
            self.driver.disconnect()
        self.raise_alarm("已断开设备连接")
        self._set_exp_state(ExpState.DISCONNECTED)

    def shutdown(self):
        """退出程序时关闭串口。"""
        self.driver.shutdown()

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

    def start_experiment(self):
        """启动培养（实验编号自动生成，无需手动配置实验信息）。"""
        if self.exp_state not in (ExpState.CONNECTED, ExpState.FINISHED):
            return False
        # 新实验新数据：清空历史统计
        for d in self.history.values():
            d.clear()
        self.param_log.clear()
        # 自动生成实验编号（每次启动为新实验，用于数据归档目录命名）
        self.exp_info = {"id": self.next_exp_id(), "name": "", "operator": "", "remark": ""}
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
        # 真实设备：写入系统总开关（对应 C# Demo 的 SystemSwitch(1)）
        if self.real_mode and not self.driver.write_system_switch(True):
            self.raise_alarm("系统总开关写入失败，请检查设备连接")
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
        if self.real_mode:
            # 真实设备：关闭系统总开关（安全停机）
            if not self.driver.write_system_switch(False):
                self.raise_alarm("系统总开关写入失败，请手动确认设备已停止")
        self._set_exp_state(ExpState.FINISHED)
        self.raise_alarm(f"实验 {self.exp_info['id']} 已结束，数据已归档")
        return True

    @property
    def unlocked(self):
        """设备连接后即解锁各功能模块（无需配置实验）。"""
        return self.exp_state is not ExpState.DISCONNECTED

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

    # ---- 控制命令（真实模式经 Modbus 下发，模拟模式仅更新本地状态）----
    def set_temp(self, target, lower, upper):
        if self.real_mode:
            if not self.driver.write_temperature(target):
                self.raise_alarm(f"温度设定写入设备失败: {target:.1f} ℃")
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
        if not self.real_mode:
            # 模拟模式：温度向目标值一阶趋近 + 噪声；真实模式由设备读数驱动
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
