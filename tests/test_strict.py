# -*- coding: utf-8 -*-
"""课24/27/37/53/61/101: 严格趋势背驰结构条件与四类返回语义(R3规格§11.6)。"""
import unittest
from datetime import datetime, timedelta

from chan import (ConfirmedMove, STRICT_CANDIDATE, STRICT_CONFIRMED,
                   STRICT_INSUFFICIENT, STRICT_REJECTED, StrictScan,
                   find_first_points, scan_strict_divergence,
                   strict_completion_cascade, strict_nested_chain,
                   travel_force)

T = datetime(2025, 1, 1)
# 完成下跌趋势: A=(88,94)系与B=(70,72)系波动分离, b=u8, c=u12-u14,
# c含回抽u13(三类点)且端点65为新低。
PRICES = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 69, 65, 76, 70, 78, 75, 82, 76, 86]


def sample(prices=PRICES, n=20):
    units = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        s = T + timedelta(hours=i * n)
        e = T + timedelta(hours=(i + 1) * n)
        units.append(ConfirmedMove('u%d' % i, 'base', 'up' if b > a else 'down',
                                   s, e, a, b, min(a, b), max(a, b),
                                   e + timedelta(minutes=2)))
    now = T + timedelta(hours=(len(prices) - 1) * n) + timedelta(days=1)
    return units, now


class TestStrictDivergenceSemantics(unittest.TestCase):
    def test_structure_close_without_force_is_insufficient(self):
        """结构四条件闭合但力度方法未注入, 不冒充成立(课37/61)。"""
        units, now = sample()
        scan = scan_strict_divergence(units, now, 'main')
        self.assertEqual(len(scan.results), 1)
        r = scan.results[0]
        self.assertEqual((r.kind, r.status, r.reason),
                         ('buy1', STRICT_INSUFFICIENT, 'force_missing'))
        self.assertEqual(r.conditions, (('trend', True), ('separated_centers', True),
                                        ('new_extreme', True), ('leave_third_point', True)))
        self.assertEqual(r.reference_ids, ('u8',))
        self.assertEqual(r.leave_ids, ('u12', 'u13', 'u14'))
        self.assertEqual(r.center_range, (70.0, 72.0))
        self.assertEqual(r.price, 65.0)
        self.assertGreater(r.confirmed_dt, r.dt)
        self.assertEqual(r.level, 'main')

    def test_mirror_is_sell(self):
        """镜像上涨趋势给卖一, 窗口对称(课37)。"""
        units, now = sample([200 - p for p in PRICES])
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.kind, r.status, r.reason),
                         ('sell1', STRICT_INSUFFICIENT, 'force_missing'))
        self.assertEqual(r.reference_ids, ('u8',))
        self.assertEqual(r.leave_ids, ('u12', 'u13', 'u14'))
        self.assertEqual(r.center_range, (128.0, 130.0))

    def test_rejected_center_waves_overlap(self):
        """课20: 中枢周围波动重叠即否决, 不只是ZD/ZG。"""
        prices = [140, 110, 125, 122, 128, 75, 74, 71, 74, 70, 110, 70, 66, 64, 75, 70, 78]
        units, now = sample(prices)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason), (STRICT_REJECTED, 'center_waves_overlap'))
        self.assertEqual(r.conditions, (('trend', True), ('separated_centers', False)))
        self.assertIsNone(r.center_range)

    def test_rejected_no_new_extreme(self):
        """课61: 背驰如果没有创新高新低, 是不存在的。"""
        prices = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 60, 72, 67, 69, 65, 76]
        units, now = sample(prices)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason), (STRICT_REJECTED, 'no_new_extreme'))
        self.assertEqual(r.conditions[-1], ('new_extreme', False))

    def test_rejected_no_third_point_in_leave(self):
        """课37: c不含末中枢三类点只是围绕B的震荡, 用盘整背驰。"""
        units, now = sample(PRICES[:13] + [67, 60, 71, 65])
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason), (STRICT_REJECTED, 'no_third_point_in_leave'))
        self.assertEqual(r.leave_ids, ('u12', 'u13'))
        self.assertEqual(r.conditions[-1], ('leave_third_point', False))

    def test_internal_extreme_waits(self):
        """c内部极值不猜发生时刻, 不把净端点叫背驰极值。"""
        prices = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 63, 65, 71, 66, 70]
        units, now = sample(prices)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_INSUFFICIENT, 'internal_extreme_time_unknown'))
        self.assertEqual(r.conditions, (('trend', True), ('separated_centers', True),
                                        ('new_extreme', None)))

    def test_zero_width_center_is_insufficient(self):
        """零宽中枢的三类点围绕关系无法表达, 登记证据不足。"""
        prices = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 70, 67, 69, 65, 76]
        units, now = sample(prices)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason), (STRICT_INSUFFICIENT, 'zero_width_center'))
        self.assertEqual(r.center_range, (70.0, 70.0))
        self.assertEqual(r.conditions[-1], ('leave_third_point', None))

    def test_consolidation_completed_type_is_skipped(self):
        """盘整完成项不构成趋势背驰问题。"""
        units, now = sample([120, 110, 115, 108, 114, 90, 94, 88, 116])
        scan = scan_strict_divergence(units, now, 'main')
        self.assertEqual(scan.results, ())
        self.assertTrue(any(reason == 'not_trend' for _, reason in scan.skipped))


