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

跨调整追加表复用既定宁德两窗的固定笔, 核给定XD分界的原邻笔几何
条件与其F1组成。标准旧侧及特殊逆时间前提另由资产补充审计；首段
种子上下文和全局分段唯一性尚未独立裁定, 不增加独立理论标签。
"""
from bisect import bisect_right
from datetime import datetime, timedelta
from types import SimpleNamespace
import ast
import hashlib
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


# 独立修订XD作为显式部件，仅验证其后的F1/F2公开组合；不验证raw→XD已修复。
# 单位=(方向,起/止时间,起/止价,低/高,mode,原proof,局部raw,顺序发布raw)。
# 原始fixture保留，X1前七段为声明基底；两组均不提供严格趋势/点位新标签。
M3_GAP_REVISION_AUDIT = {'G': {'fixture': 'real_xd_f1.json',
       'fixture_sha256': '3defd45833e0dd5339ffb43e6d3aad7cdf3617887961acedfee03df8204fec0f',
       'id': '512880-day-20181008-20191108',
       'base': 0,
       'events': ((0, 2, 1, 5),
                  (3, 5, 1, 8),
                  (6, 8, 2, 20),
                  (9, 17, 1, 20),
                  (18, 20, 2, 26),
                  (21, 23, 1, 26),
                  (24, 26, 1, 29)),
       'units': (('up', '2018-10-19', '2018-11-19', 613, 842, 613, 842, 1, 5, 65, 65),
                 ('down', '2018-11-19', '2018-12-26', 842, 695, 695, 842, 1, 8, 109, 109),
                 ('up', '2018-12-26', '2019-03-07', 695, 1185, 695, 1185, 2, 20, 179, 179),
                 ('down', '2019-03-07', '2019-05-24', 1185, 887, 887, 1185, 1, 20, 179, 179),
                 ('up', '2019-05-24', '2019-06-24', 887, 1017, 887, 1017, 2, 26, 239, 239),
                 ('down', '2019-06-24', '2019-08-07', 1017, 871, 871, 1017, 1, 26, 239, 239),
                 ('up', '2019-08-07', '2019-09-16', 871, 1039, 871, 1039, 1, 29, 267, 267)),
       'f1': ((0, 5, 'up', 'up', (0, 3), ((695, 842), (887, 1017)), 6),),
       'tail': (6, 6, 'incomplete', None, (), (), None),
       'f2': ((0, 0, 'incomplete', None, (), (), None),),
       'f1_first_counts': (267,),
       'complete_f2': 0},
 'X1': {'fixture': 'real_first_point.json',
        'fixture_sha256': '2c70070c2917c343cdfc182518996bb71bc8c0e6724c3482c22337fc9f337ad7',
        'id': '159915-60m-20240101-20250331',
        'base': 7,
        'events': ((1, 5, 1, 8),
                   (6, 16, 1, 19),
                   (17, 21, 1, 26),
                   (22, 26, 1, 29),
                   (27, 45, 1, 48),
                   (46, 48, 1, 51),
                   (49, 55, 1, 64),
                   (56, 66, 2, 84),
                   (67, 69, 1, 74),
                   (70, 78, 1, 81),
                   (79, 81, 1, 84),
                   (82, 84, 1, 87),
                   (85, 93, 1, 96),
                   (94, 104, 1, 107)),
        'units': (('down',
                   '2024-01-11 15:00:00',
                   '2024-02-05 11:30:00',
                   1744,
                   1444,
                   1444,
                   1744,
                   1,
                   8,
                   165,
                   165),
                  ('up',
                   '2024-02-05 11:30:00',
                   '2024-03-19 09:30:00',
                   1444,
                   1875,
                   1444,
                   1875,
                   1,
                   19,
                   340,
                   340),
                  ('down',
                   '2024-03-19 09:30:00',
                   '2024-04-22 10:30:00',
                   1875,
                   1687,
                   1687,
                   1875,
                   1,
                   26,
                   414,
                   414),
                  ('up',
                   '2024-04-22 10:30:00',
                   '2024-05-09 14:00:00',
                   1687,
                   1860,
                   1687,
                   1860,
                   1,
                   29,
                   443,
                   443),
                  ('down',
                   '2024-05-09 14:00:00',
                   '2024-07-09 11:30:00',
                   1860,
                   1584,
                   1584,
                   1860,
                   1,
                   48,
                   678,
                   678),
                  ('up',
                   '2024-07-09 11:30:00',
                   '2024-07-22 10:30:00',
                   1584,
                   1702,
                   1584,
                   1702,
                   1,
                   51,
                   725,
                   725),
                  ('down',
                   '2024-07-22 10:30:00',
                   '2024-08-29 10:30:00',
                   1702,
                   1484,
                   1484,
                   1702,
                   1,
                   64,
                   893,
                   893),
                  ('up',
                   '2024-08-29 10:30:00',
                   '2024-10-08 10:30:00',
                   1484,
                   2678,
                   1484,
                   2678,
                   2,
                   84,
                   1138,
                   1138),
                  ('down',
                   '2024-10-08 10:30:00',
                   '2024-10-16 15:00:00',
                   2678,
                   1989,
                   1989,
                   2678,
                   1,
                   74,
                   1018,
                   1138),
                  ('up',
                   '2024-10-16 15:00:00',
                   '2024-11-12 10:30:00',
                   1989,
                   2402,
                   1989,
                   2402,
                   1,
                   81,
                   1100,
                   1138),
                  ('down',
                   '2024-11-12 10:30:00',
                   '2024-11-27 10:30:00',
                   2402,
                   2079,
                   2079,
                   2402,
                   1,
                   84,
                   1138,
                   1138),
                  ('up',
                   '2024-11-27 10:30:00',
                   '2024-12-10 09:30:00',
                   2079,
                   2320,
                   2079,
                   2320,
                   1,
                   87,
                   1165,
                   1165),
                  ('down',
                   '2024-12-10 09:30:00',
                   '2025-01-13 09:30:00',
                   2320,
                   1916,
                   1916,
                   2320,
                   1,
                   96,
                   1285,
                   1285),
                  ('up',
                   '2025-01-13 09:30:00',
                   '2025-02-24 09:30:00',
                   1916,
                   2242,
                   1916,
                   2242,
                   1,
                   107,
                   1403,
                   1403)),
        'f1': ((0, 2, 'consolidation', None, (0,), ((1687, 1744),), 3),
               (3, 5, 'consolidation', None, (3,), ((1687, 1702),), 6),
               (6, 9, 'consolidation', 'down', (7,), ((1989, 2402),), 10),
               (10, 12, 'consolidation', None, (10,), ((2079, 2320),), 13)),
        'tail': (13, 13, 'incomplete', None, (), (), None),
        'f2': ((0, 3, 'consolidation', None, (0,), ((1584, 1860),), None),),
        'f1_first_counts': (443, 893, 1138, 1403),
        'complete_f2': 0}}


def gap_revision_input(audit):
    """显式修订部件和原始源行；不调用笔/线段识别器或修改旧fixture。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures', audit['fixture'])
    with open(path, 'rb') as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != audit['fixture_sha256']:
        raise AssertionError('修订部件的原始fixture摘要漂移')
    case = next(c for c in json.loads(payload.decode('utf-8'))['cases'] if c['id'] == audit['id'])
    names = ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks',
             'mode','proof_bi','local_raw_count','confirmed_raw_count')
    return case, [dict(zip(names, row)) for row in audit['units']]


def gap_revision_time(case, count):
    """沿既有日线15:05/分钟标签+1分钟测试约定，不证明供应实际到达。"""
    value = case['raw_rows'][count-1]['dt']
    return (date(value[:10])+timedelta(hours=15,minutes=5) if '-day-' in case['id']
            else date(value)+timedelta(minutes=1))


