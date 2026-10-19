# -*- coding: utf-8 -*-
"""课35/38/63/84: 真实固定笔及完成XD构造F1, 相邻F2的独立真值。

预期来自人工三段交集/切点/后继证明表, 编译器不导入chan。六窗口
共928原始日, 双标准和双路径分别回放。分型极值日和证据笔端点日
均不代替确认日。15:00闭合/15:05到达仅工程约定, 非供应时效实测。

另复用81因果条件两窗, 明示同一最低F1-bi规则后的真实完整类型及
F2未完成边界；独立区间表先于库比较声明, 不覆盖原条件fixture。
"""
import json
import os
import unittest
from bisect import bisect_right
from datetime import datetime, timedelta

import chan


def load_labels():
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_f1_originals.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def date(value):
    return datetime.strptime(value, '%Y-%m-%d')


def raw_bars(case, timed=False):
    rows = []
    for r in case['raw_rows']:
        bar = dict(dt=date(r['dt'][:10]), open=r['open'], high=r['high'],
                   low=r['low'], close=r['close'], volume=r['vol'])
        if timed:
            bar['closed_dt'] = bar['dt'] + timedelta(hours=15)
            bar['available_dt'] = bar['closed_dt'] + timedelta(minutes=5)
        rows.append(bar)
    return rows


def unit_record(unit):
    return dict(start_index=unit.start_index, end_index=unit.end_index,
                start_ticks=round(unit.start_value * 1000),
                end_ticks=round(unit.end_value * 1000),
                start_dt=str(unit.start_dt)[:10], end_dt=str(unit.end_dt)[:10],
                low_ticks=round(unit.low * 1000),
                high_ticks=round(unit.high * 1000), direction=unit.direction)


def move_record(move):
    return dict(kind=move.kind, complete=bool(move.complete),
                direction=move.direction, seg_start=move.seg_start,
                seg_end=move.seg_end, start_dt=str(move.start_dt)[:10],
                end_dt=str(move.end_dt)[:10], low_ticks=round(move.low * 1000),
                high_ticks=round(move.high * 1000),
                centers_ticks=[[round(a * 1000), round(b * 1000)]
                               for a, b in move.centers])


def expected_shape(record):
    return dict((key, record[key]) for key in (
        'kind', 'complete', 'direction', 'seg_start', 'seg_end',
        'start_dt', 'end_dt', 'low_ticks', 'high_ticks', 'centers_ticks'))


def path_units(bis):
    """末笔排除; XD再次从固定笔计算, 排除未完成线段。"""
    fixed = bis[:-1]
    return dict(bi=fixed, xd=[x for x in chan.find_xds(fixed) if x.complete])


def confirmed_inputs(path):
    """按独立标签的首次证明构造F1快照, 不用全样本端点过滤。"""
    out = []
    for m in path['completed']:
        unit_ids = tuple('component:' + str(i)
                         for i in range(m['seg_start'], m['seg_end'] + 1))
        evidence_ids = tuple('component:' + str(i)
                             for i in range(m['proof_unit'] + 1))
        out.append(chan.ConfirmedMoveType(
            'f1:' + str(m['seg_start']), 'F1', m['kind'], m['direction'],
            date(m['start_dt']), date(m['end_dt']), m['start_ticks'] / 1000.0,
            m['end_ticks'] / 1000.0, m['low_ticks'] / 1000.0,
            m['high_ticks'] / 1000.0,
            datetime.strptime(m['confirmed_dt'], '%Y-%m-%d %H:%M:%S'),
            unit_ids, evidence_ids,
            tuple((a / 1000.0, b / 1000.0) for a, b in m['centers_ticks'])))
    return out


