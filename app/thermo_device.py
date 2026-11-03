"""温控模块（低温恒温槽/外循环水箱）Modbus RTU 驱动（自动扫描串口连接）。

设备为 Modbus RTU 从机（doc/外循环水箱 协议文档）：
  - 通讯：115200 bps（建议值）、8 数据位、1 停止位、无校验或偶校验；
    从机地址默认 1（可通过 Add 参数修改，范围 1-32）
  - PV 实时温度：FC04 读输入寄存器 0x0000 起 2 个寄存器，IEEE754 浮点（℃），
    范围 -50.00~300.00
  - SV 设定温度：FC03 读 / FC10 写保持寄存器 0x0000 起 2 个寄存器（IEEE754 浮点）
  - 设备无系统总开关（恒温槽常开运行），write_system_switch 为兼容保留的空操作

连接流程：用户在界面选择串口 → 该串口依次尝试 8N1/8E1 × 从站地址 1~32 →
FC04 读 PV 合法（-50~300 ℃）即认定找到设备；连接后每 2s 轮询实测温度。
"""
import logging
import struct
import threading
import time

logging.getLogger("pymodbus").setLevel(logging.ERROR)

from PyQt5.QtCore import QObject, pyqtSignal
from serial.tools import list_ports
from pymodbus.client import ModbusSerialClient

DEFAULT_BAUD = 115200
PV_ADDR = 0x0000      # 输入寄存器：实时温度（FLOAT32，2 寄存器）
SV_ADDR = 0x0000      # 保持寄存器：设定温度（FLOAT32，2 寄存器）
SPL_ADDR = 0x0013     # 保持寄存器：最小温度设定值软限位（FLOAT32，出厂 -10）
RUN_ADDR = 0x0017     # 保持寄存器：循环运行开关（FC06 写 1=启动，0=停止）
PV_MIN, PV_MAX = -50.0, 300.0
SV_MIN, SV_MAX = -20.0, 50.0   # 软件侧设定范围
SCAN_SLAVES = range(1, 33)   # 从机地址默认 1，可改范围 1-32
PARITIES = ("N", "E")        # 文档：无校验或偶校验
POLL_INTERVAL = 2.0   # 温度轮询周期 s
MAX_FAILS = 3         # 连续读取失败次数达到后判定断开
SETTLE = 0.5          # 打开串口后的稳定等待 s
PROBE_TIMEOUT = 0.4   # 扫描探测超时 s（缩短以加快全地址扫描）
TX_GAP = 0.4          # 两次事务最小间隔 s（设备对背靠背请求会丢弃后一帧）
WRITE_GAP = 1.0       # 写事务后的额外间隔 s（设备写 SV 提交期间丢弃后续请求）


