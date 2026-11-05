# -*- coding: utf-8 -*-
"""自定义流程: 步骤模型、校验、执行计划、方案持久化(v2)。

步骤类型 (界面名 -> 内部类型):
  切阀 valve(port) | 注入 inject(ul) | 推出 push(ul) | 初始化 init(wait)
  等待 wait(sec)   | 循环开始 loop_start(count) | 循环结束 loop_end

约束:
  - 初始化只能是第 1 步, 且只能有一次 (循环内不允许初始化)
  - 循环不可嵌套, 次数 ≥ 1, 无上限
  - 注入 / 推出 为相对体积, 注射腔范围 0 ~ stroke_ul
  - 校验不通过则禁止执行
"""
import json
import os
import time

from port_config import app_dir
from sy01_pump import (
    DEFAULT_FLOW_UL_S, DEFAULT_SYRINGE_UL, FULL_STROKE_STEPS, SYRINGE_OPTIONS,
    PumpError, flow_range_ul_s,
)

CONFIG_FILE = os.path.join(app_dir(), "workflow_config.json")
VERSION = 2
DEFAULT_SETTINGS = dict(port_count=10, stroke_ul=DEFAULT_SYRINGE_UL, flow_speed_ul_s=DEFAULT_FLOW_UL_S)
INIT_WAIT_S = 3.0
EPS = 1e-6

TYPE_KIND = {"切阀": "valve", "注入": "inject", "推出": "push", "初始化": "init",
             "等待": "wait", "循环开始": "loop_start", "循环结束": "loop_end"}
KIND_LABEL = {v: k for k, v in TYPE_KIND.items()}


# ---------- 方案持久化 ----------

def _empty_store():
    return {"version": VERSION, "settings": dict(DEFAULT_SETTINGS), "flows": {}}


def _write(store):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def load_store():
    """读取存档。旧格式(无 version 或损坏)整体改名备份, 从空白开始。"""
    if not os.path.exists(CONFIG_FILE):
        return _empty_store()
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        stamp = time.strftime("%Y%m%d%H%M%S")
        os.replace(CONFIG_FILE, os.path.join(app_dir(), f"workflow_config.legacy-{stamp}.json"))
        return _empty_store()
    settings = dict(DEFAULT_SETTINGS)
    settings.update(data.get("settings", {}))
    if float(settings.get("stroke_ul", 0)) not in SYRINGE_OPTIONS:
        settings["stroke_ul"] = DEFAULT_SYRINGE_UL  # 存档值非法时回退默认规格
    data["settings"] = settings
    data.setdefault("flows", {})
    return data


def list_flows():
    return sorted(load_store()["flows"])


def get_flow(name):
    return [dict(s) for s in load_store()["flows"][name]["steps"]]


def save_flow(name, steps):
    store = load_store()
    store["flows"][name] = {"steps": [dict(s) for s in steps]}
    _write(store)


def delete_flow(name):
    store = load_store()
    if store["flows"].pop(name, None) is not None:
        _write(store)


def get_settings():
    return dict(load_store()["settings"])


def set_syringe_ul(ul):
    ul = float(ul)
    if ul not in SYRINGE_OPTIONS:
        raise ValueError(f"不支持的进样器规格: {ul}")
    store = load_store()
    store["settings"]["stroke_ul"] = ul
    _write(store)


def set_flow_speed_ul_s(ul_s):
    store = load_store()
    lo, hi = flow_range_ul_s(float(store["settings"]["stroke_ul"]))
    ul_s = float(ul_s)
    if not lo <= ul_s <= hi:
        raise ValueError(f"速度 {ul_s:g} μL/s 超出范围 {lo:.2f}–{hi:.2f}")
    store["settings"]["flow_speed_ul_s"] = ul_s
    _write(store)


def set_port_count(n):
    store = load_store()
    store["settings"]["port_count"] = int(n)
    _write(store)


# ---------- 执行计划 ----------
# 操作元组: (kind, 描述, 轮次标签, 数值, 步骤号)
#   kind: init(数值=初始化后等待秒) | valve(数值=端口) | move(数值=有符号 μL) | wait(数值=秒)

def ul_to_steps(ul, stroke):
    return int(round(FULL_STROKE_STEPS * ul / stroke))


def _make_op(s, no):
    k = s["kind"]
    if k == "valve":
        return ("valve", f"切阀 → 端口 {int(s['port'])}", "", int(s["port"]), no)
    if k == "inject":
        return ("move", f"注入 {float(s['ul']):g} μL", "", float(s["ul"]), no)
    if k == "push":
        return ("move", f"推出 {float(s['ul']):g} μL", "", -float(s["ul"]), no)
    if k == "init":
        w = float(s.get("wait", INIT_WAIT_S))
        return ("init", f"初始化 (Z1R)，之后等待 {w:g} 秒", "", w, no)
    if k == "wait":
        t = float(s["sec"])
        return ("wait", f"等待 {t:g} 秒", "", t, no)
    raise ValueError(f"未知步骤类型: {k}")