class TestConditionalGapRevisionRecursion(unittest.TestCase):
    """修订XD作为给定部件验收公开下游；raw→XD仍待算法和全组联合验收。"""

    def test_given_revision_batches_confirm_f1_without_rewriting_local_proofs(self):
        for key, audit in sorted(M3_GAP_REVISION_AUDIT.items()):
            case, units = gap_revision_input(audit)
            counts = {0,len(case['raw_rows'])}
            for row in units:
                counts.update((row['confirmed_raw_count']-1,row['confirmed_raw_count']))
                counts.update((row['local_raw_count']-1,row['local_raw_count']))
            first = {}
            for count in sorted(counts):
                parts = m3_xd_parts(dict(units=units),count)
                actual = chan.same_level_decompose(parts)
                expected = [s for s in audit['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                complete = [m for m in actual if m.complete]
                self.assertEqual([m3_xd_shape(m) for m in complete],
                                 [m3_xd_expected(units,s) for s in expected],(key,count))
                for move in complete:
                    first.setdefault(move.seg_start,count)
                if count == len(case['raw_rows']):
                    self.assertEqual([m3_xd_shape(m) for m in actual],
                                     [m3_xd_expected(units,s) for s in audit['f1']+(audit['tail'],)])
            self.assertEqual([first[s[0]] for s in audit['f1']],list(audit['f1_first_counts']))
            if key == 'X1':
                self.assertEqual([u['proof_bi'] for u in units[7:11]],[84,74,81,84])
                self.assertEqual([u['local_raw_count'] for u in units[7:11]],[1138,1018,1100,1138])
                self.assertEqual([u['confirmed_raw_count'] for u in units[7:11]],[1138]*4)

    def test_given_completed_f1_types_preserve_open_f2_and_filter_future_bad_types(self):
        for key, audit in sorted(M3_GAP_REVISION_AUDIT.items()):
            case, units = gap_revision_input(audit)
            parts = m3_xd_parts(dict(units=units),len(case['raw_rows']))
            complete = [m for m in chan.same_level_decompose(parts) if m.complete]
            types = [m3_xd_type('gap:'+key,m,
                               [u for u in units if u['confirmed_raw_count']<=count],
                               gap_revision_time(case,count))
                     for m,count in zip(complete,audit['f1_first_counts'])]
            self.assertEqual([len(t.evidence_ids) for t in types], [7] if key=='G' else [4,7,11,14])
            now = gap_revision_time(case,len(case['raw_rows']))
            self.assertEqual(chan.confirm_level_up(types,now,'F2'),[])
            records = [dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),
                            low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],
                             [m3_xd_expected(records,s) for s in audit['f2']])
            self.assertEqual(audit['complete_f2'],0)
            future = types[-1]._replace(move_id='gap:'+key+':future',start_price=float('nan'),
                                       confirmed_dt=now+timedelta(days=2))
            self.assertEqual(chan.confirm_level_up(types+[future],now,'F2'),[])


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


# 给定分界的原邻笔条件复算，不等同标准特征或全局分段证明。
M3_FACTOR_XD_AUDIT = {'expectations_sha256': '73107066f4eb70c4165928aa6abdd53099fe1e89532a6c237fee547e0d1f0233',
 'independent_theory_labels': False,
 'global_segmentation_independently_proven': False,
 'cases': {'2022-01-01-81': {'events': ((0, 12, 1, 15, 191, '2022-10-20 15:05:00'),
                                        (13, 17, 1, 20, 239, '2022-12-27 15:05:00')),
                             'f1': [],
                             'local_proofs': [{'event': [0, 12, 1, 15],
                                               'initial_core': [526277196640, 550209838880],
                                               'boundary_left': [490900254000, 546103945140],
                                               'reverse_first': [445604917680, 577234450000],
                                               'reverse_core': [445604917680, 461988337200],
                                               'selection_ticks': -52259145840,
                                               'proof_scope': 'first-break local overlap and direction '
                                                              'selection'},
                                              {'event': [13, 17, 1, 20],
                                               'initial_core': [445604917680, 461988337200],
                                               'boundary_left': [393345771840, 444390336000],
                                               'reverse_first': [358508384640, 425086502400],
                                               'reverse_core': [372011014080, 425086502400],
                                               'selection_ticks': 7339478400,
                                               'proof_scope': 'first-break local overlap and direction '
                                                              'selection'}]},
           '2022-01-01-106': {'events': ((0, 4, 1, 7, 88, '2022-05-19 15:05:00'),
                                         (5, 7, 2, 19, 180, '2022-09-28 15:05:00'),
                                         (8, 16, 1, 19, 180, '2022-09-28 15:05:00'),
                                         (17, 23, 1, 26, 231, '2022-12-15 15:05:00')),
                              'f1': [{'body': {'kind': 'consolidation',
                                               'complete': True,
                                               'direction': None,
                                               'seg_start': 0,
                                               'seg_end': 2,
                                               'start_dt': '2022-01-10',
                                               'end_dt': '2022-08-24',
                                               'start_ticks': 526277196640,
                                               'end_ticks': 577234450000,
                                               'low_ticks': 354371758000,
                                               'high_ticks': 612350382280,
                                               'centers_ticks': [[486944943160, 550209838880]]},
                                      'confirmed_raw_count': 231,
                                      'confirmed_dt': '2022-12-15 15:05:00'}],
                              'local_proofs': [{'event': [0, 4, 1, 7],
                                                'initial_core': [526277196640, 545612041000],
                                                'boundary_left': [494283349820, 545612041000],
                                                'reverse_first': [444731536860, 550209838880],
                                                'reverse_core': [444731536860, 537079010000],
                                                'selection_ticks': -90359778860,
                                                'proof_scope': 'first-break local overlap and direction '
                                                               'selection'},
                                               {'event': [5, 7, 2, 19],
                                                'initial_core': [444731536860, 537079010000],
                                                'gap_ticks': 11052784860,
                                                'first_sequence': [6, 8, 10],
                                                'second_sequence': [[11], [13, 15, 17], [19]],
                                                'second_top': [430365928200,
                                                               470832572860,
                                                               511981860000,
                                                               577234450000,
                                                               407577716000,
                                                               461988337200],
                                                'gap_unfilled_at_proof': False,
                                                'proof_scope': 'gap plus contained second-sequence top'},
                                               {'event': [8, 16, 1, 19],
                                                'initial_core': [390391187680, 433678752000],
                                                'boundary_left': [490900254000, 567165473420],
                                                'reverse_first': [445604917680, 577234450000],
                                                'reverse_core': [445604917680, 461988337200],
                                                'selection_ticks': -38027201680,
                                                'proof_scope': 'first-break local overlap and direction '
                                                               'selection'},
                                               {'event': [17, 23, 1, 26],
                                                'initial_core': [445604917680, 461988337200],
                                                'boundary_left': [393345771840, 444390336000],
                                                'reverse_first': [358508384640, 425086502400],
                                                'reverse_core': [372011014080, 425086502400],
                                                'selection_ticks': 2915683200,
                                                'proof_scope': 'first-break local overlap and direction '
                                                               'selection'}]},
           '2022-04-15-81': {'events': ((0, 12, 1, 15, 173, '2022-12-27 15:05:00'),),
                             'f1': [],
                             'local_proofs': [{'event': [0, 12, 1, 15],
                                               'initial_core': [390391187680, 433678752000],
                                               'boundary_left': [393345771840, 444390336000],
                                               'reverse_first': [358508384640, 425086502400],
                                               'reverse_core': [372011014080, 425086502400],
                                               'selection_ticks': 7339478400,
                                               'proof_scope': 'first-break local overlap and direction '
                                                              'selection'}]},
           '2022-04-15-106': {'events': ((0, 16, 1, 19, 165, '2022-12-15 15:05:00'),),
                              'f1': [],
                              'local_proofs': [{'event': [0, 16, 1, 19],
                                                'initial_core': [390391187680, 433678752000],
                                                'boundary_left': [393345771840, 444390336000],
                                                'reverse_first': [358508384640, 425086502400],
                                                'reverse_core': [372011014080, 425086502400],
                                                'selection_ticks': 2915683200,
                                                'proof_scope': 'first-break local overlap and direction '
                                                               'selection'}]}}}

def factor_xd_input_cases():
    """复用同目录已冻结的84个固定笔输入表，不执行另一测试模块或复制行情。"""
    path = os.path.join(os.path.dirname(__file__), 'test_real_f1_originals.py')
    with open(path, encoding='utf-8') as stream:
        tree = ast.parse(stream.read())
    table = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'M3_FACTOR_F1_AUDIT' for t in node.targets))
    return table['cases']


