# -*- coding: utf-8 -*-
"""chan.nest 多级区间套定位(课 61/37)单元测试

覆盖分支:
  单级判定(TestLevel):
    - up 背驰成立(默认 MACD 口径, 合成 K 线)/力度更强证伪/未创新高/
      柱面积符号异常/自定义 strength_fn 注入
    - down 镜像(背驰成立/未创新低)
  嵌套链(TestChain):
    - 两级全成立 -> complete + turn 定位
    - 第二级 stronger 断裂 -> break_level=2, 第一重保留
    - 第一级 stronger 断裂 -> break_level=1
    - 结构校验 not_nested
    - 空输入 empty
    - center 落档 + to_dict 结构
"""

from __future__ import print_function

import os
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.nest import (BcNestInput, NestBcState, nested_bc,  # noqa: E402
                       REASON_BC, REASON_EMPTY, REASON_NO_EXTREME,
                       REASON_NOT_NESTED, REASON_STRONGER, REASON_WEAK_SIGN)

# 鸭子类型 move: high/low/start_dt/end_dt(笔/线段/走势类型通吃口径)
M = namedtuple("M", ["low", "high", "start_dt", "end_dt"])


def _bars_from_closes(dts, closes):
    """合成 bars(仅 dt/close, MACD 面积口径够用)"""
    return [{"dt": d, "close": float(c)} for d, c in zip(dts, closes)]


