# -*- coding: utf-8 -*-
"""中枢震荡监视器测试(课 92)

覆盖分支:
    - 空输入: status="empty"
    - 震荡中轴 Z=(A+B)/2, Zn=每单元区间一半位置
    - Zn 在 (A,B) 内: positions above_Z/below_Z 与强弱计数
    - Zn 超越 B: break_up 事件, status="breaking"(课 92 变盘提醒)
    - Zn 超越 A: break_down 事件
    - 超越可多次: 事件逐条记录(只有最后一次才构成第三类买卖点)
    - Zn 数达 9: upgrade_hint(次级别升级, 课 92/20/69)
    - 上升楔型: Zn 单调抬升但全程未超越 B -> rising_wedge 诱多
    - 下降楔型镜像 -> falling_wedge 诱空
    - 有超越则不判楔型
    - 次级别趋势类型配合: kind=up/down 计入 trend_unit_idx
    - 末次级别中枢整体在被监视中枢之外: outer_center_unit_idx
    - osc_strength: 偏强/偏弱/均衡
    - zn_next_estimate: 线性外推 + 平均半振幅; 单元不足返回 None
    - to_dict 字段完整
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.osc import (  # noqa: E402
    OSC_UPGRADE_N, OscReport, osc_strength, oscillation_monitor,
    zn_next_estimate)


class U(object):
    """测试桩: 只需 low/high 的次级别单元"""

    def __init__(self, low, high, kind=None, centers=None):
        self.low = float(low)
        self.high = float(high)
        if kind is not None:
            self.kind = kind
        if centers is not None:
            self.centers = centers


# 中枢区间 [A, B] = [10, 20], Z = 15
C = (10.0, 20.0)


class TestOscillationMonitor(unittest.TestCase):

    def test_empty(self):
        """空输入: status=empty, Z 仍可算"""
        r = oscillation_monitor(C, [])
        self.assertEqual(r.status, "empty")
        self.assertEqual(r.z, 15.0)
        self.assertEqual(r.zns, [])
        self.assertEqual(osc_strength(r), "empty")

    def test_zn_math(self):
        """Zn = 单元区间一半位置; Z = (A+B)/2; A/Z/B 等距"""
        r = oscillation_monitor(C, [U(10, 20), U(12, 16)])
        self.assertEqual(r.z, 15.0)
        self.assertEqual(r.zns, [(0, 15.0), (1, 14.0)])

    def test_in_range_positions(self):
        """Zn 在 (A,B) 内: above_Z/below_Z 分类与计数"""
        r = oscillation_monitor(C, [U(10, 20), U(16, 18), U(11, 13)])
        self.assertEqual(r.status, "in_range")
        self.assertEqual(r.positions, ["above_Z", "above_Z", "below_Z"])
        self.assertEqual(r.n_above_z, 2)
        self.assertEqual(r.n_below_z, 1)
        self.assertEqual(r.breaks, [])
        # 课 92 必然关系: 未超越 = 待变盘提示
        self.assertEqual(osc_strength(r), "strong")

    def test_strength_weak_balanced(self):
        """强弱结论: Z 上/下占比"""
        r = oscillation_monitor(C, [U(11, 13), U(11, 13)])
        self.assertEqual(osc_strength(r), "weak")
        r = oscillation_monitor(C, [U(16, 18), U(11, 13)])
        self.assertEqual(osc_strength(r), "balanced")

    def test_break_up(self):
        """Zn 超越 B: break_up + status=breaking(变盘提醒)"""
        r = oscillation_monitor(C, [U(10, 20), U(18, 24)])
        self.assertEqual(r.status, "breaking")
        self.assertEqual(r.breaks, [(1, "break_up")])
        self.assertEqual(r.positions[1], "above_B")

    def test_break_down(self):
        """Zn 超越 A: break_down"""
        r = oscillation_monitor(C, [U(10, 20), U(6, 12)])
        self.assertEqual(r.breaks, [(1, "break_down")])
        self.assertEqual(r.positions[1], "below_A")

    def test_multiple_breaks(self):
        """超越可多次: 逐条记录(最后一次才构成第三类买卖点)"""
        units = [U(18, 24), U(10, 20), U(16, 18), U(6, 12)]
        r = oscillation_monitor(C, units)
        self.assertEqual(r.breaks,
                         [(0, "break_up"), (3, "break_down")])

    def test_upgrade_hint(self):
        """Zn 数达 9: 次级别升级提示"""
        units8 = [U(12, 16)] * 8
        r8 = oscillation_monitor(C, units8)
        self.assertFalse(r8.upgrade_hint)
        r9 = oscillation_monitor(C, units8 + [U(12, 16)])
        self.assertTrue(r9.upgrade_hint)
        self.assertEqual(len(r9.zns), OSC_UPGRADE_N)

    def test_rising_wedge(self):
        """Zn 单调抬升但从未超越 B: 上升楔型诱多(课 92)"""
        units = [U(10.0, 12.0), U(11.0, 13.0), U(12.0, 14.0),
                 U(13.0, 15.0)]
        r = oscillation_monitor(C, units)
        self.assertEqual(r.wedge, "rising_wedge")
        self.assertEqual(r.status, "in_range")

    def test_falling_wedge(self):
        """镜像: Zn 单调下沉但从未低于 A: 下降楔型诱空"""
        units = [U(18.0, 20.0), U(17.0, 19.0), U(16.0, 18.0),
                 U(15.0, 17.0)]
        r = oscillation_monitor(C, units)
        self.assertEqual(r.wedge, "falling_wedge")

    def test_no_wedge_when_break_or_flat(self):
        """有超越不判楔型; Zn 非单调也不判"""
        units = [U(10.0, 12.0), U(11.0, 13.0), U(12.0, 14.0),
                 U(19.0, 22.0)]  # 抬升但末段破 B
        r = oscillation_monitor(C, units)
        self.assertIsNone(r.wedge)
        units2 = [U(12, 14), U(13, 15), U(12, 14), U(13, 15)]  # 锯齿
        r2 = oscillation_monitor(C, units2)
        self.assertIsNone(r2.wedge)

    def test_trend_unit_idx(self):
        """次级别趋势类型(kind=up/down)计入配合; 盘整/无 kind 不计"""
        units = [U(10, 20, kind="up"), U(12, 16, kind="consolidation"),
                 U(14, 18, kind="down"), U(11, 13)]
        r = oscillation_monitor(C, units)
        self.assertEqual(r.trend_unit_idx, [0, 2])

    def test_outer_center_unit_idx(self):
        """末次级别中枢整体在被监视中枢之外: 强变盘征兆(课 92)"""
        units = [
            U(10, 20, centers=[(12.0, 14.0)]),   # 中枢内: 不计
            U(18, 24, centers=[(21.0, 23.0)]),   # 末中枢整体在 B 上
            U(6, 12, centers=[(7.0, 9.0)]),      # 末中枢整体在 A 下
            U(12, 16, centers=[(14.0, 22.0)]),   # 跨 B: 不计
            U(11, 13),                            # 无 centers: 不计
        ]
        r = oscillation_monitor(C, units)
        self.assertEqual(r.outer_center_unit_idx, [1, 2])

    def test_to_dict(self):
        """to_dict 字段完整"""
        r = oscillation_monitor(C, [U(10, 20, kind="up")])
        d = r.to_dict()
        self.assertEqual(d["center"], (10.0, 20.0))
        self.assertEqual(d["z"], 15.0)
        self.assertEqual(d["zns"], [(0, 15.0)])
        self.assertEqual(d["status"], "in_range")
        self.assertEqual(d["trend_unit_idx"], [0])
        self.assertIn("upgrade_hint", d)
        self.assertIn("outer_center_unit_idx", d)


class TestZnNextEstimate(unittest.TestCase):

    def test_none_when_too_few(self):
        """单元不足 2 个: 无法外推"""
        self.assertIsNone(zn_next_estimate([]))
        self.assertIsNone(zn_next_estimate([U(10, 12)]))

    def test_linear_extrapolation(self):
        """Zn 平滑线性抬升: 外推下一 Zn, 区间按平均半振幅对称"""
        units = [U(10.0, 12.0), U(11.0, 13.0), U(12.0, 14.0),
                 U(13.0, 15.0)]  # zn = 11,12,13,14, 半振幅恒 1
        est = zn_next_estimate(units)
        self.assertIsNotNone(est)
        lo, hi = est
        self.assertAlmostEqual(lo, 14.0)   # zn_next 15 - half 1
        self.assertAlmostEqual(hi, 16.0)   # zn_next 15 + half 1

    def test_flat_series(self):
        """Zn 持平: 外推值=当前值"""
        units = [U(12, 16)] * 4
        lo, hi = zn_next_estimate(units)
        self.assertAlmostEqual((lo + hi) / 2.0, 14.0)
        self.assertAlmostEqual(hi - lo, 4.0)   # 平均半振幅 2

    def test_window_m(self):
        """m 截取最近 k 个单元(不足用全部)"""
        units = [U(10, 12), U(11, 13), U(12, 14), U(13, 15), U(14, 16)]
        lo_all, hi_all = zn_next_estimate(units, m=10)
        lo_3, hi_3 = zn_next_estimate(units, m=3)
        self.assertAlmostEqual((lo_all + hi_all) / 2.0, 16.0)
        self.assertAlmostEqual((lo_3 + hi_3) / 2.0, 16.0)


if __name__ == "__main__":
    unittest.main()