def factor_xd_parts(case):
    return [SimpleNamespace(start_index=a, end_index=z,
            start_dt=datetime.strptime(start, '%Y-%m-%d'), end_dt=datetime.strptime(end, '%Y-%m-%d'),
            start_value=p0/1000.0, end_value=p1/1000.0, low=min(p0,p1)/1000.0,
            high=max(p0,p1)/1000.0, direction='up' if p1 > p0 else 'down')
            for a,z,start,end,p0,p1,_ in case['parts']]


def factor_xd_expected(case, event):
    a,z,mode,proof,count,_ = event
    parts = case['parts']
    return dict(start_index=parts[a][0], end_index=parts[z][1], start_dt=parts[a][2], end_dt=parts[z][3],
        start_ticks=parts[a][4], end_ticks=parts[z][5],
        low_ticks=min(min(r[4:6]) for r in parts[a:z+1]), high_ticks=max(max(r[4:6]) for r in parts[a:z+1]),
        direction='up' if parts[a][5] > parts[a][4] else 'down', mode=mode, proof_bi=proof,
        evidence_end_index=parts[proof][1], evidence_dt=parts[proof][3], confirmed_raw_count=count)


class TestFactorProductXdProofs(unittest.TestCase):
    def test_declared_xd_and_f1_at_all_component_arrival_counts(self):
        """836个显式部件计数快照；给定分界的输出回归不等同独立XD真值。"""
        cases = factor_xd_input_cases()
        snapshots = 0
        for key,audit in sorted(M3_FACTOR_XD_AUDIT['cases'].items()):
            case = cases[key]
            parts = factor_xd_parts(case)
            seen,first_f1 = {},{}
            for count in range(1,case['rows']+1):
                visible = [p for p,r in zip(parts,case['parts']) if r[6] <= count]
                xds = [x for x in chan.find_xds(visible) if x.complete]
                actual = []
                for x in xds:
                    identity = xd_identity(x)
                    seen.setdefault(identity,count)
                    actual.append(xd_record(x,visible,seen[identity]))
                self.assertEqual(actual,[factor_xd_expected(case,e) for e in audit['events'] if e[4] <= count],
                                 (key,count))
                moves = [m for m in chan.same_level_decompose(xds) if m.complete]
                expected = [m for m in audit['f1'] if m['confirmed_raw_count'] <= count]
                self.assertEqual([move_record(m) for m in moves],
                                 [expected_shape(m['body']) for m in expected],(key,count))
                for m in moves:
                    first_f1.setdefault(move_identity(m),count)
                snapshots += 1
            self.assertEqual(sorted(first_f1.values()),[m['confirmed_raw_count'] for m in audit['f1']])
        self.assertEqual(snapshots,836)

    def test_shared_second_sequence_proof_does_not_complete_f1_early(self):
        """同一证明笔令mode2/mode1同批完成；F1另等12月后继XD，不回填到8月端点。"""
        key = '2022-01-01-106'
        case = factor_xd_input_cases()[key]
        parts = factor_xd_parts(case)
        for count,xd_count,f1_count in ((179,1,0),(180,3,0),(230,3,0),(231,4,1)):
            visible = [p for p,r in zip(parts,case['parts']) if r[6] <= count]
            xds = [x for x in chan.find_xds(visible) if x.complete]
            self.assertEqual(len(xds),xd_count)
            complete = [m for m in chan.same_level_decompose(xds) if m.complete]
            self.assertEqual(len(complete),f1_count)
            if count == 180:
                self.assertEqual([x.mode for x in xds],[1,2,1])
                self.assertEqual(xds[1].evidence_dt,xds[2].evidence_dt)
                self.assertEqual(xds[1].evidence_end_index,xds[2].evidence_end_index)
                self.assertEqual(str(xds[1].evidence_dt)[:10],'2022-09-22')
            if complete:
                self.assertEqual((complete[0].seg_start,complete[0].seg_end),(0,2))
                self.assertEqual(str(complete[0].end_dt)[:10],'2022-08-24')
        events = M3_FACTOR_XD_AUDIT['cases'][key]['events']
        self.assertEqual([e[5] for e in events[1:3]],['2022-09-28 15:05:00']*2)
        self.assertEqual(M3_FACTOR_XD_AUDIT['cases'][key]['f1'][0]['confirmed_dt'],
                         '2022-12-15 15:05:00')


