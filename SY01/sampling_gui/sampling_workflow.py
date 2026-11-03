# -*- coding: utf-8 -*-
"""自动采样和分发控制模块 —— 工作流定义与方案持久化。

工作流类型:
  单路分发       采样口 → 液滴(默认25μL) → 检测口远端 (吸满全行程空气推)
  四路分发+补液  采样口采样(150μL+管内空气50μL) → 排空气 → 4×25μL 分发 →
                 排余量 → 逐路气推到远端 → 培养基口补液 150μL 回采样口 (液量守恒)

方案以「名称」保存到 workflow_config.json, 含类型、参数与端口角色。
"""
import json
import os

from port_config import app_dir
from sy01_pump import FULL_STROKE_STEPS

CONFIG_FILE = os.path.join(app_dir(), "workflow_config.json")

WORKFLOW_TYPES = ("单路分发", "四路分发+补液")

DEFAULT_PARAMS = dict(
    sample_ul=25.0,       # 单路: 分样体积 / 四路: 采样体积
    dead_volume_ul=50.0,  # 采样管死体积 (采样时随样品一起抽入, 分发前排到废液)
    aliquot_ul=25.0,      # 四路: 单口分发体积
    stroke_ul=250.0,      # 进样器满行程体积
)


# ---------- 方案持久化 ----------

