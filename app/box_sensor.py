"""盒内温度传感器（原温控模块，从站 0x42）Modbus RTU 驱动（手动选择串口连接）。

设备协议（原 ThermostaticModule C# Demo / 实测确认）：
  - 通讯：115200 bps、8 数据位、1 停止位、无校验；从站地址 0x42
  - 连接校验：FC04 读输入寄存器 0x701，值等于 0x0F0F 即认定找到设备
  - 温度读数：FC04 读输入寄存器 0xB020，值 = ℃ × 10

注意：打开串口的电平跳变会使该设备复位重启（串口输出 EasyLogger 启动
banner），需等待 ~2s 启动完成后再握手；设备会持续推送测量数据帧（非
Modbus 报文），读写采用原始 RTU 事务按（从站+功能码+帧长+CRC）扫描应答。
"""
import logging

logging.getLogger("pymodbus").setLevel(logging.ERROR)

import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal
from pymodbus.client import ModbusSerialClient

SERVER_ADDR = 0x42
CHECK_ADDR = 0x701
CHECK_VALUE = 0x0F0F
SYSTEM_SWITCH_ADDR = 0xB000   # 系统总开关（写线圈）：关闭时 0xB020 温度读数恒为 0
TEMP_READ_ADDR = 0xB020
TEMP_SCALE = 10.0
DEFAULT_BAUD = 115200
POLL_INTERVAL = 2.0   # 温度轮询周期 s
MAX_FAILS = 3         # 连续读取失败次数达到后判定断开
SETTLE = 2.0          # 打开串口后等待设备复位重启完成 s
TX_GAP = 0.4          # 两次事务最小间隔 s
TEMP_MIN, TEMP_MAX = -5.0, 60.0   # 合理范围，之外的读数按失败处理


class BoxSensorDriver(QObject):
    """盒内温度传感器串口驱动：手动指定串口连接 + 温度轮询，后台线程执行。"""

    state_changed = pyqtSignal(bool, str)   # (已连接, 串口名)
    temperature_read = pyqtSignal(float)    # 盒内实测温度 ℃
    error = pyqtSignal(str)

    def __init__(self, baudrate=DEFAULT_BAUD, timeout=1.0, parent=None):
        super().__init__(parent)
        self.baudrate = baudrate
        self.timeout = timeout
        self._client = None
        self._port = ""
        self._next_tx_ok = 0.0   # 下一事务最早发送时刻（保证最小事务间隔）
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._scan_thread = None

    @property
    def is_connected(self):
        return self._client is not None

    @property
    def port(self):
        return self._port

    # ---- 手动指定串口连接 ----
    def connect_port(self, port):
        """后台线程连接用户指定的串口。"""
        if self._scan_thread and self._scan_thread.is_alive():
            self._stop.set()
            self._scan_thread.join(timeout=3.0)
        self._stop.clear()
        self._scan_thread = threading.Thread(
            target=self._connect_and_poll, args=(port,), daemon=True)
        self._scan_thread.start()

    def _connect_and_poll(self, port):
        if self._try_connect(port):
            self.state_changed.emit(True, self._port)
            self._poll_loop()
            return
        self.state_changed.emit(False, port)

    # ---- 原始 RTU 事务 ----
    @staticmethod
    def _crc16(data: bytes) -> bytes:
        """Modbus RTU CRC16，线上低字节在前。"""
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc.to_bytes(2, "little")

    def _raw_transaction(self, sp, pdu: bytes, resp_fc: int, resp_len: int,
                         timeout=0.8):
        """发送原始 RTU 报文，并按（从站地址+功能码+帧长+CRC）扫描匹配应答。

        未匹配字节保留在缓冲区继续等待，直到超时；返回完整应答帧
        （含 addr/fc/CRC），失败返回 None。
        """
        try:
            # 最小事务间隔：设备对背靠背请求会丢弃后一帧
            wait = self._next_tx_ok - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            frame = bytes([SERVER_ADDR]) + pdu
            frame += self._crc16(frame)
            sp.reset_input_buffer()
            sp.write(frame)
            self._next_tx_ok = time.monotonic() + TX_GAP
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
            client = ModbusSerialClient(port=port, baudrate=self.baudrate,
                                        timeout=self.timeout, retries=1)
            if not client.connect():
                return False
            # Modbus RTU 半双工无需流控：显式关闭软/硬流控并释放 RTS/DTR 线路
            # （pyserial 打开串口默认拉高 RTS/DTR，RS485 适配器以 RTS 做收发
            # 方向控制时会导致发得出去、收不到应答）
            sp = client.socket
            sp.xonxoff = False
            sp.rtscts = False
            sp.dsrdtr = False
            sp.dtr = False
            sp.rts = False
            # 打开串口的电平跳变会使设备复位重启（串口输出 EasyLogger 启动
            # banner），需等设备启动完成再握手
            time.sleep(SETTLE)
            # 握手：FC04 读 0x701，值等于 0x0F0F 即认定找到设备
            pdu = b"\x04" + CHECK_ADDR.to_bytes(2, "big") + b"\x00\x01"
            resp = self._raw_transaction(sp, pdu, resp_fc=0x04, resp_len=7,
                                         timeout=1.0)
            if resp and int.from_bytes(resp[3:5], "big") == CHECK_VALUE:
                # 启动温度传感器（系统总开关置 1）：开关关闭时 0xB020 读数恒为 0
                self._write_system_switch(sp, True)
                with self._lock:
                    self._client = client
                    self._port = port
                return True
            client.close()
        except Exception as ex:
            self.error.emit(f"连接 {port} 失败: {ex}")
        return False

    def _poll_loop(self):
        """连接成功后的温度轮询。"""
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

    # ---- 数据读取 ----
    def read_temperature(self):
        """读盒内实测温度（℃ = 寄存器值 / 10），失败返回 None。

        设备推流或启停切换时偶发坏值，超出合理范围（-5~60 ℃）的读数
        按失败处理，由轮询下个周期重试。
        """
        with self._lock:
            if not self._client:
                return None
            pdu = b"\x04" + TEMP_READ_ADDR.to_bytes(2, "big") + b"\x00\x01"
            resp = self._raw_transaction(
                self._client.socket, pdu, resp_fc=0x04, resp_len=7,
                timeout=self.timeout)
            if not resp:
                return None
            temp = int.from_bytes(resp[3:5], "big", signed=True) / TEMP_SCALE
            if not TEMP_MIN <= temp <= TEMP_MAX:
                return None
            return temp

    def write_system_switch(self, on):
        """系统总开关（FC05 写线圈 0xB000）：启动/停止温度传感器。"""
        with self._lock:
            if not self._client:
                return False
            return self._write_system_switch(self._client.socket, on)

    def _write_system_switch(self, sp, on):
        pdu = (b"\x05" + SYSTEM_SWITCH_ADDR.to_bytes(2, "big")
               + (b"\xff\x00" if on else b"\x00\x00"))
        resp = self._raw_transaction(sp, pdu, resp_fc=0x05, resp_len=8,
                                     timeout=self.timeout)
        # FC05 应答为请求回显，校验数据段一致
        return bool(resp) and resp[2:6] == pdu[1:5]

    # ---- 连接管理 ----
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
