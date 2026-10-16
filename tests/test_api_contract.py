# -*- coding: utf-8 -*-
"""候选版公开 API 契约快照(0.13.2, R6 §11.9 第 1—3 条)。

API.md 是人读契约, 本文件是机器可查快照: 导出清单、常量值域与
核心链 to_dict 键集。任一快照变化必须另排版本并在 CHANGELOG
登记(行为变化附差异收据), 不允许静默修改; 新增导出须同步更新
本快照与 API.md。
"""

import math
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pandas as pd  # noqa: E402
import chan  # noqa: E402

#: 包级 __all__ 冻结快照(0.13.1: 185 项)。
FROZEN_EXPORTS = [
    "ALIGN_DOWN", "ALIGN_UP", "AnalysisResult", "AvailableSnapshot",
    "BAR_KEYS", "BI", "BI_STANDARD_106", "BI_STANDARD_81",
    "BI_TRANSITIONS", "BREAK_EFFECTIVE", "BREAK_NONE", "BREAK_TESTING",
    "BcNestInput", "BcNestLevel", "CenterEvent", "CenterLineage",
    "CenterVersion", "ConfirmedCenter", "ConfirmedDivergence",
    "ConfirmedFractalRange", "ConfirmedMove", "ConfirmedMoveType",
    "FX", "FirstPoint", "FirstPointScan", "FormationEvent",
    "FormationState", "FractalRangeState", "FxPowerResult", "Gap",
    "KISS_FLY", "KISS_LIP", "KISS_WET", "KissEvent",
    "LevelDecomposition", "MAX_LEVELS_DEFAULT", "MA_PERIODS",
    "MIN_K_GAP", "MIN_UNITS_FOR_NEXT", "MaArea", "MaBreakState",
    "MaClassResult", "MaPoint", "MaStrengthState", "MoveType",
    "NestBcState", "NewBar", "OSC_UPGRADE_N", "ObservationChange",
    "OscReport", "POWER_NEUTRAL", "POWER_SEVERE", "POWER_STRONG",
    "POWER_WEAK", "PointChain", "PointContext", "REASON_BC",
    "REASON_EMPTY", "REASON_NOT_NESTED", "REASON_NO_EXTREME",
    "REASON_STRONGER", "REASON_WEAK_SIGN", "ReplaySnapshot", "Round",
    "RoundChain", "SEVERITY_RANKS", "STAGE_BREAKOUT", "STAGE_STRONG",
    "STAGE_SUB_BS3", "STAGE_WITHIN", "STRICT_CANDIDATE",
    "STRICT_CONFIRMED", "STRICT_INSUFFICIENT", "STRICT_REJECTED",
    "SecondPoint", "SecondPointContext", "SectorStrength",
    "StrictChain", "StrictChainLevel", "StrictCompletion",
    "StrictCompletionLevel", "StrictDivergence", "StrictScan",
    "StructureObservation", "TURN_BREAK", "TURN_CANDIDATES",
    "TURN_EXPANSION", "TURN_SUB_FLOOR", "ThirdPoint",
    "ThirdPointContext", "UPGRADE_UNITS", "WEDGE_MIN_RUN", "XD", "ZS",
    "ZhongYinResult", "ZsEvent", "__version__", "alignment_series",
    "analyze_at", "analyze_available", "analyze_bars",
    "analyze_point_chain", "avg_strength_state", "bars_to_df",
    "bi_state", "bi_transition_valid", "boll_bands",
    "boll_bs1_hints", "boll_events", "boll_state", "build_expanded_zs",
    "causal_graph_dot", "chan_bis_xds", "chan_fx_bi",
    "change_starts_low", "classify_bc_turn", "classify_fx",
    "classify_fx_power", "classify_gap", "classify_kiss",
    "classify_ma_strength", "classify_minor_turn", "classify_trend",
    "confirm_buy2_30m", "confirm_buy3_30m", "confirm_buy3_event_30m",
    "confirm_level_up", "confirm_sell3_30m", "confirm_sell3_event_30m",
    "decompose_levels", "disease_stage", "ema", "find_bis",
    "find_buy_points", "find_first_points", "find_fxs", "find_gaps",
    "find_kisses", "find_ma_bc", "find_ma_points", "find_pan_bc",
    "find_run_exhaustion", "find_second_points", "find_sell_points",
    "find_third_points", "find_trend_bc", "find_xds", "find_zs",
    "first_point_contexts", "followup_quality", "formation_state",
    "fractal_range_state", "guaranteed_rebound_gap", "level_reading",
    "level_up", "ma_areas", "ma_break_state", "ma_strength_class",
    "macd_below_zero", "macd_guard_series", "macd_series", "nested_bc",
    "normalize_bars", "osc_strength", "oscillation_monitor",
    "remove_includes", "replay_available", "replay_bars",
    "same_level_decompose", "scan_first_points",
    "scan_strict_divergence", "sector_strength", "segment_area",
    "sma_series", "strict_completion_cascade", "strict_nested_chain",
    "track_center_lineage", "track_rounds", "track_zhongyin",
    "track_zs", "travel_force", "validate_bars", "zhongyin_health",
    "zn_next_estimate", "zs_relation",
]

