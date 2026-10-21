# -*- coding: utf-8 -*-
"""课20/35/38/62/67/78/106: 完成XD路径F1的真实独立标注。

预期由原始日线、人工包含/分型/笔和特征序列证明表独立冻结。
测试只读取标签, 不重新生成预期; 输入不继承窗口以前的结构。
固定笔为bis[:-1], complete XD才能参加F1构造。证据笔端点、
端点分型日期及实际首次可见日分别比较, 禁止把后继证明回填。

两个样本的因子恒为1, 价格单位0.001; 不填因子、不调整报价,
比较以人工整数价位表为准。时间使用北京时间的naive datetime;
15:00收盘/15:05到达是工程测试约定, 不是供应时效实测。
中枢核心移动与本工程三单元组的全包络关系分别记录; 这些工程
分组不是原文Z_n的另行角色分解, 不提供严格理论趋势正例证明。

另复用五条既有独立完成XD链, 核38个完整F1、一个完成盘整F2及开放
尾部。F2允许延伸; 后继F1的确认只作完成证据, 不并入原F2的区间。
反向中枢证明的三条XD按实际到达整批处理, 不制造批内确认时刻。
"""
from bisect import bisect_right
from datetime import datetime, timedelta
from types import SimpleNamespace
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器编译或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_xd_f1.json')
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


def unit_record(unit):
    """序列化部件真实范围和净端点; 内部极值不改写端点日期。"""
    return dict(start_index=unit.start_index, end_index=unit.end_index,
                start_ticks=round(unit.start_value * 1000),
                end_ticks=round(unit.end_value * 1000),
                start_dt=str(unit.start_dt)[:10],
                end_dt=str(unit.end_dt)[:10],
                low_ticks=round(unit.low * 1000),
                high_ticks=round(unit.high * 1000), direction=unit.direction)


def xd_identity(xd):
    """仅此固定输入版本内的观察身份, 不是跨标的全局身份。"""
    return (xd.direction, str(xd.start_dt)[:10], str(xd.end_dt)[:10], xd.mode)


def xd_record(xd, fixed_bis, confirmed_raw_count):
    """补记完成模式与证据笔; proof_bi是固定笔序列零基下标。"""
    matches = [i for i, bi in enumerate(fixed_bis)
               if bi.end_index == xd.evidence_end_index and
               bi.end_dt == xd.evidence_dt]
    if len(matches) != 1:
        raise AssertionError('完成XD须有唯一可回溯证据笔')
    record = unit_record(xd)
    record.update(mode=xd.mode, proof_bi=matches[0],
                  evidence_end_index=xd.evidence_end_index,
                  evidence_dt=str(xd.evidence_dt)[:10],
                  confirmed_raw_count=confirmed_raw_count)
    return record


def move_record(move):
    """序列化F1组成、三段中枢及实际波动范围, 不补完成时间。"""
    return dict(kind=move.kind, complete=bool(move.complete),
                direction=move.direction, seg_start=move.seg_start,
                seg_end=move.seg_end, start_dt=str(move.start_dt)[:10],
                end_dt=str(move.end_dt)[:10], low_ticks=round(move.low * 1000),
                high_ticks=round(move.high * 1000),
                centers_ticks=[[round(low * 1000), round(high * 1000)]
                               for low, high in move.centers])


def expected_shape(record):
    """只取MoveType已有结构字段, 独立标签的证明元数据另验。"""
    return dict((key, record[key]) for key in (
        'kind', 'complete', 'direction', 'seg_start', 'seg_end',
        'start_dt', 'end_dt', 'low_ticks', 'high_ticks', 'centers_ticks'))


def completed_units(bis):
    """后继笔固定前笔, 再识别XD; 不拿原始行情端点过滤代替回放。"""
    fixed = bis[:-1]
    return fixed, [xd for xd in chan.find_xds(fixed) if xd.complete]


def completed_shapes(bis):
    """公开算法只用于得到待比较实际值, 从不写入预期标签。"""
    _, xds = completed_units(bis)
    return [move_record(move) for move in chan.same_level_decompose(xds)
            if move.complete]


def move_identity(move):
    return (move.seg_start, move.seg_end, move.kind)


def confirmed_move_record(move, units, count, rows):
    """本两案例由首个回中枢后继完成XD证明, 因此proof_unit=q+1。

    该关系是本fixture覆盖的回抽分支, 不扩展为所有同级分解的
    通用证明规则。confirmed_dt取原始观察行的15:05到达约定。
    """
    record = move_record(move)
    record.update(start_ticks=round(units[move.seg_start].start_value * 1000),
                  end_ticks=round(units[move.seg_end].end_value * 1000),
                  proof_unit=move.seg_end + 1, confirmed_raw_count=count,
                  confirmed_dt=str(rows[count - 1]['dt'] +
                                   timedelta(hours=15, minutes=5)))
    return record


