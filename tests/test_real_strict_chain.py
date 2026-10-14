# -*- coding: utf-8 -*-
"""课27/61: R3 区间套次级确认链真实5m冒烟收据(0.10.4)。

输入为R2独立冻结的真实严格趋势标注样本518880-5m-20260501-20260724
(人工表经独立整数编译器冻结, 见test_real_strict_trend_5m.py)。父级
单元取冻结XD表包装为ConfirmedMove(扫描级别名'trend'), 子级单元取
全窗口5m固定笔链(chan_fx_bi课106标准, fixed=bis[:-1])按父级c段区间
精确切片包装为ConfirmedMove(级别名'bi')。子级确认时刻取R2冻结台账
foundation['bis_confirmed_raw_count']的到达约定(原始bar结束+1分钟,
逐前缀回放首确认), 不用分型端点或右K时间回填。

链评估只在父级扫描出现结果的演进时刻进行(末观察无结果, 见
test_real_strict_divergence.py收据)。冻结结论(2026-10-14):

- 06-04/06-05/07-20三个候选时刻c段内子级中枢在区间首单元起,
  对照窗口不可建立(no_compare_legs), 登记证据不足;
- 06-09候选时刻子级窗口成立(reference=b100, leave=b104-b106,
  子级中枢(9.224,9.245)), 力度未注入登记force_missing;
- 06-11候选时刻子级背驰段(b108,b109)低点9.011未破前低8.937,
  依课61"背驰如果没有创新低, 那是不存在的"否决父级c段假设
  (no_new_extreme, break_depth=1), 与行情自8.937反弹一致;
- 全部时刻链depth=1、无bc重、转折为空, 链确认时刻等于观察时刻;
- 子级切片由截断前缀固定链重算与全窗口切片逐项相等(子级无未来
  信息)。

本收据不证明5m笔识别正确(由R2测试承担), 不冒充理论力度度量;
travel_force为工程示例方法, 注入结论只代表该方法口径。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan
from chan import (ConfirmedMove, STRICT_CANDIDATE, STRICT_INSUFFICIENT,
                  STRICT_REJECTED, scan_strict_divergence,
                  strict_nested_chain, travel_force)

CASE_ID = '518880-5m-20260501-20260724'

# 候选时刻冻结收据: (观察时刻, 父级leave_ids, 重2状态, 语义,
# None或(reference_ids, leave_ids, center_range, dt, price))
RECEIPT = (
    ('2026-06-04 14:06:00', ('u11',), 'no_compare_legs',
     STRICT_INSUFFICIENT, None),
    ('2026-06-05 14:01:00', ('u11', 'u12'), 'no_compare_legs',
     STRICT_INSUFFICIENT, None),
    ('2026-06-09 14:26:00', ('u11', 'u12', 'u13'), 'force_missing',
     STRICT_INSUFFICIENT,
     (('b100',), ('b104', 'b105', 'b106'), (9.224, 9.245),
      '2026-06-08 14:45:00', 8.937)),
    ('2026-06-11 11:16:00', ('u11', 'u12', 'u13', 'u14'),
     'no_new_extreme', STRICT_REJECTED,
     (('b104',), ('b108', 'b109'), (8.969, 8.985),
      '2026-06-09 13:50:00', 9.011)),
    ('2026-07-20 13:36:00', ('u37',), 'no_compare_legs',
     STRICT_INSUFFICIENT, None),
)


def _parse(text):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError('无法解析冻结时间: %r' % text)


def load_case():
    """加载R2冻结样本; 不重新生成预期、不调用编译器。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_strict_trend_5m.json')
    with open(path, encoding='utf-8') as stream:
        data = json.load(stream)
    for case in data['cases']:
        if case['id'] == CASE_ID:
            return case
    raise AssertionError('缺少冻结样本: %s' % CASE_ID)


def raw_bars(case):
    """原始5m行情; 恒1因子样本不隐含暖机或复权。"""
    bars = []
    for row in case['raw_rows']:
        if row['adj_factor'] != 1:
            raise ValueError('新因子样本须另行冻结观察锚算术')
        dt = datetime.strptime(row['dt'], '%Y-%m-%d %H:%M:%S')
        bars.append(dict(dt=dt, open=row['open'], high=row['high'],
                         low=row['low'], close=row['close'],
                         volume=row['vol']))
    return bars


def parent_units(case):
    """父级单元: 冻结XD表包装, 级别名沿用R2样本级别。"""
    units = []
    for i, unit in enumerate(case['units']):
        units.append(ConfirmedMove(
            'u%d' % i, case['level'], unit['direction'],
            _parse(unit['start_dt']), _parse(unit['end_dt']),
            unit['start_ticks'] / 1000.0, unit['end_ticks'] / 1000.0,
            unit['low_ticks'] / 1000.0, unit['high_ticks'] / 1000.0,
            _parse(unit['confirmed_dt'])))
    return units


