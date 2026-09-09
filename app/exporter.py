"""实验数据归档/导出（精简版：仅温度）。

实验结束时由 simulator 自动调用，也可在数据管理页手动重新导出。
运行期数据（data/temperature.csv、data/param_log.csv）由 simulator 逐行追加写入，
本模块负责生成汇总文件：experiment.json。
"""
import json
import os
import time


def export_dir(sim):
    return os.path.join("exports", sim.exp_info.get("id") or "EXP-UNNAMED")


def _fmt_ts(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else None


def export_experiment(sim):
    """生成/刷新汇总文件，返回归档目录绝对路径。"""
    base = export_dir(sim)
    os.makedirs(os.path.join(base, "data"), exist_ok=True)

    doc = {
        "id": sim.exp_info.get("id"),
        "name": sim.exp_info.get("name"),
        "operator": sim.exp_info.get("operator"),
        "remark": sim.exp_info.get("remark"),
        "params": sim.exp_params,
        "started_at": _fmt_ts(sim.exp_started_at),
        "finished_at": _fmt_ts(sim.exp_finished_at),
        "elapsed": sim.exp_elapsed(),
        "param_changes": len(sim.param_log),
    }
    with open(os.path.join(base, "experiment.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return os.path.abspath(base)
