# -*- coding: utf-8 -*-
"""minor_turn 模块测试: 小级别背驰引发大级别转折(课 44/53)

覆盖分支:
- classify_minor_turn trend='up' 四档(未破/未触及次级别中枢/次级别
  三卖/跌破三买回试段高点)+ 端点触及(==)边界 + 优先级(breakout
  压过 sub_bs3);
- trend='down' 镜像四档 + 边界;
- sub_center=None 退化(跳过最强档);
- 非法 trend 抛 ValueError;
- necessary_met 字段语义(= sub_bs3, 仅必要非充分)。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.minor_turn import (STAGE_BREAKOUT, STAGE_STRONG, STAGE_SUB_BS3,  # noqa: E402
                             STAGE_WITHIN, classify_minor_turn)


class _M(object):
    """鸭子走势单元"""

    def __init__(self, low, high):
        self.low = low
        self.high = high


class _ZS(object):
    """鸭子次级别中枢"""

    def __init__(self, zd, zg):
        self.zd = zd
        self.zg = zg


# 上涨大级别场景基线: 三买回试段高点 10.0, 次级别中枢 [8.0, 9.0]
_TRI_UP = _M(9.2, 10.0)
_SUB_UP = _ZS(8.0, 9.0)


class TestTrendUp(unittest.TestCase):
    """trend='up'(大级别向上+小顶背驰)四档"""

    def test_within_valid(self):
        # 三买回试段高点 8.8; 向下走势低点 8.9(未破)但触及中枢
        # [8.0, 9.0](8.9 <= zg=9.0) -> within
        tri = _M(8.0, 8.8)
        counter = _M(8.9, 11.0)
        r = classify_minor_turn(tri, counter, "up", sub_center=_SUB_UP)
        self.assertEqual(r["stage"], STAGE_WITHIN)
        self.assertFalse(r["necessary_met"])

    def test_strong(self):
        # 低点未破三买回试段高点且未触及次级别中枢(low > zg)
        tri = _M(9.2, 10.0)
        counter = _M(10.5, 11.2)   # low 10.5 > 10.0 未破, > 9.0 未触及
        r = classify_minor_turn(tri, counter, "up", sub_center=_SUB_UP)
        self.assertEqual(r["stage"], STAGE_STRONG)

    def test_sub_bs3(self):
        # 未破回试段高点, 次级别中枢已现三卖 -> 先出一部分
        tri = _M(9.2, 10.0)
        counter = _M(9.5, 11.0)    # low 9.5 > 10.0? 不, 9.5 < 10.0 会破
        # 重新构造: 回试段高点 9.4, 向下低点 9.5 未破且触及中枢
        tri2 = _M(9.0, 9.4)
        counter2 = _M(9.5, 11.0)
        r = classify_minor_turn(tri2, counter2, "up", sub_center=_SUB_UP,
                                sub_bs3=True)
        self.assertEqual(r["stage"], STAGE_SUB_BS3)
        self.assertTrue(r["necessary_met"])

    def test_breakout(self):
        # 跌破三买回试段高点(low <= tri.high) -> 任何回抽先离场
        r = classify_minor_turn(_TRI_UP, _M(9.9, 11.0), "up")
        self.assertEqual(r["stage"], STAGE_BREAKOUT)

    def test_breakout_boundary_touch(self):
        # 端点触及口径: low == tri.high 算破
        r = classify_minor_turn(_TRI_UP, _M(10.0, 11.0), "up")
        self.assertEqual(r["stage"], STAGE_BREAKOUT)

    def test_breakout_priority_over_sub_bs3(self):
        # 同时满足破位与次级别三卖 -> breakout 优先(课 44: 先出部分
        # 后出现破位情形再出清)
        r = classify_minor_turn(_TRI_UP, _M(9.9, 11.0), "up", sub_bs3=True)
        self.assertEqual(r["stage"], STAGE_BREAKOUT)
        self.assertTrue(r["necessary_met"])


class TestTrendDown(unittest.TestCase):
    """trend='down'(大级别向下+小底背驰)镜像四档"""

    def test_within(self):
        # 三卖回抽段低点 11.2; 向上走势高点 11.1(未破)且触及中枢
        # [11.0, 12.0](11.1 >= zd=11.0) -> within
        tri = _M(11.2, 12.5)
        counter = _M(10.0, 11.1)
        sub = _ZS(11.0, 12.0)
        r = classify_minor_turn(tri, counter, "down", sub_center=sub)
        self.assertEqual(r["stage"], STAGE_WITHIN)

    def test_strong(self):
        # 向上高点未破三卖回抽低点且未触及中枢(high < zd)
        tri = _M(11.2, 12.5)
        counter = _M(9.0, 10.5)   # high 10.5 < 11.2 未破, < 11.0 未触及
        sub = _ZS(11.0, 12.0)
        r = classify_minor_turn(tri, counter, "down", sub_center=sub)
        self.assertEqual(r["stage"], STAGE_STRONG)

    def test_sub_bs3(self):
        tri = _M(12.0, 12.6)
        counter = _M(10.0, 11.9)  # high 11.9 < 12.0 未破且触及中枢
        sub = _ZS(11.0, 12.0)
        r = classify_minor_turn(tri, counter, "down", sub_center=sub,
                                sub_bs3=True)
        self.assertEqual(r["stage"], STAGE_SUB_BS3)
        self.assertTrue(r["necessary_met"])

    def test_breakout(self):
        # 向上走势高点 >= 三卖回抽段低点 -> 突破(空方离场信号)
        tri = _M(11.2, 12.5)
        r = classify_minor_turn(tri, _M(10.0, 11.3), "down")
        self.assertEqual(r["stage"], STAGE_BREAKOUT)

    def test_breakout_boundary_touch(self):
        tri = _M(11.2, 12.5)
        r = classify_minor_turn(tri, _M(10.0, 11.2), "down")
        self.assertEqual(r["stage"], STAGE_BREAKOUT)


class TestInputs(unittest.TestCase):
    """输入鲁棒性"""

    def test_invalid_trend(self):
        with self.assertRaises(ValueError):
            classify_minor_turn(_TRI_UP, _M(9.0, 11.0), "flat")

    def test_no_sub_center_degrades(self):
        # sub_center=None: 未破回试段且无三卖 -> within(跳过最强档)
        tri = _M(9.2, 10.0)
        counter = _M(10.5, 11.2)  # 若有中枢应为 strong
        r = classify_minor_turn(tri, counter, "up", sub_center=None)
        self.assertEqual(r["stage"], STAGE_WITHIN)

    def test_no_sub_center_with_bs3(self):
        # sub_center=None 但三卖已现 -> sub_bs3 照常
        tri = _M(9.2, 10.0)
        counter = _M(10.5, 11.2)
        r = classify_minor_turn(tri, counter, "up", sub_center=None,
                                sub_bs3=True)
        self.assertEqual(r["stage"], STAGE_SUB_BS3)

    def test_notes_nonempty(self):
        r = classify_minor_turn(_TRI_UP, _M(9.9, 11.0), "up")
        self.assertTrue(r["note"])


if __name__ == "__main__":
    unittest.main()
