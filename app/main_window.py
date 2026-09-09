"""主窗口（精简版：仅温度控制）：分组侧边栏 + 页面栈 + 顶部状态栏。

侧边栏分组：实验流程 / 温度控制 / 运行 / 实时数据 / 数据。
实验未建立时，温度控制、数据管理按钮禁用。
"""
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                             QMessageBox, QPushButton, QScrollArea, QStackedWidget,
                             QVBoxLayout, QWidget)

from app.pages.data_manager import DataManagerPage
from app.pages.run import RunPage
from app.pages.temperature import TemperaturePage
from app.pages.workflow import WorkflowPage
from app.simulator import DeviceSimulator, ExpState

PAGE_WORKFLOW, PAGE_RUN, PAGE_TEMP, PAGE_DATA = range(4)
LOCKED_PAGES = {PAGE_TEMP, PAGE_DATA}


class SidebarGroup(QFrame):
    """蓝色分组头 + 按钮网格的侧边栏分组卡片。"""

    def __init__(self, title, cols=2):
        super().__init__()
        self.setObjectName("SideGroup")
        self.cols = cols
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 8)
        lay.setSpacing(6)
        header = QLabel(title)
        header.setObjectName("SideGroupHeader")
        header.setAlignment(Qt.AlignCenter)
        lay.addWidget(header)
        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        lay.addLayout(self.grid)
        self._row = 0
        self._col = 0

    def add_button(self, text, callback):
        btn = QPushButton(text)
        btn.setObjectName("SideBtn")
        btn.clicked.connect(callback)
        self.grid.addWidget(btn, self._row, self._col)
        self._advance()
        return btn

    def add_widget(self, widget):
        self.grid.addWidget(widget, self._row, self._col)
        self._advance()

    def _advance(self):
        self._col += 1
        if self._col >= self.cols:
            self._col = 0
            self._row += 1


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("培养盒温度控制软件")
        self.resize(1100, 720)
        self.sim = DeviceSimulator(self)
        self.rt_labels = {}
        self.lock_buttons = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("培养盒温度控制软件")
        title.setObjectName("HeaderTitle")
        self.exp_state = QLabel()
        self.clock = QLabel()
        self.clock.setObjectName("Clock")
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(self.exp_state)
        hl.addWidget(self.clock)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self.pages = QStackedWidget()
        self.workflow_page = WorkflowPage(self.sim)
        self.run_page = RunPage(self.sim)
        self.temp_page = TemperaturePage(self.sim)
        self.data_page = DataManagerPage(self.sim)
        for w in (self.workflow_page, self.run_page, self.temp_page, self.data_page):
            self.pages.addWidget(w)
        self.pages.setCurrentIndex(PAGE_WORKFLOW)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        self.sim.exp_state_changed.connect(self._on_exp_state)
        self.sim.states_updated.connect(self._apply_locks)
        self.sim.states_updated.connect(self._update_run_buttons)
        self.sim.states_updated.connect(self._update_realtime)
        self._apply_locks()
        self._update_header()
        self._update_realtime()

        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._tick_clock)
        clock_timer.start(1000)
        self._tick_clock()

    # ---- 侧边栏 ----
    def _build_sidebar(self):
        scroll = QScrollArea()
        scroll.setObjectName("Sidebar")
        scroll.setFixedWidth(210)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        sb = QVBoxLayout(inner)
        sb.setContentsMargins(8, 8, 8, 8)
        sb.setSpacing(10)

        # 实验流程
        g_flow = SidebarGroup("实验流程")
        g_flow.add_button("设备连接", lambda: self._goto(PAGE_WORKFLOW))
        sb.addWidget(g_flow)

        # 温度控制
        g_temp = SidebarGroup("温度控制")
        self.lock_buttons.append(
            g_temp.add_button("温度控制", lambda: self._goto(PAGE_TEMP)))
        sb.addWidget(g_temp)

        # 运行
        g_run = SidebarGroup("运行")
        self.btn_start = g_run.add_button("启动", self._toggle_run)
        self.btn_stop = g_run.add_button("停止", self.sim.finish_experiment)
        sb.addWidget(g_run)

        # 实时数据
        g_rt = SidebarGroup("实时数据", cols=2)
        self.rt_labels = {}
        for key, name in (("temp", "温度"), ("elapsed", "运行时长"), ("state", "状态")):
            box = QVBoxLayout()
            cap = QLabel(name)
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet("color: #8fa8a4; font-size: 12px;")
            val = QLabel("--")
            val.setAlignment(Qt.AlignCenter)
            val.setObjectName("SideStat")
            box.addWidget(val)
            wrap = QWidget()
            wrap.setLayout(box)
            g_rt.add_widget(wrap)
            self.rt_labels[key] = val
        sb.addWidget(g_rt)

        # 数据
        g_data = SidebarGroup("数据")
        self.lock_buttons.append(g_data.add_button("数据管理", lambda: self._goto(PAGE_DATA)))
        sb.addWidget(g_data)
        sb.addStretch(1)

        scroll.setWidget(inner)
        return scroll

    # ---- 导航与运行操作 ----
    def _goto(self, page_idx):
        self.pages.setCurrentIndex(page_idx)

    def _toggle_run(self):
        """空闲时启动培养。"""
        if self.sim.start_experiment():
            self._goto(PAGE_RUN)

    # ---- 状态刷新 ----
    def _apply_locks(self):
        unlocked = self.sim.unlocked
        for btn in self.lock_buttons:
            btn.setEnabled(unlocked)
        self._update_run_buttons()

    def _update_run_buttons(self):
        st = self.sim.exp_state
        self.btn_start.setEnabled(st is ExpState.CONNECTED)
        self.btn_stop.setEnabled(st is ExpState.RUNNING)

    def _update_realtime(self):
        sim = self.sim
        self.rt_labels["temp"].setText(f"{sim.temp_current:.1f} ℃")
        self.rt_labels["elapsed"].setText(sim.exp_elapsed())
        self.rt_labels["state"].setText(sim.exp_state.value)

    def _update_header(self):
        self.exp_state.setText(f"实验状态: {self.sim.exp_state.value}")

    def _on_exp_state(self, state):
        self._apply_locks()
        self._update_header()
        # 未建立实验时若正停留在被锁页面则回到流程页
        if not self.sim.unlocked and self.pages.currentIndex() in LOCKED_PAGES:
            self._goto(PAGE_WORKFLOW)
        # 结束实验自动归档完成后统一提示
        if state is ExpState.FINISHED and self.sim.last_export_path:
            QMessageBox.information(
                self, "实验已归档",
                f"实验数据已自动导出到:\n{self.sim.last_export_path}")

    def _tick_clock(self):
        self.clock.setText(time.strftime("%Y-%m-%d %H:%M:%S"))

    def closeEvent(self, event):
        # 退出时关闭串口与轮询线程
        self.sim.shutdown()
        super().closeEvent(event)
