"""温控模块 Modbus RTU 驱动（自动扫描串口连接）。

连接流程与 ThermostaticModule C# Demo 保持一致：
  1. 枚举本机串口，逐个以 RTU 模式打开；
  2. 读输入寄存器 0x701（CheckAddress，FC04），值等于 0x0F0F（CheckValue）即认定
     找到设备（从站地址 0x42），等价于 C# Demo 的 createModbus + ConnectState；
  3. 连接成功后启动轮询线程，每 2s 读取实测温度（对应 C# pressureTimer）。

寄存器协议（与 ThermostaticModule/Form1.cs 一致）：
  0xB000 系统总开关（写线圈 0/1）
  0xB010 温度设定（保持寄存器，值 = ℃ × 10，范围 0~100 ℃）
  0xB020 温度读取（传感器寄存器，值 = ℃ × 10）
  0x701  连接校验（输入寄存器 FC04，应读到 0x0F0F）

接入真实设备后，设备会在串口上持续推送测量数据帧（非 Modbus 报文），
pymodbus 每次发送请求前会丢弃缓冲区中的残留流数据并打印告警——属正常现象，
本模块将 pymodbus 日志级别设为 ERROR 以保持终端整洁。
"""
import logging

logging.getLogger("pymodbus").setLevel(logging.ERROR)

import threading
import time

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
SCAN_DELAY = 2.0      # 软件启动后延迟开始扫描连接的时间 s


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
        # 软件启动后延迟 2s 再开始扫描连接（期间请求停止则直接退出）
        if self._stop.wait(SCAN_DELAY):
            return
        for port in [p.device for p in list_ports.comports()]:
            if self._stop.is_set():
                return
            if self._try_connect(port):
                self.state_changed.emit(True, self._port)
                self._poll_loop()
                return
        self.state_changed.emit(False, "")

    @staticmethod
    def _crc16(data: bytes) -> bytes:
        """Modbus RTU CRC16，线上低字节在前。"""
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc.to_bytes(2, "little")

    def _raw_transaction(self, sp, pdu: bytes, resp_fc: int, resp_len: int, timeout=0.8):
        """发送原始 RTU 报文，并在推流噪声中扫描匹配的应答帧。

        pymodbus 的 RTU 解帧器命中一帧（含被跳过的推流帧）时按整段缓冲区长度
        消费数据，应答帧前面若有推流帧，应答会被当垃圾一起丢掉——加热推流期间
        读数因此长时间失败。这里直接走 pyserial：清空缓冲→发送→按
        (从站地址+功能码+帧长+CRC) 逐字节扫描应答，未匹配字节保留继续等待，
        直到超时。返回完整应答帧（含 addr/fc/CRC），失败返回 None。
        """
        try:
            frame = bytes([SERVER_ADDR]) + pdu
            frame += self._crc16(frame)
            sp.reset_input_buffer()
            sp.write(frame)
            deadline = time.monotonic() + timeout
            buf = bytearray()
            while time.monotonic() < deadline:
                n = sp.in_waiting
                chunk = sp.read(n if n else 1)
                if chunk:
                    buf += chunk
                for i in range(0, len(buf) - resp_len + 1):
                    if buf[i] != SERVER_ADDR or buf[i + 1] != resp_fc:
                        continue
                    cand = bytes(buf[i:i + resp_len])
                    if self._crc16(cand[:-2]) == cand[-2:]:
                        return cand
            return None
        except Exception:
            return None

    def _try_connect(self, port):
        try:
            client = ModbusSerialClient(port=port, baudrate=self.baudrate, timeout=self.timeout)
            if not client.connect():
                return False
            # Modbus RTU 半双工无需任何流控：显式关闭软/硬流控并释放 RTS/DTR 线路。
            # pyserial 打开串口时默认拉高 RTS/DTR，若 RS485 适配器用 RTS 做收发
            # 方向控制，RTS 常高会使适配器停留在发送态、接收器关闭——表现为
            # 发得出去、收不到应答（与 C# Demo 抓包中 RTS/DTR=DISABLE 不一致）。
            sp = client.socket
            sp.xonxoff = False
            sp.rtscts = False
            sp.dsrdtr = False
            sp.dtr = False
            sp.rts = False
            # 打开串口的电平跳变会使设备复位重启（实测：开串口后 ~2s 内输出
            # EasyLogger 启动 banner），需等设备启动完成再握手
            time.sleep(2.0)
            # 握手：FC04 读 0x701，值等于 0x0F0F 即认定找到设备（与 0xB020 温度
            # 读取同为输入寄存器 FC04；设备对 FC06 写 0x701 不响应，不能先写后读）
            pdu = b"\x04" + CHECK_ADDR.to_bytes(2, "big") + b"\x00\x01"
            resp = self._raw_transaction(sp, pdu, resp_fc=0x04, resp_len=7, timeout=1.0)
            if resp and int.from_bytes(resp[3:5], "big") == CHECK_VALUE:
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
        """读顶盖实测温度（℃ = 寄存器值 / 10），失败返回 None。

        寄存器布局（0xB020 起输入寄存器 FC04，与 C# Demo readSensor 一致）：
          0xB020 = 顶盖实测温度（×10 格式；系统总开关关闭时为 0，启动后随加热上升）
          0xB021 = 盒体/环境温度（约 18，不随加热变化）

        设备推流或启停切换时偶发读到坏值（如停止后读到 3302.6℃），
        超出合理范围（-5~60 ℃）的读数按失败处理，不进曲线和数据文件。
        """
        with self._lock:
            if not self._client:
                return None
            pdu = b"\x04" + TEMP_READ_ADDR.to_bytes(2, "big") + b"\x00\x01"
            resp = self._raw_transaction(
                self._client.socket, pdu, resp_fc=0x04, resp_len=7)
            if not resp:
                return None
            temp = int.from_bytes(resp[3:5], "big", signed=True) / TEMP_SCALE
            if not -5.0 <= temp <= 60.0:
                return None
            return temp

    def write_temperature(self, temp_c):
        """下发温度设定（℃×10 写入 0xB010，范围 0~100）。对应 C# writeRegister。"""
        temp_c = min(100.0, max(0.0, temp_c))
        with self._lock:
            if not self._client:
                return False
            pdu = (b"\x06" + LID_TEMP_SET_ADDR.to_bytes(2, "big")
                   + int(round(temp_c * TEMP_SCALE)).to_bytes(2, "big"))
            resp = self._raw_transaction(
                self._client.socket, pdu, resp_fc=0x06, resp_len=8)
            # FC06 应答为请求回显，校验数据段一致
            return bool(resp) and resp[2:6] == pdu[1:5]

    def write_system_switch(self, on):
        """系统总开关（对应 C# writeSwitch(0xB000)）。"""
        with self._lock:
            if not self._client:
                return False
            pdu = (b"\x05" + SYSTEM_SWITCH_ADDR.to_bytes(2, "big")
                   + (b"\xff\x00" if on else b"\x00\x00"))
            resp = self._raw_transaction(
                self._client.socket, pdu, resp_fc=0x05, resp_len=8)
            # FC05 应答为请求回显，校验数据段一致
            return bool(resp) and resp[2:6] == pdu[1:5]

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
