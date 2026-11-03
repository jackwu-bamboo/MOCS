# -*- coding: utf-8 -*-
"""阀口角色映射配置：默认位置可由客户调整，持久化到 port_config.json。"""
import json
import os
import sys
from collections import OrderedDict


def app_dir() -> str:
    """配置文件目录: 打包后为 exe 所在目录, 源码运行为脚本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(app_dir(), "port_config.json")

DEFAULT_PORT_COUNT = 10

# 角色 -> 默认阀口位置（客户可在界面中调整）
DEFAULT_PORT_MAP = OrderedDict([
    ("采样口1", 2),
    ("采样口2", 3),
    ("采样口3", 5),
    ("培养基", 6),
    ("备用", 8),
    ("空气", 9),
    ("检测口1", 1),
    ("检测口2", 4),
    ("检测口3", 7),
    ("检测口4", 10),
])

ROLE_COLORS = {
    "采样口": "#ea580c",
    "培养基": "#16a34a",
    "备用": "#64748b",
    "空气": "#06b6d4",
    "检测口": "#2563eb",
}


def role_color(role: str) -> str:
    for prefix, color in ROLE_COLORS.items():
        if role.startswith(prefix):
            return color
    return "#334155"


def load_config():
    """返回 (port_count, mapping)。配置缺失或损坏时回退默认值。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = int(data.get("port_count", DEFAULT_PORT_COUNT))
            saved = data.get("mapping", {})
            mapping = OrderedDict(DEFAULT_PORT_MAP)
            for role, port in saved.items():
                if role in mapping:
                    mapping[role] = int(port)
            return count, mapping
        except Exception:
            pass
    return DEFAULT_PORT_COUNT, OrderedDict(DEFAULT_PORT_MAP)


def save_config(port_count: int, mapping) -> bool:
    """保存配置；端口重复时返回 False 不写入。"""
    ports = [int(v) for v in mapping.values()]
    if len(ports) != len(set(ports)):
        return False
    if any(p < 1 or p > int(port_count) for p in ports):
        return False
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"port_count": int(port_count), "mapping": dict(mapping)},
                  f, ensure_ascii=False, indent=2)
    return True
