# -*- coding: utf-8 -*-
"""自动采样和分发控制模块 · 主窗口（自定义流程）。"""
import time

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtSerialPort import QSerialPortInfo
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QStyle, QStyleOptionViewItem, QStyledItemDelegate, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from command_runner import CommandRunner
from sampling_workflow import (
    INIT_WAIT_S, KIND_LABEL, TYPE_KIND, build_segments, delete_flow, execute_op,
    get_flow, get_settings, iter_ops, list_flows, op_label, save_flow,
    set_flow_speed_ul_s, set_port_count, set_syringe_ul, validate,
)
from styles import COMBO_VIEW_QSS
from sy01_pump import (
    DEFAULT_PULSE_PER_S, PULSE_MAX, PULSE_MIN, SYRINGE_OPTIONS, PumpError,
    Sy01SerialPump, flow_range_ul_s, ul_s_to_pulse,
)


class _ComboDelegate(QStyledItemDelegate):
    """下拉列表绘制: 选中/悬停行用深青绿底色, 不依赖主题的亮色高亮。"""

    def paint(self, painter, option, index):
        sel = bool(option.state & (QStyle.State_Selected | QStyle.State_MouseOver))
        painter.fillRect(option.rect, QColor("#1d4f47" if sel else "#122623"))
        opt = QStyleOptionViewItem(option)
        opt.state &= ~(QStyle.State_Selected | QStyle.State_MouseOver | QStyle.State_HasFocus)
        opt.palette.setColor(QPalette.Text, QColor("#e6fffa" if sel else "#cdeee8"))
        super().paint(painter, opt, index)

# 表单字段在哪些步骤类型下显示
FORM_FIELDS = {
    "port": ("切阀",),
    "ul": ("注入", "推出"),
    "sec": ("等待", "初始化"),
    "count": ("循环开始",),
}


