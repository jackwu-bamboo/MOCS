"""实验流程页：设备连接 → 配置实验（实验信息）。

培养参数在"外设控制"页调整；启动/暂停/结束操作在侧边栏"运行"组与运行页执行。
"""
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from app.simulator import DEVICE_NAMES, ExpState
from app.widgets import Card, StatusCard

BADGE_STYLES = {
    "locked": ("#455a64", "#90a4ae", "等待上一步"),
    "active": ("#00e5c0", "#0f2622", "进行中"),
    "done": ("#00e676", "#0f2622", "已完成"),
}


class StepCard(Card):
    """带步骤徽章与状态标签的流程卡片。"""

    def __init__(self, no, title):
        super().__init__()
        header = QHBoxLayout()
        self.badge = QLabel(str(no))
        self.badge.setObjectName("StepBadge")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignCenter)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.badge)
        header.addWidget(t)
        header.addStretch(1)
        header.addWidget(self.status)
        self.body.addLayout(header)

        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 4, 0, 0)
        self.body.addWidget(self.content)

    def set_status(self, state):
        bg, fg, text = BADGE_STYLES[state]
        self.badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 12px; font-weight: bold;")
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {bg};")
        self.content.setEnabled(state != "locked")


class WorkflowPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(12)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        self.step1 = StepCard(1, "设备连接")
        self._build_step1()
        self.step2 = StepCard(2, "配置实验")
        self._build_step2()
        for s in (self.step1, self.step2):
            root.addWidget(s)

        status_card = Card("运行状态")
        self.run_label = QLabel("")
        self.run_label.setWordWrap(True)
        self.btn_next = QPushButton("新建下一个实验")
        self.btn_next.clicked.connect(self.new_exp)
        self.btn_next.setVisible(False)
        status_row = QHBoxLayout()
        status_row.addWidget(self.btn_next)
        status_row.addStretch(1)
        status_card.body.addWidget(self.run_label)
        status_card.body.addLayout(status_row)
        root.addWidget(status_card)
        root.addStretch(1)

        sim.states_updated.connect(self.refresh)
        sim.exp_state_changed.connect(lambda _: self.refresh())
        self.refresh()

    # ---- 步骤① 设备连接 ----
    def _build_step1(self):
        row = QHBoxLayout()
        self.dev_cards = {}
        for name in DEVICE_NAMES:
            card = StatusCard(name)
            self.dev_cards[name] = card
            row.addWidget(card)
        self.step1.content_lay.addLayout(row)

        btns = QHBoxLayout()
        self.btn_connect = QPushButton("连接全部设备")
        self.btn_disconnect = QPushButton("断开设备")
        self.btn_connect.clicked.connect(self.sim.connect_all)
        self.btn_disconnect.clicked.connect(self.sim.disconnect_all)
        self.check_label = QLabel("设备未连接")
        btns.addWidget(self.btn_connect)
        btns.addWidget(self.btn_disconnect)
        btns.addStretch(1)
        btns.addWidget(self.check_label)
        self.step1.content_lay.addLayout(btns)

    # ---- 步骤② 配置实验 ----
    def _build_step2(self):
        form = QFormLayout()
        self.ed_exp_id = QLineEdit()
        self.ed_name = QLineEdit()
        self.ed_operator = QLineEdit()
        self.ed_remark = QLineEdit()
        form.addRow("实验编号", self.ed_exp_id)
        form.addRow("实验名称", self.ed_name)
        form.addRow("操作者", self.ed_operator)
        form.addRow("备注", self.ed_remark)
        self.step2.content_lay.addLayout(form)

        note = QLabel("培养参数（温度 / 氧浓度 / 微泵 / 位置对准）在“外设控制”页调整；"
                      "检测模块在实验启动后于运行页按需启停")
        note.setStyleSheet("color: #8fa8a4;")
        note.setWordWrap(True)
        self.step2.content_lay.addWidget(note)
        btns = QHBoxLayout()
        self.btn_save = QPushButton("保存配置")
        self.btn_save.clicked.connect(self.save_config)
        btns.addWidget(self.btn_save)
        btns.addStretch(1)
        self.config_hint = QLabel("")
        self.config_hint.setStyleSheet("color: #00e5c0;")
        btns.addWidget(self.config_hint)
        self.step2.content_lay.addLayout(btns)

    def save_config(self):
        name = self.ed_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请填写实验名称")
            return
        exp_id = self.ed_exp_id.text().strip() or self.sim.next_exp_id()
        self.sim.create_experiment(exp_id, name,
                                   self.ed_operator.text(), self.ed_remark.text())
        self.config_hint.setText("配置完成，点击左侧“运行 → 启动”开始培养")

    def new_exp(self):
        self.sim.reset_experiment()
        for ed in (self.ed_exp_id, self.ed_name, self.ed_operator, self.ed_remark):
            ed.clear()
        self.config_hint.setText("")

    # ---- 状态刷新 ----
    def refresh(self):
        sim = self.sim
        st = sim.exp_state
        all_conn = all(sim.connected.values())
        has_exp = bool(sim.exp_info.get("id"))
        running = st in (ExpState.RUNNING, ExpState.PAUSED)
        finished = st is ExpState.FINISHED

        for name, card in self.dev_cards.items():
            card.set_state(sim.connected.get(name, False))
        self.btn_connect.setEnabled(not all_conn)
        self.btn_disconnect.setEnabled(all_conn and not running)
        self.check_label.setText("设备已连接" if all_conn else "设备未连接")

        self.step1.set_status("done" if all_conn else "active")
        self.step2.set_status("done" if has_exp else ("active" if all_conn else "locked"))
        self.step2.content.setEnabled(all_conn and not running)

        if all_conn and not has_exp and not self.ed_exp_id.text().strip():
            self.ed_exp_id.setText(sim.next_exp_id())

        self.btn_next.setVisible(finished)
        if running:
            self.run_label.setText(
                f"实验{sim.exp_state.value}，已运行 {sim.exp_elapsed()}；"
                f"环境数据落盘: {sim.live_data_dir}")
        elif finished:
            self.run_label.setText(
                f"实验已结束（{time.strftime('%H:%M:%S', time.localtime(sim.exp_finished_at))}），"
                f"数据已归档: {sim.last_export_path}")
        else:
            self.run_label.setText("完成设备连接与实验配置后，点击左侧“运行 → 启动”开始培养")