def build_segments(steps):
    """把步骤列表切分为 [("ops", [操作...])] 与 [("loop", 次数, [循环体操作...])] 段。"""
    segs = []
    cur = []
    body = None
    count = 0
    for no, s in enumerate(steps, 1):
        k = s["kind"]
        if k == "loop_start":
            segs.append(("ops", cur))
            cur, body, count = [], [], int(s["count"])
        elif k == "loop_end":
            segs.append(("loop", count, body))
            body = None
        else:
            (body if body is not None else cur).append(_make_op(s, no))
    segs.append(("ops", cur))
    return segs


def iter_ops(segs):
    """惰性展开为逐条操作; 循环次数再大也不占内存。"""
    for seg in segs:
        if seg[0] == "ops":
            yield from seg[1]
        else:
            _, cnt, body = seg
            for r in range(1, cnt + 1):
                tag = f"第 {r}/{cnt} 轮"
                for kind, text, _, val, no in body:
                    yield (kind, text, tag, val, no)


def op_label(op):
    _, text, tag, _, no = op
    return f"第{no}步 · {tag} · {text}" if tag else f"第{no}步 · {text}"


def _sleep_checked(pump, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if getattr(pump, "_abort", False):
            raise PumpError("操作已中止")
        time.sleep(0.05)


def execute_op(pump, op, stroke):
    kind, _, _, val, _ = op
    if getattr(pump, "_abort", False):
        raise PumpError("操作已中止")
    if kind == "init":
        pump.init_pump()
        _sleep_checked(pump, val)
    elif kind == "valve":
        pump.valve_goto(val)
    elif kind == "move":
        pump.plunger_goto(pump.current_steps + ul_to_steps(val, stroke))
    elif kind == "wait":
        _sleep_checked(pump, val)


# ---------- 校验 ----------

def _range_msg(no, cur, stroke, rnd, cnt):
    where = f"第 {no} 步" + (f"（第 {rnd}/{cnt} 轮）" if cnt > 1 else "")
    if cur < 0:
        return f"{where}：排出量超过注射腔内液量（体积将降为 {cur:.1f} μL）"
    return f"{where}：注入后注射腔体积达到 {cur:.1f} μL，超过容量 {stroke:g} μL"


def validate(steps, settings):
    """返回 (错误列表, 摘要)。错误列表为空即通过; 摘要含 peak / final / rounds。"""
    if not steps:
        return ["流程为空，请先添加步骤。"], None
    stroke = float(settings["stroke_ul"])
    ports = int(settings["port_count"])
    speed = float(settings.get("flow_speed_ul_s", DEFAULT_FLOW_UL_S))
    lo, hi = flow_range_ul_s(stroke)
    kinds = [s["kind"] for s in steps]
    errs = []
    if not lo <= speed <= hi:
        errs.append(f"注入/推出速度 {speed:g} μL/s 超出范围 {lo:.2f}–{hi:.2f} μL/s。")
    if kinds[0] != "init":
        errs.append("第 1 步必须是「初始化」。")
    if kinds.count("init") != 1:
        errs.append("「初始化」只能出现一次，且位于第 1 步。")

    open_at = None
    for i, s in enumerate(steps, 1):
        k = s["kind"]
        if k == "loop_start":
            if open_at is not None:
                errs.append(f"第 {i} 步：不支持嵌套循环。")
            elif not (isinstance(s.get("count"), int) and s["count"] >= 1):
                errs.append(f"第 {i} 步：循环次数必须为 1 以上的整数。")
            if open_at is None:
                open_at = i
        elif k == "loop_end":
            if open_at is None:
                errs.append(f"第 {i} 步：「循环结束」前没有对应的「循环开始」。")
            open_at = None
        elif k == "valve" and not (1 <= int(s["port"]) <= ports):
            errs.append(f"第 {i} 步：端口 {s['port']} 超出阀口范围 1–{ports}。")
        elif k in ("inject", "push") and not float(s["ul"]) > 0:
            errs.append(f"第 {i} 步：体积必须大于 0。")
        elif k == "wait" and float(s["sec"]) < 0:
            errs.append(f"第 {i} 步：等待时间不能为负。")
        elif k == "init" and i != 1:
            errs.append(f"第 {i} 步：「初始化」只能放在第 1 步。")
    if open_at is not None:
        errs.append(f"第 {open_at} 步「循环开始」缺少对应的「循环结束」。")
    if errs:
        return errs, None

    # 体积推演: 循环体线性, 只需检查第 1 轮与最后一轮两端
    vol, peak, rounds = 0.0, 0.0, 0
    for seg in build_segments(steps):
        if seg[0] == "ops":
            for kind, _, _, val, no in seg[1]:
                if kind == "init":
                    vol = 0.0
                elif kind == "move":
                    vol += val
                    peak = max(peak, vol)
                    if vol < -EPS or vol > stroke + EPS:
                        return [_range_msg(no, vol, stroke, 1, 1)], None
        else:
            _, cnt, body = seg
            rounds += cnt
            d = sum(op[3] for op in body if op[0] == "move")
            for k in sorted({0, cnt - 1}):
                cur = vol + k * d
                for kind, _, _, val, no in body:
                    if kind != "move":
                        continue
                    cur += val
                    peak = max(peak, cur)
                    if cur < -EPS or cur > stroke + EPS:
                        return [_range_msg(no, cur, stroke, k + 1, cnt)], None
            vol += cnt * d
    return [], {"peak": peak, "final": vol, "rounds": rounds, "steps": len(steps)}
