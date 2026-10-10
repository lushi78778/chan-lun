# -*- coding: utf-8 -*-
"""行情契约与批量门面: 拒绝脏输入、旧链路等价、快照隔离。"""

import json
import math
import os
import sys
import unittest
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from chan import (AnalysisResult, analyze_bars, chan_fx_bi, classify_trend,
                  find_buy_points, find_pan_bc, find_sell_points,
                  find_trend_bc, find_xds, find_zs, macd_series,
                  normalize_bars, validate_bars)


def make_bars(count=240):
    bars = []
    for index in range(count):
        price = 20.0 + 3.0 * math.sin(index / 6.0) + index / 80.0
        bars.append({"dt": datetime(2025, 1, 1) + timedelta(days=index),
                     "open": price, "high": price + 0.3, "low": price - 0.3,
                     "close": price, "volume": 1000.0})
    return bars


class TestBarValidation(unittest.TestCase):
    def test_supported_time_representations(self):
        bars = make_bars(3)
        conversions = [lambda dt: dt, lambda dt: dt.date(),
                       lambda dt: dt.strftime("%Y-%m-%d"),
                       lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
                       lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                       lambda dt: dt.replace(tzinfo=timezone(timedelta(hours=8)))]
        for convert in conversions:
            with self.subTest(convert=convert):
                records = deepcopy(bars)
                for bar in records:
                    bar["dt"] = convert(bar["dt"])
                before = deepcopy(records)
                self.assertIsNone(validate_bars(tuple(records)))
                self.assertEqual(records, before)

    def test_dataframe_adapter_then_validate(self):
        import pandas as pd
        frame = pd.DataFrame(make_bars(3)).set_index("dt")
        validate_bars(normalize_bars(frame))
        records = make_bars(2)
        for bar in records:
            bar["dt"] = pd.Timestamp(bar["dt"])
            bar["volume"] = np.int64(1000)
            bar["close"] = np.float64(bar["close"])
        validate_bars(records)

    def test_bad_containers(self):
        for value in (None, {}, "bars", iter(make_bars(2))):
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    validate_bars(value)
        with self.assertRaisesRegex(ValueError, r"bars\[0\]"):
            validate_bars([object()])

    def test_missing_key_and_invalid_numbers_report_row(self):
        cases = [("open", None), ("close", "20"), ("volume", True),
                 ("high", float("inf")), ("low", float("nan")),
                 ("close", 0), ("open", -1), ("volume", -1)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                bars = make_bars(2)
                bars[1][field] = value
                with self.assertRaisesRegex(ValueError, r"bars\[1\]"):
                    validate_bars(bars)
        bars = make_bars(2)
        del bars[1]["volume"]
        with self.assertRaisesRegex(ValueError, "缺少字段: volume"):
            validate_bars(bars)

    def test_price_envelope(self):
        for field, value in (("high", 1), ("low", 100), ("open", 100), ("close", 1)):
            with self.subTest(field=field):
                bars = make_bars(1)
                bars[0][field] = value
                with self.assertRaisesRegex(ValueError, "OHLC"):
                    validate_bars(bars)

    def test_duplicate_and_reversed_times_are_not_silently_repaired(self):
        bars = make_bars(2)
        for dt in (bars[0]["dt"], bars[0]["dt"] - timedelta(days=1)):
            bars[1]["dt"] = dt
            with self.assertRaisesRegex(ValueError, "严格递增"):
                validate_bars(bars)

    def test_invalid_and_mixed_times(self):
        import pandas as pd
        for dt in (None, pd.NaT, 1735689600, "2025-1-2", "2025-02-30", "2025/01/02"):
            with self.subTest(dt=str(dt)):
                bars = make_bars(2)
                bars[1]["dt"] = dt
                with self.assertRaisesRegex(ValueError, r"bars\[1\]"):
                    validate_bars(bars)
        for dt in (date(2025, 1, 2), "2025-01-02", datetime(2025, 1, 2, tzinfo=timezone.utc)):
            bars = make_bars(2)
            bars[1]["dt"] = dt
            with self.assertRaisesRegex(ValueError, "须一致"):
                validate_bars(bars)
        bars = make_bars(2)
        bars[0]["dt"] = "2025-01-01 00:00:00"
        bars[1]["dt"] = "2025-01-02T00:00:00"
        with self.assertRaisesRegex(ValueError, "须一致"):
            validate_bars(bars)

    def test_changed_utc_offset_rejected(self):
        bars = make_bars(2)
        bars[0]["dt"] = bars[0]["dt"].replace(tzinfo=timezone.utc)
        bars[1]["dt"] = bars[1]["dt"].replace(tzinfo=timezone(timedelta(hours=8)))
        with self.assertRaisesRegex(ValueError, "UTC 偏移须一致"):
            validate_bars(bars)

    def test_empty_and_zero_volume_flat_bars_are_valid(self):
        validate_bars([])
        bars = make_bars(1)
        bars[0].update(open=20, high=20, low=20, close=20, volume=0)
        validate_bars(bars)  # 停牌剔除由适配层显式决定。


class TestBatchAnalysis(unittest.TestCase):
    def test_matches_existing_manual_pipeline_at_each_level(self):
        """门面可替换现有调用接线, 不改变算法或混用中枢级别。"""
        bars = make_bars()
        result = analyze_bars(bars)
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.as_of, bars[-1]["dt"])
        new_bars, fxs, bis = chan_fx_bi(bars)
        xds = find_xds(bis)
        bi_zss, xd_zss = find_zs(bis), find_zs(xds)
        self.assertTrue(bis)
        self.assertTrue(bi_zss)
        for name, expected in (("new_bars", new_bars), ("fxs", fxs), ("bis", bis),
                               ("xds", xds), ("bi_zss", bi_zss), ("xd_zss", xd_zss)):
            self.assertEqual([item.to_dict() for item in getattr(result, name)],
                             [item.to_dict() for item in expected])
        dif, dea, hist = macd_series(bars)
        for actual, expected in ((result.dif, dif), (result.dea, dea), (result.hist, hist)):
            np.testing.assert_array_equal(actual, expected)
        trend_bc = find_trend_bc(bis, bi_zss, bars)
        self.assertEqual(result.trend_bc, trend_bc)
        self.assertEqual(result.pan_bc, find_pan_bc(bis, bi_zss, bars))
        self.assertEqual(result.bi_trends, classify_trend(bi_zss))
        self.assertEqual(result.buy_points, find_buy_points(bis, bi_zss, trend_bc))
        self.assertEqual(result.sell_points, find_sell_points(bis, bi_zss, trend_bc))

    def test_empty_and_short_history(self):
        result = analyze_bars([])
        self.assertIsNone(result.as_of)
        for field in result._fields[1:]:
            self.assertEqual(len(getattr(result, field)), 0)
        json.dumps(result.to_dict(), allow_nan=False)
        result = analyze_bars(make_bars(2))
        self.assertEqual(len(result.hist), 2)
        self.assertEqual(result.bis, [])

    def test_input_and_results_do_not_share_mutable_state(self):
        bars = make_bars()
        before = deepcopy(bars)
        first = analyze_bars(bars)
        second = analyze_bars(bars)
        expected = second.to_dict()
        self.assertEqual(bars, before)
        first.new_bars[0].close = -1
        first.new_bars[0].elements.append(-1)
        first.bis[0].end_value = -1
        first.hist[0] = -1
        self.assertEqual(bars, before)
        self.assertEqual(second.to_dict(), expected)

    def test_serialized_snapshot_is_json_ready_and_detached(self):
        result = analyze_bars(make_bars())
        snapshot = result.to_dict()
        json.dumps(snapshot, allow_nan=False)
        snapshot["new_bars"][0]["elements"].append(-1)
        snapshot["bis"][0]["end"] = -1
        snapshot["hist"][0] = -1
        self.assertNotEqual(result.hist[0], -1)
        self.assertNotEqual(result.bis[0].end_value, -1)
        self.assertNotIn(-1, result.new_bars[0].elements)
        with self.assertRaises(AttributeError):
            result.as_of = "changed"

    def test_prefix_replay_has_no_hidden_cross_call_state(self):
        bars = make_bars()
        past = analyze_bars(bars[:120]).to_dict()
        analyze_bars(bars)
        self.assertEqual(analyze_bars(bars[:120]).to_dict(), past)
        self.assertEqual(past["as_of"], str(bars[119]["dt"]))

    def test_raw_ohlc_contract_not_applied_to_merged_geometry(self):
        bars = [
            {"dt": "2025-01-01", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
            {"dt": "2025-01-02", "open": 12, "high": 14, "low": 11, "close": 13, "volume": 1},
            {"dt": "2025-01-03", "open": 13, "high": 15, "low": 10, "close": 10, "volume": 1},
        ]
        result = analyze_bars(bars)
        merged = result.new_bars[-1]
        self.assertEqual(merged.elements, [1, 2])
        self.assertLess(merged.close, merged.low)

    def test_invalid_history_rejected_before_analysis(self):
        bars = make_bars(2)
        bars[1]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, r"bars\[1\]"):
            analyze_bars(bars)

    def test_custom_gap_and_invalid_parameters(self):
        bars = make_bars()
        result = analyze_bars(bars, min_k_gap=5)
        expected = chan_fx_bi(bars, min_k_gap=5)[2]
        self.assertEqual([bi.to_dict() for bi in result.bis], [bi.to_dict() for bi in expected])
        for gap in (True, -1, 1.5, "3"):
            with self.assertRaises(ValueError):
                analyze_bars(bars, min_k_gap=gap)


if __name__ == "__main__":
    unittest.main()