def _up_fixture(strong=True):
    """向上单级 fixture(默认 MACD 口径可用; 参数经网格搜索标定)

    结构: 30 根平盘预热 + 18 根强升(100->145) + 8 根深回调(->110)
    + 18 根恢复升(->146 创新高)。strong=True 恢复段斜率 3.0(柱面积
    11.8 < 对照段 64.8 -> 背驰); strong=False 斜率 5.5(柱面积 76.6
    >= 64.8 -> 力度更强证伪)。
    """
    warm, ref_n, ref_step = 30, 18, 2.5
    n_pull, pull_to, cand_n = 8, 110.0, 18
    cand_step = 3.0 if strong else 5.5
    closes = [100.0] * warm
    ref_c = [100.0 + ref_step * (i + 1) for i in range(ref_n)]
    closes += ref_c
    top = ref_c[-1]
    closes += [top + (pull_to - top) * (i + 1) / n_pull
               for i in range(n_pull)]
    closes += [pull_to + cand_step * (i + 1) for i in range(cand_n)]
    closes[-1] = top + 1.0  # 保证严格创新高
    dts = ["2026-%02d-%02d" % (1 + i // 28, i % 28 + 1)
           for i in range(len(closes))]
    bars = _bars_from_closes(dts, closes)
    ref = M(100.0, top, dts[warm], dts[warm + ref_n - 1])
    cand = M(pull_to, closes[-1],
             dts[warm + ref_n + n_pull], dts[-1])
    return bars, ref, cand


def _down_fixture(strong=True):
    """向下镜像 fixture: 200-x 变换(MACD 线性, 面积严格反号)"""
    bars, ref, cand = _up_fixture(strong)
    mbars = [{"dt": b["dt"], "close": 200.0 - b["close"]} for b in bars]
    mref = M(200.0 - ref.high, 200.0 - ref.low,
             ref.start_dt, ref.end_dt)
    mcand = M(200.0 - cand.high, 200.0 - cand.low,
              cand.start_dt, cand.end_dt)
    return mbars, mref, mcand


class TestLevel(unittest.TestCase):
    """单级背驰段判定(课 61 三条规则)"""

    def test_up_bc_default_macd(self):
        # 默认口径: 候选段 MACD 柱面积 < 对照段 且创新高 -> 背驰段成立
        bars, ref, cand = _up_fixture(strong=True)
        st = nested_bc([BcNestInput("up", ref, cand, bars)])
        self.assertTrue(st.complete)
        self.assertEqual(len(st.levels), 1)
        lv = st.levels[0]
        self.assertTrue(lv.bc)
        self.assertEqual(lv.reason, REASON_BC)
        self.assertTrue(lv.new_extreme)
        self.assertGreater(lv.ref_strength, 0.0)
        self.assertGreater(lv.cand_strength, 0.0)
        self.assertLess(lv.cand_strength, lv.ref_strength)
        self.assertIsNotNone(lv.ratio)
        self.assertLess(lv.ratio, 1.0)
        # 转折点定位: 候选段终点/极值
        self.assertEqual(st.turn_dt, str(cand.end_dt))
        self.assertEqual(st.turn_price, cand.high)

    def test_up_stronger(self):
        # 候选段力度 >= 对照段 -> 背驰段不成立(课 61 证伪规则)
        bars, ref, cand = _up_fixture(strong=False)
        st = nested_bc([BcNestInput("up", ref, cand, bars)])
        self.assertFalse(st.complete)
        lv = st.levels[0]
        self.assertFalse(lv.bc)
        self.assertEqual(lv.reason, REASON_STRONGER)
        self.assertEqual(st.break_level, 1)
        self.assertIsNone(st.turn_dt)

    def test_up_no_new_extreme(self):
        # 候选段未超过对照段高点 -> 背驰不存在(课 61)
        bars, ref, cand = _up_fixture(strong=True)
        flat = M(cand.low, ref.high - 1.0, cand.start_dt,
                 cand.end_dt)
        st = nested_bc([BcNestInput("up", ref, flat, bars)])
        self.assertFalse(st.complete)
        self.assertEqual(st.levels[0].reason, REASON_NO_EXTREME)
        self.assertFalse(st.levels[0].new_extreme)

    def test_up_weak_sign(self):
        # 候选段柱面积非正(红柱未主导) -> 动能异常不判背驰
        bars, ref, cand = _up_fixture(strong=True)

        def _fn(bs, move):
            if move is cand:
                return -3.0  # 候选段绿柱主导
            return 10.0

        st = nested_bc([BcNestInput("up", ref, cand, None)],
                       strength_fn=_fn)
        self.assertFalse(st.complete)
        self.assertEqual(st.levels[0].reason, REASON_WEAK_SIGN)
        self.assertTrue(st.levels[0].new_extreme)  # 创新高先于符号检查

    def test_custom_strength_fn(self):
        # 注入自定义力度(如振幅): 候选段振幅 36 < 对照段 45 -> 背驰成立
        bars, ref, cand = _up_fixture(strong=True)

        def _gain(bs, move):
            return (move.high - move.low) / 1.0

        st = nested_bc([BcNestInput("up", ref, cand, bars)],
                       strength_fn=_gain)
        self.assertTrue(st.complete)
        self.assertEqual(st.levels[0].reason, REASON_BC)
        self.assertEqual(st.levels[0].ref_strength, 45.0)
        self.assertEqual(st.levels[0].cand_strength, 36.0)

    def test_down_bc_mirror(self):
        # 向下镜像: 候选段绿柱面积绝对值更小且创新低 -> 背驰段成立
        bars, ref, cand = _down_fixture(strong=True)
        st = nested_bc([BcNestInput("down", ref, cand, bars)])
        self.assertTrue(st.complete)
        lv = st.levels[0]
        self.assertTrue(lv.bc)
        self.assertEqual(lv.reason, REASON_BC)
        self.assertLess(lv.cand_strength, 0.0)
        self.assertLess(lv.ref_strength, 0.0)
        self.assertLess(abs(lv.cand_strength), abs(lv.ref_strength))
        self.assertEqual(st.turn_price, cand.low)

    def test_down_no_new_low(self):
        bars, ref, cand = _down_fixture(strong=True)
        shallow = M(ref.low + 1.0, cand.high,
                    cand.start_dt, cand.end_dt)
        st = nested_bc([BcNestInput("down", ref, shallow, bars)])
        self.assertFalse(st.complete)
        self.assertEqual(st.levels[0].reason, REASON_NO_EXTREME)


class TestChain(unittest.TestCase):
    """嵌套背驰段链(课 61 区间套 / 课 37 同构递归)"""

    @staticmethod
    def _two_levels(second_bc=True):
        """两级输入: 第 1 重日线级 + 第 2 重 30m 级(嵌套于第 1 重候选段内)"""
        # 第 1 重: 强升对照 -> 弱升候选(创新高), 力度用注入函数控死
        ref1 = M(10.0, 12.0, "2026-03-01", "2026-03-20")
        cand1 = M(11.0, 12.5, "2026-03-25", "2026-04-05")
        # 第 2 重: cand1 内部的次级别两段
        ref2 = M(11.0, 12.2, "2026-03-25", "2026-03-30")
        cand2 = M(12.0, 12.5, "2026-04-01", "2026-04-05")
        s1 = (3.0, 1.0)
        s2 = (3.0, 1.0) if second_bc else (1.0, 3.0)

        def _fn(bs, move):
            if move is ref1:
                return s1[0]
            if move is cand1:
                return s1[1]
            if move is ref2:
                return s2[0]
            return s2[1]

        return [BcNestInput("up", ref1, cand1, None),
                BcNestInput("up", ref2, cand2, None)], _fn

    def test_two_levels_complete(self):
        # 两重全部成立 -> 区间套定位成立, 转折点 = 最内一级候选段端点
        inputs, fn = self._two_levels(second_bc=True)
        st = nested_bc(inputs, strength_fn=fn)
        self.assertTrue(st.complete)
        self.assertEqual(len(st.levels), 2)
        self.assertEqual(st.depth, 2)
        self.assertIsNone(st.break_level)
        self.assertEqual(st.turn_dt, "2026-04-05")
        self.assertEqual(st.turn_price, 12.5)
        # 各重落档
        self.assertEqual([x.level for x in st.levels], [1, 2])
        self.assertTrue(all(x.bc for x in st.levels))

    def test_second_level_breaks(self):
        # 第 2 重力度更强 -> 链在第 2 重断裂, 第 1 重保留成立
        inputs, fn = self._two_levels(second_bc=False)
        st = nested_bc(inputs, strength_fn=fn)
        self.assertFalse(st.complete)
        self.assertEqual(st.break_level, 2)
        self.assertEqual(st.break_reason, REASON_STRONGER)
        self.assertEqual(len(st.levels), 2)
        self.assertTrue(st.levels[0].bc)
        self.assertFalse(st.levels[1].bc)
        self.assertEqual(st.depth, 1)
        self.assertIsNone(st.turn_dt)

    def test_first_level_breaks(self):
        # 第 1 重即证伪 -> 更细级别无须看, levels 只含第 1 重
        inputs, fn = self._two_levels(second_bc=True)
        ref1 = inputs[0].ref_move
        cand1 = inputs[0].cand_move

        def _fn_first(bs, move):
            if move is ref1:
                return 1.0
            if move is cand1:
                return 3.0  # 第 1 重即更强
            return 1.0

        st = nested_bc(inputs, strength_fn=_fn_first)
        self.assertFalse(st.complete)
        self.assertEqual(st.break_level, 1)
        self.assertEqual(len(st.levels), 1)

    def test_not_nested(self):
        # 第 2 重候选段区间不在第 1 重候选段内 -> 结构断裂
        inputs, fn = self._two_levels(second_bc=True)
        inputs[1].cand_move = M(12.0, 12.5, "2026-02-01", "2026-02-10")
        st = nested_bc(inputs, strength_fn=fn)
        self.assertFalse(st.complete)
        self.assertEqual(st.break_reason, REASON_NOT_NESTED)
        self.assertEqual(st.break_level, 2)
        self.assertEqual(len(st.levels), 1)  # 断裂级不产生判定结果

    def test_nested_equal_range_allowed(self):
        # 相等区间视为嵌套(含相等, 宽松口径)
        inputs, fn = self._two_levels(second_bc=True)
        inputs[1].cand_move = M(11.0, 12.5, "2026-03-25", "2026-04-05")
        st = nested_bc(inputs, strength_fn=fn)
        self.assertTrue(st.complete)

    def test_empty(self):
        st = nested_bc([])
        self.assertFalse(st.complete)
        self.assertEqual(st.break_reason, REASON_EMPTY)
        self.assertEqual(st.levels, [])

    def test_center_recorded_and_to_dict(self):
        # center 仅落档不参与判定; to_dict 结构完整
        C = namedtuple("C", ["zd", "zg"])
        bars, ref, cand = _up_fixture(strong=True)
        st = nested_bc([BcNestInput("up", ref, cand, bars,
                                    center=C(11.5, 12.0))])
        self.assertTrue(st.complete)
        d = st.to_dict()
        self.assertTrue(d["complete"])
        self.assertEqual(d["depth"], 1)
        self.assertIn("levels", d)
        lv = d["levels"][0]
        self.assertEqual(lv["zd"], 11.5)
        self.assertEqual(lv["zg"], 12.0)
        self.assertEqual(lv["reason"], REASON_BC)
        self.assertIn("ratio", lv)
        self.assertIn("new_extreme", lv)
        self.assertEqual(d["turn_dt"], str(cand.end_dt))

    def test_state_class_smoke(self):
        # NestBcState 直接构造 smoke(字段/默认值)
        st = NestBcState([], False, None, REASON_EMPTY)
        self.assertEqual(st.depth, 0)
        self.assertIsNone(st.turn_price)
        d = st.to_dict()
        self.assertEqual(d["levels"], [])


if __name__ == "__main__":
    unittest.main()