# 给定近期条件链→F1准入；独立整数证书先冻结，不改旧整窗表。
# unit=(方向,起/止时间,起/止价,低/高,mode,proof BI)，双合同行计数另列。
# 外部proof只入证据，未完成尾部不包装成已确认类型。
M3_CONDITIONAL_F1_ADMISSION_AUDIT = {
    'M1_recent266': {
        'fixture': 'real_third_point_xd_margin0.json',
        'id': '588000-30m-20230501-20250228',
        'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        'certificate_sha256': 'dbace4abdbf0b5acd47795a3caa36086a8756ac2f9deca4986a7e52c94eed532',
        'seed': 266,
        'events': ((266, 270, 1, 273), (271, 273, 2, 285), (274, 278, 1, 285), (279, 285, 1, 288)),
        'units': (
            ('up', '2024-12-19 10:00:00', '2024-12-27 11:30:00', 1019, 1099, 1019, 1099, 1, 273),
            ('down', '2024-12-27 11:30:00', '2025-01-06 15:00:00', 1099, 981, 981, 1099, 2, 285),
            ('up', '2025-01-06 15:00:00', '2025-01-16 10:00:00', 981, 1048, 981, 1048, 1, 285),
            ('down', '2025-01-16 10:00:00', '2025-01-27 15:00:00', 1048, 1008, 1001, 1048, 1, 288),
        ),
        'current_counts': (3665, 3815, 3815, 3831),
        'fixed_counts': (3692, 3822, 3822, 3849),
        'current_available_dt': ('2025-01-03 10:01:00', '2025-01-27 14:31:00', '2025-01-27 14:31:00', '2025-02-06 13:31:00'),
        'fixed_available_dt': ('2025-01-08 10:01:00', '2025-02-05 13:31:00', '2025-02-05 13:31:00', '2025-02-10 13:31:00'),
        'f1': (0, 2, 'consolidation', None, (0,), ((1019, 1048),), 3),
        'tail': (3, 3, 'incomplete', None, (), (), None),
        'raw_window': (3598, 3849),
        'complete_f2': 0,
    },
    'S3_recent10': {
        'fixture': 'real_strict_trend.json',
        'id': '518880-day-20210101-20260731',
        'source_sha256': 'ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        'certificate_sha256': 'b1a50900e1ffcbc03c5e2cc20d83da300da04d1c5c81824783e4fe35b9a72520',
        'seed': 10,
        'events': ((10, 12, 1, 15), (13, 23, 1, 26), (24, 26, 1, 29), (27, 35, 1, 42), (36, 42, 1, 45), (43, 81, 1, 84)),
        'units': (
            ('down', '2021-05-26 00:00:00', '2021-06-30 00:00:00', 3865, 3579, 3579, 3865, 1, 15),
            ('up', '2021-06-30 00:00:00', '2021-11-18 00:00:00', 3579, 3745, 3541, 3745, 1, 26),
            ('down', '2021-11-18 00:00:00', '2021-12-15 00:00:00', 3745, 3550, 3550, 3745, 1, 29),
            ('up', '2021-12-15 00:00:00', '2022-03-09 00:00:00', 3550, 4077, 3550, 4077, 1, 42),
            ('down', '2022-03-09 00:00:00', '2022-05-18 00:00:00', 4077, 3834, 3792, 4077, 1, 45),
            ('up', '2022-05-18 00:00:00', '2023-10-31 00:00:00', 3834, 4642, 3615, 4642, 1, 84),
        ),
        'current_counts': (141, 232, 246, 329, 348, 701),
        'fixed_counts': (149, 239, 256, 334, 355, 705),
        'current_available_dt': ('2021-08-02 15:05:00', '2021-12-16 15:05:00', '2022-01-06 15:05:00', '2022-05-17 15:05:00', '2022-06-14 15:05:00', '2023-11-24 15:05:00'),
        'fixed_available_dt': ('2021-08-12 15:05:00', '2021-12-27 15:05:00', '2022-01-20 15:05:00', '2022-05-24 15:05:00', '2022-06-23 15:05:00', '2023-11-30 15:05:00'),
        'f1': (0, 2, 'consolidation', None, (0,), ((3579, 3745),), 3),
        'tail': (3, 5, 'consolidation', None, (3,), ((3792, 4077),), None),
        'raw_window': (1, 705),
        'complete_f2': 0,
    },
    'M2_recent16': {
        'fixture': 'real_third_point_xd_margin0.json',
        'id': '512880-5m-20260201-20260724',
        'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        'certificate_sha256': '4692e046fbd8c5ae9293868dc8e8126b3e314e3e250cbb1015cd38698fb93d22',
        'seed': 16,
        'events': ((16, 34, 1, 37), (35, 37, 1, 51), (38, 48, 1, 51), (49, 55, 1, 58), (56, 64, 2, 72), (65, 67, 1, 70)),
        'units': (
            ('down', '2026-02-10 10:10:00', '2026-03-06 09:35:00', 1200, 1113, 1113, 1200, 1, 37),
            ('up', '2026-03-06 09:35:00', '2026-03-06 14:20:00', 1113, 1135, 1113, 1135, 1, 51),
            ('down', '2026-03-06 14:20:00', '2026-03-13 09:55:00', 1135, 1112, 1105, 1135, 1, 51),
            ('up', '2026-03-13 09:55:00', '2026-03-17 10:35:00', 1112, 1140, 1100, 1140, 1, 58),
            ('down', '2026-03-17 10:35:00', '2026-03-23 14:55:00', 1140, 1031, 1031, 1140, 2, 72),
            ('up', '2026-03-23 14:55:00', '2026-03-25 10:35:00', 1031, 1060, 1031, 1060, 1, 70),
        ),
        'raw_window': (372, 1648),
        'complete_f2': 0,
        'current_counts': (924, 1156, 1156, 1329, 1639, 1639),
        'current_local_counts': (924, 1156, 1156, 1329, 1639, 1582),
        'current_local_proof_prices': (1135, 1125, 1125, 1104, 1035, 1048),
        'current_available_dt': ('2026-03-06 14:26:00', '2026-03-13 13:21:00', '2026-03-13 13:21:00', '2026-03-19 09:56:00', '2026-03-27 11:16:00', '2026-03-27 11:16:00'),
        'fixed_counts': (940, 1183, 1183, 1349, 1648, 1648),
        'fixed_local_counts': (940, 1183, 1183, 1349, 1648, 1618),
        'fixed_local_proof_prices': (1135, 1125, 1125, 1101, 1035, 1033),
        'fixed_available_dt': ('2026-03-09 10:11:00', '2026-03-16 10:01:00', '2026-03-16 10:01:00', '2026-03-19 13:06:00', '2026-03-27 13:31:00', '2026-03-27 13:31:00'),
        'f1': (0, 2, 'consolidation', None, (0,), ((1113, 1135),), 3),
        'tail': (3, 5, 'incomplete', None, (), (), None),
    },
    'Y1_recent1': {
        'certificate_sha256': '211986891a02e3c3d4536e622746e51c034a94bfe7c88b25b6f873d2ca1adace',
        'complete_f2': 0,
        'current_available_dt': ('2026-05-11 09:51:00', '2026-05-13 14:26:00', '2026-05-14 11:21:00', '2026-05-15 09:31:00'),
        'current_counts': (152, 287, 317, 344),
        'current_proof_prices': (9801, 9834, 9761, 9797),
        'events': ((1, 7, 1, 14), (8, 18, 1, 29), (19, 29, 1, 32), (30, 32, 1, 35)),
        'f1': (0, 2, 'consolidation', None, (0,), ((9714, 9906),), 3),
        'fixed_available_dt': ('2026-05-11 10:46:00', '2026-05-14 09:51:00', '2026-05-14 13:21:00', '2026-05-15 10:11:00'),
        'fixed_counts': (163, 299, 323, 352),
        'fixed_proof_prices': (9780, 9834, 9761, 9797),
        'fixture': 'real_second_point.json',
        'id': '518880-5m-20260501-20260724',
        'raw_window': (1, 352),
        'seed': 1,
        'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
        'tail': (3, 3, 'incomplete', None, (), (), None),
        'units': (
            ('up', '2026-05-06 10:00:00', '2026-05-07 14:45:00', 9702, 9933, 9702, 9933, 1, 14),
            ('down', '2026-05-07 14:45:00', '2026-05-11 14:00:00', 9933, 9714, 9714, 9933, 1, 29),
            ('up', '2026-05-11 14:00:00', '2026-05-13 14:20:00', 9714, 9834, 9714, 9906, 1, 32),
            ('down', '2026-05-13 14:20:00', '2026-05-14 11:15:00', 9834, 9761, 9761, 9834, 1, 35),
        ),
    },
}

