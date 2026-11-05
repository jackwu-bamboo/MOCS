# -*- coding: utf-8 -*-
"""SY-01B 注射泵串口协议封装（ASCII 协议，行为基于 2026-09 硬件联调实测）。

帧格式:  "/" + 地址字符 + 指令体 + "\r"
应答帧:  [杂散字节] "/" + 主机地址'0' + 状态字节 + [数据] + ETX(03) + CR LF
状态字节低5位 = 错误码 (0=无误, 15=指令溢出, 9=活塞过载 ...)

实测特性:
- 指令异步执行: ACK 立即返回, 动作后台执行
- 动作期间发新运动指令 → 错误15, 指令被拒; 错误码会锁存到后续应答
- 完成判据: 轮询 ?4 (活塞位置) / ?6 (阀位) 直到到达目标值
"""
import threading
import time

import serial

FULL_STROKE_STEPS = 12000  # 额定行程 30mm / 12000 步
SYRINGE_OPTIONS = (250.0, 500.0)  # 可选进样器满行程体积 μL (界面下拉框的全部选项)
DEFAULT_SYRINGE_UL = 500.0        # 默认进样器规格

ERROR_NAMES = {
    0: "无误", 1: "初始化错误", 2: "无效指令", 3: "无效参数",
    6: "EEPROM故障", 7: "设备未初始化", 9: "活塞过载",
    10: "阀过载", 11: "泵不允许移动", 12: "内部故障",
    14: "A/D转换器故障", 15: "指令溢出",
}


class PumpError(Exception):
    pass


class Sy01SerialPump:
    def __init__(self, port: str, baudrate: int = 9600, address_switch: int = 0,
                 steps_per_sec: float = 4000.0, stroke_ul: float = DEFAULT_SYRINGE_UL, log=None):
        self.port = port
        self.baudrate = baudrate
        self.addr = chr(0x31 + address_switch)
        self.steps_per_sec = max(100.0, steps_per_sec)
        self.stroke_ul = max(1.0, float(stroke_ul))
        self._log = log or (lambda msg: None)
        self._ser = None
        self._lock = threading.Lock()
        self._abort = False
        self.current_port = 1
        self.current_steps = 0

    # ---------- 连接 ----------
    def open(self):
        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=0.3)
        except serial.SerialException as e:
            raise PumpError(f"打开串口失败: {e}") from e
        self._log(f"[串口] 已连接 {self.port} @ {self.baudrate}, 地址'{self.addr}'")

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._log("[串口] 已断开")

    # ---------- 底层收发 ----------
    def _transact(self, body: str):
        """发送指令并解析一条应答, 返回 (err_code, data)。"""
        if not self._ser or not self._ser.is_open:
            raise PumpError("串口未连接")
        cmd = f"/{self.addr}{body}\r"
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(cmd.encode("ascii"))
            self._log(f"TX> {cmd.strip()}")
            deadline = time.time() + 0.5
            buf = b""
            while time.time() < deadline:
                if self._ser.in_waiting:
                    buf += self._ser.read(self._ser.in_waiting)
                    if b"\r" in buf:
                        break
                time.sleep(0.02)
        text = buf.decode("ascii", "ignore")
        i = text.find("/")
        if i < 0 or len(text) < i + 3:
            self._log(f"RX< 异常: {buf.hex(' ')}")
            return None, ""
        status = ord(text[i + 2])
        data = text[i + 3:].rstrip("\r\n\x03")
        err = status & 0x1F
        self._log(f"RX< 状态={ERROR_NAMES.get(err, err)} 数据={data!r}")
        return err, data

    # ---------- 查询 ----------
    def query_position(self):
        err, data = self._transact("?4")
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def query_valve(self):
        err, data = self._transact("?6")
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def query_status(self):
        return self._transact("Q")

    def query(self, body: str):
        return self._transact(body)

    # ---------- 完成等待 ----------
    def wait_position(self, target: int, timeout: float = 20.0) -> bool:
        """轮询活塞位置, 连续两次等于目标视为到位。"""
        end = time.time() + timeout
        last = None
        while time.time() < end:
            if self._abort:
                raise PumpError("操作已中止")
            pos = self.query_position()
            if pos is not None and pos == target == last:
                self.current_steps = target
                return True
            last = pos
            time.sleep(0.15)
        return False

    def wait_valve(self, port: int, timeout: float = 6.0) -> bool:
        """轮询阀位, 连续两次等于目标才确认(阀转动会路过中间端口)。"""
        end = time.time() + timeout
        hits = 0
        while time.time() < end:
            if self._abort:
                raise PumpError("操作已中止")
            p = self.query_valve()
            if p == port:
                hits += 1
                if hits >= 2:
                    time.sleep(0.3)  # 阀机械稳定
                    self.current_port = port
                    return True
            else:
                hits = 0
            time.sleep(0.15)
        return False

    # ---------- 动作 ----------
    def _motion(self, body: str, verify, desc: str, max_tries: int = 3):
        """发送运动指令: 错误15等待重试, 以 verify() 轮询确认完成。"""
        for attempt in range(max_tries):
            err, _ = self._transact(body)
            if self._abort:
                raise PumpError("操作已中止")
            if err not in (0, 15, None):
                raise PumpError(f"{desc}: {ERROR_NAMES.get(err, f'错误{err}')}")
            try:
                if verify():
                    return
            except PumpError:
                if attempt == max_tries - 1:
                    raise
            if attempt < max_tries - 1:
                self._log(f"[重试] {desc} 未确认 (第{attempt + 1}次)")
                time.sleep(2.0)
        raise PumpError(f"{desc}: 多次尝试未确认完成")

    def init_pump(self):
        """半力度初始化 (250 / 500 μL 进样器均用半力度), 轮询位置归零确认。"""
        self._log("[初始化] Z1R 半力度 ...")

        def verify():
            deadline = time.time() + 22
            seen_move = False
            while time.time() < deadline:
                if self._abort:
                    raise PumpError("操作已中止")
                pos = self.query_position()
                if pos is None:
                    time.sleep(0.3)
                    continue
                if pos != 0:
                    seen_move = True
                if seen_move and pos == 0:
                    time.sleep(0.3)
                    if self.query_position() == 0:
                        self.current_steps = 0
                        return True
                time.sleep(0.3)
            return False

        self._motion("Z1R", verify, desc="初始化")
        self.current_port = 1
        self._log("[初始化] 完成")

    def valve_goto(self, port: int):
        port = int(port)

        def verify():
            return self.wait_valve(port, timeout=4.0)

        cw = port >= self.current_port
        self._motion(f"{'I' if cw else 'O'}{port}R", verify, desc=f"阀→Port {port}")
        self.current_port = port

    def plunger_goto(self, steps: int):
        steps = max(0, min(FULL_STROKE_STEPS, int(steps)))
        est = abs(steps - self.current_steps) / self.steps_per_sec + 1.0

        def verify():
            return self.wait_position(steps, timeout=max(5.0, est + 3.0))

        self._motion(f"A{steps}R", verify, desc=f"活塞→{steps}")
        self.current_steps = steps

    # ---------- 体积换算 ----------
    def vol_to_steps(self, vol_ul: float) -> int:
        return int(round(FULL_STROKE_STEPS * vol_ul / self.stroke_ul))

    def steps_to_vol(self, steps: int) -> float:
        return steps / FULL_STROKE_STEPS * self.stroke_ul

    # ---------- 控制 ----------
    def emergency_stop(self):
        try:
            self._transact("T")
        except PumpError:
            pass
        self._abort = True
        self._log("[急停] 已发送 T")
