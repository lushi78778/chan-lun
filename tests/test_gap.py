# -*- coding: utf-8 -*-
"""chan 包单元测试: gap(缺口识别与力度三分类, 课 77)

运行: python3 -m unittest discover -s tests -p 'test_*.py' -v

每个测试覆盖课 77 原文定义的哪个分支, 见各 docstring。
"""

from __future__ import print_function

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.gap import Gap, find_gaps, classify_gap  # noqa: E402


def mk_bars(rows):
    """rows: list of (dt, high, low) -> 标准 bars(open/close 取高低均值附近)"""
    out = []
    for i, (dt, h, l) in enumerate(rows):
        out.append({"dt": dt, "open": l + (h - l) * 0.3,
                    "high": h, "low": l,
                    "close": l + (h - l) * 0.7,
                    "volume": 1000.0 + i})
    return out


class TestFindGaps(unittest.TestCase):
    """find_gaps: 课 77 缺口定义的各分支"""

    def test_up_gap_sh_original_example(self):
        """向上缺口识别: 复刻课 77 原文例子——1994-07-29 与 1994-08-01
        之间的 [339,377] 缺口(前日最高 339, 次日最低 377, 区间无成交)"""
        bars = mk_bars([
            ("1994-07-28", 341.0, 335.0),
            ("1994-07-29", 339.0, 325.0),   # 前根: 最高 339
            ("1994-08-01", 445.0, 377.0),   # 后根: 最低 377
            ("1994-08-02", 450.0, 400.0),
        ])
        gaps = find_gaps(bars)
        self.assertEqual(len(gaps), 1)
        g = gaps[0]
        self.assertEqual(g.direction, "up")
        self.assertEqual(g.lower, 339.0)   # 缺口下沿 = 前根 high
        self.assertEqual(g.upper, 377.0)   # 缺口上沿 = 后根 low
        self.assertEqual(g.dt_a, "1994-07-29")
        self.assertEqual(g.dt_b, "1994-08-01")
        self.assertEqual((g.index_a, g.index_b), (1, 2))

    def test_down_gap(self):
        """向下缺口识别: 前根最低 > 后根最高, 区间 [后高, 前低] 无成交"""
        bars = mk_bars([
            (1, 12.0, 10.0),   # 前根: 最低 10
            (2, 9.0, 7.0),     # 后根: 最高 9 -> 向下缺口 [9, 10]
            (3, 9.5, 8.0),
        ])
        gaps = find_gaps(bars)
        self.assertEqual(len(gaps), 1)
        g = gaps[0]
        self.assertEqual(g.direction, "down")
        self.assertEqual(g.lower, 9.0)    # 缺口下沿 = 后根 high
        self.assertEqual(g.upper, 10.0)   # 缺口上沿 = 前根 low

    def test_touching_no_gap(self):
        """边界相接不算缺口: 前高 == 后低时该价位在两根 K 线上都有成交,
        不存在"没有成交的区间"(严格不等式分支)"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 12.0, 10.0),   # 前高 10 == 后低 10 -> 无缺口
            (3, 11.0, 9.0),
        ])
        self.assertEqual(find_gaps(bars), [])

    def test_overlap_no_gap(self):
        """区间重叠不算缺口(两根 K 线间无未成交价位)"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 11.0, 9.0),    # [9,11] 与 [8,10] 重叠
            (3, 12.0, 10.0),
        ])
        self.assertEqual(find_gaps(bars), [])

    def test_too_few_bars(self):
        """边界行为: 少于 2 根 K 线返回 [](无"两相邻 K 线")"""
        self.assertEqual(find_gaps([]), [])
        self.assertEqual(find_gaps(mk_bars([(1, 10.0, 8.0)])), [])

    def test_multiple_gaps_in_order(self):
        """序列中多个缺口按时间顺序全部识别(向上+向下混合)"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 13.0, 11.0),   # 向上缺口 [10, 11]
            (3, 12.0, 9.0),
            (4, 8.5, 6.0),     # 向下缺口 [8.5, 9]
            (5, 9.0, 7.0),
        ])
        gaps = find_gaps(bars)
        self.assertEqual([g.direction for g in gaps], ["up", "down"])
        self.assertEqual((gaps[0].lower, gaps[0].upper), (10.0, 11.0))
        self.assertEqual((gaps[1].lower, gaps[1].upper), (8.5, 9.0))
        self.assertEqual([g.index_a for g in gaps], [0, 2])

    def test_gap_to_dict_repr(self):
        """Gap.to_dict / __repr__ 序列化冒烟"""
        g = Gap("up", 10.0, 12.0, "d1", "d2", 0, 1)
        d = g.to_dict()
        self.assertEqual(d["direction"], "up")
        self.assertEqual(d["lower"], 10.0)
        self.assertEqual(d["upper"], 12.0)
        self.assertIn("up", repr(g))
        self.assertIn("10", repr(g))


class TestClassifyGap(unittest.TestCase):
    """classify_gap: 课 77 力度三分类的各分支"""

    def test_unfilled_strong(self):
        """分支一「不回补, 这显然是强势的」: 行情远离缺口再不回头
        (复刻课 77 [339,377] 语境: 「大概也没什么机会回补了」)"""
        bars = mk_bars([
            (1, 339.0, 330.0),
            (2, 445.0, 377.0),    # 向上缺口 [339, 377]
            (3, 500.0, 420.0),    # 一路走高
            (4, 600.0, 510.0),
            (5, 700.0, 620.0),
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "unfilled")
        self.assertEqual(r["strength"], "strong")
        self.assertFalse(r["exhaustion"])
        self.assertIsNone(r["fill_index"])
        self.assertIsNone(r["fill_dt"])
        self.assertIsNone(r["extreme_value"])

    def test_filled_touch_boundary(self):
        """回补判定=区间全覆盖: 后续 K 线恰好触线覆盖 [lower, upper]
        (low == lower 且 high == upper)即完成回补——「该缺口区间最终
        全部再次出现成交」"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 13.0, 12.0),     # 向上缺口 [10, 12]
            (3, 12.0, 10.0),     # [10,12] 恰好整根覆盖缺口区间
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["fill_index"], 2)
        self.assertEqual(r["fill_dt"], 3)

    def test_filled_next_kline_after_gap(self):
        """「这个过程, 可能在下一 K 线就出现」: 缺口后第一根 K 线
        即完成回补(向下缺口场景——向上缺口因后根 low==上沿,
        最早回补只能在再下一根)"""
        bars = mk_bars([
            (1, 13.0, 10.0),     # 前根 low 10
            (2, 9.5, 8.0),       # 后根 high 9.5 -> 向下缺口 [9.5, 10]
            (3, 10.2, 9.0),      # [9,10.2] 覆盖 [9.5,10] -> 下一 K 线回补
        ])
        g = find_gaps(bars)[0]
        self.assertEqual(g.direction, "down")
        r = classify_gap(g, bars)
        self.assertEqual(r["fill_index"], 2)
        self.assertEqual(r["fill_dt"], 3)

    def test_partial_coverage_then_fill(self):
        """多根 K 线接力覆盖: 缺口区间被分段成交, 最后一角补齐时才算
        回补完成(区间覆盖判定, 而非"触及边界即回补")"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 13.0, 12.0),     # 向上缺口 [10, 12]
            (3, 11.0, 10.5),     # 覆盖 [10.5, 11], 剩 (10,10.5) 与 (11,12)
            (4, 10.6, 9.0),      # 覆盖左段 (10, 10.5], 剩 (11, 12)
            (5, 13.0, 10.8),     # 覆盖右段 -> 回补完成
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["fill_index"], 4)
        self.assertEqual(r["fill_dt"], 5)

    def test_leapfrog_unfilled(self):
        """覆盖判定的区分性用例(忠于原文"全部再次出现成交"):
        后续行情以反向缺口跳过缺口区间(区间内部分价位再未成交),
        即使价格已低于缺口下沿, 也不算回补——常见简化口径
        "low <= lower 即回补"在此场景与原文定义相悖, 以覆盖判定为准"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 13.0, 12.0),     # 向上缺口 [10, 12]
            (3, 13.8, 13.5),     # 继续上行(与 2 之间还有向上缺口, 无妨)
            (4, 9.5, 9.0),       # 反向跳空直落 9.5 以下, [10,12] 未成交
            (5, 9.4, 8.8),       # 之后行情彻底走低, 缺口区间再未成交
        ])
        g = find_gaps(bars)[0]   # 第一个缺口 [10, 12]
        self.assertEqual((g.lower, g.upper), (10.0, 12.0))
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "unfilled")
        self.assertEqual(r["strength"], "strong")

    def test_filled_new_extreme_neutral(self):
        """分支二「回补后继续新高或新低, 这是平势的」: 回补完成后
        后续 K 线超过回补前趋势极值 ref(复刻课 77 附录语境
        「补完缺口后创新高, 也就是说周一的缺口依然只是中继性质的」)"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 15.0, 12.0),     # 向上缺口 [10, 12], 之后最高涨到 15
            (3, 14.5, 13.0),
            (4, 14.0, 9.0),      # 回落整根覆盖 [10,12] -> 回补完成
            (5, 15.5, 14.0),     # 此后 high 15.5 > ref 15 -> 继续新高
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "filled_new_extreme")
        self.assertEqual(r["strength"], "neutral")
        self.assertFalse(r["exhaustion"])
        self.assertEqual(r["fill_index"], 3)
        # ref = 缺口形成后至回补完成 K 线(含)的最高 high = 15
        self.assertEqual(r["extreme_value"], 15.0)

    def test_ref_is_trend_extreme_not_gap_boundary(self):
        """参照极值口径: "继续新高"的基准是回补前趋势极值(ref=15),
        不是缺口上沿 12——后续 high 仅超过 12 但未超过 15 不算新高"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 15.0, 12.0),     # 向上缺口 [10, 12], 最高 15
            (3, 14.5, 13.0),
            (4, 14.0, 9.0),      # 回补完成
            (5, 13.5, 12.5),     # high 13.5 > 12 但 < 15 -> 不算新高
            (6, 13.0, 12.0),
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "filled_no_new_extreme")
        self.assertEqual(r["strength"], "weak")

    def test_equal_extreme_not_new_high(self):
        """新高须严格超过 ref: 后续 high == ref(等于)不算继续新高"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 15.0, 12.0),     # 向上缺口 [10, 12], ref 候选 15
            (3, 14.0, 9.0),      # 回补完成
            (4, 15.0, 14.0),     # high 15 == ref 15, 不严格超过
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["strength"], "weak")

    def test_filled_no_new_extreme_weak_exhaustion(self):
        """分支三「回补后不能新高、新低, 因而出现原来走势的转折,
        这是弱势的」——衰竭性缺口特征标注 exhaustion=True"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 15.0, 12.0),     # 向上缺口 [10, 12]
            (3, 14.5, 13.0),
            (4, 14.0, 9.0),      # 回补完成
            (5, 13.0, 11.0),     # 反弹不过 ref=15, 走势转折
            (6, 11.5, 10.0),
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "filled_no_new_extreme")
        self.assertEqual(r["strength"], "weak")
        self.assertTrue(r["exhaustion"])
        self.assertEqual(r["fill_index"], 3)
        self.assertEqual(r["extreme_value"], 15.0)

    def test_down_gap_new_low_neutral(self):
        """向下缺口的镜像分支二: 回补后继续新低(后续 low < ref)为平势"""
        bars = mk_bars([
            (1, 13.0, 10.0),     # 前根 low 10
            (2, 9.5, 8.0),       # 向下缺口 [9.5, 10], 之后最低 8
            (3, 9.0, 8.5),
            (4, 12.5, 9.0),      # 整根覆盖 [9.5,10] -> 回补完成
            (5, 10.0, 7.5),      # low 7.5 < ref 8 -> 继续新低
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "filled_new_extreme")
        self.assertEqual(r["strength"], "neutral")
        self.assertEqual(r["extreme_value"], 8.0)

    def test_down_gap_no_new_low_weak(self):
        """向下缺口的镜像分支三: 回补后不能新低为弱势(衰竭)"""
        bars = mk_bars([
            (1, 13.0, 10.0),
            (2, 9.5, 8.0),       # 向下缺口 [9.5, 10], 最低 8
            (3, 9.0, 8.5),
            (4, 12.5, 9.0),      # 回补完成
            (5, 11.5, 9.5),      # low 9.5 > ref 8, 不再新低 -> 弱势
            (6, 12.0, 10.5),
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "filled_no_new_extreme")
        self.assertEqual(r["strength"], "weak")
        self.assertTrue(r["exhaustion"])

    def test_gap_at_series_end_unfilled(self):
        """边界行为: 缺口是序列最后两根 K 线(无后续 K 线)视为未回补"""
        bars = mk_bars([
            (1, 10.0, 8.0),
            (2, 13.0, 12.0),     # 向上缺口 [10, 12], 序列到此结束
        ])
        g = find_gaps(bars)[0]
        r = classify_gap(g, bars)
        self.assertEqual(r["status"], "unfilled")
        self.assertEqual(r["strength"], "strong")


if __name__ == "__main__":
    unittest.main()