def load_all() -> dict:
    """返回全部已保存方案: {名称: {"wf_type", "params", "source_role", "detect_role"}}。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _write(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_workflow(name: str, params: dict, source_role: str, detect_role: str,
                  wf_type: str = "单路分发"):
    data = load_all()
    data[name] = dict(params=params, source_role=source_role,
                      detect_role=detect_role, wf_type=wf_type)
    _write(data)


def delete_workflow(name: str):
    data = load_all()
    if name in data:
        del data[name]
        _write(data)


def load_workflow(name: str):
    """返回 (params, source_role, detect_role, wf_type)；不存在时用默认值。"""
    data = load_all().get(name, {})
    params = dict(DEFAULT_PARAMS)
    saved = data.get("params", {})
    for k in params:
        if k in saved:
            params[k] = float(saved[k])
    return (params, data.get("source_role", ""), data.get("detect_role", ""),
            data.get("wf_type", "单路分发"))


# ---------- 步骤生成 ----------

def _precheck_fn(pump):
    """工作流第一步: 无条件初始化。

    手册要求: 设备上电后必须 ZR 复位方可操作; 泉断电重启后未初始化状态
    在静止时 Q 查询不报错, 只有运动时才报错误7, 因此每次流程开始都初始化。
    """
    def precheck():
        pump.init_pump()
    return precheck


def _goto(pump, port):
    return lambda: pump.valve_goto(port)


def _move(pump, pos):
    return lambda: pump.plunger_goto(pos)


def _combined(*fns):
    return lambda: [f() for f in fns]


def build_workflow(pump, ports: dict, params: dict, wf_type: str = "单路分发"):
    """按类型分发步骤生成。"""
    if wf_type == "四路分发+补液":
        return _build_multi(pump, ports, params)
    return _build_single(pump, ports, params)


def _build_single(pump, ports: dict, params: dict):
    """单路分发: 排空 → 预充采样管(排净空气) → 采样 → 分发液滴 → 推气到远端。

    ports:  dict(source, detect, waste, air)
    params: dict(sample_ul, dead_volume_ul, stroke_ul)
    """
    steps = []
    sample_steps = pump.vol_to_steps(params["sample_ul"])
    dead_steps = pump.vol_to_steps(params["dead_volume_ul"])

    add = lambda desc, fn: steps.append((desc, fn))

    add("[0] 状态预检/自动初始化", _precheck_fn(pump))
    add("[1] 阀→备用, 排空进样器",
        _combined(lambda: pump.valve_goto(ports["waste"]), _move(pump, 0)))
    add(f"[2] 预充采样管: 阀→采样口, 抽 {params['dead_volume_ul']:g}μL",
        _combined(_goto(pump, ports["source"]), _move(pump, dead_steps)))
    add("[3] 阀→备用, 排出预充液 (排净采样管空气)",
        _combined(_goto(pump, ports["waste"]), _move(pump, 0)))
    add(f"[4] 阀→采样口, 采样 {params['sample_ul']:g}μL",
        _combined(_goto(pump, ports["source"]), _move(pump, sample_steps)))
    add(f"[5] 阀→检测口 (Port {ports['detect']}), 分发 {params['sample_ul']:g}μL 液滴",
        _combined(_goto(pump, ports["detect"]), _move(pump, 0)))
    add("[6] 阀→空气口, 吸满全行程空气",
        _combined(lambda: pump.valve_goto(ports["air"]),
                  _move(pump, FULL_STROKE_STEPS)))
    add("[7] 阀→检测口, 推气: 液滴压向远端",
        _combined(_goto(pump, ports["detect"]), _move(pump, 0)))
    return steps


def _build_multi(pump, ports: dict, params: dict):
    """四路分发+补液: 排空 → 预充采样管 → 采样 → 4×分发 → 排余 →
    逐路气推 → 培养基补液回采样口 (液量守恒)。

    ports:  dict(source, waste, air, medium, detects=[4个检测口号])
    params: dict(sample_ul, dead_volume_ul, aliquot_ul, stroke_ul)
    """
    steps = []
    sample_steps = pump.vol_to_steps(params["sample_ul"])
    dead_steps = pump.vol_to_steps(params["dead_volume_ul"])
    ali_steps = pump.vol_to_steps(params["aliquot_ul"])
    detects = ports["detects"]

    add = lambda desc, fn: steps.append((desc, fn))

    add("[0] 状态预检/自动初始化", _precheck_fn(pump))
    add("[1] 阀→备用, 排空进样器",
        _combined(lambda: pump.valve_goto(ports["waste"]), _move(pump, 0)))
    add(f"[2] 预充采样管: 阀→采样口, 抽 {params['dead_volume_ul']:g}μL",
        _combined(_goto(pump, ports["source"]), _move(pump, dead_steps)))
    add("[3] 阀→备用, 排出预充液 (排净采样管空气)",
        _combined(_goto(pump, ports["waste"]), _move(pump, 0)))
    add(f"[4] 阀→采样口, 采样 {params['sample_ul']:g}μL",
        _combined(_goto(pump, ports["source"]), _move(pump, sample_steps)))

    pos = sample_steps
    for i, port in enumerate(detects):
        add(f"[5.{i + 1}] 阀→检测口{i + 1} (Port {port})", _goto(pump, port))
        pos -= ali_steps
        add(f"[5.{i + 1}] 分发 {params['aliquot_ul']:g}μL → 检验口{i + 1}",
            _move(pump, pos))

    add("[排余] 阀→备用, 排余量",
        _combined(lambda: pump.valve_goto(ports["waste"]), _move(pump, 0)))
    for i, port in enumerate(detects):
        add(f"[气推{i + 1}.1] 阀→空气口, 吸满空气",
            _combined(lambda: pump.valve_goto(ports["air"]),
                      _move(pump, FULL_STROKE_STEPS)))
        add(f"[气推{i + 1}] 阀→检测口{i + 1} (Port {port}), 推气到远端",
            _combined(_goto(pump, port), _move(pump, 0)))
    add(f"[补液] 阀→培养基 (Port {ports['medium']}), 抽液 {params['sample_ul']:g}μL",
        _combined(lambda: pump.valve_goto(ports["medium"]),
                  _move(pump, sample_steps)))
    add(f"[补液] 阀→采样口 (Port {ports['source']}), 补液 {params['sample_ul']:g}μL",
        _combined(_goto(pump, ports["source"]), _move(pump, 0)))
    return steps