class TestStrictCandidateLifecycle(unittest.TestCase):
    def test_candidate_to_final_identity_continuity(self):
        """课61先假设进入背驰段: 候选与最终语义同一身份, 完成后冻结。"""
        units, now = sample()
        identity = None
        for i in (12, 13, 14):
            scan = scan_strict_divergence(units, units[i].confirmed_dt, 'main')
            self.assertEqual(len(scan.results), 1)
            r = scan.results[0]
            self.assertEqual((r.status, r.reason), (STRICT_CANDIDATE, 'trend_open'))
            self.assertEqual(r.conditions[0], ('trend', None))
            if identity is None:
                identity = r.divergence_id
            self.assertEqual(r.divergence_id, identity)
        frozen = None
        for i in (15, 18, 21):
            scan = scan_strict_divergence(units, units[i].confirmed_dt, 'main')
            r = scan.results[0]
            self.assertEqual((r.status, r.reason), (STRICT_INSUFFICIENT, 'force_missing'))
            self.assertEqual(r.divergence_id, identity)
            frozen = (r.status, r.reason, r.reference_ids, r.leave_ids, r.price)
        scan = scan_strict_divergence(units, now, 'main')
        r = scan.results[0]
        self.assertEqual((r.status, r.reason, r.reference_ids, r.leave_ids, r.price), frozen)
        self.assertTrue(scan.open_tail)

    def test_candidate_records_current_evidence_only(self):
        """候选只登记已确认证据: 最晚确认时刻为最后可见单元。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[14].confirmed_dt, 'main')
        r = scan.results[0]
        self.assertEqual(r.conditions, (('trend', None), ('separated_centers', True),
                                        ('new_extreme', True), ('leave_third_point', True)))
        self.assertEqual(r.confirmed_dt, units[14].confirmed_dt)
        self.assertEqual(r.dt, units[14].end_dt)
        self.assertEqual(r.price, 65.0)

    def test_leave_not_started_has_no_candidate(self):
        """末中枢回抽仍在延伸、离开段未开始时不登记候选。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[11].confirmed_dt, 'main')
        self.assertEqual(scan.results, ())
        self.assertTrue(scan.open_tail)


