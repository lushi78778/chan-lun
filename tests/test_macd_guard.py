# -*- coding: utf-8 -*-
"""课103: 黄白两线负区、零轴触及、混合状态和因果前缀。"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from chan.bc import macd_series
from chan.macd_guard import macd_below_zero, macd_guard_series


class TestMacdGuard(unittest.TestCase):
    def test_both_negative(self):
        """课103字面条件: 两线均在零轴下, 布尔回避为True。"""
        self.assertIs(macd_below_zero(-0.1, -0.2), True)

    def test_both_positive(self):
        """两线均正未命中回避; False本身不是买点许可。"""
        self.assertIs(macd_below_zero(0.1, 0.2), False)

    def test_mixed_sign_not_both_below(self):
        """一正一负属于跨轴过渡, 不偷换成'黄白两线轴下'。"""
        self.assertIs(macd_below_zero(-1, 1), False)
        self.assertIs(macd_below_zero(1, -1), False)

    def test_zero_boundary(self):
        """'下面'严格负数, 触零不等于重新站稳确认。"""
        for dif, dea in ((0, 0), (0, -1), (-1, 0), (-0.0, -0.0)):
            self.assertIs(macd_below_zero(dif, dea), False)

    def test_missing_lines_are_unknown(self):
        """数据缺口不给False通过, 任一线缺测返回None。"""
        for missing in (None, float("nan"), float("inf"), -float("inf")):
            self.assertIsNone(macd_below_zero(missing, -1))
            self.assertIsNone(macd_below_zero(-1, missing))

    def test_invalid_numeric_types(self):
        """错误类型明确拒绝, 不把字符串或bool当成有效MACD。"""
        for value in (True, "-1", object(), 10 ** 1000):
            with self.assertRaises(ValueError):
                macd_below_zero(value, -1)

    def test_numpy_values_return_python_bool(self):
        """与bc的numpy数组直接组合, 输出稳定的Python bool。"""
        self.assertIs(macd_below_zero(np.float64(-1), np.float64(-2)), True)

    def test_series_preserves_positions_and_warmup(self):
        """逐棒对齐, 不越过缺测向后找值或缩短序列。"""
        result = macd_guard_series([None, -1, -1, 0, 1], [None, -2, 1, -1, 1])
        self.assertEqual(result, [None, True, False, False, False])

    def test_empty_and_length_mismatch(self):
        """空输入无判据; 两线必须来自同一等长时间序列。"""
        self.assertEqual(macd_guard_series([], []), [])
        with self.assertRaises(ValueError):
            macd_guard_series([-1], [])

    def test_macd_integration_each_prefix_matches_history(self):
        """零轴判据复用内置因果MACD, 未来数据不改写前缀结果。"""
        bars = [{"close": float(price)} for price in [20, 19, 18, 17, 18, 21, 24, 28]]
        dif, dea, _ = macd_series(bars)
        full = macd_guard_series(dif, dea)
        self.assertTrue(any(value is True for value in full))
        for count in range(1, len(bars) + 1):
            p_dif, p_dea, _ = macd_series(bars[:count])
            self.assertEqual(macd_guard_series(p_dif, p_dea), full[:count])


if __name__ == "__main__":
    unittest.main()
