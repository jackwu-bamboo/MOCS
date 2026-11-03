"""温控设备层：恒温槽（外循环水箱）+ 盒内温度传感器，真实 Modbus RTU 驱动。

两个设备均由用户在界面选择串口后手动连接：
  - 恒温槽（低温恒温槽/外循环水箱）：FC04 读 PV、FC03/FC10 读写 SV、
    FC06 写循环运行开关；连接后每 2s 轮询实测温度
  - 盒内温度传感器（原温控模块，从站 0x42）：FC04 读 0x701 校验连接、
    0xB020 读盒内温度；连接后每 2s 轮询
"""
import time
from collections import deque
from enum import Enum

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from app.box_sensor import BoxSensorDriver
from app.thermo_device import ThermoModbusDriver

DEVICE_NAMES = ["恒温槽", "盒内温度传感器"]

HISTORY_INTERVAL = 0.2  # 慢变量历史采样间隔 s


class ExpState(Enum):
    """连接状态机：未连接 → 已连接。"""
    DISCONNECTED = "未连接"
    CONNECTED = "已连接"


class DeviceSimulator(QObject):
    states_updated = pyqtSignal()
    alarm_raised = pyqtSignal(str)
    exp_state_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = {name: False for name in DEVICE_NAMES}

        # 温度控制量
        self.temp_target = 37.0      # 恒温槽目标温度
        self.temp_current = 36.5     # 恒温槽实测温度
        self.box_temp = None         # 盒内温度传感器实测温度 ℃（只读显示）
        self.run_on = False          # 设备运行开关状态

        # 设备连接状态
        self.real_mode = False
        self.connected_port = ""

        self.alarms = deque(maxlen=50)
        self.history = {
            k: deque(maxlen=600) for k in ("temp", "temp_t")
        }

        # 实验状态机
        self.exp_state = ExpState.DISCONNECTED

        # 恒温槽驱动：用户在界面选择串口后连接
        self.real_mode = False
        self.connected_port = ""
        self.driver = ThermoModbusDriver(parent=self)
        self.driver.state_changed.connect(self._on_device_state)
        self.driver.temperature_read.connect(self._on_device_temp)
        self.driver.error.connect(lambda m: self.raise_alarm(f"恒温槽通信错误: {m}"))

        # 盒内温度传感器驱动：用户在界面选择串口后连接
        self.box_driver = BoxSensorDriver(parent=self)
        self.box_driver.state_changed.connect(self._on_box_state)
        self.box_driver.temperature_read.connect(self._on_box_temp)
        self.box_driver.error.connect(lambda m: self.raise_alarm(f"盒内温度传感器通信错误: {m}"))

        self.timer = QTimer(self)
        self.timer.setInterval(int(HISTORY_INTERVAL * 1000))
        self.timer.timeout.connect(self._tick)

    # ---- 连接管理 ----
    def connect_bath(self, port):
        """连接恒温槽（用户选择的串口）。"""
        if self.driver.is_connected:
            return
        self.raise_alarm(f"正在连接恒温槽（{port}）...")
        self.driver.connect_port(port)

    def connect_sensor(self, port):
        """连接盒内温度传感器（用户选择的串口）。"""
        if self.box_driver.is_connected:
            return
        self.raise_alarm(f"正在连接盒内温度传感器（{port}）...")
        self.box_driver.connect_port(port)

    def _on_device_state(self, connected, port):
        if connected:
            self.connected["恒温槽"] = True
            self.real_mode = True
            self.connected_port = port
            self.timer.start()
            self.raise_alarm(f"恒温槽连接成功（{port}）")
            if self.exp_state is ExpState.DISCONNECTED:
                self._set_exp_state(ExpState.CONNECTED)
            return
        # 断开或连接失败
        if self.real_mode or self.connected.get("恒温槽"):
            self.real_mode = False
            self.connected["恒温槽"] = False
            self.connected_port = ""
            # 真实会话结束：一律停表，禁止模拟趋近数据继续填充曲线
            self.timer.stop()
            self._set_exp_state(ExpState.DISCONNECTED)
            self.raise_alarm("恒温槽连接已断开")
        else:
            self.raise_alarm(f"连接失败：{port or '所选串口'} 上未发现恒温槽，请检查设备与接线")

    def _on_box_state(self, connected, port):
        """盒内温度传感器连接状态。"""
        if connected:
            self.connected["盒内温度传感器"] = True
            self.raise_alarm(f"盒内温度传感器连接成功（{port}）")
        elif self.connected.get("盒内温度传感器"):
            self.connected["盒内温度传感器"] = False
            self.raise_alarm("盒内温度传感器连接已断开")
        self.states_updated.emit()

    def _on_box_temp(self, temp):
        """盒内温度传感器读数（后台线程经信号队列进入 GUI 线程）。"""
        self.box_temp = temp
        self.states_updated.emit()

    def _on_device_temp(self, temp):
        """真实设备盒体温度读数（后台线程经信号队列进入 GUI 线程）。"""
        if self.real_mode:
            self.temp_current = temp
            self.states_updated.emit()

    def disconnect_all(self):
        for name in self.connected:
            self.connected[name] = False
        self.timer.stop()
        self.driver.disconnect()
        self.box_driver.disconnect()
        self.real_mode = False
        self.connected_port = ""
        self.raise_alarm("已断开设备连接")
        self._set_exp_state(ExpState.DISCONNECTED)

    def shutdown(self):
        """退出程序时关闭串口。"""
        self.driver.shutdown()
        self.box_driver.shutdown()

    def _set_exp_state(self, state):
        if self.exp_state is not state:
            self.exp_state = state
            self.exp_state_changed.emit(state)
        self.states_updated.emit()

    @property
    def unlocked(self):
        """设备连接后即解锁各功能模块（无需配置实验）。"""
        return self.exp_state is not ExpState.DISCONNECTED

    def raise_alarm(self, msg):
        self.alarms.appendleft((time.strftime("%H:%M:%S"), msg))
        self.alarm_raised.emit(msg)

    # ---- 控制命令（真实模式经 Modbus 下发）----
    def set_bath_temp(self, target):
        """设定恒温槽温度（水箱 SV）。"""
        if self.real_mode:
            if not self.driver.write_temperature(target):
                self.raise_alarm(f"恒温槽温度设定写入失败: {target:.1f} ℃")
        self.temp_target = target
        self.raise_alarm(f"恒温槽温度设定更新: 目标 {target:.1f} ℃")

    def set_run(self, on):
        """设备运行开关（启动/停止）。"""
        if self.real_mode:
            if not self.driver.write_run(on):
                self.raise_alarm(f"设备{'启动' if on else '停止'}命令写入失败")
        self.run_on = bool(on)
        self.raise_alarm(f"设备{'已启动' if on else '已停止'}")

    # ---- 定时刷新 ----
    def _tick(self):
        h = self.history
        h["temp"].append(self.temp_current)
        h["temp_t"].append(self.temp_target)
        self.states_updated.emit()