class TestRealXdF1(unittest.TestCase):
    def assert_fields_equal(self, actual, frozen, context):
        """标签允许说明字段; 所有实际结构和时间字段必须有独立预期。"""
        self.assertTrue(set(actual).issubset(frozen), context)
        self.assertEqual(actual, dict((key, frozen[key]) for key in actual),
                         context)

    def test_frozen_foundation_and_completed_xd_f1_tables(self):
        """课62/106/67/38: 原始包含、分型、笔与XD→F1最终完整表。"""
        for case in load_labels()['cases']:
            self.assertEqual(case['standard'], '106')
            bars = raw_bars(case)
            new_bars, fxs, bis = chan.chan_fx_bi(bars, standard='106')
            foundation = case['foundation']
            self.assertEqual(
                [dict(elements=bar.elements, low_ticks=round(bar.low * 1000),
                      high_ticks=round(bar.high * 1000)) for bar in new_bars],
                foundation['new_bars'], case['id'])
            self.assertEqual([[fx.kind, fx.bar_index, round(fx.value * 1000)]
                              for fx in fxs], foundation['fxs'], case['id'])
            self.assertEqual([[bi.direction, bi.start_index, bi.end_index,
                               round(bi.start_value * 1000),
                               round(bi.end_value * 1000)] for bi in bis],
                             foundation['bis'], case['id'])
            fixed, xds = completed_units(bis)
            path = case['paths']['xd-106']
            self.assertEqual(len(xds), len(path['units']), case['id'])
            for xd, expected in zip(xds, path['units']):
                self.assertTrue(xd.complete)
                self.assert_fields_equal(
                    xd_record(xd, fixed, expected['confirmed_raw_count']),
                    expected, case['id'])
                self.assertEqual(
                    expected['confirmed_dt'],
                    str(bars[expected['confirmed_raw_count'] - 1]['dt'] +
                        timedelta(hours=15, minutes=5)), case['id'])
            self.assertEqual(
                [move_record(move) for move in chan.same_level_decompose(xds)],
                [expected_shape(move) for move in path['moves']], case['id'])

    def test_every_raw_prefix_matches_frozen_structure_and_first_proof(self):
        """课65/67/78: 每个原始日先截断, 核固定笔/XD/F1及首确认。

        observations只压缩相同结构的连续观察, 每个原始日前缀
        仍重新计算。独立首确认日不得由端点日或证据笔端点代替。
        已完成记录后续既不能消失, 也不能更换组成、极值或证明。
        """
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            events = sorted(int(count) for count in case['observations'])
            self.assertEqual(events[0], 1, case['id'])
            xd_seen, move_seen, frozen_xds, frozen_moves = {}, {}, {}, {}
            for count in range(1, len(bars) + 1):
                event = events[bisect_right(events, count) - 1]
                expected = case['observations'][str(event)]
                _, _, bis = chan.chan_fx_bi(bars[:count], standard='106')
                fixed, xds = completed_units(bis)
                self.assertEqual([unit_record(bi) for bi in fixed],
                                 expected['fixed_bis'], (case['id'], count))
                actual_xds = []
                for xd in xds:
                    identity = xd_identity(xd)
                    xd_seen.setdefault(identity, count)
                    record = xd_record(xd, fixed, xd_seen[identity])
                    if identity in frozen_xds:
                        self.assertEqual(record, frozen_xds[identity],
                                         (case['id'], count, '完成XD修订'))
                    frozen_xds[identity] = record
                    actual_xds.append(record)
                self.assertEqual(len(actual_xds), len(expected['completed_xds']),
                                 (case['id'], count))
                for actual, frozen in zip(actual_xds, expected['completed_xds']):
                    # 压缩结构表不填写确认时间; 首次观察另用账本与
                    # 最终独立units标签比较, 不能从当前count倒填。
                    structural = dict((key, value) for key, value in actual.items()
                                      if key != 'confirmed_raw_count')
                    self.assert_fields_equal(structural, frozen,
                                             (case['id'], count))
                self.assertTrue(set(frozen_xds).issubset(
                    set(xd_identity(xd) for xd in xds)),
                    (case['id'], count, '完成XD撤销'))
                completed = [move for move in chan.same_level_decompose(xds)
                             if move.complete]
                actual_moves = []
                for move in completed:
                    identity = move_identity(move)
                    move_seen.setdefault(identity, count)
                    record = confirmed_move_record(
                        move, xds, move_seen[identity], bars)
                    if identity in frozen_moves:
                        self.assertEqual(record, frozen_moves[identity],
                                         (case['id'], count, '完成F1修订'))
                    frozen_moves[identity] = record
                    actual_moves.append(record)
                self.assertEqual(len(actual_moves), len(expected['completed_f1']),
                                 (case['id'], count))
                for actual, frozen in zip(actual_moves, expected['completed_f1']):
                    structural = dict((key, value) for key, value in actual.items()
                                      if key not in ('confirmed_raw_count',
                                                     'confirmed_dt'))
                    self.assert_fields_equal(structural, frozen,
                                             (case['id'], count))
                self.assertTrue(set(frozen_moves).issubset(
                    set(move_identity(move) for move in completed)),
                    (case['id'], count, '完成F1撤销'))
            self.assertEqual(
                xd_seen,
                dict(((unit['direction'], unit['start_dt'], unit['end_dt'],
                       unit['mode']), unit['confirmed_raw_count'])
                     for unit in case['paths']['xd-106']['units']), case['id'])
            self.assertEqual(
                move_seen,
                dict(((move['seg_start'], move['seg_end'], move['kind']),
                      move['confirmed_raw_count'])
                     for move in case['paths']['xd-106']['completed']), case['id'])
            for expected in case['paths']['xd-106']['completed']:
                identity = (expected['seg_start'], expected['seg_end'],
                            expected['kind'])
                self.assert_fields_equal(frozen_moves[identity], expected,
                                         (case['id'], '最终首确认账本'))

    def test_completed_composition_and_successor_are_distinct(self):
        """课38/78: 六组成段不含第七证明段, 尾段不包装成完成F1。"""
        kinds = set()
        for case in load_labels()['cases']:
            path = case['paths']['xd-106']
            self.assertEqual(len(path['units']), 7, case['id'])
            self.assertEqual(len(path['completed']), 1, case['id'])
            move = path['completed'][0]
            kinds.add(move['kind'])
            self.assertEqual((move['seg_start'], move['seg_end']), (0, 5))
            self.assertEqual(move['proof_unit'], 6)
            self.assertEqual(move['confirmed_raw_count'],
                             path['units'][6]['confirmed_raw_count'])
            self.assertGreater(move['confirmed_dt'][:10], move['end_dt'])
            self.assertGreater(move['confirmed_dt'][:10],
                               path['units'][6]['evidence_dt'])
            tail = path['moves'][-1]
            self.assertEqual((tail['seg_start'], tail['seg_end']), (6, 6))
            self.assertEqual(tail['kind'], 'incomplete')
            self.assertFalse(tail['complete'])
        self.assertEqual(kinds, {'up', 'down'})

    def test_core_shift_does_not_prove_strict_wave_separation(self):
        """课20边界: 两核心同向分离, 工程三单元全包络仍为expand。

        只验现行F1三单元组关系; 未另行核验原文Z_n的角色切分,
        所以既不登记严格趋势正例, 也不以此否定原文理论趋势。
        """
        directions = set()
        for case in load_labels()['cases']:
            expected = case['wave_relation']
            self.assertEqual(expected['scope'], 'engineering_three_unit_groups')
            _, _, bis = chan.chan_fx_bi(raw_bars(case), standard='106')
            _, xds = completed_units(bis)
            groups = (xds[:3], xds[3:6])
            centers = [[round(max(x.low for x in group) * 1000),
                        round(min(x.high for x in group) * 1000)]
                       for group in groups]
            waves = [[round(min(x.low for x in group) * 1000),
                      round(max(x.high for x in group) * 1000)]
                     for group in groups]
            self.assertEqual(centers, expected['centers_ticks'], case['id'])
            self.assertEqual(waves, expected['waves_ticks'], case['id'])
            direction = ('up' if centers[1][0] > centers[0][1] else
                         'down' if centers[1][1] < centers[0][0] else None)
            self.assertEqual(direction, expected['core_direction'])
            directions.add(direction)
            objects = [chan.ZS(center[0] / 1000.0, center[1] / 1000.0,
                               wave[1] / 1000.0, wave[0] / 1000.0,
                               group[0].start_dt, group[-1].end_dt,
                               group[0].direction, 3)
                       for center, wave, group in zip(centers, waves, groups)]
            self.assertEqual(chan.zs_relation(objects[0], objects[1]),
                             expected['relation'])
            self.assertEqual(expected['relation'], 'expand')
            strict = (waves[1][0] > waves[0][1] if direction == 'up' else
                      waves[1][1] < waves[0][0])
            self.assertFalse(strict, case['id'])
            self.assertFalse(expected['strict_trend_proven'], case['id'])
        self.assertEqual(directions, {'up', 'down'})

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """原始行情先截观察日; NaN、缺价格字段及未来结构均不可读。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            completed = case['paths']['xd-106']['completed'][0]
            count = completed['confirmed_raw_count']
            for stop in (count - 1, count):
                now = bars[stop - 1]['dt']
                baseline = chan.analyze_at(bars[:stop], now, bi_standard='106')
                poisoned = [dict(bar) for bar in bars]
                for bar in poisoned[stop:]:
                    bar.pop('open')
                    bar.update(high=float('nan'), low=-999, close=99999)
                future = dict(dt=bars[-1]['dt'] + timedelta(days=1),
                              high=float('inf'), low=-999, close=float('nan'),
                              volume=1)
                self.assertEqual(
                    chan.analyze_at(poisoned + [future], now,
                                    bi_standard='106').to_dict(),
                    baseline.to_dict(), (case['id'], stop))
                expected = [expected_shape(move) for move in
                            case['paths']['xd-106']['completed']
                            if move['confirmed_raw_count'] <= stop]
                self.assertEqual(completed_shapes(baseline.bis), expected,
                                 (case['id'], stop))

    def test_close_arrival_and_delayed_proof_use_actual_replay_entrypoints(self):
        """最后证明行在收盘前/到达前/晚到时等待, 实际到达后才完成。

        replay观察网格包含每个独立XD首确认时点, 因此first_seen
        可以逐条与标签比较。晚到只改元数据, 不改变价格或端点;
        最后一条XD及F1的首观察相应顺延, 既有确认记录保持不变。
        """
        for case in load_labels()['cases']:
            rows = raw_bars(case, timed=True)
            path = case['paths']['xd-106']
            completed = path['completed'][0]
            count = completed['confirmed_raw_count']
            last = rows[count - 1]
            now = last['available_dt']
            for before in (last['closed_dt'] - timedelta(microseconds=1),
                           last['closed_dt'], now - timedelta(microseconds=1)):
                baseline = chan.analyze_available(rows[:count - 1], before,
                                                  bi_standard='106')
                actual = chan.analyze_available(rows, before, bi_standard='106')
                self.assertEqual(actual.to_dict(), baseline.to_dict())
                self.assertEqual(completed_shapes(actual.bis), [])
                poison = dict(last, high=float('nan'), low=-999, close=99999)
                poison.pop('open')
                self.assertEqual(chan.analyze_available(
                    rows[:count - 1] + [poison], before,
                    bi_standard='106').to_dict(), baseline.to_dict())
            current = chan.analyze_available(rows, now, bi_standard='106')
            self.assertEqual(completed_shapes(current.bis),
                             [expected_shape(completed)])
            self.assertEqual(str(now), completed['confirmed_dt'])
            delayed = now + timedelta(days=1)
            late_rows = [dict(row) for row in rows[:count]]
            late_rows[-1]['available_dt'] = delayed
            future_day = last['dt'] + timedelta(days=2)
            late_rows.append(dict(dt=future_day,
                                  closed_dt=future_day + timedelta(hours=15),
                                  available_dt=future_day + timedelta(hours=15,
                                                                     minutes=5),
                                  high=float('inf'), low=-999, close=float('nan'),
                                  volume=1))
            proof_counts = sorted(set(unit['confirmed_raw_count']
                                      for unit in path['units']))
            observations = sorted(set(
                [rows[value - 1]['available_dt'] for value in proof_counts
                 if value < count] + [now, delayed - timedelta(microseconds=1),
                                      delayed]))
            expected_first = dict(
                ((unit['direction'], unit['start_dt'], unit['end_dt'],
                  unit['mode']),
                 delayed if unit['confirmed_raw_count'] == count else
                 rows[unit['confirmed_raw_count'] - 1]['available_dt'])
                for unit in path['units'])
            seen = {}
            for snapshot in chan.replay_available(
                    late_rows, observations, bi_standard='106'):
                moves = completed_shapes(snapshot.result.bis)
                self.assertEqual(moves, [expected_shape(completed)]
                                 if snapshot.observed_dt >= delayed else [])
                for structure in snapshot.structures:
                    if structure.kind != 'xd':
                        continue
                    record = structure.record
                    identity = (record['direction'], record['start'][0][:10],
                                record['end'][0][:10], record['mode'])
                    self.assertEqual(structure.first_seen,
                                     expected_first[identity],
                                     (case['id'], identity))
                    seen[identity] = structure.first_seen
            self.assertEqual(seen, expected_first, case['id'])


# 五条既有独立完成XD链的原起点/末端, 106标准, 不按结果裁剪。
# spec=(起/末部件,kind,进入方向,首三段起点,核心ticks,后继证明部件)。
# 包含原先已核的前缀, 不将38个F1全部计作新增独立行情。
M3_XD_RECURSION_AUDIT = {'X1': {'fixture': 'real_second_point.json',
        'f1': ((0, 2, 'consolidation', None, (0,), ((1687, 1744),), 3),
               (3, 5, 'consolidation', None, (3,), ((1687, 1702),), 6),
               (6, 9, 'consolidation', 'down', (7,), ((2080, 2256),), 10),
               (10, 12, 'consolidation', None, (10,), ((2079, 2320),), 13)),
        'tail': (13, 13, 'incomplete', None, (), (), None),
        'f2': ((0, 3, 'consolidation', None, (0,), ((1584, 1860),), None),),
        'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
        'parent_id': '159915-60m-20240101-20250331',
        'f2_spans': (((0, 2, 2),),)},
 'Y1': {'fixture': 'real_second_point.json',
        'f1': ((0, 2, 'consolidation', None, (0,), ((9780, 9834),), 3),
               (3, 8, 'down', 'down', (3, 6), ((9761, 9797), (9332, 9414)), 9),
               (9, 11, 'consolidation', None, (9,), ((9268, 9414),), 12),
               (12, 15, 'consolidation', 'up', (13,), ((8937, 9046),), 16),
               (16, 18, 'consolidation', None, (16,), ((8910, 8986),), 19),
               (19, 24, 'down', 'down', (19, 22), ((8655, 8731), (8282, 8329)), 25),
               (25, 27, 'consolidation', None, (25,), ((8253, 8389),), 28),
               (28, 30, 'consolidation', None, (28,), ((8551, 8605),), 31),
               (31, 36, 'down', 'down', (31, 34), ((8446, 8587), (8347, 8395)), 37)),
        'tail': (37, 38, 'incomplete', None, (), (), None),
        'f2': ((0, 8, 'down', 'down', (1, 4), ((9266, 9311), (8418, 8479)), None),),
        'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
        'parent_id': '518880-5m-20260501-20260724',
        'f2_spans': (((1, 3, 3), (4, 6, 8)),)},
 'S3': {'fixture': 'real_strict_trend.json',
        'f1': ((0, 2, 'consolidation', None, (0,), ((3579, 3865),), 3),
               (3, 5, 'consolidation', None, (3,), ((3579, 3730),), 6),
               (6, 9, 'consolidation', 'down', (7,), ((3834, 3942),), 10),
               (10, 13, 'consolidation', 'down', (11,), ((4488, 4642),), 14)),
        'tail': (14, 17, 'consolidation', 'down', (15,), ((5231, 5586),), None),
        'f2': ((0, 3, 'consolidation', None, (0,), ((3550, 3745),), None),),
        'source_sha256': 'ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        'parent_id': '518880-day-20210101-20260731',
        'f2_spans': (((0, 2, 3),),)},
 'M1': {'fixture': 'real_third_point_xd_margin0.json',
        'f1': ((0, 2, 'consolidation', None, (0,), ((1048, 1107),), 3),
               (3, 6, 'consolidation', 'up', (4,), ((991, 1022),), 7),
               (7, 9, 'consolidation', None, (7,), ((906, 944),), 10),
               (10, 15, 'down', 'down', (10, 13), ((879, 944), (753, 821)), 16),
               (16, 18, 'consolidation', None, (16,), ((753, 804),), 19),
               (19, 21, 'consolidation', None, (19,), ((733, 784),), 22),
               (22, 25, 'consolidation', 'down', (23,), ((915, 1118),), 26),
               (26, 28, 'consolidation', None, (26,), ((991, 1118),), 29),
               (29, 31, 'consolidation', None, (29,), ((1016, 1099),), 32),
               (32, 34, 'consolidation', None, (32,), ((1001, 1048),), 35)),
        'tail': (35, 36, 'incomplete', None, (), (), None),
        'f2': ((0, 5, 'consolidation', None, (1,), ((906, 956),), 6),
               (6, 9, 'consolidation', None, (6,), ((991, 1117),), None)),
        'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        'parent_id': '588000-30m-20230501-20250228',
        'f2_spans': (((1, 3, 3),), ((6, 8, 9),))},
 'M2': {'fixture': 'real_third_point_xd_margin0.json',
        'f1': ((0, 5, 'down', 'down', (0, 3), ((1183, 1200), (1113, 1135)), 6),
               (6, 8, 'consolidation', None, (6,), ((1031, 1060),), 9),
               (9, 11, 'consolidation', None, (9,), ((1025, 1049),), 12),
               (12, 15, 'consolidation', 'down', (13,), ((1067, 1084),), 16),
               (16, 18, 'consolidation', None, (16,), ((1070, 1079),), 19),
               (19, 21, 'consolidation', None, (19,), ((1065, 1082),), 22),
               (22, 24, 'consolidation', None, (22,), ((1073, 1100),), 25),
               (25, 27, 'consolidation', None, (25,), ((1039, 1048),), 28),
               (28, 31, 'consolidation', 'down', (29,), ((1045, 1085),), 34),
               (32, 34, 'consolidation', None, (32,), ((1111, 1137),), 35),
               (35, 37, 'consolidation', None, (35,), ((1139, 1177),), 38)),
        'tail': (38, 40, 'consolidation', None, (38,), ((1094, 1139),), None),
        'f2': ((0, 10, 'consolidation', 'down', (1,), ((1029, 1056),), None),),
        'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        'parent_id': '512880-5m-20260201-20260724',
        'f2_spans': (((1, 3, 8),),)}}


def date(value):
    return datetime.strptime(value, '%Y-%m-%d' if len(value)==10 else '%Y-%m-%d %H:%M:%S')


def m3_xd_case(audit):
    path = os.path.join(os.path.dirname(__file__), 'fixtures', audit['fixture'])
    with open(path, encoding='utf-8') as stream:
        return next(c for c in json.load(stream)['cases'] if c['id'] == audit['parent_id'])


def m3_xd_shape(move):
    return (move.seg_start, move.seg_end, move.kind, move.direction, move.complete,
            date(str(move.start_dt)), date(str(move.end_dt)), round(move.low*1000),
            round(move.high*1000), tuple((round(a*1000), round(b*1000)) for a, b in move.centers))


def m3_xd_expected(parts, spec):
    a, z, kind, entry, _, cores, proof = spec
    return (a, z, kind, entry, proof is not None, date(parts[a]['start_dt']),
            date(parts[z]['end_dt']), min(u['low_ticks'] for u in parts[a:z+1]),
            max(u['high_ticks'] for u in parts[a:z+1]), tuple(cores))


def m3_xd_parts(case, count):
    return [SimpleNamespace(direction=u['direction'], start_dt=date(u['start_dt']),
            end_dt=date(u['end_dt']), low=u['low_ticks']/1000., high=u['high_ticks']/1000.)
            for u in case['units'] if u['confirmed_raw_count'] <= count]


def m3_xd_type(key, move, parts, now):
    """仅将实际已完成F1快照转换, 证据身份保留实际到达整批。"""
    a, z = move.seg_start, move.seg_end
    return chan.ConfirmedMoveType(
        key+':f1:'+str(a), 'F1', move.kind, move.direction, move.start_dt, move.end_dt,
        parts[a]['start_ticks']/1000., parts[z]['end_ticks']/1000., move.low, move.high,
        now, tuple(key+':xd:'+str(i) for i in range(a,z+1)),
        tuple(key+':xd:'+str(i) for i in range(len(parts))), tuple(move.centers))


def m3_xd_rows(case):
    rows = []
    for r in case['raw_rows']:
        dt = date(r['dt'])
        close = dt+timedelta(hours=15) if len(r['dt'])==10 else dt
        rows.append(dict(dt=dt, open=r['open'], high=r['high'], low=r['low'],
                         close=r['close'], volume=r['vol'], closed_dt=close,
                         available_dt=close+timedelta(minutes=5 if len(r['dt'])==10 else 1)))
    return rows


class TestRealM3XdRecursion(unittest.TestCase):
    """独立完成XD→最低完整F1→允许延伸的F2; 级别及供应时效为声明输入。"""

    def test_raw_confirmation_boundaries_match_all_complete_f1_and_tails(self):
        """每个F1首证明的前/当根重算原始基础链; 不用最终端点过滤。"""
        for key, audit in sorted(M3_XD_RECURSION_AUDIT.items()):
            case = m3_xd_case(audit)
            self.assertTrue(all(r['adj_factor']==1 for r in case['raw_rows']))
            rows = m3_xd_rows(case)
            counts = {len(rows)}
            for spec in audit['f1']:
                count = case['units'][spec[-1]]['confirmed_raw_count']
                counts.update((count-1,count))
            for count in sorted(counts):
                _, _, bis = chan.chan_fx_bi(rows[:count], standard='106')
                _, xds = completed_units(bis)
                expected_xds = [u for u in case['units'] if u['confirmed_raw_count']<=count]
                self.assertEqual(
                    [(x.direction, x.start_dt, x.end_dt, round(x.start_value*1000),
                      round(x.end_value*1000), round(x.low*1000), round(x.high*1000), x.mode)
                     for x in xds],
                    [(u['direction'],date(u['start_dt']),date(u['end_dt']),u['start_ticks'],
                      u['end_ticks'],u['low_ticks'],u['high_ticks'],u['mode']) for u in expected_xds],
                    (key,count))
                actual = chan.same_level_decompose(xds)
                specs = [s for s in audit['f1'] if case['units'][s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual([m3_xd_shape(m) for m in actual if m.complete],
                                 [m3_xd_expected(case['units'],s) for s in specs], (key,count))
                if count==len(rows):
                    self.assertEqual([m3_xd_shape(m) for m in actual],
                                     [m3_xd_expected(case['units'],s) for s in audit['f1']+(audit['tail'],)])

    def test_recursive_confirmation_uses_visible_xd_batches_and_external_proof(self):
        """15202个冻结XD观察格, 实际分解并冻结首见F1后才递归; 非逐原始全链重算。"""
        totals, finished = [], []
        for key, audit in sorted(M3_XD_RECURSION_AUDIT.items()):
            case = m3_xd_case(audit)
            types, first_seen, last_size = [], {}, -1
            rows = m3_xd_rows(case)
            for count, row in enumerate(rows,1):
                parts = m3_xd_parts(case,count)
                if len(parts)!=last_size:
                    current = [m for m in chan.same_level_decompose(parts) if m.complete]
                    self.assertEqual([m3_xd_shape(m) for m in current],
                                     [m3_xd_expected(case['units'],s) for s in audit['f1']
                                      if case['units'][s[-1]]['confirmed_raw_count']<=count])
                    for move in current:
                        if move.seg_start not in first_seen:
                            first_seen[move.seg_start] = count
                            types.append(m3_xd_type(key,move,case['units'][:len(parts)],row['available_dt']))
                    self.assertEqual(len(current),len(types))
                    last_size = len(parts)
                f2 = chan.confirm_level_up(types,row['available_dt'],'F2')
                expected = [s for s in audit['f2'] if s[-1] is not None and
                            case['units'][audit['f1'][s[-1]][-1]]['confirmed_raw_count']<=count]
                records = [dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),
                                low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
                for actual, spec in zip(f2,expected):
                    self.assertEqual((actual.start_dt,actual.end_dt,actual.kind,actual.direction,
                                      round(actual.low*1000),round(actual.high*1000),
                                      tuple((round(a*1000),round(b*1000)) for a,b in actual.centers)),
                                     m3_xd_expected(records,spec)[5:7]+(spec[2],spec[3])+
                                     m3_xd_expected(records,spec)[7:])
                self.assertEqual(len(f2),len(expected),(key,count))
            self.assertEqual(first_seen,{s[0]:case['units'][s[-1]]['confirmed_raw_count'] for s in audit['f1']})
            records = [dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),
                            high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],
                             [m3_xd_expected(records,s) for s in audit['f2']])
            totals.append(len(types))
            if f2:
                actual, = f2
                finished.append(key)
                self.assertEqual(str(actual.confirmed_dt),'2024-11-11 10:01:00')
                self.assertEqual(str(actual.end_dt),'2024-08-09 10:00:00')
                self.assertEqual((round(actual.start_price*1000),round(actual.end_price*1000)),(1107,754))
                self.assertEqual((round(actual.low*1000),round(actual.high*1000)),(666,1113))
                self.assertEqual((len(actual.unit_ids),len(actual.evidence_ids)),(6,7))
                self.assertNotIn(types[6].move_id,actual.unit_ids)
                self.assertIn(types[6].move_id,actual.evidence_ids)
                self.assertEqual(round(types[6].high*1000),1202)
        self.assertEqual(totals,[10,11,4,4,9])
        self.assertEqual(finished,['M1'])

    def test_return_and_opposite_center_proof_wait_for_arrival_and_delay(self):
        """M1后继F1回入才完成F2; M2反向中枢三条XD整批可见才完成F1。"""
        for key,index in (('M1',6),('M2',8)):
            audit = M3_XD_RECURSION_AUDIT[key]
            case = m3_xd_case(audit)
            spec = audit['f1'][index]
            count = case['units'][spec[-1]]['confirmed_raw_count']
            rows = m3_xd_rows(case)
            last = rows[count-1]
            now, late = last['available_dt'], last['available_dt']+timedelta(days=1)
            target = m3_xd_expected(case['units'],spec)
            if key=='M2':
                self.assertEqual(spec[-1],spec[1]+3)
                self.assertEqual([u['confirmed_raw_count'] for u in case['units'][32:35]],[4727]*3)
                self.assertEqual((max(u['low_ticks'] for u in case['units'][32:35]),
                                  min(u['high_ticks'] for u in case['units'][32:35])),(1111,1137))
            poisoned = [dict(r) for r in rows]
            for r in poisoned[count-1:]:
                r.pop('open')
                r.update(high=float('nan'),low=-999,close=99999)
            for before in (last['closed_dt']-timedelta(microseconds=1),last['closed_dt'],
                           now-timedelta(microseconds=1)):
                baseline = chan.analyze_available(rows[:count-1],before,bi_standard='106')
                self.assertEqual(chan.analyze_available(poisoned,before,bi_standard='106').to_dict(),
                                 baseline.to_dict())
                _, xds = completed_units(baseline.bis)
                self.assertNotIn(target,[m3_xd_shape(m) for m in chan.same_level_decompose(xds) if m.complete])
            delayed = [dict(r) for r in rows[:count]]
            delayed[-1]['available_dt'] = late
            for observed,ready in ((now,False),(late-timedelta(microseconds=1),False),(late,True)):
                result = chan.analyze_available(delayed,observed,bi_standard='106')
                _, xds = completed_units(result.bis)
                moves = [m for m in chan.same_level_decompose(xds) if m.complete]
                self.assertEqual(target in [m3_xd_shape(m) for m in moves],ready)
                if key=='M1':
                    types = []
                    for i,move in enumerate(moves):
                        proof = case['units'][audit['f1'][i][-1]]
                        proof_batch = [u for u in case['units']
                                       if u['confirmed_raw_count']<=proof['confirmed_raw_count']]
                        types.append(m3_xd_type(key,move,proof_batch,
                                     late if i==index else date(proof['confirmed_dt'])))
                    f2 = chan.confirm_level_up(types,observed,'F2')
                    self.assertEqual(len(f2),int(ready))
                    future = types[-1]._replace(move_id='future',start_price=float('nan'),
                                               confirmed_dt=late+timedelta(days=2))
                    self.assertEqual(chan.confirm_level_up(types+[future],observed,'F2'),f2)
                    if ready:
                        self.assertEqual(f2[0].confirmed_dt,late)
                        self.assertEqual(round(f2[0].high*1000),1113)


# 同一五条XD→F1链的全部七个递归核心, 不筛选有点位的中枢。
# (首/第三F1,核心ticks,可知原始行,延伸(末F1,行),点或None,待回试F1或None,失败对)。
# 点=(kind,离开/回试F1,端点日期,ticks,确认原始行,全段守沿余量ticks)。
M3_XD_THIRD_AUDIT = {'M1': ((1,
         3,
         (906, 956),
         2360,
         (),
         ('buy3', 6, 7, '2024-11-25 14:30:00', 991, 3572, 29),
         None,
         ()),
        (6, 8, (991, 1117), 3822, ((9, 3913),), None, None, ())),
 'M2': ((1,
         3,
         (1029, 1056),
         2365,
         ((4, 2759), (5, 2994), (6, 3480), (7, 4016), (8, 4727)),
         ('buy3', 8, 9, '2026-06-30 11:00:00', 1113, 4774, 44),
         None,
         ((5, 6, 3480, -17),)),),
 'S3': ((0, 2, (3550, 3745), 491, ((3, 776),), None, None, ()),),
 'X1': ((0, 2, (1584, 1860), 1138, (), None, None, ()),),
 'Y1': ((1, 3, (9266, 9311), 1456, (), None, None, ()),
        (4, 6, (8418, 8479), 2113, ((7, 2279), (8, 2580)), None, 8, ()))}


def m3_xd_type_batches(key,case,extra_counts=()):
    """冻结XD到达批→实际完整F1首见快照; 原始基础链由既有证明前后测试核对。"""
    counts = {u['confirmed_raw_count'] for u in case['units']}
    counts.update(extra_counts)
    counts.add(len(case['raw_rows']))
    rows,seen = m3_xd_rows(case),{}
    for count in sorted(counts):
        parts = m3_xd_parts(case,count)
        for move in chan.same_level_decompose(parts):
            if move.complete and move.seg_start not in seen:
                seen[move.seg_start] = m3_xd_type(key,move,case['units'][:len(parts)],rows[count-1]['available_dt'])
        yield count,tuple(seen[a] for a in sorted(seen))


def m3_xd_lineage_third(types,now):
    """形成事件的v0快照接三类上下文; 延伸快照不重置形成时刻。"""
    lineage = chan.track_center_lineage(types,now,'F2')
    contexts = []
    for event in lineage.events:
        if event.kind!='formed':
            continue
        snapshot = lineage.snapshot(event.center_id,event.version)
        center = chan.ConfirmedCenter(snapshot.center_id,'F2',snapshot.zd,snapshot.zg,snapshot.confirmed_dt)
        contexts.append(chan.ThirdPointContext('xd-third:'+snapshot.center_id,'F2','F1',center))
    moves = [t.to_confirmed_move() for t in types if t.confirmed_dt<=now]
    return lineage,contexts,chan.find_third_points(moves,contexts,now)


class TestRealM3XdLineageThird(unittest.TestCase):
    """真实XD→完整F1→形成/延伸谱系→三类条件, 不授予上游一类或底顶证明。"""

    def test_all_formed_versions_and_third_points_at_visible_xd_batches(self):
        """七个形成/九个延伸及全部空/待回试结果保留; 历史快照和点位不回写。"""
        totals = [0,0,0]
        for key,audit in sorted(M3_XD_RECURSION_AUDIT.items()):
            case,records = m3_xd_case(audit),M3_XD_THIRD_AUDIT[key]
            rows = m3_xd_rows(case)
            extra = [r[3]-1 for r in records]
            extra += [r[5][5]-1 for r in records if r[5] is not None]
            extra += [f[2]-1 for r in records for f in r[7]]
            history,versions,points_seen = (),{},{}
            for count,types in m3_xd_type_batches(key,case,extra):
                now = rows[count-1]['available_dt']
                lineage,contexts,points = m3_xd_lineage_third(types,now)
                self.assertEqual(lineage.events[:len(history)],history)
                for identity,snapshot in versions.items():
                    self.assertEqual(lineage.snapshot(*identity),snapshot)
                history = lineage.events
                versions = {(c.center_id,c.version):c for c in lineage.centers}
                expected = [r for r in records if r[3]<=count]
                self.assertEqual(len(contexts),len(expected),(key,count))
                expected_versions = 0
                expected_points = []
                for context,record in zip(contexts,expected):
                    a,formed,core,known,extended,point,_,_ = record
                    self.assertEqual((round(context.center.zd*1000),round(context.center.zg*1000)),core)
                    self.assertEqual(context.center.confirmed_dt,rows[known-1]['available_dt'])
                    snapshots = [(0,formed,known)]+[(i,z,n) for i,(z,n) in enumerate(extended,1) if n<=count]
                    for version,z,first in snapshots:
                        snap = lineage.snapshot(context.center.center_id,version)
                        self.assertEqual(snap.unit_ids,tuple(t.move_id for t in types[a:z+1]))
                        self.assertEqual(snap.confirmed_dt,rows[first-1]['available_dt'])
                        self.assertEqual((round(snap.zd*1000),round(snap.zg*1000)),core)
                    expected_versions += len(snapshots)
                    if point is not None and point[5]<=count:
                        kind,leave,pull,dt,price,confirmed,_ = point
                        expected_points.append((kind,context.context_id,context.center.center_id,
                            types[leave].move_id,types[pull].move_id,dt,price,rows[confirmed-1]['available_dt']))
                self.assertEqual(len(lineage.centers),expected_versions)
                self.assertEqual([(p.kind,p.context_id,p.center_id,p.leave_move_id,p.pull_move_id,
                                   str(p.dt),round(p.price*1000),p.confirmed_dt) for p in points],expected_points)
                current = {(p.center_id,p.leave_move_id,p.pull_move_id):p for p in points}
                for identity,point in points_seen.items():
                    self.assertEqual(current[identity],point)
                points_seen = current
            totals[0] += len(contexts)
            totals[1] += len(lineage.events)-len(contexts)
            totals[2] += len(points)
        self.assertEqual(totals,[7,9,2])

    def _raw_types(self,key,case,full_types,rows,now,late_start=None,late=None):
        """在专项原始前缀重算F1; 只沿用此前实际首见的身份与证据。"""
        result = chan.analyze_available(rows,now,bi_standard='106')
        _,xds = completed_units(result.bis)
        by_id = {t.move_id:t for t in full_types}
        types = []
        for move in chan.same_level_decompose(xds):
            if not move.complete:
                continue
            prior = by_id[key+':f1:'+str(move.seg_start)]
            self.assertEqual((move.kind,move.direction,move.start_dt,move.end_dt,move.low,move.high,tuple(move.centers)),
                             (prior.kind,prior.direction,prior.start_dt,prior.end_dt,prior.low,prior.high,prior.centers))
            types.append(prior._replace(confirmed_dt=late) if move.seg_start==late_start else prior)
        return types

    def test_failed_first_return_requires_a_new_departure_from_the_same_center(self):
        """M2[5,6]破沿后保留失败; 回到中枢的新离开[8,9]才可成立, 形成身份不变。"""
        key = 'M2'
        audit = M3_XD_RECURSION_AUDIT[key]
        case = m3_xd_case(audit)
        rows = m3_xd_rows(case)
        full_types = list(m3_xd_type_batches(key,case))[-1][1]
        ids = []
        for count,ready in ((3480,False),(4773,False),(4774,True)):
            types = self._raw_types(key,case,full_types,rows,rows[count-1]['available_dt'])
            lineage,contexts,points = m3_xd_lineage_third(types,rows[count-1]['available_dt'])
            context, = contexts
            ids.append(context.center.center_id)
            self.assertEqual(context.center.confirmed_dt,rows[2364]['available_dt'])
            self.assertEqual(len(points),int(ready))
            if ready:
                point, = points
                self.assertEqual((point.leave_move_id,point.pull_move_id),
                                 (types[8].move_id,types[9].move_id))
                self.assertNotEqual(point.leave_move_id,types[5].move_id)
                self.assertEqual(round(types[6].low*1000)-1056,-17)
                self.assertTrue(1029<=round(types[6].end_price*1000)<=1056)
                self.assertTrue(1029<=round(types[8].start_price*1000)<=1056)
                self.assertEqual(round(types[9].low*1000)-1056,44)
                self.assertEqual(max(c.version for c in lineage.centers),5)
        self.assertEqual(len(set(ids)),1)

    def test_real_return_completion_proof_waits_for_arrival_and_delay(self):
        """两处三买原始证明行情的到达/晚到与未来隔离; 不把回试端点当确认。"""
        for key in ('M1','M2'):
            audit = M3_XD_RECURSION_AUDIT[key]
            case = m3_xd_case(audit)
            rows = m3_xd_rows(case)
            full_types = list(m3_xd_type_batches(key,case))[-1][1]
            point = M3_XD_THIRD_AUDIT[key][0][5]
            _,_,pull,endpoint,_,count,_ = point
            last = rows[count-1]
            now,late = last['available_dt'],last['available_dt']+timedelta(days=1)
            poisoned = [dict(r) for r in rows]
            for r in poisoned[count-1:]:
                r.pop('open')
                r.update(high=float('nan'),low=-999,close=99999)
            for before in (last['closed_dt']-timedelta(microseconds=1),last['closed_dt'],
                           now-timedelta(microseconds=1)):
                self.assertEqual(chan.analyze_available(poisoned,before,bi_standard='106').to_dict(),
                                 chan.analyze_available(rows[:count-1],before,bi_standard='106').to_dict())
                types = self._raw_types(key,case,full_types,rows,before)
                self.assertEqual(m3_xd_lineage_third(types,before)[2],[])
            delayed = [dict(r) for r in rows[:count]]
            delayed[-1]['available_dt'] = late
            for observed,ready in ((now,False),(late-timedelta(microseconds=1),False),(late,True)):
                types = self._raw_types(key,case,full_types,delayed,observed,
                                       audit['f1'][pull][0],late)
                lineage,contexts,points = m3_xd_lineage_third(types,observed)
                self.assertEqual(len(points),int(ready))
                future = full_types[-1]._replace(move_id='future',start_price=float('nan'),
                                                confirmed_dt=late+timedelta(days=2))
                poisoned_result = m3_xd_lineage_third(types+[future],observed)
                self.assertEqual(poisoned_result,(lineage,contexts,points))
                if ready:
                    self.assertEqual(points[0].confirmed_dt,late)
                    self.assertEqual(str(points[0].dt),endpoint)
                    self.assertLess(points[0].dt,points[0].confirmed_dt)


if __name__ == '__main__':
    unittest.main()