class TestConditionalF1Admission(unittest.TestCase):
    """仅给定近期XD条件链的F1接线；不验证生产raw→XD或整窗旧角色。"""

    @staticmethod
    def _parts(audit, mirrored=False):
        out=[]
        for u in audit['units']:
            direction,a,z,s,e,lo,hi,mode,proof=u
            if mirrored:
                direction='down' if direction=='up' else 'up'
                s,e,lo,hi=20000-s,20000-e,20000-hi,20000-lo
            out.append(SimpleNamespace(direction=direction,start_dt=date(a),end_dt=date(z),
                       start_value=s/1000.,end_value=e/1000.,low=lo/1000.,high=hi/1000.,
                       mode=mode,proof_bi=proof))
        return out

    @staticmethod
    def _cores(audit,name,mirrored=False):
        return tuple((20000-hi,20000-lo) if mirrored else (lo,hi) for lo,hi in audit[name][5])

    @staticmethod
    def _expected(parts,a,z,kind,complete,cores=()):
        return (a,z,kind,None,complete,parts[a].start_dt,parts[z].end_dt,
                round(min(p.low for p in parts[a:z+1])*1000),
                round(max(p.high for p in parts[a:z+1])*1000),tuple(cores))

    def _confirmed(self,audit,move,parts,contract,mirrored=False):
        self.assertTrue(move.complete)
        proof=audit['f1'][-1]
        namespace=('conditional-f1-v1:'+audit['certificate_sha256']+':'+audit['id']+
                   ':seed'+str(audit['seed'])+':'+contract+':'+str(mirrored))
        ids=tuple(namespace+':xd:'+str(i) for i in range(proof+1))
        return chan.ConfirmedMoveType(namespace+':f1:0','F1',move.kind,move.direction,
                move.start_dt,move.end_dt,parts[move.seg_start].start_value,
                parts[move.seg_end].end_value,move.low,move.high,
                date(audit[contract+'_available_dt'][proof]),ids[:move.seg_end+1],ids,tuple(move.centers))

    def test_given_prefixes_keep_three_unit_candidate_pending_until_external_proof(self):
        """三完整XD仅候选，第四段才完成；同批两XD不虚构中间raw时刻。"""
        for audit in M3_CONDITIONAL_F1_ADMISSION_AUDIT.values():
            for mirrored in (False,True):
                parts=self._parts(audit,mirrored)
                for size in range(len(parts)+1):
                    expected=[]
                    if size:
                        if size<3:
                            expected=[self._expected(parts,0,size-1,'incomplete',False)]
                        elif size==3:
                            expected=[self._expected(parts,0,2,'consolidation',False,self._cores(audit,'f1',mirrored))]
                        else:
                            tail=self._cores(audit,'tail',mirrored) if size==6 else ()
                            expected=[self._expected(parts,0,2,'consolidation',True,self._cores(audit,'f1',mirrored)),
                                      self._expected(parts,3,size-1,'consolidation' if tail else 'incomplete',False,tail)]
                    self.assertEqual([m3_xd_shape(m) for m in chan.same_level_decompose(parts[:size])],expected)
                for contract in ('current','fixed'):
                    counts=audit[contract+'_counts']
                    for count in sorted({n for at in counts for n in (at-1,at)}):
                        size=sum(at<=count for at in counts)
                        moves=chan.same_level_decompose(parts[:size])
                        self.assertEqual(sum(m.complete for m in moves),int(count>=counts[3]))

    def test_external_proof_is_evidence_and_never_changes_composition_or_confirmation(self):
        """F1止于unit2，证明unit3只入证据；较晚尾部不改首见快照身份。"""
        for audit in M3_CONDITIONAL_F1_ADMISSION_AUDIT.values():
            for mirrored in (False,True):
                parts=self._parts(audit,mirrored)
                move=chan.same_level_decompose(parts[:4])[0]
                for contract in ('current','fixed'):
                    frozen=self._confirmed(audit,move,parts,contract,mirrored)
                    later=chan.same_level_decompose(parts)[0]
                    self.assertEqual(self._confirmed(audit,later,parts,contract,mirrored),frozen)
                    self.assertEqual((move.seg_start,move.seg_end),(0,2))
                    self.assertEqual((frozen.start_dt,frozen.end_dt),(parts[0].start_dt,parts[2].end_dt))
                    self.assertEqual(frozen.end_price,parts[2].end_value)
                    self.assertNotEqual(frozen.end_dt,parts[3].end_dt)
                    self.assertNotEqual(frozen.end_price,parts[3].end_value)
                    self.assertEqual((len(frozen.unit_ids),len(frozen.evidence_ids)),(3,4))
                    self.assertNotIn(frozen.evidence_ids[3],frozen.unit_ids)
                    self.assertIn(':seed'+str(audit['seed'])+':'+contract+':',frozen.move_id)
                    self.assertIsNone(frozen.direction)
                    self.assertEqual(frozen.kind,'consolidation')
                    self.assertEqual(frozen.confirmed_dt,date(audit[contract+'_available_dt'][3]))
                    self.assertGreater(frozen.confirmed_dt,max(date(s) for s in audit[contract+'_available_dt'][:3]))

    def test_declared_external_arrival_delay_keeps_candidate_unconfirmed(self):
        """给定XD到达时间表截断；不把形态端点或旧证明时刻当F1可用时刻。"""
        for audit in M3_CONDITIONAL_F1_ADMISSION_AUDIT.values():
            parts=self._parts(audit)
            for contract in ('current','fixed'):
                stamps=[date(s) for s in audit[contract+'_available_dt']]
                now=stamps[3]
                for delayed in (False,True):
                    arrivals=list(stamps)
                    arrivals[3]=now+timedelta(days=1) if delayed else now
                    for observed,ready in ((now-timedelta(microseconds=1),False),
                                           (now,not delayed),
                                           (arrivals[3]-timedelta(microseconds=1),False),
                                           (arrivals[3],True)):
                        size=next((i for i,t in enumerate(arrivals) if t>observed),len(arrivals))
                        moves=chan.same_level_decompose(parts[:size])
                        self.assertEqual(any(m.complete for m in moves),ready)
                        if ready:
                            frozen=self._confirmed(audit,moves[0],parts,contract)
                            frozen=frozen._replace(confirmed_dt=arrivals[3])
                            self.assertGreater(frozen.confirmed_dt,frozen.end_dt)
                            self.assertEqual(chan.confirm_level_up([frozen],observed,'F2'),[])

    def test_recursive_admission_rejects_parts_and_bare_moves_and_retains_empty_f2(self):
        """XD及裸MoveType不作递归输入；真实完成F1只一项，有限范围F2仍空。"""
        for audit in M3_CONDITIONAL_F1_ADMISSION_AUDIT.values():
            parts=self._parts(audit)
            complete=chan.same_level_decompose(parts)[0]
            candidate=chan.same_level_decompose(parts[:3])[0]
            for contract in ('current','fixed'):
                known=date(audit[contract+'_available_dt'][3])
                for wrong in ([parts[0]],[candidate],[complete]):
                    with self.assertRaises(ValueError):chan.confirm_level_up(wrong,known,'F2')
                admitted=[self._confirmed(audit,m,parts,contract)
                          for m in chan.same_level_decompose(parts) if m.complete]
                self.assertEqual(len(admitted),1)
                self.assertEqual(chan.confirm_level_up(admitted,known,'F2'),[])
                self.assertFalse(any(m.complete for m in chan.level_up(admitted)))
                future=admitted[0]._replace(move_id=None,level=None,low=None,start_price=float('nan'),
                                           confirmed_dt=known+timedelta(days=2))
                self.assertEqual(chan.confirm_level_up(admitted+[future],known,'F2'),[])
                self.assertEqual(audit['complete_f2'],0)

    def test_m2_local_child_proof_waits_for_parent_publication_without_a_visible_hole(self):
        """65的local70早于parent72；给定链仍须整批发布最后两项，不跳父段。"""
        audit=M3_CONDITIONAL_F1_ADMISSION_AUDIT['M2_recent16']
        parts=self._parts(audit)
        self.assertEqual((audit['events'][-1][3],audit['events'][-2][3]),(70,72))
        for contract in ('current','fixed'):
            local=audit[contract+'_local_counts'][-1]
            published=audit[contract+'_counts'][-1]
            self.assertLess(local,published)
            self.assertEqual(published,audit[contract+'_counts'][-2])
            for observed,size in ((local,4),(published-1,4),(published,6)):
                visible=sum(at<=observed for at in audit[contract+'_counts'])
                self.assertEqual(visible,size)
                moves=chan.same_level_decompose(parts[:visible])
                self.assertEqual(sum(m.complete for m in moves),1)
                self.assertEqual((moves[-1].seg_start,moves[-1].seg_end,moves[-1].kind,moves[-1].complete),
                                 (3,size-1,'incomplete',False))
        self.assertEqual((audit['current_local_counts'][-1],audit['current_counts'][-1]),(1582,1639))
        self.assertEqual((audit['fixed_local_counts'][-1],audit['fixed_counts'][-1]),(1618,1648))