class TestRealF1Originals(unittest.TestCase):
    def test_frozen_raw_foundation_and_final_f1_tables(self):
        """原始包含/分型/笔及已固定部件→F1完整表, 尾部待定也比较。"""
        for case in load_labels()['cases']:
            for standard in ('81', '106'):
                g, f, bis = chan.chan_fx_bi(raw_bars(case), standard=standard)
                expected = case['foundation_' + standard]
                self.assertEqual(
                    [dict(elements=b.elements, low_ticks=round(b.low * 1000),
                          high_ticks=round(b.high * 1000)) for b in g],
                    expected['new_bars'], (case['id'], standard))
                self.assertEqual([[x.kind, x.bar_index, round(x.value * 1000)]
                                  for x in f], expected['fxs'])
                self.assertEqual([[x.direction, x.start_index, x.end_index,
                                   round(x.start_value * 1000),
                                   round(x.end_value * 1000)] for x in bis],
                                 expected['bis'])
                if 'xds' in expected:
                    all_xds = chan.find_xds(bis)
                    self.assertEqual(len(all_xds), len(expected['xds']))
                    for actual, frozen in zip(all_xds, expected['xds']):
                        self.assertEqual(unit_record(actual),
                                         dict((k, frozen[k])
                                              for k in unit_record(actual)))
                        self.assertEqual(actual.complete, frozen['complete'])
                        self.assertEqual(actual.mode, frozen['mode'])
                        self.assertEqual(actual.evidence_end_index,
                                         frozen['evidence_end_index'])
                        self.assertEqual(str(actual.evidence_dt)[:10]
                                         if actual.evidence_dt is not None else None,
                                         frozen['evidence_dt'])
                for path, parts in path_units(bis).items():
                    target = case['paths'][path + '-' + standard]
                    for actual, frozen in zip(parts, target['units']):
                        self.assertEqual(unit_record(actual),
                                         dict((k, frozen[k])
                                              for k in unit_record(actual)))
                    self.assertEqual(len(parts), len(target['units']))
                    self.assertEqual(
                        [move_record(m) for m in chan.same_level_decompose(parts)],
                        [expected_shape(m) for m in target['moves']],
                        (case['id'], path, standard))

    def test_every_raw_prefix_matches_independent_completion_events(self):
        """1856次原始日×标准、3712次路径回放; 第一次证明之前不得提前。"""
        for case in load_labels()['cases']:
            rows = raw_bars(case)
            events = sorted(int(c) for c in case['observations'])
            seen = dict((p + '-' + s, {}) for p in ('bi', 'xd')
                        for s in ('81', '106'))
            for count in range(1, len(rows) + 1):
                event = events[bisect_right(events, count) - 1]
                expected = case['observations'][str(event)]
                for standard in ('81', '106'):
                    _, _, bis = chan.chan_fx_bi(rows[:count], standard=standard)
                    paths = path_units(bis)
                    self.assertEqual([unit_record(b) for b in paths['bi']],
                                     expected[standard]['fixed_bis'],
                                     (case['id'], standard, count))
                    xds = expected[standard]['completed_xds']
                    self.assertEqual(
                        [(x.start_index, x.end_index, x.mode) for x in paths['xd']],
                        [(x['start_index'], x['end_index'], x['mode']) for x in xds])
                    for actual, frozen in zip(paths['xd'], xds):
                        self.assertEqual(unit_record(actual),
                                         dict((k, frozen[k])
                                              for k in unit_record(actual)))
                    for path, parts in paths.items():
                        name = path + '-' + standard
                        moves = [m for m in chan.same_level_decompose(parts)
                                 if m.complete]
                        self.assertEqual([[m.seg_start, m.seg_end] for m in moves],
                                         expected[name], (case['id'], name, count))
                        target = case['paths'][name]['completed']
                        self.assertEqual([move_record(m) for m in moves],
                                         [expected_shape(m) for m in target
                                          if m['confirmed_raw_count'] <= count])
                        for m in moves:
                            identity = (m.seg_start, m.seg_end)
                            seen[name].setdefault(identity, count)
            for name, first in seen.items():
                self.assertEqual(first, dict(
                    ((m['seg_start'], m['seg_end']), m['confirmed_raw_count'])
                    for m in case['paths'][name]['completed']))

    def test_real_completed_kinds_and_mutable_tail_exclusion(self):
        """两上涨/一下跌非镜像真值; 完成XD路径趋势缺口明确保留。"""
        cases = load_labels()['cases']
        kinds = [m['kind'] for c in cases for name, p in c['paths'].items()
                 if name.startswith('bi-') for m in p['completed']]
        self.assertEqual(kinds.count('up'), 2)
        self.assertEqual(kinds.count('down'), 1)
        self.assertIn('consolidation', kinds)
        xd = [m for c in cases for name, p in c['paths'].items()
              if name.startswith('xd-') for m in p['completed']]
        self.assertEqual(len(xd), 3)
        self.assertTrue(all(m['kind'] == 'consolidation' for m in xd))
        up = next(c for c in cases if c['window_key'] == 'E')
        self.assertEqual(len(up['paths']['bi-81']['units']), 26)
        self.assertEqual(len(up['paths']['bi-106']['units']), 34)
        self.assertEqual(len(up['paths']['xd-81']['units']), 5)
        self.assertEqual(len(up['paths']['xd-106']['units']), 8)
        self.assertTrue(all(not p['moves'][-1]['complete']
                            for p in up['paths'].values()))

    def test_f2_uses_completed_f1_and_successor_confirmation(self):
        """F2标准递归保留延伸; 下跌窗口回抽证明比组成末端及其确认晚。"""
        for case in load_labels()['cases']:
            for name, path in case['paths'].items():
                units = confirmed_inputs(path)
                self.assertEqual([move_record(m) for m in chan.level_up(units)],
                                 [expected_shape(m) for m in path['f2']],
                                 (case['id'], name))
                expected = [m for m in path['f2'] if m['complete']]
                for count, row in enumerate(raw_bars(case, True), 1):
                    now = row['available_dt']
                    actual = chan.confirm_level_up(units, now, 'F2')
                    target = [m for m in expected
                              if m['confirmed_raw_count'] <= count]
                    self.assertEqual(len(actual), len(target),
                                     (case['id'], name, count))
                    for move, m in zip(actual, target):
                        self.assertEqual(move.kind, m['kind'])
                        self.assertEqual(move.direction, m['direction'])
                        self.assertEqual(str(move.start_dt)[:10], m['start_dt'])
                        self.assertEqual(str(move.end_dt)[:10], m['end_dt'])
                        self.assertEqual([round(move.low * 1000),
                                          round(move.high * 1000)],
                                         [m['low_ticks'], m['high_ticks']])
                        self.assertEqual([[round(a * 1000), round(b * 1000)]
                                          for a, b in move.centers], m['centers_ticks'])
                        self.assertEqual(str(move.confirmed_dt), m['confirmed_dt'])
                        self.assertEqual(move.unit_ids, tuple(
                            u.move_id for u in units[m['seg_start']:m['seg_end'] + 1]))
                        self.assertEqual(move.evidence_ids,
                                         tuple(u.move_id for u in units
                                               if u.confirmed_dt <= move.confirmed_dt))
                        self.assertGreater(move.confirmed_dt,
                                           units[m['seg_end']].confirmed_dt)
                        self.assertGreater(move.confirmed_dt, move.end_dt)

    def test_closed_but_late_raw_and_future_poison_are_unread(self):
        """每个F1确认时刻前一微秒仍等待; 晚到及未来毒价先过滤再计算。"""
        for case in load_labels()['cases']:
            rows = raw_bars(case, True)
            for standard in ('81', '106'):
                confirmations = set(m['confirmed_raw_count']
                                    for p in ('bi', 'xd')
                                    for m in case['paths'][p + '-' + standard]['completed'])
                for count in sorted(confirmations):
                    now = rows[count - 1]['available_dt']
                    before = now - timedelta(microseconds=1)
                    original = chan.analyze_available(rows[:count - 1], before,
                                                       bi_standard=standard)
                    waiting = chan.analyze_available(rows, before,
                                                      bi_standard=standard)
                    self.assertEqual(waiting.to_dict(), original.to_dict())
                    late = dict(rows[count - 1], open=float('nan'),
                                low=-999, high=99999, available_dt=now)
                    self.assertEqual(chan.analyze_available(
                        rows[:count - 1] + [late], before,
                        bi_standard=standard).to_dict(), original.to_dict())
                    current = chan.analyze_available(rows, now,
                                                      bi_standard=standard)
                    self.assertEqual(current.to_dict(), chan.analyze_available(
                        rows[:count], now, bi_standard=standard).to_dict())
                    for path, parts in path_units(current.bis).items():
                        visible = [m for m in chan.same_level_decompose(parts)
                                   if m.complete]
                        self.assertEqual([move_record(m) for m in visible],
                                         [expected_shape(m) for m in
                                          case['paths'][path + '-' + standard]['completed']
                                          if m['confirmed_raw_count'] <= count])
                future_time = rows[-1]['available_dt'] + timedelta(days=1)
                future = chan.ConfirmedMove(None, None, None, None, None,
                                            float('nan'), None, None, None,
                                            future_time)
                for path in ('bi', 'xd'):
                    units = confirmed_inputs(case['paths'][path + '-' + standard])
                    now = rows[-1]['available_dt']
                    self.assertEqual(chan.confirm_level_up(units, now, 'F2'),
                                     chan.confirm_level_up(units + [future], now, 'F2'))


