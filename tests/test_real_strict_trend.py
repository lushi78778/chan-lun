# -*- coding: utf-8 -*-
"""课17/20/29/33/106: R2 严格趋势 Zn 与 a+A+b+B+c 完整角色真实标注。

预期由原始日线、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。三样本因子恒为1,
价格单位0.001, 不填因子、不调整报价。Zn取中枢形成方向同向单元;
ZD/ZG由首对同向段固定; 存在性=三连续单元重叠; 延伸=闭区间触沿
(定理一); DD/GG为zn[0]..zn[-1]全单元包络; c离开最后中枢核心才算
departed, B+c扩展按a~+A~未完成延续登记。完成严格趋势正例缺口
(本数据集0完成)如实保留, 不调宽门槛补齐。核心测试用库单元重推
角色算术对比fixture; zn成员表是人工声明结构, 自动搜索属R3。
XD组成、模式与证明笔来自冻结人工表, gate算术正确性由逐前缀回放
find_xds恰好复现冻结事件保证。台账first_raw_count按逐原始日前缀
首次可见冻结; 分型/笔端点时间不等于确认时间, 禁止确认时间回填。
15:00收盘/15:05到达是工程测试约定, 不是供应时效实测。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_strict_trend.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def raw_bars(case, timed=False):
    """保留全部源行; 恒1因子样本不隐含暖机、停牌剔除或复权。"""
    bars = []
    for row in case['raw_rows']:
        if row['adj_factor'] != 1:
            raise ValueError('新因子样本须另行冻结每个观察锚的算术')
        day = datetime.strptime(row['dt'][:10], '%Y-%m-%d')
        bar = dict(dt=day, open=row['open'], high=row['high'],
                   low=row['low'], close=row['close'], volume=row['vol'])
        if timed:
            bar['closed_dt'] = day + timedelta(hours=15)
            bar['available_dt'] = day + timedelta(hours=15, minutes=5)
        bars.append(bar)
    return bars


def bi_records(bis):
    """笔五元组; 比较以人工整数价位表为准。"""
    return [[bi.direction, bi.start_index, bi.end_index,
             round(bi.start_value * 1000), round(bi.end_value * 1000)]
            for bi in bis]


def arrival(count, rows):
    """确认时间取原始观察行的15:05到达约定, 不是端点或成交时间。"""
    return rows[count - 1]['dt'][:10] + ' 15:05:00'


def bi_unit_record(bi, count, rows):
    """固定笔序列化; 内部极值不改写端点日期。"""
    return dict(start_index=bi.start_index, end_index=bi.end_index,
                start_ticks=round(bi.start_value * 1000),
                end_ticks=round(bi.end_value * 1000),
                start_dt=str(bi.start_dt)[:10], end_dt=str(bi.end_dt)[:10],
                low_ticks=round(bi.low * 1000), high_ticks=round(bi.high * 1000),
                direction=bi.direction, confirmed_raw_count=count,
                confirmed_dt=arrival(count, rows))


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


def xd_unit_record(xd, fixed, count, rows):
    """完成XD序列化: 组成范围、模式、唯一证据笔与首确认。"""
    matches = [i for i, bi in enumerate(fixed)
               if bi.end_index == xd.evidence_end_index and
               bi.end_dt == xd.evidence_dt]
    if len(matches) != 1:
        raise AssertionError('完成XD须有唯一可回溯证据笔')
    record = dict(start_index=xd.start_index, end_index=xd.end_index,
                  start_ticks=round(xd.start_value * 1000),
                  end_ticks=round(xd.end_value * 1000),
                  start_dt=str(xd.start_dt)[:10], end_dt=str(xd.end_dt)[:10],
                  low_ticks=round(xd.low * 1000),
                  high_ticks=round(xd.high * 1000),
                  direction=xd.direction, mode=xd.mode,
                  proof_bi=matches[0],
                  evidence_end_index=xd.evidence_end_index,
                  evidence_dt=str(xd.evidence_dt)[:10],
                  confirmed_raw_count=count, confirmed_dt=arrival(count, rows))
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
    """单元首确认原始日计数: bi级取固定笔表, xd级取冻结单元表。"""
    if case['level'] == 'bi':
        return case['foundation']['bis_confirmed_raw_count']
    return [unit['confirmed_raw_count'] for unit in case['units']]


def unit_ticks(units):
    """角色算术只消费整数区间与方向, 不读端点时间。"""
    return [dict(low_ticks=round(unit.low * 1000),
                 high_ticks=round(unit.high * 1000),
                 direction=unit.direction) for unit in units]


class TestRealStrictTrend(unittest.TestCase):
    def rederive_center(self, ticks, spec, context):
        """课17/20: 库单元上重推中枢算术; zn成员为人工声明结构。

        Zn同向步2、首对核心、中间覆盖、延伸触沿、DD/GG包络与
        zn[-1]+2封口(不触沿)全部重算并与声明比对。
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
        closed_by = spec['closed_by']
        if closed_by is None:
            self.assertGreaterEqual(zn[-1] + 2, len(ticks),
                                    (context, '同向后继存在须封口'))
        else:
            self.assertEqual(closed_by, zn[-1] + 2,
                             (context, '封口单元须为zn[-1]+2'))
            unit = ticks[closed_by]
            self.assertFalse(unit['low_ticks'] <= zg and
                             unit['high_ticks'] >= zd,
                             (context, '封口单元不得触沿'))
        derived = dict(zn=list(zn), zd=zd, zg=zg, dd=dd, gg=gg,
                       closed_by=closed_by)
        self.assertEqual(derived,
                         dict((key, spec[key]) for key in derived), context)
        return derived

    def test_full_window_library_chain_matches_frozen_tables(self):
        """课106/67: 全窗口库链、单元表与XD事件恰合独立冻结标签。"""
        for case in load_labels()['cases']:
            self.assertEqual(case['standard'], '106')
            bars = raw_bars(case)
            rows = case['raw_rows']
            foundation = case['foundation']
            _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
            self.assertEqual(bi_records(bis), foundation['bis'], case['id'])
            fixed = bis[:-1]
            counts = foundation['bis_confirmed_raw_count']
            self.assertEqual(len(fixed), len(counts), case['id'])
            if case['level'] == 'bi':
                self.assertEqual(
                    [bi_unit_record(bi, counts[i], rows)
                     for i, bi in enumerate(fixed)],
                    case['units'], case['id'])
            else:
                xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                self.assertEqual(len(xds), len(case['units']), case['id'])
                self.assertEqual(
                    [xd_unit_record(xd, fixed, unit['confirmed_raw_count'],
                                    rows)
                     for xd, unit in zip(xds, case['units'])],
                    case['units'], case['id'])
                self.assertEqual(xd_events(xds, fixed),
                                 foundation['xd_events'], case['id'])

    def test_every_raw_prefix_replays_frozen_chain_and_first_confirmation(self):
        """课65/67/78: 逐原始日前缀重放; 链前缀稳定、无撤销、首确认恰合。

        固定链只随长度增长重算完成XD: 前缀稳定性已保证同长度前缀
        的固定链逐字节一致, 完成XD只由固定链决定, 不由尾笔改写。
        """
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            foundation = case['foundation']
            frozen = foundation['bis']
            events = foundation.get('xd_events') or []
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
            if case['level'] == 'bi':
                self.assertEqual(
                    [bi_seen[i] for i in range(len(case['units']))],
                    unit_counts(case), case['id'])
            else:
                self.assertEqual(
                    [xd_seen[k] for k in range(len(case['units']))],
                    unit_counts(case), case['id'])

    def test_role_arithmetic_rederived_from_library_units(self):
        """课17/20/29/33: 库单元重推a/A/b/B/c/C、gap、合并与状态算术。

        b须离开A核心; c离开B核心才departed, fail为未及核心;
        gap=A/B包络分离且恒正; 定理二合并两分支算术重推,
        determined==C已封闭; 延续分支成立时不得声明合并。
        """
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            centers = {}
            for name in ('A', 'B', 'C'):
                if roles[name] is not None:
                    centers[name] = self.rederive_center(
                        ticks, roles[name], (case['id'], name))
            self.assertIn('A', centers, case['id'])
            self.assertIn('B', centers, case['id'])
            if roles['a'] is not None:
                self.assertEqual(roles['a']['unit'],
                                 centers['A']['zn'][0] - 1, case['id'])
                self.assertEqual(ticks[roles['a']['unit']]['direction'],
                                 trend['direction'], case['id'])
            else:
                self.assertEqual(centers['A']['zn'][0], 0, case['id'])
            b = roles['b']['unit']
            self.assertEqual(b, centers['A']['zn'][-1] + 1, case['id'])
            self.assertEqual(ticks[b]['direction'], trend['direction'],
                             case['id'])
            if up:
                self.assertGreater(ticks[b]['high_ticks'], centers['A']['zg'],
                                   (case['id'], 'b未离开A核心'))
            else:
                self.assertLess(ticks[b]['low_ticks'], centers['A']['zd'],
                                (case['id'], 'b未离开A核心'))
            self.assertIn(centers['B']['zn'][0], (b, b + 1), case['id'])
            c = roles['c']['unit']
            self.assertEqual(c, centers['B']['zn'][-1] + 1, case['id'])
            self.assertEqual(ticks[c]['direction'], trend['direction'],
                             case['id'])
            unit = ticks[c]
            if up:
                departed = unit['high_ticks'] > centers['B']['zg']
                failed = unit['high_ticks'] < centers['B']['zd']
            else:
                departed = unit['low_ticks'] < centers['B']['zd']
                failed = unit['low_ticks'] > centers['B']['zg']
            self.assertNotEqual(departed, failed, case['id'])
            self.assertEqual(departed,
                             roles['c']['outcome'] == 'departed', case['id'])
            self.assertEqual(failed, roles['c']['outcome'] == 'fail',
                             case['id'])
            gap = (centers['B']['dd'] - centers['A']['gg'] if up
                   else centers['A']['dd'] - centers['B']['gg'])
            self.assertEqual(gap, roles['gap_ticks'], case['id'])
            self.assertGreater(gap, 0, (case['id'], 'A/B包络重叠'))
            if roles['C'] is not None:
                self.assertIn(centers['C']['zn'][0], (c, c + 1), case['id'])
                below = (centers['C']['zg'] < centers['B']['zd'] and
                         centers['C']['gg'] >= centers['B']['dd'])
                above = (centers['C']['zd'] > centers['B']['zg'] and
                         centers['C']['dd'] <= centers['B']['gg'])
                continuation = (centers['C']['gg'] < centers['B']['dd'] or
                                centers['C']['dd'] > centers['B']['gg'])
                self.assertFalse(continuation,
                                 (case['id'], '定理二延续分支成立'))
                merge = roles['merge']
                self.assertIsNotNone(merge, case['id'])
                self.assertEqual(merge['pair'], ['B', 'C'], case['id'])
                self.assertEqual(merge['branch'],
                                 'below' if below else 'above', case['id'])
                self.assertTrue(below or above, case['id'])
                self.assertEqual(
                    merge['determined'],
                    centers['C']['closed_by'] is not None, case['id'])
            else:
                self.assertIsNone(roles['merge'], case['id'])
            if roles['c']['outcome'] == 'fail':
                self.assertEqual(trend['status'], 'no_departure', case['id'])
            else:
                self.assertEqual(trend['status'], 'ongoing', case['id'])
                proof = False
                for i in range(c + 1, len(ticks)):
                    item = ticks[i]
                    if item['low_ticks'] <= centers['B']['zg'] and \
                            item['high_ticks'] >= centers['B']['zd']:
                        proof = True
                        break
                self.assertFalse(
                    proof, (case['id'], '完成正例缺口: 本数据集0完成'))

    def test_ledger_event_sequence_and_first_confirmation(self):
        """课29/65: 台账事件序列由角色推导, first_raw_count不回填。

        同单元内序zn_extend<closed<open<fixed<departed/fail<determined;
        事件单元取冻结单元首确认计数, 确认时间取15:05到达约定。
        """
        rank = {'extend': 0, 'closed': 1, 'open': 2, 'fixed': 3,
                'departed': 4, 'fail': 4, 'determined': 5}
        for case in load_labels()['cases']:
            roles = case['roles']
            counts = unit_counts(case)
            rows = case['raw_rows']
            events = []
            for name in ('A', 'B', 'C'):
                spec = roles[name]
                if spec is None:
                    continue
                events.append((name + '_open', spec['zn'][0] + 2))
                for i in spec['zn'][2:]:
                    events.append((name + '_zn_extend', i))
                if spec['closed_by'] is not None:
                    events.append((name + '_closed', spec['closed_by']))
            events.append(('b_fixed', roles['b']['unit']))
            events.append(('c_fixed', roles['c']['unit']))
            events.append(('c_departed' if roles['c']['outcome'] == 'departed'
                           else 'c_fail', roles['c']['unit']))
            if roles['C'] is not None and roles['merge'] is not None and \
                    roles['merge']['determined']:
                events.append(('merge_determined', roles['C']['closed_by']))
            events.sort(key=lambda item: (item[1],
                                          rank[item[0].rsplit('_', 1)[1]]))
            self.assertEqual([[entry['event'], entry['unit']]
                              for entry in case['ledger']],
                             [[name, unit] for name, unit in events],
                             case['id'])
            for entry in case['ledger']:
                self.assertEqual(entry['first_raw_count'],
                                 counts[entry['unit']],
                                 (case['id'], entry['event']))
                self.assertEqual(entry['first_dt'],
                                 arrival(entry['first_raw_count'], rows),
                                 (case['id'], entry['event']))

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察日; NaN、缺价格字段及未来结构均不可读。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            count = case['units'][-1]['confirmed_raw_count']
            for stop in (count - 1, count):
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

    def test_close_arrival_and_delayed_confirmation_use_actual_replay_entrypoints(self):
        """最后确认行在收盘前/到达前/晚到时等待, 实际到达后才确认。

        晚到只改元数据, 不改变价格或端点; 末单元首观察相应顺延,
        既有确认记录保持不变。观察网格包含每个单元独立首确认时点,
        因此first_seen逐条与标签比较。
        """
        for case in load_labels()['cases']:
            rows = raw_bars(case, timed=True)
            standard = case['standard']
            kind = 'bi' if case['level'] == 'bi' else 'xd'
            counts = unit_counts(case)
            count = counts[-1]
            last = rows[count - 1]
            now = last['available_dt']
            for before in (last['closed_dt'] - timedelta(microseconds=1),
                           last['closed_dt'],
                           now - timedelta(microseconds=1)):
                baseline = chan.analyze_available(rows[:count - 1], before,
                                                  bi_standard=standard)
                actual = chan.analyze_available(rows, before,
                                                bi_standard=standard)
                self.assertEqual(actual.to_dict(), baseline.to_dict(),
                                 (case['id'], before))
                poison = dict(last, high=float('nan'), low=-999, close=99999)
                poison.pop('open')
                self.assertEqual(
                    chan.analyze_available(rows[:count - 1] + [poison],
                                           before,
                                           bi_standard=standard).to_dict(),
                    baseline.to_dict(), (case['id'], before))
            current = chan.analyze_available(rows, now, bi_standard=standard)
            if case['level'] == 'bi':
                self.assertEqual(len(current.bis) - 1, len(case['units']),
                                 case['id'])
            else:
                stable = current.bis[:-1]
                self.assertEqual(
                    len([xd for xd in chan.find_xds(stable) if xd.complete]),
                    len(case['units']), case['id'])
            delayed = now + timedelta(days=1)
            late_rows = [dict(row) for row in rows[:count]]
            late_rows[-1]['available_dt'] = delayed
            future_day = last['dt'] + timedelta(days=2)
            late_rows.append(dict(dt=future_day,
                                  closed_dt=future_day + timedelta(hours=15),
                                  available_dt=future_day +
                                  timedelta(hours=15, minutes=5),
                                  high=float('inf'), low=-999,
                                  close=float('nan'), volume=1))
            observations = sorted(set(
                [rows[value - 1]['available_dt']
                 for value in sorted(set(counts)) if value < count] +
                [now, delayed - timedelta(microseconds=1), delayed]))

            def identity(unit):
                if case['level'] == 'bi':
                    return (unit['direction'], unit['start_dt'],
                            unit['end_dt'])
                return (unit['direction'], unit['start_dt'], unit['end_dt'],
                        unit['mode'])

            def record_identity(record):
                if case['level'] == 'bi':
                    return (record['direction'], record['start_dt'][:10],
                            record['end_dt'][:10])
                return (record['direction'], record['start'][0][:10],
                        record['end'][0][:10], record['mode'])

            expected_first = dict(
                (identity(unit),
                 delayed if unit['confirmed_raw_count'] == count else
                 rows[unit['confirmed_raw_count'] - 1]['available_dt'])
                for unit in case['units'])
            seen = {}
            for snapshot in chan.replay_available(late_rows, observations,
                                                  bi_standard=standard):
                collected = {}
                for structure in snapshot.structures:
                    if structure.kind != kind:
                        continue
                    key = record_identity(structure.record)
                    self.assertIn(key, expected_first,
                                  (case['id'], str(snapshot.observed_dt)))
                    self.assertEqual(structure.first_seen,
                                     expected_first[key],
                                     (case['id'], key))
                    collected[key] = structure.first_seen
                present = set(key for key, value in expected_first.items()
                              if value <= snapshot.observed_dt)
                self.assertEqual(set(collected), present,
                                 (case['id'], str(snapshot.observed_dt)))
                seen.update(collected)
            self.assertEqual(seen, expected_first, case['id'])


if __name__ == '__main__':
    unittest.main()
