# -*- coding: utf-8 -*-
"""课79/82分型力度: 图例边界、镜像、工程阈值与均线确认。"""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from chan.fx import NewBar, find_fxs
from chan.fxpower import (BREAK_EFFECTIVE, BREAK_NONE, BREAK_TESTING,
                         POWER_NEUTRAL, POWER_SEVERE, POWER_STRONG, POWER_WEAK,
                         classify_fx, classify_fx_power, ma_break_state)


def k(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


WEAK = [k(10, 15, 9, 14), k(15.6, 16, 13.8, 15.7), k(15, 15.5, 13, 15.1)]
STRONG = [k(10, 12, 9, 11), k(12, 15, 11, 12), k(11, 13, 10, 11)]
SEVERE = [k(10, 12, 9, 11), k(12, 15, 11, 13), k(10, 13, 8, 9.5)]
NEUTRAL = [k(10, 12, 9, 11), k(13.8, 15, 11, 14), k(13, 14, 10, 13.6)]


def mirror(bars):
    return [k(40 - b["open"], 40 - b["low"], 40 - b["high"], 40 - b["close"])
            for b in bars]


class TestFxPower(unittest.TestCase):
    def test_long_first_body_small_following_bodies(self):
        """课82: 第一根长阳、后两根小实体, 多数为中继。"""
        self.assertEqual(classify_fx_power(*WEAK, direction="top").power, POWER_WEAK)

    def test_long_upper_shadow_and_failed_bullish_recovery(self):
        """课82: 第二根长上影、第三根未以阳线收上中点。"""
        self.assertEqual(classify_fx_power(*STRONG, direction="top").power, POWER_STRONG)

    def test_long_bearish_second_body(self):
        """课82: 第二根直接长阴也属于强力度条件。"""
        bars = [k(10, 12, 9, 11), k(14, 15, 10, 11), k(10, 13, 9.5, 10)]
        self.assertEqual(classify_fx_power(*bars, direction="top").power, POWER_STRONG)

    def test_third_breaks_first_low_and_fails_to_recover_midpoint(self):
        """课82非包含图例: 第三根破第一根低点, 杀伤力较强。"""
        result = classify_fx_power(*SEVERE, direction="top")
        self.assertEqual(result.power, POWER_SEVERE)
        self.assertFalse(result.containment)

    def test_third_low_touch_is_not_break(self):
        """课82'跌破'严格小于; 触及第一根低点不判 severe。"""
        bars = [dict(bar) for bar in SEVERE]
        bars[2]["low"] = bars[0]["low"]
        self.assertNotEqual(classify_fx_power(*bars, direction="top").power, POWER_SEVERE)

    def test_first_midpoint_equality_not_high_close(self):
        """课82'一半之上'严格大于; 恰在中点仍满足 severe。"""
        bars = [dict(bar) for bar in SEVERE]
        bars[2]["close"] = 10.5
        self.assertEqual(classify_fx_power(*bars, direction="top").power, POWER_SEVERE)
        bars[2]["close"] = 10.51
        self.assertNotEqual(classify_fx_power(*bars, direction="top").power, POWER_SEVERE)

    def test_second_midpoint_recovery_requires_bullish_candle(self):
        """课82: 阳线收上第二根中点才解除长上影强力度条件。"""
        bars = [dict(bar) for bar in STRONG]
        bars[2] = k(12, 14, 10, 13)
        self.assertEqual(classify_fx_power(*bars, direction="top").power, POWER_STRONG)
        bars[2]["close"] = 13.01
        self.assertEqual(classify_fx_power(*bars, direction="top").power, POWER_NEUTRAL)
        bars[2]["open"] = 13.5  # 阴线即使收在中点之上也不满足'以阳线'。
        self.assertEqual(classify_fx_power(*bars, direction="top").power, POWER_STRONG)

    def test_neutral_pattern(self):
        """未命中课82三种定性图例时不给强弱结论。"""
        self.assertEqual(classify_fx_power(*NEUTRAL, direction="top").power, POWER_NEUTRAL)

    def test_bottom_mirrors_all_top_cases(self):
        """课82'底分型反过来': 四档分类、归一化指标镜像一致。"""
        for bars in (WEAK, STRONG, SEVERE, NEUTRAL):
            with self.subTest(bars=bars):
                top = classify_fx_power(*bars, direction="top")
                bottom = classify_fx_power(*mirror(bars), direction="bottom")
                self.assertEqual(top.power, bottom.power)
                for name in top.metrics:
                    self.assertAlmostEqual(top.metrics[name], bottom.metrics[name])

    def test_bad_containment_is_strong_in_both_directions(self):
        """课82六月案例: 长阴完整吃掉阳线, 独立标识最坏包含。"""
        bars = [k(11, 13, 10, 12), k(13, 14, 8, 9), k(10, 12, 9, 10)]
        for direction, values in (("top", bars), ("bottom", mirror(bars))):
            result = classify_fx_power(*values, direction=direction)
            self.assertTrue(result.bad_containment)
            self.assertTrue(result.containment)
            self.assertEqual(result.power, POWER_STRONG)

    def test_ordinary_containment_is_marked(self):
        """课82: 包含为观望辅助标签, 不能凭包含直接判杀伤力。"""
        bars = [k(11, 14, 9, 12), k(11, 13, 10, 11.5), k(11, 12, 8, 9)]
        result = classify_fx_power(*bars, direction="top")
        self.assertTrue(result.containment)
        self.assertFalse(result.bad_containment)
        self.assertNotEqual(result.power, POWER_SEVERE)

    def test_zero_range_and_threshold_parameters(self):
        """零波动无形态; 定性长短阈值由调用方调整并检查比例边界。"""
        flat = k(10, 10, 10, 10)
        self.assertEqual(classify_fx_power(flat, flat, flat, "top").power, POWER_NEUTRAL)
        self.assertEqual(classify_fx_power(*STRONG, direction="top", shadow=0.9).power,
                         POWER_NEUTRAL)
        for kwargs in ({"shadow": 0}, {"shadow": float("nan")}, {"long_body": True},
                       {"small_body": 0.5}, {"long_body": 1.1}, {"long_body": "0.3"}):
            with self.assertRaises(ValueError):
                classify_fx_power(*STRONG, direction="top", **kwargs)

    def test_find_fxs_object_entry_matches_explicit_triple(self):
        """便捷入口取相同无包含序列的左右邻, 不使用分型后数据。"""
        new_bars = [NewBar(str(i), b["open"], b["high"], b["low"], b["close"], 1)
                    for i, b in enumerate(WEAK)]
        fx = find_fxs(new_bars)[0]
        self.assertEqual(classify_fx(fx, new_bars).power,
                         classify_fx_power(*WEAK, direction="top").power)
        for index in (0, 2, -1, 1.5, True):
            with self.assertRaises(ValueError):
                classify_fx(SimpleNamespace(bar_index=index, kind="top"), new_bars)

    def test_invalid_direction_and_raw_ohlc(self):
        """拒绝无意义方向和坏形态数据, 防 NaN 默默落 neutral。"""
        with self.assertRaises(ValueError):
            classify_fx_power(*STRONG, direction="up")
        for bar in (k(11, 10, 12, 11), k(20, 12, 9, 10),
                    k(10, 12, 9, float("nan"))):
            with self.assertRaises(ValueError):
                classify_fx_power(bar, STRONG[1], STRONG[2], "top")

    def test_result_serialization_copies_collections(self):
        """结果存档不共享可修改的说明列表与指标字典。"""
        result = classify_fx_power(*SEVERE, direction="top")
        snapshot = result.to_dict()
        snapshot["reasons"].clear()
        snapshot["metrics"]["k1_body"] = -1
        self.assertTrue(result.reasons)
        self.assertGreaterEqual(result.metrics["k1_body"], 0)


class TestMaBreak(unittest.TestCase):
    def test_empty_equality_and_no_break(self):
        """课79: 未有效破5均线为中继辅助; 恰等于不算跌破。"""
        self.assertEqual(ma_break_state([], [], "top").state, BREAK_NONE)
        result = ma_break_state([10, 11, 10], [10] * 3, "top")
        self.assertEqual(result.state, BREAK_NONE)
        self.assertFalse(result.ever_tested)

    def test_unconfirmed_break(self):
        """一次收盘越线默认仍在测试, 连续两根为工程确认约定。"""
        result = ma_break_state([11, 9], [10, 10], "top")
        self.assertEqual(result.state, BREAK_TESTING)
        self.assertEqual((result.break_idx, result.confirm_idx, result.streak), (1, None, 1))

    def test_false_break_then_recovery(self):
        """课79 000938: 单次越线收回, 记录假突破而未确认。"""
        result = ma_break_state([9, 11], [10, 10], "top")
        self.assertEqual(result.state, BREAK_NONE)
        self.assertTrue(result.recovered)
        self.assertTrue(result.ever_tested)

    def test_effective_history_not_rewritten_after_recovery(self):
        """确认时刻历史单调; 收回不取消曾确认的事实, 不承诺成笔。"""
        closes = [11, 9, 8, 12]
        for count in (3, 4):
            result = ma_break_state(closes[:count], [10] * count, "top")
            self.assertEqual(result.state, BREAK_EFFECTIVE)
            self.assertEqual(result.confirm_idx, 2)
        self.assertEqual(result.streak, 0)

    def test_bottom_direction_and_configured_confirmation(self):
        """课79买点镜像: 收盘升破; confirm=1 明示单棒收盘确认。"""
        result = ma_break_state([11, 12], [10, 10], "bottom")
        self.assertEqual(result.state, BREAK_EFFECTIVE)
        self.assertEqual(result.confirm_idx, 1)
        self.assertEqual(ma_break_state([9], [10], "top", confirm=1).confirm_idx, 0)

    def test_missing_data_interrupts_confirmation_not_false_break(self):
        """暖机/缺测不能假装连续越线; 缺测不同于实际收回。"""
        for missing in (None, float("nan"), float("inf")):
            result = ma_break_state([9, missing, 9], [10] * 3, "top")
            self.assertEqual(result.state, BREAK_TESTING)
            self.assertFalse(result.recovered)
        result = ma_break_state([9, 9, 9], [10, None, 10], "top")
        self.assertEqual(result.state, BREAK_TESTING)

    def test_invalid_arguments(self):
        """确认根数为正整数, 收盘和均线按同一下标等长对齐。"""
        for confirm in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                ma_break_state([9], [10], "top", confirm=confirm)
        for closes, mas, direction in (([9], [], "top"), ([9], [10], "up"),
                                       (["9"], [10], "top")):
            with self.assertRaises(ValueError):
                ma_break_state(closes, mas, direction)


if __name__ == "__main__":
    unittest.main()
