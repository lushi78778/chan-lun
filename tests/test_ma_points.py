# -*- coding: utf-8 -*-
"""课11/12/15辅助点的独立差值盘面, 不由现有输出生成预期。"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import (alignment_series, avg_strength_state, find_kisses,
                  find_ma_points, ma_point_state, sma_series)


FIRST = [-10, -8, 1, -11, -10, 1, -12, -1, 0]
SECOND = [-2, -1, 2, 3, 1, 4]
BASE = datetime(2026, 1, 1)


def bars(diffs, mirror=False):
    """1/2均线差等于相邻收盘差一半, 可手算吻及面积。"""
    values = [500.]
    for diff in diffs:
        values.append(values[-1] + 2 * diff)
    if mirror:
        values = [1000 - price for price in values]
    return [dict(dt=BASE + timedelta(days=i), open=price, high=price+1,
                 low=price-1, close=price, volume=1.,
                 closed_dt=BASE + timedelta(days=i, hours=15),
                 available_dt=BASE + timedelta(days=i, hours=15, minutes=5))
            for i, price in enumerate(values)]


def points(rows, **kwargs):
    return find_ma_points(rows, rows[-1]['available_dt'] if rows else BASE,
                          short_period=1, long_period=2, **kwargs)


# 课11/12/15工程合同的真实整数审计表, 独立SMA/区间算术先于库比较。
# 所有索引从各冻结原始窗口0起, 不沿用其原笔/XD标签或窗口前暖机。
# 差值单位0.0001: 2*sum(close_ticks[-5:])-sum(close_ticks[-10:])。
# (reference_start, reference_end, current_start, current_end, 两段绝对面积,
#  面积减弱, 平均力度减弱)。这里各行的价格高低点均向上, 最近吻已了结。
REAL_FIRST = (
    ('real_strict_trend_minute.json', '159915-60m-20240101-20250331',
     (887, 897, 2, 'wet'), (
         (943, 945, 947, 956, 78, 4029, False, False),
         (962, 965, 973, 979, 87, 1089, False, False),
         (993, 996, 1004, 1015, 229, 3788, False, False),
         (1004, 1015, 1020, 1025, 3788, 1729, True, True),
         (1020, 1025, 1030, 1035, 1729, 1692, True, True),
         (1089, 1094, 1097, 1108, 706, 1571, False, False),
         (1097, 1108, 1121, 1128, 1571, 1012, True, True),
         (1121, 1128, 1130, 1135, 1012, 794, True, False),
         (1160, 1162, 1170, 1176, 39, 468, False, False),
         (1185, 1189, 1192, 1192, 188, 3, True, True),
         (1264, 1265, 1267, 1279, 20, 1528, False, False),
         (1267, 1279, 1286, 1290, 1528, 266, True, True),
         (1294, 1297, 1308, 1319, 203, 2629, False, False),
         (1308, 1319, 1329, 1345, 2629, 1616, True, True),
         (1329, 1345, 1354, 1369, 1616, 1693, False, False),
         (1395, 1395, 1402, 1413, 47, 1041, False, False),
         (1425, 1430, 1438, 1444, 250, 1203, False, False))),
    ('real_third_point_xd_margin0.json', '512880-5m-20260201-20260724',
     (103, 139, 2, 'wet'), (
         (136, 146, 170, 186, 288, 319, False, True),)),
)

# (吻前腿起, 峰, 了结, 体位, 吻种); 日线两侧不是镜像行情。
REAL_SECOND = (
    ('real_strict_trend.json', '159915-day-20180101-20191231', (
        (97, 100, 112, 'down', 'lip'),
        (267, 271, 278, 'up', 'fly'))),
    ('real_strict_trend_minute.json', '159915-60m-20240101-20250331', (
        (126, 130, 887, 'up', 'wet'),)),
)

# 月初起点固定网格的不同买侧锚点, 不将同锚点的多个起点计为独立样本。
# 仍读取既有原始行; :: 后是显式观察起点, 不自动带窗口前暖机。
REAL_BUY_FIRST = (
    ('real_f1_originals.json', '512880-day-2016-11-09-2017-08-30::2017-01-01',
     (72, 81, 3, 'lip'), (67, 87, 92, 95, 1764, 140, True, True)),
    ('real_causal_formation.json', '588000-30m-20220801-20230501::2022-11-01',
     (302, 312, 2, 'lip'), (298, 335, 339, 352, 1257, 519, True, False)),
    ('real_strict_trend_5m.json', '518880-5m-20260501-20260724::2026-06-01',
     (249, 347, 2, 'wet'), (334, 368, 388, 412, 8924, 7685, True, False)),
)


def real_bars(filename, key):
    """复用包内原始行; 日线15:05/分钟结束+1分仅为到达测试约定。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    parent, separator, start = key.partition('::')
    with open(path, encoding='utf-8') as stream:
        case = next(c for c in json.load(stream)['cases'] if c['id'] == parent)
    rows = []
    for raw in case['raw_rows']:
        if separator and raw['dt'][:10] < start:
            continue
        if raw['adj_factor'] != 1:
            raise ValueError('本表只审计恒1因子, 不自动重算报价')
        dt = datetime.strptime(raw['dt'], '%Y-%m-%d %H:%M:%S')
        daily = '-day-' in key
        closed = dt + timedelta(hours=15) if daily else dt
        rows.append(dict(dt=dt, open=raw['open'], high=raw['high'], low=raw['low'],
                         close=raw['close'], volume=raw['vol'], closed_dt=closed,
                         available_dt=closed + timedelta(minutes=5 if daily else 1)))
    return rows


def integer_diffs(rows):
    """直接整数滑窗, 不调用sma_series/ma_areas/find_ma_bc。"""
    closes = [round(row['close'] * 1000) for row in rows]
    return [None if i < 9 else
            2 * sum(closes[i-4:i+1]) - sum(closes[i-9:i+1])
            for i in range(len(rows))]


