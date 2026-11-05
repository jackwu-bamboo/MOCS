# -*- coding: utf-8 -*-
"""流程模型单元测试 (不需要硬件): python -m unittest test_flow -v"""
import unittest

from sampling_workflow import (
    build_segments, execute_op, iter_ops, validate,
)

from sy01_pump import DEFAULT_FLOW_UL_S, DEFAULT_SYRINGE_UL, FULL_STROKE_STEPS, Sy01SerialPump

SETTINGS = dict(port_count=10, stroke_ul=DEFAULT_SYRINGE_UL, flow_speed_ul_s=DEFAULT_FLOW_UL_S)


def st(ul):
    """体积 μL -> 期望步数, 随进样器规格自动换算。"""
    return round(FULL_STROKE_STEPS * ul / DEFAULT_SYRINGE_UL)


def S(kind, **kw):
    return dict(kind=kind, **kw)


INIT = S("init", wait=0.0)  # 测试中不等待


class FakePump:
    """桩泵: 记录指令, 活塞位置按 plunger_goto 更新。"""

    def __init__(self):
        self.current_steps = 0
        self.calls = []
        self._abort = False

    def init_pump(self):
        self.calls.append(("init",))
        self.current_steps = 0

    def valve_goto(self, port):
        self.calls.append(("valve", port))

    def plunger_goto(self, steps):
        self.calls.append(("plunger", steps))
        self.current_steps = steps


class ValidateTests(unittest.TestCase):

    def test_valid_flow_summary(self):
        steps = [INIT, S("valve", port=2), S("inject", ul=50), S("valve", port=8), S("push", ul=50)]
        errs, summ = validate(steps, SETTINGS)
        self.assertEqual(errs, [])
        self.assertAlmostEqual(summ["peak"], 50)
        self.assertAlmostEqual(summ["final"], 0)
        self.assertEqual(summ["rounds"], 0)

    def test_empty_flow(self):
        errs, _ = validate([], SETTINGS)
        self.assertTrue(errs)

    def test_first_step_must_be_init(self):
        errs, _ = validate([S("valve", port=2)], SETTINGS)
        self.assertTrue(any("第 1 步必须是「初始化」" in e for e in errs))

    def test_init_inside_loop_rejected(self):
        steps = [INIT, S("loop_start", count=2), S("init", wait=3), S("loop_end")]
        errs, _ = validate(steps, SETTINGS)
        self.assertTrue(any("只能放在第 1 步" in e for e in errs))

    def test_nested_loop_rejected(self):
        steps = [INIT, S("loop_start", count=2), S("loop_start", count=2), S("loop_end"), S("loop_end")]
        errs, _ = validate(steps, SETTINGS)
        self.assertTrue(any("嵌套" in e for e in errs))

    def test_unclosed_loop_rejected(self):
        steps = [INIT, S("loop_start", count=2), S("valve", port=1)]
        errs, _ = validate(steps, SETTINGS)
        self.assertTrue(any("缺少对应的「循环结束」" in e for e in errs))

    def test_loop_end_without_start(self):
        errs, _ = validate([INIT, S("loop_end")], SETTINGS)
        self.assertTrue(any("没有对应的「循环开始」" in e for e in errs))

    def test_loop_count_must_be_positive(self):
        steps = [INIT, S("loop_start", count=0), S("loop_end")]
        errs, _ = validate(steps, SETTINGS)
        self.assertTrue(any("循环次数" in e for e in errs))

    def test_port_out_of_range(self):
        errs, _ = validate([INIT, S("valve", port=11)], SETTINGS)
        self.assertTrue(any("超出阀口范围" in e for e in errs))

    def test_push_more_than_contained(self):
        steps = [INIT, S("inject", ul=50), S("push", ul=60)]
        errs, _ = validate(steps, SETTINGS)
        self.assertEqual(len(errs), 1)
        self.assertIn("第 3 步", errs[0])
        self.assertIn("液量", errs[0])

    def test_inject_over_capacity(self):
        steps = [INIT, S("inject", ul=DEFAULT_SYRINGE_UL * 0.8), S("inject", ul=DEFAULT_SYRINGE_UL * 0.5)]
        errs, _ = validate(steps, SETTINGS)
        self.assertIn("第 3 步", errs[0])
        self.assertIn("超过容量", errs[0])

    def test_loop_drift_detected_on_last_round(self):
        # 每轮净增 20 μL: 第 1 轮峰值 50, 第 100 轮末必然超过容量 (任何规格)
        steps = [INIT, S("loop_start", count=100), S("inject", ul=50), S("push", ul=30), S("loop_end")]
        errs, _ = validate(steps, SETTINGS)
        self.assertTrue(errs)
        self.assertIn("轮", errs[0])

    def test_loop_within_range_passes(self):
        steps = [INIT, S("loop_start", count=3), S("inject", ul=50), S("push", ul=30), S("loop_end")]
        errs, summ = validate(steps, SETTINGS)
        self.assertEqual(errs, [])
        self.assertEqual(summ["rounds"], 3)
        self.assertAlmostEqual(summ["final"], 60)

    def test_huge_loop_validates_quickly(self):
        steps = [INIT, S("loop_start", count=10**9), S("inject", ul=10), S("push", ul=10), S("loop_end")]
        errs, summ = validate(steps, SETTINGS)
        self.assertEqual(errs, [])
        self.assertEqual(summ["rounds"], 10**9)


