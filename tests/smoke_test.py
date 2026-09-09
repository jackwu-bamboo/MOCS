"""离屏冒烟测试（精简版：仅温度控制，无实验信息配置）：状态机 + 参数日志 + 自动归档。"""
import os
import shutil
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication, QMessageBox
from qt_material import apply_stylesheet

from app.main_window import MainWindow, PAGE_RUN, PAGE_WORKFLOW
from app.simulator import ExpState
from app.styles import CUSTOM_QSS


def assert_locked(w, locked):
    """locked=True 时导航按钮应全部禁用。"""
    for btn in w.lock_buttons:
        assert btn.isEnabled() != locked, f"nav button {btn.text()} lock state wrong"


def pump_events(app, seconds):
    for _ in range(max(1, int(seconds / 0.05))):
        time.sleep(0.05)
        app.processEvents()


def main():
    # 归档完成弹窗为模态，测试中打补丁避免阻塞
    QMessageBox.information = staticmethod(lambda *a, **k: None)

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_teal.xml")
    app.setStyleSheet(app.styleSheet() + CUSTOM_QSS)
    w = MainWindow()
    w.show()

    assert w.pages.count() == 4, "应有 4 个页面"
    assert w.pages.currentIndex() == PAGE_WORKFLOW
    assert_locked(w, locked=True)

    # 连接设备后各模块即解锁，可直接启动（无需配置实验信息）
    w.sim.connect_all()
    assert w.sim.exp_state is ExpState.CONNECTED
    pump_events(app, 0.3)
    assert_locked(w, locked=False)
    assert w.btn_start.isEnabled(), "连接后启动应可用"

    # 启动（经侧边栏按钮，应跳转运行页；实验编号自动生成）
    w.btn_start.click()
    assert w.sim.exp_state is ExpState.RUNNING
    assert w.pages.currentIndex() == PAGE_RUN
    assert w.sim.exp_info.get("id"), "启动时应自动生成实验编号"
    exp_id = w.sim.exp_info["id"]
    base = os.path.join("exports", exp_id)
    pump_events(app, 1.0)

    # 暂停 → 温度冻结 → 继续
    assert w.sim.pause_experiment()
    assert w.sim.exp_state is ExpState.PAUSED
    t0 = w.sim.temp_current
    pump_events(app, 0.4)
    assert abs(w.sim.temp_current - t0) < 1e-9, "暂停应冻结温度"
    assert w.btn_pause.text() == "继续"
    assert w.sim.resume_experiment()
    assert w.sim.exp_state is ExpState.RUNNING

    # 运行中温度参数变更日志
    n0 = len(w.sim.param_log)
    w.sim.set_temp(38.0, 36.0, 40.0)
    assert len(w.sim.param_log) > n0
    pump_events(app, 0.5)

    # 运行/暂停中禁止断开设备
    w.sim.disconnect_all()
    assert w.sim.exp_state in (ExpState.RUNNING, ExpState.PAUSED)

    # 结束 → 归档（页面保持解锁）
    w.sim.finish_experiment()
    assert w.sim.exp_state is ExpState.FINISHED
    pump_events(app, 0.3)
    assert_locked(w, locked=False)
    assert len(w.sim.experiments) == 1
    assert os.path.isfile(os.path.join(base, "experiment.json"))
    temp_csv = os.path.join(base, "data", "temperature.csv")
    with open(temp_csv, encoding="utf-8-sig") as f:
        assert sum(1 for _ in f) > 2, "temperature.csv 应有数据行"
    assert os.path.isfile(os.path.join(base, "data", "param_log.csv"))

    # 结束后可直接再次启动新实验（编号自动递增）
    assert w.sim.start_experiment()
    assert w.sim.exp_info["id"] != exp_id
    pump_events(app, 0.2)
    assert w.sim.finish_experiment()
    assert len(w.sim.experiments) == 2

    w.sim.disconnect_all()
    assert w.sim.exp_state is ExpState.DISCONNECTED
    pump_events(app, 0.2)
    assert_locked(w, locked=True)
    shutil.rmtree(os.path.join("exports", exp_id), ignore_errors=True)
    shutil.rmtree(os.path.join("exports", w.sim.exp_info["id"]), ignore_errors=True)
    print("SMOKE OK")
    app.quit()


if __name__ == "__main__":
    main()
