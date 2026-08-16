# -*- coding: utf-8 -*-
"""cross30 跨级别确认单元测试 + bs.py v3 字段

运行: python3 -m unittest tests.test_cross30 -v
"""

from __future__ import print_function

import os
import sys
import datetime
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.cross30 import (confirm_buy3_30m, confirm_sell3_30m,  # noqa: E402
                          confirm_buy2_30m, confirm_buy3_event_30m,
                          confirm_sell3_event_30m)


def make_run_bars(runs, base_dt=None, step_min=30, end_bar_date=None):
    """用 run 序列构造 bars: runs = [(direction, start_close, end_close, n), ...]

    direction: 'up'/'down'; n >= 4(形成笔需要足够的独立K线)。
    OHLC 简式: open=v*0.99, high=v*1.01, low=v*0.98, close=v。
    """
    if base_dt is None:
        base_dt = datetime.datetime(2026, 8, 11, 9, 30)
    bars = []
    dt = base_dt
    for direction, s, e, n in runs:
        for i in range(n):
            t = (i + 1.0) / n
            v = s + (e - s) * t
            bars.append({"dt": dt, "open": v * 0.99, "high": v * 1.01,
                         "low": v * 0.98, "close": v, "volume": 1000.0})
            dt = dt + datetime.timedelta(minutes=step_min)
    return bars


def mk_buy3_bars(b_end, a_end=12.0, b_start=13.0, trail=4):
    """三买确认标准结构(8根/段, 与真实30m粒度接近):
    up 10->15, down A 15->a_end(强跌), up ->b_start, down B b_start->b_end(缓跌创新低), 尾部小反弹
    """
    runs = [
        ("up", 10.0, 15.0, 8),
        ("down", 15.0, a_end, 8),
        ("up", a_end, b_start, 8),
        ("down", b_start, b_end, 8),
        ("up", b_end, b_end + 0.3, trail),
    ]
    return make_run_bars(runs)


class TestBsV3Fields(unittest.TestCase):
    def test_buy3_extra_fields(self):
        """三买事件附带中枢上下沿与回抽笔端点"""
        from chan.bs import find_buy_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []

        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si,
                      max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei,
                      max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))

        mk_bi("up", 10, 12, 0, 4)
        mk_bi("down", 12, 10.5, 4, 8)
        mk_bi("up", 10.5, 13, 8, 12)
        mk_bi("down", 13, 12.2, 12, 16)
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 10.0, "gg": 13.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        res = find_buy_points(bis, [zs])
        r3 = [r for r in res if r["type"] == 3][0]
        self.assertAlmostEqual(r3["zs_zd"], 10.0)
        self.assertAlmostEqual(r3["zs_zg"], 12.0)
        self.assertEqual(r3["pull_start_dt"], "d12")
        self.assertEqual(r3["pull_end_dt"], "d16")
        self.assertAlmostEqual(r3["pull_start"], 13.0)
        self.assertAlmostEqual(r3["pull_end"], 12.2)

    def test_sell3_extra_fields(self):
        from chan.bs import find_sell_points
        from chan.fx import FX
        from chan.bi import BI
        bis = []

        def mk_bi(d, s, e, si, ei):
            fx_a = FX("bottom" if d == "up" else "top", "d%d" % si,
                      max(s, e), min(s, e), si, [si])
            fx_b = FX("top" if d == "up" else "bottom", "d%d" % ei,
                      max(s, e), min(s, e), ei, [ei])
            bis.append(BI(d, fx_a, fx_b, si, ei))

        mk_bi("down", 12, 10, 0, 4)
        mk_bi("up", 10, 11.5, 4, 8)
        mk_bi("down", 11.5, 9, 8, 12)
        mk_bi("up", 9, 9.8, 12, 16)
        zs = type("ZS", (), {"zd": 10.0, "zg": 12.0, "dd": 9.0, "gg": 12.0,
                             "start_dt": "d0", "end_dt": "d16"})()
        res = find_sell_points(bis, [zs])
        r3 = [r for r in res if r["type"] == 3][0]
        self.assertAlmostEqual(r3["zs_zd"], 10.0)
        self.assertAlmostEqual(r3["zs_zg"], 12.0)
        self.assertEqual(r3["pull_start_dt"], "d12")
        self.assertEqual(r3["pull_end_dt"], "d16")