class TestStrictRobustness(unittest.TestCase):
    def test_prefix_input_equivalence(self):
        """截断输入与全量输入同观察时刻等价, 未来单元不读取。"""
        units, _ = sample()
        for i in (10, 13, 14, 15, 18, 21):
            cut = units[i].confirmed_dt
            self.assertEqual(scan_strict_divergence(units[:i + 1], cut, 'main'),
                             scan_strict_divergence(units, cut, 'main'))

    def test_future_poison_not_read(self):
        """观察时刻之后的身份/级别/价格毒值不影响结果。"""
        units, _ = sample()
        cut = units[15].confirmed_dt
        poison = units[16]._replace(move_id=None, level=None, low=None,
                                    start_price=float('nan'))
        self.assertEqual(scan_strict_divergence(units[:16] + [poison], cut, 'main'),
                         scan_strict_divergence(units[:16], cut, 'main'))

    def test_empty_scan(self):
        """空输入不产生结果, 尾部标记为否。"""
        units, now = sample()
        self.assertEqual(scan_strict_divergence([], now, 'main'),
                         StrictScan((), (), 0, False))
        scan = scan_strict_divergence(units, units[0].confirmed_dt, 'main')
        self.assertEqual(scan.results, ())
        self.assertTrue(scan.open_tail)

    def test_to_dict_roundtrip(self):
        """存档格式: 条件与中枢区间转列表, 时间转字符串。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        out = r.to_dict()
        self.assertEqual(out['conditions'],
                         [['trend', True], ['separated_centers', True],
                          ['new_extreme', True], ['leave_third_point', True]])
        self.assertEqual(out['center_range'], [70.0, 72.0])
        self.assertIsNone(out['force_method'])
        self.assertIsNone(out['force_reference'])
        self.assertIsNone(out['force_leave'])
        self.assertIsInstance(out['confirmed_dt'], str)
        self.assertEqual(sorted(out.keys()), sorted([
            'divergence_id', 'kind', 'level', 'status', 'reason', 'trend_id',
            'center_id', 'center_range', 'reference_ids', 'leave_ids',
            'force_method', 'force_reference', 'force_leave',
            'conditions', 'confirmed_dt', 'dt', 'price']))

    def test_semantic_constants(self):
        """四类语义常量与确认语义声明。"""
        self.assertEqual((STRICT_CANDIDATE, STRICT_CONFIRMED,
                          STRICT_INSUFFICIENT, STRICT_REJECTED),
                         ('candidate', 'confirmed', 'insufficient_evidence', 'rejected'))


class TestStrictForceInjection(unittest.TestCase):
    def _fn(self, value):
        return lambda reference, leave: value

    def test_force_decline_confirms(self):
        """结构闭合+注入力度减弱成立, 保留方法身份与力度值。"""
        units, now = sample()
        scan = scan_strict_divergence(units, now, 'main',
                                      force_fn=self._fn((10.0, 5.0)),
                                      force_method='unit_travel')
        r = scan.results[0]
        self.assertEqual((r.kind, r.status, r.reason),
                         ('buy1', STRICT_CONFIRMED, 'force_decline'))
        self.assertEqual(r.conditions, (('trend', True), ('separated_centers', True),
                                        ('new_extreme', True),
                                        ('leave_third_point', True),
                                        ('force', True)))
        self.assertEqual((r.force_method, r.force_reference, r.force_leave),
                         ('unit_travel', 10.0, 5.0))

    def test_force_not_declining_rejects(self):
        """注入力度不减即反例, 背驰段假设不成立(课61)。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main',
                                   force_fn=self._fn((5.0, 10.0)),
                                   force_method='unit_travel').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_REJECTED, 'force_not_declining'))
        self.assertEqual(r.conditions[-1], ('force', False))
        self.assertEqual((r.force_reference, r.force_leave), (5.0, 10.0))

    def test_equal_force_rejects(self):
        """力度相等不减, 同样否决。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main',
                                   force_fn=self._fn((7.0, 7.0)),
                                   force_method='unit_travel').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_REJECTED, 'force_not_declining'))

    def test_force_unavailable_is_insufficient(self):
        """方法对该输入不可用返回None, 登记证据不足不否决。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main',
                                   force_fn=self._fn(None),
                                   force_method='macd_area').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_INSUFFICIENT, 'force_unavailable'))
        self.assertEqual(r.conditions[-1], ('force', None))
        self.assertEqual(r.force_method, 'macd_area')
        self.assertIsNone(r.force_reference)

    def test_injection_requires_method_identity(self):
        """注入force_fn必须声明方法身份, 保留方法身份与局限。"""
        units, now = sample()
        with self.assertRaises(ValueError):
            scan_strict_divergence(units, now, 'main', force_fn=self._fn((1, 0)))
        with self.assertRaises(ValueError):
            scan_strict_divergence(units, now, 'main', force_fn=self._fn((1, 0)),
                                   force_method='')

    def test_structural_rejection_ignores_force(self):
        """结构否决先于力度评估, 力度方法不被消费。"""
        prices = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 60, 72, 67, 69, 65, 76]
        units, now = sample(prices)
        calls = []
        def fn(reference, leave):
            calls.append(1)
            return (10.0, 5.0)
        r = scan_strict_divergence(units, now, 'main', force_fn=fn,
                                   force_method='unit_travel').results[0]
        self.assertEqual((r.status, r.reason), (STRICT_REJECTED, 'no_new_extreme'))
        self.assertEqual(calls, [])

    def test_travel_force_example(self):
        """内置示例力度: 单元行程和, 不冒充理论度量。"""
        units, _ = sample()
        leave = units[12:15]
        self.assertEqual(travel_force(leave),
                         sum(u.high - u.low for u in leave))

    def test_candidate_not_force_evaluated(self):
        """开放尾部候选不评估力度, 方法身份与力度值为空。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[13].confirmed_dt, 'main',
                                      force_fn=self._fn((10.0, 5.0)),
                                      force_method='unit_travel')
        r = scan.results[0]
        self.assertEqual(r.status, STRICT_CANDIDATE)
        self.assertIsNone(r.force_method)
        self.assertIsNone(r.force_reference)
        self.assertIsNone(r.force_leave)


class TestStrictNestedChain(unittest.TestCase):
    """课27/61: 区间套次级确认链——围绕末次级中枢的两段比较逐重下探。"""

    @staticmethod
    def _units(rows, level, start):
        units = []
        for i, (a, b, hours) in enumerate(rows):
            s = start + timedelta(hours=sum(r[2] for r in rows[:i]))
            e = s + timedelta(hours=hours)
            units.append(ConfirmedMove('%s%d' % (level[0], i), level,
                                       'up' if b > a else 'down',
                                       s, e, a, b, min(a, b), max(a, b),
                                       e + timedelta(minutes=2)))
        return units

    def sub_units(self):
        """重2单元: 精确覆盖父级c段[T+240h,T+300h] 72->65。

        分解: a=[s0], 中枢(68,69)=[s1,s2,s3](s4/s5触沿延伸), 最后
        反向回试=s4, 背驰段=[s5]。
        """
        return self._units([(72, 70, 10), (70, 67.5, 5), (67.5, 69, 10),
                            (69, 68, 5), (68, 69.5, 5), (69.5, 65, 25)],
                           'sub', T + timedelta(hours=240))

    def tick_units(self):
        """重3单元: 精确覆盖重2背驰段[T+275h,T+300h] 69.5->65。

        分解: a=[t0], 中枢(66.8,67.8)=[t1,t2,t3](t4/t5触沿延伸),
        最后反向回试=t4, 背驰段=[t5]。
        """
        return self._units([(69.5, 68, 10), (68, 66.5, 4), (66.5, 67.8, 4),
                            (67.8, 66.8, 2), (66.8, 67.5, 2), (67.5, 65, 3)],
                           'tick', T + timedelta(hours=275))

    def test_bc_chain_completes_with_injected_force(self):
        """重2力度减弱bc: 转折定位在该重背驰段终点与极值价格。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        chain = strict_nested_chain(r, units, [('sub', sub)], now,
                                    force_fn=lambda ref, lv: (10.0, 5.0),
                                    force_method='unit_travel')
        self.assertEqual(chain.divergence_id, r.divergence_id)
        self.assertEqual((chain.kind, chain.level), ('buy1', 'main'))
        self.assertEqual(chain.depth, 1)
        self.assertTrue(chain.complete)
        self.assertIsNone(chain.break_depth)
        self.assertIsNone(chain.break_reason)
        lv = chain.levels[0]
        self.assertEqual((lv.depth, lv.level, lv.status, lv.reason),
                         (1, 'sub', 'bc', None))
        self.assertEqual(lv.reference_ids, ('s0',))
        self.assertEqual(lv.leave_ids, ('s5',))
        self.assertEqual(lv.center_range, (68.0, 69.0))
        self.assertEqual((lv.force_method, lv.force_reference, lv.force_leave),
                         ('unit_travel', 10.0, 5.0))
        self.assertEqual((lv.dt, lv.price), (sub[5].end_dt, 65.0))
        self.assertEqual((chain.turn_dt, chain.turn_price),
                         (sub[5].end_dt, 65.0))
        self.assertGreaterEqual(chain.confirmed_dt, sub[5].confirmed_dt)
        self.assertGreaterEqual(chain.confirmed_dt, r.confirmed_dt)

    def test_travel_force_not_declining_breaks(self):
        """内置行程力度不减即反例, 该重否决(课61力度大于前者)。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        chain = strict_nested_chain(
            r, units, [('sub', sub)], now,
            force_fn=lambda ref, lv: (travel_force(ref), travel_force(lv)),
            force_method='unit_travel')
        lv = chain.levels[0]
        self.assertEqual((lv.status, lv.reason),
                         ('force_not_declining', STRICT_REJECTED))
        self.assertEqual((chain.break_depth, chain.break_reason),
                         (1, 'force_not_declining'))
        self.assertFalse(chain.complete)
        self.assertIsNone(chain.turn_dt)
        self.assertEqual(lv.force_reference, travel_force(sub[:1]))
        self.assertEqual(lv.force_leave, travel_force(sub[5:]))

    def test_force_missing_descends_to_next_layer(self):
        """力度未注入不否决: 无否定证据继续下探(课61), 窗口逐重传递。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        chain = strict_nested_chain(
            r, units, [('sub', self.sub_units()), ('tick', self.tick_units())],
            now)
        self.assertEqual(chain.depth, 2)
        self.assertEqual([lv.status for lv in chain.levels],
                         ['force_missing', 'force_missing'])
        self.assertEqual([lv.reason for lv in chain.levels],
                         [STRICT_INSUFFICIENT, STRICT_INSUFFICIENT])
        self.assertFalse(chain.complete)
        self.assertIsNone(chain.turn_dt)
        self.assertEqual(chain.levels[1].reference_ids, ('t0',))
        self.assertEqual(chain.levels[1].leave_ids, ('t5',))
        self.assertEqual(chain.levels[1].center_range, (66.8, 67.8))

    def test_force_unavailable_descends(self):
        """方法对该输入不可用登记证据不足, 同样继续下探。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        chain = strict_nested_chain(
            r, units, [('sub', self.sub_units()), ('tick', self.tick_units())],
            now, force_fn=lambda ref, lv: None, force_method='macd_area')
        self.assertEqual([lv.status for lv in chain.levels],
                         ['force_unavailable', 'force_unavailable'])
        self.assertEqual([lv.force_method for lv in chain.levels],
                         ['macd_area', 'macd_area'])
        self.assertFalse(chain.complete)

    def test_double_layer_bc_chain_locates_turn_at_innermost(self):
        """双层bc链: 转折取最内重背驰段终点与极值(课61逐重嵌套)。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        tick = self.tick_units()
        chain = strict_nested_chain(
            r, units, [('sub', self.sub_units()), ('tick', tick)], now,
            force_fn=lambda ref, lv: (10.0, 5.0),
            force_method='unit_travel')
        self.assertEqual(chain.depth, 2)
        self.assertTrue(chain.complete)
        self.assertEqual([lv.status for lv in chain.levels], ['bc', 'bc'])
        self.assertEqual((chain.turn_dt, chain.turn_price),
                         (tick[5].end_dt, 65.0))
        lv2 = chain.levels[1]
        self.assertEqual((lv2.reference_ids, lv2.leave_ids),
                         (('t0',), ('t5',)))
        self.assertGreaterEqual(chain.confirmed_dt, tick[5].confirmed_dt)

    def test_inner_rejection_keeps_outer_turn(self):
        """重3力度不减否决该重, 转折仍取最内bc重(重2)定位。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        values = [(10.0, 5.0), (0.5, 3.0)]
        calls = []

        def fn(reference, leave):
            value = values[len(calls)]
            calls.append(1)
            return value

        chain = strict_nested_chain(
            r, units, [('sub', sub), ('tick', self.tick_units())], now,
            force_fn=fn, force_method='unit_travel')
        self.assertEqual([lv.status for lv in chain.levels],
                         ['bc', 'force_not_declining'])
        self.assertEqual((chain.break_depth, chain.break_reason),
                         (2, 'force_not_declining'))
        self.assertFalse(chain.complete)
        self.assertEqual((chain.turn_dt, chain.turn_price),
                         (sub[5].end_dt, 65.0))
        self.assertEqual((chain.levels[1].force_reference,
                          chain.levels[1].force_leave), (0.5, 3.0))

    def test_candidate_parent_chain_locates_turn_now(self):
        """开放尾部候选可当下定位: 重2bc链在候选父级上成立(课61)。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[14].confirmed_dt, 'main')
        r = scan.results[0]
        self.assertEqual(r.status, STRICT_CANDIDATE)
        self.assertEqual(r.leave_ids, ('u12', 'u13', 'u14'))
        chain = strict_nested_chain(r, units, [('sub', self.sub_units())],
                                    units[14].confirmed_dt,
                                    force_fn=lambda ref, lv: (10.0, 5.0),
                                    force_method='unit_travel')
        self.assertTrue(chain.complete)
        self.assertEqual(chain.turn_price, 65.0)
        self.assertIsNone(chain.break_depth)

    def test_no_new_extreme_rejects_sub_level(self):
        """课61: 子级未创新低即否决该重背驰段假设(候选父级可达)。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[13].confirmed_dt, 'main')
        r = scan.results[0]
        self.assertEqual(r.leave_ids, ('u12', 'u13'))
        flat = self._units([(72, 70, 10), (70, 67.5, 5), (67.5, 69, 10),
                            (69, 68, 5), (68, 69.5, 5), (69.5, 69, 5)],
                           'sub', T + timedelta(hours=240))
        chain = strict_nested_chain(r, units, [('sub', flat)],
                                    units[13].confirmed_dt)
        lv = chain.levels[0]
        self.assertEqual((lv.status, lv.reason),
                         ('no_new_extreme', STRICT_REJECTED))
        self.assertEqual((chain.break_depth, chain.break_reason),
                         (1, 'no_new_extreme'))
        self.assertFalse(chain.complete)
        self.assertIsNone(chain.turn_dt)

    def test_not_covered_by_truncated_layer(self):
        """子单元未覆盖上一重背驰段区间登记not_covered, 不猜窗口。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        chain = strict_nested_chain(r, units, [('sub', self.sub_units()[:4])],
                                    now)
        lv = chain.levels[0]
        self.assertEqual((lv.status, lv.reason),
                         ('not_covered', STRICT_INSUFFICIENT))
        self.assertEqual(lv.reference_ids, ())
        self.assertEqual(lv.leave_ids, ())
        self.assertIsNone(lv.center_range)
        self.assertIsNone(lv.dt)
        self.assertIsNone(lv.price)
        self.assertFalse(chain.complete)

    def test_not_covered_empty_layer(self):
        """空单元表不可见任何证据: not_covered且该重确认时间为空。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        chain = strict_nested_chain(r, units, [('sub', [])], now)
        lv = chain.levels[0]
        self.assertEqual((lv.status, lv.reason),
                         ('not_covered', STRICT_INSUFFICIENT))
        self.assertIsNone(lv.confirmed_dt)

    def test_no_sub_center(self):
        """区间内无次级中枢(单调下行不成重叠)登记证据不足。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        flat = self._units([(72, 68, 20), (68, 66, 20), (66, 65, 20)],
                           'sub', T + timedelta(hours=240))
        chain = strict_nested_chain(r, units, [('sub', flat)], now)
        self.assertEqual((chain.levels[0].status, chain.levels[0].reason),
                         ('no_sub_center', STRICT_INSUFFICIENT))

    def test_no_compare_legs(self):
        """中枢在区间首单元起(进入段为空): 对照窗口不可建立。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        legs = self._units([(72, 70, 10), (70, 71, 10), (71, 69, 10),
                            (69, 68, 10), (68, 65, 20)],
                           'sub', T + timedelta(hours=240))
        chain = strict_nested_chain(r, units, [('sub', legs)], now)
        self.assertEqual((chain.levels[0].status, chain.levels[0].reason),
                         ('no_compare_legs', STRICT_INSUFFICIENT))

    def test_parent_rejected_short_circuits(self):
        """父级已否决: 不消费任何重, break_depth=0/parent_rejected。"""
        prices = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 60, 72, 67, 69, 65, 76]
        units, now = sample(prices)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual(r.status, STRICT_REJECTED)
        chain = strict_nested_chain(r, units, [('sub', self.sub_units())], now)
        self.assertEqual(chain.levels, ())
        self.assertEqual(chain.depth, 0)
        self.assertEqual((chain.break_depth, chain.break_reason),
                         (0, 'parent_rejected'))
        self.assertFalse(chain.complete)
        self.assertIsNone(chain.turn_dt)
        self.assertIsNone(chain.turn_price)
        self.assertEqual(chain.confirmed_dt, r.confirmed_dt)

    def test_price_misalignment_raises(self):
        """时间覆盖但端点价格不对齐: 价格坐标契约违反报错。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        bad = self._units([(71.9, 67, 20), (67, 69, 20), (69, 66, 10),
                           (66, 65, 10)],
                          'sub', T + timedelta(hours=240))
        with self.assertRaises(ValueError):
            strict_nested_chain(r, units, [('sub', bad)], now)

    def test_layer_level_mismatch_raises(self):
        """声明的级别名须与该重单元级别一致。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_nested_chain(r, units, [('other', self.sub_units())], now)

    def test_leave_ids_must_be_visible(self):
        """父级leave_ids不在as_of可见单元中: 输入与结果不配套报错。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_nested_chain(r, units[:10], [], now)

    def test_chain_requires_divergence_result(self):
        """divergence须为scan_strict_divergence结果, layers须为序列。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_nested_chain(object(), units, [], now)
        with self.assertRaises(TypeError):
            strict_nested_chain(r, units, 'bad', now)

    def test_chain_injection_requires_method_identity(self):
        """链上注入force_fn同样必须声明方法身份。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_nested_chain(r, units, [('sub', self.sub_units())], now,
                                force_fn=lambda ref, lv: (10.0, 5.0))

    def test_chain_to_dict_roundtrip(self):
        """存档格式: 层级嵌套转列表, 时间转字符串, 区间转列表。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        chain = strict_nested_chain(r, units, [('sub', self.sub_units())],
                                    now, force_fn=lambda ref, lv: (10.0, 5.0),
                                    force_method='unit_travel')
        out = chain.to_dict()
        self.assertIsInstance(out['turn_dt'], str)
        self.assertIsInstance(out['confirmed_dt'], str)
        self.assertEqual(sorted(out.keys()), sorted([
            'divergence_id', 'kind', 'level', 'levels', 'depth', 'complete',
            'break_depth', 'break_reason', 'turn_dt', 'turn_price',
            'confirmed_dt']))
        lv = out['levels'][0]
        self.assertEqual(sorted(lv.keys()), sorted([
            'depth', 'level', 'status', 'reason', 'reference_ids',
            'leave_ids', 'center_range', 'force_method', 'force_reference',
            'force_leave', 'confirmed_dt', 'dt', 'price']))
        self.assertEqual(lv['center_range'], [68.0, 69.0])
        self.assertEqual(lv['reference_ids'], ['s0'])
        self.assertEqual(lv['leave_ids'], ['s5'])
        self.assertIsInstance(lv['confirmed_dt'], str)
        self.assertIsInstance(lv['dt'], str)


class TestStrictCompletionCascade(unittest.TestCase):
    """课35/37: 次级走势完成级联确认——端点单元由细级完成证据逐层复核。"""

    @staticmethod
    def _make(rows, level, start):
        units = []
        for i, (a, b, hours) in enumerate(rows):
            s = start + timedelta(hours=sum(r[2] for r in rows[:i]))
            e = s + timedelta(hours=hours)
            units.append(ConfirmedMove('%s%d' % (level[0], i), level,
                                       'up' if b > a else 'down',
                                       s, e, a, b, min(a, b), max(a, b),
                                       e + timedelta(minutes=2)))
        return units

    def sub_units(self):
        """细级层: 复核u14[T+280h,T+300h]69->65。

        中枢(67,68)=[s1,s2,s3], s4离开, 证据s5回抽进中枢(课39 A3
        跌回, 递归规则3)——完成证据在端点之后, 属下一走势。
        """
        return self._make([(69, 70, 4), (70, 67, 6), (67, 68, 4),
                           (68, 66, 3), (66, 65, 3), (65, 67, 6)],
                          'sub', T + timedelta(hours=280))

    def tick_units(self):
        """更细级层: 复核s4[T+297h,T+300h]66->65。

        中枢(65.5,65.9)=[t0,t1,t2], t3/t4离开, 证据t5回抽进中枢。
        """
        return self._make([(66, 65.5, 0.5), (65.5, 65.9, 0.5),
                           (65.9, 65.4, 0.5), (65.4, 65.2, 0.5),
                           (65.2, 65.0, 1.0), (65.0, 65.7, 1.0)],
                          'tick', T + timedelta(hours=297))

    def test_confirmed_cascade_single_layer(self):
        """端点单元恰为细级完成类型: 该层confirmed并级联至末组成单元。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        cascade = strict_completion_cascade(r, units, [('sub', sub)], now)
        self.assertEqual(cascade.divergence_id, r.divergence_id)
        self.assertEqual((cascade.kind, cascade.level), ('buy1', 'main'))
        self.assertEqual(cascade.depth, 1)
        self.assertTrue(cascade.complete)
        lv = cascade.levels[0]
        self.assertEqual((lv.depth, lv.level, lv.unit_id, lv.status),
                         (1, 'sub', 'u14', 'confirmed'))
        self.assertEqual(lv.unit_ids, ('s0', 's1', 's2', 's3', 's4'))
        self.assertEqual(lv.confirmed_dt, sub[5].confirmed_dt)
        self.assertEqual(cascade.confirmed_dt,
                         max(r.confirmed_dt, sub[5].confirmed_dt))

    def test_double_layer_cascade_confirmed(self):
        """双层confirmed: 级联对象为上层匹配类型的末组成单元(分解定理二)。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        tick = self.tick_units()
        cascade = strict_completion_cascade(
            r, units, [('sub', sub), ('tick', tick)], now)
        self.assertEqual(cascade.depth, 2)
        self.assertTrue(cascade.complete)
        self.assertEqual([(lv.unit_id, lv.status) for lv in cascade.levels],
                         [('u14', 'confirmed'), ('s4', 'confirmed')])
        lv2 = cascade.levels[1]
        self.assertEqual(lv2.unit_ids, ('t0', 't1', 't2', 't3', 't4'))
        self.assertEqual(lv2.confirmed_dt, tick[5].confirmed_dt)
        self.assertEqual(cascade.confirmed_dt,
                         max(r.confirmed_dt, sub[5].confirmed_dt,
                             tick[5].confirmed_dt))

    def test_completion_evidence_not_arrived_is_unverified(self):
        """完成证据在端点之后: 证据单元未确认前该层unverified(课35)。"""
        units, _ = sample()
        r = scan_strict_divergence(units, units[14].confirmed_dt,
                                   'main').results[0]
        sub = self.sub_units()
        early = strict_completion_cascade(
            r, units, [('sub', sub)], units[14].confirmed_dt)
        lv = early.levels[0]
        self.assertEqual((lv.unit_id, lv.status, lv.unit_ids),
                         ('u14', 'unverified', ()))
        self.assertIsNone(lv.confirmed_dt)
        self.assertFalse(early.complete)
        late = strict_completion_cascade(
            r, units, [('sub', sub)], sub[5].confirmed_dt)
        self.assertEqual(late.levels[0].status, 'confirmed')
        self.assertTrue(late.complete)

    def test_no_matching_type_is_unverified(self):
        """细级切片不成完成类型或区间不匹配: unverified不判任一方错误。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        bare = self._make([(69, 68, 10), (68, 65, 10)],
                          'sub', T + timedelta(hours=280))
        cascade = strict_completion_cascade(r, units, [('sub', bare)], now)
        self.assertEqual((cascade.levels[0].status, cascade.levels[0].unit_ids),
                         ('unverified', ()))
        self.assertFalse(cascade.complete)

    def test_decomposition_without_start_cut_is_unverified(self):
        """细级前缀已及端点单元起点但不在此切开: 分解口径不同。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        shift = self._make([(69.5, 70, 4), (70, 67, 6), (67, 68, 4),
                            (68, 66, 3), (66, 65, 3), (65, 67, 6)],
                           'sub', T + timedelta(hours=280)
                           - timedelta(minutes=30))
        cascade = strict_completion_cascade(r, units, [('sub', shift)], now)
        self.assertEqual(cascade.levels[0].status, 'unverified')

    def test_first_failure_stops_cascade(self):
        """首个未通过层即止: 其余声明层不消费。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        bare = self._make([(69, 68, 10), (68, 65, 10)],
                          'sub', T + timedelta(hours=280))
        cascade = strict_completion_cascade(
            r, units, [('sub', bare), ('tick', self.tick_units())], now)
        self.assertEqual(cascade.depth, 1)
        self.assertEqual(len(cascade.levels), 1)
        self.assertFalse(cascade.complete)

    def test_not_covered_layer(self):
        """细级前缀未及端点单元起点: not_covered; 空单元表同理。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        short = self._make([(72, 70, 10), (70, 67.5, 5), (67.5, 69, 10)],
                           'sub', T + timedelta(hours=240))
        cascade = strict_completion_cascade(r, units, [('sub', short)], now)
        self.assertEqual((cascade.levels[0].status,
                          cascade.levels[0].confirmed_dt),
                         ('not_covered', None))
        self.assertFalse(cascade.complete)
        empty = strict_completion_cascade(r, units, [('sub', [])], now)
        self.assertEqual(empty.levels[0].status, 'not_covered')
        self.assertEqual(empty.depth, 1)

    def test_price_misalignment_raises(self):
        """起点切分处端点价格不对齐: 价格坐标契约违反报错。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        bad = self._make([(69.5, 70, 4), (70, 67, 6), (67, 68, 4),
                          (68, 66, 3), (66, 65, 3), (65, 67, 6)],
                         'sub', T + timedelta(hours=280))
        with self.assertRaises(ValueError):
            strict_completion_cascade(r, units, [('sub', bad)], now)

    def test_layer_level_mismatch_raises(self):
        """声明的级别名须与该层单元级别一致。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_completion_cascade(r, units,
                                      [('other', self.sub_units())], now)

    def test_future_layer_unit_not_read(self):
        """观察时刻之后的细级身份/价格毒值不影响复核。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        sub = self.sub_units()
        extra = self._make([(67, 68, 4)], 'sub', sub[5].end_dt)
        cut = sub[5].confirmed_dt
        base = strict_completion_cascade(r, units, [('sub', sub + extra)], cut)
        self.assertEqual(base.levels[0].status, 'confirmed')
        poison = extra[0]._replace(move_id=None, level=None,
                                   start_price=float('nan'))
        self.assertEqual(strict_completion_cascade(r, units,
                                                   [('sub', sub + [poison])],
                                                   cut),
                         base)

    def test_requires_divergence_and_layer_shape(self):
        """divergence须为扫描结果; layers须为(级别名, 单元表)序列。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_completion_cascade(object(), units, [], now)
        with self.assertRaises(TypeError):
            strict_completion_cascade(r, units, 'bad', now)
        with self.assertRaises(ValueError):
            strict_completion_cascade(r, units, [('sub',)], now)

    def test_leave_ids_must_be_visible(self):
        """父级leave_ids不在as_of可见单元中: 输入与结果不配套报错。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        with self.assertRaises(ValueError):
            strict_completion_cascade(r, units[:10], [], now)

    def test_candidate_endpoint_cascade(self):
        """开放尾部候选端点同样可级联复核, 与父级语义正交。"""
        units, _ = sample()
        scan = scan_strict_divergence(units, units[14].confirmed_dt, 'main')
        r = scan.results[0]
        self.assertEqual(r.status, STRICT_CANDIDATE)
        sub = self.sub_units()
        cascade = strict_completion_cascade(
            r, units, [('sub', sub)], sub[5].confirmed_dt)
        lv = cascade.levels[0]
        self.assertEqual((lv.unit_id, lv.status), ('u14', 'confirmed'))
        self.assertTrue(cascade.complete)

    def test_cascade_to_dict_roundtrip(self):
        """存档格式: 层级嵌套转列表, 时间转字符串, 组成身份转列表。"""
        units, now = sample()
        r = scan_strict_divergence(units, now, 'main').results[0]
        cascade = strict_completion_cascade(
            r, units, [('sub', self.sub_units())], now)
        out = cascade.to_dict()
        self.assertEqual(sorted(out.keys()), sorted([
            'divergence_id', 'kind', 'level', 'levels', 'depth',
            'complete', 'confirmed_dt']))
        lv = out['levels'][0]
        self.assertEqual(sorted(lv.keys()), sorted([
            'depth', 'level', 'unit_id', 'status', 'unit_ids',
            'confirmed_dt']))
        self.assertEqual(lv['unit_ids'], ['s0', 's1', 's2', 's3', 's4'])
        self.assertIsInstance(lv['confirmed_dt'], str)
        self.assertIsInstance(out['confirmed_dt'], str)


