"""数据管理界面：数据统计、导出（实验建立与参数设置在"实验流程"页完成）。"""
import os
import time

from PyQt5.QtWidgets import (QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from app.exporter import export_experiment
from app.simulator import ExpState
from app.widgets import Card

DATA_TYPES = ["温度数据", "参数变更记录"]


class DataManagerPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top = Card("实验信息")
        form = QFormLayout()
        self.lbl_exp = QLabel("--")
        self.lbl_state = QLabel("--")
        form.addRow("实验编号", self.lbl_exp)
        form.addRow("实验状态", self.lbl_state)
        btns = QHBoxLayout()
        self.b_stop = QPushButton("结束实验")
        self.b_export = QPushButton("导出数据")
        btns.addWidget(self.b_stop)
        btns.addWidget(self.b_export)
        btns.addStretch(1)
        form.addRow(btns)
        top.body.addLayout(form)
        root.addWidget(top)

        table_card = Card("数据统计 (自动保存)")
        self.table = QTableWidget(len(DATA_TYPES), 3)
        self.table.setHorizontalHeaderLabels(["数据类型", "数据点数", "最近更新"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_card.body.addWidget(self.table)
        root.addWidget(table_card, 1)

        self.b_stop.clicked.connect(self.sim.finish_experiment)
        self.b_export.clicked.connect(self.export)
        sim.states_updated.connect(self.refresh)
        self.refresh()

    def export(self):
        """手动导出 = 重新生成汇总文件（与结束实验自动归档共用同一逻辑）。"""
        if not self.sim.exp_info.get("id"):
            QMessageBox.warning(self, "提示", "尚未开始实验，无数据可导出")
            return
        base = export_experiment(self.sim)
        QMessageBox.information(self, "导出完成", f"数据已导出到:\n{base}")

    def refresh(self):
        sim = self.sim
        exp_id = sim.exp_info.get("id")
        if exp_id:
            self.lbl_exp.setText(exp_id)
        else:
            self.lbl_exp.setText("未开始（启动实验后自动生成编号）")
        self.lbl_state.setText(sim.exp_state.value)
        running = sim.exp_state is ExpState.RUNNING
        counts = [
            len(sim.history["temp"]),
            len(sim.param_log),
        ]
        for i, (name, c) in enumerate(zip(DATA_TYPES, counts)):
            self._set(i, 0, name)
            self._set(i, 1, str(c))
            self._set(i, 2, time.strftime("%H:%M:%S") if running else "--")

    def _set(self, i, j, text):
        it = self.table.item(i, j)
        if it is None:
            it = QTableWidgetItem()
            self.table.setItem(i, j, it)
        it.setText(text)