# 给定seed1修正头部与保留后缀的固定合同；旧表保持，原型不生成预期。
M3_Y1_JOINED_ROLE_AUDIT = {
    'fixture': 'real_second_point.json',
    'id': '518880-5m-20260501-20260724',
    'fixture_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
    'seed': 1,
    'scope': 'given_recent_seed1_fixed_without_active',
    'certificate_sha256': 'ee58a32f2af125706a60a384624854de3777117cbd131e42ea951b32b4b17d3d',
    'events': (
        (1, 7, 1, 14),
        (8, 18, 1, 29),
        (19, 29, 1, 32),
        (30, 32, 1, 35),
        (33, 35, 1, 38),
        (36, 48, 1, 51),
        (49, 51, 2, 65),
        (52, 58, 1, 61),
        (59, 63, 2, 79),
        (64, 76, 2, 86),
        (77, 83, 1, 86),
        (84, 86, 2, 94),
        (87, 91, 1, 94),
        (92, 94, 1, 97),
        (95, 97, 1, 100),
        (98, 106, 1, 109),
        (107, 109, 1, 112),
        (110, 112, 2, 122),
        (113, 123, 2, 129),
        (124, 126, 2, 136),
        (127, 131, 2, 147),
        (132, 144, 1, 147),
        (145, 147, 1, 150),
        (148, 158, 2, 164),
        (159, 161, 1, 164),
        (162, 164, 1, 169),
        (165, 171, 1, 176),
        (172, 176, 2, 182),
        (177, 179, 1, 182),
        (180, 182, 1, 185),
        (183, 191, 1, 194),
        (192, 200, 1, 203),
        (201, 205, 1, 208),
        (206, 208, 1, 211),
        (209, 211, 1, 214),
        (212, 220, 2, 228),
        (221, 225, 1, 228),
        (226, 240, 1, 243),
        (241, 251, 2, 263),
    ),
    'units': (
        ('up', '2026-05-06 10:00:00', '2026-05-07 14:45:00', 9702, 9933, 9702, 9933, 1, 14, 163, 163),
        ('down', '2026-05-07 14:45:00', '2026-05-11 14:00:00', 9933, 9714, 9714, 9933, 1, 29, 299, 299),
        ('up', '2026-05-11 14:00:00', '2026-05-13 14:20:00', 9714, 9834, 9714, 9906, 1, 32, 323, 323),
        ('down', '2026-05-13 14:20:00', '2026-05-14 11:15:00', 9834, 9761, 9761, 9834, 1, 35, 352, 352),
        ('up', '2026-05-14 11:15:00', '2026-05-14 15:00:00', 9761, 9797, 9761, 9797, 1, 38, 381, 381),
        ('down', '2026-05-14 15:00:00', '2026-05-20 11:15:00', 9797, 9332, 9332, 9797, 1, 51, 557, 557),
        ('up', '2026-05-20 11:15:00', '2026-05-21 09:45:00', 9332, 9543, 9332, 9543, 2, 65, 661, 661),
        ('down', '2026-05-21 09:45:00', '2026-05-22 10:40:00', 9543, 9445, 9445, 9543, 1, 61, 630, 661),
        ('up', '2026-05-22 10:40:00', '2026-05-25 09:35:00', 9445, 9540, 9441, 9540, 2, 79, 840, 840),
        ('down', '2026-05-25 09:35:00', '2026-05-28 13:10:00', 9540, 9108, 9108, 9540, 2, 86, 946, 946),
        ('up', '2026-05-28 13:10:00', '2026-06-01 09:45:00', 9108, 9414, 9108, 9414, 1, 86, 946, 946),
        ('down', '2026-06-01 09:45:00', '2026-06-02 10:00:00', 9414, 9266, 9266, 9414, 2, 94, 1017, 1017),
        ('up', '2026-06-02 10:00:00', '2026-06-02 14:40:00', 9266, 9414, 9266, 9414, 1, 94, 1017, 1017),
        ('down', '2026-06-02 14:40:00', '2026-06-03 13:35:00', 9414, 9268, 9268, 9414, 1, 97, 1067, 1067),
        ('up', '2026-06-03 13:35:00', '2026-06-04 13:20:00', 9268, 9311, 9268, 9311, 1, 100, 1115, 1115),
        ('down', '2026-06-04 13:20:00', '2026-06-08 14:45:00', 9311, 8937, 8937, 9311, 1, 109, 1218, 1218),
        ('up', '2026-06-08 14:45:00', '2026-06-09 13:50:00', 8937, 9046, 8937, 9046, 1, 112, 1296, 1296),
        ('down', '2026-06-09 13:50:00', '2026-06-11 10:50:00', 9046, 8418, 8418, 9046, 2, 122, 1377, 1377),
        ('up', '2026-06-11 10:50:00', '2026-06-15 10:55:00', 8418, 8988, 8418, 8988, 2, 129, 1456, 1456),
        ('down', '2026-06-15 10:55:00', '2026-06-15 14:45:00', 8988, 8910, 8910, 8988, 2, 136, 1520, 1520),
        ('up', '2026-06-15 14:45:00', '2026-06-17 09:35:00', 8910, 8986, 8910, 8986, 2, 147, 1624, 1624),
        ('down', '2026-06-17 09:35:00', '2026-06-22 11:25:00', 8986, 8655, 8655, 8986, 1, 147, 1624, 1624),
        ('up', '2026-06-22 11:25:00', '2026-06-22 14:55:00', 8655, 8731, 8655, 8731, 1, 150, 1675, 1675),
        ('down', '2026-06-22 14:55:00', '2026-06-25 10:15:00', 8731, 8267, 8267, 8731, 2, 164, 1773, 1773),
        ('up', '2026-06-25 10:15:00', '2026-06-25 13:15:00', 8267, 8329, 8267, 8329, 1, 164, 1773, 1773),
        ('down', '2026-06-25 13:15:00', '2026-06-25 15:00:00', 8329, 8282, 8282, 8329, 1, 169, 1830, 1830),
        ('up', '2026-06-25 15:00:00', '2026-06-29 11:30:00', 8282, 8479, 8282, 8479, 1, 176, 1881, 1881),
        ('down', '2026-06-29 11:30:00', '2026-06-30 10:20:00', 8479, 8224, 8224, 8479, 2, 182, 1963, 1963),
        ('up', '2026-06-30 10:20:00', '2026-06-30 14:55:00', 8224, 8389, 8224, 8389, 1, 182, 1963, 1963),
        ('down', '2026-06-30 14:55:00', '2026-07-01 14:20:00', 8389, 8253, 8253, 8389, 1, 185, 1993, 1993),
        ('up', '2026-07-01 14:20:00', '2026-07-06 09:50:00', 8253, 8738, 8253, 8738, 1, 194, 2113, 2113),
        ('down', '2026-07-06 09:50:00', '2026-07-08 10:05:00', 8738, 8551, 8551, 8738, 1, 203, 2189, 2189),
        ('up', '2026-07-08 10:05:00', '2026-07-08 14:30:00', 8551, 8605, 8551, 8605, 1, 208, 2235, 2235),
        ('down', '2026-07-08 14:30:00', '2026-07-09 11:25:00', 8605, 8446, 8446, 8605, 1, 211, 2279, 2279),
        ('up', '2026-07-09 11:25:00', '2026-07-10 11:10:00', 8446, 8587, 8446, 8587, 1, 214, 2323, 2323),
        ('down', '2026-07-10 11:10:00', '2026-07-14 09:30:00', 8587, 8302, 8302, 8587, 2, 228, 2440, 2440),
        ('up', '2026-07-14 09:30:00', '2026-07-15 09:35:00', 8302, 8420, 8302, 8420, 1, 228, 2440, 2440),
        ('down', '2026-07-15 09:35:00', '2026-07-17 13:25:00', 8420, 8261, 8261, 8420, 1, 243, 2580, 2580),
        ('up', '2026-07-17 13:25:00', '2026-07-22 11:25:00', 8261, 8614, 8261, 8614, 2, 263, 2793, 2793),
    ),
    'f1': (
        (0, 2, 'consolidation', None, (0,), ((9714, 9906),), 3),
        (3, 8, 'down', 'down', (3, 6), ((9761, 9797), (9445, 9540)), 9),
        (9, 11, 'consolidation', None, (9,), ((9266, 9414),), 12),
        (12, 14, 'consolidation', None, (12,), ((9268, 9311),), 15),
        (15, 17, 'consolidation', None, (15,), ((8937, 9046),), 18),
        (18, 20, 'consolidation', None, (18,), ((8910, 8986),), 21),
        (21, 26, 'down', 'down', (21, 24), ((8655, 8731), (8282, 8329)), 27),
        (27, 29, 'consolidation', None, (27,), ((8253, 8389),), 30),
        (30, 32, 'consolidation', None, (30,), ((8551, 8605),), 33),
        (33, 37, 'consolidation', None, (33,), ((8446, 8587),), 38),
    ),
    'f2': (
        (0, 9, 'down', 'down', (1, 4), ((9332, 9414), (8418, 8986)), None),
    ),
    'f1_first_counts': (352, 946, 1017, 1218, 1456, 1624, 1963, 2113, 2279, 2793),
    'f1_evidence_counts': (4, 11, 13, 16, 19, 22, 29, 31, 34, 39),
    'tail': (38, 38, 'incomplete', None, (), (), None),
    'f2_spans': (((1, 3, 3), (4, 6, 9)),),
    'complete_f2': 0,
    'strict_tail_skip': 'no_compare_legs',
    'automatic_F2_points': 0,
    'legacy_guard': {
        'middle_low': 9445,
        'middle_misses_ticks': 4,
        'new_A_core': (9714, 9906),
        'new_B_first_pair': (9441, 9540),
        'old_anchor_event': (52, 76, 2, 86),
        'old_first_and_second_reusable': False,
        'remapped_B_zn': (6, 10),
        'strict_roles_reusable': False,
    },
}