def wrap_slice(fixed, ledger, rows, low, high):
    """固定笔[low,high]切片包装; 确认时刻取冻结台账到达约定。"""
    out = []
    for i in range(low, high + 1):
        bi = fixed[i]
        stamp = datetime.strptime(rows[ledger[i] - 1]['dt'],
                                  '%Y-%m-%d %H:%M:%S')
        out.append(ConfirmedMove(
            'b%d' % i, 'bi', bi.direction, bi.start_dt, bi.end_dt,
            bi.start_value, bi.end_value, bi.low, bi.high,
            stamp + timedelta(minutes=1)))
    return out


class TestRealStrictChain5m(unittest.TestCase):
    def _sub_slice(self, case, fixed, result):
        """父级c段区间上的固定笔切片; 边界笔须唯一回溯。"""
        rows = case['raw_rows']
        table = dict(('u%d' % i, unit)
                     for i, unit in enumerate(case['units']))
        starts, ends = {}, {}
        for i, bi in enumerate(fixed):
            starts.setdefault(bi.start_index, []).append(i)
            ends.setdefault(bi.end_index, []).append(i)
        start = table[result.leave_ids[0]]['start_index']
        end = table[result.leave_ids[-1]]['end_index']
        if len(starts[start]) != 1 or len(ends[end]) != 1:
            raise AssertionError('c段边界笔须唯一回溯')
        return wrap_slice(fixed, case['foundation']['bis_confirmed_raw_count'],
                          rows, starts[start][0], ends[end][0])

    def test_candidate_moments_match_frozen_receipt(self):
        """演进候选时刻的链输出与冻结收据一致; 候选时刻不多不少。"""
        case = load_case()
        units = parent_units(case)
        bars = raw_bars(case)
        _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
        fixed = bis[:-1]
        self.assertEqual(
            len(fixed), len(case['foundation']['bis_confirmed_raw_count']))
        by_id = dict((u.move_id, u) for u in units)
        moments = []
        for unit in units:
            if not moments or moments[-1] != unit.confirmed_dt:
                moments.append(unit.confirmed_dt)
        hits = []
        for cut in moments:
            scan = scan_strict_divergence(units, cut, 'trend')
            if not scan.results:
                continue
            hits.append(cut)
            self.assertEqual(len(scan.results), 1, cut)
            r = scan.results[0]
            self.assertEqual(r.status, STRICT_CANDIDATE, cut)
            entry = next(item for item in RECEIPT
                         if _parse(item[0]) == cut)
            # R2趋势方向down -> buy1; c段组成与收据一致。
            self.assertEqual(r.kind, 'buy1', cut)
            self.assertEqual(r.leave_ids, entry[1], cut)
            leave = [by_id[name] for name in r.leave_ids]
            sub = self._sub_slice(case, fixed, r)
            # 切片须精确覆盖父级c段区间且端点价格对齐。
            self.assertEqual(sub[0].start_dt, leave[0].start_dt, cut)
            self.assertEqual(sub[-1].end_dt, leave[-1].end_dt, cut)
            self.assertEqual(sub[0].start_price,
                             leave[0].start_price, cut)
            self.assertEqual(sub[-1].end_price,
                             leave[-1].end_price, cut)
            chain = strict_nested_chain(r, units, [('bi', sub)], cut)
            self.assertEqual(chain.divergence_id, r.divergence_id, cut)
            self.assertEqual((chain.kind, chain.level),
                             ('buy1', 'trend'), cut)
            self.assertEqual(chain.depth, 1, cut)
            self.assertFalse(chain.complete, cut)
            self.assertIsNone(chain.turn_dt, cut)
            self.assertIsNone(chain.turn_price, cut)
            self.assertEqual(chain.confirmed_dt, cut, cut)
            lv = chain.levels[0]
            self.assertEqual((lv.depth, lv.level), (1, 'bi'), cut)
            self.assertEqual((lv.status, lv.reason),
                             (entry[2], entry[3]), cut)
            self.assertEqual(lv.force_method, None, cut)
            detail = entry[4]
            if detail is None:
                self.assertEqual(lv.reference_ids, (), cut)
                self.assertEqual(lv.leave_ids, (), cut)
                self.assertIsNone(lv.center_range, cut)
                self.assertIsNone(lv.dt, cut)
                self.assertIsNone(lv.price, cut)
                self.assertIsNone(chain.break_depth, cut)
                self.assertIsNone(chain.break_reason, cut)
                continue
            reference_ids, leave_ids, center, dt_text, price = detail
            self.assertEqual(lv.reference_ids, reference_ids, cut)
            self.assertEqual(lv.leave_ids, leave_ids, cut)
            self.assertEqual(lv.center_range, center, cut)
            self.assertEqual(lv.dt, _parse(dt_text), cut)
            self.assertEqual(lv.price, price, cut)
            # 确认不早于被消费证据; 背驰段终点不晚于确认。
            consumed = [u for u in sub
                        if u.move_id in reference_ids or
                        u.move_id in leave_ids]
            self.assertGreaterEqual(
                lv.confirmed_dt, max(u.confirmed_dt for u in consumed),
                cut)
            self.assertLessEqual(lv.dt, lv.confirmed_dt, cut)
            if entry[3] == STRICT_REJECTED:
                self.assertEqual(
                    (chain.break_depth, chain.break_reason),
                    (1, entry[2]), cut)
            else:
                self.assertIsNone(chain.break_depth, cut)
                self.assertIsNone(chain.break_reason, cut)
        self.assertEqual([cut.strftime('%Y-%m-%d %H:%M:%S')
                          for cut in hits],
                         [entry[0] for entry in RECEIPT])

    def test_force_injection_semantics_on_real_windows(self):
        """行程示例力度注入: 06-09力度不减否决; 06-11结构否决先于力度。"""
        case = load_case()
        units = parent_units(case)
        bars = raw_bars(case)
        _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
        fixed = bis[:-1]
        open_cut = _parse('2026-06-09 14:26:00')
        r = scan_strict_divergence(units, open_cut, 'trend').results[0]
        sub = self._sub_slice(case, fixed, r)
        wrapped = dict((u.move_id, u) for u in sub)

        def fn(reference, leave):
            return (travel_force(reference), travel_force(leave))

        chain = strict_nested_chain(r, units, [('bi', sub)], open_cut,
                                    force_fn=fn,
                                    force_method='unit_travel')
        lv = chain.levels[0]
        self.assertEqual((lv.status, lv.reason),
                         ('force_not_declining', STRICT_REJECTED),
                         open_cut)
        self.assertEqual(lv.force_method, 'unit_travel', open_cut)
        self.assertEqual(
            lv.force_reference,
            travel_force([wrapped[name] for name in lv.reference_ids]),
            open_cut)
        self.assertEqual(
            lv.force_leave,
            travel_force([wrapped[name] for name in lv.leave_ids]),
            open_cut)
        # 力度不减: leave 行程 0.353 不小于 ref 行程 0.086。
        self.assertGreaterEqual(lv.force_leave, lv.force_reference)
        self.assertEqual((chain.break_depth, chain.break_reason),
                         (1, 'force_not_declining'), open_cut)
        # 06-11结构否决先于力度评估, 注入方法不被消费。
        reject_cut = _parse('2026-06-11 11:16:00')
        r2 = scan_strict_divergence(units, reject_cut, 'trend').results[0]
        sub2 = self._sub_slice(case, fixed, r2)
        calls = []

        def counting_fn(reference, leave):
            calls.append(1)
            return (1.0, 0.5)

        chain2 = strict_nested_chain(r2, units, [('bi', sub2)], reject_cut,
                                     force_fn=counting_fn,
                                     force_method='unit_travel')
        self.assertEqual(chain2.levels[0].status, 'no_new_extreme',
                         reject_cut)
        self.assertEqual(calls, [], reject_cut)

    def test_sub_slice_prefix_equivalence(self):
        """子级切片由截断前缀固定链重算与全窗口切片一致, 无未来信息。"""
        case = load_case()
        units = parent_units(case)
        bars = raw_bars(case)
        _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
        fixed = bis[:-1]
        for entry in RECEIPT:
            cut = _parse(entry[0])
            r = scan_strict_divergence(units, cut, 'trend').results[0]
            sub = self._sub_slice(case, fixed, r)
            count = max(unit['confirmed_raw_count']
                        for unit in case['units']
                        if _parse(unit['confirmed_dt']) == cut)
            _, _, prefix_bis = chan.chan_fx_bi(
                bars[:count], standard=case['standard'])
            prefix_fixed = prefix_bis[:-1]
            self.assertGreater(len(prefix_fixed), len(sub) - 1, cut)
            prefix_sub = self._sub_slice(case, prefix_fixed, r)
            self.assertEqual(prefix_sub, sub, cut)
            self.assertEqual(
                strict_nested_chain(r, units, [('bi', prefix_sub)], cut),
                strict_nested_chain(r, units, [('bi', sub)], cut), cut)


if __name__ == '__main__':
    unittest.main()
