"""离屏冒烟测试（精简版：仅温度控制）：流程状态机 + 参数日志 + 自动归档。"""
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

    assert w.pages.count() == 4, "应有 4 个页面（实验流程/运行/温度控制/数据管理）"
    assert w.pages.currentIndex() == PAGE_WORKFLOW
    assert_locked(w, locked=True)

    # 连接设备
    w.sim.connect_all()
    assert w.sim.exp_state is ExpState.CONNECTED
    pump_events(app, 0.3)
    assert_locked(w, locked=True)

    today = time.strftime("%Y%m%d")
    exp_id = f"EXP-{today}-T{int(time.time()) % 100000:05d}"
    base = os.path.join("exports", exp_id)
    shutil.rmtree(base, ignore_errors=True)

    # 配置实验（仅实验信息；温度参数在温度控制页调整）
    assert w.sim.create_experiment(exp_id, "测试实验", "tester", "smoke")
    pump_events(app, 0.2)
    assert w.btn_start.isEnabled(), "配置完成后侧边栏启动应可用"
    assert_locked(w, locked=False), "实验建立后各模块应解锁"

    # 启动（经侧边栏按钮，应跳转运行页）
    w.btn_start.click()
    assert w.sim.exp_state is ExpState.RUNNING
    assert w.pages.currentIndex() == PAGE_RUN
    pump_events(app, 1.0)
    assert_locked(w, locked=False)

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

    # 结束 → 归档（页面保持解锁，便于导出数据）
    w.sim.finish_experiment()
    assert w.sim.exp_state is ExpState.FINISHED
    pump_events(app, 0.3)
    assert_locked(w, locked=False)
    assert len(w.sim.experiments) == 1
    assert os.path.isfile(os.path.join(base, "experiment.json"))
    temp_csv = os.path.join(base, "data", "temperature.csv")
    assert os.path.isfile(temp_csv), "温度数据应已落盘"
    with open(temp_csv, encoding="utf-8-sig") as f:
        assert sum(1 for _ in f) > 2, "temperature.csv 应有数据行"
    assert os.path.isfile(os.path.join(base, "data", "param_log.csv"))

    # 新建下一个实验（清空实验信息后重新锁定）
    w.sim.reset_experiment()
    assert w.sim.next_exp_id() != exp_id
    pump_events(app, 0.2)
    assert_locked(w, locked=True)

    w.sim.disconnect_all()
    assert w.sim.exp_state is ExpState.DISCONNECTED
    shutil.rmtree(base, ignore_errors=True)
    print("SMOKE OK")
    app.quit()


if __name__ == "__main__":
    main()
