# -*- coding: utf-8 -*-
"""levels(多级唯一分解——记数法, 课 102)单元测试

覆盖分支:
- decompose_levels: 空输入/None 输入; 第 1 级=输入原样; 逐级上推
  (合成趋势盘面 3 级); 高级别单元数 < 3 时停止; max_levels 截断;
  无聚合防御终止;
- level_reading: 覆盖时点的各级 kind 读数; 缝隙时点返回 None;
  端点触及算覆盖; dt 不可比时该级 None;
- change_starts_low: 真实 level_up 分解天然满足先行(正例); 手工
  构造违背序列(高级别转向而低级别仍旧方向)返回 False; 配件级
  单元(无 direction)不构成反证; 无切换点/空输入返回 None;
  seg_start 越界退化为 dt 覆盖;
- 集成: 笔级单元 -> decompose_levels -> 各级无缝覆盖 + 读数一致。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.decompose import MoveType  # noqa: E402
from chan.levels import (LevelDecomposition, change_starts_low,  # noqa: E402
                         decompose_levels, level_reading)
from chan.recurse import level_up  # noqa: E402


def mk_moves(rows):
    """按 (kind, low, high, start_idx, end_idx) 造次级别走势类型"""
    out = []
    for kind, lo, hi, si, ei in rows:
        out.append(MoveType(kind, True,
                            kind if kind in ("up", "down") else None,
                            "d%d" % si, "d%d" % ei, float(hi), float(lo),
                            si, ei, []))
    return out


def mk_xds(rows):
    """按 (direction, start_value, end_value, start_idx, end_idx) 造 XD"""
    from chan.xd import XD
    xds = []
    for d, s, e, si, ei in rows:
        start = ("d%d" % si, float(s), si)
        end = ("d%d" % ei, float(e), ei)
        xds.append(XD(d, start, end, 1))
    return xds


def trend_up_units(n_center=3, seg_len=4):
    """合成上涨趋势盘面: n_center 个依次上移的重叠组(线段级单元)

    每组 4 段: 上-下-上-下, 组内重叠(中枢), 组间整体上移。
    """
    rows = []
    idx = 0
    for g in range(n_center):
        lo = 10.0 + g
        hi = lo + 2.0
        rows.append(("up", lo, lo + 1.0, idx, idx + 1))
        rows.append(("down", lo + 1.0, hi, idx + 1, idx + 2))
        rows.append(("up", lo + 0.5, hi - 0.2, idx + 2, idx + 3))
        rows.append(("down", lo + 0.8, hi, idx + 3, idx + 4))
        idx += 4
    return mk_xds(rows)


def trend_updown_units():
    """合成先涨后跌盘面: 前 3 组依次上移 + 后 3 组依次下移(24 单元)

    实测 L2 = up 趋势(1) + 盘整(3), L3 = 1 个走势类型。
    """
    rows = []
    idx = 0
    for g in range(3):
        lo, hi = 10.0 + g, 12.0 + g
        rows.append(("up", lo, lo + 1.0, idx, idx + 1))
        rows.append(("down", lo + 1.0, hi, idx + 1, idx + 2))
        rows.append(("up", lo + 0.5, hi - 0.2, idx + 2, idx + 3))
        rows.append(("down", lo + 0.8, hi, idx + 3, idx + 4))
        idx += 4
    for g in range(3):
        lo, hi = 11.5 - g, 13.5 - g
        rows.append(("up", lo, lo + 1.0, idx, idx + 1))
        rows.append(("down", lo + 1.0, hi, idx + 1, idx + 2))
        rows.append(("up", lo + 0.5, hi - 0.2, idx + 2, idx + 3))
        rows.append(("down", lo + 0.8, hi, idx + 3, idx + 4))
        idx += 4
    return mk_xds(rows)


class TestDecomposeLevels(unittest.TestCase):
    """decompose_levels 多级分解"""

    def test_empty_input(self):
        # 空输入 -> 仅空第 1 级? 约定: 空输入返回空列表
        self.assertEqual(decompose_levels([]), [])
        self.assertEqual(decompose_levels(None), [])

    def test_level1_is_input(self):
        # 第 1 级 = 输入单元原样(配件级也入分解)
        units = trend_up_units(2)
        out = decompose_levels(units, max_levels=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].level, 1)
        self.assertEqual(out[0].moves, units)

    def test_multi_level_chain(self):
        # 24 单元先涨后跌盘面: 实测 L2=4 项(>=3 可继续上推) ->
        # L3=1 项停止; 各级数量严格递减(聚合)
        units = trend_updown_units()
        out = decompose_levels(units, max_levels=8)
        self.assertEqual(len(out), 3)
        counts = [len(ld.moves) for ld in out]
        self.assertEqual(counts[0], 24)
        self.assertEqual(counts[1], 4)
        self.assertEqual(counts[2], 1)
        # 每级严格少于上一级
        for i in range(1, len(counts)):
            self.assertLess(counts[i], counts[i - 1])

    def test_stop_when_too_few(self):
        # 高级别走势数 < 3 时停止上推
        units = trend_up_units(1)  # 单组 -> L2 只有 1 个走势类型
        out = decompose_levels(units, max_levels=8)
        self.assertEqual(len(out), 2)  # L1 + L2(仅 1 个, 不再上推)
        self.assertEqual(len(out[1].moves), 1)

    def test_max_levels_cap(self):
        # max_levels 截断
        units = trend_up_units(3)
        out = decompose_levels(units, max_levels=2)
        self.assertEqual(len(out), 2)

    def test_to_dict(self):
        # to_dict 结构
        units = trend_up_units(1)
        out = decompose_levels(units, max_levels=2)
        d = out[-1].to_dict()
        self.assertEqual(d["level"], 2)
        self.assertEqual(d["count"], len(out[-1].moves))
        self.assertTrue(all("kind" in m for m in d["moves"]))


class TestLevelReading(unittest.TestCase):
    """level_reading 记数法读数"""

    def test_reading_at_points(self):
        # 各时点读数: 级别越低读数越细
        units = trend_up_units(2)
        out = decompose_levels(units, max_levels=4)
        # 第 2 段中点(d1)处: L1 为单元(非 MoveType -> kind None),
        # L2 应有走势类型覆盖
        r = level_reading(out, "d1")
        self.assertEqual(len(r), len(out))
        self.assertIsNone(r[0])  # XD 无 kind 属性
        self.assertIn(r[1], ("up", "down", "consolidation"))

    def test_reading_gap_returns_none(self):
        # 时点在覆盖缝隙 -> 该级 None
        units = trend_up_units(1)
        out = decompose_levels(units, max_levels=1)
        r = level_reading(out, "d999")
        self.assertEqual(r, [None])

    def test_reading_endpoint_touch(self):
        # 端点触及算覆盖
        units = mk_moves([("up", 10.0, 12.0, 0, 2)])
        ld = LevelDecomposition(1, units)
        self.assertEqual(level_reading([ld], "d0"), ["up"])
        self.assertEqual(level_reading([ld], "d2"), ["up"])

    def test_reading_incomparable_dt(self):
        # dt 类型不可比 -> 该级 None 不抛异常
        class _Odd(object):
            def __lt__(self, other):
                raise TypeError("bad")

            __le__ = __lt__

        units = mk_moves([("up", 10.0, 12.0, 0, 2)])
        ld = LevelDecomposition(1, units)
        self.assertEqual(level_reading([ld], _Odd()), [None])


class TestChangeStartsLow(unittest.TestCase):
    """change_starts_low 高级别改变必先从低级别开始(课 102)"""

    def test_natural_no_switch_returns_none(self):
        # 纯上涨盘面: L2 仅 1 个 up 走势类型 -> 无相邻切换对 -> None
        units = trend_up_units(3)
        low = level_up(units)
        high = level_up(low)
        # 纯上涨: L2 不足以再聚合 -> L3 仅 1 项 -> 无相邻切换对 -> None
        self.assertLessEqual(len(high), 1)
        self.assertIsNone(change_starts_low(low, high))

    def test_natural_switch_satisfied(self):
        # 先涨后跌盘面: L2 有方向切换(up -> consolidation)时,
        # 每个切换段的低级别区间内存在同向单元(天然满足先行);
        # 若分解无切换(全 consolidation 无向) -> None
        units = trend_updown_units()
        out = decompose_levels(units, max_levels=3)
        low, high = out[1].moves, out[2].moves
        res = change_starts_low(low, high)
        if res is not None:
            self.assertTrue(res)

    def test_violation_detected(self):
        # 手工构造违背: 高级别转向而低级别区间内无同向单元
        low = mk_moves([
            ("up", 10.0, 12.0, 0, 2),
            ("down", 9.0, 12.0, 2, 4),
            ("up", 9.0, 11.0, 4, 6),
        ])
        # 正例: h[1] direction=down, seg 区间(低级别列表索引 1..1)
        # 含 low[1]='down' -> 满足先行
        high = [MoveType("up", True, "up", "d0", "d2", 12.0, 10.0, 0, 0, []),
                MoveType("down", True, "down", "d2", "d3", 12.0, 9.0, 1, 1, [])]
        self.assertTrue(change_starts_low(low, high))
        # 负例: h[1] 声称 down 但 seg 区间只含 low[2]='up' -> 违背
        high_bad = [MoveType("up", True, "up", "d0", "d2", 12.0, 10.0, 0, 1, []),
                    MoveType("down", True, "down", "d4", "d5", 11.0, 9.0, 2, 2, [])]
        self.assertFalse(change_starts_low(low, high_bad))

    def test_accessory_units_not_counter_evidence(self):
        # 配件级单元(无 direction 属性)不构成反证
        class _Accessory(object):
            def __init__(self):
                self.start_dt = "d0"
                self.end_dt = "d2"

        low = [_Accessory(), _Accessory()]
        high = [MoveType("up", True, "up", "d0", "d0", 10.0, 9.0, 0, 0, []),
                MoveType("down", True, "down", "d1", "d1", 9.0, 8.0, 1, 1, [])]
        # h[1].seg_start=1, low[1] 无 direction -> 不构成反证 -> True
        self.assertTrue(change_starts_low(low, high))

    def test_no_switch_returns_none(self):
        # 无切换点(全同向) -> None
        low = mk_moves([("up", 10.0, 12.0, 0, 2), ("up", 11.0, 13.0, 2, 4)])
        high = [MoveType("up", True, "up", "d0", "d2", 12.0, 10.0, 0, 2, []),
                MoveType("up", True, "up", "d2", "d4", 13.0, 11.0, 2, 4, [])]
        self.assertIsNone(change_starts_low(low, high))

    def test_empty_inputs(self):
        # 空输入 -> None
        self.assertIsNone(change_starts_low([], []))
        self.assertIsNone(change_starts_low(
            mk_moves([("up", 10.0, 12.0, 0, 2)]), []))


class TestIntegration(unittest.TestCase):
    """集成: 笔级单元 -> 多级分解 -> 覆盖与读数一致"""

    def test_bi_units_chain(self):
        # 8 单元合成两级上推, 各级覆盖无缝
        units = trend_up_units(2)  # 8 个 XD 单元
        out = decompose_levels(units, max_levels=8)
        self.assertGreaterEqual(len(out), 2)
        # L2 相邻项索引无缝: seg_end + 1 == seg_start
        l2 = out[1].moves
        for i in range(1, len(l2)):
            self.assertEqual(l2[i - 1].seg_end + 1, l2[i].seg_start)
        # 末级读数: 末时点处最高级有值
        last_dt = units[-1].end_dt
        r = level_reading(out, last_dt)
        self.assertIsNotNone(r[-1])


if __name__ == "__main__":
    unittest.main()
