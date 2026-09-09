"""温控模块 Modbus RTU 驱动（自动扫描串口连接）。

连接流程与 ThermostaticModule C# Demo 保持一致：
  1. 枚举本机串口，逐个以 RTU 模式打开；
  2. 读保持寄存器 0x701（CheckAddress），值等于 0x0F0F（CheckValue）即认定
     找到设备（从站地址 0x42），等价于 C# Demo 的 createModbus + ConnectState；
  3. 连接成功后启动轮询线程，每 2s 读取实测温度（对应 C# pressureTimer）。

寄存器协议（与 ThermostaticModule/Form1.cs 一致）：
  0xB000 系统总开关（写线圈 0/1）
  0xB010 温度设定（保持寄存器，值 = ℃ × 10，范围 0~100 ℃）
  0xB020 温度读取（传感器寄存器，值 = ℃ × 10）
  0x701  连接校验（保持寄存器，应读到 0x0F0F）

接入真实设备后，设备会在串口上持续推送测量数据帧（非 Modbus 报文），
pymodbus 每次发送请求前会丢弃缓冲区中的残留流数据并打印告警——属正常现象，
本模块将 pymodbus 日志级别设为 ERROR 以保持终端整洁。
"""
import logging

logging.getLogger("pymodbus").setLevel(logging.ERROR)

import threading

from PyQt5.QtCore import QObject, pyqtSignal
from serial.tools import list_ports
from pymodbus.client import ModbusSerialClient

SERVER_ADDR = 0x42
CHECK_ADDR = 0x701
CHECK_VALUE = 0x0F0F
SYSTEM_SWITCH_ADDR = 0xB000
LID_TEMP_SET_ADDR = 0xB010
TEMP_READ_ADDR = 0xB020
TEMP_SCALE = 10.0
DEFAULT_BAUD = 115200
POLL_INTERVAL = 2.0   # 温度轮询周期 s（与 C# Demo pressureTimer 一致）
MAX_FAILS = 3         # 连续读取失败次数达到后判定断开


class ThermoModbusDriver(QObject):
    """温控模块串口驱动：自动扫描连接 + 温度轮询，全部在后台线程执行。"""

    state_changed = pyqtSignal(bool, str)   # (已连接, 串口名)
    temperature_read = pyqtSignal(float)    # 盒体实测温度 ℃
    error = pyqtSignal(str)

    def __init__(self, baudrate=DEFAULT_BAUD, timeout=1.0, parent=None):
        super().__init__(parent)
        self.baudrate = baudrate
        self.timeout = timeout
        self._client = None
        self._port = ""
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._scan_thread = None

    @property
    def is_connected(self):
        return self._client is not None

    @property
    def port(self):
        return self._port

    # ---- 自动扫描连接 ----
    def start_scan(self):
        """后台线程自动扫描串口并连接（应用启动时与手动重连时调用）。"""
        if self._scan_thread and self._scan_thread.is_alive():
            self._stop.set()
            self._scan_thread.join(timeout=3.0)
        self._stop.clear()
        self._scan_thread = threading.Thread(target=self._scan_and_poll, daemon=True)
        self._scan_thread.start()

    def _scan_and_poll(self):
        for port in [p.device for p in list_ports.comports()]:
            if self._stop.is_set():
                return
            if self._try_connect(port):
                self.state_changed.emit(True, self._port)
                self._poll_loop()
                return
        self.state_changed.emit(False, "")

    def _try_connect(self, port):
        try:
            client = ModbusSerialClient(port=port, baudrate=self.baudrate, timeout=self.timeout)
            if not client.connect():
                return False
            # 握手：写校验值 0x0F0F 到 0x701 并回读验证（对应 C# Parameter 的
            # CheckAddress/CheckValue 机制，等价于 createModbus + ConnectState）
            wr = client.write_register(CHECK_ADDR, CHECK_VALUE, device_id=SERVER_ADDR)
            if wr.isError():
                client.close()
                return False
            rr = client.read_holding_registers(CHECK_ADDR, count=1, device_id=SERVER_ADDR)
            if not rr.isError() and rr.registers and rr.registers[0] == CHECK_VALUE:
                with self._lock:
                    self._client = client
                    self._port = port
                return True
            client.close()
        except Exception as ex:
            self.error.emit(f"扫描 {port} 失败: {ex}")
        return False

    def _poll_loop(self):
        """连接成功后的温度轮询（对应 C# Demo 的 PressureTimer_Tick）。"""
        fails = 0
        while not self._stop.is_set():
            temps = self.read_temperature()
            if temps is None:
                fails += 1
                if fails >= MAX_FAILS:
                    self._close_port()
                    self.state_changed.emit(False, "")
                    return
            else:
                fails = 0
                self.temperature_read.emit(temps)
            self._stop.wait(POLL_INTERVAL)

    # ---- 数据读写 ----
    def read_temperature(self):
        """读盒体实测温度（原始 ℃ 值），失败返回 None。

        实测寄存器布局（0xB020 起输入寄存器 FC04）：
          0xB020 = 顶盖温度（系统未启动时为 0，暂不使用）
          0xB021 = 盒体温度（原始 ℃ 值，真机观察 18~19 随环境波动）
        """
        with self._lock:
            if not self._client:
                return None
            try:
                rr = self._client.read_input_registers(
                    TEMP_READ_ADDR, count=2, device_id=SERVER_ADDR)
                if rr.isError() or len(rr.registers) < 2:
                    return None
                return float(rr.registers[1])
            except Exception:
                return None

    def write_temperature(self, temp_c):
        """下发温度设定（℃×10 写入 0xB010，范围 0~100）。对应 C# writeRegister。"""
        temp_c = min(100.0, max(0.0, temp_c))
        with self._lock:
            if not self._client:
                return False
            try:
                rr = self._client.write_register(
                    LID_TEMP_SET_ADDR, int(round(temp_c * TEMP_SCALE)), device_id=SERVER_ADDR)
                return not rr.isError()
            except Exception:
                return False

    def write_system_switch(self, on):
        """系统总开关（对应 C# writeSwitch(0xB000)）。"""
        with self._lock:
            if not self._client:
                return False
            try:
                rr = self._client.write_coil(
                    SYSTEM_SWITCH_ADDR, bool(on), device_id=SERVER_ADDR)
                return not rr.isError()
            except Exception:
                return False

    def shutdown(self):
        """停止轮询并关闭串口。"""
        self._stop.set()
        self._close_port()

    def disconnect(self):
        """断开连接并停止轮询线程。"""
        self._stop.set()
        self._close_port()

    def shutdown(self):
        """退出程序时调用：停止线程并关闭串口。"""
        self.disconnect()

    def _close_port(self):
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
                self._port = ""
