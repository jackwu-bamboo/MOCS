"""东海希多 STX 气体单元（CO2 / O2）驱动：经 HITLIB64_UNI.dll（STX-SDK ver 1.4）控制。

通道（StxControl.h ChType）：5 = CO2（Unit3 ch2），6 = CO2（Unit4 ch2），7 = O2，8 = 气体流量（本驱动不用）。
设定值与实测值单位均为 %。DLL 导出为 MSVC 修饰名，按 STX-SDK API 函数名映射后以 cdecl 调用。
串口参数同 StxSample：38400、7 数据位、偶校验、2 停止位；COM 口号直接填入 PORTSETTING.byPortNo。
"""
import ctypes
import os
import threading

from PyQt5.QtCore import QObject, pyqtSignal

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
DLL_PATH = os.path.join(VENDOR, "HITLIB64_UNI.dll")
SETTING_DIR = os.path.join(VENDOR, "setting_table") + os.sep

CH_CO2_U3, CH_CO2_U4, CH_O2 = 5, 6, 7
PV_CHANNELS = {"co2_u3": CH_CO2_U3, "co2_u4": CH_CO2_U4, "o2": CH_O2}
SET_CHANNELS = {"co2": (CH_CO2_U3, CH_CO2_U4), "o2": (CH_O2,)}   # CO2 两路同时下发同一设定值

ERR_OK = 0
QUICK_START, DISH, WSKMX, TEMP_MIDDLE = 0, 0, 0, 1   # StxSample 的默认值
EVEN_PARITY, TWO_STOP_BITS = 2, 2
POLL_INTERVAL = 2.0
MAX_FAILS = 3
MAX_PATH_LEN = 1024


class PORTSETTING(ctypes.Structure):
    _fields_ = [("dwBaudRate", ctypes.c_ulong), ("byDataBits", ctypes.c_ubyte),
                ("byParityBits", ctypes.c_ubyte), ("byStopBits", ctypes.c_ubyte),
                ("byPortNo", ctypes.c_ubyte), ("dwTimeOut", ctypes.c_ulong),
                ("nRetryCount", ctypes.c_short)]


class INITSTX(ctypes.Structure):
    _fields_ = [("nHeaterMode", ctypes.c_short), ("nVslType", ctypes.c_short),
                ("nChambType", ctypes.c_short), ("nRoomTemp", ctypes.c_short),
                ("dDishTopRef", ctypes.c_double), ("dDishBathRef", ctypes.c_double),
                ("dDishStageRef", ctypes.c_double), ("dWellTopRef", ctypes.c_double),
                ("dWellBathRef", ctypes.c_double), ("dWellStageRef", ctypes.c_double),
                ("sTableFolderPath", ctypes.c_char * MAX_PATH_LEN)]


_EXPORTS = {
    "init": ("?StxInit@@YAFPEAU_PORTSETTING@@PEAU_INITSTX@@@Z",
             [ctypes.POINTER(PORTSETTING), ctypes.POINTER(INITSTX)], ctypes.c_short),
    "terminate": ("?StxTerminate@@YAXXZ", [], None),
    "get_pv": ("?StxGetPv@@YAFFPEAN@Z", [ctypes.c_short, ctypes.POINTER(ctypes.c_double)], ctypes.c_short),
    "set_sv": ("?StxSetSv@@YAFFN@Z", [ctypes.c_short, ctypes.c_double], ctypes.c_short),
    "run": ("?StxRunChannel@@YAFF@Z", [ctypes.c_short], ctypes.c_short),
    "stop": ("?StxStopChannel@@YAFF@Z", [ctypes.c_short], ctypes.c_short),
}


def _load_dll():
    dll = ctypes.CDLL(DLL_PATH)
    for name, (mangled, args, res) in _EXPORTS.items():
        fn = getattr(dll, mangled)
        fn.argtypes, fn.restype = args, res
        setattr(dll, name, fn)
    return dll


class StxGasDriver(QObject):
    """STX 气体单元驱动：按 COM 口初始化、运行 CO2/O2 通道、周期读取实测值。

    所有 DLL 调用经同一把锁串行化（DLL 内部也是单通道串口访问）。
    """

    state_changed = pyqtSignal(bool, str)   # (已连接, 串口名)
    gas_read = pyqtSignal(dict)             # {"co2_u3": pv, "co2_u4": pv, "o2": pv}，失败为 None
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dll = None
        self._lock = threading.Lock()
        self._connected = False
        self._stop = threading.Event()
        self._thread = None

    @property
    def is_connected(self):
        return self._connected

    # ---- 连接 ----
    def connect_port(self, port):
        """后台线程初始化 STX 通信并进入读数循环。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._connect_and_poll, args=(port,), daemon=True)
        self._thread.start()

    def _connect_and_poll(self, port):
        try:
            com_no = int(port.upper().replace("COM", ""))
            if not self._init(com_no):
                self.error.emit(f"STX 初始化失败（串口 {port}），请检查串口与设备电源")
                self.state_changed.emit(False, port)
                return
        except Exception as ex:
            self.error.emit(f"STX 驱动加载/初始化异常: {ex}")
            self.state_changed.emit(False, port)
            return
        self.state_changed.emit(True, port)
        try:
            self._poll_loop()
        finally:
            self._terminate()
            self.state_changed.emit(False, "")

    def _init(self, com_no):
        if self._dll is None:
            self._dll = _load_dll()
        port = PORTSETTING(dwBaudRate=38400, byDataBits=7, byParityBits=EVEN_PARITY,
                           byStopBits=TWO_STOP_BITS, byPortNo=com_no, dwTimeOut=200, nRetryCount=3)
        init = INITSTX(nHeaterMode=QUICK_START, nVslType=DISH, nChambType=WSKMX, nRoomTemp=TEMP_MIDDLE)
        init.sTableFolderPath = SETTING_DIR.encode("mbcs")
        with self._lock:
            if self._dll.init(ctypes.byref(port), ctypes.byref(init)) != ERR_OK:
                return False
            for ch in (CH_CO2_U3, CH_CO2_U4, CH_O2):
                if self._dll.run(ch) != ERR_OK:
                    self.error.emit(f"气体通道 {ch} 启动失败")
            self._connected = True
        return True

    def _terminate(self):
        with self._lock:
            if self._connected:
                self._dll.stop(CH_CO2_U3)
                self._dll.stop(CH_CO2_U4)
                self._dll.stop(CH_O2)
                self._dll.terminate()
            self._connected = False

    def _poll_loop(self):
        fails = 0
        while not self._stop.is_set():
            data = self._read_all()
            if all(v is None for v in data.values()):
                fails += 1
                if fails >= MAX_FAILS:
                    self.error.emit("气体单元连续读取失败，已断开")
                    return
            else:
                fails = 0
                self.gas_read.emit(data)
            self._stop.wait(POLL_INTERVAL)

    def _read_all(self):
        out = {}
        for key, ch in PV_CHANNELS.items():
            value = ctypes.c_double()
            with self._lock:
                if not self._connected:
                    return {k: None for k in PV_CHANNELS}
                ok = self._dll.get_pv(ch, ctypes.byref(value)) == ERR_OK
            out[key] = value.value if ok else None
        return out

    # ---- 设定 ----
    def set_gas(self, key, value):
        """下发 CO2（两路）或 O2 设定值（%），返回是否全部成功。"""
        with self._lock:
            if not self._connected:
                return False
            return all(self._dll.set_sv(ch, float(value)) == ERR_OK for ch in SET_CHANNELS[key])

    # ---- 断开 ----
    def disconnect(self):
        self._stop.set()

    def shutdown(self):
        self.disconnect()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
