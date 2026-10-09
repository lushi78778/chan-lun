# -*- coding: utf-8 -*-
"""turn 模块测试: 背驰-转折定理三分类(课 29)

覆盖分支:
- classify_bc_turn 下跌三分支(BREAK 回区间/EXPANSION 只触 DD/
  SUB_FLOOR 未及 DD)+ 端点触及边界(==ZG / ==DD);
- 上涨镜像三分支 + 边界(==ZD / ==GG);
- candidates 仅转折时非空;
- 非法 trend 抛 ValueError;
- ZS 实例与鸭子对象通吃;
- guaranteed_rebound_gap 下跌/上涨/负值/比例无定义(None)。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.turn import (TURN_BREAK, TURN_CANDIDATES, TURN_EXPANSION,
                       TURN_SUB_FLOOR, classify_bc_turn,
                       guaranteed_rebound_gap)
from chan.zs import ZS


class _Pull(object):
    """鸭子回抽单元(笔/线段/走势类型同构)"""

    def __init__(self, low, high):
        self.low = low
        self.high = high


def _center(zd=10.0, zg=11.0, gg=12.0, dd=9.0):
    return ZS(zd=zd, zg=zg, gg=gg, dd=dd, start_dt=None, end_dt=None,
              direction="down", n=3)


class TestClassifyDown(unittest.TestCase):
    """trend='down'(下跌背驰, 一买后反弹)三分类"""

    def test_break_pull_into_center(self):
        # 反弹高点回到中枢区间(ZG 之上) -> 转折, 最弱情况排除
        r = classify_bc_turn(_center(), _Pull(8.0, 11.5), "down")
        self.assertEqual(r["kind"], TURN_BREAK)
        self.assertEqual(r["candidates"], TURN_CANDIDATES)

    def test_break_boundary_touch_zg(self):
        # 端点触及口径: high == ZG 算回到区间
        r = classify_bc_turn(_center(), _Pull(9.5, 11.0), "down")
        self.assertEqual(r["kind"], TURN_BREAK)

    def test_expansion_only_dd(self):
        # 只触及 DD(9 <= high < 11) -> 最后中枢级别扩展(最弱反弹)
        r = classify_bc_turn(_center(), _Pull(8.5, 10.5), "down")
        self.assertEqual(r["kind"], TURN_EXPANSION)
        self.assertEqual(r["candidates"], [])

    def test_expansion_boundary_touch_dd(self):
        # high == DD 算触及(课 29 "反弹一定触及 DD 之上"的下界)
        r = classify_bc_turn(_center(), _Pull(8.0, 9.0), "down")
        self.assertEqual(r["kind"], TURN_EXPANSION)

    def test_sub_floor_below_dd(self):
        # 反弹连 DD 都不及 -> 定理保证之外, 标记供核查
        r = classify_bc_turn(_center(), _Pull(7.0, 8.9), "down")
        self.assertEqual(r["kind"], TURN_SUB_FLOOR)

    def test_expansion_vs_break_distinction(self):
        # 课 29: 回抽到区间与否是第一/二三种情况的分水岭
        c = _center(zd=100.0, zg=110.0, gg=115.0, dd=95.0)
        self.assertEqual(
            classify_bc_turn(c, _Pull(90.0, 109.9), "down")["kind"],
            TURN_EXPANSION)
        self.assertEqual(
            classify_bc_turn(c, _Pull(90.0, 110.0), "down")["kind"],
            TURN_BREAK)


class TestClassifyUp(unittest.TestCase):
    """trend='up'(上涨背驰, 一卖后回落)镜像三分类"""

    def test_break_pull_into_center(self):
        # 回落低点回到中枢区间(ZD 之下) -> 转折
        r = classify_bc_turn(_center(), _Pull(9.5, 13.0), "up")
        self.assertEqual(r["kind"], TURN_BREAK)
        self.assertEqual(r["candidates"], TURN_CANDIDATES)

    def test_break_boundary_touch_zd(self):
        r = classify_bc_turn(_center(), _Pull(10.0, 13.0), "up")
        self.assertEqual(r["kind"], TURN_BREAK)

    def test_expansion_only_gg(self):
        # 只触及 GG(10 < low <= 12) -> 级别扩展(最弱回落)
        r = classify_bc_turn(_center(), _Pull(11.5, 13.0), "up")
        self.assertEqual(r["kind"], TURN_EXPANSION)

    def test_expansion_boundary_touch_gg(self):
        r = classify_bc_turn(_center(), _Pull(12.0, 13.5), "up")
        self.assertEqual(r["kind"], TURN_EXPANSION)

    def test_sub_floor_above_gg(self):
        # 回落连 GG 都不及 -> 定理保证之外
        r = classify_bc_turn(_center(), _Pull(12.1, 14.0), "up")
        self.assertEqual(r["kind"], TURN_SUB_FLOOR)


class TestInputs(unittest.TestCase):
    """输入鲁棒性"""

    def test_invalid_trend(self):
        with self.assertRaises(ValueError):
            classify_bc_turn(_center(), _Pull(8.0, 11.5), "flat")

    def test_duck_center(self):
        # 鸭子中枢(无需 ZS 实例)
        class _C(object):
            zd, zg, gg, dd = 10.0, 11.0, 12.0, 9.0
        r = classify_bc_turn(_C(), _Pull(8.0, 11.5), "down")
        self.assertEqual(r["kind"], TURN_BREAK)

    def test_notes_nonempty(self):
        # 说明文字非空(便于落档)
        for kind_args in ((_Pull(8.0, 11.5),), (_Pull(8.5, 10.5),),
                          (_Pull(7.0, 8.9),)):
            r = classify_bc_turn(_center(), kind_args[0], "down")
            self.assertTrue(r["note"])


class TestGuaranteedGap(unittest.TestCase):
    """guaranteed_rebound_gap 课 29 超跌标准"""

    def test_down_gap(self):
        # (DD - price)/DD = (9 - 8.1)/9 = 0.1
        g = guaranteed_rebound_gap(_center(), 8.1, "down")
        self.assertAlmostEqual(g, 0.1)

    def test_down_price_at_dd(self):
        # 价格恰在 DD: 保证空间 0
        self.assertAlmostEqual(
            guaranteed_rebound_gap(_center(), 9.0, "down"), 0.0)

    def test_down_price_above_dd(self):
        # 价格已越过保证位: 负值(无超跌)
        self.assertLess(guaranteed_rebound_gap(_center(), 10.0, "down"), 0.0)

    def test_up_gap(self):
        # (price - GG)/GG = (13.2 - 12)/12 = 0.1
        g = guaranteed_rebound_gap(_center(), 13.2, "up")
        self.assertAlmostEqual(g, 0.1)

    def test_invalid_trend(self):
        with self.assertRaises(ValueError):
            guaranteed_rebound_gap(_center(), 10.0, "flat")

    def test_none_when_undefined(self):
        # DD<=0 / GG<=0 时比例无定义
        c = _center(zd=-2.0, zg=-1.0, gg=-0.5, dd=-3.0)
        self.assertIsNone(guaranteed_rebound_gap(c, -4.0, "down"))
        self.assertIsNone(guaranteed_rebound_gap(c, -1.0, "up"))

    def test_oversold_ranking(self):
        # 课 29: 超跌以距 DD 幅度为标准 -> 幅度大者优先
        c = _center()
        deep = guaranteed_rebound_gap(c, 7.2, "down")
        shallow = guaranteed_rebound_gap(c, 8.55, "down")
        self.assertGreater(deep, shallow)


if __name__ == "__main__":
    unittest.main()