class TestMaEvidenceBoundaries(unittest.TestCase):
    """课12局部差异的工程证据, 不将派生差值当作完整原图点位标签。"""

    # 600519, 固定2006-05-25..11-30窗的第28..84行(07-04..09-20)。
    # 原CSV SHA256: 513aa257b143ce397a7fc39733c394b02640b94b4a2ddebee5ff3a1d7f64ba7e
    # 在调用库前直接以收盘分价冻结: 2*sum(last5)-sum(last10), 单位0.001元。
    # 这里只保留派生差值; 不复制原OHLC/量, 不继承窗前吻计数或确认日。
    DIFFS = (-27, -209, -484, -705, -790, -819, -945, -1004,
             -1001, -841, -659, -455, -292, -164, -12, 281, 636,
             863, 984, 628, 170, -375, -884, -1272, -1215, -1160,
             -941, -518, -98, 211, 455, 592, 513, 379, 270, 286,
             115, 77, 63, -5, -65, 48, 174, 286, 446, 327, 285,
             149, -15, -243, -285, -423, -288, -89, 181, 556, 991)

    def test_sign_crossing_does_not_confirm_the_host_regime_flip(self):
        """瞬时上穿不重置吻计数; 592<1272/2, 后到991才跨默认门槛。"""
        # 共用整数平移使差值精确, 仅验证吻几何, 不用于pre_gain或价格趋势。
        short = [10000 + d for d in self.DIFFS]
        long = [10000] * len(short)
        alignment = alignment_series(short, long)
        self.assertTrue(all(a == 'up' for a in alignment[29:39]))  # 08-14..25
        self.assertEqual(max(self.DIFFS[24:56]), 592)
        self.assertLess(2 * 592, 1272)
        self.assertLess(2 * self.DIFFS[55], 1272)  # 09-19: 556
        self.assertGreaterEqual(2 * self.DIFFS[56], 1272)  # 09-20: 991
        expected = [(7, 16, 'down'), (18, 22, 'up'), (23, 56, 'down')]
        previous = []
        for count in range(1, len(short)+1):
            with self.subTest(count=count):
                events = find_kisses(short[:count], long[:count])
                closed = [e for e in events if not e.open]
                self.assertEqual([(e.start_idx, e.end_idx, e.direction) for e in closed],
                                 [w for w in expected if w[1] < count])
                self.assertTrue(all(e.kiss_index == 1 and e.kind == 'wet' and
                                    not e.resumed for e in closed))
                payload = [e.to_dict() for e in closed]
                self.assertEqual(payload[:len(previous)], previous)
                previous = payload
                if count == 25:  # 08-07回撤太浅, 不返回开放吻, 也不转化。
                    self.assertLess(5 * (1272-1215), 1272)
                    self.assertEqual(len(events), 2)
                    self.assertTrue(all(not e.open for e in events))
                if count == 53:  # 09-14已有足够深的回撤, 吻仍未转化。
                    current = events[-1]
                    self.assertEqual((current.start_idx, current.end_idx), (23, count-1))
                    self.assertEqual((current.direction, current.kiss_index,
                                      current.open, current.resumed), ('down', 1, True, False))

    def test_nearest_same_sign_area_and_shortening_are_separate_conditions(self):
        """距离缩短不能补回平均力度; 不能跳过最近同向段挑有利参照。"""
        # (观察行, 前段起止, 当前段起止, 两段绝对面积); 均为本表局部序号。
        table = ((24, 0, 14, 21, 24, 8407, 3746),
                 (52, 39, 40, 48, 52, 70, 1254))
        for stop, a, b, c, d, before, current in table:
            with self.subTest(stop=stop):
                self.assertEqual(-sum(self.DIFFS[a:b+1]), before)
                self.assertEqual(-sum(self.DIFFS[c:d+1]), current)
                self.assertTrue(all(x < 0 for x in self.DIFFS[a:b+1]+self.DIFFS[c:d+1]))
                self.assertTrue(all(x > 0 for x in self.DIFFS[b+1:c]))
                self.assertGreater(current*(b-a+1), before*(d-c+1))
                self.assertLess(abs(self.DIFFS[stop]), abs(self.DIFFS[stop-1]))
                state = avg_strength_state([10000+x for x in self.DIFFS[:stop+1]],
                                           [10000]*(stop+1))
                self.assertEqual(state.direction, 'down')
                self.assertEqual((state.prev_area.start_idx, state.prev_area.end_idx), (a, b))
                self.assertEqual((state.open_area.start_idx, state.open_area.end_idx), (c, d))
                self.assertTrue(state.prev_area.closed)
                self.assertFalse(state.open_area.closed)
                self.assertAlmostEqual(state.avg_prev, -before / float(b-a+1))
                self.assertAlmostEqual(state.avg_cur, -current / float(d-c+1))
                self.assertFalse(state.forming_weak)
                self.assertTrue(state.stretch_shortening)