class TestBuy3Confirm30m(unittest.TestCase):
    def test_confirmed(self):
        """30m 底背驰 + 低点不破 ZG -> confirmed"""
        bars = mk_buy3_bars(b_end=11.6)   # 低点≈11.37 ≥ ZG=11.2
        sig_dt = bars[-1]["dt"]
        r = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        self.assertEqual(r["status"], "confirmed", r)
        self.assertGreater(r["dist_zg"], 0)
        self.assertLess(r["swing_ratio"], 1.0)

    def test_weak(self):
        """30m 底背驰 + 低点轻微刺破 ZG -> weak"""
        bars = mk_buy3_bars(b_end=11.3)   # 低点≈11.07 < ZG=11.2 但 ≥ 10.976
        sig_dt = bars[-1]["dt"]
        r = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        self.assertEqual(r["status"], "weak", r)
        self.assertLess(r["dist_zg"], 0)

    def test_broke(self):
        """30m 低点跌破 ZG 超 2% -> broke"""
        bars = mk_buy3_bars(b_end=10.9)   # 低点≈10.68 < 10.976
        sig_dt = bars[-1]["dt"]
        r = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        self.assertEqual(r["status"], "broke", r)

    def test_no_exhaustion(self):
        """末段下跌力度更大(无背驰)且不破 ZG -> no_exhaustion"""
        bars = mk_buy3_bars(b_end=11.0, a_end=13.5, b_start=14.0)
        # A: 15->13.5 温和; B: 14.0->11.0 更陡 -> 末段力度更大
        sig_dt = bars[-1]["dt"]
        r = confirm_buy3_30m(bars, 9.8, 10.5, sig_dt)
        self.assertEqual(r["status"], "no_exhaustion", r)

    def test_stale(self):
        """回抽段终点早于信号日超 1 天 -> stale"""
        bars = mk_buy3_bars(b_end=11.6)
        sig_dt = bars[-1]["dt"] + datetime.timedelta(days=3)
        r = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        self.assertEqual(r["status"], "stale", r)

    def test_run_end_one_day_before_signal(self):
        """回抽段终点比信号日早 1 天: 不是 stale, 正常确认"""
        bars = mk_buy3_bars(b_end=11.6)
        sig_dt = bars[-1]["dt"] + datetime.timedelta(days=1)
        r = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        self.assertNotEqual(r["status"], "stale", r)

    def test_no_data(self):
        r = confirm_buy3_30m([], 9.8, 10.5, "2026-08-13")
        self.assertEqual(r["status"], "no_data")

    def test_min_prev_swing_floor(self):
        """前段是微型波动(摆动不足价格0.7%): 无法比较力度 -> no_exhaustion"""
        runs = [
            ("up", 10.0, 15.0, 8),
            ("down", 15.0, 14.98, 4),   # 微型下跌段(对照段, 几乎走平)
            ("up", 14.98, 15.2, 5),
            ("down", 15.2, 13.5, 8),    # 末段: 大跌创新低
            ("up", 13.5, 13.8, 4),
        ]
        bars = make_run_bars(runs)
        sig_dt = bars[-1]["dt"]
        # 该合成微段实测摆动≈0.094(≈价格0.65%), 用 0.7% 门槛触发
        r = confirm_buy3_30m(bars, 9.8, 10.5, sig_dt,
                             min_prev_swing_ratio=0.007)
        self.assertEqual(r["status"], "no_exhaustion", r)
        self.assertIn("无法比较", r["note"])
        self.assertIsNone(r["swing_ratio"])
        # 不加门槛时: 末段力度更大 -> 无背驰(逻辑本身不变)
        r2 = confirm_buy3_30m(bars, 9.8, 10.5, sig_dt)
        self.assertEqual(r2["status"], "no_exhaustion", r2)
        self.assertIsNotNone(r2["swing_ratio"])

    def test_few_bis(self):
        """30m 笔不足 -> no_data"""
        bars = make_run_bars([("up", 10.0, 11.0, 8)])
        r = confirm_buy3_30m(bars, 9.0, 10.0, bars[-1]["dt"])
        self.assertEqual(r["status"], "no_data", r)


class TestSell3Confirm30m(unittest.TestCase):
    def mk_sell3_bars(self, b_end=12.8, trail=4):
        runs = [
            ("down", 12.0, 9.0, 8),
            ("up", 9.0, 12.6, 8),     # U A: 强涨
            ("down", 12.6, 11.0, 8),
            ("up", 11.0, b_end, 8),   # U B: 缓涨(顶背驰)
            ("down", b_end, b_end - 0.3, trail),
        ]
        return make_run_bars(runs)

    def test_confirmed(self):
        """30m 顶背驰 + 高点不升破 ZD -> confirmed"""
        bars = self.mk_sell3_bars(b_end=12.8)   # 高点≈12.93 ≤ ZD=13.2
        sig_dt = bars[-1]["dt"]
        r = confirm_sell3_30m(bars, 13.2, 14.0, sig_dt)
        self.assertEqual(r["status"], "confirmed", r)
        self.assertLess(r["dist_zd"], 0)
        self.assertLess(r["swing_ratio"], 1.0)

    def test_broke(self):
        """30m 高点升破 ZD 超 2% -> broke"""
        bars = self.mk_sell3_bars(b_end=12.8)
        sig_dt = bars[-1]["dt"]
        r = confirm_sell3_30m(bars, 12.5, 13.5, sig_dt)   # 高点 12.93 > 12.75
        self.assertEqual(r["status"], "broke", r)

    def test_no_exhaustion(self):
        """末段上涨力度更大 -> no_exhaustion"""
        runs = [
            ("down", 12.0, 9.0, 8),
            ("up", 9.0, 11.0, 8),     # U A: 温和 +2.0
            ("down", 11.0, 9.5, 8),
            ("up", 9.5, 12.0, 8),     # U B: 更陡 +2.5, 创新高
            ("down", 12.0, 11.7, 4),
        ]
        bars = make_run_bars(runs)
        sig_dt = bars[-1]["dt"]
        r = confirm_sell3_30m(bars, 12.5, 13.5, sig_dt)
        self.assertEqual(r["status"], "no_exhaustion", r)

    def test_weak(self):
        """顶背驰 + 高点轻微刺破 ZD -> weak"""
        bars = self.mk_sell3_bars(b_end=12.8)   # 高点≈12.93
        sig_dt = bars[-1]["dt"]
        r = confirm_sell3_30m(bars, 12.75, 13.5, sig_dt)  # 12.93 ≤ 12.75*1.02
        self.assertEqual(r["status"], "weak", r)


