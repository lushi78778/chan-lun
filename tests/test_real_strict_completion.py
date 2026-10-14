# -*- coding: utf-8 -*-
"""课35/37: R3 次级走势完成级联确认真实5m收据(0.10.5)。

输入沿用R2独立冻结的518880-5m-20260501-20260724样本与0.10.4链
收据同源(test_real_strict_chain.py): 父级单元取冻结XD表包装为
ConfirmedMove(级别名'xd'), 细级层取全窗口5m固定笔链(chan_fx_bi
课106标准, fixed=bis[:-1])按冻结台账到达约定包装(级别名'bi')。

冻结结论(2026-10-14):

- 五个链收据候选时刻(06-04/06-05/06-09/06-11/07-20)父级端点
  单元(u11/u12/u13/u14/u37)起点均在笔链边界精确切开且端点价格
  与原始行情close精确相等——起点切分与价格坐标两层证据对齐;
- 端点单元完成不可由自动笔链复核: 每时刻级联登记unverified。
  已知分解差异(0.10.3登记口径): R2人工XD标注终点早于自动
  bi→xd分解, 如06-09端点u13人工区间[2026-06-04 13:20,
  2026-06-08 14:45]9.311->8.937, 自动xd类型自同一起点9.311
  延伸至[2026-06-09 13:50]9.046; 晚期视野(末笔台账时刻)下仍
  unverified, 证明是分解口径差异而非完成证据未到达, 不判
  实现或标注错误;
- 自动路径如实登记: 全窗口24个自动xd类型在'trend'级扫描无
  结果, 自动路径无可冻结级联收据。

本收据不证明R2人工XD标注正确(由R2测试承担), 不以自动分解
覆盖人工口径; 级联语义按声明证据逐层复核, 差异登记不仲裁。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan
from chan import (ConfirmedMove, confirm_level_up,
                  scan_strict_divergence, strict_completion_cascade)

CASE_ID = '518880-5m-20260501-20260724'

# 级联收据: (观察时刻, 端点单元, 起止原始行号, 端点起点价格)。
RECEIPT = (
    ('2026-06-04 14:06:00', 'u11', 661, 687, 9.414),
    ('2026-06-05 14:01:00', 'u12', 687, 709, 9.268),
    ('2026-06-09 14:26:00', 'u13', 709, 782, 9.311),
    ('2026-06-11 11:16:00', 'u14', 782, 804, 8.937),
    ('2026-07-20 13:36:00', 'u37', 1691, 1720, 8.373),
)

# 06-09端点u13的已知分解差异: 自动xd类型自同一起点延伸的终点。
AUTO_TYPE_END = '2026-06-09 13:50:00'
AUTO_TYPE_PRICE = 9.046


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
        bars.append(dict(dt=datetime.strptime(row['dt'],
                                              '%Y-%m-%d %H:%M:%S'),
                         open=row['open'], high=row['high'],
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


def bi_units(case):
    """细级层: 全窗口固定笔链按冻结台账到达约定包装。"""
    _, _, bis = chan.chan_fx_bi(raw_bars(case), standard=case['standard'])
    fixed = bis[:-1]
    rows = case['raw_rows']
    ledger = case['foundation']['bis_confirmed_raw_count']
    if len(fixed) != len(ledger):
        raise AssertionError('固定笔链与台账长度须一致')
    out = []
    for i, bi in enumerate(fixed):
        stamp = datetime.strptime(rows[ledger[i] - 1]['dt'],
                                  '%Y-%m-%d %H:%M:%S')
        out.append(ConfirmedMove(
            'b%d' % i, 'bi', bi.direction, bi.start_dt, bi.end_dt,
            bi.start_value, bi.end_value, bi.low, bi.high,
            stamp + timedelta(minutes=1)))
    return out


class TestRealStrictCompletion5m(unittest.TestCase):
    def test_endpoint_start_alignment_and_unverified_receipt(self):
        """五时刻端点起点对齐笔链边界与价格, 完成复核登记unverified。"""
        case = load_case()
        units = parent_units(case)
        chain = bi_units(case)
        by_name = dict((u.move_id, u) for u in units)
        table = dict(('u%d' % i, unit)
                     for i, unit in enumerate(case['units']))
        last_stamp = max(b.confirmed_dt for b in chain)
        for cut_text, endpoint_id, start_index, end_index, price in RECEIPT:
            cut = _parse(cut_text)
            scan = scan_strict_divergence(units, cut, 'trend')
            self.assertEqual(len(scan.results), 1, cut_text)
            r = scan.results[0]
            self.assertEqual(r.leave_ids[-1], endpoint_id, cut_text)
            endpoint = by_name[endpoint_id]
            raw = table[endpoint_id]
            # 端点单元冻结区间与价格。
            self.assertEqual((raw['start_index'], raw['end_index']),
                             (start_index, end_index), cut_text)
            self.assertEqual(endpoint.start_price, price, cut_text)
            # 起点在笔链边界精确切开且价格相等(两层证据坐标对齐)。
            hit = [b for b in chain if b.start_dt == endpoint.start_dt]
            self.assertEqual(len(hit), 1, cut_text)
            self.assertEqual(hit[0].start_price, endpoint.start_price,
                             cut_text)
            # 完成不可由自动笔链复核: 已知分解差异登记unverified。
            cascade = strict_completion_cascade(r, units, [('bi', chain)],
                                                cut)
            self.assertEqual(cascade.divergence_id, r.divergence_id,
                             cut_text)
            self.assertEqual(cascade.depth, 1, cut_text)
            self.assertFalse(cascade.complete, cut_text)
            lv = cascade.levels[0]
            self.assertEqual((lv.depth, lv.level, lv.unit_id, lv.status),
                             (1, 'bi', endpoint_id, 'unverified'), cut_text)
            self.assertEqual(lv.unit_ids, (), cut_text)
            self.assertIsNone(lv.confirmed_dt, cut_text)
            self.assertEqual(cascade.confirmed_dt, cut, cut_text)
            # 晚期视野仍unverified: 分解差异而非证据未到达。
            late = strict_completion_cascade(r, units, [('bi', chain)],
                                             last_stamp)
            self.assertEqual(late.levels[0].status, 'unverified', cut_text)
            self.assertFalse(late.complete, cut_text)

    def test_known_decomposition_difference_on_u13(self):
        """06-09端点u13: 自动xd类型自同一起点9.311延伸至更晚终点。"""
        case = load_case()
        units = parent_units(case)
        chain = bi_units(case)
        last_stamp = max(b.confirmed_dt for b in chain)
        by_name = dict((u.move_id, u) for u in units)
        cut = _parse('2026-06-09 14:26:00')
        r = scan_strict_divergence(units, cut, 'trend').results[0]
        endpoint = by_name[r.leave_ids[-1]]
        self.assertEqual(endpoint.start_price, 9.311)
        self.assertEqual(endpoint.end_dt, _parse('2026-06-08 14:45:00'))
        self.assertEqual(endpoint.end_price, 8.937)
        visible = [b for b in chain if b.confirmed_dt <= last_stamp]
        low = next(i for i, b in enumerate(visible)
                   if b.start_dt == endpoint.start_dt)
        types = confirm_level_up(visible[low:], last_stamp, 'xd')
        self.assertTrue(types)
        first = types[0]
        # 同一起点同价延伸至更晚终点: 人工标注与自动分解口径差异。
        self.assertEqual(first.start_dt, endpoint.start_dt)
        self.assertEqual(first.start_price, endpoint.start_price)
        self.assertEqual(first.end_dt, _parse(AUTO_TYPE_END))
        self.assertEqual(first.end_price, AUTO_TYPE_PRICE)
        self.assertNotEqual(first.end_dt, endpoint.end_dt)
        self.assertNotEqual(first.end_price, endpoint.end_price)

    def test_automatic_xd_path_has_no_scan_receipt(self):
        """自动xd路径如实登记: 全窗口自动类型在trend级扫描无结果。"""
        case = load_case()
        chain = bi_units(case)
        last_stamp = max(b.confirmed_dt for b in chain)
        xd_types = confirm_level_up(chain, last_stamp, 'xd')
        self.assertEqual(len(xd_types), 24)
        moments = []
        for item in xd_types:
            if not moments or moments[-1] != item.confirmed_dt:
                moments.append(item.confirmed_dt)
        for cut in moments:
            scan = scan_strict_divergence(xd_types, cut, 'trend')
            self.assertEqual(scan.results, (), cut)


if __name__ == '__main__':
    unittest.main()
