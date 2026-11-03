# -*- coding: utf-8 -*-
"""SY-01B 注射泵手动测试台主窗口（分步验证，不含全流程）。"""
from collections import OrderedDict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtSerialPort import QSerialPortInfo
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from command_runner import CommandRunner
from port_config import (
    DEFAULT_PORT_COUNT, DEFAULT_PORT_MAP, load_config, role_color, save_config,
)
from command_runner import CommandRunner
from port_config import (
    DEFAULT_PORT_COUNT, DEFAULT_PORT_MAP, load_config, role_color, save_config,
)
from sy01_pump import PumpError, Sy01SerialPump
from valve_widget import ValveWidget
from sampling_workflow import (
    WORKFLOW_TYPES, build_workflow, delete_workflow, load_all, load_workflow,
    save_workflow,
)


class MainWindow(QMainWindow):
    log_sig = pyqtSignal(str)
    step_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动采样和分发控制模块")
        self.resize(1400, 860)
        self.pump = None
        self.port_count, self.mapping = load_config()
        self.wf_params, _, _, _ = load_workflow("默认方案")
        self.wf_running = False
        self.wf_steps = None
        self.wf_step_idx = 0
        self.log_sig.connect(self._append_log)

        self.runner = CommandRunner(self)
        self.runner.log.connect(self._append_log)
        self.runner.failed.connect(self._on_task_failed)
        self.runner.task_done.connect(self._on_task_done)
        self.runner.start()

        self._build_ui()
        self.step_sig.connect(self._on_step)
        self._refresh_ports()
        self._sync_valve_config()
        self._append_log("就绪。请选择串口并连接设备。")

    # ================= UI =================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        root.addWidget(self._build_left_panel(), 0)
        root.addWidget(self._build_right_panel(), 1)

    def _build_left_panel(self):
        panel = QWidget()
        panel.setFixedWidth(460)
        lay = QVBoxLayout(panel)

        # 设备连接
        gb = QGroupBox("设备连接")
        g = QGridLayout(gb)
        self.cmb_port = QComboBox()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh_ports)
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(["9600", "38400"])
        self.spn_addr = QSpinBox()
        self.spn_addr.setRange(0, 14)
        self.lbl_addr = QLabel("地址字符 '1'")
        self.spn_addr.valueChanged.connect(
            lambda v: self.lbl_addr.setText(f"地址字符 '{chr(0x31 + v)}'"))
        g.addWidget(self.cmb_port, 0, 0)
        g.addWidget(btn_refresh, 0, 1)
        g.addWidget(QLabel("波特率"), 1, 0)
        g.addWidget(self.cmb_baud, 1, 1)
        g.addWidget(QLabel("泵地址拨码"), 2, 0)
        g.addWidget(self.spn_addr, 2, 1)
        g.addWidget(self.lbl_addr, 3, 0, 1, 2)
        self.btn_connect = QPushButton("连接设备")
        self.btn_connect.clicked.connect(self._toggle_connect)
        g.addWidget(self.btn_connect, 4, 0)
        self.btn_stop = QPushButton("急停 (T)")
        self.btn_stop.clicked.connect(self._do_estop)
        g.addWidget(self.btn_stop, 4, 1)
        lay.addWidget(gb)

        lay.addWidget(self._build_workflow_group())

        # 日志
        gb4 = QGroupBox("日志")
        v4 = QVBoxLayout(gb4)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        v4.addWidget(self.log)
        lay.addWidget(gb4, 1)
        return panel

    def _build_workflow_group(self):
        gb = QGroupBox("自动流程")
        g = QGridLayout(gb)

        self.cmb_wftype = QComboBox()
        self.cmb_wftype.addItems(WORKFLOW_TYPES)
        self.cmb_wftype.currentTextChanged.connect(self._on_wftype_changed)
        g.addWidget(QLabel("流程类型"), 0, 0)
        g.addWidget(self.cmb_wftype, 0, 1)

        self.cmb_scheme = QComboBox()
        self._refresh_scheme_combo()
        self.edt_wf_name = QLineEdit()
        self.edt_wf_name.setPlaceholderText("输入方案名称")
        g.addWidget(QLabel("已存方案"), 1, 0)
        g.addWidget(self.cmb_scheme, 1, 1)
        btn_load = QPushButton("加载")
        btn_load.clicked.connect(self._load_wf_scheme)
        btn_del = QPushButton("删除")
        btn_del.clicked.connect(self._delete_wf_scheme)
        g.addWidget(btn_load, 1, 2)
        g.addWidget(btn_del, 1, 3)
        g.addWidget(QLabel("方案名称"), 2, 0)
        g.addWidget(self.edt_wf_name, 2, 1, 1, 2)

        self.cmb_source = QComboBox()
        self.cmb_detect = QComboBox()
        self._refresh_role_combos()
        g.addWidget(QLabel("源口(采样)"), 3, 0)
        g.addWidget(self.cmb_source, 3, 1)
        self.lbl_target = QLabel("目标口")
        g.addWidget(self.lbl_target, 4, 0)
        g.addWidget(self.cmb_detect, 4, 1)

        self.lbl_param1 = QLabel("分样体积")
        self.spn_sample = QDoubleSpinBox()
        self.spn_sample.setRange(1, 250)
        self.spn_sample.setValue(self.wf_params["sample_ul"])
        self.spn_sample.setSuffix(" μL")
        self.lbl_param2 = QLabel("排空气体积")
        self.spn_dead = QDoubleSpinBox()
        self.spn_dead.setRange(0, 5000)
        self.spn_dead.setValue(self.wf_params["dead_volume_ul"])
        self.spn_dead.setSuffix(" μL")
        self.lbl_param3 = QLabel("单口分发体积")
        self.spn_aliquot = QDoubleSpinBox()
        self.spn_aliquot.setRange(1, 250)
        self.spn_aliquot.setValue(self.wf_params.get("aliquot_ul", 25.0))
        self.spn_aliquot.setSuffix(" μL")
        self.spn_aliquot.setVisible(False)
        self.lbl_param3.setVisible(False)
        for sp in (self.spn_sample, self.spn_dead, self.spn_aliquot):
            sp.valueChanged.connect(self._invalidate_wf)
        g.addWidget(self.lbl_param1, 5, 0)
        g.addWidget(self.spn_sample, 5, 1)
        g.addWidget(self.lbl_param2, 6, 0)
        g.addWidget(self.spn_dead, 6, 1)
        g.addWidget(self.lbl_param3, 7, 0)
        g.addWidget(self.spn_aliquot, 7, 1)

        self.btn_save = QPushButton("保存方案")
        self.btn_save.clicked.connect(self._save_wf_params)
        g.addWidget(self.btn_save, 8, 0)
        self.btn_run = QPushButton("▶ 执行流程")
        self.btn_run.clicked.connect(self._run_workflow)
        g.addWidget(self.btn_run, 8, 1)
        self.btn_step = QPushButton("▶ 执行单步")
        self.btn_step.clicked.connect(self._run_one_step)
        g.addWidget(self.btn_step, 9, 0)
        self.btn_halt = QPushButton("■ 停止")
        self.btn_halt.clicked.connect(self._stop_workflow)
        g.addWidget(self.btn_halt, 9, 1)
        self.lbl_step = QLabel("就绪")
        self.lbl_step.setWordWrap(True)
        g.addWidget(self.lbl_step, 10, 0, 1, 3)
        return gb

    def _on_wftype_changed(self, wftype):
        multi = wftype == "四路分发+补液"
        self.lbl_param1.setText("采样体积" if multi else "分样体积")
        self.lbl_param2.setText("排空气体积")
        self.lbl_param3.setText("单口分发体积")
        self.lbl_param3.setVisible(multi)
        self.spn_aliquot.setVisible(multi)
        if multi:
            if self.spn_sample.value() < 100:
                self.spn_sample.setValue(150.0)
            self.spn_aliquot.setValue(25.0)
            self.cmb_detect.setEnabled(False)
        else:
            self.cmb_detect.setEnabled(True)
        self._invalidate_wf()

    def _refresh_scheme_combo(self):
        self.cmb_scheme.clear()
        names = sorted(load_all().keys())
        self.cmb_scheme.addItems(names)

    def _load_wf_scheme(self):
        name = self.cmb_scheme.currentText()
        if not name:
            return
        params, src_role, det_role, wf_type = load_workflow(name)
        idx = self.cmb_wftype.findText(wf_type)
        if idx >= 0:
            self.cmb_wftype.setCurrentIndex(idx)
        self.spn_sample.setValue(params["sample_ul"])
        self.spn_dead.setValue(params["dead_volume_ul"])
        self.spn_aliquot.setValue(params.get("aliquot_ul", 25.0))
        self.edt_wf_name.setText(name)
        for box, role in ((self.cmb_source, src_role), (self.cmb_detect, det_role)):
            idx = box.findText(role) if role else -1
            if idx >= 0:
                box.setCurrentIndex(idx)
        self._invalidate_wf()
        self._append_log(f"已加载方案「{name}」")

    def _invalidate_wf(self):
        if self.wf_steps is not None:
            self.wf_steps = None
            self.wf_step_idx = 0
            if not self.wf_running:
                self.step_sig.emit("参数已修改, 单步计数将从头开始")

    def _delete_wf_scheme(self):
        name = self.cmb_scheme.currentText()
        if not name:
            return
        if QMessageBox.question(self, "删除方案", f"确定删除方案「{name}」？") != QMessageBox.Yes:
            return
        delete_workflow(name)
        self._refresh_scheme_combo()
        self._append_log(f"方案「{name}」已删除")

    def _on_step(self, text):
        self.lbl_step.setText(text)

    def _save_wf_params(self):
        name = self.edt_wf_name.text().strip() or self.cmb_scheme.currentText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请先输入方案名称再保存。")
            return
        wf_type = self.cmb_wftype.currentText()
        if wf_type == "四路分发+补液":
            self.wf_params = dict(
                sample_ul=self.spn_sample.value(),
                dead_volume_ul=self.spn_dead.value(),
                aliquot_ul=self.spn_aliquot.value(),
                stroke_ul=250.0,
            )
        else:
            self.wf_params = dict(
                sample_ul=self.spn_sample.value(),
                dead_volume_ul=self.spn_dead.value(),
                stroke_ul=250.0,
            )
        save_workflow(name, self.wf_params,
                      self.cmb_source.currentText(), self.cmb_detect.currentText(),
                      wf_type)
        self._refresh_scheme_combo()
        idx = self.cmb_scheme.findText(name)
        if idx >= 0:
            self.cmb_scheme.setCurrentIndex(idx)
        self._append_log(f"方案「{name}」({wf_type}) 已保存")

    def _refresh_role_combos(self):
        sel_src = self.cmb_source.currentData() if hasattr(self, "cmb_source") else None
        sel_det = self.cmb_detect.currentData() if hasattr(self, "cmb_detect") else None
        self.cmb_source.clear()
        self.cmb_detect.clear()
        for role, port in self.mapping.items():
            if role.startswith("采样口"):
                self.cmb_source.addItem(f"{role}→P{port}", port)
            elif role.startswith("检测口"):
                self.cmb_detect.addItem(f"{role}→P{port}", port)
        for box, sel in ((self.cmb_source, sel_src), (self.cmb_detect, sel_det)):
            if sel is not None:
                idx = box.findData(sel)
                if idx >= 0:
                    box.setCurrentIndex(idx)

    def _on_step(self, text):
        self.lbl_step.setText(text)

    def _gather_workflow(self):
        """从 UI 收集端口与参数, 按流程类型生成步骤。失败返回 None。"""
        pump = self._require_pump()
        if not pump:
            return None
        wf_type = self.cmb_wftype.currentText()
        source = self.cmb_source.currentData()
        waste = self.mapping.get("备用")
        air = self.mapping.get("空气")
        medium = self.mapping.get("培养基")
        if wf_type == "四路分发+补液":
            params = dict(
                sample_ul=self.spn_sample.value(),
                dead_volume_ul=self.spn_dead.value(),
                aliquot_ul=self.spn_aliquot.value(),
                stroke_ul=250.0,
            )
        else:
            params = dict(
                sample_ul=self.spn_sample.value(),
                dead_volume_ul=self.spn_dead.value(),
                stroke_ul=250.0,
            )
        if wf_type == "四路分发+补液":
            detects = [p for role, p in sorted(self.mapping.items())
                       if role.startswith("检测口")]
            if None in (source, waste, air, medium) or len(detects) != 4:
                QMessageBox.warning(self, "提示", "端口映射缺少所需角色，请检查配置。")
                return None
            ports = dict(source=source, waste=waste, air=air,
                         medium=medium, detects=detects)
        else:
            detect = self.cmb_detect.currentData()
            if detect is None:
                QMessageBox.warning(self, "提示", "端口映射缺少所需角色，请检查配置。")
                return None
            ports = dict(source=source, detect=detect, waste=waste, air=air)
        return build_workflow(pump, ports, params, wf_type)

    def _set_wf_ui(self, running):
        self.valve.setEnabled(not running)
        for b in (self.btn_run, self.btn_step, self.btn_save):
            b.setEnabled(not running)

    def _run_workflow(self):
        pump = self._require_pump()
        if not pump or self.wf_running:
            return
        self.wf_steps = self._gather_workflow()
        if not self.wf_steps:
            return
        self.wf_step_idx = 0
        self.wf_running = True
        self._set_wf_ui(True)
        pump._abort = False

        def run():
            n = len(self.wf_steps)
            for i, (desc, fn) in enumerate(self.wf_steps, 1):
                self.step_sig.emit(f"({i}/{n}) {desc}")
                fn()
            self.step_sig.emit("✅ 流程完成")

        self.runner.submit("自动流程", run)

    def _run_one_step(self):
        pump = self._require_pump()
        if not pump or self.wf_running:
            return
        if self.wf_steps is None or self.wf_step_idx >= len(self.wf_steps):
            self.wf_steps = self._gather_workflow()
            self.wf_step_idx = 0
        if not self.wf_steps:
            return
        desc, fn = self.wf_steps[self.wf_step_idx]
        self.wf_running = True
        self._set_wf_ui(True)
        pump._abort = False
        self.step_sig.emit(f"单步 ({self.wf_step_idx + 1}/{len(self.wf_steps)}): {desc}")
        self.runner.submit("自动流程", fn)

    def _stop_workflow(self):
        if self.pump:
            self.pump.emergency_stop()
        self.runner.clear()

    def _finish_workflow(self, advance=True):
        if not self.wf_running:
            return
        self.wf_running = False
        self._set_wf_ui(False)
        if self.pump is not None:
            self.valve.set_current(self.pump.current_port)
            self._update_current_label()
        if advance and self.wf_steps:
            self.wf_step_idx += 1
        if self.wf_steps and self.wf_step_idx < len(self.wf_steps):
            self.step_sig.emit(f"下一步 ({self.wf_step_idx + 1}/{len(self.wf_steps)}): "
                               f"{self.wf_steps[self.wf_step_idx][0]}")
        elif self.wf_steps:
            self.step_sig.emit("✅ 全部步骤完成")

    def _build_right_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)

        self.valve = ValveWidget()
        self.valve.port_clicked.connect(self._on_valve_clicked)
        lay.addWidget(self.valve, 1)

        self.lbl_current = QLabel("当前端口：1")
        self.lbl_current.setAlignment(Qt.AlignCenter)
        self.lbl_current.setStyleSheet("font-size:15px; font-weight:700;")
        lay.addWidget(self.lbl_current)

        lay.addWidget(self._build_mapping_group())
        return panel

    def _build_mapping_group(self):
        gb = QGroupBox("端口角色映射（默认位置，可按实际管路调整）")
        g = QGridLayout(gb)
        self.map_spins = OrderedDict()
        roles = list(self.mapping.keys())
        half = (len(roles) + 1) // 2
        for i, role in enumerate(roles):
            col = (i // half) * 2
            row = i % half
            g.addWidget(QLabel(role), row, col)
            sp = QSpinBox()
            sp.setRange(1, self.port_count)
            sp.setValue(int(self.mapping[role]))
            sp.valueChanged.connect(self._on_mapping_changed)
            self.map_spins[role] = sp
            g.addWidget(sp, row, col + 1)
        r = half + 1
        g.addWidget(QLabel("阀总端口数"), r, 0)
        self.spn_count = QSpinBox()
        self.spn_count.setRange(4, 15)
        self.spn_count.setValue(self.port_count)
        self.spn_count.valueChanged.connect(self._on_count_changed)
        g.addWidget(self.spn_count, r, 1)
        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self._reset_mapping)
        btn_save = QPushButton("保存配置")
        btn_save.clicked.connect(self._save_mapping)
        g.addWidget(btn_default, r, 2)
        g.addWidget(btn_save, r, 3)
        return gb

    # ================= 日志 =================
    def _append_log(self, msg):
        import time
        self.log.appendPlainText(time.strftime("[%H:%M:%S] ") + msg)

    def _on_task_failed(self, msg):
        self._append_log(f"[错误] {msg}")
        self._finish_workflow(advance=False)
        if self.pump is not None:
            self.valve.set_current(self.pump.current_port)
            self._update_current_label()

    # ================= 设备 =================
    def _refresh_ports(self):
        self.cmb_port.clear()
        for info in QSerialPortInfo.availablePorts():
            self.cmb_port.addItem(info.portName())

    def _toggle_connect(self):
        if self.pump is None:
            port = self.cmb_port.currentText()
            if not port:
                QMessageBox.warning(self, "提示", "请先选择串口。")
                return
            pump = Sy01SerialPump(port, int(self.cmb_baud.currentText()),
                                  self.spn_addr.value(), steps_per_sec=4000.0,
                                  stroke_ul=self.wf_params["stroke_ul"],
                                  log=self.log_sig.emit)
            try:
                pump.open()
            except PumpError as e:
                QMessageBox.critical(self, "连接失败", str(e))
                return
            self.pump = pump
            self.btn_connect.setText("断开设备")
        else:
            self.runner.clear()
            self.pump.emergency_stop()
            self.pump.close()
            self.pump = None
            self.btn_connect.setText("连接设备")

    def _require_pump(self):
        if self.pump is None:
            QMessageBox.information(self, "提示", "请先连接设备。")
            return None
        return self.pump

    def _do_estop(self):
        if self.pump is None:
            return
        self.runner.clear()
        self.pump.emergency_stop()
        self._finish_workflow()
        self._append_log("[急停] 已发送 T 指令并清空队列")

    def _on_valve_clicked(self, port):
        if self.wf_running:
            QMessageBox.information(self, "提示", "自动流程执行中，请先停止。")
            return
        pump = self._require_pump()
        if not pump:
            return
        role = self.valve.role_of(port)
        desc = f"阀→Port {port}" + (f"({role})" if role else "")
        self.runner.submit(desc, lambda: pump.valve_goto(port))

    # ================= 状态同步 =================
    def _on_task_done(self, desc):
        if self.pump is None:
            return
        if desc == "自动流程":
            self._finish_workflow(advance=True)
        elif desc.startswith("阀"):
            self.valve.set_current(self.pump.current_port)
            self._update_current_label()
        self._append_log(f"完成: {desc}")

    def _update_current_label(self):
        port = self.valve.current_port
        role = self.valve.role_of(port)
        text = f"当前端口：{port}" + (f"（{role}）" if role else "")
        color = role_color(role) if role else "#334155"
        self.lbl_current.setText(text)
        self.lbl_current.setStyleSheet(f"font-size:15px; font-weight:700; color:{color};")

    # ================= 映射配置 =================
    def _read_mapping(self):
        return OrderedDict((role, sp.value()) for role, sp in self.map_spins.items())

    def _sync_valve_config(self):
        self.valve.set_config(self.port_count, self.mapping)
        self._update_current_label()

    def _on_mapping_changed(self):
        self.mapping = self._read_mapping()
        self._sync_valve_config()
        self._refresh_role_combos()

    def _on_count_changed(self, count):
        self.port_count = count
        for sp in self.map_spins.values():
            sp.setRange(1, count)
        self._on_mapping_changed()

    def _reset_mapping(self):
        self.port_count = DEFAULT_PORT_COUNT
        self.mapping = OrderedDict(DEFAULT_PORT_MAP)
        self.spn_count.blockSignals(True)
        self.spn_count.setValue(DEFAULT_PORT_COUNT)
        self.spn_count.blockSignals(False)
        for role, sp in self.map_spins.items():
            sp.blockSignals(True)
            sp.setValue(int(self.mapping[role]))
            sp.blockSignals(False)
        self._sync_valve_config()
        self._append_log("端口映射已恢复默认。")

    def _save_mapping(self):
        self.mapping = self._read_mapping()
        if not save_config(self.port_count, self.mapping):
            QMessageBox.warning(self, "保存失败", "存在重复端口或端口超出范围，请检查映射。")
            return
        self._append_log(f"配置已保存: 阀 {self.port_count} 口, "
                         + ", ".join(f"{r}={p}" for r, p in self.mapping.items()))

    # ================= 关闭 =================
    def closeEvent(self, event):
        self.runner.clear()
        self.runner.shutdown()
        self.runner.wait(1000)
        if self.pump is not None:
            self.pump.close()
        super().closeEvent(event)
