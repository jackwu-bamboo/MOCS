"""主窗口：三栏仪表盘，布局对应 doc/整体UI设计/gui.png。

左栏：控制模块参数设置 / 检测模块参数设置（各条目可展开）
中栏：明场显微成像 / 心脏搏动曲线 / 多通道电生理信号实时显示
右栏：培养环境实时参数 / TEER / 电化学结果 / 干预参数设置 / 工作日志
未开发模块以“待开发”占位，后续逐项接入。
"""
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QDialog, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QListWidget, QMainWindow, QPushButton, QVBoxLayout,
                             QWidget)

from app.camera_view import MicroscopeView
from app.external_app import ExternalAppView
from app.pages.workflow import WorkflowPage
from app.simulator import DeviceSimulator
from app.widgets import Card, CollapsibleSection, ValueCard

PENDING = "待开发"
LOG_MAX = 200
ELECTRO_EXE = r"C:\Program Files\JetBrains\PyCharm 2024.3.5\bin\pycharm64.exe"


def _wrap(layout):
    w = QWidget()
    w.setLayout(layout)
    return w


def _pending_label(text=PENDING):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: #5f7d78;")
    return lbl


def _placeholder_card(title):
    card = Card(title)
    card.body.addWidget(_pending_label(), 1)
    return card


def _external_card(title, exe):
    """嵌入外部程序主窗口的卡片。"""
    card = Card(title)
    view = ExternalAppView(exe, parent=card)
    card.body.addWidget(view, 1)
    card.external_view = view
    return card


def _pending_section(title):
    sec = CollapsibleSection(title)
    sec.add_widget(_pending_label())
    return sec