#: 导出常量值域冻结快照(值即协议)。
FROZEN_CONSTANTS = {
    "TURN_BREAK": "turn",
    "TURN_EXPANSION": "expansion",
    "TURN_SUB_FLOOR": "sub_floor",
    "TURN_CANDIDATES": ["consolidation", "counter_trend"],
    "STAGE_WITHIN": "within",
    "STAGE_STRONG": "strong",
    "STAGE_SUB_BS3": "sub_bs3",
    "STAGE_BREAKOUT": "breakout",
    "KISS_FLY": "fly",
    "KISS_LIP": "lip",
    "KISS_WET": "wet",
    "ALIGN_UP": "up",
    "ALIGN_DOWN": "down",
    "POWER_WEAK": "weak",
    "POWER_NEUTRAL": "neutral",
    "POWER_STRONG": "strong",
    "POWER_SEVERE": "severe",
    "BREAK_NONE": "none",
    "BREAK_TESTING": "testing",
    "BREAK_EFFECTIVE": "effective",
    "STRICT_CONFIRMED": "confirmed",
    "STRICT_CANDIDATE": "candidate",
    "STRICT_INSUFFICIENT": "insufficient_evidence",
    "STRICT_REJECTED": "rejected",
    "BI_STANDARD_81": "81",
    "BI_STANDARD_106": "106",
    "UPGRADE_UNITS": 9,
    "OSC_UPGRADE_N": 9,
    "WEDGE_MIN_RUN": 4,
    "MAX_LEVELS_DEFAULT": 8,
    "MIN_UNITS_FOR_NEXT": 3,
    "MA_PERIODS": (5, 13, 21, 34, 55, 89, 144, 233),
    "MIN_K_GAP": 3,
    "REASON_BC": "bc",
    "REASON_STRONGER": "stronger",
    "REASON_NO_EXTREME": "no_new_extreme",
    "REASON_WEAK_SIGN": "weak_sign",
    "REASON_NOT_NESTED": "not_nested",
    "REASON_EMPTY": "empty",
}

#: 核心链 to_dict 键集冻结快照(API.md §5)。
FROZEN_KEY_SETS = {
    "AnalysisResult": ["as_of", "bi_trends", "bi_zss", "bis",
                       "buy_points", "dea", "dif", "fxs", "hist",
                       "new_bars", "pan_bc", "sell_points", "trend_bc",
                       "xd_zss", "xds"],
    "NewBar": ["close", "dt", "elements", "high", "low", "open",
               "volume"],
    "FX": ["bar_index", "dt", "elements", "high", "kind", "low",
           "value"],
    "BI": ["direction", "end", "end_dt", "end_index", "high", "low",
           "start", "start_dt", "start_index"],
    "XD": ["complete", "dd", "direction", "end", "evidence_dt",
           "evidence_end_index", "gg", "mode", "start"],
    "ZS": ["dd", "direction", "end_dt", "extended_9", "gg",
           "start_dt", "xd_count", "zd", "zg"],
    "ReplaySnapshot": ["changes", "observed_dt", "result"],
    "ObservationChange": ["after", "before", "field", "first_seen",
                          "identity", "kind", "observed_dt"],
}


def sine_bars():
    """与 README §3 同源合成行情(160 根日线)。"""
    closes = [20.0 + 3.0 * math.sin(i / 6.0) + i / 80.0
              for i in range(160)]
    frame = pd.DataFrame({
        "open": closes, "close": closes,
        "high": [price + 0.3 for price in closes],
        "low": [price - 0.3 for price in closes],
        "volume": [1000.0] * len(closes),
    }, index=[datetime(2025, 1, 1) + timedelta(days=i)
              for i in range(160)])
    return chan.normalize_bars(frame)


class TestExportSnapshot(unittest.TestCase):
    """__all__ 与常量值域冻结。"""

    def test_exports_frozen(self):
        """包级导出清单与快照逐一相等; 增删须另排版本登记。"""
        self.assertEqual(sorted(chan.__all__), FROZEN_EXPORTS)

    def test_constant_values_frozen(self):
        """导出常量值域与快照一致; 值即协议, 禁止改值。"""
        for name, expected in FROZEN_CONSTANTS.items():
            with self.subTest(name=name):
                actual = getattr(chan, name)
                if isinstance(expected, list):
                    self.assertEqual(list(actual), expected)
                else:
                    self.assertEqual(actual, expected)


class TestCoreChainKeySets(unittest.TestCase):
    """核心链 to_dict 键集冻结(API.md §5 表)。"""

    @classmethod
    def setUpClass(cls):
        cls.bars = sine_bars()
        cls.result = chan.analyze_bars(cls.bars)

    def test_analysis_result_key_set(self):
        self.assertEqual(sorted(self.result.to_dict()),
                         FROZEN_KEY_SETS["AnalysisResult"])

    def test_structure_key_sets(self):
        """NewBar/FX/BI/XD/ZS 键集逐对象冻结; 空结构跳过。"""
        cases = [("NewBar", self.result.new_bars),
                 ("FX", self.result.fxs),
                 ("BI", self.result.bis),
                 ("XD", self.result.xds),
                 ("ZS", self.result.bi_zss)]
        for name, items in cases:
            if not items:
                continue
            with self.subTest(name=name):
                self.assertEqual(sorted(items[0].to_dict()),
                                 FROZEN_KEY_SETS[name])

    def test_replay_key_sets(self):
        """ReplaySnapshot/ObservationChange 键集冻结。"""
        snaps = list(chan.replay_bars(self.bars))
        self.assertTrue(snaps)
        self.assertEqual(sorted(snaps[-1].to_dict()),
                         FROZEN_KEY_SETS["ReplaySnapshot"])
        changes = [c for s in snaps for c in s.changes]
        if changes:
            self.assertEqual(sorted(changes[0].to_dict()),
                             FROZEN_KEY_SETS["ObservationChange"])


if __name__ == "__main__":
    unittest.main()