def bars(prices=PRICES, n=20):
    """与sample()同时间戳的线性路径行情: MACD辅助证据输入。"""
    rows = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        for j in range(n):
            dt = T + timedelta(hours=i * n + j)
            p = a + (b - a) * j / n
            rows.append(dict(dt=dt, open=p, high=p, low=p, close=p,
                             volume=100., closed_dt=dt,
                             available_dt=dt + timedelta(minutes=1)))
    dt = T + timedelta(hours=(len(prices) - 1) * n)
    p = prices[-1]
    rows.append(dict(dt=dt, open=p, high=p, low=p, close=p, volume=100.,
                     closed_dt=dt, available_dt=dt + timedelta(minutes=1)))
    return rows


class TestStrictR3Closeout(unittest.TestCase):
    """§11.6边界清单收口: 平端点触平、迟到历史数据、MACD辅助并列示例。"""

    def sample_with_reference_dip(self, leave_end):
        """参考段u8单元内下探66回收70设置前低, 离开段低点恰触66。"""
        prices = list(PRICES)
        prices[13] = 66
        prices[15] = leave_end
        units = []
        for i, (a, b) in enumerate(zip(prices, prices[1:])):
            s = T + timedelta(hours=i * 20)
            e = T + timedelta(hours=(i + 1) * 20)
            low = 66 if i == 8 else min(a, b)
            units.append(ConfirmedMove('u%d' % i, 'base',
                                       'up' if b > a else 'down', s, e,
                                       a, b, low, max(a, b),
                                       e + timedelta(minutes=2)))
        now = T + timedelta(hours=(len(prices) - 1) * 20) + timedelta(days=1)
        return units, now

    def test_flat_touch_extreme_is_no_new_extreme(self):
        """平端点触平: 离开段低点恰触前低66不构成新低(课37/61严格
        超越口径, 触平非创新); 破一位(65)即结构闭合, 等值边界精确。"""
        units, now = self.sample_with_reference_dip(66)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_REJECTED, 'no_new_extreme'))
        self.assertEqual(r.conditions[-1], ('new_extreme', False))
        self.assertEqual(r.leave_ids, ('u12', 'u13', 'u14'))
        self.assertEqual(r.price, 66.0)
        units, now = self.sample_with_reference_dip(65)
        r = scan_strict_divergence(units, now, 'main').results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_INSUFFICIENT, 'force_missing'))
        self.assertEqual(r.price, 65.0)

    def test_late_history_requires_rebuilt_version(self):
        """迟到历史数据不静默参与: 可见单元须连续前缀, 乱序到达须由
        调用方重建版本(R3规格边界清单), 按时版本不受影响。"""
        units, now = sample()
        late = units[10]._replace(
            confirmed_dt=units[16].end_dt + timedelta(minutes=2))
        mixed = list(units)
        mixed[10] = late
        with self.assertRaises(ValueError):
            scan_strict_divergence(mixed, units[15].confirmed_dt, 'main')
        scan = scan_strict_divergence(units, units[15].confirmed_dt, 'main')
        self.assertEqual(len(scan.results), 1)

    def test_macd_auxiliary_and_strict_are_separate(self):
        """§11.6交付物并列示例: 同一样本上MACD辅助候选与严格结构
        条件互不冒名——辅助输出method=macd_area不赋予严格身份;
        严格扫描不消费MACD面积, 力度证据仅经显式注入并声明方法
        身份(四分离)。"""
        units, now = sample()
        points = find_first_points(units, bars(), now, 'main')
        self.assertEqual(len(points), 1)
        point = points[0]
        self.assertEqual((point.method, point.kind), ('macd_area', 'buy1'))
        self.assertGreater(point.reference_area, point.leave_area)
        scan = scan_strict_divergence(units, now, 'main')
        self.assertEqual(len(scan.results), 1)
        r = scan.results[0]
        self.assertEqual((r.status, r.reason),
                         (STRICT_INSUFFICIENT, 'force_missing'))
        self.assertIsNone(r.force_method)
        self.assertEqual(r.trend_id, point.trend_id)

        def macd_area_force(reference, leave):
            return (point.reference_area, point.leave_area)

        confirmed = scan_strict_divergence(units, now, 'main',
                                           macd_area_force, 'macd_area')
        r2 = confirmed.results[0]
        self.assertEqual((r2.status, r2.reason),
                         (STRICT_CONFIRMED, 'force_decline'))
        self.assertEqual(r2.force_method, 'macd_area')
        self.assertEqual(r2.force_reference, point.reference_area)
        self.assertEqual(r2.force_leave, point.leave_area)


if __name__ == "__main__":
    unittest.main()