class ModuleGroup(QFrame):
    """设计图中的模块分组：蓝色边框 + 标题 + 可展开条目。"""

    def __init__(self, title):
        super().__init__()
        self.setObjectName("ModuleGroup")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(8, 8, 8, 8)
        self.body.setSpacing(8)
        t = QLabel(title)
        t.setObjectName("ModuleTitle")
        t.setAlignment(Qt.AlignCenter)
        self.body.addWidget(t)

    def add_widget(self, widget):
        self.body.addWidget(widget)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多器官芯片培养盒集成控制软件")
        self.resize(1480, 840)
        self.setMinimumSize(1280, 800)
        self.sim = DeviceSimulator(self)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        cols = QHBoxLayout()
        cols.setContentsMargins(12, 12, 12, 12)
        cols.setSpacing(12)
        cols.addWidget(self._build_left(), 2)
        cols.addWidget(self._build_middle(), 6)
        cols.addWidget(self._build_right(), 2)
        root.addLayout(cols, 1)

        self.device_dialog = QDialog(self)
        self.device_dialog.setWindowTitle("设备连接")
        self.device_dialog.resize(720, 520)
        QVBoxLayout(self.device_dialog).addWidget(WorkflowPage(self.sim))

        self.sim.states_updated.connect(self._refresh)
        self.sim.alarm_raised.connect(self._on_alarm)
        self._refresh()

        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._tick_clock)
        clock_timer.start(1000)
        self._tick_clock()

    # ---- 顶部栏 ----
    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("多器官芯片培养盒集成控制软件")
        title.setObjectName("HeaderTitle")
        self.dev_status = QLabel()
        btn_connect = QPushButton("设备连接")
        btn_connect.clicked.connect(self._open_device_dialog)
        self.clock = QLabel()
        self.clock.setObjectName("Clock")
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(self.dev_status)
        hl.addSpacing(16)
        hl.addWidget(btn_connect)
        hl.addSpacing(16)
        hl.addWidget(self.clock)
        return header

    # ---- 左栏：控制 / 检测模块参数设置 ----
    def _build_left(self):
        col = QVBoxLayout()
        col.setSpacing(12)
        col.addWidget(self._build_control_group())
        col.addWidget(self._build_detect_group())
        col.addStretch(1)
        return _wrap(col)

    def _build_microscope_card(self):
        card = Card("明场显微成像实时显示")
        self.microscope = MicroscopeView()
        card.body.addWidget(self.microscope, 1)
        return card

    def _build_control_group(self):
        g = ModuleGroup("控制模块参数设置")
        env = CollapsibleSection("器官芯片培养环境控制", expanded=True)
        env.add_widget(self._build_temp_control_section())
        env.add_widget(self._build_gas_section())
        env.add_widget(_pending_section("微泵驱动参数"))
        g.add_widget(env)
        g.add_widget(_pending_section("电动载物台控制"))
        return g

    def _build_detect_group(self):
        g = ModuleGroup("检测模块参数设置")
        for title in ("明场显微成像及分析参数设置", "电生理检测设置",
                      "采样加样设置", "电化学检测设置", "TEER检测设置"):
            g.add_widget(_pending_section(title))
        return g

    def _build_temp_control_section(self):
        """培养盒中温度：恒温槽目标温度设定（已接入 set_bath_temp）。"""
        sec = CollapsibleSection("培养盒中温度", expanded=True)
        row = QHBoxLayout()
        row.addWidget(QLabel("目标温度 (℃)"))
        self.sp_bath = QDoubleSpinBox()
        self.sp_bath.setRange(-20.0, 50.0)
        self.sp_bath.setDecimals(1)
        self.sp_bath.setValue(self.sim.temp_target)
        self.sp_bath.setMinimumWidth(70)
        row.addWidget(self.sp_bath, 1)
        self.btn_apply_temp = QPushButton("应用")
        self.btn_apply_temp.clicked.connect(
            lambda: self.sim.set_bath_temp(self.sp_bath.value()))
        row.addWidget(self.btn_apply_temp)
        sec.add_widget(_wrap(row))
        self.temp_section = sec
        return sec

    def _build_gas_section(self):
        """培养盒中氧气和二氧化碳浓度：设定值（%），经 STX 气体单元下发。"""
        sec = CollapsibleSection("培养盒中氧气和二氧化碳浓度", expanded=True)
        self.gas_spins = {}
        for key, name, vmax in (("co2", "二氧化碳浓度 (%)", 20.0), ("o2", "氧气浓度 (%)", 100.0)):
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            sp = QDoubleSpinBox()
            sp.setRange(0.0, vmax)
            sp.setDecimals(1)
            sp.setValue(self.sim.gas[key]["sv"])
            sp.setMinimumWidth(70)
            row.addWidget(sp, 1)
            btn = QPushButton("应用")
            btn.clicked.connect(lambda _, k=key, s=sp: self.sim.set_gas(k, s.value()))
            row.addWidget(btn)
            sec.add_widget(_wrap(row))
            self.gas_spins[key] = sp
        self.gas_section = sec
        return sec

    # ---- 中栏：实时显示 ----
    def _build_middle(self):
        col = QVBoxLayout()
        col.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(_placeholder_card("心脏类器官搏动曲线和搏动频率实时显示"), 1)
        top.addWidget(self._build_microscope_card(), 1)
        col.addLayout(top, 1)
        self.electro_card = _external_card("多通道电生理信号实时显示", ELECTRO_EXE)
        col.addWidget(self.electro_card, 1)
        return _wrap(col)

    # ---- 右栏：实时参数 / 干预 / 日志 ----
    def _build_right(self):
        col = QVBoxLayout()
        col.setSpacing(12)

        env = Card("器官芯片培养环境参数实时显示")
        self.val_bath = ValueCard("恒温槽温度", "℃")
        self.val_box = ValueCard("盒内温度", "℃")
        env.body.addWidget(self.val_bath)
        env.body.addWidget(self.val_box)
        grid = QGridLayout()
        grid.setSpacing(4)
        self.gas_labels = {}
        for r, (key, name) in enumerate((("co2_u3", "CO2 实测 (Unit3)"),
                                         ("co2_u4", "CO2 实测 (Unit4)"),
                                         ("o2", "O2 实测"))):
            v = QLabel("--")
            v.setObjectName("SideStat")
            grid.addWidget(QLabel(name), r, 0)
            grid.addWidget(v, r, 1)
            grid.addWidget(QLabel("%"), r, 2)
            self.gas_labels[key] = v
        env.body.addLayout(grid)
        col.addWidget(env)

        col.addWidget(_placeholder_card("TEER检测数值实时显示"))
        col.addWidget(_placeholder_card("电化学检测结果显示"))

        iv = Card("干预参数设置")
        iv.body.addWidget(_pending_section("电刺激"))
        iv.body.addWidget(_pending_section("化学刺激（即加样）"))
        col.addWidget(iv)

        log = Card("工作日志")
        self.log_list = QListWidget()
        self.log_list.setObjectName("AlarmList")
        log.body.addWidget(self.log_list, 1)
        col.addWidget(log, 1)
        return _wrap(col)

    # ---- 交互与刷新 ----
    def _open_device_dialog(self):
        self.device_dialog.show()
        self.device_dialog.raise_()

    def _refresh(self):
        sim = self.sim
        bath_ok = sim.connected.get("恒温槽", False)
        box_ok = sim.connected.get("盒内温度传感器", False)
        self.dev_status.setText(
            f"恒温槽: {'已连接' if bath_ok else '未连接'}    "
            f"盒内传感器: {'已连接' if box_ok else '未连接'}")
        self.temp_section.setEnabled(sim.unlocked)
        self.gas_section.setEnabled(sim.connected.get("气体单元", False))
        self.val_bath.set_value(f"{sim.temp_current:.2f}" if bath_ok else "--")
        self.val_box.set_value(
            f"{sim.box_temp:.2f}" if box_ok and sim.box_temp is not None else "--")
        for key, lbl in self.gas_labels.items():
            v = sim.gas_pv.get(key)
            lbl.setText(f"{v:.2f}" if v is not None else "--")

    def _on_alarm(self, msg):
        ts, _ = self.sim.alarms[0]
        self.log_list.insertItem(0, f"[{ts}] {msg}")
        while self.log_list.count() > LOG_MAX:
            self.log_list.takeItem(self.log_list.count() - 1)

    def _tick_clock(self):
        self.clock.setText(time.strftime("%Y-%m-%d %H:%M:%S"))

    def closeEvent(self, event):
        # 退出时关闭嵌入的外部程序、串口与轮询线程
        self.electro_card.external_view.shutdown()
        self.microscope.shutdown()
        self.sim.shutdown()
        super().closeEvent(event)
