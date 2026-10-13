# -*- coding: utf-8 -*-
"""课20/21/101: R2 0.9.8 xd级触沿允许(margin=0)三类买卖点真实样本。

预期由原始行情、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。两案例因子恒为1, 价格
单位0.001。课20定理三(行77-80): 次级别离开中枢后第一次回试, 买点
低点不跌破ZG、卖点高点不升破ZD; 触沿允许(margin=0)——0.9.7登记
的xd级触沿成立缺口以M1 sell3(回试高点=ZD)与M2 buy3(回试低点=
ZG)两侧闭合; 回试必须是第一次(行89-93); 成立即中枢毁灭(课101
行7)。zn规则: 四中枢均为定理一贪婪zn(课29行20-26离开冻结不适用,
无趋势上下文)。xd级单元为完成XD, 尝试结局以回试XD的proof笔首次
确认为准。first_raw_count按逐原始bar前缀首次可见冻结; 分型/笔端
点时间不等于确认时间, 禁止确认时间回填。30m/5m bar以结束时刻为
标签, 到达按结束+1分钟计(测试约定)。覆盖: buy3成立x3(其一
margin=0)、sell3成立x1(margin=0)、fail x9、pending x0。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_third_point_xd_margin0.json')
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
    """到达时刻测试约定: 日线收盘日15:05; 30m/5m按bar结束+1分钟。"""
    if granularity == 'day':
        return rows[count - 1]['dt'][:10] + ' 15:05:00'
    stamp = datetime.strptime(rows[count - 1]['dt'], '%Y-%m-%d %H:%M:%S')
    return (stamp + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')


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
    """全窗口库链单元: xd级为完成XD(不含尾部)。"""
    bars = raw_bars(case)
    _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
    fixed = bis[:-1]
    return [xd for xd in chan.find_xds(fixed) if xd.complete]


def unit_counts(case):
    """单元首确认原始bar计数: xd级取冻结单元表。"""
    return [unit['confirmed_raw_count'] for unit in case['units']]


def unit_ticks(units):
    """三类算术只消费整数区间与方向, 不读端点时间。"""
    return [dict(low_ticks=round(unit.low * 1000),
                 high_ticks=round(unit.high * 1000),
                 end_ticks=round(unit.end_value * 1000),
                 direction=unit.direction) for unit in units]


class TestRealThirdPointXdMarginZero(unittest.TestCase):
    def rederive_center(self, ticks, spec, context):
        """课17/20/29: 库单元上重推中枢算术; zn成员为人工声明结构。

        Zn同向步2、首对核心、中间覆盖、延伸触沿、DD/GG包络全部重算
        并与声明比对。状态算术: closed_by非null时封口单元=zn[-1]+2
        且不触沿; 本轮四中枢均为定理一贪婪zn(closed_by封口),
        frozen_by_departure不得出现。
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
        self.assertFalse(frozen, (context, '贪婪zn不得声明离开冻结'))
        self.assertIsNotNone(closed_by, (context, '本轮中枢须封口'))
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
            self.assertEqual(case['level'], 'xd', case['id'])
            bars = raw_bars(case)
            granularity = case.get('granularity', 'day')
            _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
            fixed = bis[:-1]
            self.assertEqual(bi_records(bis), case['foundation']['bis'],
                             case['id'])
            counts = unit_counts(case)
            rows = case['raw_rows']
            xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
            self.assertEqual(xd_events(xds, fixed),
                             case['foundation']['xd_events'], case['id'])
            self.assertEqual(
                [xd_unit_record(xd, fixed, counts[i], rows, granularity)
                 for i, xd in enumerate(xds)],
                case['units'], case['id'])

    def test_every_raw_prefix_replays_frozen_chain_and_first_confirmation(self):
        """课65/67/78: 逐原始bar前缀重放; 链前缀稳定、无撤销、首确认
        恰合; 尝试结局确认恰为回试XD的proof笔首次确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            foundation = case['foundation']
            frozen = foundation['bis']
            events = foundation['xd_events']
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
                if len(fixed) != computed:
                    xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                    visible = [event for event in events
                               if event[3] < len(fixed)]
                    self.assertEqual(xd_events(xds, fixed), visible,
                                     (case['id'], count, '完成XD恰合冻结事件'))
                    for k in range(len(visible)):
                        xd_seen.setdefault(k, count)
                    computed = len(fixed)
            self.assertEqual(
                [bi_seen[i]
                 for i in range(len(foundation['bis_confirmed_raw_count']))],
                foundation['bis_confirmed_raw_count'], case['id'])
            self.assertEqual(
                [xd_seen[i] for i in range(len(case['units']))],
                unit_counts(case), case['id'])
            for name in ('A', 'B'):
                for entry in case['attempts'][name]:
                    self.assertEqual(entry['first_raw_count'],
                                     xd_seen[entry['pull']],
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
        否决定理算术、第一次回试与成立即闭环全部重推。"""
        coverage = dict(buy3_established=0, sell3_established=0,
                        fail=0, pending=0)
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            for name in ('A', 'B'):
                center = self.rederive_center(ticks, case['centers'][name],
                                              (case['id'], name))
                declared = case['attempts'][name]
                for spec in declared:
                    self.assertIn(spec['outcome'], ('fail', 'established'),
                                  (case['id'], name))
                enumerated = self.enumerate_attempts(ticks, center)
                self.assertEqual(len(enumerated), len(declared),
                                 (case['id'], name))
                for enum, spec in zip(enumerated, declared):
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
        self.assertEqual(coverage, dict(buy3_established=3,
                                        sell3_established=1, fail=9,
                                        pending=0))

    def test_margin_zero_touch_edge_establishment(self):
        """课20行77-80: xd级触沿允许(margin=0)成立两侧闭合——买点回试
        低点恰为ZG、卖点回试高点恰为ZD时成立; fail严格回中枢;
        成立margin非负、fail margin为负。"""
        touches = dict(buy3=0, sell3=0)
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            for name in ('A', 'B'):
                center = self.rederive_center(ticks, case['centers'][name],
                                              (case['id'], name))
                for spec in case['attempts'][name]:
                    pull = ticks[spec['pull']]
                    if spec['outcome'] == 'established':
                        self.assertGreaterEqual(spec['margin_ticks'], 0,
                                                (case['id'], name))
                    else:
                        self.assertLess(spec['margin_ticks'], 0,
                                        (case['id'], name))
                    if spec['outcome'] != 'established':
                        continue
                    if spec['side'] == 'buy3':
                        self.assertEqual(spec['point_ticks'],
                                         pull['end_ticks'], (case['id'], name))
                        if pull['low_ticks'] == center['zg']:
                            touches['buy3'] += 1
                            self.assertEqual(spec['margin_ticks'], 0,
                                             (case['id'], name))
                    else:
                        self.assertEqual(spec['point_ticks'],
                                         pull['end_ticks'], (case['id'], name))
                        if pull['high_ticks'] == center['zd']:
                            touches['sell3'] += 1
                            self.assertEqual(spec['margin_ticks'], 0,
                                             (case['id'], name))
        self.assertEqual(touches, dict(buy3=1, sell3=1))

    def test_margin_zero_frozen_values(self):
        """冻结xd级触沿样本回归: M1 A sell3(u32,u33)@1048=ZD; M2 A
        buy3(u31,u32)@1100=ZG; M1 B buy3@1062(margin 14); M2 B
        buy3@1139(margin 2); M2 B首成员u32即A成立回试单元(三类后中
        枢新生), M1 B首成员u32即A离开单元。"""
        labels = {case['window_key']: case
                  for case in load_labels()['cases']}
        m1 = labels['M1']
        m1a = m1['attempts']['A'][-1]
        self.assertEqual((m1a['side'], m1a['leave'], m1a['pull'],
                          m1a['outcome'], m1a['point_ticks'],
                          m1a['margin_ticks']),
                         ('sell3', 32, 33, 'established', 1048, 0))
        self.assertEqual(m1['centers']['A']['zd'], 1048)
        self.assertEqual(len(m1['attempts']['A']), 9)
        self.assertEqual(m1['centers']['B']['zn'][0], m1a['leave'])
        m1b = m1['attempts']['B'][-1]
        self.assertEqual((m1b['side'], m1b['leave'], m1b['pull'],
                          m1b['outcome'], m1b['point_ticks'],
                          m1b['margin_ticks']),
                         ('buy3', 35, 36, 'established', 1062, 14))
        m2 = labels['M2']
        m2a = m2['attempts']['A'][-1]
        self.assertEqual((m2a['side'], m2a['leave'], m2a['pull'],
                          m2a['outcome'], m2a['point_ticks'],
                          m2a['margin_ticks']),
                         ('buy3', 31, 32, 'established', 1100, 0))
        self.assertEqual(m2['centers']['A']['zg'], 1100)
        self.assertEqual(m2['centers']['B']['zn'][0], m2a['pull'])
        m2b = m2['attempts']['B'][-1]
        self.assertEqual((m2b['side'], m2b['leave'], m2b['pull'],
                          m2b['outcome'], m2b['point_ticks'],
                          m2b['margin_ticks']),
                         ('buy3', 35, 36, 'established', 1139, 2))
        m2a0 = m2['attempts']['A'][0]
        self.assertEqual((m2a0['side'], m2a0['leave'], m2a0['pull']),
                         ('sell3', 30, 31))
        self.assertEqual(m2a0['outcome'], 'fail')
        self.assertEqual(m2a0['margin_ticks'], -87)

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察时刻; NaN、缺价格字段及未来结构均
        不可读; 尝试结局确认边界恰为回试XD首确认。"""
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
                stable = baseline.bis[:-1]
                self.assertEqual(
                    len([xd for xd in chan.find_xds(stable)
                         if xd.complete]), expected, (case['id'], stop))
            for name in ('A', 'B'):
                for entry in case['attempts'][name]:
                    self.assertLessEqual(unit_counts(case)[entry['pull']],
                                         last, (case['id'], name))


if __name__ == '__main__':
    unittest.main()