class ExecutionTests(unittest.TestCase):

    def run_flow(self, steps):
        pump = FakePump()
        for op in iter_ops(build_segments(steps)):
            execute_op(pump, op, SETTINGS["stroke_ul"])
        return pump.calls

    def test_fixed_flow_commands(self):
        steps = [INIT, S("valve", port=2), S("inject", ul=50), S("valve", port=8), S("push", ul=50)]
        calls = self.run_flow(steps)
        self.assertEqual(calls, [
            ("init",), ("valve", 2), ("plunger", st(50)), ("valve", 8), ("plunger", 0),
        ])

    def test_init_runs_once_loop_body_repeats(self):
        steps = [INIT, S("loop_start", count=2), S("valve", port=2), S("inject", ul=50),
                 S("valve", port=8), S("push", ul=50), S("loop_end")]
        calls = self.run_flow(steps)
        self.assertEqual(sum(1 for c in calls if c[0] == "init"), 1)
        self.assertEqual(calls, [
            ("init",), ("valve", 2), ("plunger", st(50)), ("valve", 8), ("plunger", 0),
            ("valve", 2), ("plunger", st(50)), ("valve", 8), ("plunger", 0),
        ])

    def test_round_labels(self):
        steps = [INIT, S("loop_start", count=2), S("valve", port=2), S("loop_end")]
        labels = [op[2] for op in iter_ops(build_segments(steps))]
        self.assertEqual(labels, ["", "第 1/2 轮", "第 2/2 轮"])

    def test_wait_step(self):
        steps = [INIT, S("wait", sec=0)]
        calls = self.run_flow(steps)
        self.assertEqual(calls, [("init",)])


class SpeedTests(unittest.TestCase):

    def test_default_speed_matches_pump_4000_pps(self):
        # 默认 μL/s 换算回脉冲速度应等于泵实测的 4000 脉冲/秒
        pump = Sy01SerialPump("X", stroke_ul=DEFAULT_SYRINGE_UL, speed_ul_s=DEFAULT_FLOW_UL_S)
        self.assertEqual(pump.pulse_per_s, 4000)

    def test_speed_out_of_range_rejected(self):
        steps = [INIT, S("inject", ul=10)]
        errs, _ = validate(steps, dict(SETTINGS, flow_speed_ul_s=DEFAULT_SYRINGE_UL * 2))
        self.assertTrue(any("速度" in e for e in errs))

    def test_move_command_carries_velocity(self):
        pump = Sy01SerialPump("X", stroke_ul=500.0, speed_ul_s=250.0)
        sent = []
        pump._motion = lambda body, verify, desc, max_tries=3: sent.append(body)
        pump.plunger_goto(2400)
        # 250 μL/s @ 500 μL 规格 -> 6000 脉冲/秒
        self.assertEqual(sent, ["V6000A2400R"])

    def test_speed_follows_syringe_when_ul_s_kept(self):
        pump = Sy01SerialPump("X", stroke_ul=250.0, speed_ul_s=100.0)
        self.assertEqual(pump.pulse_per_s, 4800)
        pump.stroke_ul = 500.0
        self.assertEqual(pump.pulse_per_s, 2400)

if __name__ == "__main__":
    unittest.main()
