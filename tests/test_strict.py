# -*- coding: utf-8 -*-
"""课24/27/37/53/61/101: 严格趋势背驰结构条件与四类返回语义(R3规格§11.6)。"""
import unittest
from datetime import datetime, timedelta

from chan import (ConfirmedMove, STRICT_CANDIDATE, STRICT_CONFIRMED,
                  STRICT_INSUFFICIENT, STRICT_REJECTED, StrictScan,
                  scan_strict_divergence, travel_force)

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


if __name__ == "__main__":
    unittest.main()
