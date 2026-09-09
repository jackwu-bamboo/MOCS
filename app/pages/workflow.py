"""实验流程页：设备连接。

培养参数在"温度控制"页调整；启动/停止操作在侧边栏"运行"组与运行页执行。
实验编号在启动时自动生成，无需手动配置实验信息。
"""
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

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
        root.addWidget(self.step1)

        status_card = Card("运行状态")
        self.run_label = QLabel("")
        self.run_label.setWordWrap(True)
        status_card.body.addWidget(self.run_label)
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

    # ---- 状态刷新 ----
    def refresh(self):
        sim = self.sim
        st = sim.exp_state
        all_conn = all(sim.connected.values())
        running = st is ExpState.RUNNING
        finished = st is ExpState.FINISHED

        for name, card in self.dev_cards.items():
            card.set_state(sim.connected.get(name, False))
        self.btn_connect.setEnabled(not all_conn)
        self.btn_disconnect.setEnabled(all_conn and not running)
        self.check_label.setText(
            f"已连接（{sim.connected_port}）" if sim.real_mode
            else ("模拟模式" if all_conn else "设备未连接"))

        self.step1.set_status("done" if all_conn else "active")

        if running:
            self.run_label.setText(
                f"实验{sim.exp_state.value}（{sim.exp_info.get('id') or '--'}），"
                f"已运行 {sim.exp_elapsed()}；温度数据落盘: {sim.live_data_dir}")
        elif finished:
            self.run_label.setText(
                f"实验已结束（{time.strftime('%H:%M:%S', time.localtime(sim.exp_finished_at))}），"
                f"数据已归档: {sim.last_export_path}；再次点击“运行 → 启动”开始新实验")
        else:
            self.run_label.setText("连接设备后，点击左侧“运行 → 启动”开始培养")
