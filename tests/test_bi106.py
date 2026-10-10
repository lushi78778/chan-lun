# -*- coding: utf-8 -*-
"""课106: 六个无包含K单位+5周期均线必要条件, 默认课81零漂移。"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from chan import analyze_bars, chan_bis_xds, chan_fx_bi, find_bis
from chan.strength import sma_series


def bars_from(ranges):
    return [{"dt": datetime(2025, 1, 1) + timedelta(days=i),
             "open": (h + l) / 2.0, "close": (h + l) / 2.0,
             "high": float(h), "low": float(l), "volume": 100.0}
            for i, (h, l) in enumerate(ranges)]


SIX = [(12, 10), (11, 9), (13, 11), (15, 13), (16, 14), (15, 13)]


class TestBi106(unittest.TestCase):
    def test_six_units_and_five_ma_touch(self):
        """课106六K例: 两个三K分型不共用, 极值索引1至4。"""
        nb, fxs, bis = chan_fx_bi(bars_from(SIX), standard="106")
        self.assertEqual(len(nb), 6)
        self.assertEqual([fx.bar_index for fx in fxs], [1, 4])
        self.assertEqual(len(bis), 1)
        self.assertEqual((bis[0].start_index, bis[0].end_index), (1, 4))
        self.assertEqual(bis[0].direction, "up")

    def test_default_81_and_explicit_81_match(self):
        """课81仍要求中间3根, 同一六K盘面默认不成笔。"""
        bars = bars_from(SIX)
        self.assertEqual(chan_fx_bi(bars)[2], [])
        self.assertEqual(chan_fx_bi(bars, standard="81")[2], [])

    def test_five_units_too_short_even_with_ma_evidence(self):
        """课106硬边界: 五K使两个分型共用, 均线触及也不能成笔。"""
        nb, fxs, _ = chan_fx_bi(bars_from([(12, 10), (11, 9), (13, 11), (16, 14), (15, 13)]))
        self.assertEqual(find_bis(nb, fxs, standard="106", ma5=[10] * 5), [])

    def test_no_touch_rejects_up_bi(self):
        """课106: 反弹最高也达不到MA5, 缺少笔级反弹必要证据。"""
        nb, fxs, _ = chan_fx_bi(bars_from(SIX))
        self.assertEqual(find_bis(nb, fxs, standard="106", ma5=[100] * 6), [])

    def test_touch_equality_counts(self):
        """原文'碰到'含相等, 不额外要求收盘突破。"""
        nb, fxs, _ = chan_fx_bi(bars_from(SIX))
        ma5 = [100] * 6
        ma5[4] = nb[4].high
        self.assertEqual(len(find_bis(nb, fxs, standard="106", ma5=ma5)), 1)

    def test_confirmation_neighbor_not_used_for_ma_touch(self):
        """确认分型右邻不属于笔的端点区间, 不拿它制造均线触及。"""
        nb, fxs, _ = chan_fx_bi(bars_from(SIX))
        ma5 = [100] * 6
        ma5[5] = 10
        self.assertEqual(find_bis(nb, fxs, standard="106", ma5=ma5), [])

    def test_down_direction_mirror(self):
        """课106调整反过来: low<=MA5镜像触及而成向下笔。"""
        nb, fxs, bis = chan_fx_bi(bars_from([(40 - l, 40 - h) for h, l in SIX]),
                                  standard="106")
        self.assertEqual(len(bis), 1)
        self.assertEqual(bis[0].direction, "down")
        self.assertEqual(find_bis(nb, fxs, standard="106", ma5=[0] * 6), [])

    def test_explicit_gap_can_tighten_but_not_relax_six_units(self):
        """工程参数可额外收紧; 即使min_gap=0也不能取消六K条件。"""
        self.assertEqual(chan_fx_bi(bars_from(SIX), standard="106", min_k_gap=3)[2], [])
        self.assertEqual(len(chan_fx_bi(bars_from(SIX), standard="106", min_k_gap=0)[2]), 1)

    def test_missing_ma_cannot_silently_fall_back(self):
        """缺整条MA5序列报错, 全暖机/非有限缺测不构成触及。"""
        nb, fxs, _ = chan_fx_bi(bars_from(SIX))
        for ma5 in (None, [], [10] * 5, ["10"] * 6):
            with self.assertRaises(ValueError):
                find_bis(nb, fxs, standard="106", ma5=ma5)
        for value in (None, float("nan"), float("inf")):
            self.assertEqual(find_bis(nb, fxs, standard="106", ma5=[value] * 6), [])

    def test_raw_ma_alignment_through_include_groups(self):
        """课106五周期是原始周期; 包含组取最后原始下标, 不重算合并MA。"""
        bars = bars_from(SIX[:3] + [(12.5, 11.5)] + SIX[3:])
        import chan.bi as module
        original = module.find_bis
        with patch.object(module, "find_bis", wraps=original) as called:
            nb, _, _ = chan_fx_bi(bars, standard="106")
        self.assertTrue(any(len(bar.elements) > 1 for bar in nb))
        raw_ma5 = sma_series([bar["close"] for bar in bars], 5)
        expected = [raw_ma5[bar.elements[-1]] for bar in nb]
        self.assertEqual(called.call_args[1]["ma5"], expected)

    def test_right_neighbor_required_before_new_bi_visible(self):
        """分型确认不能使用未来右邻; 五根前缀看不到第4根顶分型。"""
        self.assertEqual(chan_fx_bi(bars_from(SIX[:5]), standard="106")[2], [])
        self.assertEqual(len(chan_fx_bi(bars_from(SIX), standard="106")[2]), 1)

    def test_tail_extreme_extension_keeps_existing_rule(self):
        """课81既有同向极端替换在106中同样延伸尾笔。"""
        bars = bars_from(SIX + [(18, 16), (17, 15)])
        first = chan_fx_bi(bars[:6], standard="106")[2][0]
        second = chan_fx_bi(bars, standard="106")[2][0]
        self.assertEqual(first.end_index, 4)
        self.assertEqual(second.end_index, 6)
        self.assertEqual(second.start_index, first.start_index)

    def test_pipeline_entry_points_forward_selected_standard(self):
        """组合入口显式选106, 同一笔对象定义进入线段与批量分析。"""
        bars = bars_from(SIX)
        expected = [bi.to_dict() for bi in chan_fx_bi(bars, standard="106")[2]]
        self.assertEqual([bi.to_dict() for bi in chan_bis_xds(bars, standard="106")[2]], expected)
        self.assertEqual([bi.to_dict() for bi in analyze_bars(bars, bi_standard="106").bis], expected)

    def test_empty_and_invalid_configuration(self):
        """空输入返回空; 无效规则或间隔拒绝, 不自动切换标准。"""
        self.assertEqual(chan_fx_bi([], standard="106"), ([], [], []))
        for standard in ("62", "bad", 106):
            with self.assertRaises(ValueError):
                chan_fx_bi([], standard=standard)
        for gap in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                find_bis([], min_k_gap=gap)


if __name__ == "__main__":
    unittest.main()