# 课35/38/84；复用0.9.0的F1-bi合同：固定笔无延伸同级切分。
# (起笔, 末笔, kind, 进入方向, 三段起点, 交集ticks, 证明笔, 首确认原始行)
# 交集/切点/证明来自独立区间表；不从库输出搜索或回填预期。
M3_F1_AUDIT = {
    'M3T81': {
        'completed': (
            (0, 2, 'consolidation', None, (0,), ((1495, 1524),), 3, 41),
            (3, 8, 'up', 'up', (3, 6), ((1495, 1582), (1685, 1728)), 9, 133),
            (9, 11, 'consolidation', None, (9,), ((1663, 1763),), 12, 165),
        ),
        'tail': (12, 14, 'consolidation', None, (12,), ((1784, 1849),), None, None),
        'f2_kind': 'incomplete', 'f2_centers': (),
    },
    'M3B81': {
        'completed': (
            (0, 2, 'consolidation', None, (0,), ((1767, 1808),), 3, 48),
            (3, 5, 'consolidation', None, (3,), ((1631, 1688),), 6, 68),
            (6, 8, 'consolidation', None, (6,), ((1626, 1702),), 9, 87),
            (9, 11, 'consolidation', None, (9,), ((1595, 1751),), 12, 126),
            (12, 14, 'consolidation', None, (12,), ((1631, 1765),), 15, 177),
        ),
        'tail': (15, 16, 'incomplete', None, (), (), None, None),
        'f2_kind': 'consolidation', 'f2_centers': ((1719, 1751),),
    },
}