class MainWindow(QMainWindow):
    log_sig = pyqtSignal(str)
    flow_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动采样和分发控制模块")
        self.resize(1440, 960)
        self.pump = None
        self.settings = get_settings()
        self.steps = []          # 当前编辑中的步骤列表
        self.op_iter = None      # 单步执行用的操作迭代器
        self.pending = None      # 下一条待执行的操作
        self.running = False
        self.log_sig.connect(self._append_log)
        self.flow_sig.connect(self._set_flow_text)

        self.runner = CommandRunner(self)
        self.runner.log.connect(self._append_log)
        self.runner.failed.connect(self._on_task_failed)
        self.runner.task_done.connect(self._on_task_done)
        self.runner.start()

        self._build_ui()
        for cmb in self.findChildren(QComboBox):
            view = cmb.view()
            view.setStyleSheet(COMBO_VIEW_QSS)
            pal = view.palette()
            pal.setColor(QPalette.Highlight, QColor("#1d4f47"))
            pal.setColor(QPalette.HighlightedText, QColor("#e6fffa"))
            pal.setColor(QPalette.Base, QColor("#122623"))
            pal.setColor(QPalette.Text, QColor("#cdeee8"))
            view.setPalette(pal)
            view.viewport().setPalette(pal)
            view.setItemDelegate(_ComboDelegate(view))
        self._refresh_ports()
        self._refresh_flow_combo()
        self._refresh_table()
        self._append_log("就绪。请选择串口并连接设备。")

    # ================= 界面 =================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        top = QHBoxLayout()
        top.addWidget(self._build_left(), 0)
        top.addWidget(self._build_main(), 1)
        root.addLayout(top, 1)
        root.addWidget(self._build_log())

    def _build_left(self):
        panel = QWidget()
        panel.setFixedWidth(340)
        lay = QVBoxLayout(panel)

        gb = QGroupBox("设备连接")
        g = QGridLayout(gb)
        self.cmb_port = QComboBox()
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh_ports)
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems(["9600", "38400"])
        self.spn_addr = QSpinBox()
        self.spn_addr.setRange(0, 14)
        g.addWidget(QLabel("串口"), 0, 0)
        g.addWidget(self.cmb_port, 0, 1)
        g.addWidget(btn_refresh, 0, 2)
        g.addWidget(QLabel("波特率"), 1, 0)
        g.addWidget(self.cmb_baud, 1, 1)
        g.addWidget(QLabel("泵地址"), 2, 0)
        g.addWidget(self.spn_addr, 2, 1)
        self.btn_connect = QPushButton("连接设备")
        self.btn_connect.clicked.connect(self._toggle_connect)
        self.btn_stop_dev = QPushButton("急停 (T)")
        self.btn_stop_dev.clicked.connect(self._stop)
        g.addWidget(self.btn_connect, 3, 0, 1, 2)
        g.addWidget(self.btn_stop_dev, 3, 2)
        lay.addWidget(gb)

        gb = QGroupBox("流程方案")
        g = QGridLayout(gb)
        self.cmb_flow = QComboBox()
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText("方案名称")
        g.addWidget(QLabel("已存方案"), 0, 0)
        g.addWidget(self.cmb_flow, 0, 1, 1, 2)
        g.addWidget(QLabel("方案名称"), 1, 0)
        g.addWidget(self.edt_name, 1, 1, 1, 2)
        self.btn_new = QPushButton("新建")
        self.btn_new.clicked.connect(self._new_flow)
        self.btn_load = QPushButton("加载")
        self.btn_load.clicked.connect(self._load_flow)
        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self._save_flow)
        self.btn_del = QPushButton("删除")
        self.btn_del.clicked.connect(self._delete_flow)
        for i, b in enumerate((self.btn_new, self.btn_load, self.btn_save, self.btn_del)):
            g.addWidget(b, 2, i)
        lay.addWidget(gb)

        gb = QGroupBox("设备设置")
        g = QGridLayout(gb)
        self.spn_ports = QSpinBox()
        self.spn_ports.setRange(4, 15)
        self.spn_ports.setValue(int(self.settings["port_count"]))
        self.spn_ports.valueChanged.connect(self._on_port_count_changed)
        g.addWidget(QLabel("阀口总数"), 0, 0)
        g.addWidget(self.spn_ports, 0, 1)
        self.cmb_syringe = QComboBox()
        self.cmb_syringe.addItems([f"{int(v)} μL" for v in SYRINGE_OPTIONS])
        self.cmb_syringe.setCurrentIndex(SYRINGE_OPTIONS.index(float(self.settings["stroke_ul"])))
        self.cmb_syringe.currentIndexChanged.connect(self._on_syringe_changed)
        g.addWidget(QLabel("进样器规格"), 1, 0)
        g.addWidget(self.cmb_syringe, 1, 1)
        self.spn_speed = QDoubleSpinBox()
        self.spn_speed.setDecimals(2)
        self.spn_speed.setSuffix(" μL/s")
        self.spn_speed.setRange(*flow_range_ul_s(float(self.settings["stroke_ul"])))
        self.spn_speed.setValue(float(self.settings["flow_speed_ul_s"]))
        self.spn_speed.valueChanged.connect(self._on_speed_changed)
        self.lbl_pps = QLabel()
        self.lbl_pps.setStyleSheet("color:#7fa39b;")
        g.addWidget(QLabel("注入/推出速度"), 2, 0)
        g.addWidget(self.spn_speed, 2, 1)
        g.addWidget(self.lbl_pps, 3, 0, 1, 2)
        self._update_pps_label()
        hint = QLabel("流程中直接使用端口号（1 – 阀口总数）。")
        hint.setWordWrap(True)
        g.addWidget(hint, 4, 0, 1, 2)
        lay.addWidget(gb)
        lay.addStretch(1)
        return panel

    def _build_main(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)

        gb = QGroupBox("流程步骤")
        v = QVBoxLayout(gb)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setMinimumHeight(200)
        self.tbl.setHorizontalHeaderLabels(["#", "类型", "参数"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        v.addWidget(self.tbl)
        self.btn_del_row = QPushButton("删除选中行")
        self.btn_del_row.clicked.connect(self._delete_row)
        v.addWidget(self.btn_del_row, 0, Qt.AlignLeft)
        lay.addWidget(gb, 1)

        gb = QGroupBox("添加步骤")
        g = QGridLayout(gb)
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(list(TYPE_KIND.keys()))
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)
        g.addWidget(QLabel("步骤类型"), 0, 0)
        g.addWidget(self.cmb_type, 0, 1)

        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, int(self.settings["port_count"]))
        self.spn_ul = QDoubleSpinBox()
        self.spn_ul.setRange(0.1, float(self.settings["stroke_ul"]))
        self.spn_ul.setValue(50.0)
        self.spn_ul.setSuffix(" μL")
        self.spn_sec = QDoubleSpinBox()
        self.spn_sec.setRange(0, 3600)
        self.spn_sec.setValue(INIT_WAIT_S)
        self.spn_sec.setSuffix(" 秒")
        self.spn_count = QSpinBox()
        self.spn_count.setRange(1, 2147483647)
        self.spn_count.setValue(2)
        self.spn_count.setSuffix(" 次")

        self.fields = {}
        for row, (key, text, widget) in enumerate([
            ("port", "端口号", self.spn_port),
            ("ul", "体积", self.spn_ul),
            ("sec", "等待时间", self.spn_sec),
            ("count", "循环次数", self.spn_count),
        ], start=1):
            lab = QLabel(text)
            g.addWidget(lab, row, 0)
            g.addWidget(widget, row, 1)
            self.fields[key] = (lab, widget)

        self.btn_add = QPushButton("添加到末尾")
        self.btn_add.clicked.connect(self._add_step)
        g.addWidget(self.btn_add, 5, 0, 1, 2)
        g.setColumnStretch(2, 1)
        lay.addWidget(gb)
        self._on_type_changed(self.cmb_type.currentText())

        gb = QGroupBox("执行")
        v = QVBoxLayout(gb)
        row = QHBoxLayout()
        self.btn_validate = QPushButton("校验")
        self.btn_validate.clicked.connect(self._check)
        self.btn_run = QPushButton("▶ 执行流程")
        self.btn_run.clicked.connect(self._run_flow)
        self.btn_step = QPushButton("▶ 执行单步")
        self.btn_step.clicked.connect(self._run_one_step)
        self.btn_halt = QPushButton("■ 停止")
        self.btn_halt.clicked.connect(self._stop)
        for b in (self.btn_validate, self.btn_run, self.btn_step):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.btn_halt)
        v.addLayout(row)
        self.lbl_check = QLabel("未校验")
        self.lbl_check.setWordWrap(True)
        v.addWidget(self.lbl_check)
        self.lbl_flow = QLabel("就绪")
        self.lbl_flow.setWordWrap(True)
        v.addWidget(self.lbl_flow)
        lay.addWidget(gb)
        return panel

    def _build_log(self):
        gb = QGroupBox("日志")
        v = QVBoxLayout(gb)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setMaximumHeight(150)
        v.addWidget(self.log)
        return gb

    # ================= 表单 =================
    def _on_type_changed(self, text):
        for key, (lab, widget) in self.fields.items():
            show = text in FORM_FIELDS[key]
            lab.setVisible(show)
            widget.setVisible(show)
        if text == "初始化":
            self.spn_sec.setValue(INIT_WAIT_S)

    def _on_syringe_changed(self, idx):
        ul = SYRINGE_OPTIONS[idx]
        set_syringe_ul(ul)
        self.settings["stroke_ul"] = ul
        self.spn_ul.setRange(0.1, ul)  # 超出新容量的输入值会被自动收紧
        self.spn_speed.setRange(*flow_range_ul_s(ul))  # 流速 μL/s 保持不变, 脉冲速度随规格变化
        if self.pump is not None:
            self.pump.stroke_ul = ul
        self._update_pps_label()
        self._append_log(f"进样器规格已设为 {int(ul)} μL")
        self._invalidate("进样器规格已修改，请重新校验")

    def _on_speed_changed(self, ul_s):
        set_flow_speed_ul_s(ul_s)
        self.settings["flow_speed_ul_s"] = float(ul_s)
        if self.pump is not None:
            self.pump.set_speed(ul_s)
        self._update_pps_label()
        self._invalidate("注入/推出速度已修改，请重新校验")

    def _update_pps_label(self):
        pps = ul_s_to_pulse(self.spn_speed.value(), float(self.settings["stroke_ul"]))
        pps = max(PULSE_MIN, min(PULSE_MAX, pps))
        self.lbl_pps.setText(f"换算: 最快速度 V = {pps} 脉冲/秒（泵上电默认 {DEFAULT_PULSE_PER_S}）")

    def _on_port_count_changed(self, n):
        set_port_count(n)
        self.settings["port_count"] = n
        self.spn_port.setMaximum(n)
        self._invalidate("阀口总数已修改，请重新校验")

    # ================= 步骤编辑 =================
    def _describe(self, s):
        k = s["kind"]
        if k == "valve":
            return f"端口 {s['port']}"
        if k in ("inject", "push"):
            return f"{float(s['ul']):g} μL"
        if k == "init":
            return f"Z1R 半力度，之后等待 {float(s['wait']):g} 秒"
        if k == "wait":
            return f"{float(s['sec']):g} 秒"
        if k == "loop_start":
            return f"共 {s['count']} 次（不含初始化）"
        return "—"

    def _refresh_table(self):
        self.tbl.setRowCount(0)
        in_loop = False
        for i, s in enumerate(self.steps, 1):
            k = s["kind"]
            indent = "      " if in_loop and k not in ("loop_start", "loop_end") else ""
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(str(i)))
            self.tbl.setItem(r, 1, QTableWidgetItem(indent + KIND_LABEL[k]))
            self.tbl.setItem(r, 2, QTableWidgetItem(self._describe(s)))
            if k == "loop_start":
                in_loop = True
            elif k == "loop_end":
                in_loop = False

    def _add_step(self):
        kind = TYPE_KIND[self.cmb_type.currentText()]
        s = {"kind": kind}
        if kind == "valve":
            s["port"] = int(self.spn_port.value())
        elif kind in ("inject", "push"):
            s["ul"] = float(self.spn_ul.value())
        elif kind == "init":
            s["wait"] = float(self.spn_sec.value())
        elif kind == "wait":
            s["sec"] = float(self.spn_sec.value())
        elif kind == "loop_start":
            s["count"] = int(self.spn_count.value())
        self.steps.append(s)
        self._refresh_table()
        self._invalidate("已修改，请重新校验")

    def _delete_row(self):
        r = self.tbl.currentRow()
        if r < 0 or r >= len(self.steps):
            return
        del self.steps[r]
        self._refresh_table()
        self._invalidate("已修改，请重新校验")

    def _invalidate(self, text=None):
        """流程被修改: 清空单步进度, 校验结果过期。"""
        self.op_iter = None
        self.pending = None
        self.lbl_check.setStyleSheet("")
        self.lbl_check.setText(text or "未校验")
        self.lbl_flow.setText("就绪")

    def _set_flow_text(self, text):
        self.lbl_flow.setText(text)

    # ================= 校验 =================
    def _check(self):
        errs, summ = validate(self.steps, self.settings)
        if errs:
            self.lbl_check.setStyleSheet("color:#ff5252; font-weight:bold;")
            self.lbl_check.setText("✗ 校验未通过：\n" + "\n".join(errs))
            return None
        self.lbl_check.setStyleSheet("color:#00e5c0; font-weight:bold;")
        text = (f"✓ 校验通过：活塞峰值 {summ['peak']:.1f} μL，"
                f"结束余量 {summ['final']:.1f} μL")
        if summ["rounds"]:
            text += f"，循环共 {summ['rounds']} 轮"
        self.lbl_check.setText(text)
        return summ

    def _ready_to_run(self):
        if self.pump is None:
            QMessageBox.information(self, "提示", "请先连接设备。")
            return False
        if self.running:
            return False
        if self._check() is None:
            QMessageBox.warning(self, "无法执行", "流程校验未通过，请按提示修改后再执行。")
            return False
        return True

    # ================= 执行 =================
    def _set_busy(self, busy):
        self.running = busy
        for w in (self.btn_run, self.btn_step, self.btn_validate, self.btn_add, self.btn_del_row,
                  self.btn_new, self.btn_load, self.btn_save, self.btn_del, self.cmb_type):
            w.setEnabled(not busy)

    def _run_flow(self):
        """从头执行整个流程。"""
        if not self._ready_to_run():
            return
        segs = build_segments(self.steps)
        stroke = float(self.settings["stroke_ul"])
        pump = self.pump
        self.op_iter = None
        self.pending = None
        pump._abort = False
        self._set_busy(True)

        def run():
            for op in iter_ops(segs):
                self.flow_sig.emit(op_label(op))
                execute_op(pump, op, stroke)
            self.flow_sig.emit("✅ 流程完成")

        self.runner.submit("自动流程", run)

    def _run_one_step(self):
        """逐条执行: 每点一次执行下一条操作, 循环内按轮次推进。"""
        if not self._ready_to_run():
            return
        if self.op_iter is None:
            self.op_iter = iter_ops(build_segments(self.steps))
            self.pending = next(self.op_iter, None)
        op = self.pending
        if op is None:
            self.op_iter = None
            self.flow_sig.emit("✅ 全部步骤已完成，再次点击将从头开始")
            return
        self.pending = next(self.op_iter, None)
        stroke = float(self.settings["stroke_ul"])
        pump = self.pump
        pump._abort = False
        self._set_busy(True)
        self.flow_sig.emit(f"执行中: {op_label(op)}")
        self.runner.submit("单步", lambda: execute_op(pump, op, stroke))

    def _stop(self):
        self.runner.clear()
        if self.pump is not None:
            self.pump.emergency_stop()
        self.op_iter = None
        self.pending = None
        self._append_log("[停止] 已发送 T 指令并清空队列，下次执行将从头开始")

    def _on_task_done(self, desc):
        self._set_busy(False)
        if desc == "自动流程":
            self.op_iter = None
            self.pending = None
        else:
            if self.pending is None:
                self.op_iter = None
                self.flow_sig.emit("✅ 全部步骤已完成，再次点击将从头开始")
            else:
                self.flow_sig.emit(f"下一步: {op_label(self.pending)}")
        self._append_log(f"完成: {desc}")

    def _on_task_failed(self, msg):
        self._set_busy(False)
        self.op_iter = None
        self.pending = None
        self._append_log(f"[错误] {msg}（流程已停止）")
        self.flow_sig.emit("⚠ 执行中断，请检查原因后重新执行")

    # ================= 方案管理 =================
    def _refresh_flow_combo(self, select=None):
        self.cmb_flow.blockSignals(True)
        self.cmb_flow.clear()
        self.cmb_flow.addItems(list_flows())
        if select is not None:
            idx = self.cmb_flow.findText(select)
            if idx >= 0:
                self.cmb_flow.setCurrentIndex(idx)
        self.cmb_flow.blockSignals(False)

    def _new_flow(self):
        self.steps = []
        self.edt_name.clear()
        self._refresh_table()
        self._invalidate("新建流程，请添加步骤")

    def _load_flow(self):
        name = self.cmb_flow.currentText()
        if not name:
            return
        self.steps = get_flow(name)
        self.edt_name.setText(name)
        self._refresh_table()
        self._invalidate(f"已加载「{name}」，请重新校验")
        self._append_log(f"已加载方案「{name}」（{len(self.steps)} 步）")

    def _save_flow(self):
        name = self.edt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请先输入方案名称。")
            return
        save_flow(name, self.steps)
        self._refresh_flow_combo(select=name)
        self._append_log(f"方案「{name}」已保存（{len(self.steps)} 步）")

    def _delete_flow(self):
        name = self.cmb_flow.currentText()
        if not name:
            return
        if QMessageBox.question(self, "删除方案", f"确定删除方案「{name}」？") != QMessageBox.Yes:
            return
        delete_flow(name)
        self._refresh_flow_combo()
        self._append_log(f"方案「{name}」已删除")

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
                                  self.spn_addr.value(),
                                  speed_ul_s=float(self.settings["flow_speed_ul_s"]),
                                  stroke_ul=float(self.settings["stroke_ul"]),
                                  log=self.log_sig.emit)
            try:
                pump.open()
            except PumpError as e:
                QMessageBox.critical(self, "连接失败", str(e))
                return
            self.pump = pump
            self.btn_connect.setText("断开设备")
        else:
            self._stop()
            self.pump.close()
            self.pump = None
            self.btn_connect.setText("连接设备")

    # ================= 日志 =================
    def _append_log(self, msg):
        self.log.appendPlainText(time.strftime("[%H:%M:%S] ") + msg)

    def closeEvent(self, event):
        self.runner.clear()
        self.runner.shutdown()
        self.runner.wait(1000)
        if self.pump is not None:
            self.pump.close()
        super().closeEvent(event)