class TestRealMaPoints(unittest.TestCase):
    """真实报价的独立工程条件审计, 不宣称茅台原图或精确理论点位。"""

    def first_points(self, rows, use_avg=False, as_of=None):
        events = find_ma_points(rows, rows[-1]['available_dt'] if as_of is None else as_of,
                                use_avg=use_avg)
        return [e for e in events if e.pattern == 'post_kiss_divergence']

    def test_real_first_area_and_average_tables(self):
        """60m面积独有一例、5m平均独有一例; 两种量纲不能互相代替。"""
        for filename, key, kiss, table in REAL_FIRST:
            rows = real_bars(filename, key)
            diffs = integer_diffs(rows)
            indices = {r['dt']: i for i, r in enumerate(rows)}
            for a, b, c, d, before, current, area_weak, avg_weak in table:
                with self.subTest(key=key, current=(c, d)):
                    self.assertEqual(sum(diffs[a:b+1]), before)
                    self.assertEqual(sum(diffs[c:d+1]), current)
                    self.assertTrue(all(x > 0 for x in diffs[a:b+1] + diffs[c:d+1]))
                    self.assertLessEqual(diffs[b+1], 0)
                    self.assertLessEqual(diffs[d+1], 0)
                    self.assertFalse(any(x > 0 for x in diffs[b+1:c]))
                    self.assertEqual(current < before, area_weak)
                    self.assertEqual(current * (b-a+1) < before * (d-c+1), avg_weak)
                    for price in ('low', 'high'):
                        pick = min if price == 'low' else max
                        self.assertGreater(pick(r[price] for r in rows[c:d+1]),
                                           pick(r[price] for r in rows[a:b+1]))
            for average in (False, True):
                expected = [t for t in table if t[7 if average else 6]]
                actual = self.first_points(rows, average)
                self.assertEqual([(indices[e.reference_start_dt], indices[e.reference_end_dt],
                                   indices[e.evidence_start_dt], indices[e.evidence_end_dt])
                                  for e in actual], [t[:4] for t in expected])
                for event, (a, b, c, d, before, current, _, _) in zip(actual, expected):
                    self.assertEqual(event.kind, 'ma_sell1_candidate')
                    self.assertEqual((indices[event.kiss_start_dt], indices[event.kiss_end_dt],
                                      event.kiss_index, event.kiss_kind), kiss)
                    self.assertAlmostEqual(event.reference_strength,
                                           before / 10000. / (b-a+1 if average else 1))
                    self.assertAlmostEqual(event.current_strength,
                                           current / 10000. / (d-c+1 if average else 1))
                    extreme = max(rows[c:d+1], key=lambda r: r['high'])
                    self.assertEqual((event.dt, event.price), (extreme['dt'], extreme['high']))
                    self.assertEqual(event.confirmed_dt, rows[d+1]['available_dt'])
                    self.assertFalse(event.last_kiss_proven)

    def test_real_buy_first_conditions_and_origin_are_explicit(self):
        """三个实际买侧锚点; 月初重新暖机, 不套用原窗口的吻状态。"""
        for filename, key, kiss, table in REAL_BUY_FIRST:
            rows = real_bars(filename, key)
            a, b, c, d, prior, current, weak, avg_weak = table
            diffs = integer_diffs(rows)
            self.assertEqual(-sum(diffs[a:b+1]), prior)
            self.assertEqual(-sum(diffs[c:d+1]), current)
            self.assertTrue(all(x < 0 for x in diffs[a:b+1] + diffs[c:d+1]))
            self.assertGreaterEqual(diffs[b+1], 0)
            self.assertGreaterEqual(diffs[d+1], 0)
            self.assertTrue(all(x >= 0 for x in diffs[b+1:c]))
            self.assertEqual(current < prior, weak)
            self.assertEqual(current * (b-a+1) < prior * (d-c+1), avg_weak)
            for field, pick in (('low', min), ('high', max)):
                self.assertLess(pick(r[field] for r in rows[c:d+1]),
                                pick(r[field] for r in rows[a:b+1]))
            for average, expected in ((False, weak), (True, avg_weak)):
                events = [e for e in self.first_points(rows, average)
                          if e.kind == 'ma_buy1_candidate']
                self.assertEqual(len(events), int(expected))
                if not events:
                    continue
                event = events[0]
                self.assertEqual((event.reference_start_dt, event.reference_end_dt,
                                  event.evidence_start_dt, event.evidence_end_dt),
                                 tuple(rows[i]['dt'] for i in (a, b, c, d)))
                self.assertEqual((event.kiss_start_dt, event.kiss_end_dt, event.kiss_index,
                                  event.kiss_kind), (rows[kiss[0]]['dt'], rows[kiss[1]]['dt'],
                                                     kiss[2], kiss[3]))
                self.assertAlmostEqual(event.reference_strength, prior / 10000. / (b-a+1 if average else 1))
                self.assertAlmostEqual(event.current_strength, current / 10000. / (d-c+1 if average else 1))
                extreme = min(rows[c:d+1], key=lambda r: r['low'])
                self.assertEqual((event.dt, event.price), (extreme['dt'], extreme['low']))
                self.assertEqual(event.confirmed_dt, rows[d+1]['available_dt'])
            # 原始父窗口没有该买侧条件。起点改变属于输入合同变化, 不是修复算法。
            parent = real_bars(filename, key.partition('::')[0])
            self.assertFalse(any(e.kind == 'ma_buy1_candidate' and e.evidence_start_dt == rows[c]['dt']
                                 for e in self.first_points(parent)))

    def test_real_buy_kiss_witnesses(self):
        """第三次唇吻和第二次唇/湿吻, 同体位峰/恢复及半峰转化门槛。"""
        witnesses = (((38, 53, 81), (53, 70, 91), (72, 81, 108)),
                     ((275, 302, 55), (302, 312, 59)),
                     ((102, 247, 585), (249, 347, 1233)))
        for (filename, key, kiss, _), sequence in zip(REAL_BUY_FIRST, witnesses):
            rows = real_bars(filename, key)
            diffs = integer_diffs(rows)
            for number, (peak, end, value) in enumerate(sequence, 1):
                self.assertEqual(diffs[peak], -value)
                self.assertTrue(all(-value < -2*x <= 2*value for x in diffs[peak+1:end]))
                self.assertLess(diffs[end], -value)
                self.assertGreaterEqual(5 * (value+max(diffs[peak+1:end+1])), value)
                closes = [r['close'] for r in rows[:end+1]]
                event = [e for e in find_kisses(sma_series(closes, 5), sma_series(closes, 10))
                         if not e.open][-1]
                self.assertEqual((event.start_idx, event.end_idx, event.direction, event.resumed,
                                  event.kiss_index), (peak, end, 'down', True, number))
            self.assertEqual((event.kiss_index, event.kind), (kiss[2], kiss[3]))

    def test_real_buy_confirmation_prefixes_and_future_poison(self):
        """买侧同样不能在封闭行实际到达前使用; 相邻前缀及未来坏字段隔离。"""
        for filename, key, _, table in REAL_BUY_FIRST:
            rows = real_bars(filename, key)
            start, end = table[2:4]
            for average, expected in ((False, table[6]), (True, table[7])):
                for stop in range(end-1, end+3):
                    now = rows[stop]['available_dt']
                    visible = rows[:stop+1]
                    future = [{k: r[k] for k in ('dt', 'closed_dt', 'available_dt')}
                              for r in rows[stop+1:]]
                    actual = self.first_points(visible, average)
                    self.assertEqual(actual, self.first_points(rows, average, now))
                    self.assertEqual(actual, self.first_points(visible+future, average, now))
                    self.assertEqual(any(e.kind == 'ma_buy1_candidate' and
                                         e.evidence_start_dt == rows[start]['dt'] for e in actual),
                                     expected and stop > end)
                before = rows[end+1]['available_dt']-timedelta(microseconds=1)
                self.assertFalse(any(e.kind == 'ma_buy1_candidate' and e.evidence_start_dt == rows[start]['dt']
                                     for e in self.first_points(rows, average, before)))

    def test_real_combined_warning_has_both_sides_and_can_disappear(self):
        """独立价格/吻证据与即时平均力度组合; 快照不成为永久已确认点。"""
        buy_file, buy_key, _, _ = REAL_BUY_FIRST[0]
        sell_file, sell_key, _, _ = REAL_FIRST[0]
        cases = ((buy_file, buy_key, 94, 'ma_buy1_warning', 1764/21/10000., 128/3/10000.),
                 (buy_file, buy_key, 95, 'ma_buy1_warning', 1764/21/10000., 140/4/10000.),
                 (sell_file, sell_key, 1025, 'ma_sell1_warning', 3788/12/10000., 1729/6/10000.))
        for filename, key, end, kind, reference, current in cases:
            rows = real_bars(filename, key)
            now = rows[end]['available_dt']
            actual = ma_point_state(rows, now)
            self.assertEqual((actual.status, actual.kind, actual.reasons), ('warning', kind, ()))
            self.assertAlmostEqual(actual.reference_strength, reference)
            self.assertAlmostEqual(actual.current_strength, current)
            self.assertEqual(actual.observed_dt, now)
            self.assertEqual(actual.evidence_end_dt, rows[end]['dt'])
            self.assertEqual(actual, ma_point_state(rows[:end+1], now))
            future = [{k: r[k] for k in ('dt', 'closed_dt', 'available_dt')} for r in rows[end+1:]]
            self.assertEqual(actual, ma_point_state(rows[:end+1]+future, now))
            before = now-timedelta(microseconds=1)
            self.assertEqual(ma_point_state(rows, before), ma_point_state(rows[:end], before))
            self.assertFalse(any(e.evidence_start_dt == actual.evidence_start_dt
                                 for e in self.first_points(rows[:end+1])))
        # 已有独立表中1135距离缩短但平均力度增强; 组合不能只读距离产生预警。
        rows = real_bars(sell_file, sell_key)
        state = ma_point_state(rows, rows[1135]['available_dt'])
        self.assertEqual(state.status, 'no_warning')
        self.assertIn('average_not_weaker', state.reasons)
        self.assertTrue(state.stretch_shortening)


    def test_real_kiss_witnesses_precede_the_area(self):
        """冻结两次同体位中继的峰/了结; 第二次不由未来吻回填。"""
        witnesses = (((130, 887, 454), (887, 897, 476)),
                     ((85, 102, 16), (103, 139, 26)))
        for (filename, key, _, _), pair in zip(REAL_FIRST, witnesses):
            rows = real_bars(filename, key)
            diffs = integer_diffs(rows)
            for peak, end, value in pair:
                self.assertEqual(diffs[peak], value)
                self.assertTrue(all(-value < 2*x <= 2*value for x in diffs[peak+1:end]))
                self.assertGreater(diffs[end], value)
                self.assertGreaterEqual(5 * (value-min(diffs[peak+1:end+1])), value)
                short = sma_series([r['close'] for r in rows[:end+1]], 5)
                long = sma_series([r['close'] for r in rows[:end+1]], 10)
                events = [e for e in find_kisses(short, long) if not e.open]
                event = events[-1]
                self.assertEqual((event.start_idx, event.end_idx, event.kind, event.resumed),
                                 (peak, end, 'wet', True))
            self.assertEqual(event.kiss_index, 2)

    def test_real_second_continuation_both_sides_and_three_kiss_kinds(self):
        """独立日线买卖两侧与60m中继, 前腿涨幅/量比直接复算。"""
        for filename, key, table in REAL_SECOND:
            rows = real_bars(filename, key)
            closes = [round(r['close'] * 1000) for r in rows]
            indices = {r['dt']: i for i, r in enumerate(rows)}
            actual = [e for e in find_ma_points(rows, rows[-1]['available_dt'])
                      if e.pattern == 'first_continuation']
            self.assertEqual([(indices[e.kiss_start_dt], indices[e.kiss_end_dt], e.kiss_kind)
                              for e in actual], [(t[1], t[2], t[4]) for t in table])
            for event, (leg, peak, end, direction, kind) in zip(actual, table):
                sign = 1 if direction == 'up' else -1
                gain = sign * 2 * (sum(closes[peak-4:peak+1])-sum(closes[leg-4:leg+1])) / \
                    sum(closes[leg-9:leg+1])
                mean_leg = sum(r['volume'] for r in rows[leg:peak+1]) / (peak-leg+1)
                mean_prior = sum(r['volume'] for r in rows[leg-10:leg]) / 10
                self.assertGreaterEqual(gain, .02)
                self.assertLessEqual(mean_leg/mean_prior, 2)
                self.assertAlmostEqual(event.pre_gain, gain)
                self.assertAlmostEqual(event.volume_ratio, mean_leg/mean_prior)
                self.assertEqual(event.kind, 'ma_buy2_candidate' if sign > 0 else 'ma_sell2_candidate')
                self.assertEqual((event.kiss_index, event.kiss_kind), (1, kind))
                self.assertEqual((event.evidence_start_dt, event.evidence_end_dt),
                                 (rows[peak+1]['dt'], rows[end]['dt']))
                price = 'low' if sign > 0 else 'high'
                extreme = (min if sign > 0 else max)(rows[peak+1:end+1], key=lambda r: r[price])
                self.assertEqual((event.dt, event.price), (extreme['dt'], extreme[price]))
                self.assertEqual(event.confirmed_dt, rows[end]['available_dt'])

    def test_real_confirmation_prefixes_future_poison_and_history(self):
        """逐确认相邻原始前缀及闭合/到达边界; 历史事件不随后缀修订。"""
        cases = [(filename, key, sorted(set(t[3]+1 for t in table)))
                 for filename, key, _, table in REAL_FIRST]
        cases += [(filename, key, [t[2] for t in table])
                  for filename, key, table in REAL_SECOND]
        for filename, key, confirmations in cases:
            rows = real_bars(filename, key)
            stops = sorted(set(i for c in confirmations for i in (c-1, c, c+1)))
            for average in (False, True):
                previous = set()
                for end in stops:
                    now = rows[end]['available_dt']
                    visible = rows[:end+1]
                    actual = find_ma_points(visible, now, use_avg=average)
                    future = [{k: r[k] for k in ('dt', 'closed_dt', 'available_dt')}
                              for r in rows[end+1:]]
                    self.assertEqual(actual, find_ma_points(visible+future, now, use_avg=average))
                    self.assertEqual(actual, find_ma_points(rows, now, use_avg=average))
                    self.assertTrue(previous.issubset(set(actual)))
                    previous = set(actual)
                    for before in (rows[end]['closed_dt']-timedelta(microseconds=1),
                                   rows[end]['available_dt']-timedelta(microseconds=1)):
                        self.assertEqual(find_ma_points(rows, before, use_avg=average),
                                         find_ma_points(rows[:end], before, use_avg=average))

    def test_real_delayed_confirmation_is_not_the_price_endpoint(self):
        """60m已封闭后仍等实际到达; 延迟两日不回填原确认时刻。"""
        filename, key, _, _ = REAL_FIRST[0]
        rows = real_bars(filename, key)
        end, confirming = 1025, 1026
        event = next(e for e in self.first_points(rows)
                     if e.evidence_end_dt == rows[end]['dt'])
        delayed = [dict(r) for r in rows]
        for row in delayed[confirming:]:
            row['available_dt'] += timedelta(days=2)
        original = rows[confirming]['available_dt']
        self.assertFalse(any(e.evidence_end_dt == event.evidence_end_dt
                             for e in self.first_points(delayed, as_of=original)))
        arrived = delayed[confirming]['available_dt']
        late = next(e for e in self.first_points(delayed, as_of=arrived)
                    if e.evidence_end_dt == event.evidence_end_dt)
        self.assertEqual((late.dt, late.price), (event.dt, event.price))
        self.assertEqual(late.confirmed_dt, arrived)
        self.assertGreater(late.confirmed_dt, event.confirmed_dt)

    def test_real_instant_average_warning_can_be_revoked(self):
        """平均预警从弱转强而撤销, 距离缩短不能补回平均力度条件。"""
        filename, key, _, _ = REAL_FIRST[0]
        rows = real_bars(filename, key)
        # (观察行, 当下面积, 根数, 前同向面积, 根数, 距离, 缩短, 酝酿弱)
        table = ((1129, 17, 1, 743, 12, -17, True, True),
                 (1130, 35, 1, 1012, 8, 35, False, True),
                 (1131, 85, 2, 1012, 8, 50, False, True),
                 (1132, 236, 3, 1012, 8, 151, False, True),
                 (1133, 462, 4, 1012, 8, 226, False, True),
                 (1134, 721, 5, 1012, 8, 259, False, False),
                 (1135, 794, 6, 1012, 8, 73, True, False),
                 (1136, 13, 1, 17, 1, -13, True, True),
                 (1137, 119, 2, 17, 1, -106, False, False))
        for end, area, count, prior, prior_count, stretch, shortening, weak in table:
            closes = [r['close'] for r in rows[:end+1]]
            state = avg_strength_state(sma_series(closes, 5), sma_series(closes, 10))
            self.assertEqual(state.direction, 'up' if stretch > 0 else 'down')
            sign = 1 if stretch > 0 else -1
            self.assertAlmostEqual(state.avg_cur, sign * area / count / 10000.)
            self.assertAlmostEqual(state.avg_prev, sign * prior / prior_count / 10000.)
            self.assertAlmostEqual(state.stretch, stretch / 10000.)
            self.assertEqual((state.stretch_shortening, state.forming_weak), (shortening, weak))
            area_events = self.first_points(rows[:end+1])
            avg_events = self.first_points(rows[:end+1], True)
            self.assertEqual(any(e.evidence_start_dt == rows[1130]['dt'] for e in area_events), end >= 1136)
            self.assertFalse(any(e.evidence_start_dt == rows[1130]['dt'] for e in avg_events))