def m3_cases():
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_causal_formation_81.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)['cases']


def m3_expected(case, spec):
    """装配已声明区间, 只读取冻结源坐标, 不调用识别器或寻找切点。"""
    a, z, kind, direction, triples, centers, proof, count = spec
    parts = case['units']
    return dict(kind=kind, complete=proof is not None, direction=direction,
                seg_start=a, seg_end=z, start_dt=parts[a]['start_dt'],
                end_dt=parts[z]['end_dt'], start_ticks=parts[a]['start_ticks'],
                end_ticks=parts[z]['end_ticks'],
                low_ticks=min(p['low_ticks'] for p in parts[a:z + 1]),
                high_ticks=max(p['high_ticks'] for p in parts[a:z + 1]),
                centers_ticks=[list(c) for c in centers], proof_unit=proof,
                confirmed_raw_count=count,
                confirmed_dt=(case['raw_rows'][count - 1]['dt'][:10]
                              + ' 15:05:00') if count is not None else None)


class TestRealM3MinimumTypes(unittest.TestCase):
    def test_declared_f1_tables_and_every_raw_prefix_confirmation(self):
        """两窗8个完整F1及未完成尾部, 全部原始前缀独立核对。"""
        for case in m3_cases():
            audit = M3_F1_AUDIT[case['window_key']]
            specs = audit['completed'] + (audit['tail'],)
            target = [m3_expected(case, spec) for spec in specs]
            for spec, record in zip(specs, target):
                triples, centers, proof, count = spec[4:]
                parts = case['units']
                actual = [(max(p['low_ticks'] for p in parts[j:j + 3]),
                           min(p['high_ticks'] for p in parts[j:j + 3]))
                          for j in triples]
                self.assertEqual(tuple(actual), centers, case['window_key'])
                if proof is not None:
                    self.assertEqual(case['foundation']['bis_confirmed_raw_count'][proof], count)
                    self.assertGreater(count,
                                       parts[record['seg_end']]['confirmed_raw_count'])
            bars = raw_bars(case)
            seen = {}
            for count in range(1, len(bars) + 1):
                _, _, bis = chan.chan_fx_bi(bars[:count], standard='81')
                moves = chan.same_level_decompose(bis[:-1])
                completed = [m for m in moves if m.complete]
                expected = [m for m in target if m['complete']
                            and m['confirmed_raw_count'] <= count]
                self.assertEqual([move_record(m) for m in completed],
                                 [expected_shape(m) for m in expected],
                                 (case['window_key'], count))
                for move in completed:
                    seen.setdefault(move.seg_start, count)
            self.assertEqual(seen, {m['seg_start']: m['confirmed_raw_count']
                                    for m in target if m['complete']})
            self.assertEqual([move_record(m) for m in moves],
                             [expected_shape(m) for m in target])

    def test_complete_f1_prefixes_cannot_manufacture_a_strict_f2_trend(self):
        """F1已确认才能递归；F2不完整时注入力度也不能生成严格结果。"""
        for case in m3_cases():
            audit = M3_F1_AUDIT[case['window_key']]
            completed = [m3_expected(case, s) for s in audit['completed']]
            units = confirmed_inputs(dict(completed=completed))
            calls = []

            def force(reference, leave):
                calls.append((reference, leave))
                return 10.0, 1.0

            for count, row in enumerate(case['raw_rows'], 1):
                now = date(row['dt'][:10]) + timedelta(hours=15, minutes=5)
                visible = [u for u in units if u.confirmed_dt <= now]
                self.assertEqual(chan.confirm_level_up(units, now, 'F2'), [])
                scan = chan.scan_strict_divergence(
                    units, now, 'F2', force_fn=force, force_method='boundary_test')
                self.assertEqual(scan.results, (), (case['window_key'], count))
                self.assertEqual(scan.completed_types, 0)
                self.assertEqual(scan.open_tail, bool(visible))
                self.assertEqual([reason for _, reason in scan.skipped],
                                 ['not_two_separated_centers'] if visible else [])
                poisoned = [u if u.confirmed_dt <= now else u._replace(
                    move_id=None, level=None, low=float('nan'), centers=None)
                            for u in units]
                self.assertEqual(chan.scan_strict_divergence(
                    poisoned, now, 'F2').to_dict(),
                    chan.scan_strict_divergence(units, now, 'F2').to_dict())
            self.assertEqual(calls, [])
            final = chan.level_up(units)
            self.assertEqual(len(final), 1)
            self.assertFalse(final[0].complete)
            self.assertEqual(final[0].kind, audit['f2_kind'])
            self.assertEqual(tuple((round(a * 1000), round(b * 1000))
                                   for a, b in final[0].centers),
                             audit['f2_centers'])
            _, _, bis = chan.chan_fx_bi(raw_bars(case), standard='81')
            with self.assertRaises(ValueError):
                chan.confirm_level_up(bis[:-1], now, 'F2')

    def test_r2_c_is_internal_and_core_shift_is_not_wave_separation(self):
        """辅助c笔在未完成F1内部；工程up的核心移位不证明严格波动分离。"""
        for case in m3_cases():
            c = case['first_point']['c_unit']
            target = [m3_expected(case, spec)
                      for spec in M3_F1_AUDIT[case['window_key']]['completed']]
            containing = [m for m in target if m['seg_start'] <= c <= m['seg_end']]
            self.assertEqual(len(containing), 1)
            move = containing[0]
            self.assertGreater(move['confirmed_raw_count'],
                               case['first_point']['first_raw_count'])
            self.assertNotEqual(move['end_dt'], case['units'][c]['end_dt'])
            self.assertEqual(sum(m['confirmed_raw_count'] <=
                                 case['first_point']['first_raw_count'] for m in target), 2)
            if case['window_key'] == 'M3T81':
                up = target[1]
                self.assertEqual(up['kind'], 'up')
                self.assertGreater(up['centers_ticks'][1][0], up['centers_ticks'][0][1])
                parts = case['units']
                first_gg = max(p['high_ticks'] for p in parts[3:6])
                second_dd = min(p['low_ticks'] for p in parts[6:9])
                self.assertEqual(second_dd - first_gg, -79)


if __name__ == '__main__':
    unittest.main()
