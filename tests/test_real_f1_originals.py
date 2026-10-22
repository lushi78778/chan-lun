# -*- coding: utf-8 -*-
"""课35/38/63/84: 真实固定笔及完成XD构造F1, 相邻F2的独立真值。

预期来自人工三段交集/切点/后继证明表, 编译器不导入chan。六窗口
共928原始日, 双标准和双路径分别回放。分型极值日和证据笔端点日
均不代替确认日。15:00闭合/15:05到达仅工程约定, 非供应时效实测。

另复用81因果条件两窗, 明示同一最低F1-bi规则后的真实完整类型及
F2未完成边界；独立区间表先于库比较声明, 不覆盖原条件fixture。
另复用既有5m/30m/日线报价，静态表核验34个完整F1到三个完成F2。
严格接口的波动重叠、未创新低与内部极值待判分别保留；输入为明示
最低F1-bi合同，不提升为精确理论一类点、严格成立或真实周期级别证明。
同一完整F1表另接三类条件；三组窗口六个中枢全部保留，不择样本或改切点。
另以600721已冻结的显式F1输入核三个完成F2的组成/证明与严格返回角色；
该条件表不新增独立F1理论标签，也不提供严格成立或真实周期级别证明。
宁德2022两窗另以固定q=p*f*10^6的84个显式固定笔回放19个完整F1条目；
该部分测试部件到达快照，原始行情/因子逐前缀对照由仓库验收收据单列。
"""
import json
import hashlib
import os
import unittest
from bisect import bisect_right
from datetime import datetime, timedelta
from types import SimpleNamespace

import chan


def load_labels():
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_f1_originals.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def date(value):
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S' if len(value) > 10 else '%Y-%m-%d')


def raw_bars(case, timed=False):
    rows = []
    daily = '-day-' in case['id']
    for r in case['raw_rows']:
        bar = dict(dt=date(r['dt']), open=r['open'], high=r['high'],
                   low=r['low'], close=r['close'], volume=r['vol'])
        if timed:
            bar['closed_dt'] = bar['dt'] + timedelta(hours=15 if daily else 0)
            bar['available_dt'] = bar['closed_dt'] + timedelta(minutes=5 if daily else 1)
        rows.append(bar)
    return rows


def unit_record(unit):
    return dict(start_index=unit.start_index, end_index=unit.end_index,
                start_ticks=round(unit.start_value * 1000),
                end_ticks=round(unit.end_value * 1000),
                start_dt=str(unit.start_dt)[:10], end_dt=str(unit.end_dt)[:10],
                low_ticks=round(unit.low * 1000),
                high_ticks=round(unit.high * 1000), direction=unit.direction)