class TestBuy2Confirm30m(unittest.TestCase):
    def mk_buy2_bars(self):
        """以底分型收尾的 30m 序列: up -> down(缓跌至 10.5) -> 小反弹

        下行段末根 close=10.5, low=10.29; 其后反弹确认底分型。
        """
        runs = [
            ("up", 10.0, 12.0, 8),
            ("down", 12.0, 10.5, 8),
            ("up", 10.5, 11.0, 4),
        ]
        return make_run_bars(runs)

    def test_confirmed(self):
        """30m 底分型 + 低点(≈10.29)不破一买低点 10.0 -> confirmed"""
        bars = self.mk_buy2_bars()
        sig_dt = bars[-1]["dt"]
        r = confirm_buy2_30m(bars, buy1_price=10.0, signal_dt=sig_dt)
        self.assertEqual(r["status"], "confirmed", r)
        self.assertGreaterEqual(r["dist_b1"], 0)

    def test_broke(self):
        """低点 ≈10.29 < 一买低点 10.6 -> broke(默认 pierce_tol=0)"""
        bars = self.mk_buy2_bars()
        sig_dt = bars[-1]["dt"]
        r = confirm_buy2_30m(bars, buy1_price=10.6, signal_dt=sig_dt)
        self.assertEqual(r["status"], "broke", r)

    def test_weak_with_pierce_tol(self):
        """刺破 1.9% 在 5% 容忍内 -> weak"""
        bars = self.mk_buy2_bars()
        sig_dt = bars[-1]["dt"]
        r = confirm_buy2_30m(bars, buy1_price=10.6, signal_dt=sig_dt,
                             pierce_tol=0.05)
        self.assertEqual(r["status"], "weak", r)

    def test_stale(self):
        """信号日 5 天后 -> 窗口内无底分型 -> stale"""
        bars = self.mk_buy2_bars()
        sig_dt = bars[-1]["dt"] + datetime.timedelta(days=5)
        r = confirm_buy2_30m(bars, buy1_price=10.0, signal_dt=sig_dt)
        self.assertEqual(r["status"], "stale", r)

    def test_no_data(self):
        r = confirm_buy2_30m([], buy1_price=10.0, signal_dt="2026-08-14")
        self.assertEqual(r["status"], "no_data")


class TestEventBridges(unittest.TestCase):
    def test_buy3_bridge_matches_direct(self):
        """事件桥接结果与直接调用一致"""
        bars = mk_buy3_bars(b_end=11.6)
        sig_dt = bars[-1]["dt"]
        evt = {"zs_zd": 10.0, "zs_zg": 11.2,
               "pull_end_dt": sig_dt, "dt": sig_dt}
        direct = confirm_buy3_30m(bars, 10.0, 11.2, sig_dt)
        bridged = confirm_buy3_event_30m(evt, bars)
        self.assertEqual(bridged["status"], direct["status"])
        self.assertEqual(bridged["status"], "confirmed")

    def test_sell3_bridge_matches_direct(self):
        """卖点桥接镜像"""
        runs = [
            ("down", 12.0, 9.0, 8),
            ("up", 9.0, 12.6, 8),
            ("down", 12.6, 11.0, 8),
            ("up", 11.0, 12.8, 8),
            ("down", 12.8, 12.5, 4),
        ]
        bars = make_run_bars(runs)
        sig_dt = bars[-1]["dt"]
        evt = {"zs_zd": 13.2, "zs_zg": 14.0,
               "pull_end_dt": sig_dt, "dt": sig_dt}
        direct = confirm_sell3_30m(bars, 13.2, 14.0, sig_dt)
        bridged = confirm_sell3_event_30m(evt, bars)
        self.assertEqual(bridged["status"], direct["status"])

    def test_bridge_missing_fields(self):
        """事件缺中枢字段 -> no_data"""
        r = confirm_buy3_event_30m({}, [])
        self.assertEqual(r["status"], "no_data")
        r = confirm_sell3_event_30m({"zs_zd": 10.0}, [])
        self.assertEqual(r["status"], "no_data")


if __name__ == "__main__":
    unittest.main()
