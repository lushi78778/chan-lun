# -*- coding: utf-8 -*-
"""课20/21/101: R2 0.9.5 三类买卖点真实正反例标注。

预期由原始行情、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。四案例因子恒为1, 价格
单位0.001。课20定理三(行77-80): 次级别离开中枢后第一次回试, 买点
低点不跌破ZG、卖点高点不升破ZD; 回试必须是第一次(行89-93); 成立
即中枢毁灭(课101行7三类=中枢破坏点); 成立后不必然趋势(行93-94)。
zn规则: 趋势末中枢沿用0.9.2-0.9.4离开冻结(课29行20-26), 无趋势
上下文独立中枢按定理一全延伸。尝试台账几何: 核心确立后非zn单元
与核心闭区间重叠且端点越沿为离开, 紧邻反向单元为回试; 触沿允许
(margin=0); fail后不跳过; 成立即闭环。xd级尝试结局以回试XD完成
为准, bi级以回试笔进入固定链为准; first_raw_count按逐原始bar
前缀首次可见冻结; 分型/笔端点时间不等于确认时间, 禁止确认时间
回填。60m bar以结束时刻为标签, 到达按结束+1分钟计; 日线到达
15:05(测试约定)。覆盖: buy3成立x2、sell3成立x4、fail x9、
pending x1; 触沿允许(margin=0)成立无样本, 缺口如实登记。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_third_point.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def raw_bars(case, timed=False):
    """保留全部源行与完整bar时刻; 恒1因子样本不隐含暖机或复权。"""
    bars = []
    for row in case['raw_rows']:
        if row['adj_factor'] != 1:
            raise ValueError('新因子样本须另行冻结每个观察锚的算术')
        dt = datetime.strptime(row['dt'], '%Y-%m-%d %H:%M:%S')
        bar = dict(dt=dt, open=row['open'], high=row['high'],
                   low=row['low'], close=row['close'], volume=row['vol'])
        if timed:
            bar['closed_dt'] = dt
            bar['available_dt'] = dt + timedelta(minutes=1)
        bars.append(bar)
    return bars


def bi_records(bis):
    """笔五元组; 比较以人工整数价位表为准。"""
    return [[bi.direction, bi.start_index, bi.end_index,
             round(bi.start_value * 1000), round(bi.end_value * 1000)]
            for bi in bis]


def arrival(count, rows, granularity):
    """到达时刻测试约定: 日线收盘日15:05; 60m按bar结束+1分钟。"""
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
                start_dt=str(bi.start_dt)[:width], end_dt=str(bi.end_dt)[:width],
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
    record = dict(start_index=xd.start_index, end_index=xd.end_index,
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
    return record

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
    """三类算术只消费整数区间与方向, 不读端点时间。"""
    return [dict(low_ticks=round(unit.low * 1000),
                 high_ticks=round(unit.high * 1000),
                 end_ticks=round(unit.end_value * 1000),
                 direction=unit.direction) for unit in units]


class TestRealThirdPoint(unittest.TestCase):
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

    def enumerate_attempts(self, ticks, center):
        """课20行77-96: 尝试台账几何重枚举; fail不跳过, 成立即闭环。"""
        zn = set(center['zn'])
        zd, zg = center['zd'], center['zg']
        out = []
        for i in range(center['zn'][1] + 1, len(ticks) - 1):
            if i in zn:
                continue
            leave, pull = ticks[i], ticks[i + 1]
            if leave['direction'] == pull['direction']:
                continue
            if not (leave['low_ticks'] <= zg and leave['high_ticks'] >= zd):
                continue
            if leave['direction'] == 'up':
                if leave['end_ticks'] <= zg:
                    continue
                side = 'buy3'
                holds = pull['low_ticks'] >= zg
                margin = pull['low_ticks'] - zg
            else:
                if leave['end_ticks'] >= zd:
                    continue
                side = 'sell3'
                holds = pull['high_ticks'] <= zd
                margin = zd - pull['high_ticks']
            out.append(dict(side=side, leave=i, pull=i + 1, holds=holds,
                            point_ticks=pull['end_ticks'],
                            margin_ticks=margin))
            if holds:
                break
        return out

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
        恰合; 尝试结局确认恰为回试(或pending离开)单元首确认。"""
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
            for name in ('A', 'B'):
                for entry in case['attempts'][name]:
                    unit = entry['pull'] if entry['pull'] is not None \
                        else entry['leave']
                    self.assertEqual(entry['first_raw_count'],
                                     unit_seen[unit],
                                     (case['id'], name, entry['side']))
                    self.assertEqual(
                        entry['first_dt'],
                        arrival(entry['first_raw_count'], rows, granularity),
                        (case['id'], name, entry['side']))

    def test_center_arithmetic_rederived_from_library_units(self):
        """课17/20/29: 库单元重推A/B中枢全部算术与状态。"""
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            for name in ('A', 'B'):
                self.rederive_center(ticks, case['centers'][name],
                                     (case['id'], name))

    def test_attempt_ledger_matches_enumeration_and_theorem(self):
        """课20定理三/行89-96: 尝试台账与几何重枚举逐项一致; 成立/
        否决定理算术、第一次回试、成立即闭环与pending条件全部重推。"""
        coverage = dict(buy3_established=0, sell3_established=0,
                        fail=0, pending=0)
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            for name in ('A', 'B'):
                center = self.rederive_center(ticks, case['centers'][name],
                                              (case['id'], name))
                declared = case['attempts'][name]
                pending = None
                completed = declared
                if declared[-1]['outcome'] == 'pending':
                    pending = declared[-1]
                    completed = declared[:-1]
                enumerated = self.enumerate_attempts(ticks, center)
                self.assertEqual(len(enumerated), len(completed),
                                 (case['id'], name))
                for enum, spec in zip(enumerated, completed):
                    context = (case['id'], name, spec['leave'])
                    self.assertEqual(
                        (enum['side'], enum['leave'], enum['pull']),
                        (spec['side'], spec['leave'], spec['pull']), context)
                    self.assertEqual(enum['holds'],
                                     spec['outcome'] == 'established',
                                     context)
                    self.assertEqual(enum['point_ticks'],
                                     spec['point_ticks'], context)
                    self.assertEqual(enum['margin_ticks'],
                                     spec['margin_ticks'], context)
                    leave = ticks[spec['leave']]
                    pull = ticks[spec['pull']]
                    self.assertNotEqual(leave['direction'],
                                        pull['direction'], context)
                    self.assertEqual(spec['pull'], spec['leave'] + 1,
                                     (context, '回试必须是离开后第一次'))
                    self.assertTrue(
                        leave['low_ticks'] <= center['zg'] and
                        leave['high_ticks'] >= center['zd'],
                        (context, '离开未与核心重叠'))
                    self.assertNotIn(spec['leave'], center['zn'], context)
                    if spec['side'] == 'buy3':
                        self.assertGreater(leave['end_ticks'], center['zg'],
                                           (context, '向上离开须端点越沿'))
                        if spec['outcome'] == 'established':
                            self.assertGreaterEqual(pull['low_ticks'],
                                                    center['zg'],
                                                    (context, '低点不跌破ZG'))
                            self.assertNotIn(spec['pull'], center['zn'],
                                             context)
                            coverage['buy3_established'] += 1
                        else:
                            self.assertLess(pull['low_ticks'], center['zg'],
                                            (context, 'fail须回中枢'))
                            coverage['fail'] += 1
                    else:
                        self.assertLess(leave['end_ticks'], center['zd'],
                                        (context, '向下离开须端点越沿'))
                        if spec['outcome'] == 'established':
                            self.assertLessEqual(pull['high_ticks'],
                                                 center['zd'],
                                                 (context, '高点不升破ZD'))
                            self.assertNotIn(spec['pull'], center['zn'],
                                             context)
                            coverage['sell3_established'] += 1
                        else:
                            self.assertGreater(pull['high_ticks'],
                                               center['zd'],
                                               (context, 'fail须回中枢'))
                            coverage['fail'] += 1
                if pending is not None:
                    context = (case['id'], name, 'pending')
                    self.assertTrue(
                        not enumerated or not enumerated[-1]['holds'],
                        (context, '已成立中枢不得再pending'))
                    leave = ticks[pending['leave']]
                    self.assertEqual(pending['leave'], len(ticks) - 1,
                                     (context, 'pending离开须为窗口末单元'))
                    self.assertIsNone(pending['pull'], context)
                    self.assertIsNone(pending['point_ticks'], context)
                    self.assertIsNone(pending['margin_ticks'], context)
                    self.assertNotIn(pending['leave'], center['zn'], context)
                    self.assertTrue(
                        leave['low_ticks'] <= center['zg'] and
                        leave['high_ticks'] >= center['zd'],
                        (context, 'pending离开未与核心重叠'))
                    if pending['side'] == 'buy3':
                        self.assertEqual(leave['direction'], 'up', context)
                        self.assertGreater(leave['end_ticks'], center['zg'],
                                           (context, 'pending须端点越沿'))
                    else:
                        self.assertEqual(leave['direction'], 'down', context)
                        self.assertLess(leave['end_ticks'], center['zd'],
                                        (context, 'pending须端点越沿'))
                    coverage['pending'] += 1
        self.assertEqual(coverage, dict(buy3_established=2,
                                        sell3_established=4, fail=9,
                                        pending=1))

    def test_context_center_and_no_trend_necessity(self):
        """课20行93-94/课21行31-40: 三类成立后b区可现第三中枢,
        不必然趋势; 上下文中枢交集重推。"""
        for case in load_labels()['cases']:
            for spec in case.get('context_centers', []):
                ticks = unit_ticks(library_units(case))
                members = spec['units']
                low = max(ticks[i]['low_ticks'] for i in members)
                high = min(ticks[i]['high_ticks'] for i in members)
                self.assertEqual([low, high],
                                 [spec['low_ticks'], spec['high_ticks']],
                                 case['id'])
                self.assertLessEqual(low, high, case['id'])

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察时刻; NaN、缺价格字段及未来结构均
        不可读; 尝试结局确认边界恰为回试单元首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            last = max(entry['first_raw_count']
                       for name in ('A', 'B')
                       for entry in case['attempts'][name])
            for stop in (last - 1, last):
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
            for name in ('A', 'B'):
                for entry in case['attempts'][name]:
                    unit = entry['pull'] if entry['pull'] is not None \
                        else entry['leave']
                    self.assertLessEqual(unit_counts(case)[unit], last,
                                         (case['id'], name))


if __name__ == '__main__':
    unittest.main()
