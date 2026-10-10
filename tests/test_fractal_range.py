# -*- coding: utf-8 -*-
"""课108原文边界独立预期; 有效站住参数与极值失守分别检验。"""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import ConfirmedFractalRange, fractal_range_state


BASE = datetime(2026, 7, 1)


def bar(day, low=10, high=12, close=11, lag=5):
    dt = BASE + timedelta(days=day)
    return dict(dt=dt, closed_dt=dt + timedelta(hours=15),
                available_dt=dt + timedelta(hours=15, minutes=lag),
                open=close, close=close, low=low, high=high, volume=1.)


def context(kind='bottom', **kwargs):
    data = dict(kind=kind, dt=BASE, low=10., high=12.,
                confirmed_dt=BASE + timedelta(hours=15, minutes=5), level='day')
    data.update(kwargs)
    return ConfirmedFractalRange(**data)


def state(rows, fractal=None, confirm=2, as_of=None):
    return fractal_range_state(context() if fractal is None else fractal, rows,
                               as_of or BASE + timedelta(days=20), confirm)


class TestFractalRange(unittest.TestCase):
    def test_empty_and_not_yet_known(self):
        """确认前等待, 确认后无新K线仍在构造。"""
        self.assertEqual(fractal_range_state(None, [], BASE).phase, 'waiting')
        self.assertEqual(state([], as_of=BASE).phase, 'waiting')
        self.assertEqual(state([]).phase, 'constructing')

    def test_bottom_first_continuous_closes_complete_at_arrival(self):
        """连续两次严格站沿, 以第二根实际到达时间为首次成功。"""
        rows = [bar(1, high=14, close=13), bar(2, high=15, close=14)]
        self.assertEqual(state(rows[:1]).phase, 'testing')
        result = state(rows)
        self.assertEqual((result.phase, result.streak), ('completed', 2))
        self.assertEqual(result.end_dt, rows[1]['available_dt'])
        self.assertEqual(result.first_test_dt, rows[0]['available_dt'])

    def test_intrabar_low_break_fails_even_when_close_is_above(self):
        """盘中破底即失败, 同根大阳收上沿不能弥补。"""
        row = bar(1, low=9, high=14, close=13)
        self.assertEqual(state([row], confirm=1).phase, 'failed')
        self.assertEqual(state([row]).end_dt, row['available_dt'])

    def test_top_mirrors_success_and_failure(self):
        """顶部连续收盘跌下沿成功, 盘中破顶失败。"""
        self.assertEqual(state([bar(1, low=8, close=9), bar(2, low=7, close=8)],
                               context('top')).phase, 'completed')
        self.assertEqual(state([bar(1, high=13)], context('top')).phase, 'failed')

    def test_touch_invalid_edge_is_not_failure(self):
        """原文跌破/升破为严格边界, 触低/高点仍在构造。"""
        self.assertEqual(state([bar(1)]).phase, 'constructing')
        self.assertEqual(state([bar(1)], context('top')).phase, 'constructing')

    def test_touch_success_edge_resets_streak(self):
        """收盘恰触上沿不算站住, 连续次数必须重新累计。"""
        rows = [bar(1, high=14, close=13), bar(2, close=12),
                bar(3, high=14, close=13)]
        result = state(rows)
        self.assertEqual((result.phase, result.streak, result.recovered), ('testing', 1, True))
        self.assertEqual(result.first_test_dt, rows[0]['available_dt'])

    def test_high_only_does_not_count_as_effective(self):
        """单根影线穿上沿不是工程口径的有效站住。"""
        self.assertEqual(state([bar(1, high=14, close=11)]).phase, 'constructing')

    def test_confirm_parameter_and_invalid_parameters(self):
        """确认根数可调但不得默认为原文定理。"""
        row = bar(1, high=14, close=13)
        self.assertEqual(state([row], confirm=1).phase, 'completed')
        for value in (0, -1, True, 1.5, '2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                state([], confirm=value)

    def test_success_and_failure_terminal_prefixes_do_not_rewrite(self):
        """首次终态保留, 后续相反价格不是重写旧构造的理由。"""
        success = [bar(1, high=14, close=13), bar(2, high=15, close=14)]
        failed = [bar(1, low=9)]
        self.assertEqual(state(success), state(success + [bar(3, low=5)]))
        self.assertEqual(state(failed), state(failed + [bar(2, high=14, close=13)]))

    def test_pre_confirmation_and_delayed_old_bars_do_not_confirm(self):
        """形成分型的K线及在确认前闭合但晚到的旧行不能算后续。"""
        old = bar(0, high=14, close=13, lag=10)
        self.assertEqual(state([old], confirm=1).phase, 'constructing')

    def test_available_gate_blocks_unclosed_and_late_data(self):
        """日期标签和收盘不是到达时间, 提前观察排除该行。"""
        row = bar(1, high=14, close=13, lag=10)
        for time in (row['dt'], row['closed_dt'], row['available_dt'] - timedelta(minutes=1)):
            self.assertEqual(state([row], confirm=1, as_of=time).phase, 'constructing')
        self.assertEqual(state([row], confirm=1, as_of=row['available_dt']).phase, 'completed')

    def test_future_prices_and_future_range_are_not_read(self):
        """未来OHLC缺失及未来区间NaN不影响当前有效前缀。"""
        row = bar(1, high=14, close=13)
        future = {key: value for key, value in bar(2).items()
                  if key in ('dt', 'closed_dt', 'available_dt')}
        self.assertEqual(state([row], as_of=row['available_dt']),
                         state([row, future], as_of=row['available_dt']))
        unknown = context(low=float('nan'), confirmed_dt=BASE + timedelta(days=3))
        self.assertEqual(state([row], unknown, as_of=row['available_dt']).phase, 'waiting')

    def test_time_and_delivery_order_errors(self):
        """混合时间、乱序到达和元数据缺失明确拒绝。"""
        with self.assertRaises(ValueError):
            state([], context(dt='2026-07-01'))
        rows = [bar(1, lag=1500), bar(2)]
        with self.assertRaises(ValueError):
            state(rows)
        row = bar(1); del row['closed_dt']
        with self.assertRaises(ValueError):
            state([row])

    def test_interval_identity_and_prices_validate(self):
        """无效区间、方向、周期和布尔价格不是有效分型输入。"""
        for changes in ({'low': 12}, {'low': 0}, {'high': float('inf')},
                        {'kind': 'buy1'}, {'level': ''}, {'low': True},
                        {'dt': BASE + timedelta(days=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                state([], context(**changes))

    def test_original_108_month_interval_boundaries(self):
        """课108的2284/2952边沿作独立范围例, 不冒充2008市场行情。"""
        monthly = context(low=2284., high=2952., level='month')
        touch = bar(1, low=2284, high=2900, close=2500)
        broken = bar(2, low=2283, high=2900, close=2500)
        self.assertEqual(state([touch], monthly).phase, 'constructing')
        self.assertEqual(state([touch, broken], monthly).phase, 'failed')

    def test_input_immutable_and_serialization(self):
        """输入不修改, 输出时间文本化便于归档。"""
        rows = [bar(1)]; original = dict(rows[0]); fractal = context()
        result = state(rows, fractal)
        self.assertEqual(rows[0], original)
        self.assertEqual(result.to_dict()['start_dt'], str(fractal.confirmed_dt))
        with self.assertRaises(AttributeError):
            fractal.high = 100


if __name__ == '__main__':
    unittest.main()