class TestY1JoinedFixedRoles(unittest.TestCase):
    """给定39个条件XD的固定合同；不把旧严格角色或原型结果当预期。"""

    @staticmethod
    def _data():
        return gap_revision_input(M3_Y1_JOINED_ROLE_AUDIT)

    @staticmethod
    def _types(case,units,moves):
        audit=M3_Y1_JOINED_ROLE_AUDIT
        key='Y1-joined1-fixed:'+audit['certificate_sha256']
        return [m3_xd_type(key,move,units[:size],gap_revision_time(case,count))
                for move,count,size in zip(moves,audit['f1_first_counts'],audit['f1_evidence_counts'])]

    def test_joined_unit_prefixes_and_mirrors_preserve_the_ten_declared_f1_cuts(self):
        audit=M3_Y1_JOINED_ROLE_AUDIT
        _,original=self._data()
        self.assertEqual(audit['events'][:4],M3_CONDITIONAL_F1_ADMISSION_AUDIT['Y1_recent1']['events'])
        self.assertEqual(audit['f1'][0],M3_CONDITIONAL_F1_ADMISSION_AUDIT['Y1_recent1']['f1'])
        for mirrored in (False,True):
            units=[dict(u,direction='down' if u['direction']=='up' else 'up',
                        start_ticks=20000-u['start_ticks'],end_ticks=20000-u['end_ticks'],
                        low_ticks=20000-u['high_ticks'],high_ticks=20000-u['low_ticks'])
                   for u in original] if mirrored else original
            specs=[]
            for a,z,kind,entry,triples,cores,proof in audit['f1']+(audit['tail'],):
                if mirrored:
                    kind={'up':'down','down':'up'}.get(kind,kind)
                    entry={'up':'down','down':'up'}.get(entry,entry)
                    cores=tuple((20000-hi,20000-lo) for lo,hi in cores)
                specs.append((a,z,kind,entry,triples,cores,proof))
            for count in range(len(units)+1):
                parts=m3_xd_parts(dict(units=units[:count]),2793)
                actual=chan.same_level_decompose(parts)
                expected=[s for s in specs if s[-1] is not None and s[-1]<count]
                self.assertEqual([m3_xd_shape(m) for m in actual if m.complete],
                                 [m3_xd_expected(units,s) for s in expected],(mirrored,count))
                if count==len(units):
                    self.assertEqual([m3_xd_shape(m) for m in actual],
                                     [m3_xd_expected(units,s) for s in specs])

    def test_fixed_arrival_batches_freeze_f1_evidence_and_keep_recursive_f2_open(self):
        audit=M3_Y1_JOINED_ROLE_AUDIT
        case,units=self._data()
        counts=sorted({n for u in units for n in (u['confirmed_raw_count']-1,u['confirmed_raw_count'])})
        first,types={},[]
        key='Y1-joined1-fixed:'+audit['certificate_sha256']
        for count in counts:
            size=sum(u['confirmed_raw_count']<=count for u in units)
            moves=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
            expected=[s for s in audit['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
            self.assertEqual([m3_xd_shape(m) for m in moves],
                             [m3_xd_expected(units,s) for s in expected])
            for move in moves:
                if move.seg_start not in first:
                    first[move.seg_start]=count
                    types.append(m3_xd_type(key,move,units[:size],gap_revision_time(case,count)))
            self.assertEqual(chan.confirm_level_up(types,gap_revision_time(case,count),'F2'),[])
        self.assertEqual([first[s[0]] for s in audit['f1']],list(audit['f1_first_counts']))
        self.assertEqual([len(t.evidence_ids) for t in types],list(audit['f1_evidence_counts']))
        self.assertEqual(types,self._types(case,units,moves))
        self.assertEqual((types[1].unit_ids[-1],len(types[1].evidence_ids)),(key+':xd:8',11))
        self.assertIsNone(types[0].direction)
        self.assertGreater(types[0].end_price,types[0].start_price)
        records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),
                      high_ticks=round(t.high*1000)) for t in types]
        self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],
                         [m3_xd_expected(records,s) for s in audit['f2']])

    def test_f2_scans_keep_missing_completion_distinct_from_legacy_point_verdicts(self):
        audit=M3_Y1_JOINED_ROLE_AUDIT
        case,units=self._data()
        moves=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),2793)) if m.complete]
        types=self._types(case,units,moves)
        now=gap_revision_time(case,2793)
        rows=m3_xd_rows(case)
        for supplied in (types,types+[types[-1]._replace(move_id='future',
                        confirmed_dt=now+timedelta(days=1),start_price=float('nan'))]):
            scan=chan.scan_strict_divergence(supplied,now,'F2')
            self.assertEqual(scan.results,())
            self.assertEqual([reason for _,reason in scan.skipped],[audit['strict_tail_skip']])
            self.assertEqual(scan.completed_types,0)
            first=chan.scan_first_points(supplied,rows,now,'F2')
            self.assertEqual((first.points,first.exclusions,first.completed_types),([],(),0))
            chain=chan.analyze_point_chain(supplied,rows,now,'F2')
            self.assertEqual((chain.first_points,chain.contexts,chain.second_points,
                              chain.third_points,chain.formations,chain.unresolved_move_ids),
                             ([],[],[],[],[],()))
        self.assertFalse(audit['legacy_guard']['strict_roles_reusable'])
        self.assertFalse(audit['legacy_guard']['old_first_and_second_reusable'])
        self.assertEqual(case['first_point']['reason'],'no_new_extreme')  # 历史原表保留。


# 活动合同只扩展实际证明/发布时钟；组成与F1/F2规格复用上方固定角色表。
M3_Y1_CURRENT_CLOCK_AUDIT = {
    'certificate_sha256': 'c7f542460f4019da02ee93d8945504162f1faf5821f3b32a79cce7eef34e8dd0',
    'fixed_role_certificate_sha256': 'ee58a32f2af125706a60a384624854de3777117cbd131e42ea951b32b4b17d3d',
    'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
    'scope': 'given_recent_seed1_all_current',
    'local_counts': (152, 287, 317, 344, 377, 542, 655, 624, 836, 907, 907, 1007, 1013, 1059, 1084, 1212, 1277, 1371, 1450, 1513, 1612, 1612, 1642, 1761, 1761, 1809, 1869, 1953, 1953, 1981, 2110, 2182, 2230, 2276, 2306, 2434, 2434, 2568, 2788),
    'published_counts': (152, 287, 317, 344, 377, 542, 655, 655, 836, 907, 907, 1007, 1013, 1059, 1084, 1212, 1277, 1371, 1450, 1513, 1612, 1612, 1642, 1761, 1761, 1809, 1869, 1953, 1953, 1981, 2110, 2182, 2230, 2276, 2306, 2434, 2434, 2568, 2788),
    'f1_first_counts': (344, 907, 1013, 1212, 1450, 1612, 1953, 2110, 2276, 2788),
    'f1_evidence_counts': (4, 11, 13, 16, 19, 22, 29, 31, 34, 39),
    'local_proofs': (
        (9801, '2026-05-11 09:45:00', True),
        (9834, '2026-05-13 14:20:00', True),
        (9761, '2026-05-14 11:15:00', True),
        (9797, '2026-05-14 15:00:00', True),
        (9540, '2026-05-15 13:40:00', True),
        (9541, '2026-05-21 09:35:00', True),
        (9524, '2026-05-25 10:50:00', True),
        (9474, '2026-05-22 13:50:00', True),
        (9386, '2026-05-29 09:35:00', True),
        (9374, '2026-06-01 11:25:00', True),
        (9374, '2026-06-01 11:25:00', True),
        (9293, '2026-06-03 13:05:00', True),
        (9268, '2026-06-03 13:35:00', True),
        (9311, '2026-06-04 13:20:00', True),
        (9241, '2026-06-05 09:50:00', True),
        (9046, '2026-06-09 13:50:00', True),
        (8550, '2026-06-11 09:35:00', True),
        (8645, '2026-06-12 14:50:00', True),
        (8967, '2026-06-16 13:15:00', True),
        (8944, '2026-06-17 14:25:00', True),
        (8711, '2026-06-22 14:30:00', True),
        (8711, '2026-06-22 14:30:00', True),
        (8570, '2026-06-23 11:25:00', True),
        (8288, '2026-06-25 14:40:00', True),
        (8288, '2026-06-25 14:40:00', True),
        (8377, '2026-06-26 14:35:00', True),
        (8240, '2026-06-30 09:55:00', True),
        (8253, '2026-07-01 14:20:00', True),
        (8253, '2026-07-01 14:20:00', True),
        (8445, '2026-07-02 11:05:00', True),
        (8588, '2026-07-07 09:35:00', True),
        (8602, '2026-07-08 11:30:00', True),
        (8446, '2026-07-09 11:25:00', True),
        (8587, '2026-07-10 11:10:00', True),
        (8470, '2026-07-13 09:35:00', True),
        (8351, '2026-07-15 13:35:00', True),
        (8351, '2026-07-15 13:35:00', True),
        (8362, '2026-07-20 11:00:00', True),
        (8388, '2026-07-24 14:30:00', True),
    ),
    'publication_proofs': (
        (9801, '2026-05-11 09:45:00', True),
        (9834, '2026-05-13 14:20:00', True),
        (9761, '2026-05-14 11:15:00', True),
        (9797, '2026-05-14 15:00:00', True),
        (9540, '2026-05-15 13:40:00', True),
        (9541, '2026-05-21 09:35:00', True),
        (9524, '2026-05-25 10:50:00', True),
        (9474, '2026-05-22 13:50:00', False),
        (9386, '2026-05-29 09:35:00', True),
        (9374, '2026-06-01 11:25:00', True),
        (9374, '2026-06-01 11:25:00', True),
        (9293, '2026-06-03 13:05:00', True),
        (9268, '2026-06-03 13:35:00', True),
        (9311, '2026-06-04 13:20:00', True),
        (9241, '2026-06-05 09:50:00', True),
        (9046, '2026-06-09 13:50:00', True),
        (8550, '2026-06-11 09:35:00', True),
        (8645, '2026-06-12 14:50:00', True),
        (8967, '2026-06-16 13:15:00', True),
        (8944, '2026-06-17 14:25:00', True),
        (8711, '2026-06-22 14:30:00', True),
        (8711, '2026-06-22 14:30:00', True),
        (8570, '2026-06-23 11:25:00', True),
        (8288, '2026-06-25 14:40:00', True),
        (8288, '2026-06-25 14:40:00', True),
        (8377, '2026-06-26 14:35:00', True),
        (8240, '2026-06-30 09:55:00', True),
        (8253, '2026-07-01 14:20:00', True),
        (8253, '2026-07-01 14:20:00', True),
        (8445, '2026-07-02 11:05:00', True),
        (8588, '2026-07-07 09:35:00', True),
        (8602, '2026-07-08 11:30:00', True),
        (8446, '2026-07-09 11:25:00', True),
        (8587, '2026-07-10 11:10:00', True),
        (8470, '2026-07-13 09:35:00', True),
        (8351, '2026-07-15 13:35:00', True),
        (8351, '2026-07-15 13:35:00', True),
        (8362, '2026-07-20 11:00:00', True),
        (8388, '2026-07-24 14:30:00', True),
    ),
}


