# -*- coding: utf-8 -*-
"""课106历史攻克分类与板块算术均值, 不按当前均线位置降类。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from chan import MA_PERIODS, classify_ma_strength, ma_strength_class, sector_strength


def rank(number):
    return classify_ma_strength([10],
                                {n: [9 if i < number - 1 else 11]
                                 for i, n in enumerate(MA_PERIODS)}, 0)


class TestMaClass(unittest.TestCase):
    def test_all_nine_classes(self):
        for cls in range(1, 10):
            result = rank(cls)
            self.assertEqual(result.class_no, cls)
            self.assertEqual(result.unconquered_period,
                             MA_PERIODS[cls - 1] if cls < 9 else None)

    def test_prior_conquest_survives_return_below(self):
        result = classify_ma_strength([12, 8], {n: [10, 10] for n in MA_PERIODS}, 0)
        self.assertEqual(result.class_no, 9)
        self.assertEqual(result.conquered_at, (0,) * 8)

    def test_minimum_unconquered_not_count(self):
        result = classify_ma_strength([10], {5: [9], 13: [11], 21: [9]}, 0)
        self.assertEqual(result.states, (True, False, True))
        self.assertEqual(result.class_no, 2)

    def test_equal_touch_does_not_conquer(self):
        self.assertEqual(classify_ma_strength([10], {5: [10]}, 0).class_no, 1)

    def test_confirm_and_missing_break_streak(self):
        result = classify_ma_strength([12, None, 12, 12, 8], {5: [10] * 5}, 0, confirm=2)
        self.assertEqual(result.conquered_at, (3,))
        self.assertEqual(result.class_no, 2)
        result = classify_ma_strength([12, 8, 12], {5: [10] * 3}, 0, confirm=2)
        self.assertEqual(result.class_no, 1)

    def test_unknown_not_weak(self):
        for missing in [None, float("nan"), float("inf")]:
            result = classify_ma_strength([8, 8], {5: [missing, 10]}, 0)
            self.assertIsNone(result.class_no)
            self.assertEqual(result.states, (None,))

    def test_observed_conquest_resolves_prior_missing(self):
        result = classify_ma_strength([8, 12], {5: [None, 10]}, 0)
        self.assertEqual(result.class_no, 2)

    def test_higher_unknown_does_not_hide_lower_resistance(self):
        result = classify_ma_strength([8], {5: [10], 13: [None]}, 0)
        self.assertEqual(result.class_no, 1)
        self.assertEqual(result.states, (False, None))

    def test_new_rebound_resets_evidence(self):
        result = classify_ma_strength([12, 8], {5: [10, 10]}, 1)
        self.assertEqual((result.class_no, result.start_index), (1, 1))

    def test_prefix_replay_is_causal(self):
        prices = [8, 12, 8, 14, 8]
        mas = {5: [10] * 5, 13: [13] * 5}
        expected = [1, 2, 2, 3, 3]
        for length, cls in enumerate(expected, 1):
            result = classify_ma_strength(prices[:length], {n: line[:length] for n, line in mas.items()}, 0)
            self.assertEqual(result.class_no, cls)

    def test_sma_uses_pre_rebound_history(self):
        result = ma_strength_class([20, 20, 20, 20, 30], 4, periods=(5,))
        self.assertEqual(result.class_no, 2)
        self.assertEqual(result.conquered_at, (4,))

    def test_sma_missing_windows_are_not_filled(self):
        result = ma_strength_class([10, None, 8, 7], 2, periods=(2,))
        self.assertIsNone(result.class_no)
        self.assertEqual(ma_strength_class([10, None, 8, 7], 3, periods=(2,)).class_no, 1)

    def test_full_warmup_constant_prices_stay_equal(self):
        result = ma_strength_class([10] * 233, 232)
        self.assertEqual(result.states, (False,) * 8)
        self.assertEqual(result.class_no, 1)

    def test_generated_sma_every_prefix_matches_manual(self):
        prices = [10, 12, 8, 14, 11, 15]
        for length in range(3, len(prices) + 1):
            prefix = prices[:length]
            mas = {n: [None if i < n - 1 else sum(prefix[i-n+1:i+1]) / n
                       for i in range(length)] for n in [2, 3]}
            self.assertEqual(ma_strength_class(prefix, 2, periods=(2, 3)),
                             classify_ma_strength(prefix, mas, 2))

    def test_empty_or_not_yet_observed_is_unknown(self):
        for result in [ma_strength_class([], 0), ma_strength_class([10], 1)]:
            self.assertIsNone(result.class_no)
            self.assertEqual(result.states, (None,) * 8)

    def test_input_contracts(self):
        for start in [-1, 2, 0.5, True]:
            with self.assertRaises(ValueError):
                ma_strength_class([10], start)
        for confirm in [0, 1.5, True]:
            with self.assertRaises(ValueError):
                ma_strength_class([10], 0, confirm=confirm)
        for periods in [(), (2, 2), (3, 2), (False,), (2.5,)]:
            with self.assertRaises(ValueError):
                ma_strength_class([10], 0, periods=periods)
        for mas in [{}, {5: []}, {5: [10], "bad": [10]}, {True: [10]}, {5: ["10"]}]:
            with self.assertRaises(ValueError):
                classify_ma_strength([10], mas, 0)
        for bad in [False, "10", 0, -10]:
            with self.assertRaises(ValueError):
                ma_strength_class([bad], 0)

    def test_snapshot_owned_and_result_immutable(self):
        result = rank(4)
        with self.assertRaises(AttributeError):
            result.class_no = 9
        snapshot = result.to_dict()
        snapshot["period_states"][0]["conquered"] = False
        self.assertTrue(result.states[0])


class TestSectorStrength(unittest.TestCase):
    def test_arithmetic_mean_and_coverage(self):
        unknown = ma_strength_class([], 0)
        result = sector_strength({"a": rank(1), "b": rank(9), "c": unknown})
        self.assertEqual(result.mean_class, 5)
        self.assertEqual((result.valid_count, result.total_count), (2, 3))
        self.assertAlmostEqual(result.coverage, 2/3)
        self.assertEqual(result.distribution, (1, 0, 0, 0, 0, 0, 0, 0, 1))

    def test_empty_and_all_unknown_have_no_mean(self):
        for members in [{}, {"a": ma_strength_class([], 0)}]:
            result = sector_strength(members)
            self.assertIsNone(result.mean_class)
            self.assertEqual(result.coverage, 0)

    def test_incomparable_periods_or_confirmation_rejected(self):
        for other in [ma_strength_class([10], 0, periods=(5,)),
                      ma_strength_class([10], 0, confirm=2)]:
            with self.assertRaises(ValueError):
                sector_strength({"a": rank(1), "b": other})

    def test_member_and_snapshot_contract(self):
        for members in [[rank(1)], {"": rank(1)}, {"a": 1}, {"a": rank(1)._replace(class_no=0)}]:
            with self.assertRaises(ValueError):
                sector_strength(members)
        result = sector_strength({"a": rank(1)})
        snapshot = result.to_dict()
        snapshot["distribution"][0] = 9
        self.assertEqual(result.distribution[0], 1)


if __name__ == "__main__":
    unittest.main()