class TestMaPointState(unittest.TestCase):
    def state(self, rows, **kwargs):
        return ma_point_state(rows, rows[-1]['available_dt'] if rows else BASE,
                              short_period=1, long_period=2, **kwargs)

    def test_open_weak_and_shortening_has_warning_on_both_sides(self):
        """第二次吻后开放面积12+1, 均值6.5<10.5且距离缩短, 非封闭候选。"""
        for mirror, direction, kind in ((False, 'down', 'ma_buy1_warning'),
                                         (True, 'up', 'ma_sell1_warning')):
            rows = bars(FIRST[:-1], mirror=mirror)
            state = self.state(rows)
            self.assertEqual((state.status, state.direction, state.kind, state.reasons),
                             ('warning', direction, kind, ()))
            self.assertEqual((state.reference_strength, state.current_strength), (10.5, 6.5))
            self.assertEqual((state.kiss_index, state.kiss_kind), (2, 'wet'))
            self.assertEqual(state.observed_dt, rows[-1]['available_dt'])
            self.assertEqual(points(rows), [])
            self.assertFalse(state.last_kiss_proven)
            for name in ('dt', 'price', 'confirmed_dt'):
                self.assertFalse(hasattr(state, name))

    def test_warning_revokes_and_immutable_snapshot_is_preserved(self):
        """未封闭末段继续扩展可转强, 已取快照保持, 不虚构已确认记录。"""
        rows = bars(FIRST[:-1])
        old = self.state(rows)
        later = self.state(bars(FIRST[:-1]+[-2, -50]))
        self.assertEqual((old.status, old.current_strength), ('warning', 6.5))
        self.assertEqual(later.status, 'no_warning')
        self.assertEqual(later.kind, None)
        self.assertIn('average_not_weaker', later.reasons)
        self.assertIn('stretch_not_shortening', later.reasons)
        with self.assertRaises(AttributeError):
            old.status = 'no_warning'

    def test_closed_touch_and_equal_average_do_not_warn(self):
        """触零已封闭与平均力度相等均不满足即时严格减弱条件。"""
        closed = self.state(bars(FIRST))
        self.assertEqual(closed.status, 'no_warning')
        self.assertIn('area_closed', closed.reasons)
        equal = self.state(bars(FIRST[:6]+[-12, -9]))
        self.assertEqual(equal.status, 'no_warning')
        self.assertIn('average_not_weaker', equal.reasons)
        self.assertEqual(equal.reference_strength, equal.current_strength)

    def test_price_and_latest_kiss_conditions_remain_required(self):
        """价格两极值、第二次中继及体位都需满足, 不挑更早有利吻。"""
        rows = bars(FIRST[:-1]); rows[7]['high'] = 500.
        self.assertIn('price_not_trending', self.state(rows).reasons)
        first = self.state(bars([-10, -8, 1, -11, -1]))
        self.assertIn('kiss_count_below_two', first.reasons)
        wrong = self.state(bars(FIRST[:-1]+[2, 1]))
        self.assertIn('kiss_not_continuation', wrong.reasons)
        self.assertNotEqual(wrong.status, 'warning')

    def test_missing_visible_history_and_sma_are_insufficient(self):
        """空、未来、暖机、恒零、缺前同向面积/前置吻均明确缺证据。"""
        self.assertEqual(self.state([]).reasons, ('no_visible_bars',))
        future = [{'dt': BASE, 'closed_dt': BASE+timedelta(days=1),
                   'available_dt': BASE+timedelta(days=2)}]
        self.assertEqual(ma_point_state(future, BASE).reasons, ('no_visible_bars',))
        self.assertEqual(ma_point_state(bars([1]), BASE+timedelta(days=3)).reasons,
                         ('ma_unavailable',))
        self.assertEqual(self.state(bars([0, 0, 0])).reasons, ('ma_unavailable',))
        state = self.state(bars([-3, -2, -1]))
        self.assertEqual(state.status, 'insufficient_evidence')
        self.assertIn('reference_missing', state.reasons)
        self.assertIn('kiss_missing', state.reasons)

    def test_late_arrival_and_future_prices_are_not_read(self):
        """新观测先截断, 同一已见前缀状态与未来缺字段/迟到无关。"""
        rows = bars(FIRST[:-1])
        expected = self.state(rows)
        poison = [dict(dt=BASE+timedelta(days=30), closed_dt=BASE+timedelta(days=31),
                       available_dt=BASE+timedelta(days=32))]
        self.assertEqual(expected, ma_point_state(rows+poison, rows[-1]['available_dt'], 1, 2))
        delayed = [dict(r) for r in rows]
        delayed[-1]['available_dt'] += timedelta(days=2)
        self.assertEqual(ma_point_state(delayed, rows[-1]['available_dt'], 1, 2), self.state(rows[:-1]))
        late = self.state(delayed)
        self.assertEqual(late.status, 'warning')
        self.assertEqual(late.observed_dt, delayed[-1]['available_dt'])
        self.assertEqual(late.evidence_end_dt, expected.evidence_end_dt)

    def test_parameters_invalid_bars_and_delivery_order_are_rejected(self):
        """新入口沿用周期/吻阈值、原始OHLC与实际到达非降序合同。"""
        rows = bars(FIRST[:-1])
        for kwargs in ({'short_period':True}, {'short_period':2, 'long_period':2},
                       {'proximity':float('nan')}, {'min_depth':2}, {'flip_confirm':0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ma_point_state(rows, rows[-1]['available_dt'], **kwargs)
        invalid = [dict(r) for r in rows]; invalid[0]['high'] = 1
        with self.assertRaises(ValueError): self.state(invalid)
        invalid = [dict(r) for r in rows]; invalid[0]['available_dt'] = rows[-1]['available_dt']
        with self.assertRaises(ValueError): self.state(invalid)
        invalid = [dict(r) for r in rows]; del invalid[0]['closed_dt']
        with self.assertRaises(ValueError): self.state(invalid)

    def test_nonprefix_arrival_does_not_rebase_warning_history(self):
        """课11/12/15工程时间: 首行或内部迟到不能跳行重算吻和平均力度。"""
        for mirror in (False, True):
            rows = bars(FIRST[:-1], mirror)
            now = rows[-1]['available_dt']
            self.assertEqual(self.state(rows).status, 'warning')
            for gap in (0, 3, 6):
                for metadata_only in (False, True):
                    with self.subTest(mirror=mirror, gap=gap, metadata_only=metadata_only):
                        broken = [dict(r) for r in rows]
                        broken[gap]['available_dt'] = now + timedelta(days=1)
                        if metadata_only:
                            broken[gap] = {k: broken[gap][k] for k in
                                           ('dt', 'closed_dt', 'available_dt')}
                        untouched = [dict(r) for r in broken]
                        with self.assertRaises(ValueError):
                            ma_point_state(broken, now, 1, 2)
                        self.assertEqual(broken, untouched)

    def test_serialization_input_and_volume_boundary(self):
        """快照序列化独立, 不回写输入; 一类预警无二类量比过滤。"""
        rows = bars(FIRST[:-1]); original = [dict(r) for r in rows]
        expected = self.state(rows)
        payload = expected.to_dict()
        self.assertEqual(payload['observed_dt'], str(expected.observed_dt))
        self.assertEqual(payload['reasons'], [])
        self.assertEqual(payload['kind'], 'ma_buy1_warning')
        payload['reasons'].append('changed')
        self.assertEqual(expected.reasons, ())
        json.dumps(payload)
        self.assertEqual(rows, original)
        for row in rows: row['volume'] = 0
        self.assertEqual(self.state(rows), expected)


class TestMaPoints(unittest.TestCase):
    def test_nonprefix_arrival_cannot_remove_closed_candidate(self):
        """已了结候选的历史坐标不能因中间行情未到而被静默压缩。"""
        for mirror in (False, True):
            rows = bars(FIRST, mirror)
            now = rows[-1]['available_dt']
            for use_avg in (False, True):
                self.assertEqual(len(points(rows, use_avg=use_avg)), 1)
                for gap in (0, 3, 6):
                    with self.subTest(mirror=mirror, use_avg=use_avg, gap=gap):
                        broken = [dict(r) for r in rows]
                        broken[gap] = {k: broken[gap][k] for k in
                                       ('dt', 'closed_dt', 'available_dt')}
                        broken[gap]['available_dt'] = now + timedelta(days=1)
                        untouched = [dict(r) for r in broken]
                        with self.assertRaises(ValueError):
                            find_ma_points(broken, now, 1, 2, use_avg=use_avg)
                        self.assertEqual(broken, untouched)

    def test_explicit_batch_snapshot_and_unavailable_suffix_remain_valid(self):
        """连续尾部延迟仍按原前缀计算; 显式同批可用快照保留价格与了结时刻。"""
        for mirror in (False, True):
            for diffs, state_mode in ((FIRST, False), (FIRST[:-1], True)):
                rows = bars(diffs, mirror)
                now = rows[-1]['available_dt']
                batch = now + timedelta(days=2)
                delayed = [dict(r) for r in rows]
                for row in delayed[3:]:
                    row['available_dt'] = batch
                fn = ma_point_state if state_mode else find_ma_points
                self.assertEqual(fn(delayed, now, 1, 2), fn(rows[:3], now, 1, 2))
                original = fn(rows, now, 1, 2)
                rebuilt = fn(delayed, batch, 1, 2)
                if state_mode:
                    self.assertEqual(rebuilt._replace(observed_dt=now), original)
                    self.assertEqual(rebuilt.observed_dt, batch)
                else:
                    self.assertEqual(len(rebuilt), 1)
                    self.assertEqual(rebuilt[0]._replace(confirmed_dt=now), original[0])
                    self.assertEqual(rebuilt[0].confirmed_dt, batch)
                self.assertEqual(delayed[0], rows[0])

    def test_closed_area_buy1_after_second_wet_kiss(self):
        """第二湿吻后下降腿21->13, 两个价格极值均下移。"""
        rows = bars(FIRST)
        event = points(rows)[0]
        self.assertEqual(event.kind, 'ma_buy1_candidate')
        self.assertEqual((event.reference_strength, event.current_strength), (21., 13.))
        self.assertEqual((event.kiss_index, event.kiss_kind), (2, 'wet'))
        self.assertEqual((event.dt, event.price), (BASE+timedelta(days=8), 399.))
        self.assertEqual(event.confirmed_dt, rows[9]['available_dt'])
        self.assertFalse(event.to_dict()['last_kiss_proven'])

    def test_closed_area_sell1_mirror(self):
        """上涨力度衰减与价格新高为卖端镜像, 不反转买端标签。"""
        event = points(bars(FIRST, mirror=True))[0]
        self.assertEqual((event.kind, event.price), ('ma_sell1_candidate', 601.))

    def test_unclosed_area_is_not_confirmed_at_extreme(self):
        """面积末端不是可见确认时刻, 必须等后一相交行。"""
        rows = bars(FIRST)
        self.assertEqual(points(rows[:-1]), [])
        self.assertEqual(find_ma_points(rows, rows[-1]['closed_dt'], 1, 2), [])

    def test_first_kiss_cannot_be_last_kiss_candidate(self):
        """趋势初次湿吻后虽力度减弱, 课12不称最后缠绕。"""
        self.assertEqual(points(bars([-10,-8,1,-11,-1,0])), [])

    def test_first_divergence_after_lip_kiss(self):
        """唇吻前置的同向面积背驰: 课15力度定义无吻种类要求。"""
        rows = bars([-10,-8,1,-11,-1,-12,1,-9,-1,0])
        event = points(rows)[0]
        self.assertEqual(event.kind, 'ma_buy1_candidate')
        self.assertEqual((event.kiss_index, event.kiss_kind), (2, 'lip'))
        self.assertEqual((event.reference_strength, event.current_strength), (24., 10.))
        self.assertEqual(event.confirmed_dt, rows[10]['available_dt'])

    def test_first_divergence_after_fly_kiss(self):
        """飞吻前置同样构成候选, 快速变动图上不出现湿吻也正常。"""
        rows = bars([-10,-8,1,-11,-7,-12,1,-9,-1,0])
        event = points(rows)[0]
        self.assertEqual((event.kiss_index, event.kiss_kind), (2, 'fly'))
        self.assertEqual((event.reference_strength, event.current_strength), (30., 10.))

    def test_lip_preceded_divergence_sell_mirror(self):
        """唇吻前置的卖端镜像不反转买端标签。"""
        rows = bars([-10,-8,1,-11,-1,-12,1,-9,-1,0], mirror=True)
        event = points(rows)[0]
        self.assertEqual(event.kind, 'ma_sell1_candidate')
        self.assertEqual(event.kiss_kind, 'lip')

    def test_wet_preceded_divergence_unchanged_after_kind_relaxation(self):
        """放宽吻种类后湿吻前置候选字段不变。"""
        rows = bars(FIRST)
        event = points(rows)[0]
        self.assertEqual((event.kiss_index, event.kiss_kind), (2, 'wet'))
        self.assertEqual((event.reference_strength, event.current_strength), (21., 13.))

    def test_stronger_or_equal_area_is_not_divergence(self):
        """严格弱于才比较成立; 相等或更强不触发first。"""
        for tail in ([-12,-9,0], [-12,-12,-12,0]):
            self.assertEqual(points(bars(FIRST[:6]+tail)), [])

    def test_area_weakness_without_both_price_extremes_is_rejected(self):
        """课15没有趋势没有背驰, 面积单独变小不足。"""
        rows = bars(FIRST); rows[7]['high'] = 500.
        self.assertEqual(points(rows), [])

    def test_average_strength_has_explicit_separate_units(self):
        """平均力度与面积选择显式, 两段平均10.5->6.5。"""
        event = points(bars(FIRST), use_avg=True)[0]
        self.assertEqual((event.reference_strength, event.current_strength), (10.5,6.5))

    def test_first_up_continuation_buy2_not_required_to_follow_buy1(self):
        """已观察转化后的第一次中继, 不要求本模块此前出一买。"""
        rows = bars(SECOND)
        event = points(rows, min_pre_gain=0)[0]
        self.assertEqual((event.kind, event.kiss_index), ('ma_buy2_candidate',1))
        self.assertEqual((event.dt,event.price), (BASE+timedelta(days=5),505.))
        self.assertEqual(event.confirmed_dt, rows[6]['available_dt'])
        self.assertEqual(event.volume_ratio,1.)

    def test_first_down_continuation_sell2_mirror(self):
        """新男上位第一次中继高位是卖端镜像。"""
        event = points(bars(SECOND,mirror=True),min_pre_gain=0)[0]
        self.assertEqual((event.kind,event.price), ('ma_sell2_candidate',495.))

    def test_second_pattern_accepts_fly_lip_and_wet(self):
        """课15回复: second不必湿吻, 飞吻/唇吻同样可用。"""
        for diff, expected in ((2,'fly'),(1,'lip'),(-.4,'wet')):
            rows = bars(SECOND[:4]+[diff,4])
            event = points(rows,min_pre_gain=0)[0]
            self.assertEqual(event.kiss_kind,expected)

    def test_open_kiss_or_flip_is_not_first_continuation(self):
        """吻尚在进行或最终转折不是已完成中继。"""
        self.assertEqual(points(bars(SECOND[:-1]),min_pre_gain=0),[])
        self.assertEqual(points(bars(SECOND[:4]+[1,-2]),min_pre_gain=0),[])

    def test_left_censored_alignment_does_not_prove_first(self):
        """窗口直接始于女上位, 无转化记录就不伪称第一次。"""
        self.assertEqual(points(bars([2,3,1,4]),min_pre_gain=0),[])

    def test_second_or_later_kiss_is_not_relabelled_as_first(self):
        """同一体位只有第一次中继取second, 不随尾部增补改写。"""
        rows = bars(SECOND+[2,5])
        events = points(rows,min_pre_gain=0)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0],points(bars(SECOND),min_pre_gain=0)[0])

    def test_front_leg_gain_threshold_is_inclusive_and_configurable(self):
        """有力前腿工程门槛独立设置, 等于阈值通过。"""
        rows = bars(SECOND); event = points(rows,min_pre_gain=0)[0]
        self.assertEqual(points(rows,min_pre_gain=event.pre_gain),[event])
        self.assertEqual(points(rows,min_pre_gain=event.pre_gain+.001),[])
        self.assertEqual(points(rows),[])

    def test_front_leg_volume_burst_is_rejected_before_later_shrink(self):
        """前腿放量不能以之后吻中缩量证明正常。"""
        rows = bars(SECOND); rows[3]['volume']=100.; rows[4]['volume']=100.
        self.assertEqual(points(rows,min_pre_gain=0),[])
        self.assertEqual(len(points(rows,min_pre_gain=0,max_volume_ratio=None)),1)

    def test_unknown_volume_baseline_does_not_pass_volume_gate(self):
        """零可比均量不做除零或将缺证据补为正常。"""
        rows = bars(SECOND)
        for row in rows: row['volume']=0.
        self.assertEqual(points(rows,min_pre_gain=0),[])

    def test_every_prefix_future_poison_and_closed_evidence_stability(self):
        """逐可见前缀已输出事件保持, 未来缺失/NaN价格不读取。"""
        rows = bars(FIRST + [-2,-1,2,3,1,4])
        old = set()
        for stop in range(1,len(rows)+1):
            visible=rows[:stop]
            future=[{key:row[key] for key in ('dt','closed_dt','available_dt')} for row in rows[stop:]]
            current=points(visible,min_pre_gain=0)
            self.assertEqual(current,find_ma_points(visible+future,visible[-1]['available_dt'],1,2,min_pre_gain=0))
            self.assertTrue(old.issubset(set(current)))
            old=set(current)

    def test_invalid_periods_thresholds_and_time_metadata(self):
        """非法周期、比例和时间字段必须明确拒绝。"""
        rows=bars(SECOND)
        for kwargs in ({'short_period':True},{'short_period':2,'long_period':2},
                       {'flip_confirm':0},{'proximity':float('nan')},
                       {'min_depth':2},{'min_pre_gain':-1},{'max_volume_ratio':0},
                       {'use_avg':1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                find_ma_points(rows,rows[-1]['available_dt'],**kwargs)
        del rows[0]['closed_dt']
        with self.assertRaises(ValueError): points(rows)

    def test_delivery_order_and_material_price_errors(self):
        """乱序到达需版本快照; 原始坏价格不放宽。"""
        rows=bars(SECOND); rows[0]['available_dt']=rows[-1]['available_dt']
        with self.assertRaises(ValueError): points(rows,min_pre_gain=0)
        rows=bars(SECOND); rows[0]['high']=1.
        with self.assertRaises(ValueError): points(rows)

    def test_empty_warmup_mutability_and_serialization(self):
        """空/暖机无候选, 输入不修改, 公开结果不可变且便于归档。"""
        self.assertEqual(points([]),[])
        self.assertEqual(find_ma_points(bars([1,2]),BASE+timedelta(days=20)),[])
        rows=bars(FIRST); original=[dict(row) for row in rows]
        event=points(rows)[0]
        self.assertEqual(rows,original)
        self.assertEqual(event.to_dict()['dt'],str(event.dt))
        with self.assertRaises(AttributeError): event.price=1


if __name__ == '__main__':
    unittest.main()