class TestY1CurrentRoleClocks(unittest.TestCase):
    """活动证明版本分别准入；组成复用固定角色，时钟和输入身份独立。"""

    @staticmethod
    def _data():
        clock=M3_Y1_CURRENT_CLOCK_AUDIT
        role=M3_Y1_JOINED_ROLE_AUDIT
        if clock['fixed_role_certificate_sha256']!=role['certificate_sha256']:
            raise AssertionError('活动时钟须绑定同一组成版本')
        case,units=gap_revision_input(role)
        for i,unit in enumerate(units):
            unit['local_raw_count']=clock['local_counts'][i]
            unit['confirmed_raw_count']=clock['published_counts'][i]
        return case,units,clock

    @staticmethod
    def _types(case,units,moves,clock):
        key='Y1joined1-current:'+clock['certificate_sha256']
        return [m3_xd_type(key,move,units[:size],gap_revision_time(case,count))
                for move,count,size in zip(moves,clock['f1_first_counts'],clock['f1_evidence_counts'])]

    def test_proof94_versions_are_distinct_and_local_child61_waits_for_parent65(self):
        case,units,clock=self._data()
        role=M3_Y1_JOINED_ROLE_AUDIT
        self.assertEqual(role['events'][11][3],role['events'][12][3])
        self.assertEqual((clock['published_counts'][11],clock['published_counts'][12]),(1007,1013))
        self.assertEqual(clock['publication_proofs'][11],(9293,'2026-06-03 13:05:00',True))
        self.assertEqual(clock['publication_proofs'][12],(9268,'2026-06-03 13:35:00',True))
        self.assertEqual((role['units'][11][-1],role['units'][12][-1]),(1017,1017))
        self.assertEqual((clock['local_counts'][7],clock['published_counts'][7]),(624,655))
        self.assertEqual((clock['local_proofs'][7],clock['publication_proofs'][7]),
                         ((9474,'2026-05-22 13:50:00',True),(9474,'2026-05-22 13:50:00',False)))
        for count,size,complete in ((624,6,1),(654,6,1),(655,8,1),(1007,12,2),(1012,12,2),(1013,13,3)):
            visible=m3_xd_parts(dict(units=units),count)
            moves=chan.same_level_decompose(visible)
            self.assertEqual((len(visible),sum(m.complete for m in moves)),(size,complete))
            if count==1007:
                self.assertEqual((moves[-1].seg_start,moves[-1].seg_end,moves[-1].kind,moves[-1].complete),
                                 (9,11,'consolidation',False))
        self.assertLess(gap_revision_time(case,1007),gap_revision_time(case,1013))

    def test_current_batches_freeze_ten_f1_at_actual_proof_prices_and_leave_f2_open(self):
        case,units,clock=self._data()
        role=M3_Y1_JOINED_ROLE_AUDIT
        counts=sorted({2793}|{n for at in clock['local_counts']+clock['published_counts'] for n in (at-1,at)})
        types,first=[],{}
        key='Y1joined1-current:'+clock['certificate_sha256']
        for count in counts:
            visible=[u for u in units if u['confirmed_raw_count']<=count]
            moves=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
            specs=[s for s in role['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
            self.assertEqual([m3_xd_shape(m) for m in moves],[m3_xd_expected(units,s) for s in specs])
            for move in moves:
                if move.seg_start not in first:
                    first[move.seg_start]=count
                    types.append(m3_xd_type(key,move,visible,gap_revision_time(case,count)))
            self.assertEqual(chan.confirm_level_up(types,gap_revision_time(case,count),'F2'),[])
        self.assertEqual([first[s[0]] for s in role['f1']],list(clock['f1_first_counts']))
        self.assertEqual([len(t.evidence_ids) for t in types],list(clock['f1_evidence_counts']))
        self.assertEqual(types,self._types(case,units,moves,clock))
        self.assertEqual(types[2].confirmed_dt,gap_revision_time(case,1013))
        self.assertNotEqual(types[2].confirmed_dt,gap_revision_time(case,1007))
        self.assertNotEqual(types[2].confirmed_dt,gap_revision_time(case,1017))
        records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),
                      high_ticks=round(t.high*1000)) for t in types]
        self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],
                         [m3_xd_expected(records,s) for s in role['f2']])

    def test_late_second_proof94_version_keeps_f1_pending_and_future_prices_unread(self):
        case,units,clock=self._data()
        role=M3_Y1_JOINED_ROLE_AUDIT
        arrivals=[gap_revision_time(case,n) for n in clock['published_counts']]
        now=arrivals[12]
        late=now+timedelta(days=1)
        delayed=list(arrivals)
        delayed[12]=late
        for i in range(13,len(delayed)):
            delayed[i]=max(delayed[i],delayed[i-1])
        self.assertEqual(delayed[11],arrivals[11])
        for observed,ready in ((now-timedelta(microseconds=1),False),(now,False),
                               (late-timedelta(microseconds=1),False),(late,True)):
            size=next((i for i,at in enumerate(delayed) if at>observed),len(delayed))
            moves=chan.same_level_decompose(m3_xd_parts(dict(units=units[:size]),2793))
            target=next((m for m in moves if m.seg_start==9 and m.complete),None)
            self.assertEqual(target is not None,ready)
            if ready:
                frozen=m3_xd_type('Y1current:late-proof94-version2',target,units[:size],observed)
                self.assertEqual(frozen.confirmed_dt,late)
                self.assertGreater(frozen.confirmed_dt,gap_revision_time(case,1013))
        moves=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),2793)) if m.complete]
        types=self._types(case,units,moves,clock)
        cutoff=gap_revision_time(case,clock['f1_first_counts'][-1])
        bars=m3_xd_rows(case)
        for row in bars[clock['f1_first_counts'][-1]:]:
            row.pop('open')
            row.update(high=float('nan'),low=-999,close=99999)
        supplied=types+[types[-1]._replace(move_id='future',confirmed_dt=cutoff+timedelta(days=1),
                                         start_price=float('nan'))]
        strict=chan.scan_strict_divergence(supplied,cutoff,'F2')
        self.assertEqual((strict.results,strict.completed_types),((),0))
        self.assertEqual([reason for _,reason in strict.skipped],[role['strict_tail_skip']])
        first=chan.scan_first_points(supplied,bars,cutoff,'F2')
        self.assertEqual((first.points,first.exclusions,first.completed_types),([],(),0))
        chain=chan.analyze_point_chain(supplied,bars,cutoff,'F2')
        self.assertEqual((chain.first_points,chain.contexts,chain.second_points,
                          chain.third_points,chain.formations,chain.unresolved_move_ids),
                         ([],[],[],[],[],()))


if __name__ == '__main__':
    unittest.main()
