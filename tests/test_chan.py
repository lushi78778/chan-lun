# -*- coding: utf-8 -*-
"""chan 包单元测试: bars / fx(包含+分型) / bi(笔)

运行: python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

from __future__ import print_function

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.bars import normalize_bars          # noqa: E402
from chan.fx import remove_includes, find_fxs, NewBar  # noqa: E402
from chan.bi import find_bis, chan_fx_bi, BI  # noqa: E402


def mk_bars(rows):
    """rows: list of (dt, high, low) -> 标准 bars(open/close 取高低均值附近)"""
    out = []
    for i, (dt, h, l) in enumerate(rows):
        out.append({"dt": dt, "open": l + (h - l) * 0.3,
                    "high": h, "low": l,
                    "close": l + (h - l) * 0.7,
                    "volume": 1000.0 + i})
    return out


def hl(bars):
    return [(b["high"], b["low"]) for b in bars]


def nhl(new_bars):
    return [(b.high, b.low) for b in new_bars]


class TestNormalizeBars(unittest.TestCase):
    def test_basic(self):
        import pandas as pd
        df = pd.DataFrame({
            "date": ["2026-08-03", "2026-08-04"],
            "open": [10.0, 10.5], "high": [11.0, 11.5],
            "low": [9.5, 10.0], "close": [10.8, 11.2],
            "volume": [100.0, 200.0]})
        bars = normalize_bars(df)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["high"], 11.0)
        self.assertEqual(list(bars[0].keys()),
                         ["dt", "open", "high", "low", "close", "volume"])

    def test_drop_paused(self):
        import pandas as pd
        df = pd.DataFrame({
            "date": ["2026-08-03", "2026-08-04"],
            "open": [10.0, 10.0], "high": [10.0, 10.0],
            "low": [10.0, 10.0], "close": [10.0, 10.0],
            "volume": [0.0, 100.0]})
        bars = normalize_bars(df)
        self.assertEqual(len(bars), 1)

    def test_missing_col(self):
        import pandas as pd
        df = pd.DataFrame({"date": ["2026-08-03"], "open": [10.0]})
        with self.assertRaises(ValueError):
            normalize_bars(df)


class TestRemoveIncludes(unittest.TestCase):
    def test_no_include(self):
        bars = mk_bars([(1, 10, 8), (2, 11, 9), (3, 10.5, 8.5)])
        nb = remove_includes(bars)
        self.assertEqual(nhl(nb), [(10, 8), (11, 9), (10.5, 8.5)])

    def test_down_merge(self):
        # 向下包含: [10,8] 包含 [9.5,8.5] -> [9.5, 8]
        bars = mk_bars([(1, 10, 8), (2, 9.5, 8.5)])
        nb = remove_includes(bars)
        self.assertEqual(nhl(nb), [(9.5, 8)])
        self.assertEqual(nb[0].elements, [0, 1])

    def test_up_merge_sequence(self):
        # b2=[11,9] 包含 b3=[10.5,9](10.5<=11 且 9>=9), 方向向上 -> 合并为 [11,9]
        bars = mk_bars([(1, 10, 8), (2, 11, 9), (3, 10.5, 9)])
        nb = remove_includes(bars)
        self.assertEqual(nhl(nb), [(10, 8), (11, 9)])
        self.assertEqual(nb[1].elements, [1, 2])

    def test_direction_change(self):
        # b2=[9,7] 包含 b3=[8.5,7.2](9>=8.5 且 7<=7.2), 方向向下 -> 合并为 [8.5,7]
        bars = mk_bars([(1, 10, 8), (2, 9, 7), (3, 8.5, 7.2)])
        nb = remove_includes(bars)
        self.assertEqual(nhl(nb), [(10, 8), (8.5, 7)])

    def test_three_way_include(self):
        # 1、2 包含, 2、3 也包含, 但 1、3 不包含(传递律不成立)
        # [10,8] [9.5,8.5] [9.8,8.2]: 1 vs 2: 向下合并 -> [9.5,8]; 与 3: 9.8 含? [9.5,8] vs [9.8,8.2]: 无包含(9.8>9.5 且 8.2>8) -> 追加
        bars = mk_bars([(1, 10, 8), (2, 9.5, 8.5), (3, 9.8, 8.2)])
        nb = remove_includes(bars)
        self.assertEqual(nhl(nb), [(9.5, 8), (9.8, 8.2)])

    def test_single(self):
        bars = mk_bars([(1, 10, 8)])
        nb = remove_includes(bars)
        self.assertEqual(len(nb), 1)
        self.assertEqual(nb[0].elements, [0])


class TestFindFX(unittest.TestCase):
    def test_top_and_bottom(self):
        # 锯齿: 顶分型@2, 底分型@6
        bars = mk_bars([
            (1, 10, 9), (2, 11, 10), (3, 12, 11), (4, 11, 10),
            (5, 10, 9), (6, 9, 8), (7, 8, 7), (8, 9, 8)])
        nb = remove_includes(bars)
        fxs = find_fxs(nb)
        kinds = [f.kind for f in fxs]
        self.assertEqual(kinds, ["top", "bottom"])
        self.assertEqual(fxs[0].high, 12.0)   # 顶
        self.assertEqual(fxs[1].low, 7.0)     # 底
        self.assertEqual(fxs[0].bar_index, 2)
        self.assertEqual(fxs[1].bar_index, 6)

    def test_short_series(self):
        self.assertEqual(find_fxs(remove_includes(mk_bars([(1, 10, 8)]))), [])
        self.assertEqual(find_fxs(remove_includes(mk_bars([(1, 10, 8), (2, 11, 9)]))), [])

    def test_no_fx_monotonic(self):
        bars = mk_bars([(1, 10, 9), (2, 11, 10), (3, 12, 11), (4, 13, 12)])
        self.assertEqual(find_fxs(remove_includes(bars)), [])


class TestFindBI(unittest.TestCase):
    def test_two_bis_sawtooth(self):
        # 顶@2 -> 底@6(间隔3根) -> 顶@10(间隔3根): 两笔
        rows = [(1, 10, 9), (2, 11, 10), (3, 12, 11), (4, 11, 10),
                (5, 10, 9), (6, 9, 8), (7, 8, 7), (8, 9, 8),
                (9, 10, 9), (10, 11, 10), (11, 12, 11), (12, 11, 10)]
        nb, fxs, bis = chan_fx_bi(mk_bars(rows))
        self.assertEqual(len(bis), 2)
        self.assertEqual([b.direction for b in bis], ["down", "up"])
        self.assertEqual(bis[0].start_value, 12.0)
        self.assertEqual(bis[0].end_value, 7.0)
        self.assertEqual(bis[1].start_value, 7.0)
        self.assertEqual(bis[1].end_value, 12.0)

    def test_gap_too_small_no_bi(self):
        # 顶@2 与 底@5 间隔 2 根 -> 不成笔
        rows = [(1, 10, 9), (2, 11, 10), (3, 12, 11), (4, 10, 9),
                (5, 9, 8), (6, 8, 7), (7, 9, 8)]
        nb, fxs, bis = chan_fx_bi(mk_bars(rows))
        # 顶@2、底@5(第7根确认), gap=2 -> 无笔
        self.assertEqual(len(bis), 0)

    def test_same_direction_take_extreme(self):
        # T1@2(12) 后出现更高 T2@4(13), 中间无底分型 -> 笔从 T2 开始
        rows = [(1, 10, 9), (2, 11, 10), (3, 12, 11), (4, 13, 12),
                (5, 12, 11), (6, 11, 10), (7, 10, 9), (8, 9, 8),
                (9, 10, 9)]
        nb, fxs, bis = chan_fx_bi(mk_bars(rows))
        # 分型: T@2, T@4(取极端), 底@7
        self.assertTrue(len(bis) >= 1)
        self.assertEqual(bis[0].direction, "down")
        self.assertEqual(bis[0].start_value, 13.0)

    def test_fx_level_bi_rules(self):
        # 直接构造分型序列验证成笔规则
        from chan.fx import FX
        # T(12) -> D(11): 底在顶上方, 不成笔(顶必须高于底)
        f1 = FX("top", "d2", 12.0, 10.0, 2, [1, 2, 3])
        f2 = FX("bottom", "d4", 11.5, 11.0, 4, [3, 4, 5])
        nb = [NewBar("d1", 0, 10, 9, 0, 0, [0]),
              NewBar("d2", 0, 12, 10, 0, 0, [1]),
              NewBar("d3", 0, 11, 9.5, 0, 0, [2]),
              NewBar("d4", 0, 11.5, 11, 0, 0, [3]),
              NewBar("d5", 0, 11.2, 10.5, 0, 0, [4])]
        bis = find_bis(nb, [f1, f2])
        self.assertEqual(len(bis), 0)  # 顶不高于底 -> 不成笔

    def test_bottom_above_top_no_bi_value(self):
        # 底分型极值 >= 顶分型极值 时不成下跌笔
        from chan.fx import FX
        f1 = FX("top", "d2", 10.0, 8.0, 2, [1, 2, 3])
        f2 = FX("bottom", "d7", 12.0, 10.5, 7, [6, 7, 8])
        nb = [NewBar("d%d" % i, 0, 10 + i * 0.1, 9 + i * 0.1, 0, 0, [i])
              for i in range(10)]
        bis = find_bis(nb, [f1, f2])
        self.assertEqual(len(bis), 0)

    def test_higher_top_extends_last_bi(self):
        """回归: 顶分型后未出有效底分型而继续新高(碎步上涨),
        上一笔终点应随更高顶分型延伸(真实数据 000001 2023-07 场景)"""
        from chan.fx import FX
        # 底@2 -> 顶@6 成 up 笔; 顶@9(更高, 中间无有效底分型) -> 笔终点延伸至@9;
        # 底@12 -> 从新顶成 down 笔
        fxs = [
            FX("bottom", "d2", 9.8, 9.4, 2, [1, 2, 3]),
            FX("top", "d6", 10.2, 9.68, 6, [5, 6, 7]),
            FX("top", "d9", 10.5, 9.7, 9, [8, 9, 10]),   # 更高顶
            FX("bottom", "d13", 10.2, 9.8, 13, [12, 13, 14]),
        ]
        nb = [NewBar("d%d" % i, 0, 10.0, 9.0, 0, 0, [i]) for i in range(16)]
        bis = find_bis(nb, fxs)
        self.assertEqual(len(bis), 2)
        # 第一笔: up, 终点应延伸到更高顶 @9(10.5), 而非 @6(10.2)
        self.assertEqual(bis[0].direction, "up")
        self.assertEqual(bis[0].end_value, 10.5)
        self.assertEqual(bis[0].end_index, 9)
        # 第二笔: down 从 10.5 到 9.8
        self.assertEqual(bis[1].direction, "down")
        self.assertEqual(bis[1].start_value, 10.5)
        self.assertEqual(bis[1].end_value, 9.8)

    def test_lower_bottom_extends_last_bi(self):
        """回归: 底分型后未出有效顶分型而继续新低, 上一笔终点随更低底延伸"""
        from chan.fx import FX
        fxs = [
            FX("top", "d2", 11.0, 10.4, 2, [1, 2, 3]),
            FX("bottom", "d6", 10.6, 10.0, 6, [5, 6, 7]),
            FX("bottom", "d10", 10.5, 9.5, 10, [9, 10, 11]),  # 更低底
        ]
        nb = [NewBar("d%d" % i, 0, 10.0, 9.0, 0, 0, [i]) for i in range(12)]
        bis = find_bis(nb, fxs)
        self.assertEqual(len(bis), 1)
        self.assertEqual(bis[0].direction, "down")
        self.assertEqual(bis[0].end_value, 9.5)   # 终点延伸到更低底
        self.assertEqual(bis[0].end_index, 10)


class TestFindXD(unittest.TestCase):
    """线段识别(特征序列)"""

    @staticmethod
    def mk_bis(rows):
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        for d, s, e, si, ei in rows:
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si,
                      max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei,
                      max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        return bis

    def test_case1_no_gap(self):
        """第一种情况(无缺口): up 线段结束于特征序列顶分型高点"""
        from chan.xd import find_xds
        rows = [
            ("up", 0, 10, 0, 4),
            ("down", 10, 6, 4, 8),
            ("up", 6, 12, 8, 12),
            ("down", 12, 7, 12, 16),
            ("up", 7, 11, 16, 20),
            ("down", 11, 5, 20, 24),
        ]
        xds = find_xds(self.mk_bis(rows))
        self.assertEqual(xds[0].direction, "up")
        self.assertEqual(xds[0].start_value, 0)
        self.assertEqual(xds[0].end_value, 12)
        self.assertEqual(xds[0].mode, 1)

    def test_case2_gap_confirm(self):
        """第二种情况(有缺口): 待第二特征序列底分型确认后结束"""
        from chan.xd import find_xds
        rows = [
            ("up", 0, 10, 0, 4),
            ("down", 10, 8, 4, 8),
            ("up", 8, 13, 8, 12),
            ("down", 13, 11, 12, 16),   # X2: 缺口(X1.high=10 < X2.low=11)
            ("up", 11, 12.5, 16, 20),
            ("down", 12.5, 9.5, 20, 24),  # X3 -> 顶分型, 有缺口 -> pending=13
            ("up", 9.5, 12.5, 24, 28),    # S1
            ("down", 12.5, 9.2, 28, 32),
            ("up", 9.2, 11.5, 32, 36),    # S2(弱反弹)
            ("down", 11.5, 9.6, 36, 40),
            ("up", 9.6, 13, 40, 44),       # S3 -> 第二特征序列底分型 -> 确认
        ]
        xds = find_xds(self.mk_bis(rows))
        self.assertEqual(xds[0].direction, "up")
        self.assertEqual(xds[0].start_value, 0)
        self.assertEqual(xds[0].end_value, 13)
        self.assertEqual(xds[0].mode, 2)

    def test_less_than_3_bis(self):
        from chan.xd import find_xds
        rows = [("up", 0, 10, 0, 4)]
        xds = find_xds(self.mk_bis(rows))
        self.assertEqual(len(xds), 1)
        self.assertEqual(xds[0].end_value, 10)

    def test_down_case1(self):
        """向下线段第一种情况"""
        from chan.xd import find_xds
        rows = [
            ("down", 10, 2, 0, 4),
            ("up", 2, 6, 4, 8),
            ("down", 6, 1, 8, 12),
            ("up", 1, 5, 12, 16),
            ("down", 5, 3, 16, 20),
            ("up", 3, 7, 20, 24),
        ]
        xds = find_xds(self.mk_bis(rows))
        self.assertEqual(xds[0].direction, "down")
        self.assertEqual(xds[0].start_value, 10)
        self.assertEqual(xds[0].end_value, 1)
        self.assertEqual(xds[0].mode, 1)


class TestFindZS(unittest.TestCase):
    """中枢识别"""

    @staticmethod
    def mk_xds(rows):
        from chan.xd import XD
        xds = []
        for d, s, e, si, ei in rows:
            start = ("d%d" % si, float(s), si)
            end = ("d%d" % ei, float(e), ei)
            xds.append(XD(d, start, end, 1))
        return xds

    def test_basic_zs_with_extend(self):
        from chan.zs import find_zs
        rows = [
            ("up", 0, 10, 0, 4),
            ("down", 10, 4, 4, 8),
            ("up", 4, 9, 8, 12),
            ("down", 9, 3, 12, 16),
            ("up", 3, 8, 16, 20),
            ("down", 8, 2, 20, 24),
            ("up", 2, 7, 24, 28),
            ("down", 7, 2.5, 28, 32),
            ("up", 2.5, 8, 32, 36),
            ("down", 8, 3, 36, 40),
            ("up", 3, 9.5, 40, 44),
            ("down", 9.5, 1.5, 44, 48),
            ("up", 1.5, 12, 48, 52),
            ("down", 12, 11, 52, 56),
        ]
        zss = find_zs(self.mk_xds(rows))
        self.assertEqual(len(zss), 1)
        zs = zss[0]
        self.assertEqual(zs.zd, 4.0)
        self.assertEqual(zs.zg, 9.0)
        self.assertEqual(zs.gg, 12.0)   # up 1.5->12 延伸后 gg 更新
        self.assertEqual(zs.dd, 0.0)
        self.assertTrue(zs.extended_9)   # 12 段延伸

    def test_no_overlap_no_zs(self):
        from chan.zs import find_zs
        rows = [
            ("up", 0, 10, 0, 4),
            ("down", 10, 5, 4, 8),
            ("up", 11, 20, 8, 12),   # 第三线段整体在中枢候选之上 -> 无重叠
            ("down", 20, 12, 12, 16),
            ("up", 12, 18, 16, 20),
        ]
        zss = find_zs(self.mk_xds(rows))
        # 滑动窗口: (0,1,2) 无重叠; (1,2,3): zd=max(5,11,12)=12, zg=min(10,20,20)=10 -> 12>10 无
        # (2,3,4): zd=max(11,12,12)=12, zg=min(20,20,18)=18 -> 12<18 有中枢
        self.assertEqual(len(zss), 1)
        self.assertEqual(zss[0].zd, 12.0)
        self.assertEqual(zss[0].zg, 18.0)

    def test_two_zs_newborn(self):
        from chan.zs import find_zs
        rows = [
            ("up", 0, 10, 0, 4),
            ("down", 10, 4, 4, 8),
            ("up", 4, 9, 8, 12),     # zs1: [4,9]
            ("down", 9, 5, 12, 16),  # 延伸 zs1
            ("up", 5, 15, 16, 20),   # 向上离开(15>9)
            ("down", 15, 12, 20, 24),  # 回抽不重叠(12>9) -> zs1 结束
            ("up", 12, 14, 24, 28),  # zs2: [12,14]
            ("down", 14, 12.5, 28, 32),
            ("up", 12.5, 14.5, 32, 36),
        ]
        zss = find_zs(self.mk_xds(rows))
        self.assertEqual(len(zss), 2)
        self.assertEqual([z.zd for z in zss], [4.0, 12.5])
        self.assertEqual([z.zg for z in zss], [9.0, 14.0])

    def test_trend_classify(self):
        from chan.zs import find_zs, classify_trend
        rows = [
            ("up", 0, 10, 0, 4), ("down", 10, 4, 4, 8), ("up", 4, 9, 8, 12),
            ("down", 9, 5, 12, 16), ("up", 5, 15, 16, 20), ("down", 15, 12, 20, 24),
            ("up", 12, 14, 24, 28), ("down", 14, 12.5, 28, 32),
            ("up", 12.5, 14.5, 32, 36), ("down", 14.5, 13, 36, 40),
            ("up", 13, 20, 40, 44), ("down", 20, 17, 44, 48),
            ("up", 17, 19, 48, 52), ("down", 19, 18, 52, 56),
        ]
        zss = find_zs(self.mk_xds(rows))
        trend = classify_trend(zss)
        self.assertTrue(len(zss) >= 2)
        self.assertTrue(len(trend) >= 1)


def make_bars_from_values(vals):
    """用收盘价序列构造 bars(简单 OHLC)"""
    import datetime
    bars = []
    base = datetime.datetime(2024, 1, 1)
    for i, v in enumerate(vals):
        dt = base + datetime.timedelta(days=i)
        bars.append({"dt": dt, "open": v * 0.99, "high": v * 1.01,
                     "low": v * 0.98, "close": v, "volume": 1000.0})
    return bars


class TestMacd(unittest.TestCase):
    def test_macd_shape(self):
        from chan.bc import macd_series
        bars = make_bars_from_values([10.0 + i * 0.1 for i in range(50)])
        dif, dea, hist = macd_series(bars)
        self.assertEqual(len(dif), 50)
        self.assertEqual(len(hist), 50)
        # 单边上涨: DIF 应为正
        self.assertGreater(dif[-1], 0)

    def test_segment_area_sign(self):
        from chan.bc import macd_series, segment_area, _dt_index
        vals = [10.0 + i * 0.1 for i in range(20)] + [12.0 - i * 0.1 for i in range(20)]
        bars = make_bars_from_values(vals)
        _, _, hist = macd_series(bars)
        dt_map = _dt_index(bars)
        a_up = segment_area(hist, bars, dt_map, bars[0]["dt"], bars[19]["dt"])
        a_dn = segment_area(hist, bars, dt_map, bars[20]["dt"], bars[39]["dt"])
        self.assertGreater(a_up, 0)   # 上涨段红柱主导
        self.assertLess(a_dn, 0)      # 下跌段绿柱主导


class TestBacklash(unittest.TestCase):
    def test_pan_bc_top(self):
        """盘整顶背驰: 中枢内两段向上, 后段创新高但面积更小"""
        from chan.bc import find_pan_bc
        from chan.fx import FX
        from chan.bi import BI
        # 构造笔: up1 -> down1 -> up2(更高但弱)
        bis = []
        def mk_bi(d, s, e, si, ei, dt_s, dt_e):
            fx_a = FX("bottom" if d == "up" else "top", dt_s, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", dt_e, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        # bars: 构造对应 MACD(前段斜率大, 后段斜率小)
        vals = []
        for i in range(5):
            vals.append(10 + i * 1.0)     # 10->14 快
        for i in range(5):
            vals.append(15 - i * 0.6)     # 15->12.6
        for i in range(5):
            vals.append(12 + i * 0.8)     # 12->15.2 慢
        bars = make_bars_from_values(vals)
        mk_bi("up", 10, 15, 0, 4, bars[0]["dt"], bars[4]["dt"])     # 段A: 快速强涨
        mk_bi("down", 15, 12, 4, 8, bars[4]["dt"], bars[8]["dt"])
        mk_bi("up", 12, 16, 8, 12, bars[8]["dt"], bars[12]["dt"])  # 段B: 缓涨创新高
        # 构造单中枢
        zs = type("ZS", (), {"zd": 12.0, "zg": 15.0, "dd": 10.0, "gg": 15.0,
                             "start_dt": bars[0]["dt"], "end_dt": bars[14]["dt"]})()
        res = find_pan_bc(bis, [zs], bars)
        # 段B(up) 创新高(16>15) 且面积更小 -> 盘整顶背驰
        self.assertTrue(any(r["direction"] == "up" for r in res), res)


class TestBuySellPoints(unittest.TestCase):
    def test_buy3(self):
        """三买: 向上突破 ZG 后回抽不破 ZG"""
        from chan.bs import find_buy_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        # 中枢 [10, 12]: 震荡后向上突破 13, 回抽到 12.2(不破 12)
        mk_bi("up", 10, 12, 0, 4)
        mk_bi("down", 12, 10.5, 4, 8)
        mk_bi("up", 10.5, 13, 8, 12)   # 突破
        mk_bi("down", 13, 12.2, 12, 16)  # 回抽不破 ZG
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 10.0, "gg": 13.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        res = find_buy_points(bis, [zs])
        types = [r["type"] for r in res]
        self.assertIn(3, types)
        r3 = [r for r in res if r["type"] == 3][0]
        self.assertAlmostEqual(r3["price"], 12.2)

    def test_sell3(self):
        from chan.bs import find_sell_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        mk_bi("down", 12, 10, 0, 4)
        mk_bi("up", 10, 11.5, 4, 8)
        mk_bi("down", 11.5, 9, 8, 12)   # 向下离开
        mk_bi("up", 9, 9.8, 12, 16)     # 回抽不升破 ZD=10
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 9.0, "gg": 12.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        res = find_sell_points(bis, [zs])
        types = [r["type"] for r in res]
        self.assertIn(3, types)

    def test_buy2_carries_b1_price(self):
        """二买事件携带一买低点 b1_price(供 30m 轻量确认)"""
        from chan.bs import find_buy_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        mk_bi("down", 12, 9, 0, 4)        # 一买笔: 终点 d4, 低点 9.0
        mk_bi("up", 9, 10.5, 4, 8)
        mk_bi("down", 10.5, 9.8, 8, 12)   # 二买: 回调不破 9.0
        trend_bc = [{"direction": "down", "dt": "d4", "price": 9.0,
                     "zs_idx": 0, "note": "底背驰"}]
        zs = type("ZS", (), {"zd": 8.5, "zg": 11.0, "dd": 8.5, "gg": 11.0,
                             "start_dt": "d0", "end_dt": "d12"})()
        res = find_buy_points(bis, [zs], trend_bc)
        r2 = [r for r in res if r["type"] == 2]
        self.assertEqual(len(r2), 1, res)
        self.assertAlmostEqual(r2[0]["b1_price"], 9.0)
        self.assertAlmostEqual(r2[0]["price"], 9.8)

    def test_sell2_carries_s1_price(self):
        """二卖事件携带一卖高点 s1_price(镜像)"""
        from chan.bs import find_sell_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        mk_bi("up", 9, 12, 0, 4)          # 一卖笔: 终点 d4, 高点 12.0
        mk_bi("down", 12, 11, 4, 8)
        mk_bi("up", 11, 11.5, 8, 12)      # 二卖: 反弹不破 12.0
        trend_bc = [{"direction": "up", "dt": "d4", "price": 12.0,
                     "zs_idx": 0, "note": "顶背驰"}]
        zs = type("ZS", (), {"zd": 8.5, "zg": 11.0, "dd": 8.5, "gg": 11.0,
                             "start_dt": "d0", "end_dt": "d12"})()
        res = find_sell_points(bis, [zs], trend_bc)
        r2 = [r for r in res if r["type"] == 2]
        self.assertEqual(len(r2), 1, res)
        self.assertAlmostEqual(r2[0]["s1_price"], 12.0)

    def test_buy3_min_power_ratio(self):
        """三买力度过滤参数化: None=默认(>1.0), 数值=比值下限"""
        from chan.bs import find_buy_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []
        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si, max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei, max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))
        mk_bi("up", 10, 12, 0, 4)
        mk_bi("down", 12, 10.5, 4, 8)
        mk_bi("up", 10.5, 13, 8, 12)      # 离开 +23.8%
        mk_bi("down", 13, 12.2, 12, 16)   # 回抽 -6.2% -> 比值 ≈3.87
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 10.0, "gg": 13.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        # 默认(None): 比值 3.87 > 1.0 -> 出信号
        res = find_buy_points(bis, [zs])
        self.assertEqual(len([r for r in res if r["type"] == 3]), 1)
        # 门槛 4.0: 3.87 < 4.0 -> 过滤
        res = find_buy_points(bis, [zs], min_power_ratio=4.0)
        self.assertEqual(len([r for r in res if r["type"] == 3]), 0)
        # 门槛 3.5: 3.87 >= 3.5 -> 出信号
        res = find_buy_points(bis, [zs], min_power_ratio=3.5)
        self.assertEqual(len([r for r in res if r["type"] == 3]), 1)


class TestMinKGapParam(unittest.TestCase):
    def test_min_k_gap_param(self):
        """min_k_gap 参数化: 默认 3 不成笔的间隔 2, 放宽到 2 成笔"""
        from chan.fx import FX
        fxs = [
            FX("top", "d2", 11.0, 9.0, 2, [1, 2, 3]),
            FX("bottom", "d5", 9.5, 8.0, 5, [4, 5, 6]),
        ]
        nb = [NewBar("d%d" % i, 0, 10.0, 9.0, 0, 0, [i]) for i in range(8)]
        # 间隔 2 根独立K线: 默认 MIN_K_GAP=3 -> 不成笔
        self.assertEqual(len(find_bis(nb, fxs)), 0)
        # 放宽到 2 -> 成一笔(down: 11.0 -> 8.0)
        bis = find_bis(nb, fxs, min_k_gap=2)
        self.assertEqual(len(bis), 1)
        self.assertEqual(bis[0].direction, "down")
        self.assertEqual(bis[0].start_value, 11.0)
        self.assertEqual(bis[0].end_value, 8.0)


class TestClassifyTrendDetail(unittest.TestCase):
    def test_zs_list_detail(self):
        """classify_trend: 新增 zs_list 含组内全部中枢明细, 旧字段保留"""
        from chan.zs import ZS, classify_trend
        zs1 = ZS(10.0, 12.0, 12.5, 9.5, "d1", "d5", "up", 3)
        zs2 = ZS(13.0, 15.0, 15.5, 12.5, "d7", "d11", "up", 3)   # 与 zs1 不重叠
        zs3 = ZS(12.5, 14.0, 14.3, 12.2, "d13", "d16", "up", 3)  # 与 zs2 重叠
        res = classify_trend([zs1, zs2, zs3])
        self.assertEqual(len(res), 2)
        # 第一组: zs1+zs2 不重叠 -> 趋势
        self.assertEqual(res[0]["type"], "趋势")
        self.assertEqual(res[0]["zs_count"], 2)
        self.assertEqual(len(res[0]["zs_list"]), 2)
        self.assertEqual(res[0]["zs_list"][0]["zd"], 10.0)
        self.assertEqual(res[0]["zs_list"][1]["zd"], 13.0)
        self.assertEqual(res[0]["zs_list"][1]["zg"], 15.0)
        self.assertIn("gg", res[0]["zs_list"][0])
        self.assertIn("extended_9", res[0]["zs_list"][0])
        # 旧字段(组内首个中枢边界)保留
        self.assertEqual(res[0]["zd"], 10.0)
        self.assertEqual(res[0]["zg"], 12.0)
        # 第二组: zs3 与 zs2 区间重叠 -> 新组(盘整)
        self.assertEqual(res[1]["type"], "盘整")
        self.assertEqual(len(res[1]["zs_list"]), 1)


class TestPackageExports(unittest.TestCase):
    def test_top_level_api(self):
        """chan 顶层导出全部公开 API, from chan import xxx 可用"""
        import chan
        for name in chan.__all__:
            self.assertTrue(hasattr(chan, name), "缺少导出: %s" % name)
        from chan import (find_zs, normalize_bars, confirm_buy2_30m,
                          find_buy_points, classify_trend)
        self.assertTrue(callable(find_zs))
        self.assertTrue(callable(normalize_bars))
        self.assertTrue(callable(confirm_buy2_30m))
        self.assertTrue(callable(find_buy_points))
        self.assertTrue(callable(classify_trend))

    def test_version_exported(self):
        import chan
        self.assertIn("__version__", chan.__all__)
        self.assertTrue(len(chan.__version__) >= 5)
        self.assertEqual(chan.__version__.count("."), 2)


class TestRobustness(unittest.TestCase):
    def test_ema_empty(self):
        """空序列: ema/macd_series 返回空数组, 不抛异常"""
        from chan.bc import ema, macd_series
        out = ema([], 12)
        self.assertEqual(len(out), 0)
        dif, dea, hist = macd_series([])
        self.assertEqual(len(dif), 0)
        self.assertEqual(len(dea), 0)
        self.assertEqual(len(hist), 0)

    def test_trend_bc_empty_bis(self):
        """无笔/无中枢: find_trend_bc/find_pan_bc 返回 [], 不抛异常"""
        from chan.bc import find_trend_bc, find_pan_bc
        self.assertEqual(find_trend_bc([], [], []), [])
        self.assertEqual(find_pan_bc([], [], []), [])
        # 有中枢但无笔: 返回 []
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 9.0, "gg": 13.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        self.assertEqual(find_trend_bc([], [zs], []), [])


class TestClassifyTrendDirection(unittest.TestCase):
    def test_direction_consistency(self):
        """方向不一致的中枢即使区间不重叠, 也不并入同一趋势"""
        from chan.zs import ZS, classify_trend
        zs1 = ZS(10.0, 12.0, 12.5, 9.5, "d1", "d5", "up", 3)
        zs2 = ZS(13.0, 15.0, 15.5, 12.5, "d7", "d11", "down", 3)  # 反向
        res = classify_trend([zs1, zs2])
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["type"], "盘整")
        self.assertEqual(res[1]["type"], "盘整")
        # 同向不重叠 -> 仍合并为趋势(回归)
        zs2_up = ZS(13.0, 15.0, 15.5, 12.5, "d7", "d11", "up", 3)
        res2 = classify_trend([zs1, zs2_up])
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["type"], "趋势")


if __name__ == "__main__":
    unittest.main(verbosity=2)
