# -*- coding: utf-8 -*-
"""课17/20/24/27/29/106: R2 0.9.9 一类买卖点真实正反例标注。

预期由原始行情、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。五案例因子恒为1, 价格
单位0.001。一类买卖点裁定: 先为完成严格趋势(0.9.3口径: A/B中枢
Zn冻结、c离开最后中枢核心、证明段紧随c自外侧回核心、gap>0);
MACD(12,26,9)固定EMA自窗口首行起算, hist=(DIF-DEA)*2; 面积=b/c
单元同方向柱正幅值和, 区间(start,end](课24行31-33); 新极值=c
极值超越全趋势先验极值(a或A首Zn成员..B.zn[-1]); 成立=完成严格
趋势+0<area_c<area_b+c创新极值; 不成立二分no_divergence/
no_new_extreme; 零轴回拉max(|DIF|,|DEA|)/close于B zn区间最小值
仅记录性登记, 不作裁定门槛(课24明示MACD不绝对精确)。裁定可见
时刻=证明段单元首确认, first_raw_count按逐原始bar前缀首次可见
冻结; 分型/笔端点时间不等于确认时间, 禁止确认时间回填。60m/5m
bar以结束时刻为标签, 到达按结束+1分钟计; 日线到达15:05(测试
约定)。覆盖: buy1成立x1、sell1成立x1、no_divergence x1、
no_new_extreme x2。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_first_point.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def raw_bars(case):
    """保留全部源行与完整bar时刻; 恒1因子样本不隐含暖机或复权。"""
    bars = []
    for row in case['raw_rows']:
        if row['adj_factor'] != 1:
            raise ValueError('新因子样本须另行冻结每个观察锚的算术')
        dt = datetime.strptime(row['dt'], '%Y-%m-%d %H:%M:%S')
        bars.append(dict(dt=dt, open=row['open'], high=row['high'],
                         low=row['low'], close=row['close'],
                         volume=row['vol']))
    return bars


def bi_records(bis):
    """笔五元组; 比较以人工整数价位表为准。"""
    return [[bi.direction, bi.start_index, bi.end_index,
             round(bi.start_value * 1000), round(bi.end_value * 1000)]
            for bi in bis]


def arrival(count, rows, granularity):
    """到达时刻测试约定: 日线收盘日15:05; 分钟按bar结束+1分钟。"""
    if granularity == 'day':
        return rows[count - 1]['dt'][:10] + ' 15:05:00'
    stamp = datetime.strptime(rows[count - 1]['dt'], '%Y-%m-%d %H:%M:%S')
    return (stamp + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')


def bi_unit_record(bi, count, rows, granularity):
    """固定笔序列化; 内部极值不改写端点bar时刻; day单元时刻取日期。"""
    width = 10 if granularity == 'day' else None
    return dict(start_index=bi.start_index, end_index=bi.end_index,
                start_ticks=round(bi.start_value * 1000),
                end_ticks=round(bi.end_value * 1000),
                start_dt=str(bi.start_dt)[:width],
                end_dt=str(bi.end_dt)[:width],
                low_ticks=round(bi.low * 1000), high_ticks=round(bi.high * 1000),
                direction=bi.direction, confirmed_raw_count=count,
                confirmed_dt=arrival(count, rows, granularity))


def xd_events(xds, fixed):
    """完成XD事件表[a,z,mode,proof]; proof为固定笔序列零基下标。"""
    out = []
    for xd in xds:
        starts = [i for i, bi in enumerate(fixed)
                  if bi.start_index == xd.start_index]
        ends = [i for i, bi in enumerate(fixed)
                if bi.end_index == xd.end_index]
        proofs = [i for i, bi in enumerate(fixed)
                  if bi.end_index == xd.evidence_end_index]
        if not (len(starts) == len(ends) == len(proofs) == 1):
            raise AssertionError('完成XD组成/证明须在固定笔内唯一回溯')
        out.append([starts[0], ends[0], xd.mode, proofs[0]])
    return out


def xd_unit_record(xd, fixed, count, rows, granularity):
    """完成XD序列化: 组成范围、模式、唯一证据笔与首确认。"""
    matches = [i for i, bi in enumerate(fixed)
               if bi.end_index == xd.evidence_end_index and
               bi.end_dt == xd.evidence_dt]
    if len(matches) != 1:
        raise AssertionError('完成XD须有唯一可回溯证据笔')
    return dict(start_index=xd.start_index, end_index=xd.end_index,
                start_ticks=round(xd.start_value * 1000),
                end_ticks=round(xd.end_value * 1000),
                start_dt=str(xd.start_dt), end_dt=str(xd.end_dt),
                low_ticks=round(xd.low * 1000),
                high_ticks=round(xd.high * 1000),
                direction=xd.direction, mode=xd.mode,
                proof_bi=matches[0],
                evidence_end_index=xd.evidence_end_index,
                evidence_dt=str(xd.evidence_dt),
                confirmed_raw_count=count,
                confirmed_dt=arrival(count, rows, granularity))


def library_units(case):
    """全窗口库链单元: bi级为固定笔, xd级为完成XD(不含尾部)。"""
    bars = raw_bars(case)
    _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
    fixed = bis[:-1]
    if case['level'] == 'bi':
        return fixed
    return [xd for xd in chan.find_xds(fixed) if xd.complete]


def unit_counts(case):
    """单元首确认原始bar计数: bi级取固定笔表, xd级取冻结单元表。"""
    if case['level'] == 'bi':
        return case['foundation']['bis_confirmed_raw_count']
    return [unit['confirmed_raw_count'] for unit in case['units']]


def unit_ticks(units):
    """一类算术只消费整数区间与方向, 不读端点时间。"""
    return [dict(low_ticks=round(unit.low * 1000),
                 high_ticks=round(unit.high * 1000),
                 start_dt=(str(unit.start_dt)[:10] if
                           str(unit.start_dt)[11:] == '00:00:00'
                           else str(unit.start_dt)),
                 end_dt=(str(unit.end_dt)[:10] if
                         str(unit.end_dt)[11:] == '00:00:00'
                         else str(unit.end_dt)),
                 direction=unit.direction) for unit in units]


def ema(values, n):
    """固定EMA: 首值种子values[0], k=2/(n+1); 与冻结口径一致。"""
    out = [0.0] * len(values)
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def raw_index(rows, unit_dt, granularity, last=False):
    """单元端点映射原始行下标: 日线按日期, 分钟按完整bar标签。"""
    key = unit_dt if granularity != 'day' else unit_dt[:10]
    hits = [i for i, row in enumerate(rows)
            if (row['dt'] if granularity != 'day'
                else row['dt'][:10]) == key]
    if not hits:
        raise AssertionError('单元端点不在原始行: ' + str(unit_dt))
    return hits[-1] if last else hits[0]


class TestRealFirstPoint(unittest.TestCase):
    def rederive_center(self, ticks, spec, context):
        """课17/20/29: 库单元上重推中枢算术; zn成员为人工声明结构。

        Zn同向步2、首对核心、中间覆盖、延伸触沿、DD/GG包络全部重算
        并与声明比对。状态算术: closed_by非null时封口单元=zn[-1]+2
        且不触沿; frozen_by_departure=true时中间反向单元离开核心且
        同向后继存在并触沿(课29行20-26离开后定界, 仅趋势末中枢);
        二者互斥; 均缺席时zn[-1]+2须越界(窗口末开放中枢)。
        """
        zn = spec['zn']
        self.assertGreaterEqual(len(zn), 2, context)
        for i in range(1, len(zn)):
            self.assertEqual(zn[i], zn[i - 1] + 2, (context, 'Zn同向步2'))
        direction = ticks[zn[0]]['direction']
        for i in zn:
            self.assertEqual(ticks[i]['direction'], direction,
                             (context, 'Zn成员方向'))
        first, second = ticks[zn[0]], ticks[zn[1]]
        zd = max(first['low_ticks'], second['low_ticks'])
        zg = min(first['high_ticks'], second['high_ticks'])
        self.assertLessEqual(zd, zg, (context, '首对核心为空'))
        self.assertEqual([zd, zg], [spec['zd'], spec['zg']],
                         (context, '首对核心与声明不一致'))
        middle = ticks[zn[0] + 1]
        self.assertLessEqual(middle['low_ticks'], zd,
                             (context, '中间单元未覆盖核心下沿'))
        self.assertGreaterEqual(middle['high_ticks'], zg,
                                (context, '中间单元未覆盖核心上沿'))
        for i in zn[2:]:
            unit = ticks[i]
            self.assertTrue(unit['low_ticks'] <= zg and
                            unit['high_ticks'] >= zd,
                            (context, '延伸单元未触沿', i))
        span = ticks[zn[0]:zn[-1] + 1]
        dd = min(unit['low_ticks'] for unit in span)
        gg = max(unit['high_ticks'] for unit in span)
        self.assertEqual([dd, gg], [spec['dd'], spec['gg']],
                         (context, 'DD/GG包络与声明不一致'))
        closed_by = spec['closed_by']
        frozen = spec.get('frozen_by_departure', False)
        self.assertIsInstance(frozen, bool, (context, 'frozen须为布尔'))
        if closed_by is None:
            if frozen:
                self.assertLess(zn[-1] + 2, len(ticks),
                                (context, '离开冻结须后继存在'))
                mid = ticks[zn[-1] + 1]
                self.assertNotEqual(mid['direction'], direction,
                                    (context, '冻结判定单元须为反向'))
                if direction == 'down':
                    self.assertGreater(mid['high_ticks'], zg,
                                       (context, '冻结须反向单元离开核心'))
                else:
                    self.assertLess(mid['low_ticks'], zd,
                                    (context, '冻结须反向单元离开核心'))
                successor = ticks[zn[-1] + 2]
                self.assertEqual(successor['direction'], direction,
                                 (context, '冻结须同向后继存在（承重）'))
                self.assertTrue(successor['low_ticks'] <= zg and
                                successor['high_ticks'] >= zd,
                                (context, '冻结承重：同向后继须触沿'))
            else:
                self.assertGreaterEqual(zn[-1] + 2, len(ticks),
                                        (context, '开放中枢不得有同向后继'))
        else:
            self.assertFalse(frozen, (context, 'closed_by与frozen互斥'))
            self.assertEqual(closed_by, zn[-1] + 2,
                             (context, '封口单元须为zn[-1]+2'))
            unit = ticks[closed_by]
            self.assertFalse(unit['low_ticks'] <= zg and
                             unit['high_ticks'] >= zd,
                             (context, '封口单元不得触沿'))
        return dict(zn=list(zn), zd=zd, zg=zg, dd=dd, gg=gg,
                    closed_by=closed_by, frozen_by_departure=frozen)

    def derive_ledger_events(self, roles, centers):
        """台账事件由角色推导; 同单元内固定顺序, 时间不回填。"""
        events = []

        def add_center(prefix, center):
            events.append((prefix + '_open', center['zn'][0] + 2))
            for i in center['zn'][2:]:
                events.append((prefix + '_zn_extend', i))
            if center['closed_by'] is not None:
                events.append((prefix + '_closed', center['closed_by']))

        add_center('A', centers['A'])
        events.append(('b_fixed', roles['b']['unit']))
        add_center('B', centers['B'])
        events.append(('c_fixed', roles['c']['unit']))
        events.append(('c_departed' if roles['c']['outcome'] == 'departed'
                       else 'c_fail', roles['c']['unit']))
        if roles.get('proof') is not None:
            events.append(('proof_fixed', roles['proof']['unit']))
        rank = {'extend': 0, 'closed': 1, 'open': 2, 'fixed': 3,
                'departed': 4, 'fail': 4, 'determined': 5}
        events.sort(key=lambda item: (item[1], rank[item[0].rsplit('_', 1)[1]]))
        return events

    def test_library_structure_matches_frozen_labels(self):
        """课65/67: 库全窗口链与冻结结构逐字段一致; 不读标签外预期。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            granularity = case.get('granularity', 'day')
            _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
            fixed = bis[:-1]
            self.assertEqual(bi_records(bis), case['foundation']['bis'],
                             case['id'])
            counts = unit_counts(case)
            rows = case['raw_rows']
            if case['level'] == 'bi':
                self.assertEqual(len(fixed), len(counts), case['id'])
                self.assertEqual(
                    [bi_unit_record(bi, counts[i], rows, granularity)
                     for i, bi in enumerate(fixed)],
                    case['units'], case['id'])
            else:
                xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                self.assertEqual(xd_events(xds, fixed),
                                 case['foundation']['xd_events'], case['id'])
                self.assertEqual(
                    [xd_unit_record(xd, fixed, counts[i], rows, granularity)
                     for i, xd in enumerate(xds)],
                    case['units'], case['id'])

    def test_every_raw_prefix_replays_frozen_chain_and_first_confirmation(self):
        """课65/67/78: 逐原始bar前缀重放; 链前缀稳定、无撤销、首确认
        恰合; 一类裁定可见恰为证明段单元首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            foundation = case['foundation']
            frozen = foundation['bis']
            events = foundation.get('xd_events') or []
            granularity = case.get('granularity', 'day')
            rows = case['raw_rows']
            bi_seen, xd_seen = {}, {}
            previous, computed = 0, -1
            for count in range(1, len(bars) + 1):
                _, _, bis = chan.chan_fx_bi(bars[:count],
                                            standard=case['standard'])
                fixed = bis[:-1]
                records = bi_records(bis)
                self.assertEqual(records[:len(fixed)], frozen[:len(fixed)],
                                 (case['id'], count, '固定链漂移'))
                self.assertGreaterEqual(len(fixed), previous,
                                        (case['id'], count, '固定笔撤销'))
                previous = len(fixed)
                for i in range(len(fixed)):
                    bi_seen.setdefault(i, count)
                if case['level'] == 'xd' and len(fixed) != computed:
                    xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                    visible = [event for event in events
                               if event[3] < len(fixed)]
                    self.assertEqual(xd_events(xds, fixed), visible,
                                     (case['id'], count, '完成XD恰合冻结事件'))
                    for k in range(len(visible)):
                        xd_seen.setdefault(k, count)
                    computed = len(fixed)
            self.assertEqual(
                [bi_seen[i] for i in range(len(foundation['bis_confirmed_raw_count']))],
                foundation['bis_confirmed_raw_count'], case['id'])
            unit_seen = (xd_seen if case['level'] == 'xd' else bi_seen)
            self.assertEqual(
                [unit_seen[i] for i in range(len(case['units']))],
                unit_counts(case), case['id'])
            counts = unit_counts(case)
            for entry in case['ledger']:
                context = (case['id'], entry['event'])
                self.assertEqual(entry['first_raw_count'],
                                 unit_seen[entry['unit']], context)
                self.assertEqual(
                    entry['first_dt'],
                    arrival(entry['first_raw_count'], rows, granularity),
                    context)
            first = case['first_point']
            proof = first['proof_unit']
            self.assertEqual(first['first_raw_count'],
                             unit_seen[proof], case['id'])
            self.assertEqual(first['first_dt'],
                             arrival(first['first_raw_count'], rows,
                                     granularity), case['id'])
            self.assertEqual(first['first_raw_count'],
                             counts[proof], case['id'])

    def test_strict_trend_roles_rederived_from_library_units(self):
        """课17/20/29: 库单元重推A/B中枢、b/c/证明段角色、gap与台账。"""
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            self.assertEqual(trend['status'], 'completed', case['id'])
            centers = {}
            for name in ('A', 'B'):
                centers[name] = self.rederive_center(
                    ticks, roles[name], (case['id'], name))
            if roles['a'] is None:
                self.assertEqual(centers['A']['zn'][0], 0,
                                 (case['id'], 'a缺席时A首Zn成员须为单元0'))
            b = roles['b']['unit']
            self.assertEqual(b, centers['A']['zn'][-1] + 1,
                             (case['id'], 'b须为A.zn[-1]+1'))
            self.assertEqual(ticks[b]['direction'], trend['direction'],
                             (case['id'], 'b方向须与趋势同向'))
            if up:
                self.assertGreater(ticks[b]['high_ticks'], centers['A']['zg'],
                                   (case['id'], 'b未离开A核心'))
            else:
                self.assertLess(ticks[b]['low_ticks'], centers['A']['zd'],
                                (case['id'], 'b未离开A核心'))
            self.assertIn(centers['B']['zn'][0], (b, b + 1),
                          (case['id'], 'B首Zn成员须紧随b'))
            c = roles['c']['unit']
            self.assertEqual(c, centers['B']['zn'][-1] + 1,
                             (case['id'], 'c须为B.zn[-1]+1'))
            self.assertEqual(ticks[c]['direction'], trend['direction'],
                             (case['id'], 'c方向须与趋势同向'))
            self.assertEqual(roles['c']['outcome'], 'departed', case['id'])
            if up:
                self.assertGreater(ticks[c]['high_ticks'], centers['B']['zg'],
                                   (case['id'], 'c未离开B核心'))
            else:
                self.assertLess(ticks[c]['low_ticks'], centers['B']['zd'],
                                (case['id'], 'c未离开B核心'))
            proof = roles['proof']['unit']
            self.assertEqual(proof, c + 1,
                             (case['id'], '证明段须紧随c立即回核心'))
            if up:
                self.assertEqual(ticks[proof]['direction'], 'down',
                                 (case['id'], '证明段方向'))
                self.assertGreater(ticks[proof]['high_ticks'],
                                   centers['B']['zg'],
                                   (case['id'], '证明段须自外侧'))
                self.assertLessEqual(ticks[proof]['low_ticks'],
                                     centers['B']['zg'],
                                     (case['id'], '证明段须回B核心'))
            else:
                self.assertEqual(ticks[proof]['direction'], 'up',
                                 (case['id'], '证明段方向'))
                self.assertLess(ticks[proof]['low_ticks'],
                                centers['B']['zd'],
                                (case['id'], '证明段须自外侧'))
                self.assertGreaterEqual(ticks[proof]['high_ticks'],
                                        centers['B']['zd'],
                                        (case['id'], '证明段须回B核心'))
            self.assertTrue(centers['B']['frozen_by_departure'],
                            (case['id'], '完成须B按0.9.3离开冻结'))
            gap = (centers['B']['dd'] - centers['A']['gg'] if up
                   else centers['A']['dd'] - centers['B']['gg'])
            self.assertEqual(roles['gap_ticks'], gap, (case['id'], 'gap算术'))
            self.assertGreater(gap, 0, (case['id'], 'A与B包络重叠'))
            self.assertEqual(
                self.derive_ledger_events(roles, centers),
                [(entry['event'], entry['unit']) for entry in case['ledger']],
                (case['id'], '台账事件序列'))

    def test_first_point_arithmetic_rederived_from_raw_rows(self):
        """课24/27/29: 原始行重推MACD面积/新极值/零轴与裁定结局;
        覆盖买/卖成立与两类不成立原因。"""
        coverage = dict(buy1_established=0, sell1_established=0,
                        no_divergence=0, no_new_extreme=0)
        for case in load_labels()['cases']:
            rows = case['raw_rows']
            granularity = case.get('granularity', 'day')
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            sign = 1 if up else -1
            first = case['first_point']
            self.assertEqual(first['side'],
                             'sell1' if up else 'buy1', case['id'])
            b, c = roles['b']['unit'], roles['c']['unit']
            self.assertEqual(first['b_unit'], b, case['id'])
            self.assertEqual(first['c_unit'], c, case['id'])
            self.assertEqual(first['proof_unit'], roles['proof']['unit'],
                             case['id'])
            closes = [row['close'] for row in rows]
            fast, slow = ema(closes, 12), ema(closes, 26)
            dif = [x - y for x, y in zip(fast, slow)]
            dea = ema(dif, 9)
            hist = [(x - y) * 2.0 for x, y in zip(dif, dea)]
            spans = {}
            for name, unit in (('b_span_raw', b), ('c_span_raw', c)):
                start = raw_index(rows, ticks[unit]['start_dt'],
                                  granularity)
                end = raw_index(rows, ticks[unit]['end_dt'], granularity,
                                True)
                spans[name] = [start, end]
            self.assertEqual([spans['b_span_raw'], spans['c_span_raw']],
                             [first['b_span_raw'], first['c_span_raw']],
                             (case['id'], '单元端点原始行映射'))
            b0, b1 = spans['b_span_raw']
            c0, c1 = spans['c_span_raw']
            area_b = sum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
            area_c = sum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
            self.assertEqual(area_b, first['area_b'], (case['id'], 'area_b'))
            self.assertEqual(area_c, first['area_c'], (case['id'], 'area_c'))
            divergence = 0 < area_c < area_b
            trend_first = (roles['a']['unit'] if roles['a']
                           else roles['A']['zn'][0])
            self.assertEqual(first['trend_first_unit'], trend_first, case['id'])
            prior = ticks[trend_first:roles['B']['zn'][-1] + 1]
            prior_ext = (max(unit['high_ticks'] for unit in prior) if up
                         else min(unit['low_ticks'] for unit in prior))
            c_ext = (ticks[c]['high_ticks'] if up
                     else ticks[c]['low_ticks'])
            self.assertEqual(prior_ext, first['prior_extreme_ticks'],
                             (case['id'], '全趋势先验极值'))
            self.assertEqual(c_ext, first['c_extreme_ticks'],
                             (case['id'], 'c极值'))
            new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
            self.assertEqual(new_extreme, first['new_extreme'], case['id'])
            z_start = raw_index(rows, ticks[roles['B']['zn'][0]]['start_dt'],
                                granularity)
            z_end = raw_index(rows, ticks[roles['B']['zn'][-1]]['end_dt'],
                              granularity, True)
            self.assertEqual([z_start, z_end], first['zero_span_raw'],
                             (case['id'], '零轴区间原始行映射'))
            zero = min(max(abs(dif[i]), abs(dea[i])) / closes[i]
                       for i in range(z_start, z_end + 1))
            self.assertEqual(zero, first['zero_axis'], (case['id'], '零轴回拉'))
            if divergence and new_extreme:
                verdict, reason = 'established', None
            elif not divergence:
                verdict, reason = 'not_established', 'no_divergence'
            else:
                verdict, reason = 'not_established', 'no_new_extreme'
            self.assertEqual(first['verdict'], verdict, (case['id'], '裁定'))
            self.assertEqual(first['reason'], reason, (case['id'], '不成立原因'))
            if verdict == 'established':
                coverage['buy1_established' if not up
                         else 'sell1_established'] += 1
            else:
                coverage[reason] += 1
        self.assertEqual(coverage, dict(buy1_established=1,
                                        sell1_established=1,
                                        no_divergence=1,
                                        no_new_extreme=2))

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察时刻; NaN、缺价格字段及未来结构均
        不可读; 裁定可见边界恰为证明段单元首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            first = case['first_point']
            stop_points = (first['first_raw_count'] - 1,
                           first['first_raw_count'])
            for stop in stop_points:
                now = bars[stop - 1]['dt']
                baseline = chan.analyze_at(bars[:stop], now,
                                           bi_standard=case['standard'])
                poisoned = [dict(bar) for bar in bars]
                for bar in poisoned[stop:]:
                    bar.pop('open')
                    bar.update(high=float('nan'), low=-999, close=99999)
                future = dict(dt=bars[-1]['dt'] + timedelta(days=1),
                              high=float('inf'), low=-999,
                              close=float('nan'), volume=1)
                self.assertEqual(
                    chan.analyze_at(poisoned + [future], now,
                                    bi_standard=case['standard']).to_dict(),
                    baseline.to_dict(), (case['id'], stop))
                expected = len([unit for unit in case['units']
                                if unit['confirmed_raw_count'] <= stop])
                if case['level'] == 'bi':
                    self.assertEqual(len(baseline.bis) - 1, expected,
                                     (case['id'], stop))
                else:
                    stable = baseline.bis[:-1]
                    self.assertEqual(
                        len([xd for xd in chan.find_xds(stable)
                             if xd.complete]), expected, (case['id'], stop))
            self.assertLessEqual(first['first_raw_count'],
                                 len(case['raw_rows']), case['id'])


if __name__ == '__main__':
    unittest.main()