class ThermoModbusDriver(QObject):
    """温控模块串口驱动：自动扫描连接 + 温度轮询，全部在后台线程执行。"""

    state_changed = pyqtSignal(bool, str)   # (已连接, 串口名)
    temperature_read = pyqtSignal(float)    # 实时温度 ℃
    error = pyqtSignal(str)

    def __init__(self, baudrate=DEFAULT_BAUD, timeout=1.0, parent=None):
        super().__init__(parent)
        self.baudrate = baudrate
        self.timeout = timeout
        self._client = None
        self._port = ""
        self._slave = 1
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

    # ---- 用户指定串口连接 ----
    def connect_port(self, port):
        """后台线程连接用户指定的串口（扫描从站地址 1~32 × 校验位 N/E）。"""
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

    def _raw_transaction(self, sp, slave, pdu: bytes, resp_fc: int, resp_len: int,
                         timeout=0.8, post_gap=TX_GAP):
        """发送原始 RTU 报文，并按（从站地址+功能码+帧长+CRC）扫描匹配应答。

        未匹配字节保留在缓冲区继续等待，直到超时；返回完整应答帧
        （含 addr/fc/CRC），失败返回 None。写事务用 post_gap 拉长下一事务间隔。
        """
        try:
            # 最小事务间隔：设备对背靠背请求会丢弃后一帧
            wait = self._next_tx_ok - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            frame = bytes([slave]) + pdu
            frame += self._crc16(frame)
            sp.reset_input_buffer()
            sp.write(frame)
            self._next_tx_ok = time.monotonic() + post_gap
            deadline = time.monotonic() + timeout
            buf = bytearray()
            while time.monotonic() < deadline:
                n = sp.in_waiting
                chunk = sp.read(n if n else 1)
                if chunk:
                    buf += chunk
                for i in range(0, len(buf) - resp_len + 1):
                    if buf[i] != slave or buf[i + 1] != resp_fc:
                        continue
                    cand = bytes(buf[i:i + resp_len])
                    if self._crc16(cand[:-2]) == cand[-2:]:
                        return cand
            return None
        except Exception:
            return None

    def _read_pv(self, sp, slave, timeout=0.8):
        """读实时温度 PV（FC04 @ 0x0000，2 寄存器 FLOAT32），非法读数返回 None。"""
        pdu = b"\x04" + PV_ADDR.to_bytes(2, "big") + b"\x00\x02"
        resp = self._raw_transaction(sp, slave, pdu, resp_fc=0x04, resp_len=9,
                                     timeout=timeout)
        if not resp or resp[2] != 0x04:
            return None
        temp = struct.unpack(">f", resp[3:7])[0]
        if not PV_MIN <= temp <= PV_MAX:
            return None
        return temp

    def _try_connect(self, port):
        for parity in PARITIES:
            try:
                client = ModbusSerialClient(port=port, baudrate=self.baudrate,
                                            parity=parity, timeout=self.timeout,
                                            retries=1)
                if not client.connect():
                    continue
                # Modbus RTU 半双工无需流控：显式关闭软/硬流控并释放 RTS/DTR 线路
                # （pyserial 打开串口默认拉高 RTS/DTR，RS485 适配器以 RTS 做收发
                # 方向控制时会导致发得出去、收不到应答）
                sp = client.socket
                sp.xonxoff = False
                sp.rtscts = False
                sp.dsrdtr = False
                sp.dtr = False
                sp.rts = False
                time.sleep(SETTLE)
                # 从机地址默认 1，依次扫描 1~32；读到合法 PV 即认定找到设备
                for slave in SCAN_SLAVES:
                    if self._stop.is_set():
                        client.close()
                        return False
                    if self._read_pv(sp, slave, timeout=PROBE_TIMEOUT) is not None:
                        with self._lock:
                            self._client = client
                            self._port = port
                            self._slave = slave
                        return True
                client.close()
            except Exception as ex:
                self.error.emit(f"扫描 {port} 失败: {ex}")
                return False
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

    # ---- 数据读写 ----
    def read_temperature(self):
        """读实时温度 PV（℃），失败返回 None。"""
        with self._lock:
            if not self._client:
                return None
            return self._read_pv(self._client.socket, self._slave, self.timeout)

    def _read_float(self, sp, slave, addr, timeout=0.8):
        """FC03 读 2 寄存器 FLOAT32（大端），失败返回 None。"""
        pdu = b"\x03" + addr.to_bytes(2, "big") + b"\x00\x02"
        resp = self._raw_transaction(sp, slave, pdu, resp_fc=0x03, resp_len=9,
                                     timeout=timeout)
        if not resp or resp[2] != 0x04:
            return None
        return struct.unpack(">f", resp[3:7])[0]

    def _write_float(self, sp, slave, addr, value, timeout=0.8):
        """FC10 写 2 寄存器 FLOAT32（大端），回显校验，写后拉长事务间隔。"""
        pdu = (b"\x10" + addr.to_bytes(2, "big") + b"\x00\x02\x04"
               + struct.pack(">f", value))
        resp = self._raw_transaction(sp, slave, pdu, resp_fc=0x10, resp_len=8,
                                     timeout=timeout, post_gap=WRITE_GAP)
        # FC10 应答为回显：起始地址+数量与请求一致即成功
        return bool(resp) and resp[2:6] == pdu[1:5]

    def read_setpoint(self):
        """读设定温度 SV（℃），失败返回 None。"""
        with self._lock:
            if not self._client:
                return None
            sv = self._read_float(self._client.socket, self._slave, SV_ADDR,
                                  timeout=self.timeout)
            return sv if sv is not None and PV_MIN <= sv <= PV_MAX else None

    def write_temperature(self, temp_c):
        """下发设定温度 SV（FC10 写 0x0000 起 2 寄存器，IEEE754 浮点）。

        软件范围 -20~50 ℃。设备侧另有 SPL 软限位（出厂 -10）：设定低于
        SPL 时先放宽 SPL 再写 SV，否则设备拒绝。
        """
        temp_c = min(SV_MAX, max(SV_MIN, temp_c))
        with self._lock:
            if not self._client:
                return False
            sp = self._client.socket
            slave = self._slave
            if temp_c < 0:
                spl = self._read_float(sp, slave, SPL_ADDR, timeout=self.timeout)
                if spl is not None and temp_c < spl:
                    if not self._write_float(sp, slave, SPL_ADDR, temp_c,
                                             timeout=self.timeout):
                        return False
            return self._write_float(sp, slave, SV_ADDR, temp_c,
                                     timeout=self.timeout)

    def write_run(self, on):
        """运行开关（FC06 写保持寄存器 0x0023：1=启动，0=停止）。"""
        with self._lock:
            if not self._client:
                return False
            pdu = (b"\x06" + RUN_ADDR.to_bytes(2, "big")
                   + int(bool(on)).to_bytes(2, "big"))
            resp = self._raw_transaction(
                self._client.socket, self._slave, pdu, resp_fc=0x06, resp_len=8,
                timeout=self.timeout, post_gap=WRITE_GAP)
            # FC06 应答为请求回显，校验数据段一致
            return bool(resp) and resp[2:6] == pdu[1:5]

    def read_run(self):
        """读运行开关状态（0x0023），失败返回 None。"""
        with self._lock:
            if not self._client:
                return None
            pdu = b"\x03" + RUN_ADDR.to_bytes(2, "big") + b"\x00\x01"
            resp = self._raw_transaction(
                self._client.socket, self._slave, pdu, resp_fc=0x03, resp_len=7,
                timeout=self.timeout)
            if not resp or resp[2] != 0x02:
                return None
            return int.from_bytes(resp[3:5], "big")

    def write_system_switch(self, on):
        """兼容保留：旧设备的系统总开关，新设备用 write_run。"""
        return self.write_run(on)

    def shutdown(self):
        """停止轮询并关闭串口。"""
        self._stop.set()
        self._close_port()

    def disconnect(self):
        """断开连接并停止轮询线程。"""
        self._stop.set()
        self._close_port()

    def _close_port(self):
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
                self._port = ""
                self._slave = 1