def move_record(move, full_time=False):
    start = str(move.start_dt) if full_time else str(move.start_dt)[:10]
    end = str(move.end_dt) if full_time else str(move.end_dt)[:10]
    return dict(kind=move.kind, complete=bool(move.complete),
                direction=move.direction, seg_start=move.seg_start,
                seg_end=move.seg_end, start_dt=start,
                end_dt=end, low_ticks=round(move.low * 1000),
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


# 三个真实完成F2边界。固定月初重启、无窗前暖机；先冻结整数表再比较库。
# F1行：(起笔,末笔,kind,进入方向,三段起点,核心ticks,证明笔,首确认行数,
#        起/终原始行下标,起/终ticks,全段low/high ticks)。原始行下标从0起。
M3_STRICT_F2_AUDIT = {
    "M3I106": {
        'fixture': "real_third_point_xd_margin0.json",
        'source_sha256': "5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01",
        'parent_id': "512880-5m-20260201-20260724",
        'anchor': "2026-07-01", 'standard': "106", 'cutoff': 573,
        'f1': (
            (0, 2, "consolidation", None, (0,), ((1169, 1181),), 3, 63, 16, 36, 1181, 1169, 1167, 1191),
            (3, 6, "consolidation", "up", (4,), ((1146, 1155),), 7, 133, 36, 107, 1169, 1139, 1139, 1177),
            (7, 9, "consolidation", None, (7,), ((1144, 1156),), 10, 150, 107, 136, 1139, 1159, 1139, 1159),
            (10, 12, "consolidation", None, (10,), ((1152, 1159),), 13, 181, 136, 153, 1159, 1150, 1150, 1177),
            (13, 15, "consolidation", None, (13,), ((1150, 1159),), 16, 229, 153, 188, 1150, 1164, 1149, 1164),
            (16, 18, "consolidation", None, (16,), ((1128, 1131),), 19, 263, 188, 248, 1164, 1115, 1115, 1164),
            (19, 21, "consolidation", None, (19,), ((1116, 1122),), 22, 300, 248, 269, 1115, 1122, 1115, 1133),
            (22, 24, "consolidation", None, (22,), ((1110, 1122),), 25, 348, 269, 309, 1122, 1108, 1108, 1125),
            (25, 27, "consolidation", None, (25,), ((1111, 1127),), 28, 415, 309, 367, 1108, 1127, 1108, 1136),
            (28, 30, "consolidation", None, (28,), ((1100, 1106),), 31, 439, 367, 423, 1127, 1100, 1098, 1127),
            (31, 33, "consolidation", None, (31,), ((1100, 1101),), 34, 488, 423, 449, 1100, 1101, 1086, 1105),
            (34, 39, "consolidation", "down", (35,), ((1116, 1124),), 40, 572, 449, 538, 1101, 1132, 1085, 1139),
        ),
        'f2': (0, 10, "down", "down", (1, 6), ((1150, 1159), (1115, 1125)), 11),
        'spans': ((1, 3, 5), (6, 8, 9)), 'tails': (4, 8),
        'reference': (5, 5), 'leave': (9, 10), 'wave_gap': 3,
        'extreme': 1086, 'prior': 1108,
        'status': "insufficient_evidence", 'reason': "internal_extreme_time_unknown",
    },
    "M3N81": {
        'fixture': "real_third_point_xd_margin0.json",
        'source_sha256': "5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01",
        'parent_id': "588000-30m-20230501-20250228",
        'anchor': "2023-12-01", 'standard': "81", 'cutoff': 756,
        'f1': (
            (0, 2, "consolidation", None, (0,), ((898, 914),), 3, 120, 5, 63, 898, 924, 884, 924),
            (3, 5, "consolidation", None, (3,), ((883, 895),), 6, 147, 63, 126, 924, 877, 877, 924),
            (6, 8, "consolidation", None, (6,), ((877, 896),), 9, 261, 126, 184, 877, 899, 866, 899),
            (9, 11, "consolidation", None, (9,), ((810, 833),), 12, 313, 184, 301, 899, 778, 778, 899),
            (12, 14, "consolidation", None, (12,), ((778, 792),), 15, 359, 301, 334, 778, 792, 769, 811),
            (15, 17, "consolidation", None, (15,), ((781, 792),), 18, 442, 334, 408, 792, 666, 666, 796),
            (18, 20, "consolidation", None, (18,), ((781, 798),), 21, 467, 408, 449, 666, 798, 666, 804),
            (21, 23, "consolidation", None, (21,), ((791, 798),), 24, 516, 449, 480, 798, 791, 779, 806),
            (24, 26, "consolidation", None, (24,), ((804, 851),), 27, 561, 480, 532, 791, 862, 791, 862),
            (27, 29, "consolidation", None, (27,), ((842, 857),), 30, 595, 532, 571, 862, 829, 829, 862),
            (30, 32, "consolidation", None, (30,), ((853, 863),), 33, 632, 571, 600, 829, 863, 829, 867),
            (33, 38, "down", "down", (33, 36), ((833, 863), (788, 809)), 39, 755, 600, 720, 863, 815, 788, 865),
        ),
        'f2': (0, 10, "down", "down", (0, 4), ((884, 899), (769, 796)), 11),
        'spans': ((0, 2, 3), (4, 6, 8)), 'tails': (2, 8),
        'reference': (3, 3), 'leave': (9, 10), 'wave_gap': 4,
        'extreme': 829, 'prior': 666,
        'status': "rejected", 'reason': "no_new_extreme",
    },
    "M3W106": {
        'fixture': "real_strict_trend.json",
        'source_sha256': "ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde",
        'parent_id': "518880-day-20210101-20260731",
        'anchor': "2021-11-01", 'standard': "106", 'cutoff': 259,
        'f1': (
            (0, 2, "consolidation", None, (0,), ((3560, 3595),), 3, 45, 13, 32, 3745, 3550, 3550, 3745),
            (3, 5, "consolidation", None, (3,), ((3604, 3640),), 6, 63, 32, 52, 3550, 3658, 3550, 3658),
            (6, 8, "consolidation", None, (6,), ((3642, 3658),), 9, 84, 52, 68, 3658, 3642, 3620, 3680),
            (9, 11, "consolidation", None, (9,), ((3817, 3866),), 12, 97, 68, 86, 3642, 4077, 3642, 4077),
            (12, 14, "consolidation", None, (12,), ((3818, 3919),), 15, 120, 86, 102, 4077, 3818, 3792, 4077),
            (15, 17, "consolidation", None, (15,), ((3864, 3945),), 18, 136, 102, 124, 3818, 3945, 3818, 3969),
            (18, 20, "consolidation", None, (18,), ((3846, 3918),), 21, 157, 124, 141, 3945, 3846, 3834, 3945),
            (21, 24, "consolidation", "up", (22,), ((3750, 3812),), 25, 209, 141, 198, 3846, 3750, 3615, 3942),
            (25, 27, "consolidation", None, (25,), ((3750, 3792),), 28, 222, 198, 212, 3750, 3792, 3717, 3795),
            (28, 30, "consolidation", None, (28,), ((3766, 3792),), 31, 258, 212, 235, 3792, 3766, 3726, 3836),
        ),
        'f2': (0, 8, "up", "up", (0, 4), ((3620, 3658), (3834, 3945)), 9),
        'spans': ((0, 2, 3), (4, 6, 7)), 'tails': (2, 7),
        'reference': (3, 3), 'leave': (8, 8), 'wave_gap': -130,
        'extreme': None, 'prior': None,
        'status': "rejected", 'reason': "center_waves_overlap",
    },
}


def m3_strict_source(audit):
    """只消费已有fixture原始行情；旧笔/XD/买卖点标签不作为新预期。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures', audit['fixture'])
    with open(path, 'rb') as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != audit['source_sha256']:
        raise AssertionError('冻结原始fixture摘要漂移')
    parent = next(c for c in json.loads(payload.decode('utf-8'))['cases']
                  if c['id'] == audit['parent_id'])
    rows = [r for r in parent['raw_rows'] if r['dt'][:10] >= audit['anchor']]
    return dict(id=parent['id'], raw_rows=rows[:audit['cutoff']])


def m3_strict_records(audit, case):
    """静态整数表及源行时间装配F1，不从库输出反推边界或首次确认。"""
    rows = case['raw_rows']
    arrivals = raw_bars(case, timed=True)
    out = []
    for spec in audit['f1']:
        a, z, kind, direction, triples, centers, proof, count, start, end, p0, p1, lo, hi = spec
        out.append(dict(kind=kind, complete=True, direction=direction,
                        seg_start=a, seg_end=z, start_dt=rows[start]['dt'],
                        end_dt=rows[end]['dt'], start_ticks=p0, end_ticks=p1,
                        low_ticks=lo, high_ticks=hi, centers_ticks=[list(c) for c in centers],
                        proof_unit=proof, confirmed_raw_count=count,
                        confirmed_dt=str(arrivals[count-1]['available_dt'])))
    return out


class TestRealM3StrictF2Boundaries(unittest.TestCase):
    def test_independent_complete_f1_tables_at_every_raw_prefix(self):
        """34个完整F1的组成、全程极值、三段交集和首次确认逐原始前缀核对。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            records = m3_strict_records(audit, case)
            bars = raw_bars(case)
            seen = {}
            for count in range(1, len(bars)+1):
                fixed = chan.chan_fx_bi(bars[:count], standard=audit['standard'])[2][:-1]
                moves = [m for m in chan.same_level_decompose(fixed) if m.complete]
                expected = [m for m in records if m['confirmed_raw_count'] <= count]
                self.assertEqual([move_record(m, full_time=True) for m in moves],
                                 [expected_shape(m) for m in expected], (key, count))
                for actual, target in zip(moves, expected):
                    self.assertEqual((actual.low, actual.high),
                                     (target['low_ticks']/1000., target['high_ticks']/1000.))
                    seen.setdefault(actual.seg_start, count)
            self.assertEqual(seen, {m['seg_start']: m['confirmed_raw_count'] for m in records})
            for spec, record in zip(audit['f1'], records):
                triples, centers = spec[4:6]
                actual = tuple((round(max(u.low for u in fixed[j:j+3])*1000),
                                round(min(u.high for u in fixed[j:j+3])*1000))
                               for j in triples)
                self.assertEqual(actual, centers, key)
                self.assertGreater(record['confirmed_raw_count'], spec[9]+1)

    def test_f2_confirmation_includes_successor_proof_and_excludes_its_price_range(self):
        """F2端点早于确认；后继F1只供证明，不并入已完成类型的组成及极值。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            records = m3_strict_records(audit, case)
            units = confirmed_inputs(dict(completed=records))
            a, z, kind, direction, triples, centers, proof = audit['f2']
            now = units[proof].confirmed_dt
            for row in raw_bars(case, timed=True):
                current = chan.confirm_level_up(units, row['available_dt'], 'F2')
                if row['available_dt'] < now:
                    self.assertEqual(current, [], key)
                else:
                    self.assertEqual(len(current), 1, key)
                    move = current[0]
                    self.assertEqual((move.kind, move.direction), (kind, direction))
                    self.assertEqual((move.start_dt, move.end_dt), (units[a].start_dt, units[z].end_dt))
                    self.assertEqual((move.start_price, move.end_price),
                                     (units[a].start_price, units[z].end_price))
                    self.assertEqual(move.unit_ids, tuple(u.move_id for u in units[a:z+1]))
                    self.assertEqual(move.evidence_ids, tuple(u.move_id for u in units[:proof+1]))
                    self.assertEqual(move.confirmed_dt, now)
                    self.assertEqual(tuple((round(lo*1000), round(hi*1000)) for lo, hi in move.centers),
                                     centers)
                    self.assertEqual(move.low, min(u.low for u in units[a:z+1]))
                    self.assertEqual(move.high, max(u.high for u in units[a:z+1]))
                    self.assertGreater(now, move.end_dt)
            self.assertNotIn(units[proof].move_id, move.unit_ids)
            self.assertIn(units[proof].move_id, move.evidence_ids)
            if key == 'M3I106':
                self.assertEqual((move.low, units[proof].low), (1.086, 1.085))
            with self.assertRaises(ValueError):
                chan.confirm_level_up(chan.chan_fx_bi(raw_bars(case), standard=audit['standard'])[2][:-1], now, 'F2')

    def test_strict_rejection_and_insufficient_evidence_cannot_be_overridden_by_force(self):
        """完成F1→F2的真实必要条件；无效结构不评力度，未来毒字段不提前可见。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            records = m3_strict_records(audit, case)
            units = confirmed_inputs(dict(completed=records))
            calls = []

            def force(reference, leave):
                calls.append((reference, leave))
                return 10., 1.

            now = units[audit['f2'][-1]].confirmed_dt
            before = now-timedelta(microseconds=1)
            early = chan.scan_strict_divergence(units, before, 'F2')
            if key == 'M3W106':
                self.assertEqual(early.results, ())
                self.assertIn('center_waves_overlap', [reason for _, reason in early.skipped])
            else:
                self.assertEqual([(r.status, r.reason) for r in early.results],
                                 [('candidate', 'trend_open')], key)
            poisoned = [u if u.confirmed_dt <= before else u._replace(
                move_id=None, level=None, low=float('nan'), centers=None) for u in units]
            self.assertEqual(chan.scan_strict_divergence(poisoned, before, 'F2'), early)
            scan = chan.scan_strict_divergence(
                units, now, 'F2', force_fn=force, force_method='unused_boundary_probe')
            self.assertEqual(scan.completed_types, 1)
            self.assertEqual(len(scan.results), 1, key)
            result = scan.results[0]
            self.assertEqual((result.status, result.reason), (audit['status'], audit['reason']), key)
            serialized = json.loads(json.dumps(scan.to_dict()))['results'][0]
            self.assertEqual((serialized['status'], serialized['reason']),
                             (audit['status'], audit['reason']), key)
            self.assertEqual(serialized['center_range'],
                             None if result.center_range is None else list(result.center_range), key)
            self.assertEqual(result.confirmed_dt, now)
            self.assertEqual(result.kind, 'sell1' if audit['f2'][2] == 'up' else 'buy1')
            ra, rz = audit['reference']
            ca, cz = audit['leave']
            self.assertEqual(result.reference_ids, tuple(u.move_id for u in units[ra:rz+1]))
            self.assertEqual(result.leave_ids, tuple(u.move_id for u in units[ca:cz+1]))
            self.assertEqual((result.dt, result.price), (units[cz].end_dt, units[cz].end_price))
            self.assertIsNone(result.force_reference)
            self.assertIsNone(result.force_leave)
            pa = audit['spans'][-2][0]
            ba = audit['spans'][-1][0]
            pt, bt = audit['tails']
            first, last = records[pa:pt+1], records[ba:bt+1]
            gap = (min(u['low_ticks'] for u in last)-max(u['high_ticks'] for u in first)
                   if audit['f2'][2] == 'up' else
                   min(u['low_ticks'] for u in first)-max(u['high_ticks'] for u in last))
            self.assertEqual(gap, audit['wave_gap'], key)
            if audit['extreme'] is not None:
                extreme = min(u['low_ticks'] for u in records[ca:cz+1])
                prior = min(u['low_ticks'] for u in records[:bt+1])
                self.assertEqual((extreme, prior), (audit['extreme'], audit['prior']))
                if key == 'M3I106':
                    self.assertLess(extreme, prior)
                    self.assertNotEqual(records[cz]['end_ticks'], extreme)
                    self.assertEqual(result.conditions[-1], ('new_extreme', None))
                else:
                    self.assertGreaterEqual(extreme, prior)
                    self.assertEqual(result.conditions[-1], ('new_extreme', False))
            else:
                self.assertLessEqual(gap, 0)
                self.assertEqual(result.conditions[-1], ('separated_centers', False))
            future = units[-1]._replace(move_id=None, level=None, low=float('nan'),
                                       centers=None, confirmed_dt=now+timedelta(days=1))
            self.assertEqual(chan.scan_strict_divergence(
                units+[future], now, 'F2', force_fn=force, force_method='unused_boundary_probe'), scan)
            self.assertEqual(calls, [], key)


# 既有三个完整F1窗口的两个F2核心, 独立整数表在调用三类接口前冻结。
# 每行: (中枢首确认原始行数, 三类条件或None, 仍待首回试的离开F1下标或None)。
# 点行: (kind, leave/pull的F1下标, 回试端点原始行下标, 端点ticks,
#        实际确认原始行数, 全区间守沿余量ticks)。均为本窗口坐标。
M3_F1_THIRD_AUDIT = {
    'M3I106': ((181, ('sell3', 5, 6, 269, 1122, 300, 17), None),
               (415, None, 11)),
    'M3N81': ((261, None, None),
              (467, ('buy3', 8, 9, 571, 829, 595, 33), None)),
    'M3W106': ((84, None, None), (157, None, 9)),
}


def m3_third_contexts(key, audit, types):
    """只在三个完整F1均可见后冻结核心; 不用未来F2完成时刻回填。"""
    out = []
    for number, (start, formed, _) in enumerate(audit['spans']):
        if len(types) <= formed:
            continue
        parts = types[start:formed+1]
        center = chan.ConfirmedCenter(
            key+':center:'+str(number), 'F2', max(t.low for t in parts),
            min(t.high for t in parts), max(t.confirmed_dt for t in parts))
        out.append(chan.ThirdPointContext(key+':context:'+str(number), 'F2', 'F1', center))
    return out


class TestRealM3CompleteF1ThirdPoints(unittest.TestCase):
    """真实完整F1→三类条件; 最低规则/邻接明示, 不证明严格背驰或理论周期。"""

    def test_actual_complete_f1_pipeline_at_every_raw_prefix(self):
        """1588个原始前缀从行情产生完整F1, 再冻结因果中枢及首离开/首回试。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            rows = raw_bars(case, timed=True)
            frozen, history = {}, {}
            for count, row in enumerate(rows, 1):
                fixed = chan.chan_fx_bi(rows[:count], standard=audit['standard'])[2][:-1]
                completed = [m for m in chan.same_level_decompose(fixed) if m.complete]
                for m in completed:
                    old = frozen.get(m.seg_start)
                    item = chan.ConfirmedMoveType(
                        'f1:'+str(m.seg_start), 'F1', m.kind, m.direction, m.start_dt, m.end_dt,
                        fixed[m.seg_start].start_value, fixed[m.seg_end].end_value, m.low, m.high,
                        row['available_dt'] if old is None else old.confirmed_dt,
                        tuple('component:'+str(i) for i in range(m.seg_start, m.seg_end+1)),
                        tuple('component:'+str(i) for i in range(len(fixed)))
                        if old is None else old.evidence_ids, tuple(m.centers))
                    if old is not None:
                        self.assertEqual(item, old, (key, count, '完成F1回写'))
                    frozen[m.seg_start] = item
                self.assertEqual([m.seg_start for m in completed], sorted(frozen))
                types = [frozen[i] for i in sorted(frozen)]
                moves = [t.to_confirmed_move() for t in types]
                for item, move in zip(types, moves):
                    self.assertEqual((move.low, move.high, move.confirmed_dt),
                                     (item.low, item.high, item.confirmed_dt))
                contexts = m3_third_contexts(key, audit, types)
                actual = chan.find_third_points(moves, contexts, row['available_dt'])
                expected = []
                for number, (_, point, _) in enumerate(M3_F1_THIRD_AUDIT[key]):
                    if point is None or count < point[5]:
                        continue
                    kind, leave, pull, end, price, known, margin = point
                    expected.append((kind, key+':context:'+str(number), key+':center:'+str(number),
                                     rows[end]['dt'], price/1000., rows[known-1]['available_dt'],
                                     'f1:'+str(audit['f1'][leave][0]),
                                     'f1:'+str(audit['f1'][pull][0])))
                self.assertEqual([(p.kind, p.context_id, p.center_id, p.dt, p.price,
                                   p.confirmed_dt, p.leave_move_id, p.pull_move_id) for p in actual],
                                 expected, (key, count))
                for p in actual:
                    if p.context_id in history:
                        self.assertEqual(p, history[p.context_id])
                    history[p.context_id] = p
            declared = confirmed_inputs(dict(completed=m3_strict_records(audit, case)))
            self.assertEqual(types, declared, key)
            for number, context in enumerate(contexts):
                known, _, pending = M3_F1_THIRD_AUDIT[key][number]
                self.assertEqual(context.center.confirmed_dt, rows[known-1]['available_dt'])
                core = audit['f2'][5][number]
                self.assertEqual((context.center.zd, context.center.zg), tuple(v/1000. for v in core))
                # 首个紧接的F1开始早于中枢可知, 不能倒填为因果离开。
                formed = audit['spans'][number][1]
                self.assertLess(types[formed+1].start_dt, context.center.confirmed_dt)
                if pending is not None:
                    last = moves[pending]
                    self.assertEqual(pending, len(moves)-1)
                    self.assertGreaterEqual(last.start_dt, context.center.confirmed_dt)
                    self.assertLessEqual(last.low, context.center.zg)
                    self.assertGreaterEqual(last.high, context.center.zd)
                    self.assertTrue(last.end_price > context.center.zg if last.direction == 'up'
                                    else last.end_price < context.center.zd)

    def test_full_future_types_and_centers_do_not_enter_earlier_snapshots(self):
        """完整输入按观察截止与真实可见前缀同值; 未来身份/极值/中枢毒值不读取。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            rows = raw_bars(case, timed=True)
            types = confirmed_inputs(dict(completed=m3_strict_records(audit, case)))
            moves = [t.to_confirmed_move() for t in types]
            contexts = m3_third_contexts(key, audit, types)
            for row in rows:
                now = row['available_dt']
                visible = [m for m in moves if m.confirmed_dt <= now]
                known = [c for c in contexts if c.center.confirmed_dt <= now]
                expected = chan.find_third_points(visible, known, now)
                self.assertEqual(chan.find_third_points(moves, contexts, now), expected)
                poison = [m if m.confirmed_dt <= now else m._replace(
                    move_id=None, level=None, low=float('nan'), high=float('inf')) for m in moves]
                future = [c if c.center.confirmed_dt <= now else c._replace(
                    level=None, sub_level=None, center=c.center._replace(
                        center_id=None, zd=float('nan'), zg=float('inf'))) for c in contexts]
                self.assertEqual(chan.find_third_points(poison, future, now), expected)

    def test_external_proof_delay_and_center_causality_on_both_real_sides(self):
        """回试端点不能代替外部证明; 人工延迟是工程变体, 不另计真实反例。"""
        for key, audit in sorted(M3_STRICT_F2_AUDIT.items()):
            case = m3_strict_source(audit)
            types = confirmed_inputs(dict(completed=m3_strict_records(audit, case)))
            moves = [t.to_confirmed_move() for t in types]
            contexts = m3_third_contexts(key, audit, types)
            for number, (_, point, _) in enumerate(M3_F1_THIRD_AUDIT[key]):
                if point is None:
                    continue
                _, leave, pull, _, _, _, margin = point
                context = contexts[number]
                target = moves[pull]
                endpoint = chan.find_third_points(moves, [context], target.end_dt)
                self.assertEqual(endpoint, [])
                actual, = chan.find_third_points(moves, [context], target.confirmed_dt)
                self.assertGreater(actual.confirmed_dt, actual.dt)
                self.assertEqual(round((context.center.zd-target.high if actual.kind == 'sell3'
                                        else target.low-context.center.zg)*1000), margin)
                delay = target.confirmed_dt+timedelta(minutes=1)
                late = [m._replace(confirmed_dt=delay) if i == pull else m for i, m in enumerate(moves)]
                self.assertEqual(chan.find_third_points(late, [context], target.confirmed_dt), [])
                delayed, = chan.find_third_points(late, [context], delay)
                self.assertEqual(delayed, actual._replace(confirmed_dt=delay))
                late_center = context._replace(center=context.center._replace(
                    confirmed_dt=moves[leave].start_dt+timedelta(microseconds=1)))
                self.assertFalse(any(p.leave_move_id == moves[leave].move_id for p in
                                     chan.find_third_points(moves, [late_center], moves[-1].confirmed_dt)))


# 显式F1-bi输入；来源为已冻结接续算术，不新增独立F1理论标签。
# 输入行：(起/末笔,kind,进入方向,起/末日,起/末价,全段低/高,首确认行,确认日时,证据笔数,核心)。
M3_JOINED_F2_AUDIT = {
    'source_expectations_sha256': '8b00e438b838b894e5616f3e1755654f5cabad5d1d6b873f9362e1875d2ac431',
    'inputs': {
        '81': (
            (0, 2, 'consolidation', None, '2013-11-14', '2013-12-19', 6820, 8190, 6820, 8190, 83, '2014-02-14 15:05:00', 4, ((7220, 8000),)),
            (3, 5, 'consolidation', None, '2013-12-19', '2014-02-28', 8190, 6540, 6470, 8190, 135, '2014-04-30 15:05:00', 7, ((6540, 7990),)),
            (6, 8, 'consolidation', None, '2014-02-28', '2014-05-14', 6540, 7520, 6480, 7520, 156, '2014-06-03 15:05:00', 10, ((6540, 7370),)),
            (9, 11, 'consolidation', None, '2014-05-14', '2014-06-20', 7520, 6910, 6900, 8260, 210, '2014-08-18 15:05:00', 13, ((6910, 7520),)),
            (12, 17, 'up', 'up', '2014-06-20', '2014-10-24', 6910, 9000, 6910, 11300, 274, '2014-11-24 15:05:00', 19, ((8090, 8500), (9170, 9800))),
            (18, 20, 'consolidation', None, '2014-10-24', '2014-12-16', 9000, 10200, 9000, 11190, 310, '2015-01-15 15:05:00', 22, ((9250, 10200),)),
            (21, 23, 'consolidation', None, '2014-12-16', '2015-02-10', 10200, 8600, 8510, 10200, 380, '2015-05-04 15:05:00', 25, ((8600, 9980),)),
            (24, 28, 'consolidation', None, '2015-02-10', '2015-06-18', 8600, 23300, 8600, 23300, 439, '2015-07-27 15:05:00', 30, ((13220, 18780),)),
            (29, 31, 'consolidation', None, '2015-06-18', '2016-03-11', 23300, 13030, 9190, 23300, 633, '2016-05-13 15:05:00', 33, ((13030, 20790),)),
            (32, 34, 'consolidation', None, '2016-03-11', '2016-06-13', 13030, 17310, 13030, 17640, 669, '2016-07-06 15:05:00', 36, ((14550, 17310),)),
            (35, 38, 'consolidation', 'down', '2016-06-13', '2016-08-09', 17310, 21000, 16200, 21000, 733, '2016-10-13 15:05:00', 40, ((17600, 19200),)),
            (39, 41, 'consolidation', None, '2016-08-09', '2016-11-04', 21000, 18420, 18000, 21000, 765, '2016-11-28 15:05:00', 43, ((18420, 20540),)),
            (42, 44, 'consolidation', None, '2016-11-04', '2016-12-27', 18420, 19000, 17210, 19270, 813, '2017-02-10 15:05:00', 46, ((18420, 19000),)),
            (45, 47, 'consolidation', None, '2016-12-27', '2017-02-16', 19000, 16880, 15880, 19000, 836, '2017-03-15 15:05:00', 49, ((16880, 17440),)),
            (48, 51, 'consolidation', 'up', '2017-02-16', '2017-06-01', 16880, 12480, 12480, 19710, 921, '2017-07-19 15:05:00', 53, ((13650, 15400),)),
            (52, 54, 'consolidation', None, '2017-06-01', '2017-08-09', 12480, 14630, 12480, 15390, 950, '2017-08-29 15:05:00', 56, ((12700, 14630),)),
            (55, 64, 'down', 'down', '2017-08-09', '2018-01-09', 14630, 11950, 9960, 15120, 1050, '2018-01-24 15:05:00', 66, ((13310, 14630), (12000, 12410), (10330, 11180))),
            (65, 67, 'consolidation', None, '2018-01-09', '2018-02-09', 11950, 7020, 7020, 11950, 1089, '2018-03-27 15:05:00', 69, ((10040, 10510),)),
            (68, 70, 'consolidation', None, '2018-02-09', '2018-04-04', 7020, 10750, 7020, 11690, 1112, '2018-05-03 15:05:00', 72, ((8680, 10750),)),
        ),
        '106': (
            (0, 2, 'consolidation', None, '2013-11-14', '2013-12-19', 6820, 8190, 6820, 8190, 68, '2014-01-17 15:05:00', 4, ((7220, 8000),)),
            (3, 5, 'consolidation', None, '2013-12-19', '2014-01-21', 8190, 6470, 6470, 8190, 92, '2014-02-27 15:05:00', 7, ((6500, 6900),)),
            (6, 8, 'consolidation', None, '2014-01-21', '2014-04-17', 6470, 7370, 6470, 7990, 138, '2014-05-07 15:05:00', 10, ((6540, 7370),)),
            (9, 11, 'consolidation', None, '2014-04-17', '2014-05-23', 7370, 6900, 6480, 7520, 162, '2014-06-11 15:05:00', 13, ((6900, 7370),)),
            (12, 14, 'consolidation', None, '2014-05-23', '2014-06-13', 6900, 7640, 6900, 8260, 179, '2014-07-04 15:05:00', 16, ((7210, 7640),)),
            (15, 18, 'consolidation', 'down', '2014-06-13', '2014-08-28', 7640, 9800, 6910, 9800, 261, '2014-11-05 15:05:00', 22, ((8090, 8500),)),
            (19, 21, 'consolidation', None, '2014-08-28', '2014-10-24', 9800, 9000, 9000, 11300, 274, '2014-11-24 15:05:00', 23, ((9170, 9800),)),
            (22, 24, 'consolidation', None, '2014-10-24', '2014-12-16', 9000, 10200, 9000, 11190, 310, '2015-01-15 15:05:00', 26, ((9250, 10200),)),
            (25, 27, 'consolidation', None, '2014-12-16', '2015-02-10', 10200, 8600, 8510, 10200, 373, '2015-04-22 15:05:00', 29, ((8600, 9980),)),
            (28, 32, 'consolidation', None, '2015-02-10', '2015-06-15', 8600, 23740, 8600, 23740, 431, '2015-07-15 15:05:00', 34, ((13220, 18780),)),
            (33, 35, 'consolidation', None, '2015-06-15', '2016-03-11', 23740, 13030, 9190, 23740, 604, '2016-03-31 15:05:00', 37, ((13030, 20790),)),
            (36, 38, 'consolidation', None, '2016-03-11', '2016-04-19', 13030, 17610, 13030, 17610, 623, '2016-04-28 15:05:00', 40, ((14850, 16350),)),
            (39, 41, 'consolidation', None, '2016-04-19', '2016-05-12', 17610, 14550, 14550, 17640, 641, '2016-05-25 15:05:00', 43, ((15770, 17610),)),
            (42, 48, 'up', 'up', '2016-05-12', '2016-08-31', 14550, 20700, 14550, 21000, 733, '2016-10-13 15:05:00', 50, ((15850, 16590), (19610, 20700))),
            (49, 51, 'consolidation', None, '2016-08-31', '2016-11-04', 20700, 18420, 18000, 20700, 765, '2016-11-28 15:05:00', 53, ((18420, 20540),)),
            (52, 54, 'consolidation', None, '2016-11-04', '2016-12-01', 18420, 18520, 17910, 19270, 780, '2016-12-19 15:05:00', 56, ((18420, 18520),)),
            (55, 57, 'consolidation', None, '2016-12-01', '2017-01-18', 18520, 15880, 15880, 19000, 818, '2017-02-17 15:05:00', 59, ((17210, 18520),)),
            (58, 60, 'consolidation', None, '2017-01-18', '2017-03-06', 15880, 19710, 15880, 19710, 870, '2017-05-05 15:05:00', 62, ((16880, 17440),)),
            (61, 63, 'consolidation', None, '2017-03-06', '2017-05-23', 19710, 12550, 12550, 19710, 896, '2017-06-14 15:05:00', 65, ((13650, 15400),)),
            (64, 66, 'consolidation', None, '2017-05-23', '2017-06-29', 12550, 15390, 12550, 15390, 927, '2017-07-27 15:05:00', 68, ((12940, 13950),)),
            (67, 69, 'consolidation', None, '2017-06-29', '2017-08-03', 15390, 13140, 12700, 15390, 942, '2017-08-17 15:05:00', 71, ((13140, 13870),)),
            (70, 72, 'consolidation', None, '2017-08-03', '2017-08-22', 13140, 14670, 13140, 14670, 955, '2017-09-05 15:05:00', 74, ((13310, 14630),)),
            (73, 78, 'down', 'down', '2017-08-22', '2017-11-03', 14670, 13170, 12000, 15120, 1014, '2017-12-04 15:05:00', 80, ((13990, 14670), (12650, 13170))),
            (79, 81, 'consolidation', None, '2017-11-03', '2017-12-15', 13170, 9960, 9960, 13170, 1045, '2018-01-17 15:05:00', 83, ((10330, 11180),)),
            (82, 84, 'consolidation', None, '2017-12-15', '2018-01-23', 9960, 10510, 9960, 11950, 1070, '2018-02-28 15:05:00', 86, ((10040, 10510),)),
            (85, 87, 'consolidation', None, '2018-01-23', '2018-03-26', 10510, 8680, 7020, 11690, 1105, '2018-04-20 15:05:00', 89, ((8680, 10510),)),
            (88, 90, 'consolidation', None, '2018-03-26', '2018-05-11', 8680, 10090, 8040, 10750, 1131, '2018-05-30 15:05:00', 92, ((8680, 10090),)),
            (91, 93, 'consolidation', None, '2018-05-11', '2018-06-05', 10090, 8680, 8680, 10920, 1146, '2018-06-21 15:05:00', 95, ((8860, 10090),)),
            (94, 97, 'consolidation', 'up', '2018-06-05', '2018-07-11', 8680, 6270, 6270, 9430, 1180, '2018-08-08 15:05:00', 99, ((7070, 7790),)),
            (98, 100, 'consolidation', None, '2018-07-11', '2018-08-10', 6270, 6540, 5790, 7290, 1195, '2018-08-29 15:05:00', 102, ((6270, 6540),)),
            (101, 103, 'consolidation', None, '2018-08-10', '2018-09-03', 6540, 5480, 5430, 6540, 1210, '2018-09-19 15:05:00', 105, ((5480, 6030),)),
            (104, 106, 'consolidation', None, '2018-09-03', '2018-09-28', 5480, 6860, 5480, 6860, 1232, '2018-10-29 15:05:00', 108, ((5520, 5950),)),
            (107, 109, 'consolidation', None, '2018-09-28', '2018-11-30', 6860, 5470, 4300, 6860, 1274, '2018-12-26 15:05:00', 111, ((5470, 6390),)),
            (110, 112, 'consolidation', None, '2018-11-30', '2019-01-28', 5470, 6570, 5110, 6570, 1312, '2019-02-27 15:05:00', 114, ((5470, 5830),)),
            (113, 115, 'consolidation', None, '2019-01-28', '2019-03-01', 6570, 5830, 4460, 6570, 1328, '2019-03-21 15:05:00', 117, ((5830, 6360),)),
            (116, 118, 'consolidation', None, '2019-03-01', '2019-04-10', 5830, 7070, 5620, 7530, 1352, '2019-04-25 15:05:00', 120, ((5830, 7070),)),
            (119, 124, 'down', 'down', '2019-04-10', '2019-07-05', 7070, 5720, 4840, 7130, 1410, '2019-07-22 15:05:00', 126, ((6490, 7070), (5080, 5660))),
            (125, 127, 'consolidation', None, '2019-07-05', '2019-08-15', 5720, 5580, 5520, 6470, 1443, '2019-09-05 15:05:00', 129, ((5580, 5720),)),
            (128, 130, 'consolidation', None, '2019-08-15', '2019-09-16', 5580, 5940, 5580, 6240, 1467, '2019-10-17 15:05:00', 132, ((5720, 5940),)),
            (131, 133, 'consolidation', None, '2019-09-16', '2019-11-01', 5940, 5480, 5300, 6040, 1492, '2019-11-21 15:05:00', 135, ((5480, 5940),)),
            (134, 139, 'up', 'up', '2019-11-01', '2020-03-02', 5480, 6040, 5270, 7240, 1574, '2020-03-25 15:05:00', 141, ((5480, 5880), (6040, 7230))),
        ),
    },
    'cases': {
        '81-up': {
            'standard': '81',
            'f2': [0, 14, 'up', 'up', [0, 5, 10], [[6820, 7520], [9000, 10200], [18000, 19270]], 18],
            'spans': [[0, 2, 4], [5, 7, 8], [10, 12, 14]],
            'tails': (8, 14),
            'reference': (9, 9),
            'leave': None,
            'waves': [[8510, 23300], [12480, 21000]],
            'wave_overlap': (12480, 21000),
            'status': 'skipped',
            'reason': 'no_compare_legs',
            'confirmed_raw_count': 1112,
            'completion': ('reverse_center', 15, (16, 17, 18), (9960, 11690)),
        },
        '106-up': {
            'standard': '106',
            'f2': [0, 15, 'up', 'up', [0, 6, 11], [[6820, 7990], [9000, 10200], [14550, 17610]], 16],
            'spans': [[0, 2, 5], [6, 8, 10], [11, 13, 13]],
            'tails': (10, None),
            'reference': None,
            'leave': None,
            'waves': [[8510, 23740], [13030, 21000]],
            'wave_overlap': (13030, 21000),
            'status': 'skipped',
            'reason': 'no_comparable_center_tail',
            'confirmed_raw_count': 818,
            'completion': ('first_return', 14, None, None),
        },
        '106-down': {
            'standard': '106',
            'f2': [16, 39, 'down', 'down', [16, 19, 24, 28], [[15880, 19000], [13140, 14670], [9960, 10750], [6270, 6540]], 40],
            'spans': [[16, 18, 18], [19, 21, 23], [24, 26, 27], [28, 30, 37]],
            'tails': (26, 35),
            'reference': (27, 27),
            'leave': (36, 39),
            'waves': [[7020, 11950], [4300, 9430]],
            'wave_overlap': (7020, 9430),
            'status': 'rejected',
            'reason': 'center_waves_overlap',
            'confirmed_raw_count': 1574,
            'completion': ('first_return', 38, None, None),
        },
    },
}


def joined_f1_inputs(standard):
    """仅装配已声明的F1快照；不由F2结果反推切点或重新搜索行情。"""
    records = []
    for row in M3_JOINED_F2_AUDIT['inputs'][standard]:
        a, z, kind, direction, start, end, p0, p1, lo, hi, count, known, evidence, cores = row
        records.append(dict(seg_start=a, seg_end=z, kind=kind, direction=direction,
                            start_dt=start, end_dt=end, start_ticks=p0, end_ticks=p1,
                            low_ticks=lo, high_ticks=hi, confirmed_raw_count=count,
                            confirmed_dt=known, proof_unit=evidence-1, centers_ticks=cores))
    return confirmed_inputs(dict(completed=records))


class TestJoinedF2Roles(unittest.TestCase):
    def test_successor_proofs_close_f2_without_joining_its_composition(self):
        """课35/38：反向新核或首次回入的证明独立于组成；实际到达才确认。"""
        for key, audit in sorted(M3_JOINED_F2_AUDIT['cases'].items()):
            units = joined_f1_inputs(audit['standard'])
            a, z, kind, direction, _, centers, proof = audit['f2']
            now = units[proof].confirmed_dt
            for cutoff in (units[z].end_dt, units[z].confirmed_dt,
                           now.replace(hour=15, minute=0), now-timedelta(microseconds=1)):
                early = chan.confirm_level_up(units, cutoff, 'F2')
                self.assertFalse(any(m.unit_ids[0] == units[a].move_id for m in early), key)
            closed = chan.confirm_level_up(units, now, 'F2')
            move, = [m for m in closed if m.unit_ids[0] == units[a].move_id]
            self.assertEqual((move.kind, move.direction), (kind, direction), key)
            self.assertEqual((move.start_dt, move.end_dt), (units[a].start_dt, units[z].end_dt))
            self.assertEqual((move.start_price, move.end_price), (units[a].start_price, units[z].end_price))
            self.assertEqual(move.unit_ids, tuple(u.move_id for u in units[a:z+1]))
            self.assertEqual(move.evidence_ids, tuple(u.move_id for u in units[:proof+1]))
            self.assertTrue(set(u.move_id for u in units[z+1:proof+1]).isdisjoint(move.unit_ids))
            self.assertEqual(move.confirmed_dt, now)
            self.assertGreater(now, max(u.confirmed_dt for u in units[a:z+1]))
            self.assertEqual((move.low, move.high),
                             (min(u.low for u in units[a:z+1]), max(u.high for u in units[a:z+1])))
            self.assertEqual(move.centers, tuple((lo/1000., hi/1000.) for lo, hi in centers))
            delay = now+timedelta(days=1)
            late = [u._replace(confirmed_dt=delay) if i == proof else u for i, u in enumerate(units)]
            self.assertFalse(any(m.move_id == move.move_id for m in chan.confirm_level_up(late, now, 'F2')))
            delayed, = [m for m in chan.confirm_level_up(late, delay, 'F2') if m.move_id == move.move_id]
            self.assertEqual(delayed, move._replace(confirmed_dt=delay))

    def test_missing_roles_and_wave_rejection_do_not_reach_force(self):
        """课20/37：核心分离不充分；缺角色先跳过，完整波动重叠才按条件否决。"""
        def forbidden_force(reference, leave):
            raise AssertionError('三个结构均不得进入力度判断')

        for key, audit in sorted(M3_JOINED_F2_AUDIT['cases'].items()):
            units = joined_f1_inputs(audit['standard'])
            a, _, _, _, _, _, proof = audit['f2']
            now = units[proof].confirmed_dt
            move, = [m for m in chan.confirm_level_up(units, now, 'F2')
                     if m.unit_ids[0] == units[a].move_id]
            scan = chan.scan_strict_divergence(units, now, 'F2',
                                               force_fn=forbidden_force, force_method='unused')
            found = [r for r in scan.results if r.trend_id == move.move_id]
            if audit['status'] == 'skipped':
                self.assertEqual(found, [], key)
                self.assertIn((move.move_id, audit['reason']), scan.skipped, key)
            else:
                result, = found
                self.assertEqual((result.status, result.reason), (audit['status'], audit['reason']))
                self.assertEqual(result.conditions, (('trend', True), ('separated_centers', False)))
                self.assertIsNone(result.center_range)
                self.assertIsNone(json.loads(json.dumps(result.to_dict()))['center_range'])
                ra, rz = audit['reference']
                ca, cz = audit['leave']
                self.assertEqual(result.reference_ids, tuple(u.move_id for u in units[ra:rz+1]))
                self.assertEqual(result.leave_ids, tuple(u.move_id for u in units[ca:cz+1]))
            json.dumps(scan.to_dict())

    def test_visible_f1_prefixes_keep_closed_results_and_ignore_future_fields(self):
        """60个显式F1到达前缀：未来毒值不提前读取；已完成F2及否决结果不回写。"""
        for standard in ('81', '106'):
            units = joined_f1_inputs(standard)
            closed, rejected = {}, {}
            for unit in units:
                now = unit.confirmed_dt
                visible = [u for u in units if u.confirmed_dt <= now]
                future = [u if u.confirmed_dt <= now else u._replace(
                    move_id=None, level=None, low=float('nan'), centers=None) for u in units]
                moves = chan.confirm_level_up(visible, now, 'F2')
                self.assertEqual(chan.confirm_level_up(future, now, 'F2'), moves)
                scan = chan.scan_strict_divergence(visible, now, 'F2')
                self.assertEqual(chan.scan_strict_divergence(future, now, 'F2'), scan)
                for move in moves:
                    if move.move_id in closed:
                        self.assertEqual(move, closed[move.move_id])
                    closed[move.move_id] = move
                for result in scan.results:
                    if result.status == chan.STRICT_CANDIDATE:
                        continue
                    if result.divergence_id in rejected:
                        self.assertEqual(result, rejected[result.divergence_id])
                    rejected[result.divergence_id] = result
            self.assertEqual(len(closed), 1 if standard == '81' else 2)
            self.assertEqual(len(rejected), 0 if standard == '81' else 1)


# 已核原价/因子快照的固定q坐标输入；计算回归不新增独立理论标签。
M3_FACTOR_F1_AUDIT = {'source_zip_sha256': 'a6bff9dc97915b70807a2327104d2609c38f44418407ab843981a5c6ed9c3b7e',
 'expectations_sha256': 'd31bc4daff2e239ab90222cb446da6953f40636996f1544dac4ec05eef8b14de',
 'price_multiplier': 1000000,
 'independent_theory_labels': False,
 'cases': {'2022-01-01-81': {'rows': 242,
                             'parts': ((2, 11, '2022-01-10', '2022-02-07', 526277196640, 612350382280, 32),
                                       (11, 20, '2022-02-07', '2022-02-22', 612350382280, 494283349820, 37),
                                       (20, 24, '2022-02-22', '2022-03-01', 494283349820, 550209838880, 42),
                                       (24, 29, '2022-03-01', '2022-03-08', 550209838880, 444731536860, 49),
                                       (29, 36, '2022-03-08', '2022-03-17', 444731536860, 537079010000, 54),
                                       (36, 59, '2022-03-17', '2022-05-05', 537079010000, 354371758000, 88),
                                       (59, 65, '2022-05-05', '2022-05-20', 354371758000, 433678752000, 94),
                                       (65, 69, '2022-05-20', '2022-05-26', 433678752000, 390391187680, 101),
                                       (69, 82, '2022-05-26', '2022-06-27', 390391187680, 567165473420, 126),
                                       (82, 90, '2022-06-27', '2022-07-12', 567165473420, 501561523320, 134),
                                       (90, 97, '2022-07-12', '2022-07-22', 501561523320, 546103945140, 139),
                                       (97, 106, '2022-07-22', '2022-08-08', 546103945140, 490900254000, 153),
                                       (106, 114, '2022-08-08', '2022-08-24', 490900254000, 577234450000, 166),
                                       (114, 123, '2022-08-24', '2022-09-06', 577234450000, 445604917680, 170),
                                       (123, 127, '2022-09-06', '2022-09-13', 445604917680, 461988337200, 177),
                                       (127, 140, '2022-09-13', '2022-10-10', 461988337200, 393345771840, 191),
                                       (140, 145, '2022-10-10', '2022-10-19', 393345771840, 444390336000, 199),
                                       (145, 152, '2022-10-19', '2022-10-31', 444390336000, 358508384640, 205),
                                       (152, 156, '2022-10-31', '2022-11-08', 358508384640, 425086502400, 212),
                                       (156, 161, '2022-11-08', '2022-11-17', 425086502400, 372011014080, 217),
                                       (161, 181, '2022-11-17', '2022-12-19', 372011014080, 432425980800, 239)),
                             'f1': ((0,
                                     2,
                                     'consolidation',
                                     None,
                                     (0,),
                                     ((526277196640, 550209838880),),
                                     3,
                                     49,
                                     '2022-03-18 15:05:00'),
                                    (3,
                                     7,
                                     'consolidation',
                                     None,
                                     (3,),
                                     ((444731536860, 537079010000),),
                                     8,
                                     126,
                                     '2022-07-13 15:05:00'),
                                    (8,
                                     10,
                                     'consolidation',
                                     None,
                                     (8,),
                                     ((501561523320, 546103945140),),
                                     11,
                                     153,
                                     '2022-08-19 15:05:00'),
                                    (11,
                                     17,
                                     'down',
                                     'down',
                                     (11, 15),
                                     ((490900254000, 546103945140), (393345771840, 444390336000)),
                                     18,
                                     212,
                                     '2022-11-18 15:05:00')),
                             'tail': {'kind': 'consolidation',
                                      'complete': False,
                                      'direction': None,
                                      'seg_start': 18,
                                      'seg_end': 20,
                                      'start_dt': '2022-10-31',
                                      'end_dt': '2022-12-19',
                                      'start_ticks': 358508384640,
                                      'end_ticks': 432425980800,
                                      'low_ticks': 358508384640,
                                      'high_ticks': 432425980800,
                                      'centers_ticks': [[372011014080, 425086502400]]},
                             'f2_tail': {'kind': 'consolidation',
                                         'complete': False,
                                         'direction': None,
                                         'seg_start': 0,
                                         'seg_end': 3,
                                         'start_dt': '2022-01-10',
                                         'end_dt': '2022-10-31',
                                         'start_ticks': 526277196640,
                                         'end_ticks': 358508384640,
                                         'low_ticks': 354371758000,
                                         'high_ticks': 612350382280,
                                         'centers_ticks': [[494283349820, 550209838880]]},
                             'factors': (('2022-01-04', '1.003886'), ('2022-09-28', '1.005408'))},
           '2022-01-01-106': {'rows': 242,
                              'parts': ((2, 11, '2022-01-10', '2022-02-07', 526277196640, 612350382280, 26),
                                        (11, 14, '2022-02-07', '2022-02-14', 612350382280, 486944943160, 29),
                                        (14, 17, '2022-02-14', '2022-02-17', 486944943160, 545612041000, 32),
                                        (17, 20, '2022-02-17', '2022-02-22', 545612041000, 494283349820, 37),
                                        (20, 24, '2022-02-22', '2022-03-01', 494283349820, 550209838880, 42),
                                        (24, 29, '2022-03-01', '2022-03-08', 550209838880, 444731536860, 49),
                                        (29, 36, '2022-03-08', '2022-03-17', 444731536860, 537079010000, 52),
                                        (36, 59, '2022-03-17', '2022-05-05', 537079010000, 354371758000, 88),
                                        (59, 65, '2022-05-05', '2022-05-20', 354371758000, 433678752000, 94),
                                        (65, 69, '2022-05-20', '2022-05-26', 433678752000, 390391187680, 101),
                                        (69, 73, '2022-05-26', '2022-06-07', 390391187680, 470832572860, 106),
                                        (73, 76, '2022-06-07', '2022-06-14', 470832572860, 430365928200, 115),
                                        (76, 82, '2022-06-14', '2022-06-27', 430365928200, 567165473420, 120),
                                        (82, 85, '2022-06-27', '2022-07-04', 567165473420, 511981860000, 124),
                                        (85, 88, '2022-07-04', '2022-07-08', 511981860000, 567165473420, 133),
                                        (88, 106, '2022-07-08', '2022-08-08', 567165473420, 490900254000, 153),
                                        (106, 114, '2022-08-08', '2022-08-24', 490900254000, 577234450000, 166),
                                        (114, 123, '2022-08-24', '2022-09-06', 577234450000, 445604917680, 170),
                                        (123, 127, '2022-09-06', '2022-09-13', 445604917680, 461988337200, 173),
                                        (127, 134, '2022-09-13', '2022-09-22', 461988337200, 407577716000, 180),
                                        (134, 137, '2022-09-22', '2022-09-27', 407577716000, 437021692380, 184),
                                        (137, 140, '2022-09-27', '2022-10-10', 437021692380, 393345771840, 191),
                                        (140, 145, '2022-10-10', '2022-10-19', 393345771840, 444390336000, 195),
                                        (145, 152, '2022-10-19', '2022-10-31', 444390336000, 358508384640, 205),
                                        (152, 156, '2022-10-31', '2022-11-08', 358508384640, 425086502400, 212),
                                        (156, 161, '2022-11-08', '2022-11-17', 425086502400, 372011014080, 217),
                                        (161, 176, '2022-11-17', '2022-12-09', 372011014080, 428002185600, 231)),
                              'f1': ((0,
                                      2,
                                      'consolidation',
                                      None,
                                      (0,),
                                      ((526277196640, 545612041000),),
                                      3,
                                      37,
                                      '2022-03-02 15:05:00'),
                                     (3,
                                      5,
                                      'consolidation',
                                      None,
                                      (3,),
                                      ((494283349820, 545612041000),),
                                      6,
                                      52,
                                      '2022-03-23 15:05:00'),
                                     (6,
                                      9,
                                      'consolidation',
                                      'up',
                                      (7,),
                                      ((390391187680, 433678752000),),
                                      10,
                                      106,
                                      '2022-06-15 15:05:00'),
                                     (10,
                                      15,
                                      'up',
                                      'up',
                                      (10, 13),
                                      ((430365928200, 470832572860), (511981860000, 567165473420)),
                                      16,
                                      166,
                                      '2022-09-07 15:05:00'),
                                     (16,
                                      19,
                                      'consolidation',
                                      'up',
                                      (17,),
                                      ((445604917680, 461988337200),),
                                      22,
                                      195,
                                      '2022-10-26 15:05:00'),
                                     (20,
                                      22,
                                      'consolidation',
                                      None,
                                      (20,),
                                      ((407577716000, 437021692380),),
                                      23,
                                      205,
                                      '2022-11-09 15:05:00'),
                                     (23,
                                      25,
                                      'consolidation',
                                      None,
                                      (23,),
                                      ((372011014080, 425086502400),),
                                      26,
                                      231,
                                      '2022-12-15 15:05:00')),
                              'tail': {'kind': 'incomplete',
                                       'complete': False,
                                       'direction': None,
                                       'seg_start': 26,
                                       'seg_end': 26,
                                       'start_dt': '2022-11-17',
                                       'end_dt': '2022-12-09',
                                       'start_ticks': 372011014080,
                                       'end_ticks': 428002185600,
                                       'low_ticks': 372011014080,
                                       'high_ticks': 428002185600,
                                       'centers_ticks': []},
                              'f2_tail': {'kind': 'consolidation',
                                          'complete': False,
                                          'direction': None,
                                          'seg_start': 0,
                                          'seg_end': 6,
                                          'start_dt': '2022-01-10',
                                          'end_dt': '2022-11-17',
                                          'start_ticks': 526277196640,
                                          'end_ticks': 372011014080,
                                          'low_ticks': 354371758000,
                                          'high_ticks': 612350382280,
                                          'centers_ticks': [[486944943160, 537079010000]]},
                              'factors': (('2022-01-04', '1.003886'), ('2022-09-28', '1.005408'))},
           '2022-04-15-81': {'rows': 176,
                             'parts': ((1, 8, '2022-04-19', '2022-05-05', 461365927880, 354371758000, 22),
                                       (8, 14, '2022-05-05', '2022-05-20', 354371758000, 433678752000, 28),
                                       (14, 18, '2022-05-20', '2022-05-26', 433678752000, 390391187680, 35),
                                       (18, 31, '2022-05-26', '2022-06-27', 390391187680, 567165473420, 60),
                                       (31, 39, '2022-06-27', '2022-07-12', 567165473420, 501561523320, 68),
                                       (39, 46, '2022-07-12', '2022-07-22', 501561523320, 546103945140, 73),
                                       (46, 55, '2022-07-22', '2022-08-08', 546103945140, 490900254000, 87),
                                       (55, 63, '2022-08-08', '2022-08-24', 490900254000, 577234450000, 100),
                                       (63, 72, '2022-08-24', '2022-09-06', 577234450000, 445604917680, 104),
                                       (72, 76, '2022-09-06', '2022-09-13', 445604917680, 461988337200, 111),
                                       (76, 89, '2022-09-13', '2022-10-10', 461988337200, 393345771840, 125),
                                       (89, 94, '2022-10-10', '2022-10-19', 393345771840, 444390336000, 133),
                                       (94, 101, '2022-10-19', '2022-10-31', 444390336000, 358508384640, 139),
                                       (101, 105, '2022-10-31', '2022-11-08', 358508384640, 425086502400, 146),
                                       (105, 110, '2022-11-08', '2022-11-17', 425086502400, 372011014080, 151),
                                       (110, 130, '2022-11-17', '2022-12-19', 372011014080, 432425980800, 173)),
                             'f1': ((0,
                                     2,
                                     'consolidation',
                                     None,
                                     (0,),
                                     ((390391187680, 433678752000),),
                                     3,
                                     60,
                                     '2022-07-13 15:05:00'),
                                    (3,
                                     5,
                                     'consolidation',
                                     None,
                                     (3,),
                                     ((501561523320, 546103945140),),
                                     6,
                                     87,
                                     '2022-08-19 15:05:00'),
                                    (6,
                                     12,
                                     'down',
                                     'down',
                                     (6, 10),
                                     ((490900254000, 546103945140), (393345771840, 444390336000)),
                                     13,
                                     146,
                                     '2022-11-18 15:05:00')),
                             'tail': {'kind': 'consolidation',
                                      'complete': False,
                                      'direction': None,
                                      'seg_start': 13,
                                      'seg_end': 15,
                                      'start_dt': '2022-10-31',
                                      'end_dt': '2022-12-19',
                                      'start_ticks': 358508384640,
                                      'end_ticks': 432425980800,
                                      'low_ticks': 358508384640,
                                      'high_ticks': 432425980800,
                                      'centers_ticks': [[372011014080, 425086502400]]},
                             'f2_tail': {'kind': 'consolidation',
                                         'complete': False,
                                         'direction': None,
                                         'seg_start': 0,
                                         'seg_end': 2,
                                         'start_dt': '2022-04-19',
                                         'end_dt': '2022-10-31',
                                         'start_ticks': 461365927880,
                                         'end_ticks': 358508384640,
                                         'low_ticks': 354371758000,
                                         'high_ticks': 577234450000,
                                         'centers_ticks': [[390391187680, 461365927880]]},
                             'factors': (('2022-04-15', '1.003886'), ('2022-09-28', '1.005408'))},
           '2022-04-15-106': {'rows': 176,
                              'parts': ((1, 8, '2022-04-19', '2022-05-05', 461365927880, 354371758000, 22),
                                        (8, 14, '2022-05-05', '2022-05-20', 354371758000, 433678752000, 28),
                                        (14, 18, '2022-05-20', '2022-05-26', 433678752000, 390391187680, 35),
                                        (18, 22, '2022-05-26', '2022-06-07', 390391187680, 470832572860, 40),
                                        (22, 25, '2022-06-07', '2022-06-14', 470832572860, 430365928200, 49),
                                        (25, 31, '2022-06-14', '2022-06-27', 430365928200, 567165473420, 54),
                                        (31, 34, '2022-06-27', '2022-07-04', 567165473420, 511981860000, 58),
                                        (34, 37, '2022-07-04', '2022-07-08', 511981860000, 567165473420, 67),
                                        (37, 55, '2022-07-08', '2022-08-08', 567165473420, 490900254000, 87),
                                        (55, 63, '2022-08-08', '2022-08-24', 490900254000, 577234450000, 100),
                                        (63, 72, '2022-08-24', '2022-09-06', 577234450000, 445604917680, 104),
                                        (72, 76, '2022-09-06', '2022-09-13', 445604917680, 461988337200, 107),
                                        (76, 83, '2022-09-13', '2022-09-22', 461988337200, 407577716000, 114),
                                        (83, 86, '2022-09-22', '2022-09-27', 407577716000, 437021692380, 118),
                                        (86, 89, '2022-09-27', '2022-10-10', 437021692380, 393345771840, 125),
                                        (89, 94, '2022-10-10', '2022-10-19', 393345771840, 444390336000, 129),
                                        (94, 101, '2022-10-19', '2022-10-31', 444390336000, 358508384640, 139),
                                        (101, 105, '2022-10-31', '2022-11-08', 358508384640, 425086502400, 146),
                                        (105, 110, '2022-11-08', '2022-11-17', 425086502400, 372011014080, 151),
                                        (110, 125, '2022-11-17', '2022-12-09', 372011014080, 428002185600, 165)),
                              'f1': ((0,
                                      2,
                                      'consolidation',
                                      None,
                                      (0,),
                                      ((390391187680, 433678752000),),
                                      3,
                                      40,
                                      '2022-06-15 15:05:00'),
                                     (3,
                                      8,
                                      'up',
                                      'up',
                                      (3, 6),
                                      ((430365928200, 470832572860), (511981860000, 567165473420)),
                                      9,
                                      100,
                                      '2022-09-07 15:05:00'),
                                     (9,
                                      12,
                                      'consolidation',
                                      'up',
                                      (10,),
                                      ((445604917680, 461988337200),),
                                      15,
                                      129,
                                      '2022-10-26 15:05:00'),
                                     (13,
                                      15,
                                      'consolidation',
                                      None,
                                      (13,),
                                      ((407577716000, 437021692380),),
                                      16,
                                      139,
                                      '2022-11-09 15:05:00'),
                                     (16,
                                      18,
                                      'consolidation',
                                      None,
                                      (16,),
                                      ((372011014080, 425086502400),),
                                      19,
                                      165,
                                      '2022-12-15 15:05:00')),
                              'tail': {'kind': 'incomplete',
                                       'complete': False,
                                       'direction': None,
                                       'seg_start': 19,
                                       'seg_end': 19,
                                       'start_dt': '2022-11-17',
                                       'end_dt': '2022-12-09',
                                       'start_ticks': 372011014080,
                                       'end_ticks': 428002185600,
                                       'low_ticks': 372011014080,
                                       'high_ticks': 428002185600,
                                       'centers_ticks': []},
                              'f2_tail': {'kind': 'consolidation',
                                          'complete': False,
                                          'direction': None,
                                          'seg_start': 0,
                                          'seg_end': 4,
                                          'start_dt': '2022-04-19',
                                          'end_dt': '2022-11-17',
                                          'start_ticks': 461365927880,
                                          'end_ticks': 372011014080,
                                          'low_ticks': 354371758000,
                                          'high_ticks': 577234450000,
                                          'centers_ticks': [[407577716000, 461365927880]]},
                              'factors': (('2022-04-15', '1.003886'), ('2022-09-28', '1.005408'))}}}


def factor_f1_parts(case):
    """q=p*f*10^6为发现坐标，所有价格均非实际报价；只装配显式固定笔。"""
    return [SimpleNamespace(start_index=a, end_index=z, start_dt=date(start), end_dt=date(end),
                            start_value=p0/1000.0, end_value=p1/1000.0,
                            low=min(p0, p1)/1000.0, high=max(p0, p1)/1000.0,
                            direction='up' if p1 > p0 else 'down')
            for a, z, start, end, p0, p1, _ in case['parts']]


def factor_f1_records(case):
    """三段交集、组成端点、后继证明及确认时间均来自已冻结表。"""
    records = []
    for a, z, kind, direction, _, cores, proof, count, known in case['f1']:
        parts = case['parts']
        records.append(dict(seg_start=a, seg_end=z, kind=kind, direction=direction,
                            complete=True, start_dt=parts[a][2], end_dt=parts[z][3],
                            start_ticks=parts[a][4], end_ticks=parts[z][5],
                            low_ticks=min(min(r[4:6]) for r in parts[a:z+1]),
                            high_ticks=max(max(r[4:6]) for r in parts[a:z+1]),
                            centers_ticks=[list(c) for c in cores], proof_unit=proof,
                            confirmed_raw_count=count, confirmed_dt=known))
    return records


class TestFactorProductCompleteF1(unittest.TestCase):
    def test_explicit_fixed_parts_keep_complete_f1_across_factor_change(self):
        """84个显式固定笔、836个行计数快照；跨因子切换不重写已完成q坐标。"""
        total = 0
        for key, case in sorted(M3_FACTOR_F1_AUDIT['cases'].items()):
            parts = factor_f1_parts(case)
            frozen = factor_f1_records(case)
            seen = {}
            for count in range(1, case['rows']+1):
                visible = [part for part, row in zip(parts, case['parts']) if row[6] <= count]
                moves = chan.same_level_decompose(visible)
                completed = [m for m in moves if m.complete]
                expected = [m for m in frozen if m['confirmed_raw_count'] <= count]
                self.assertEqual([move_record(m) for m in completed],
                                 [expected_shape(m) for m in expected], (key, count))
                for m in completed:
                    value = move_record(m)
                    if m.seg_start in seen:
                        self.assertEqual(seen[m.seg_start][1], value)
                    else:
                        seen[m.seg_start] = (count, value)
                total += 1
            self.assertEqual({k: v[0] for k, v in seen.items()},
                             {m['seg_start']: m['confirmed_raw_count'] for m in frozen})
            self.assertEqual(move_record(moves[-1]), expected_shape(case['tail']))
        self.assertEqual(total, 836)

    def test_complete_f1_inputs_do_not_promote_unfinished_f2(self):
        """19个F1到达快照保持F2开放；后续证明/坏字段不能提前进入。"""
        def no_force(*args):
            self.fail('完整F2前提未成立，不应调用力度方法')

        count = 0
        for key, case in sorted(M3_FACTOR_F1_AUDIT['cases'].items()):
            types = confirmed_inputs(dict(completed=factor_f1_records(case)))
            for item in types:
                now = item.confirmed_dt
                visible = [u for u in types if u.confirmed_dt <= now]
                future = [u if u.confirmed_dt <= now else u._replace(
                    move_id=None, level=None, low=float('nan'), centers=None) for u in types]
                self.assertEqual(chan.confirm_level_up(visible, now, 'F2'), [], key)
                self.assertEqual(chan.confirm_level_up(future, now, 'F2'), [], key)
                scan = chan.scan_strict_divergence(visible, now, 'F2', force_fn=no_force,
                                                   force_method='factor-q:structure-not-complete')
                self.assertFalse(scan.results, key)
                self.assertEqual(chan.scan_strict_divergence(future, now, 'F2', force_fn=no_force,
                    force_method='factor-q:structure-not-complete'), scan)
                count += 1
            self.assertEqual([move_record(m) for m in chan.level_up(types)],
                             [expected_shape(case['f2_tail'])], key)
        self.assertEqual(count, 19)


if __name__ == '__main__':
    unittest.main()
