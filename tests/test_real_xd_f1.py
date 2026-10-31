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


# 课20三段全程区间角色；不沿用旧Zn简化式或已完成严格趋势标签。
M3_Y1_HEAD_ROLE_AUDIT = {'certificate_sha256': '91e2e0f58e1fdbda3ff9868016d85d03a2f37c55a458673ee22b4e4be02928c0',
 'fixed_role_certificate_sha256': 'ee58a32f2af125706a60a384624854de3777117cbd131e42ea951b32b4b17d3d',
 'current_clock_certificate_sha256': 'c7f542460f4019da02ee93d8945504162f1faf5821f3b32a79cce7eef34e8dd0',
 'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
 'scope': 'given_seed1_head_roles_not_complete_strict_trend',
 'roles': {'A': {'zn': (0, 2, 4),
                 'zd': 9714,
                 'zg': 9906,
                 'dd': 9702,
                 'gg': 9933,
                 'closed_by': 6,
                 'core_basis': 'three_units'},
           'B': {'zn': (6, 8),
                 'zd': 9445,
                 'zg': 9540,
                 'dd': 9332,
                 'gg': 9543,
                 'closed_by': 10,
                 'core_basis': 'three_units'},
           'C': {'zn': (10, 12, 14),
                 'zd': 9266,
                 'zg': 9414,
                 'dd': 9108,
                 'gg': 9414,
                 'closed_by': 16,
                 'core_basis': 'three_units'},
           'a': None,
           'b': {'unit': 5},
           'c': {'unit': 9, 'outcome': 'departed'},
           'proof': None,
           'merge': {'pair': ['B', 'C'], 'branch': 'below', 'determined': True},
           'gap_ticks': 159},
 'ledger': {'current': (('A_open', 2, 317),
                        ('A_zn_extend', 4, 377),
                        ('b_fixed', 5, 542),
                        ('A_closed', 6, 655),
                        ('B_open', 8, 836),
                        ('c_fixed', 9, 907),
                        ('c_departed', 9, 907),
                        ('B_closed', 10, 907),
                        ('C_open', 12, 1013),
                        ('C_zn_extend', 14, 1084),
                        ('C_closed', 16, 1277),
                        ('merge_determined', 16, 1277)),
            'fixed': (('A_open', 2, 323),
                      ('A_zn_extend', 4, 381),
                      ('b_fixed', 5, 557),
                      ('A_closed', 6, 661),
                      ('B_open', 8, 840),
                      ('c_fixed', 9, 946),
                      ('c_departed', 9, 946),
                      ('B_closed', 10, 946),
                      ('C_open', 12, 1017),
                      ('C_zn_extend', 14, 1115),
                      ('C_closed', 16, 1296),
                      ('merge_determined', 16, 1296))},
 'pair_B_core': (9441, 9540),
 'return_gap_ticks': 31,
 'BC_wave_overlap_ticks': 82,
 'prior_low_ticks': 9332,
 'c_low_ticks': 9108}


class TestY1HeadThreeUnitRoles(unittest.TestCase):
    """给定Y1头部角色的全程交集、回核缺口和两合同首达。"""

    @staticmethod
    def _data():
        case,units=gap_revision_input(M3_Y1_JOINED_ROLE_AUDIT)
        audit=M3_Y1_HEAD_ROLE_AUDIT
        if (audit['fixed_role_certificate_sha256']!=M3_Y1_JOINED_ROLE_AUDIT['certificate_sha256'] or
                audit['current_clock_certificate_sha256']!=M3_Y1_CURRENT_CLOCK_AUDIT['certificate_sha256']):
            raise AssertionError('角色须绑定组成和活动时钟版本')
        return case,units,audit

    def test_general_three_unit_core_keeps_internal_low_and_mirrored_middle_bound(self):
        _,units,audit=self._data()
        parts=m3_xd_parts(dict(units=units),2793)
        for name in ('A','B','C'):
            spec=audit['roles'][name]
            i=spec['zn'][0]
            center=chan.find_zs(parts[i:i+3])[0]
            self.assertEqual((round(center.zd*1000),round(center.zg*1000)),(spec['zd'],spec['zg']))
        self.assertEqual((units[8]['low_ticks'],units[8]['start_ticks']),(9441,9445))
        self.assertEqual(audit['pair_B_core'],(9441,9540))
        for middle_low,expected in ((9440,9441),(9441,9441),(9442,9442),(9445,9445)):
            for mirror in (False,True):
                triple=[]
                for i in (6,7,8):
                    lo=middle_low if i==7 else units[i]['low_ticks']
                    hi=units[i]['high_ticks']
                    triple.append(SimpleNamespace(low=(20000-hi if mirror else lo)/1000.,
                                  high=(20000-lo if mirror else hi)/1000.,
                                  direction=('down' if units[i]['direction']=='up' else 'up') if mirror else units[i]['direction'],
                                  start_dt=parts[i].start_dt,end_dt=parts[i].end_dt))
                actual=chan.find_zs(triple)[0]
                core=(20000-9540,20000-expected) if mirror else (expected,9540)
                self.assertEqual((round(actual.zd*1000),round(actual.zg*1000)),core)

    def test_new_c_has_new_low_but_immediate_unit10_never_returns_to_B(self):
        _,units,audit=self._data()
        roles=audit['roles'];B=roles['B'];C=roles['C'];c=roles['c']['unit']
        self.assertEqual((roles['b']['unit'],c),(5,9))
        self.assertEqual((min(u['low_ticks'] for u in units[:c]),units[c]['low_ticks']),
                         (audit['prior_low_ticks'],audit['c_low_ticks']))
        self.assertLess(units[c]['low_ticks'],audit['prior_low_ticks'])
        self.assertEqual(B['zd']-units[c+1]['high_ticks'],audit['return_gap_ticks'])
        self.assertEqual([i for i in range(c+1,len(units)) if units[i]['low_ticks']<=B['zg'] and
                          units[i]['high_ticks']>=B['zd']],[])
        self.assertIsNone(roles['proof'])
        self.assertEqual((C['zg']<B['zd'],C['gg']-B['dd']),(True,audit['BC_wave_overlap_ticks']))
        def center(spec):
            return chan.ZS(spec['zd']/1000.,spec['zg']/1000.,spec['gg']/1000.,spec['dd']/1000.,
                           None,None,'up',len(spec['zn'])*2-1)
        self.assertEqual(chan.zs_relation(center(B),center(C)),'expand')
        # 历史旧c9没有创新低的结论不迁移到新c9；新c的回核/完成仍缺。
        case,_,_=self._data()
        self.assertEqual(case['first_point']['reason'],'no_new_extreme')

    def test_head_role_formations_wait_for_their_actual_current_and_fixed_batches(self):
        case,units,audit=self._data()
        for contract in ('current','fixed'):
            counts=(M3_Y1_CURRENT_CLOCK_AUDIT['published_counts'] if contract=='current'
                    else tuple(u['confirmed_raw_count'] for u in units))
            supplied=[dict(u,confirmed_raw_count=at) for u,at in zip(units,counts)]
            for name in ('A','B','C'):
                spec=audit['roles'][name];i=spec['zn'][0];formed=i+2;at=counts[formed]
                for observed,ready in ((at-1,False),(at,True)):
                    parts=m3_xd_parts(dict(units=supplied),observed)
                    centers=chan.find_zs(parts[i:i+3])
                    self.assertEqual(bool(centers),ready,(contract,name,observed))
                    if ready:
                        self.assertEqual((round(centers[0].zd*1000),round(centers[0].zg*1000)),
                                         (spec['zd'],spec['zg']))
            actual=tuple((event,index,counts[index]) for event,index,_ in audit['ledger'][contract])
            self.assertEqual(actual,audit['ledger'][contract])
        self.assertEqual((audit['ledger']['current'][-1][-1],audit['ledger']['fixed'][-1][-1]),(1277,1296))
        self.assertLess(gap_revision_time(case,1277),gap_revision_time(case,1296))


# 自动递归吸收延伸的独立有限角色；与同级切分10个F1的合同分开。
M3_Y1_RECURSIVE_CONSUMERS_AUDIT = {'certificate_sha256': 'fc3b03ca135bd4b8f11f8716a2227dd37ea2c1e6caeb21b2db1bd1c36eeea3ee',
 'source_sha256': '745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
 'fixed_role_certificate_sha256': 'ee58a32f2af125706a60a384624854de3777117cbd131e42ea951b32b4b17d3d',
 'current_clock_certificate_sha256': 'c7f542460f4019da02ee93d8945504162f1faf5821f3b32a79cce7eef34e8dd0',
 'head_role_certificate_sha256': '91e2e0f58e1fdbda3ff9868016d85d03a2f37c55a458673ee22b4e4be02928c0',
 'scope': 'given39_XD_recursive_consumers_not_theory_F1_proof',
 'centers': ((0, 2, 5, 9714, 9906),
             (6, 8, 9, 9445, 9540),
             (10, 12, 15, 9266, 9414),
             (16, 18, 21, 8937, 8988),
             (23, 25, 30, 8282, 8329),
             (31, 33, 35, 8551, 8605)),
 'completed': ((0,
                30,
                'down',
                'down',
                (0, 6, 10, 16, 23),
                ((9714, 9906), (9445, 9540), (9266, 9414), (8937, 8988), (8282, 8329)),
                33),
               (31, 37, 'consolidation', None, (31,), ((8551, 8605),), 38)),
 'tail': (38, 38, 'incomplete', None, (), (), None),
 'open_skip_sizes': {'not_two_separated_centers': (1, 2, 3, 4, 5, 6, 7, 8, 34, 35, 36, 37, 38, 39),
                     'no_compare_legs': (9, 13, 15, 19, 21, 27, 29, 31),
                     'center_waves_overlap': (14, 16, 17, 18, 28, 30, 32, 33),
                     'no_comparable_center_tail': (26,)},
 'candidates': ((10, (5,), (9,), (9445, 9540), True, None),
                (11, (5,), (9, 10), (9445, 9540), True, True),
                (12, (5,), (9, 10, 11), (9445, 9540), True, True),
                (20, (15,), (19,), (8937, 8988), None, None),
                (22, (15,), (21,), (8937, 8988), None, None),
                (23, (15,), (21, 22), (8937, 8988), None, True),
                (24, (15,), (21, 22, 23), (8937, 8988), True, True),
                (25, (15,), (21, 22, 23, 24), (8937, 8988), True, True)),
 'arrivals': {'current': {'completed_raw': (2276, 2788),
                          'evidence_sizes': (34, 39),
                          'candidate_raw': ((907, 11), (1007, 12), (1513, 20), (1612, 22), (1642, 23), (1761, 25))},
              'fixed': {'completed_raw': (2279, 2793),
                        'evidence_sizes': (34, 39),
                        'candidate_raw': ((946, 11), (1520, 20), (1624, 22), (1675, 23), (1773, 25))}},
 'completed_reference': (21, 22),
 'completed_leave': (),
 'final_strict_skipped': ('no_compare_legs', 'not_trend', 'not_two_separated_centers'),
 'final_first_exclusions': ('no_directional_compare_legs', 'not_trend')}


class TestY1RecursiveConsumers(unittest.TestCase):
    """给定XD上的自动递归消费；有限单元前缀与真实同批到达分别核对。"""

    @staticmethod
    def _data(contract):
        case,units=gap_revision_input(M3_Y1_JOINED_ROLE_AUDIT)
        audit=M3_Y1_RECURSIVE_CONSUMERS_AUDIT
        if (audit['fixed_role_certificate_sha256']!=M3_Y1_JOINED_ROLE_AUDIT['certificate_sha256'] or
                audit['current_clock_certificate_sha256']!=M3_Y1_CURRENT_CLOCK_AUDIT['certificate_sha256'] or
                audit['head_role_certificate_sha256']!=M3_Y1_HEAD_ROLE_AUDIT['certificate_sha256']):
            raise AssertionError('自动消费者须绑定已声明组成、活动时钟与头部角色')
        counts=(M3_Y1_CURRENT_CLOCK_AUDIT['published_counts'] if contract=='current'
                else tuple(u['confirmed_raw_count'] for u in units))
        key='Y1recursive:'+contract+':'+audit['certificate_sha256']
        given=[chan.ConfirmedMove(key+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
                                 u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
                                 gap_revision_time(case,counts[i])) for i,u in enumerate(units)]
        return case,units,audit,given,counts

    def _strict(self,given,now):
        def unavailable(reference,leave):
            self.fail('结构未齐或开放候选不得执行力度方法')
        return chan.scan_strict_divergence(given,now,'recursive-F1',unavailable,'structural_guard')

    def _check(self,scan,audit,size):
        candidate=next((c for c in audit['candidates'] if c[0]==size),None)
        expected=[]
        if size>=34:expected.append('no_compare_legs')
        if size==39:expected.append('not_trend')
        if candidate is None:
            expected.append(next(reason for reason,counts in audit['open_skip_sizes'].items() if size in counts))
        self.assertEqual([reason for _,reason in scan.skipped],expected)
        self.assertEqual((scan.completed_types,scan.open_tail),(sum(s[-1]<size for s in audit['completed']),True))
        self.assertEqual(len(scan.results),int(candidate is not None))
        if candidate:
            result=scan.results[0];_,reference,leave,core,new,third=candidate
            self.assertEqual((result.status,result.reason),('candidate','trend_open'))
            self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in result.reference_ids),reference)
            self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in result.leave_ids),leave)
            self.assertEqual(tuple(round(v*1000) for v in result.center_range),core)
            self.assertEqual(dict(result.conditions),dict(trend=None,separated_centers=True,
                                                        new_extreme=new,leave_third_point=third))
            self.assertIsNone(result.force_method)

    def test_declared_unit_prefixes_keep_recursive_composition_and_open_candidates_separate(self):
        case,units,audit,given,_=self._data('current')
        identity=None
        for size in range(1,40):
            prefix=given[:size];now=prefix[-1].confirmed_dt
            scan=self._strict(prefix,now);self._check(scan,audit,size)
            if scan.results:
                identity=identity or scan.results[0].divergence_id
                self.assertEqual(scan.results[0].divergence_id,identity)
            specs=[s for s in audit['completed'] if s[-1]<size]
            if size<3:tail=(0,size-1,'incomplete',None,(),(),None)
            elif size<34:
                cs=[c for c in audit['centers'][:5] if c[1]<size]
                direction='down' if len(cs)>1 else None
                tail=(0,size-1,'down' if direction else 'consolidation',direction,
                      tuple(c[0] for c in cs),tuple((c[3],c[4]) for c in cs),None)
            elif size<39:tail=(31,size-1,'consolidation',None,(31,),((8551,8605),),None)
            else:tail=audit['tail']
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(prefix)],
                             [m3_xd_expected(units,s) for s in specs+[tail]])
        # 这些有限单元前缀不等于实际raw观察；同批发布会跳过部分size。
        self.assertEqual(tuple(c[0] for c in audit['candidates']),(10,11,12,20,22,23,24,25))
        self.assertEqual(len(M3_Y1_JOINED_ROLE_AUDIT['f1']),10)
        self.assertEqual((len(audit['completed']),audit['completed'][0][1]),(2,30))

    def test_actual_batches_freeze_two_recursive_types_and_never_create_point_anchors(self):
        for contract in ('current','fixed'):
            case,_,audit,given,counts=self._data(contract);rows=m3_xd_rows(case)
            candidates=[]
            for count in sorted(set(counts)):
                now=gap_revision_time(case,count);size=sum(at<=count for at in counts)
                scan=self._strict(given,now);self._check(scan,audit,size)
                if scan.results:candidates.append((count,size))
                first=chan.scan_first_points(given,rows,now,'recursive-F1')
                self.assertEqual(first.points,[])
                expected=(() if size<34 else ('no_directional_compare_legs',) if size<39
                          else audit['final_first_exclusions'])
                self.assertEqual(tuple(reason for _,reason in first.exclusions),expected)
                self.assertFalse(any(chan.analyze_point_chain(given,rows,now,'recursive-F1')))
            self.assertEqual(tuple(candidates),audit['arrivals'][contract]['candidate_raw'])
            done=chan.confirm_level_up(given,given[-1].confirmed_dt,'recursive-F1')
            self.assertEqual([len(t.unit_ids) for t in done],[31,7])
            self.assertEqual(tuple(len(t.evidence_ids) for t in done),audit['arrivals'][contract]['evidence_sizes'])
            self.assertEqual([t.confirmed_dt for t in done],
                             [gap_revision_time(case,n) for n in audit['arrivals'][contract]['completed_raw']])
            first_time=done[0].confirmed_dt
            self.assertEqual(chan.confirm_level_up(given,first_time,'recursive-F1'),[done[0]])
            self.assertEqual(tuple(reason for _,reason in self._strict(given,given[-1].confirmed_dt).skipped),
                             audit['final_strict_skipped'])

    def test_reverse_center_and_last_return_confirm_only_at_actual_late_arrival(self):
        for contract in ('current','fixed'):
            case,_,audit,given,counts=self._data(contract)
            for proof in (33,38):
                late=given[proof].confirmed_dt+timedelta(days=1)
                delayed=list(given);delayed[proof]=given[proof]._replace(confirmed_dt=late)
                for i in range(proof+1,len(given)):
                    delayed[i]=given[i]._replace(confirmed_dt=max(given[i].confirmed_dt,delayed[i-1].confirmed_dt))
                earlier=chan.confirm_level_up(delayed,late-timedelta(microseconds=1),'recursive-F1')
                after=chan.confirm_level_up(delayed,late,'recursive-F1')
                self.assertEqual((len(earlier),len(after)),((0,1) if proof==33 else (1,2)))
                self.assertEqual(after[-1].confirmed_dt,late)
                self.assertLess(after[-1].end_dt,after[-1].confirmed_dt)
                if earlier:self.assertEqual(after[0],earlier[0])
                self.assertEqual(len(after[-1].evidence_ids),34 if proof==33 else 39)
            cutoff=gap_revision_time(case,counts[-1]);rows=m3_xd_rows(case)
            for row in rows[counts[-1]:]:
                row.pop('open');row.update(high=float('nan'),low=-999,close=99999)
            future=given[-1]._replace(move_id=None,level=None,start_price=float('nan'),confirmed_dt=cutoff+timedelta(days=1))
            first=chan.scan_first_points(given+[future],rows,cutoff,'recursive-F1')
            self.assertEqual((first.points,tuple(r for _,r in first.exclusions)),([],audit['final_first_exclusions']))
            self.assertFalse(any(chan.analyze_point_chain(given+[future],rows,cutoff,'recursive-F1')))
            self.assertEqual(len(self._strict(given+[future],cutoff).results),0)


# 给定seed16的14段衔接；111资格仅限此已声明祖先路径，旧全窗表保持。
M3_M2_JOINED_ROLE_AUDIT = {'certificate_sha256': '7f592db0a28e4f6e120c28addd0e6d9ee661fdcb9b182ead07ed146e6a99efdc',
 'fixture': 'real_third_point_xd_margin0.json',
 'id': '512880-5m-20260201-20260724',
 'fixture_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'head_certificate_sha256': '4692e046fbd8c5ae9293868dc8e8126b3e314e3e250cbb1015cd38698fb93d22',
 'seed': 16,
 'raw_window': (372, 2476),
 'events': ((16, 34, 1, 37),
            (35, 37, 1, 51),
            (38, 48, 1, 51),
            (49, 55, 1, 58),
            (56, 64, 2, 72),
            (65, 67, 1, 70),
            (68, 74, 1, 77),
            (75, 77, 1, 80),
            (78, 86, 1, 89),
            (87, 89, 1, 92),
            (90, 92, 1, 103),
            (93, 103, 1, 106),
            (104, 110, 1, 113),
            (111, 113, 1, 116)),
 'units': (('down', '2026-02-10 10:10:00', '2026-03-06 09:35:00', 1200, 1113, 1113, 1200, 1, 37, 940, 940),
           ('up', '2026-03-06 09:35:00', '2026-03-06 14:20:00', 1113, 1135, 1113, 1135, 1, 51, 1183, 1183),
           ('down', '2026-03-06 14:20:00', '2026-03-13 09:55:00', 1135, 1112, 1105, 1135, 1, 51, 1183, 1183),
           ('up', '2026-03-13 09:55:00', '2026-03-17 10:35:00', 1112, 1140, 1100, 1140, 1, 58, 1349, 1349),
           ('down', '2026-03-17 10:35:00', '2026-03-23 14:55:00', 1140, 1031, 1031, 1140, 2, 72, 1648, 1648),
           ('up', '2026-03-23 14:55:00', '2026-03-25 10:35:00', 1031, 1060, 1031, 1060, 1, 70, 1618, 1648),
           ('down', '2026-03-25 10:35:00', '2026-03-30 10:00:00', 1060, 1025, 1025, 1060, 1, 77, 1745, 1745),
           ('up', '2026-03-30 10:00:00', '2026-03-31 09:45:00', 1025, 1049, 1025, 1049, 1, 80, 1775, 1775),
           ('down', '2026-03-31 09:45:00', '2026-04-07 13:30:00', 1049, 1010, 1010, 1049, 1, 89, 2003, 2003),
           ('up', '2026-04-07 13:30:00', '2026-04-08 13:30:00', 1010, 1056, 1010, 1056, 1, 92, 2063, 2063),
           ('down', '2026-04-08 13:30:00', '2026-04-09 14:55:00', 1056, 1029, 1029, 1056, 1, 103, 2221, 2221),
           ('up', '2026-04-09 14:55:00', '2026-04-15 09:35:00', 1029, 1086, 1029, 1091, 1, 106, 2261, 2261),
           ('down', '2026-04-15 09:35:00', '2026-04-17 10:20:00', 1086, 1070, 1070, 1086, 1, 113, 2365, 2365),
           ('up', '2026-04-17 10:20:00', '2026-04-20 09:40:00', 1070, 1079, 1070, 1079, 1, 116, 2437, 2437)),
 'current_local_counts': (924, 1156, 1156, 1329, 1639, 1582, 1720, 1764, 1992, 2040, 2208, 2254, 2356, 2398),
 'current_counts': (924, 1156, 1156, 1329, 1639, 1639, 1720, 1764, 1992, 2040, 2208, 2254, 2356, 2398),
 'local_proofs': {'current': ((1135, '2026-03-06 14:20:00', True),
                              (1125, '2026-03-13 13:15:00', True),
                              (1125, '2026-03-13 13:15:00', True),
                              (1104, '2026-03-19 09:50:00', True),
                              (1035, '2026-03-27 11:10:00', True),
                              (1048, '2026-03-26 10:30:00', True),
                              (1049, '2026-03-31 09:45:00', True),
                              (1027, '2026-03-31 14:55:00', True),
                              (1056, '2026-04-08 13:30:00', True),
                              (1031, '2026-04-09 13:25:00', True),
                              (1086, '2026-04-15 09:35:00', True),
                              (1072, '2026-04-15 14:55:00', True),
                              (1079, '2026-04-20 09:40:00', True),
                              (1072, '2026-04-20 14:40:00', True)),
                  'fixed': ((1135, '2026-03-06 14:20:00', False),
                            (1125, '2026-03-13 13:15:00', False),
                            (1125, '2026-03-13 13:15:00', False),
                            (1101, '2026-03-19 10:40:00', False),
                            (1035, '2026-03-27 11:10:00', False),
                            (1033, '2026-03-26 14:25:00', False),
                            (1049, '2026-03-31 09:45:00', False),
                            (1027, '2026-03-31 14:55:00', False),
                            (1056, '2026-04-08 13:30:00', False),
                            (1029, '2026-04-09 14:55:00', False),
                            (1086, '2026-04-15 09:35:00', False),
                            (1072, '2026-04-15 14:55:00', False),
                            (1079, '2026-04-20 09:40:00', False),
                            (1064, '2026-04-21 10:30:00', False))},
 'publication_proofs': {'current': ((1135, '2026-03-06 14:20:00', True),
                                    (1125, '2026-03-13 13:15:00', True),
                                    (1125, '2026-03-13 13:15:00', True),
                                    (1104, '2026-03-19 09:50:00', True),
                                    (1035, '2026-03-27 11:10:00', True),
                                    (1033, '2026-03-26 14:25:00', False),
                                    (1049, '2026-03-31 09:45:00', True),
                                    (1027, '2026-03-31 14:55:00', True),
                                    (1056, '2026-04-08 13:30:00', True),
                                    (1031, '2026-04-09 13:25:00', True),
                                    (1086, '2026-04-15 09:35:00', True),
                                    (1072, '2026-04-15 14:55:00', True),
                                    (1079, '2026-04-20 09:40:00', True),
                                    (1072, '2026-04-20 14:40:00', True)),
                        'fixed': ((1135, '2026-03-06 14:20:00', False),
                                  (1125, '2026-03-13 13:15:00', False),
                                  (1125, '2026-03-13 13:15:00', False),
                                  (1101, '2026-03-19 10:40:00', False),
                                  (1035, '2026-03-27 11:10:00', False),
                                  (1033, '2026-03-26 14:25:00', False),
                                  (1049, '2026-03-31 09:45:00', False),
                                  (1027, '2026-03-31 14:55:00', False),
                                  (1056, '2026-04-08 13:30:00', False),
                                  (1029, '2026-04-09 14:55:00', False),
                                  (1086, '2026-04-15 09:35:00', False),
                                  (1072, '2026-04-15 14:55:00', False),
                                  (1079, '2026-04-20 09:40:00', False),
                                  (1064, '2026-04-21 10:30:00', False))},
 'reactions': ((39, 41, 2, 51), (94, 96, 1, 103)),
 'successors': ((42, 48, 1, 51), (97, 103, 1, 106)),
 'earlier_revoked': ((68, 71, 74, 'gap'),
                     (78, 81, 82, 'direct'),
                     (78, 83, 84, 'direct'),
                     (78, 85, 86, 'gap'),
                     (104, 107, 110, 'direct')),
 'f1': ((0, 2, 'consolidation', None, (0,), ((1113, 1135),), 3),
        (3, 6, 'consolidation', 'up', (4,), ((1031, 1060),), 7),
        (7, 9, 'consolidation', None, (7,), ((1025, 1049),), 10)),
 'tail': (10, 13, 'consolidation', 'down', (11,), ((1070, 1079),), None),
 'f1_first_counts': {'current': (1329, 1764, 2208), 'fixed': (1349, 1775, 2221)},
 'f1_evidence_counts': (4, 8, 11),
 'natural111_qualified_in_seed16_chain': True,
 'natural111_predecessor': (104, 110, 1, 113),
 'complete_f2': 0,
 'source_origin_bridge_proven': False}


class TestM2JoinedSeed16(unittest.TestCase):
    """修订近期祖先链接通111资格；不将声明单位冒充已合入的生产输出。"""

    @staticmethod
    def _data(contract):
        audit=M3_M2_JOINED_ROLE_AUDIT
        head=M3_CONDITIONAL_F1_ADMISSION_AUDIT['M2_recent16']
        if audit['head_certificate_sha256']!=head['certificate_sha256']:
            raise AssertionError('M2衔接须绑定同一近期头部证书')
        case,units=gap_revision_input(audit)
        if contract=='current':
            for i,u in enumerate(units):
                u['local_raw_count']=audit['current_local_counts'][i]
                u['confirmed_raw_count']=audit['current_counts'][i]
        return case,units,audit

    def test_joined_fourteen_keeps_natural87_bridge_and_qualified111_ancestry(self):
        _,units,audit=self._data('fixed')
        head=M3_CONDITIONAL_F1_ADMISSION_AUDIT['M2_recent16']
        self.assertEqual(audit['events'][:6],head['events'])
        self.assertEqual(tuple(tuple(u[:9]) for u in audit['units'][:6]),head['units'])
        self.assertEqual(audit['events'][9:],((87,89,1,92),(90,92,1,103),(93,103,1,106),
                                             (104,110,1,113),(111,113,1,116)))
        self.assertTrue(audit['natural111_qualified_in_seed16_chain'])
        self.assertEqual(audit['natural111_predecessor'],audit['events'][12])
        for a,b in zip(audit['events'],audit['events'][1:]):self.assertEqual(a[1]+1,b[0])
        self.assertNotIn((93,97,1,102),audit['events'])
        self.assertNotIn((108,110,1,113),audit['events'])
        self.assertEqual((units[11]['start_ticks'],units[11]['end_ticks'],units[11]['high_ticks']),
                         (1029,1086,1091))
        self.assertEqual((units[12]['start_ticks'],units[12]['end_ticks']),(1086,1070))
        self.assertEqual((audit['publication_proofs']['current'][13],audit['publication_proofs']['fixed'][13]),
                         ((1072,'2026-04-20 14:40:00',True),(1064,'2026-04-21 10:30:00',False)))

    def test_three_f1_freeze_actual_batches_while_fourth_tail_and_f2_remain_pending(self):
        for contract in ('current','fixed'):
            case,units,audit=self._data(contract);first={};types=[]
            counts=sorted({2476}|{n for u in units for at in (u['local_raw_count'],u['confirmed_raw_count'])
                                 for n in (at-1,at)})
            for count in counts:
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                moves=chan.same_level_decompose(m3_xd_parts(dict(units=units),count))
                complete=[m for m in moves if m.complete]
                expected=[s for s in audit['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual([m3_xd_shape(m) for m in complete],[m3_xd_expected(units,s) for s in expected])
                for move in complete:
                    if move.seg_start not in first:
                        first[move.seg_start]=count
                        types.append(m3_xd_type('M2joined16:'+contract+':'+audit['certificate_sha256'],
                                                 move,visible,gap_revision_time(case,count)))
                self.assertEqual(chan.confirm_level_up(types,gap_revision_time(case,count),'F2'),[])
            self.assertEqual(tuple(first[s[0]] for s in audit['f1']),audit['f1_first_counts'][contract])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),audit['f1_evidence_counts'])
            self.assertEqual(m3_xd_shape(moves[-1]),m3_xd_expected(units,audit['tail']))
            # 第二F1进入方向up与净下跌分别保留，组成低1025不取旧F1低1031。
            self.assertEqual((types[1].kind,types[1].direction,round(types[1].low*1000)),
                             ('consolidation','up',1025))
            self.assertLess(types[1].end_price,types[1].start_price)
            now=gap_revision_time(case,2476)
            strict=chan.scan_strict_divergence(types,now,'F2')
            self.assertEqual((strict.results,strict.completed_types),((),0))
            self.assertEqual([reason for _,reason in strict.skipped],['not_two_separated_centers'])
            points=chan.scan_first_points(types,m3_xd_rows(case),now,'F2')
            self.assertEqual((points.points,points.exclusions,points.completed_types),([],(),0))
            self.assertFalse(any(chan.analyze_point_chain(types,m3_xd_rows(case),now,'F2')))

    def test_late_natural_bridge_delays_f1_without_rewriting_prior_completions(self):
        case,units,audit=self._data('current')
        arrivals=[gap_revision_time(case,u['confirmed_raw_count']) for u in units]
        late=arrivals[10]+timedelta(days=1);delayed=list(arrivals);delayed[10]=late
        for i in range(11,14):delayed[i]=max(arrivals[i],delayed[i-1])
        frozen=[]
        for observed in (late-timedelta(microseconds=1),late):
            size=next((i for i,at in enumerate(delayed) if at>observed),14)
            moves=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:size]),2476)) if m.complete]
            self.assertEqual(len(moves),2 if observed<late else 3)
            built=[]
            for move in moves:
                proof=next(s[-1] for s in audit['f1'] if s[0]==move.seg_start)
                known=max(delayed[:proof+1]);width=sum(at<=known for at in delayed)
                built.append(m3_xd_type('M2joined16:late-bridge',move,units[:width],known))
            if frozen:self.assertEqual(built[:2],frozen)
            frozen=built
            if observed==late:
                self.assertEqual(built[-1].confirmed_dt,late)
                self.assertEqual(len(built[-1].evidence_ids),size)
        before=chan.same_level_decompose(m3_xd_parts(dict(units=units[:13]),2476))[-1]
        after=chan.same_level_decompose(m3_xd_parts(dict(units=units),2476))[-1]
        self.assertEqual((before.kind,after.kind,after.complete),('incomplete','consolidation',False))
        cutoff=arrivals[10];rows=m3_xd_rows(case)
        for row in rows[audit['current_counts'][10]:]:
            row.pop('open');row.update(high=float('nan'),low=-999,close=99999)
        prior=frozen[:2]
        future=frozen[-1]._replace(move_id='future',start_price=float('nan'),confirmed_dt=cutoff+timedelta(days=3))
        self.assertFalse(any(chan.analyze_point_chain(prior+[future],rows,cutoff,'F2')))


# 给定seed16保留后缀；current自然S311可见，fixed不得借用未固定的BI322。
M3_M2_SUFFIX_ROLE_AUDIT = {'certificate_sha256': 'ee14d65c88a367594a37eeb28b31689bdb19fd88d28d1f01357e910bb4ca2e3a',
 'head_certificate_sha256': '7f592db0a28e4f6e120c28addd0e6d9ee661fdcb9b182ead07ed146e6a99efdc',
 'events': ((114, 122, 1, 125),
            (123, 125, 2, 131),
            (126, 128, 2, 136),
            (129, 133, 1, 136),
            (134, 138, 1, 141),
            (139, 143, 1, 146),
            (144, 160, 1, 163),
            (161, 163, 1, 172),
            (164, 174, 2, 180),
            (175, 177, 2, 197),
            (178, 180, 1, 189),
            (181, 189, 1, 194),
            (190, 200, 1, 203),
            (201, 227, 2, 241),
            (228, 238, 1, 255),
            (239, 257, 1, 260),
            (258, 262, 1, 265),
            (263, 267, 1, 270),
            (268, 290, 1, 293),
            (291, 293, 2, 305),
            (294, 302, 1, 305)),
 'units': (('down', '2026-04-20 09:40:00', '2026-04-24 10:05:00', 1079, 1050, 1050, 1085, 1, 125, 2660, 2660),
           ('up', '2026-04-24 10:05:00', '2026-04-28 10:10:00', 1050, 1082, 1050, 1082, 2, 131, 2759, 2759),
           ('down', '2026-04-28 10:10:00', '2026-04-29 09:35:00', 1082, 1065, 1065, 1082, 2, 136, 2872, 2872),
           ('up', '2026-04-29 09:35:00', '2026-05-06 10:25:00', 1065, 1100, 1065, 1100, 1, 136, 2872, 2872),
           ('down', '2026-05-06 10:25:00', '2026-05-11 09:45:00', 1100, 1073, 1073, 1100, 1, 141, 2994, 2994),
           ('up', '2026-05-11 09:45:00', '2026-05-12 11:10:00', 1073, 1111, 1073, 1111, 1, 146, 3077, 3077),
           ('down', '2026-05-12 11:10:00', '2026-05-19 11:15:00', 1111, 1039, 1039, 1111, 1, 163, 3362, 3362),
           ('up', '2026-05-19 11:15:00', '2026-05-21 10:15:00', 1039, 1092, 1039, 1092, 1, 172, 3563, 3563),
           ('down', '2026-05-21 10:15:00', '2026-05-28 13:25:00', 1092, 1015, 1015, 1092, 2, 180, 3681, 3681),
           ('up', '2026-05-28 13:25:00', '2026-05-29 09:55:00', 1015, 1048, 1015, 1048, 2, 197, 3956, 3956),
           ('down', '2026-05-29 09:55:00', '2026-06-01 09:35:00', 1048, 1025, 1025, 1048, 1, 189, 3811, 3956),
           ('up', '2026-06-01 09:35:00', '2026-06-03 11:15:00', 1025, 1044, 1025, 1044, 1, 194, 3928, 3956),
           ('down', '2026-06-03 11:15:00', '2026-06-09 09:55:00', 1044, 994, 994, 1044, 1, 203, 4016, 4016),
           ('up', '2026-06-09 09:55:00', '2026-06-23 10:00:00', 994, 1160, 994, 1160, 2, 241, 4563, 4563),
           ('down', '2026-06-23 10:00:00', '2026-06-25 09:50:00', 1160, 1100, 1100, 1160, 1, 255, 4727, 4727),
           ('up', '2026-06-25 09:50:00', '2026-07-01 13:30:00', 1100, 1191, 1100, 1191, 1, 260, 4774, 4774),
           ('down', '2026-07-01 13:30:00', '2026-07-03 10:15:00', 1191, 1139, 1139, 1191, 1, 265, 4848, 4848),
           ('up', '2026-07-03 10:15:00', '2026-07-06 09:35:00', 1139, 1177, 1139, 1177, 1, 270, 4894, 4894),
           ('down', '2026-07-06 09:35:00', '2026-07-14 11:30:00', 1177, 1085, 1085, 1177, 1, 293, 5235, 5235),
           ('up', '2026-07-14 11:30:00', '2026-07-15 13:55:00', 1085, 1139, 1085, 1139, 2, 305, 5364, 5364),
           ('down',
            '2026-07-15 13:55:00',
            '2026-07-17 13:50:00',
            1139,
            1094,
            1094,
            1139,
            1,
            305,
            5364,
            5364)),
 'current_tail_event': (303, 309, 1, 322),
 'current_tail_unit': ('up',
                       '2026-07-17 13:50:00',
                       '2026-07-21 09:55:00',
                       1094,
                       1131,
                       1094,
                       1131,
                       1,
                       322,
                       5564,
                       5564),
 'reaction': (165, 169, 1, 172),
 'successor': (170, 174, 2, 180),
 'tail_reaction': (311, 319, 1, 322),
 'local_counts': {'current': (2656,
                              2740,
                              2834,
                              2834,
                              2984,
                              3052,
                              3343,
                              3554,
                              3678,
                              3940,
                              3796,
                              3923,
                              4010,
                              4554,
                              4716,
                              4767,
                              4842,
                              4885,
                              5231,
                              5352,
                              5352,
                              5564),
                  'fixed': (2660,
                            2759,
                            2872,
                            2872,
                            2994,
                            3077,
                            3362,
                            3563,
                            3681,
                            3956,
                            3811,
                            3928,
                            4016,
                            4563,
                            4727,
                            4774,
                            4848,
                            4894,
                            5235,
                            5364,
                            5364)},
 'published_counts': {'current': (2656,
                                  2740,
                                  2834,
                                  2834,
                                  2984,
                                  3052,
                                  3343,
                                  3554,
                                  3678,
                                  3940,
                                  3940,
                                  3940,
                                  4010,
                                  4554,
                                  4716,
                                  4767,
                                  4842,
                                  4885,
                                  5231,
                                  5352,
                                  5352,
                                  5564),
                      'fixed': (2660,
                                2759,
                                2872,
                                2872,
                                2994,
                                3077,
                                3362,
                                3563,
                                3681,
                                3956,
                                3956,
                                3956,
                                4016,
                                4563,
                                4727,
                                4774,
                                4848,
                                4894,
                                5235,
                                5364,
                                5364)},
 'local_proofs': {'current': ((1082, '2026-04-28 10:10:00', True),
                              (1077, '2026-04-29 14:35:00', True),
                              (1089, '2026-05-06 14:15:00', True),
                              (1089, '2026-05-06 14:15:00', True),
                              (1104, '2026-05-11 14:30:00', True),
                              (1086, '2026-05-13 10:30:00', True),
                              (1092, '2026-05-21 10:15:00', True),
                              (1037, '2026-05-27 11:30:00', True),
                              (1025, '2026-06-01 09:35:00', True),
                              (1017, '2026-06-08 11:00:00', True),
                              (1044, '2026-06-03 11:15:00', True),
                              (1003, '2026-06-08 09:35:00', True),
                              (1005, '2026-06-09 14:15:00', True),
                              (1150, '2026-06-25 14:40:00', True),
                              (1170, '2026-07-01 10:20:00', True),
                              (1146, '2026-07-02 10:30:00', True),
                              (1159, '2026-07-03 14:10:00', True),
                              (1149, '2026-07-06 13:40:00', True),
                              (1139, '2026-07-15 13:55:00', True),
                              (1126, '2026-07-20 10:15:00', True),
                              (1126, '2026-07-20 10:15:00', True),
                              (1107, '2026-07-24 13:05:00', True)),
                  'fixed': ((1082, '2026-04-28 10:10:00', False),
                            (1095, '2026-04-30 10:00:00', False),
                            (1082, '2026-05-07 10:45:00', False),
                            (1082, '2026-05-07 10:45:00', False),
                            (1104, '2026-05-11 14:30:00', False),
                            (1084, '2026-05-13 11:15:00', False),
                            (1092, '2026-05-21 10:15:00', False),
                            (1037, '2026-05-27 11:30:00', False),
                            (1025, '2026-06-01 09:35:00', False),
                            (1017, '2026-06-08 11:00:00', False),
                            (1044, '2026-06-03 11:15:00', False),
                            (1003, '2026-06-08 09:35:00', False),
                            (1005, '2026-06-09 14:15:00', False),
                            (1150, '2026-06-25 14:40:00', False),
                            (1181, '2026-07-01 10:50:00', False),
                            (1146, '2026-07-02 10:30:00', False),
                            (1159, '2026-07-03 14:10:00', False),
                            (1149, '2026-07-06 13:40:00', False),
                            (1139, '2026-07-15 13:55:00', False),
                            (1126, '2026-07-20 10:15:00', False),
                            (1126, '2026-07-20 10:15:00', False))},
 'publication_proofs': {'current': ((1082, '2026-04-28 10:10:00', True),
                                    (1077, '2026-04-29 14:35:00', True),
                                    (1089, '2026-05-06 14:15:00', True),
                                    (1089, '2026-05-06 14:15:00', True),
                                    (1104, '2026-05-11 14:30:00', True),
                                    (1086, '2026-05-13 10:30:00', True),
                                    (1092, '2026-05-21 10:15:00', True),
                                    (1037, '2026-05-27 11:30:00', True),
                                    (1025, '2026-06-01 09:35:00', True),
                                    (1017, '2026-06-08 11:00:00', True),
                                    (1044, '2026-06-03 11:15:00', False),
                                    (1003, '2026-06-08 09:35:00', False),
                                    (1005, '2026-06-09 14:15:00', True),
                                    (1150, '2026-06-25 14:40:00', True),
                                    (1170, '2026-07-01 10:20:00', True),
                                    (1146, '2026-07-02 10:30:00', True),
                                    (1159, '2026-07-03 14:10:00', True),
                                    (1149, '2026-07-06 13:40:00', True),
                                    (1139, '2026-07-15 13:55:00', True),
                                    (1126, '2026-07-20 10:15:00', True),
                                    (1126, '2026-07-20 10:15:00', True),
                                    (1107, '2026-07-24 13:05:00', True)),
                        'fixed': ((1082, '2026-04-28 10:10:00', False),
                                  (1095, '2026-04-30 10:00:00', False),
                                  (1082, '2026-05-07 10:45:00', False),
                                  (1082, '2026-05-07 10:45:00', False),
                                  (1104, '2026-05-11 14:30:00', False),
                                  (1084, '2026-05-13 11:15:00', False),
                                  (1092, '2026-05-21 10:15:00', False),
                                  (1037, '2026-05-27 11:30:00', False),
                                  (1025, '2026-06-01 09:35:00', False),
                                  (1017, '2026-06-08 11:00:00', False),
                                  (1044, '2026-06-03 11:15:00', False),
                                  (1003, '2026-06-08 09:35:00', False),
                                  (1005, '2026-06-09 14:15:00', False),
                                  (1150, '2026-06-25 14:40:00', False),
                                  (1181, '2026-07-01 10:50:00', False),
                                  (1146, '2026-07-02 10:30:00', False),
                                  (1159, '2026-07-03 14:10:00', False),
                                  (1149, '2026-07-06 13:40:00', False),
                                  (1139, '2026-07-15 13:55:00', False),
                                  (1126, '2026-07-20 10:15:00', False),
                                  (1126, '2026-07-20 10:15:00', False))},
 'f1': ((10, 13, 'consolidation', 'down', (11,), ((1070, 1079),), 14),
        (14, 16, 'consolidation', None, (14,), ((1065, 1082),), 17),
        (17, 19, 'consolidation', None, (17,), ((1073, 1100),), 20),
        (20, 22, 'consolidation', None, (20,), ((1039, 1092),), 23),
        (23, 25, 'consolidation', None, (23,), ((1025, 1044),), 26),
        (26, 29, 'consolidation', 'down', (27,), ((1100, 1160),), 30),
        (30, 32, 'consolidation', None, (30,), ((1139, 1177),), 33)),
 'f1_first_counts': {'current': (2656, 2834, 3343, 3940, 4010, 4842, 5352),
                     'fixed': (2660, 2872, 3362, 3956, 4016, 4848, 5364)},
 'f1_evidence_counts': (15, 18, 21, 26, 27, 31, 35),
 'tails': {'current': (33, 35, 'consolidation', None, (33,), ((1094, 1131),), None),
           'fixed': (33, 34, 'incomplete', None, (), (), None)},
 'f2': ((0, 5, 'consolidation', None, (1,), ((1029, 1056),), 6),
        (6, 9, 'consolidation', None, (6,), ((1015, 1048),), None)),
 'f2_spans': (((1, 3, 4),), ((6, 8, 8),)),
 'auto_centers': ((0, 2, 4, 1113, 1135),
                  (5, 7, 11, 1031, 1049),
                  (12, 14, 22, 1070, 1079),
                  (23, 25, 27, 1025, 1044),
                  (28, 30, 34, 1139, 1160)),
 'auto_complete': ((0, 11, 'down', 'down', (0, 5), ((1113, 1135), (1031, 1049)), 14),
                   (12, 27, 'down', 'down', (12, 23), ((1070, 1079), (1025, 1044)), 30)),
 'auto_tails': {'current': (28, 35, 'consolidation', None, (28,), ((1139, 1160),), None),
                'fixed': (28, 34, 'consolidation', None, (28,), ((1139, 1160),), None)},
 'auto_candidates': ((9, (4,), (8,), (1031, 1049), True, None),
                     (11, (4,), (10,), (1031, 1049), None, None),
                     (13, (4,), (12,), (1031, 1049), None, None),
                     (14, (4,), (12, 13), (1031, 1049), None, True)),
 'auto_reasons': ('not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'no_compare_legs',
                  'trend_open',
                  'no_compare_legs',
                  'trend_open',
                  'no_compare_legs',
                  'trend_open',
                  'trend_open',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'no_compare_legs',
                  'center_waves_overlap',
                  'no_compare_legs',
                  'center_waves_overlap',
                  'center_waves_overlap',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers'),
 'revocations': ((114, 117, 118, 'gap'),
                 (114, 119, 122, 'direct'),
                 (129, 132, 133, 'gap'),
                 (134, 137, 138, 'direct'),
                 (139, 142, 143, 'direct'),
                 (144, 147, 148, 'direct'),
                 (144, 149, 150, 'gap'),
                 (144, 151, 152, 'gap'),
                 (144, 153, 158, 'gap'),
                 (144, 159, 160, 'direct'),
                 (164, 169, 174, 'direct'),
                 (164, 173, 174, 'direct'),
                 (181, 188, 189, 'direct'),
                 (190, 195, 198, 'gap'),
                 (190, 199, 200, 'gap'),
                 (201, 204, 205, 'direct'),
                 (201, 206, 207, 'gap'),
                 (201, 208, 209, 'direct'),
                 (201, 210, 211, 'gap'),
                 (201, 212, 227, 'gap'),
                 (228, 231, 232, 'direct'),
                 (228, 233, 234, 'direct'),
                 (228, 235, 236, 'gap'),
                 (228, 237, 238, 'direct'),
                 (239, 248, 255, 'direct'),
                 (239, 256, 257, 'gap'),
                 (258, 261, 262, 'gap'),
                 (263, 266, 267, 'direct'),
                 (268, 271, 272, 'direct'),
                 (268, 273, 274, 'gap'),
                 (268, 275, 278, 'direct'),
                 (268, 279, 280, 'direct'),
                 (268, 281, 284, 'direct'),
                 (268, 285, 288, 'gap'),
                 (268, 289, 290, 'direct'),
                 (294, 297, 298, 'gap'),
                 (294, 299, 300, 'direct'),
                 (294, 301, 302, 'direct')),
 'ineligible_turns': ((114, 121),
                      (144, 155),
                      (144, 157),
                      (164, 167),
                      (164, 171),
                      (181, 184),
                      (181, 186),
                      (190, 193),
                      (190, 197),
                      (201, 214),
                      (201, 216),
                      (201, 220),
                      (201, 222),
                      (201, 224),
                      (201, 226),
                      (239, 242),
                      (239, 244),
                      (239, 246),
                      (239, 250),
                      (239, 252),
                      (239, 254),
                      (268, 277),
                      (268, 283),
                      (268, 287)),
 'source_origin_bridge_proven': False,
 'production_merged': False}


def m2_suffix_input(contract):
    """复用14段头部；尾部自然反应仅在current可见，不虚构fixed时钟。"""
    audit=M3_M2_SUFFIX_ROLE_AUDIT;head=M3_M2_JOINED_ROLE_AUDIT
    if audit['head_certificate_sha256']!=head['certificate_sha256']:
        raise AssertionError('M2后缀须绑定已验祖先链')
    case,units=gap_revision_input(dict(head,units=head['units']+audit['units']))
    if contract=='current':
        names=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks',
               'mode','proof_bi','local_raw_count','confirmed_raw_count')
        units.append(dict(zip(names,audit['current_tail_unit'])))
    for i,u in enumerate(units[14:]):
        u['local_raw_count']=audit['local_counts'][contract][i]
        u['confirmed_raw_count']=audit['published_counts'][contract][i]
    if contract=='current':
        for i,u in enumerate(units[:14]):
            u['local_raw_count']=head['current_local_counts'][i]
            u['confirmed_raw_count']=head['current_counts'][i]
    return case,units,audit


class TestM2SuffixConsumers(unittest.TestCase):
    """给定seed16全供给窗；同级切分与自动递归的合同分别验证。"""

    @staticmethod
    def _types(case,units,arrivals=None):
        audit=M3_M2_SUFFIX_ROLE_AUDIT
        arrivals=arrivals or [gap_revision_time(case,u['confirmed_raw_count']) for u in units]
        result=[]
        for spec in M3_M2_JOINED_ROLE_AUDIT['f1']+audit['f1']:
            now=max(arrivals[:spec[-1]+1]);size=sum(at<=now for at in arrivals)
            move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:size]),5586))
                      if m.complete and m.seg_start==spec[0])
            result.append(m3_xd_type('M2-full16',move,units[:size],now))
        return result

    def test_full_window_ten_f1_and_one_f2_freeze_first_visible_evidence(self):
        for contract in ('current','fixed'):
            case,units,audit=m2_suffix_input(contract);seen={};types=[];frozen=None
            specs=M3_M2_JOINED_ROLE_AUDIT['f1']+audit['f1']
            for count in sorted({5586}|{n for u in units for at in (u['local_raw_count'],u['confirmed_raw_count']) for n in (at-1,at)}):
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                moves=chan.same_level_decompose(m3_xd_parts(dict(units=units),count))
                done=[m for m in moves if m.complete]
                expected=[s for s in specs if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual([m3_xd_shape(m) for m in done],[m3_xd_expected(units,s) for s in expected])
                for move in done:
                    if move.seg_start not in seen:
                        seen[move.seg_start]=count
                        types.append(m3_xd_type('M2-full16',move,visible,gap_revision_time(case,count)))
                f2=chan.confirm_level_up(types,gap_revision_time(case,count),'F2')
                self.assertEqual(len(f2),int(len(types)>=7))
                if f2:
                    if frozen is None:frozen=f2[0]
                    self.assertEqual(f2[0],frozen)
            self.assertEqual(tuple(seen[s[0]] for s in specs),M3_M2_JOINED_ROLE_AUDIT['f1_first_counts'][contract]+audit['f1_first_counts'][contract])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),(4,8,11)+audit['f1_evidence_counts'])
            self.assertEqual(m3_xd_shape(moves[-1]),m3_xd_expected(units,audit['tails'][contract]))
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,s) for s in audit['f2']])
            self.assertEqual((frozen.kind,frozen.direction,len(frozen.unit_ids),len(frozen.evidence_ids)),('consolidation',None,6,7))
            self.assertEqual(frozen.confirmed_dt,types[6].confirmed_dt)
            self.assertEqual((round(frozen.low*1000),round(frozen.high*1000)),(1010,1200))
            now=gap_revision_time(case,5586);rows=m3_xd_rows(case)
            strict=chan.scan_strict_divergence(types,now,'F2')
            self.assertEqual((strict.results,tuple(r for _,r in strict.skipped)),((),('not_trend','not_two_separated_centers')))
            first=chan.scan_first_points(types,rows,now,'F2')
            self.assertEqual((first.points,tuple(r for _,r in first.exclusions)),([],('not_trend',)))
            self.assertFalse(any(chan.analyze_point_chain(types,rows,now,'F2')))

    def test_automatic_recursive_finite_prefixes_and_actual_batches_keep_missing_legs(self):
        def forbidden(a,b):raise AssertionError('候选或缺比较腿不得评估力度')
        for contract in ('current','fixed'):
            case,units,audit=m2_suffix_input(contract);counts=[u['confirmed_raw_count'] for u in units]
            given=[chan.ConfirmedMove('M2-full16:xd:'+str(i),'XD',u['direction'],date(u['start_dt']),date(u['end_dt']),u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,gap_revision_time(case,counts[i])) for i,u in enumerate(units)]
            candidates={c[0]:c[1:] for c in audit['auto_candidates']};rows=m3_xd_rows(case)
            sizes=list(range(1,len(units)+1))+[sum(at<=n for at in counts) for n in sorted(set(counts))]
            for size in sizes:
                now=given[size-1].confirmed_dt;scan=chan.scan_strict_divergence(given[:size],now,'recursive-F1',forbidden,'structural_guard')
                expected=['no_compare_legs']*(int(size>=15)+int(size>=31))
                if size not in candidates:expected.append(audit['auto_reasons'][size-1])
                self.assertEqual(tuple(r for _,r in scan.skipped),tuple(expected))
                self.assertEqual(len(scan.results),int(size in candidates))
                if size in candidates:
                    reference,leave,core,extreme,third=candidates[size];r=scan.results[0]
                    self.assertEqual((r.status,r.reason),('candidate','trend_open'))
                    self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in r.reference_ids),reference)
                    self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in r.leave_ids),leave)
                    self.assertEqual(tuple(round(v*1000) for v in r.center_range),core)
                    self.assertEqual(dict(r.conditions),dict(trend=None,separated_centers=True,new_extreme=extreme,leave_third_point=third))
                first=chan.scan_first_points(given[:size],rows,now,'recursive-F1')
                self.assertEqual((first.points,tuple(r for _,r in first.exclusions)),([],('no_directional_compare_legs',)*(int(size>=15)+int(size>=31))))
                self.assertFalse(any(chan.analyze_point_chain(given[:size],rows,now,'recursive-F1')))
            done=chan.confirm_level_up(given,given[-1].confirmed_dt,'recursive-F1')
            self.assertEqual([len(t.unit_ids) for t in done],[12,16])
            self.assertEqual(tuple(len(t.evidence_ids) for t in done),(15,31))
            self.assertEqual([t.confirmed_dt for t in done],[gap_revision_time(case,counts[i]) for i in (14,30)])
            self.assertEqual((done[1].kind,done[1].direction),('down','down'))
            self.assertGreater(done[1].end_price,done[1].start_price)
            expected=audit['auto_complete']+(audit['auto_tails'][contract],)
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,s) for s in expected])

    def test_parent23_late_batch_delays_first_f2_and_preserves_prior_f1(self):
        for contract in ('current','fixed'):
            case,units,_=m2_suffix_input(contract);arrivals=[gap_revision_time(case,u['confirmed_raw_count']) for u in units]
            baseline=self._types(case,units)
            for proof in (23,33):
                delayed=list(arrivals);late=arrivals[proof]+timedelta(days=1);delayed[proof]=late
                for i in range(proof+1,len(delayed)):delayed[i]=max(arrivals[i],delayed[i-1])
                changed=self._types(case,units,delayed)
                before=[t for t in changed if t.confirmed_dt<late];after=[t for t in changed if t.confirmed_dt<=late]
                old=chan.confirm_level_up(before,late-timedelta(microseconds=1),'F2')
                new=chan.confirm_level_up(after,late,'F2')
                self.assertEqual((len(old),len(new)),(0,1) if proof==23 else (1,1))
                if proof==23:
                    self.assertEqual(changed[:6],baseline[:6])
                    self.assertEqual(new[0].confirmed_dt,late)
                    self.assertEqual(len(new[0].evidence_ids),sum(t.confirmed_dt<=late for t in changed))
                    self.assertEqual(delayed[23:26],[late]*3)
                else:self.assertEqual(old,new)
            cutoff=baseline[6].confirmed_dt;rows=m3_xd_rows(case)
            for row in rows[units[23]['confirmed_raw_count']:]:
                row.pop('open');row.update(high=float('nan'),low=-999,close=99999)
            future=baseline[-1]._replace(move_id=None,start_price=float('nan'),confirmed_dt=cutoff+timedelta(days=30))
            self.assertFalse(any(chan.analyze_point_chain(baseline[:7]+[future],rows,cutoff,'F2')))

    def test_last_f1_closed_edge_and_current_natural_tail_are_different_states(self):
        for contract in ('current','fixed'):
            _,units,audit=m2_suffix_input(contract)
            self.assertEqual(len(units),36 if contract=='current' else 35)
            self.assertEqual((units[14]['start_ticks'],units[14]['high_ticks']),(1079,1085))
            # F1第十项由外部单元33恰触核心下沿1139确认；镜像仍为闭交集。
            source=m3_xd_parts(dict(units=units),5586)[30:34]
            for delta in (-1,0,1):
                for mirror in (False,True):
                    values=[(p.low,p.high) for p in source];values[-1]=(values[-1][0],(1139+delta)/1000.)
                    sample=[SimpleNamespace(direction=('down' if p.direction=='up' else 'up') if mirror else p.direction,start_dt=p.start_dt,end_dt=p.end_dt,low=-hi if mirror else lo,high=-lo if mirror else hi) for p,(lo,hi) in zip(source,values)]
                    self.assertEqual(any(m.complete for m in chan.same_level_decompose(sample)),delta>=0)
            final=chan.same_level_decompose(m3_xd_parts(dict(units=units),5586))[-1]
            self.assertFalse(final.complete)
            self.assertEqual(final.kind,'consolidation' if contract=='current' else 'incomplete')
            self.assertEqual(m3_xd_shape(final),m3_xd_expected(units,audit['tails'][contract]))


# 课20/24/29给定seed16头部角色；c未离开，不复用旧三类标签。
M3_M2_ZN_ROLE_AUDIT = {'certificate_sha256': '3e71d9f7eb30e98f5a41495379ec1d9bff1eac56d7db2779d5e077bd46355d51',
 'BC_wave_overlap_ticks': 52,
 'C_wave_snapshots': ((15, 1050, 1085, 41),
                      (17, 1050, 1100, 41),
                      (19, 1050, 1111, 41),
                      (20, 1039, 1111, 52),
                      (21, 1039, 1111, 52)),
 'c_low_ticks': 1070,
 'event_clock_units': (14, 20, 24, 26),
 'head_certificate_sha256': '7f592db0a28e4f6e120c28addd0e6d9ee661fdcb9b182ead07ed146e6a99efdc',
 'ledger': {'current': (('A_open', 3, 1329),
                        ('b_fixed', 4, 1639),
                        ('A_closed', 5, 1639),
                        ('B_open', 7, 1764),
                        ('B_zn_extend', 9, 2040),
                        ('B_zn_extend', 11, 2254),
                        ('c_fixed', 12, 2356),
                        ('c_fail', 12, 2356),
                        ('B_closed', 13, 2398),
                        ('C_open', 15, 2740),
                        ('C_zn_extend', 17, 2834),
                        ('C_zn_extend', 19, 3052),
                        ('C_zn_extend', 21, 3554),
                        ('C_closed', 23, 3940),
                        ('merge_determined', 23, 3940)),
            'fixed': (('A_open', 3, 1349),
                      ('b_fixed', 4, 1648),
                      ('A_closed', 5, 1648),
                      ('B_open', 7, 1775),
                      ('B_zn_extend', 9, 2063),
                      ('B_zn_extend', 11, 2261),
                      ('c_fixed', 12, 2365),
                      ('c_fail', 12, 2365),
                      ('B_closed', 13, 2437),
                      ('C_open', 15, 2759),
                      ('C_zn_extend', 17, 2872),
                      ('C_zn_extend', 19, 3077),
                      ('C_zn_extend', 21, 3563),
                      ('C_closed', 23, 3956),
                      ('merge_determined', 23, 3956))},
 'legacy_A_closed_by_map': (28, 26),
 'legacy_A_member_map': ((22, 18), (24, 20), (26, 22)),
 'legacy_A_proof_changed_from': (161, 163, 1, 168),
 'legacy_A_proof_changed_to': (161, 163, 1, 172),
 'legacy_attempt_pairs': ((30, 31), (31, 32), (35, 36)),
 'missing_legacy_units': (30, 31, 32, 33, 34, 35),
 'near_return_gap_ticks': 1,
 'near_return_unit': 14,
 'old_labels_reusable': False,
 'prior_low_ticks': 1010,
 'retained_A': {'closed_by': 24,
                'core_basis': 'three_units',
                'dd': 1015,
                'frozen_by_departure': False,
                'gg': 1111,
                'zd': 1073,
                'zg': 1100,
                'zn': (18, 20, 22)},
 'return_gap_ticks': 21,
 'return_unit': 20,
 'roles': {'A': {'closed_by': 5,
                 'core_basis': 'three_units',
                 'dd': 1100,
                 'gg': 1140,
                 'zd': 1113,
                 'zg': 1135,
                 'zn': (1, 3)},
           'B': {'closed_by': 13,
                 'core_basis': 'three_units',
                 'dd': 1010,
                 'gg': 1091,
                 'zd': 1031,
                 'zg': 1049,
                 'zn': (5, 7, 9, 11)},
           'C': {'closed_by': 23,
                 'core_basis': 'three_units',
                 'dd': 1039,
                 'gg': 1111,
                 'zd': 1070,
                 'zg': 1079,
                 'zn': (13, 15, 17, 19, 21)},
           'a': {'unit': 0},
           'b': {'unit': 4},
           'c': {'outcome': 'fail', 'unit': 12},
           'gap_ticks': 9,
           'merge': {'branch': 'above', 'determined': True, 'pair': ['B', 'C']},
           'proof': None},
 'scope': 'given_seed16_head_and_retained_roles_not_complete_strict_trend',
 'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'suffix_certificate_sha256': 'ee14d65c88a367594a37eeb28b31689bdb19fd88d28d1f01357e910bb4ca2e3a',
 'surviving_pullback_map': (36, 30),
 'trend': {'direction': 'down', 'status': 'no_departure'}}


class TestM2ZnRoles(unittest.TestCase):
    """给定seed16头部Zn及b/c，独立于自动递归的工程走势身份。"""

    @staticmethod
    def _data(contract='fixed'):
        case,units,_=m2_suffix_input(contract);audit=M3_M2_ZN_ROLE_AUDIT
        if (audit['head_certificate_sha256']!=M3_M2_JOINED_ROLE_AUDIT['certificate_sha256'] or
                audit['suffix_certificate_sha256']!=M3_M2_SUFFIX_ROLE_AUDIT['certificate_sha256']):
            raise AssertionError('M2角色须绑定同一已验衔接与后缀')
        return case,units,audit

    @staticmethod
    def _zs(spec,mirror=False):
        lo,hi,dd,gg=[spec[k] for k in ('zd','zg','dd','gg')]
        if mirror:lo,hi,dd,gg=3000-hi,3000-lo,3000-gg,3000-dd
        return chan.ZS(lo/1000.,hi/1000.,gg/1000.,dd/1000.,None,None,
                       'down' if mirror else 'up',2*len(spec['zn'])-1)

    def test_zn_three_unit_cores_and_wave_separation_are_different_conditions(self):
        _,units,audit=self._data();roles=audit['roles'];parts=m3_xd_parts(dict(units=units),5586)
        for mirror in (False,True):
            supplied=[SimpleNamespace(low=(3-p.high if mirror else p.low),high=(3-p.low if mirror else p.high),
                      direction=('down' if p.direction=='up' else 'up') if mirror else p.direction,
                      start_dt=p.start_dt,end_dt=p.end_dt) for p in parts]
            for name in ('A','B','C'):
                spec=roles[name];a,z=spec['zn'][0],spec['zn'][-1]
                actual=chan.find_zs(supplied[a:z+1])[0];expected=self._zs(spec,mirror)
                self.assertEqual(tuple(round(v*1000) for v in (actual.zd,actual.zg,actual.dd,actual.gg)),
                                 tuple(round(v*1000) for v in (expected.zd,expected.zg,expected.dd,expected.gg)))
            self.assertEqual(chan.zs_relation(self._zs(roles['A'],mirror),self._zs(roles['B'],mirror)),
                             'up_continue' if mirror else 'down_continue')
            self.assertEqual(chan.zs_relation(self._zs(roles['B'],mirror),self._zs(roles['C'],mirror)),'expand')
            # A/B全程波动间隙为9格；等触不能算严格分离。
            for delta in (-1,0,1):
                changed=dict(roles['B'],gg=1100+delta)
                self.assertEqual(chan.zs_relation(self._zs(roles['A'],mirror),self._zs(changed,mirror)),
                                 ('up_continue' if mirror else 'down_continue') if delta<0 else 'expand')
        self.assertEqual(roles['A']['dd']-roles['B']['gg'],roles['gap_ticks'])
        self.assertEqual(roles['B']['gg']-roles['C']['dd'],audit['BC_wave_overlap_ticks'])

    def test_c_failed_to_depart_and_later_touch_is_not_an_immediate_return(self):
        _,units,audit=self._data();roles=audit['roles'];parts=m3_xd_parts(dict(units=units),5586)
        A=chan.find_zs(parts[1:4])[0];B=chan.find_zs(parts[5:12])[0]
        b,c=roles['b']['unit'],roles['c']['unit']
        self.assertLess(parts[b].low,A.zd)
        self.assertEqual((b,c,audit['trend']['status'],roles['c']['outcome']),(4,12,'no_departure','fail'))
        self.assertEqual(units[c]['low_ticks']-round(B.zg*1000),audit['return_gap_ticks'])
        self.assertEqual((min(u['low_ticks'] for u in units[:c]),units[c]['low_ticks']),
                         (audit['prior_low_ticks'],audit['c_low_ticks']))
        self.assertGreater(units[c]['low_ticks'],audit['prior_low_ticks'])
        touches=[i for i in range(c+1,len(parts)) if parts[i].low<=B.zg and parts[i].high>=B.zd]
        self.assertEqual(touches[0],audit['return_unit'])
        self.assertGreater(touches[0],c+1)
        self.assertEqual(units[audit['near_return_unit']]['low_ticks']-round(B.zg*1000),audit['near_return_gap_ticks'])
        self.assertIsNone(roles['proof'])
        # 角色c12不等于既有自动递归走势的离开比较腿；不移植旧点位标签。
        self.assertFalse(audit['old_labels_reusable'])

    def test_role_ledger_and_partial_C_ranges_wait_for_actual_publication(self):
        for contract in ('current','fixed'):
            _,units,audit=self._data(contract);counts=[u['confirmed_raw_count'] for u in units]
            self.assertEqual(tuple((name,i,counts[i]) for name,i,_ in audit['ledger'][contract]),audit['ledger'][contract])
            for name in ('A','B','C'):
                spec=audit['roles'][name];start=spec['zn'][0];at=counts[start+2]
                for now,formed in ((at-1,False),(at,True)):
                    visible=m3_xd_parts(dict(units=units),now);zs=chan.find_zs(visible[start:start+3])
                    self.assertEqual(bool(zs),formed)
                    if formed:self.assertEqual((round(zs[0].zd*1000),round(zs[0].zg*1000)),(spec['zd'],spec['zg']))
            self.assertEqual(counts[4],counts[5])  # b与A封口同批，不能制造中间快照。
            self.assertLess(counts[20],counts[21])
            self.assertLess(counts[24],counts[audit['legacy_A_closed_by_map'][1]])
            for stop,lo,hi,overlap in audit['C_wave_snapshots']:
                visible=m3_xd_parts(dict(units=units),counts[stop]);z=chan.find_zs(visible[13:stop+1])[0]
                self.assertEqual((round(z.dd*1000),round(z.gg*1000),1091-round(z.dd*1000)),(lo,hi,overlap))
            # C初成1050；20的中间反向波动才降至1039，早于21的Zn延伸。
            formed=chan.find_zs(m3_xd_parts(dict(units=units),counts[15])[13:16])[0]
            self.assertEqual(round(formed.dd*1000),1050)
            self.assertEqual(audit['roles']['C']['dd'],1039)


# 给定XD与因果中枢形成快照的首次回试；不沿用最终Zn成员排除或旧标签。
M3_M2_THIRD_LIFECYCLE_AUDIT = {'certificate_sha256': 'cd4fb8185aa5b8dff3d4efcbd4c416ad6d99e0ca653104a2f95070e3559d3714',
 'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'head_certificate_sha256': '7f592db0a28e4f6e120c28addd0e6d9ee661fdcb9b182ead07ed146e6a99efdc',
 'suffix_certificate_sha256': 'ee14d65c88a367594a37eeb28b31689bdb19fd88d28d1f01357e910bb4ca2e3a',
 'zn_certificate_sha256': '3e71d9f7eb30e98f5a41495379ec1d9bff1eac56d7db2779d5e077bd46355d51',
 'scope': 'given_seed16_causal_XD_contexts_not_automatic_theory_levels',
 'contexts': {'A': (1, 3, 1113, 1135, None),
              'B': (5, 7, 1031, 1049, None),
              'C': (13, 15, 1070, 1079, None),
              'N': (29, 31, 1139, 1177, 'R'),
              'R': (18, 20, 1073, 1100, None)},
 'attempts': {'A': (('sell3', 4, 5, 53, 1060, 'before_center_known'),
                    ('buy3', 27, 28, -35, 1100, 'fail'),
                    ('sell3', 28, 29, -78, 1191, 'fail'),
                    ('buy3', 29, 30, 4, 1139, 'established')),
              'B': (('sell3', 8, 9, -25, 1056, 'before_center_known'),
                    ('buy3', 9, 10, -20, 1029, 'fail'),
                    ('sell3', 10, 11, -60, 1086, 'fail'),
                    ('buy3', 11, 12, 21, 1070, 'established')),
              'C': (('sell3', 16, 17, -30, 1100, 'before_center_known'),
                    ('buy3', 17, 18, -6, 1073, 'before_center_known'),
                    ('buy3', 19, 20, -40, 1039, 'fail'),
                    ('sell3', 20, 21, -22, 1092, 'fail'),
                    ('buy3', 21, 22, -64, 1015, 'fail'),
                    ('sell3', 22, 23, 22, 1048, 'established')),
              'N': (('sell3', 32, 33, 0, 1139, 'before_center_known'), ('sell3', 34, 35, 8, 1131, 'established')),
              'R': (('sell3', 22, 23, 25, 1048, 'before_center_known'), ('buy3', 27, 28, 0, 1100, 'established'))},
 'parent_N_pull': 28,
 'clock_units': (3,
                 4,
                 5,
                 7,
                 8,
                 9,
                 10,
                 11,
                 12,
                 15,
                 16,
                 17,
                 18,
                 19,
                 20,
                 21,
                 22,
                 23,
                 24,
                 25,
                 26,
                 27,
                 28,
                 29,
                 30,
                 31,
                 32,
                 33,
                 34,
                 35),
 'legacy_Zn_members_do_not_filter_causal_attempts': (('B', 9), ('B', 11), ('C', 19), ('C', 21)),
 'terminal_counts': {'current': 5, 'fixed': 4},
 'points': {'A': ('buy3', 29, 30, 1139, 4),
            'B': ('buy3', 11, 12, 1070, 21),
            'C': ('sell3', 22, 23, 1048, 22),
            'N': ('sell3', 34, 35, 1131, 8),
            'R': ('buy3', 27, 28, 1100, 0)},
 'known_raw': {'current': {'A': 1329, 'B': 1764, 'C': 2740, 'N': 4885, 'R': 3343},
               'fixed': {'A': 1349, 'B': 1775, 'C': 2759, 'N': 4894, 'R': 3362}},
 'point_raw': {'current': {'A': 4842, 'B': 2356, 'C': 3940, 'N': 5564, 'R': 4716},
               'fixed': {'A': 4848, 'B': 2365, 'C': 3956, 'N': None, 'R': 4727}},
 'point_order': ('B', 'C', 'R', 'A', 'N'),
 'suppressed_pairs': {'A': ((32, 33), (33, 34), (34, 35)),
                      'B': ((21, 22), (22, 23), (24, 25), (26, 27), (27, 28)),
                      'C': ((27, 28),),
                      'N': (),
                      'R': ((29, 30), (33, 34))},
 'source_origin_bridge_proven': False,
 'production_merged': False}


def m2_third_input(contract):
    """给定XD级别与形成快照；新生N使用新身份并等待父中枢首个有效点。"""
    case,units,_=m2_suffix_input(contract);a=M3_M2_THIRD_LIFECYCLE_AUDIT
    if (a['suffix_certificate_sha256']!=M3_M2_SUFFIX_ROLE_AUDIT['certificate_sha256'] or
            a['zn_certificate_sha256']!=M3_M2_ZN_ROLE_AUDIT['certificate_sha256']):
        raise AssertionError('三类上下文须绑定同一给定链与角色证书')
    root='M2-third16:'+contract+':'+a['certificate_sha256']
    moves=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           gap_revision_time(case,u['confirmed_raw_count'])) for i,u in enumerate(units)]
    contexts=[]
    for name,(first,formed,zd,zg,parent) in a['contexts'].items():
        known=moves[formed].confirmed_dt
        if parent:known=max(known,moves[a['parent_N_pull']].confirmed_dt)
        contexts.append(chan.ThirdPointContext(root+':context:'+name,'given-center','given-XD',
                        chan.ConfirmedCenter(root+':center:'+name,'given-center',zd/1000.,zg/1000.,known)))
    return case,units,a,moves,contexts


class TestM2CausalThirdLifecycle(unittest.TestCase):
    """只核给定种子/级别/中枢形成快照下的条件三类，不迁移旧标签。"""

    def test_actual_batches_freeze_first_points_and_keep_newborn_N_pending_in_fixed(self):
        for contract in ('current','fixed'):
            case,units,a,moves,contexts=m2_third_input(contract);previous={}
            counts=sorted({5586}|{n for i in a['clock_units'] if i<len(units)
                                  for n in (units[i]['confirmed_raw_count']-1,units[i]['confirmed_raw_count'])})
            for count in counts:
                points=chan.find_third_points(moves,contexts,gap_revision_time(case,count))
                names=[n for n in a['point_order'] if a['point_raw'][contract][n] is not None and a['point_raw'][contract][n]<=count]
                self.assertEqual(len(points),len(names))
                for point,name in zip(points,names):
                    kind,leave,pull,price,margin=a['points'][name]
                    self.assertEqual((point.kind,point.leave_move_id,point.pull_move_id,round(point.price*1000),str(point.dt),point.confirmed_dt),
                                     (kind,moves[leave].move_id,moves[pull].move_id,price,units[pull]['end_dt'],gap_revision_time(case,a['point_raw'][contract][name])))
                    self.assertTrue(point.context_id.endswith(':context:'+name))
                    self.assertTrue(point.center_id.endswith(':center:'+name))
                    self.assertLess(point.dt,point.confirmed_dt)
                current={p.context_id:p for p in points}
                for key,point in previous.items():self.assertEqual(current[key],point)
                previous=current
            self.assertEqual(len(points),a['terminal_counts'][contract])
            by_name={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            self.assertNotEqual(by_name['N'].center.center_id,by_name['R'].center.center_id)
            self.assertGreater(by_name['N'].center.confirmed_dt,moves[a['parent_N_pull']].confirmed_dt)
            self.assertEqual(a['contexts']['N'][0],a['parent_N_pull']+1)
            if contract=='fixed':
                self.assertEqual(len(moves),35)
                self.assertEqual(chan.find_third_points(moves,[by_name['N']],gap_revision_time(case,5586)),[])

    def test_failed_first_returns_and_center_known_time_are_distinct_gates(self):
        for contract in ('current','fixed'):
            case,units,a,moves,contexts=m2_third_input(contract);by_name={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            for name,rows in a['attempts'].items():
                for side,leave,pull,margin,price,status in rows:
                    if pull>=len(units):continue
                    now=gap_revision_time(case,units[pull]['confirmed_raw_count'])
                    if status in ('fail','before_center_known'):
                        self.assertEqual(chan.find_third_points(moves,[by_name[name]],now),[])
            # R的22/23几何守沿，但原首离开早于确认；等时边界为合成门控检查。
            context=by_name['R'];edge=moves[22].start_dt
            for delta in (-1,0,1):
                changed=context._replace(center=context.center._replace(confirmed_dt=edge+timedelta(microseconds=delta)))
                point,=chan.find_third_points(moves,[changed],gap_revision_time(case,5586))
                self.assertEqual((point.leave_move_id,point.pull_move_id),
                                 (moves[22].move_id,moves[23].move_id) if delta<=0 else (moves[27].move_id,moves[28].move_id))
            for name in ('B','C','R'):
                points=chan.find_third_points(moves,[by_name[name]],gap_revision_time(case,5586))
                self.assertEqual(len(points),1)  # 后续再满足几何，也不重发已破坏中枢的点。

    def test_touching_R_pullback_and_mirror_use_closed_edges(self):
        case,units,_,moves,contexts=m2_third_input('current');context=next(c for c in contexts if c.context_id.endswith(':R'))
        for delta in (-1,0,1):
            for mirror in (False,True):
                changed=list(moves[:29]);price=(1100+delta)/1000.
                changed[28]=changed[28]._replace(end_price=price,low=price)
                active=context
                if mirror:
                    flip=lambda v:(3000-round(v*1000))/1000.
                    changed=[m._replace(direction='down' if m.direction=='up' else 'up',start_price=flip(m.start_price),
                             end_price=flip(m.end_price),low=flip(m.high),high=flip(m.low)) for m in changed]
                    active=context._replace(center=context.center._replace(zd=flip(context.center.zg),zg=flip(context.center.zd)))
                points=chan.find_third_points(changed,[active],gap_revision_time(case,units[28]['confirmed_raw_count']))
                self.assertEqual(len(points),int(delta>=0))
                if points:self.assertEqual(points[0].kind,'sell3' if mirror else 'buy3')

    def test_each_pull_waits_for_late_arrival_and_future_values_stay_unread(self):
        for contract in ('current','fixed'):
            case,units,a,moves,contexts=m2_third_input(contract)
            for context in contexts:
                name=context.context_id.rsplit(':',1)[1]
                if a['point_raw'][contract][name] is None:continue
                _,leave,pull,_,_=a['points'][name];late=moves[pull].confirmed_dt+timedelta(days=1)
                delayed=list(moves);delayed[pull]=moves[pull]._replace(confirmed_dt=late)
                for i in range(pull+1,len(moves)):delayed[i]=moves[i]._replace(confirmed_dt=max(moves[i].confirmed_dt,delayed[i-1].confirmed_dt))
                self.assertEqual(chan.find_third_points(delayed,[context],late-timedelta(microseconds=1)),[])
                point,=chan.find_third_points(delayed,[context],late)
                self.assertEqual((point.leave_move_id,point.pull_move_id,point.confirmed_dt),(moves[leave].move_id,moves[pull].move_id,late))
                future=moves[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=late+timedelta(days=10))
                future_context=context._replace(context_id=None,center=context.center._replace(center_id=None,zd=float('nan'),confirmed_dt=late+timedelta(days=10)))
                self.assertEqual(chan.find_third_points(delayed+[future],[context,future_context],late),[point])


# E长日线窗给定seed0的双合同消费者；不复用旧首见时钟或源起点理论资格。
M3_E_CONSUMERS_AUDIT = {'certificate_sha256': '88fec023f9df48631a9720f3a8f604c30dc90fc60bdfacc79eff02bc09470533',
 'auto': (0, 7, 'up', 'up', (0, 4), ((695, 737), (887, 1017)), None),
 'auto_centers': ((0, 2, 3, 695, 737), (4, 6, 7, 887, 1017)),
 'auto_leave': (7,),
 'auto_reasons': ('not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'not_two_separated_centers',
                  'no_compare_legs',
                  'trend_open'),
 'auto_reference': (3,),
 'auto_wave_overlap': 314,
 'complete_F2': 0,
 'current_counts': (57, 84, 113, 200, 200, 255, 255, 279),
 'events': ((0, 2, 1, 5),
            (3, 5, 1, 8),
            (6, 8, 1, 11),
            (9, 11, 2, 23),
            (12, 20, 1, 23),
            (21, 23, 2, 29),
            (24, 26, 1, 29),
            (27, 29, 1, 32)),
 'f1': ((0, 2, 'consolidation', None, (0,), ((695, 737),), 3),
        (3, 5, 'consolidation', None, (3,), ((887, 1017),), 6)),
 'f1_evidence': {'current': (5, 7), 'fixed': (5, 7)},
 'f1_first': {'current': (200, 255), 'fixed': (204, 264)},
 'f2': (0, 1, 'incomplete', None, (), (), None),
 'fixture': 'real_f1_originals.json',
 'fixture_sha256': '7c8408bf8beaf9f9c492460cb00353856c15dec56951a310de8522b1db9b5d29',
 'id': '512880-day-2018-08-24-2019-11-20',
 'impact_contracts': ((9, 'all_current', 300), (10, 'fixed_without_active', 300)),
 'impact_snapshot_sha256': '7414303cf5ed9e7dc1c62c565c4e69009baeb996da4de200b4b3a9e058f5972e',
 'legacy_first_raw': 175,
 'legacy_mode_proof_end': (1, 18, 1153),
 'new_mode_proof_end': (2, 23, 1185),
 'prior_event_receipt_sha256': 'd55126633a153c0c0b9948c2c33b5184d6393f848eb94c7516116e0476d5dc8d',
 'production_merged': False,
 'publication_proofs': {'current': ((842, '2018-11-19', True),
                                    (695, '2018-12-26', True),
                                    (845, '2019-02-14', True),
                                    (1017, '2019-06-24', True),
                                    (1017, '2019-06-24', True),
                                    (1024, '2019-09-09', True),
                                    (1024, '2019-09-09', True),
                                    (913, '2019-10-21', True)),
                        'fixed': ((842, '2018-11-19', False),
                                  (695, '2018-12-26', False),
                                  (1185, '2019-03-07', False),
                                  (1017, '2019-06-24', False),
                                  (1017, '2019-06-24', False),
                                  (1039, '2019-09-16', False),
                                  (1039, '2019-09-16', False),
                                  (913, '2019-10-21', False))},
 'scope': 'E_given_seed0_full300_consumers_not_source_theory_proof',
 'seed': 0,
 'source_origin_bridge_proven': False,
 'strict_c_high': 1039,
 'strict_gap_ticks': 29,
 'strict_prior_high': 1185,
 'strict_roles': {'A': {'closed_by': 4,
                        'core_basis': 'three_units',
                        'dd': 613,
                        'gg': 842,
                        'zd': 695,
                        'zg': 737,
                        'zn': (0, 2)},
                  'B': {'closed_by': None,
                        'core_basis': 'three_units',
                        'dd': 871,
                        'gg': 1185,
                        'zd': 887,
                        'zg': 1017,
                        'zn': (4, 6)},
                  'C': None,
                  'a': None,
                  'b': {'unit': 3},
                  'c': {'outcome': 'departed', 'unit': 7},
                  'gap_ticks': 29,
                  'merge': None,
                  'proof': None},
 'tail': (6, 7, 'incomplete', None, (), (), None),
 'units': (('down', '2018-08-28', '2018-10-19', 737, 613, 613, 737, 1, 5, 63, 63),
           ('up', '2018-10-19', '2018-11-19', 613, 842, 613, 842, 1, 8, 90, 90),
           ('down', '2018-11-19', '2018-12-26', 842, 695, 695, 842, 1, 11, 134, 134),
           ('up', '2018-12-26', '2019-03-07', 695, 1185, 695, 1185, 2, 23, 204, 204),
           ('down', '2019-03-07', '2019-05-24', 1185, 887, 887, 1185, 1, 23, 204, 204),
           ('up', '2019-05-24', '2019-06-24', 887, 1017, 887, 1017, 2, 29, 264, 264),
           ('down', '2019-06-24', '2019-08-07', 1017, 871, 871, 1017, 1, 29, 264, 264),
           ('up', '2019-08-07', '2019-09-16', 871, 1039, 871, 1039, 1, 32, 292, 292))}


def e_consumer_input(contract):
    """E日线午夜标签与15:05可用约定分开；不改原始fixture或旧XD声明。"""
    a=M3_E_CONSUMERS_AUDIT;case,units=gap_revision_input(a)
    if contract=='current':
        for u,count in zip(units,a['current_counts']):u.update(local_raw_count=count,confirmed_raw_count=count)
    rows=m3_xd_rows(dict(raw_rows=[dict(r,dt=r['dt'][:10]) for r in case['raw_rows']]))
    root='E-given0:'+contract+':'+a['certificate_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           gap_revision_time(case,u['confirmed_raw_count'])) for i,u in enumerate(units)]
    return case,units,a,rows,given


class TestEConditionalConsumers(unittest.TestCase):
    """原变化清单E两条合同：给定8段的同级F1与开放递归消费者。"""

    @staticmethod
    def _types(case,units,a,contract,arrivals=None):
        arrivals=arrivals or [gap_revision_time(case,u['confirmed_raw_count']) for u in units];types=[]
        for spec in a['f1']:
            known=max(arrivals[:spec[-1]+1]);width=sum(at<=known for at in arrivals)
            move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:width]),300))
                      if m.complete and m.seg_start==spec[0])
            types.append(m3_xd_type('E-given0:'+contract+':'+a['certificate_sha256'],move,units[:width],known))
        return types

    def test_daily_prefixes_freeze_two_F1_and_whole_arrival_batches(self):
        for contract in ('current','fixed'):
            case,units,a,rows,_=e_consumer_input(contract);first={};types=[]
            self.assertEqual((rows[0]['closed_dt'].hour,rows[0]['available_dt'].hour,rows[0]['available_dt'].minute),(15,15,5))
            for count in range(1,301):
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                done=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
                expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual([m3_xd_shape(m) for m in done],[m3_xd_expected(units,s) for s in expected])
                for m in done:
                    if m.seg_start not in first:
                        first[m.seg_start]=count;types.append(m3_xd_type('E-given0:'+contract+':'+a['certificate_sha256'],m,visible,rows[count-1]['available_dt']))
                self.assertEqual(chan.confirm_level_up(types,rows[count-1]['available_dt'],'F2'),[])
            self.assertEqual(tuple(first[s[0]] for s in a['f1']),a['f1_first'][contract])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),a['f1_evidence'][contract])
            self.assertEqual((round(types[0].low*1000),round(types[0].high*1000),len(types[0].evidence_ids)),(613,842,5))
            self.assertEqual(m3_xd_shape(chan.same_level_decompose(m3_xd_parts(dict(units=units),300))[-1]),m3_xd_expected(units,a['tail']))
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,a['f2'])])
            now=rows[-1]['available_dt'];self.assertFalse(chan.scan_first_points(types,rows,now,'F2').points)
            self.assertFalse(any(chan.analyze_point_chain(types,rows,now,'F2')))
            self.assertEqual(case['paths']['xd-106']['completed'][0]['confirmed_raw_count'],a['legacy_first_raw'])
            self.assertNotEqual(a['legacy_first_raw'],a['f1_first']['fixed'][0])

    def test_open_recursive_candidate_has_explicit_b_c_and_never_evaluates_force(self):
        def forbidden(a,b):raise AssertionError('开放候选不得评估力度')
        for contract in ('current','fixed'):
            _,units,a,rows,given=e_consumer_input(contract);candidate=None
            sizes=list(range(1,9))+[sum(u['confirmed_raw_count']<=n for u in units) for n in range(1,301)]
            for size in sizes:
                if not size:continue
                now=given[size-1].confirmed_dt;scan=chan.scan_strict_divergence(given[:size],now,'auto-E-F1',forbidden,'guard')
                self.assertEqual(scan.completed_types,0)
                if size<8:
                    self.assertEqual((scan.results,tuple(r for _,r in scan.skipped)),((),(a['auto_reasons'][size-1],)))
                else:
                    r,=scan.results
                    self.assertEqual((r.status,r.reason,r.kind),('candidate','trend_open','sell1'))
                    self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in r.reference_ids),a['auto_reference'])
                    self.assertEqual(tuple(int(k.rsplit(':',1)[1]) for k in r.leave_ids),a['auto_leave'])
                    self.assertEqual(tuple(round(v*1000) for v in r.center_range),(887,1017))
                    self.assertEqual(dict(r.conditions),dict(trend=None,separated_centers=True,new_extreme=None,leave_third_point=None))
                    self.assertEqual((r.force_method,r.force_reference,r.force_leave),(None,None,None))
                    if candidate is not None:self.assertEqual(r,candidate)
                    candidate=r
                first=chan.scan_first_points(given[:size],rows,now,'auto-E-F1')
                self.assertEqual((first.points,first.exclusions,first.completed_types),([],(),0))
            self.assertEqual(m3_xd_shape(chan.level_up(given)[0]),m3_xd_expected(units,a['auto']))
            self.assertEqual(candidate.confirmed_dt,given[7].confirmed_dt)
            self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-E-F1')))

    def test_late_proof_batches_delay_F1_and_candidate_without_future_price_reads(self):
        for contract in ('current','fixed'):
            case,units,a,rows,given=e_consumer_input(contract);base=self._types(case,units,a,contract)
            arrivals=[m.confirmed_dt for m in given]
            for proof in (3,6):
                delayed=list(arrivals);late=arrivals[proof]+timedelta(days=1);delayed[proof]=late
                for i in range(proof+1,8):delayed[i]=max(arrivals[i],delayed[i-1])
                types=self._types(case,units,a,contract,delayed);target=0 if proof==3 else 1
                self.assertEqual(types[target].confirmed_dt,late)
                self.assertEqual(len(types[target].evidence_ids),5 if proof==3 else 7)
                self.assertEqual(len([t for t in types if t.confirmed_dt<late]),target)
                if target:self.assertEqual(types[0],base[0])
            late=given[7].confirmed_dt+timedelta(days=1);delayed=list(given);delayed[7]=given[7]._replace(confirmed_dt=late)
            before=chan.scan_strict_divergence(delayed,late-timedelta(microseconds=1),'auto-E-F1')
            self.assertEqual((before.results,tuple(r for _,r in before.skipped)),((),('no_compare_legs',)))
            after=chan.scan_strict_divergence(delayed,late,'auto-E-F1');r,=after.results
            self.assertEqual((r.status,r.confirmed_dt),('candidate',late))
            future=given[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=late+timedelta(days=10))
            self.assertEqual(chan.scan_strict_divergence(delayed+[future],late,'auto-E-F1'),after)
            self.assertFalse(any(chan.analyze_point_chain(delayed+[future],rows,late,'auto-E-F1')))


# G/X1实际合同的活动/固定时钟及给定链消费者；源起点资格与生产合入另验。
M3_GX_CLOCK_CONSUMERS_AUDIT = {'G': {'certificate_sha256': 'd02982b1a7eaaac60a7d2faaf74421098206e2cdbe9e974256a3d6233c5bc3ac',
       'auto': (0, 6, 'up', 'up', (0, 3), ((695, 842), (887, 1017)), None),
       'base_sha256': '3b6ce0c2152277e61359829b606c353af0bb1595f23d2b6e4bda02a9b4ba2082',
       'bounds': {'current': 267, 'fixed': 267},
       'candidates': {},
       'contracts': {'current': {'candidate_raw': (),
                                 'f1_evidence': (7,),
                                 'f1_first': (254,),
                                 'local': (59, 88, 175, 175, 230, 230, 254),
                                 'local_proofs': ((695, '2018-12-26', True),
                                                  (845, '2019-02-14', True),
                                                  (1017, '2019-06-24', True),
                                                  (1017, '2019-06-24', True),
                                                  (1024, '2019-09-09', True),
                                                  (1024, '2019-09-09', True),
                                                  (913, '2019-10-21', True)),
                                 'publication_proofs': ((695, '2018-12-26', True),
                                                        (845, '2019-02-14', True),
                                                        (1017, '2019-06-24', True),
                                                        (1017, '2019-06-24', True),
                                                        (1024, '2019-09-09', True),
                                                        (1024, '2019-09-09', True),
                                                        (913, '2019-10-21', True)),
                                 'published': (59, 88, 175, 175, 230, 230, 254)},
                     'fixed': {'candidate_raw': (),
                               'f1_evidence': (7,),
                               'f1_first': (267,),
                               'local': (65, 109, 179, 179, 239, 239, 267),
                               'local_proofs': ((695, '2018-12-26', False),
                                                (1185, '2019-03-07', False),
                                                (1017, '2019-06-24', False),
                                                (1017, '2019-06-24', False),
                                                (1039, '2019-09-16', False),
                                                (1039, '2019-09-16', False),
                                                (913, '2019-10-21', False)),
                               'publication_proofs': ((695, '2018-12-26', False),
                                                      (1185, '2019-03-07', False),
                                                      (1017, '2019-06-24', False),
                                                      (1017, '2019-06-24', False),
                                                      (1039, '2019-09-16', False),
                                                      (1039, '2019-09-16', False),
                                                      (913, '2019-10-21', False)),
                               'published': (65, 109, 179, 179, 239, 239, 267)}},
       'fixture_sha256': '3defd45833e0dd5339ffb43e6d3aad7cdf3617887961acedfee03df8204fec0f',
       'impact_contracts': ((15, 'all_current', 267), (16, 'fixed_without_active', 267)),
       'inherited_base': 0,
       'production_merged': False,
       'reasons': ('not_two_separated_centers',
                   'not_two_separated_centers',
                   'not_two_separated_centers',
                   'not_two_separated_centers',
                   'not_two_separated_centers',
                   'no_comparable_center_tail',
                   'no_comparable_center_tail'),
       'seed': 0,
       'source_origin_bridge_proven': False,
       'source_rows': 267,
       'spans': ((0, 2, 2), (3, 5, 6))},
 'X1': {'certificate_sha256': 'd02982b1a7eaaac60a7d2faaf74421098206e2cdbe9e974256a3d6233c5bc3ac',
        'auto': (0, 13, 'up', 'up', (0, 8), ((1687, 1744), (2079, 2402)), None),
        'base_sha256': '01833573244088a5ecadbf9e80354f25752b04b622fb29a17f4187a9eb2aabbf',
        'bounds': {'current': 1403, 'fixed': 1495},
        'candidates': {12: {'gap': 114, 'leave': (11,), 'leave_high': 2320, 'prior_high': 2678, 'reference': (7,)},
                       14: {'gap': 41, 'leave': (13,), 'leave_high': 2242, 'prior_high': 2678, 'reference': (7,)}},
        'contracts': {'current': {'candidate_raw': ((12, 1157), (14, 1393)),
                                  'f1_evidence': (4, 7, 11, 14),
                                  'f1_first': (431, 889, 1126, 1393),
                                  'local': (155,
                                            320,
                                            410,
                                            431,
                                            651,
                                            712,
                                            889,
                                            1126,
                                            1013,
                                            1082,
                                            1126,
                                            1157,
                                            1275,
                                            1393),
                                  'local_proofs': ((1736, '2024-02-21 14:00:00', True),
                                                   (1731, '2024-04-10 14:00:00', True),
                                                   (1860, '2024-05-09 14:00:00', True),
                                                   (1795, '2024-05-15 15:00:00', True),
                                                   (1674, '2024-07-17 15:00:00', True),
                                                   (1589, '2024-08-05 09:30:00', True),
                                                   (1649, '2024-09-25 11:30:00', True),
                                                   (2247, '2024-12-06 15:00:00', True),
                                                   (2316, '2024-11-06 10:30:00', True),
                                                   (2100, '2024-11-26 09:30:00', True),
                                                   (2247, '2024-12-06 15:00:00', True),
                                                   (2148, '2024-12-17 09:30:00', True),
                                                   (2077, '2025-01-20 14:00:00', True),
                                                   (2120, '2025-03-03 10:30:00', True)),
                                  'publication_proofs': ((1736, '2024-02-21 14:00:00', True),
                                                         (1731, '2024-04-10 14:00:00', True),
                                                         (1860, '2024-05-09 14:00:00', True),
                                                         (1795, '2024-05-15 15:00:00', True),
                                                         (1674, '2024-07-17 15:00:00', True),
                                                         (1589, '2024-08-05 09:30:00', True),
                                                         (1649, '2024-09-25 11:30:00', True),
                                                         (2247, '2024-12-06 15:00:00', True),
                                                         (2316, '2024-11-06 10:30:00', False),
                                                         (2079, '2024-11-27 10:30:00', False),
                                                         (2247, '2024-12-06 15:00:00', True),
                                                         (2148, '2024-12-17 09:30:00', True),
                                                         (2077, '2025-01-20 14:00:00', True),
                                                         (2120, '2025-03-03 10:30:00', True)),
                                  'published': (155,
                                                320,
                                                410,
                                                431,
                                                651,
                                                712,
                                                889,
                                                1126,
                                                1126,
                                                1126,
                                                1126,
                                                1157,
                                                1275,
                                                1393)},
                      'fixed': {'candidate_raw': ((12, 1165), (14, 1403)),
                                'f1_evidence': (4, 7, 11, 14),
                                'f1_first': (443, 893, 1138, 1403),
                                'local': (165,
                                          340,
                                          414,
                                          443,
                                          678,
                                          725,
                                          893,
                                          1138,
                                          1018,
                                          1100,
                                          1138,
                                          1165,
                                          1285,
                                          1403),
                                'local_proofs': ((1736, '2024-02-21 14:00:00', False),
                                                 (1711, '2024-04-15 09:30:00', False),
                                                 (1860, '2024-05-09 14:00:00', False),
                                                 (1791, '2024-05-17 10:30:00', False),
                                                 (1702, '2024-07-22 10:30:00', False),
                                                 (1576, '2024-08-05 15:00:00', False),
                                                 (1649, '2024-09-25 11:30:00', False),
                                                 (2320, '2024-12-10 09:30:00', False),
                                                 (2316, '2024-11-06 10:30:00', False),
                                                 (2079, '2024-11-27 10:30:00', False),
                                                 (2320, '2024-12-10 09:30:00', False),
                                                 (2148, '2024-12-17 09:30:00', False),
                                                 (2083, '2025-01-21 09:30:00', False),
                                                 (2120, '2025-03-03 10:30:00', False)),
                                'publication_proofs': ((1736, '2024-02-21 14:00:00', False),
                                                       (1711, '2024-04-15 09:30:00', False),
                                                       (1860, '2024-05-09 14:00:00', False),
                                                       (1791, '2024-05-17 10:30:00', False),
                                                       (1702, '2024-07-22 10:30:00', False),
                                                       (1576, '2024-08-05 15:00:00', False),
                                                       (1649, '2024-09-25 11:30:00', False),
                                                       (2320, '2024-12-10 09:30:00', False),
                                                       (2316, '2024-11-06 10:30:00', False),
                                                       (2079, '2024-11-27 10:30:00', False),
                                                       (2320, '2024-12-10 09:30:00', False),
                                                       (2148, '2024-12-17 09:30:00', False),
                                                       (2083, '2025-01-21 09:30:00', False),
                                                       (2120, '2025-03-03 10:30:00', False)),
                                'published': (165,
                                              340,
                                              414,
                                              443,
                                              678,
                                              725,
                                              893,
                                              1138,
                                              1138,
                                              1138,
                                              1138,
                                              1165,
                                              1285,
                                              1403)}},
        'fixture_sha256': '2c70070c2917c343cdfc182518996bb71bc8c0e6724c3482c22337fc9f337ad7',
        'impact_contracts': ((57, 'all_current', 1403), (58, 'fixed_without_active', 1495)),
        'inherited_base': 7,
        'production_merged': False,
        'reasons': ('not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'not_two_separated_centers',
                    'no_compare_legs',
                    'trend_open',
                    'no_compare_legs',
                    'trend_open'),
        'seed': 1,
        'source_origin_bridge_proven': False,
        'source_rows': 1495,
        'spans': ((0, 2, 7), (8, 10, 13))}}


def gx_consumer_input(key,contract):
    """复用既有G/X1组成，只绑定逐事件实际证明和本合同消费上限。"""
    base=M3_GAP_REVISION_AUDIT[key];a=M3_GX_CLOCK_CONSUMERS_AUDIT[key]
    digest=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    if digest!=a['base_sha256']:raise AssertionError('G/X1时钟须绑定同一既有修订组成')
    case,units=gap_revision_input(base);clock=a['contracts'][contract]
    for i,u in enumerate(units):u.update(local_raw_count=clock['local'][i],confirmed_raw_count=clock['published'][i])
    raw=case['raw_rows'][:a['bounds'][contract]]
    rows=m3_xd_rows(dict(raw_rows=[dict(r,dt=r['dt'][:10]) for r in raw])) if key=='G' else m3_xd_rows(dict(raw_rows=raw))
    root='GX-clock:'+key+':'+contract+':'+a['certificate_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           gap_revision_time(case,u['confirmed_raw_count'])) for i,u in enumerate(units)]
    return case,units,base,a,rows,given


class TestGxClockConsumers(unittest.TestCase):
    """给定G seed0、X1声明基底的实际活动/固定消费窗口，分开冻结完成项与候选。"""

    @staticmethod
    def _types(case,units,base,key,contract,arrivals=None):
        arrivals=arrivals or [gap_revision_time(case,u['confirmed_raw_count']) for u in units];out=[]
        for spec in base['f1']:
            known=max(arrivals[:spec[-1]+1]);width=sum(at<=known for at in arrivals)
            move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:width]),len(case['raw_rows'])))
                      if m.complete and m.seg_start==spec[0])
            out.append(m3_xd_type('GX-clock:'+key+':'+contract,move,units[:width],known))
        return out

    def test_actual_contract_windows_freeze_F1_batches_and_keep_F2_open(self):
        for key in ('G','X1'):
            for contract in ('current','fixed'):
                case,units,base,a,rows,_=gx_consumer_input(key,contract);first={};types=[]
                self.assertEqual(len(rows),a['bounds'][contract])
                for count in range(1,len(rows)+1):
                    visible=[u for u in units if u['confirmed_raw_count']<=count]
                    done=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
                    expected=[s for s in base['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                    self.assertEqual([m3_xd_shape(m) for m in done],[m3_xd_expected(units,s) for s in expected])
                    for m in done:
                        if m.seg_start not in first:
                            first[m.seg_start]=count;types.append(m3_xd_type('GX-clock:'+key+':'+contract,m,visible,rows[count-1]['available_dt']))
                    self.assertEqual(chan.confirm_level_up(types,rows[count-1]['available_dt'],'F2'),[])
                self.assertEqual(tuple(first[s[0]] for s in base['f1']),a['contracts'][contract]['f1_first'])
                self.assertEqual(tuple(len(t.evidence_ids) for t in types),a['contracts'][contract]['f1_evidence'])
                self.assertEqual(m3_xd_shape(chan.same_level_decompose(m3_xd_parts(dict(units=units),len(rows)))[-1]),m3_xd_expected(units,base['tail']))
                records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
                self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,s) for s in base['f2']])
                now=rows[-1]['available_dt'];self.assertFalse(chan.scan_first_points(types,rows,now,'F2').points)
                self.assertFalse(any(chan.analyze_point_chain(types,rows,now,'F2')))
                if key=='X1':
                    self.assertEqual((types[2].kind,types[2].direction),('consolidation','down'))
                    self.assertGreater(types[2].end_price,types[2].start_price)

    def test_recursive_finite_prefixes_keep_G_missing_tail_and_X1_open_candidates(self):
        def forbidden(a,b):raise AssertionError('候选或缺结构时不得评估力度')
        for key in ('G','X1'):
            for contract in ('current','fixed'):
                _,units,_,a,rows,given=gx_consumer_input(key,contract)
                for size in range(1,len(units)+1):
                    now=given[size-1].confirmed_dt;scan=chan.scan_strict_divergence(given[:size],now,'auto-GX-F1',forbidden,'guard')
                    self.assertEqual(scan.completed_types,0)
                    if size in a['candidates']:
                        c=a['candidates'][size];r,=scan.results
                        self.assertEqual((r.status,r.reason,r.kind),('candidate','trend_open','sell1'))
                        self.assertEqual(tuple(int(i.rsplit(':',1)[1]) for i in r.reference_ids),c['reference'])
                        self.assertEqual(tuple(int(i.rsplit(':',1)[1]) for i in r.leave_ids),c['leave'])
                        self.assertEqual(tuple(round(v*1000) for v in r.center_range),(2079,2402))
                        self.assertEqual(dict(r.conditions),dict(trend=None,separated_centers=True,new_extreme=None,leave_third_point=None))
                        self.assertEqual((r.force_method,r.force_reference,r.force_leave),(None,None,None))
                    else:self.assertEqual((scan.results,tuple(v for _,v in scan.skipped)),((),(a['reasons'][size-1],)))
                    first=chan.scan_first_points(given[:size],rows,now,'auto-GX-F1')
                    self.assertEqual((first.points,first.exclusions,first.completed_types),([],(),0))
                self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,a['auto'])])
                self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-GX-F1')))

    def test_X1_parent_four_unit_batch_keeps_local_proofs_and_delays_only_third_F1(self):
        for contract in ('current','fixed'):
            case,units,base,a,_,given=gx_consumer_input('X1',contract);clock=a['contracts'][contract]
            self.assertEqual(clock['published'][7:11],(1126,)*4 if contract=='current' else (1138,)*4)
            self.assertLess(clock['local'][8],clock['published'][8]);self.assertLess(clock['local'][9],clock['published'][9])
            self.assertEqual([u['proof_bi'] for u in units[7:11]],[84,74,81,84])
            arrivals=[u.confirmed_dt for u in given];late=arrivals[7]+timedelta(days=1);delayed=list(arrivals);delayed[7]=late
            for i in range(8,len(delayed)):delayed[i]=max(arrivals[i],delayed[i-1])
            base_types=self._types(case,units,base,'X1',contract);types=self._types(case,units,base,'X1',contract,delayed)
            self.assertEqual(types[:2],base_types[:2])
            self.assertEqual((types[2].confirmed_dt,len(types[2].evidence_ids)),(late,11))
            self.assertEqual(len([t for t in types if t.confirmed_dt<late]),2)
            self.assertEqual(delayed[7:11],[late]*4)
            self.assertEqual(tuple(units[i]['local_raw_count'] for i in (8,9)),clock['local'][8:10])

    def test_X1_candidate_disappearance_is_not_a_completed_result_rewrite(self):
        for contract in ('current','fixed'):
            _,units,_,a,rows,given=gx_consumer_input('X1',contract)
            first,=chan.scan_strict_divergence(given,given[11].confirmed_dt,'auto-GX-F1').results
            snapshot=first.to_dict()
            middle=chan.scan_strict_divergence(given,given[12].confirmed_dt,'auto-GX-F1')
            self.assertEqual((middle.results,tuple(v for _,v in middle.skipped)),((),('no_compare_legs',)))
            last,=chan.scan_strict_divergence(given,given[13].confirmed_dt,'auto-GX-F1').results
            self.assertEqual(first.divergence_id,last.divergence_id)
            self.assertNotEqual(first.leave_ids,last.leave_ids)
            self.assertEqual(first.to_dict(),snapshot)
            late=given[13].confirmed_dt+timedelta(days=1);delayed=list(given);delayed[13]=given[13]._replace(confirmed_dt=late)
            self.assertEqual(chan.scan_strict_divergence(delayed,late-timedelta(microseconds=1),'auto-GX-F1').results,())
            after=chan.scan_strict_divergence(delayed,late,'auto-GX-F1');point,=after.results
            self.assertEqual((point.status,point.confirmed_dt),('candidate',late))
            future=given[-1]._replace(move_id=None,level=None,high=float('nan'),confirmed_dt=late+timedelta(days=10))
            self.assertEqual(chan.scan_strict_divergence(delayed+[future],late,'auto-GX-F1'),after)
            self.assertFalse(any(chan.analyze_point_chain(delayed+[future],rows,late,'auto-GX-F1')))


# G1给定BI35后共同后缀的实际活动窗消费者；不继承原链点位与源起点资格。
M3_G1_CONSUMERS_AUDIT = {'certificate_sha256': '8a26b8b4a8c4bed25d72e2b593881d41e6efb6ac49a614cbf5732a0e79b5d8c8',
 'actual_observations': ((125, 0, 0), (126, 0, 0), (1623, 8, 2)),
 'auto': (0, 7, 'consolidation', None, (0,), ((1027, 1066),), None),
 'auto_spans': ((0, 2, 6),),
 'base_sha256': 'e5676d07d13f1170922f18866c63c3f9b68e560281626778fe53703893fd241e',
 'contract': 'all_current',
 'events': ((35, 49, 2, 63),
            (50, 60, 1, 63),
            (61, 63, 1, 66),
            (64, 76, 1, 79),
            (77, 89, 1, 94),
            (90, 100, 2, 126),
            (101, 123, 1, 126),
            (124, 126, 1, 129)),
 'f1': ((0, 2, 'consolidation', None, (0,), ((1027, 1066),), 3),
        (3, 5, 'consolidation', None, (3,), ((1022, 1066),), 6)),
 'f1_evidence': (4, 7),
 'f1_first': (924, 1540),
 'f2': ((0, 1, 'incomplete', None, (), (), None),),
 'fixture': 'real_causal_formation.json',
 'fixture_sha256': '6e72f6931e6cbe957ee40d184c51ab0bf9a666aefd6f9c521333343b7e3dbf5b',
 'id': '588000-30m-20220801-20230501',
 'impact_contract': (0, 'all_current', 1623),
 'limit': 1623,
 'packet_sha256': '35e7a15319477a7628edf2ac1a8869969a60534ed632db8535b2d3fb1978a009',
 'prior_receipt_sha256': '675b97d6eb3b08263428c4c5b91fa31f41f7f7893a62a37d8a92475dff9adbe7',
 'production_merged': False,
 'publication_proofs': ((1056, '2022-12-01 15:00:00', True),
                        (1056, '2022-12-01 15:00:00', True),
                        (1044, '2022-12-07 10:00:00', True),
                        (1011, '2022-12-29 11:30:00', True),
                        (1048, '2023-02-09 10:00:00', True),
                        (1155, '2023-04-13 11:00:00', True),
                        (1141, '2023-04-13 15:00:00', True),
                        (1206, '2023-04-20 11:00:00', True)),
 'seed': 35,
 'seed0_seed1_resolved': False,
 'source_origin_bridge_proven': False,
 'source_rows': 1638,
 'tail': (6, 7, 'incomplete', None, (), (), None),
 'units': (('up', '2022-10-12 10:30:00', '2022-11-04 15:00:00', 910, 1126, 910, 1126, 2, 63, 748, 748),
           ('down', '2022-11-04 15:00:00', '2022-11-28 10:00:00', 1126, 1027, 1027, 1126, 1, 63, 748, 748),
           ('up', '2022-11-28 10:00:00', '2022-12-02 10:30:00', 1027, 1066, 1027, 1066, 1, 66, 777, 777),
           ('down', '2022-12-02 10:30:00', '2022-12-23 14:30:00', 1066, 954, 954, 1066, 1, 79, 924, 924),
           ('up', '2022-12-23 14:30:00', '2023-01-30 10:00:00', 954, 1093, 954, 1093, 1, 94, 1137, 1137),
           ('down', '2023-01-30 10:00:00', '2023-02-20 10:00:00', 1093, 1022, 1022, 1093, 2, 126, 1535, 1535),
           ('up', '2023-02-20 10:00:00', '2023-04-10 10:30:00', 1022, 1216, 1022, 1216, 1, 126, 1540, 1540),
           ('down', '2023-04-10 10:30:00', '2023-04-14 10:30:00', 1216, 1139, 1139, 1216, 1, 129, 1580, 1580)),
 'visible_sizes': (0, 2, 3, 4, 5, 6, 7, 8)}


def g1_consumer_input():
    """只消费G1登记的1623行活动窗，给定BI35起段；不继承旧点位。"""
    a=M3_G1_CONSUMERS_AUDIT;case,units=gap_revision_input(a)
    rows=m3_xd_rows(dict(raw_rows=case['raw_rows'][:a['limit']]))
    root='G1-given35:'+a['certificate_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           rows[u['confirmed_raw_count']-1]['available_dt']) for i,u in enumerate(units)]
    return case,units,a,rows,given


class TestG1BoundedConsumers(unittest.TestCase):
    """G1共同后缀的同级两项F1与单核心自动递归分开，实际合同仅all_current。"""

    @staticmethod
    def _types(units,a,arrivals):
        out=[]
        for spec in a['f1']:
            known=max(arrivals[:spec[-1]+1]);width=sum(at<=known for at in arrivals)
            move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:width]),a['limit']))
                      if m.complete and m.seg_start==spec[0])
            out.append(m3_xd_type('G1-given35:'+a['certificate_sha256'],move,units[:width],known))
        return out

    def test_actual_prefixes_freeze_two_F1_at_separate_proofs_and_keep_F2_incomplete(self):
        _,units,a,rows,_=g1_consumer_input();first={};types=[];prior=[]
        self.assertEqual(len(rows),1623)
        for count in range(1,len(rows)+1):
            visible=[u for u in units if u['confirmed_raw_count']<=count]
            done=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
            expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
            shapes=[m3_xd_shape(m) for m in done]
            self.assertEqual(shapes,[m3_xd_expected(units,s) for s in expected]);self.assertEqual(shapes[:len(prior)],prior);prior=shapes
            for m in done:
                if m.seg_start not in first:
                    first[m.seg_start]=count;types.append(m3_xd_type('G1-given35:'+a['certificate_sha256'],m,visible,rows[count-1]['available_dt']))
            self.assertEqual(chan.confirm_level_up(types,rows[count-1]['available_dt'],'F2'),[])
        self.assertEqual(tuple(first[s[0]] for s in a['f1']),a['f1_first'])
        self.assertEqual(tuple(len(t.evidence_ids) for t in types),a['f1_evidence'])
        self.assertEqual(tuple((round(t.low*1000),round(t.high*1000)) for t in types),((910,1126),(954,1093)))
        self.assertEqual(tuple(t.unit_ids for t in types),tuple(tuple('G1-given35:'+a['certificate_sha256']+':xd:'+str(i) for i in range(s[0],s[1]+1)) for s in a['f1']))
        records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
        self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,s) for s in a['f2']])
        self.assertEqual(m3_xd_shape(chan.same_level_decompose(m3_xd_parts(dict(units=units),len(rows)))[-1]),m3_xd_expected(units,a['tail']))
        self.assertFalse(chan.scan_first_points(types,rows,rows[-1]['available_dt'],'F2').points)
        self.assertFalse(any(chan.analyze_point_chain(types,rows,rows[-1]['available_dt'],'F2')))

    def test_recursive_single_center_never_becomes_a_strict_or_auxiliary_first_point(self):
        def forbidden(a,b):raise AssertionError('单中枢开放走势不得评估严格力度')
        case,units,a,rows,given=g1_consumer_input()
        for size in range(1,len(given)+1):
            now=given[size-1].confirmed_dt;scan=chan.scan_strict_divergence(given[:size],now,'auto-G1-F1',forbidden,'guard')
            self.assertEqual((scan.completed_types,scan.results,tuple(r for _,r in scan.skipped)),(0,(),('not_two_separated_centers',)))
            auxiliary=chan.scan_first_points(given[:size],rows,now,'auto-G1-F1')
            self.assertEqual((auxiliary.points,auxiliary.exclusions,auxiliary.completed_types),([],(),0))
        self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,a['auto'])])
        self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-G1-F1')))
        historical=case['first_point']
        self.assertLess(historical['first_raw_count'],units[0]['confirmed_raw_count'])
        self.assertLess(date(historical['first_dt']),given[0].start_dt)
        self.assertEqual(historical['side'],'sell1')
        self.assertFalse(a['source_origin_bridge_proven']);self.assertFalse(a['seed0_seed1_resolved'])

    def test_shared_BI126_keeps_distinct_arrivals_and_late_proofs_delay_only_their_F1(self):
        _,units,a,rows,given=g1_consumer_input();arrivals=[g.confirmed_dt for g in given];base=self._types(units,a,arrivals)
        self.assertEqual((units[5]['proof_bi'],units[6]['proof_bi']),(126,126))
        self.assertEqual((units[5]['mode'],units[6]['mode']),(2,1))
        self.assertLess(arrivals[5],arrivals[6]);self.assertEqual(tuple(units[i]['confirmed_raw_count'] for i in (5,6)),(1535,1540))
        before=[m for m in chan.same_level_decompose(given[:6]) if m.complete]
        self.assertEqual(len(before),1)
        for proof in (3,6):
            late=arrivals[proof]+timedelta(days=1);delayed=list(arrivals);delayed[proof]=late
            for i in range(proof+1,len(delayed)):delayed[i]=max(delayed[i-1],arrivals[i])
            after=self._types(units,a,delayed);target=0 if proof==3 else 1
            self.assertEqual((after[target].confirmed_dt,len(after[target].evidence_ids)),(late,a['f1_evidence'][target]))
            if target:self.assertEqual(after[0],base[0])
        late_tail=arrivals[7]+timedelta(days=1);delayed=list(arrivals);delayed[7]=late_tail
        self.assertEqual(self._types(units,a,delayed),base)
        now=rows[-1]['available_dt'];future=given[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=now+timedelta(days=10))
        self.assertEqual(chan.scan_strict_divergence(given+[future],now,'auto-G1-F1'),chan.scan_strict_divergence(given,now,'auto-G1-F1'))
        poisoned=[dict(r) for r in rows]+[dict(dt=now+timedelta(days=10),closed_dt=now+timedelta(days=10),available_dt=now+timedelta(days=11),high=float('nan'))]
        self.assertEqual(chan.scan_first_points(given+[future],poisoned,now,'auto-G1-F1'),chan.scan_first_points(given,rows,now,'auto-G1-F1'))
        self.assertFalse(any(chan.analyze_point_chain(given+[future],poisoned,now,'auto-G1-F1')))


# S3/T实际窗口中的给定种子完整后缀；自然反应、第二序列和下游递归分别验收。
M3_EXPANDED_SUFFIX_AUDIT = {'S3': {'certificate_sha256': '16ed57fbacc688fdc552b82ad16ee41b820fe3ea3db5de8eaffe9ecbae2d0161',
        'auto': ((0, 4, 'consolidation', None, (0,), ((3579, 3745),), 5),
                 (5, 11, 'consolidation', None, (5,), ((4488, 4642),), None)),
        'auto_spans': (((0, 2, 3),), ((5, 7, 9),)),
        'base_sha256': '6f5937fccba040a44929a2a6fcc8b78e12b078272b02cefc9eb41229ef76d2de',
        'bounds': {'current': 1349, 'fixed': 1350},
        'clocks': {'current': {'auto_evidence': 6,
                               'auto_first': 701,
                               'f1_evidence': (4, 10),
                               'f1_first': (329, 826),
                               'local': (141, 232, 246, 329, 348, 701, 726, 745, 771, 826, 900, 1344),
                               'publication_proofs': ((3730, '2021-07-30 00:00:00', True),
                                                      (3550, '2021-12-15 00:00:00', True),
                                                      (3643, '2022-01-05 00:00:00', True),
                                                      (3845, '2022-05-16 00:00:00', True),
                                                      (3942, '2022-06-13 00:00:00', True),
                                                      (4488, '2023-11-23 00:00:00', True),
                                                      (4687, '2023-12-28 00:00:00', True),
                                                      (4602, '2024-01-25 00:00:00', True),
                                                      (4921, '2024-03-11 00:00:00', True),
                                                      (5274, '2024-06-03 00:00:00', True),
                                                      (5626, '2024-09-18 00:00:00', True),
                                                      (8614, '2026-07-22 00:00:00', True)),
                               'published': (141, 232, 246, 329, 348, 701, 726, 745, 771, 826, 900, 1344)},
                   'fixed': {'auto_evidence': 6,
                             'auto_first': 705,
                             'f1_evidence': (4, 10),
                             'f1_first': (334, 830),
                             'local': (149, 239, 256, 334, 355, 705, 730, 751, 776, 830, 911, 1349),
                             'publication_proofs': ((3730, '2021-07-30 00:00:00', False),
                                                    (3550, '2021-12-15 00:00:00', False),
                                                    (3658, '2022-01-13 00:00:00', False),
                                                    (3834, '2022-05-18 00:00:00', False),
                                                    (3942, '2022-06-13 00:00:00', False),
                                                    (4488, '2023-11-23 00:00:00', False),
                                                    (4687, '2023-12-28 00:00:00', False),
                                                    (4602, '2024-01-25 00:00:00', False),
                                                    (4921, '2024-03-11 00:00:00', False),
                                                    (5274, '2024-06-03 00:00:00', False),
                                                    (5771, '2024-09-26 00:00:00', False),
                                                    (8614, '2026-07-22 00:00:00', False)),
                             'published': (149, 239, 256, 334, 355, 705, 730, 751, 776, 830, 911, 1349)}},
        'events': ((10, 12, 1, 15),
                   (13, 23, 1, 26),
                   (24, 26, 1, 29),
                   (27, 35, 1, 42),
                   (36, 42, 1, 45),
                   (43, 81, 1, 84),
                   (82, 84, 1, 87),
                   (85, 87, 1, 90),
                   (88, 90, 1, 93),
                   (91, 97, 1, 100),
                   (98, 104, 1, 111),
                   (105, 149, 2, 163)),
        'f1': ((0, 2, 'consolidation', None, (0,), ((3579, 3745),), 3),
               (3, 8, 'up', 'up', (3, 6), ((3792, 4077), (4602, 4642)), 9)),
        'f2': ((0, 1, 'incomplete', None, (), (), None),),
        'fixture': 'real_strict_trend.json',
        'fixture_sha256': 'ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        'id': '518880-day-20210101-20260731',
        'impact_contracts': ((6, 'all_current', 1349), (7, 'fixed_without_active', 1350)),
        'natural_reaction': (37, 39, 1, 42),
        'parent_gap': (105, 150, 328, 163),
        'pending_gap': (150, 161, 319, 163, None),
        'pending_reaction': (154, 161, 745, 163, None),
        'prior_certificate_sha256': 'b1a50900e1ffcbc03c5e2cc20d83da300da04d1c5c81824783e4fe35b9a72520',
        'production_merged': False,
        'rejected': {91: {94: 95, 96: 97},
                     98: {101: 102, 103: 104},
                     105: {112: 113, 114: 119, 120: 123, 124: 125, 126: 139, 140: 147, 148: 149}},
        'seed': 10,
        'source_origin_bridge_proven': False,
        'tail': (9, 11, 'consolidation', None, (9,), ((5231, 5586),), None),
        'units': (('down', '2021-05-26 00:00:00', '2021-06-30 00:00:00', 3865, 3579, 3579, 3865, 1, 15),
                  ('up', '2021-06-30 00:00:00', '2021-11-18 00:00:00', 3579, 3745, 3541, 3745, 1, 26),
                  ('down', '2021-11-18 00:00:00', '2021-12-15 00:00:00', 3745, 3550, 3550, 3745, 1, 29),
                  ('up', '2021-12-15 00:00:00', '2022-03-09 00:00:00', 3550, 4077, 3550, 4077, 1, 42),
                  ('down', '2022-03-09 00:00:00', '2022-05-18 00:00:00', 4077, 3834, 3792, 4077, 1, 45),
                  ('up', '2022-05-18 00:00:00', '2023-10-31 00:00:00', 3834, 4642, 3615, 4642, 1, 84),
                  ('down', '2023-10-31 00:00:00', '2023-11-23 00:00:00', 4642, 4488, 4488, 4642, 1, 87),
                  ('up', '2023-11-23 00:00:00', '2023-12-28 00:00:00', 4488, 4687, 4488, 4687, 1, 90),
                  ('down', '2023-12-28 00:00:00', '2024-01-25 00:00:00', 4687, 4602, 4602, 4687, 1, 93),
                  ('up', '2024-01-25 00:00:00', '2024-05-20 00:00:00', 4602, 5586, 4602, 5586, 1, 100),
                  ('down', '2024-05-20 00:00:00', '2024-06-27 00:00:00', 5586, 5231, 5231, 5586, 1, 111),
                  ('up', '2024-06-27 00:00:00', '2026-01-29 00:00:00', 5231, 11977, 5231, 11977, 2, 163))},
 'T': {'certificate_sha256': '510e5f8792e4f7bd984523e64f6331dca9d3c0774d38b2ad180562a6cb517e7e',
       'auto': ((0, 1, 'incomplete', None, (), (), None),),
       'auto_spans': ((),),
       'base_sha256': '1ed1e29c9eb26032aedeaea9dee7ac4e8b9b3f092e5308082ddbd18cbf4c4f3d',
       'bounds': {'current': 679},
       'clocks': {'current': {'auto_evidence': None,
                              'auto_first': None,
                              'f1_evidence': (),
                              'f1_first': (),
                              'local': (370, 586),
                              'publication_proofs': ((1088, '2022-07-13 00:00:00', True),
                                                     (1113, '2023-06-05 00:00:00', True)),
                              'published': (370, 586)}},
       'events': ((22, 30, 2, 38), (31, 39, 1, 59)),
       'f1': (),
       'f2': (),
       'fixture': 'real_third_point_margin0.json',
       'fixture_sha256': '64c4f4b80eca2f31f262b86c26523ddc9c13d59195ca33a5c5aa5904460c0217',
       'id': '588000-day-20210101-20231231',
       'impact_contracts': ((8, 'all_current', 679),),
       'incomplete_start': 67,
       'natural_reaction': (41, 53, 2, 59),
       'pending_owner': 40,
       'production_merged': False,
       'rejected': {57: 62, 61: 62, 63: 64, 65: 66},
       'seed': 22,
       'source_origin_bridge_proven': False,
       'source_rows': 726,
       'tail': (0, 1, 'incomplete', None, (), (), None),
       'units': (('down', '2021-11-24 00:00:00', '2022-04-27 00:00:00', 1545, 890, 890, 1545, 2, 38),
                 ('up', '2022-04-27 00:00:00', '2022-08-11 00:00:00', 890, 1230, 890, 1230, 1, 59))}}


def expanded_suffix_input(key,contract):
    """仅适配已独立冻结的S3/T给定后缀；实际窗口和日线到达约定显式保留。"""
    a=M3_EXPANDED_SUFFIX_AUDIT[key];clock=a['clocks'][contract]
    spec=dict(a,units=[tuple(u)+(clock['local'][i],clock['published'][i]) for i,u in enumerate(a['units'])])
    case,units=gap_revision_input(spec);raw=case['raw_rows'][:a['bounds'][contract]]
    rows=m3_xd_rows(dict(raw_rows=[dict(r,dt=r['dt'][:10]) for r in raw]))
    root='expanded:'+key+':'+contract+':'+a['certificate_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           rows[u['confirmed_raw_count']-1]['available_dt']) for i,u in enumerate(units)]
    return case,units,a,rows,given


class TestExpandedSuffixConsumers(unittest.TestCase):
    """S3给seed10、T日线给seed22；完整给定后缀不等于源起点自然桥接。"""

    def test_actual_windows_freeze_same_level_F1_and_leave_F2_unfinished(self):
        total=0
        for key,audit in M3_EXPANDED_SUFFIX_AUDIT.items():
            for contract in audit['bounds']:
                _,units,a,rows,_=expanded_suffix_input(key,contract);first={};types=[];previous=[]
                for count in range(1,len(rows)+1):
                    total+=1;visible=[u for u in units if u['confirmed_raw_count']<=count]
                    done=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
                    shapes=[m3_xd_shape(m) for m in done];expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                    self.assertEqual(shapes,[m3_xd_expected(units,s) for s in expected]);self.assertEqual(shapes[:len(previous)],previous);previous=shapes
                    for m in done:
                        if m.seg_start not in first:
                            first[m.seg_start]=count;types.append(m3_xd_type(key+':'+contract,m,visible,rows[count-1]['available_dt']))
                    self.assertEqual(chan.confirm_level_up(types,rows[count-1]['available_dt'],'F2'),[])
                c=a['clocks'][contract];self.assertEqual(tuple(first[s[0]] for s in a['f1']),c['f1_first'])
                self.assertEqual(tuple(len(t.evidence_ids) for t in types),c['f1_evidence'])
                self.assertEqual(m3_xd_shape(chan.same_level_decompose(m3_xd_parts(dict(units=units),len(rows)))[-1]),m3_xd_expected(units,a['tail']))
                records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
                self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,s) for s in a['f2']])
                self.assertFalse(any(chan.analyze_point_chain(types,rows,rows[-1]['available_dt'],'F2')))
        self.assertEqual(total,3378)

    def test_auto_consolidation_and_open_tail_are_not_strict_trend_or_point_rejections(self):
        def forbidden(a,b):raise AssertionError('盘整或开放尾不评估严格趋势力度')
        for key,audit in M3_EXPANDED_SUFFIX_AUDIT.items():
            for contract in audit['bounds']:
                _,units,a,rows,given=expanded_suffix_input(key,contract);snapshot=None
                for size in range(1,len(given)+1):
                    now=given[size-1].confirmed_dt;expected=int(key=='S3' and size>5)
                    scan=chan.scan_strict_divergence(given[:size],now,'auto-expanded-F1',forbidden,'guard')
                    self.assertEqual((scan.completed_types,scan.results),(expected,()))
                    self.assertEqual(tuple(r for _,r in scan.skipped),('not_trend','not_two_separated_centers') if expected else ('not_two_separated_centers',))
                    types=chan.confirm_level_up(given[:size],now,'auto-expanded-F1')
                    if types:
                        if snapshot is None:snapshot=types[0]
                        self.assertEqual(types[0],snapshot);self.assertEqual((snapshot.kind,len(snapshot.evidence_ids)),('consolidation',6))
                    first=chan.scan_first_points(given[:size],rows,now,'auto-expanded-F1')
                    self.assertEqual((first.points,tuple(r for _,r in first.exclusions),first.completed_types),([],('not_trend',) if expected else (),expected))
                self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,s) for s in a['auto']])
                self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-expanded-F1')))
                self.assertFalse(a['source_origin_bridge_proven']);self.assertFalse(a['production_merged'])

    def test_late_auto_proof_is_frozen_separately_and_future_identity_prices_are_unread(self):
        for key,audit in M3_EXPANDED_SUFFIX_AUDIT.items():
            for contract in audit['bounds']:
                _,_,_,rows,given=expanded_suffix_input(key,contract);now=rows[-1]['available_dt']
                if key=='S3':
                    late=given[5].confirmed_dt+timedelta(days=1);delayed=list(given);delayed[5]=given[5]._replace(confirmed_dt=late)
                    self.assertEqual(chan.confirm_level_up(delayed,late-timedelta(microseconds=1),'auto-expanded-F1'),[])
                    after,=chan.confirm_level_up(delayed,late,'auto-expanded-F1')
                    self.assertEqual((after.confirmed_dt,len(after.evidence_ids)),(late,6))
                    base,=chan.confirm_level_up(given,now,'auto-expanded-F1')
                    late_tail=list(given);late_tail[-1]=given[-1]._replace(confirmed_dt=now+timedelta(days=1))
                    self.assertEqual(chan.confirm_level_up(late_tail,now,'auto-expanded-F1'),[base])
                future=given[-1]._replace(move_id=None,level=None,high=float('nan'),confirmed_dt=now+timedelta(days=10))
                self.assertEqual(chan.scan_strict_divergence(given+[future],now,'auto-expanded-F1'),chan.scan_strict_divergence(given,now,'auto-expanded-F1'))
                poisoned=rows+[dict(dt=now+timedelta(days=10),closed_dt=now+timedelta(days=10),available_dt=now+timedelta(days=11),high=float('nan'))]
                self.assertEqual(chan.scan_first_points(given+[future],poisoned,now,'auto-expanded-F1'),chan.scan_first_points(given,rows,now,'auto-expanded-F1'))
                self.assertFalse(any(chan.analyze_point_chain(given+[future],poisoned,now,'auto-expanded-F1')))


# M1给seed38的实际双合同完整后缀；264与266的不同起点证书分别保留。
M3_M1_FULL_SUFFIX_AUDIT = {'certificate_sha256': '203d72ee106711ff44e535492735200f5914bbe6f3f23e447a4d899fa41f7562',
 'auto': ((0, 5, 'consolidation', 'up', (1,), ((902, 944),), 8),
          (6, 27, 'up', 'up', (6, 15), ((753, 821), (985, 1118)), None)),
 'auto_spans': (((1, 3, 5),), ((6, 8, 14), (15, 17, 27))),
 'base_sha256': '23dc9fcf57833c2f36a51814ef97ca2576ec377a3bd33673113402eabb24d1f0',
 'bounds': {'current': 3942, 'fixed': 3978},
 'candidates': {19: {'gap': 48, 'leave': (18,), 'leave_high': 1136, 'prior_high': 1202, 'reference': (14,)},
                21: {'gap': 48, 'leave': (20,), 'leave_high': 1117, 'prior_high': 1202, 'reference': (14,)},
                23: {'gap': 48, 'leave': (22,), 'leave_high': 1099, 'prior_high': 1202, 'reference': (14,)},
                25: {'gap': 48, 'leave': (24,), 'leave_high': 1048, 'prior_high': 1202, 'reference': (14,)},
                27: {'gap': 48, 'leave': (26,), 'leave_high': 1100, 'prior_high': 1202, 'reference': (14,)}},
 'clocks': {'current': {'auto_evidence': 9,
                        'auto_first': 2226,
                        'candidate_raw': ((19, 3360), (21, 3544), (23, 3665), (25, 3815), (27, 3908)),
                        'f1_evidence': (5, 9, 12, 16, 18, 21, 25, 27),
                        'f1_first': (1236, 2226, 2593, 3188, 3317, 3544, 3815, 3908),
                        'local': (637,
                                  930,
                                  1011,
                                  1123,
                                  1236,
                                  1754,
                                  1895,
                                  2144,
                                  2226,
                                  2349,
                                  2464,
                                  2593,
                                  2721,
                                  3068,
                                  3188,
                                  3188,
                                  3317,
                                  3317,
                                  3360,
                                  3461,
                                  3544,
                                  3665,
                                  3665,
                                  3815,
                                  3815,
                                  3831,
                                  3908,
                                  3936),
                        'publication_proofs': ((963, '2023-08-14 13:30:00', True),
                                               (930, '2023-09-28 10:00:00', True),
                                               (906, '2023-10-19 10:00:00', True),
                                               (936, '2023-11-06 13:30:00', True),
                                               (907, '2023-11-23 10:00:00', True),
                                               (806, '2024-02-21 14:00:00', True),
                                               (845, '2024-03-14 11:00:00', True),
                                               (774, '2024-04-25 09:30:00', True),
                                               (793, '2024-05-13 10:00:00', True),
                                               (781, '2024-05-30 14:30:00', True),
                                               (783, '2024-06-19 13:30:00', True),
                                               (745, '2024-07-09 15:00:00', True),
                                               (733, '2024-07-30 10:00:00', True),
                                               (698, '2024-09-24 14:00:00', True),
                                               (1094, '2024-10-21 09:30:00', True),
                                               (1094, '2024-10-21 09:30:00', True),
                                               (1129, '2024-11-08 11:00:00', True),
                                               (1129, '2024-11-08 11:00:00', True),
                                               (1062, '2024-11-15 10:00:00', True),
                                               (1075, '2024-12-02 11:00:00', True),
                                               (1042, '2024-12-13 13:30:00', True),
                                               (997, '2025-01-03 09:30:00', True),
                                               (997, '2025-01-03 09:30:00', True),
                                               (1012, '2025-01-27 14:00:00', True),
                                               (1012, '2025-01-27 14:00:00', True),
                                               (1069, '2025-02-06 11:30:00', True),
                                               (1062, '2025-02-19 09:30:00', True),
                                               (1171, '2025-02-24 10:00:00', True)),
                        'published': (637,
                                      930,
                                      1011,
                                      1123,
                                      1236,
                                      1754,
                                      1895,
                                      2144,
                                      2226,
                                      2349,
                                      2464,
                                      2593,
                                      2721,
                                      3068,
                                      3188,
                                      3188,
                                      3317,
                                      3317,
                                      3360,
                                      3461,
                                      3544,
                                      3665,
                                      3665,
                                      3815,
                                      3815,
                                      3831,
                                      3908,
                                      3936)},
            'fixed': {'auto_evidence': 9,
                      'auto_first': 2235,
                      'candidate_raw': ((19, 3391), (21, 3572), (23, 3692), (25, 3822), (27, 3913)),
                      'f1_evidence': (5, 9, 12, 16, 18, 21, 25, 27),
                      'f1_first': (1244, 2235, 2609, 3198, 3323, 3572, 3822, 3913),
                      'local': (642,
                                943,
                                1017,
                                1143,
                                1244,
                                1757,
                                1919,
                                2153,
                                2235,
                                2360,
                                2472,
                                2609,
                                2739,
                                3081,
                                3198,
                                3198,
                                3323,
                                3323,
                                3391,
                                3467,
                                3572,
                                3692,
                                3692,
                                3822,
                                3822,
                                3849,
                                3913,
                                3942),
                      'publication_proofs': ((963, '2023-08-14 13:30:00', False),
                                             (934, '2023-09-28 14:30:00', False),
                                             (906, '2023-10-19 10:00:00', False),
                                             (950, '2023-11-08 11:30:00', False),
                                             (907, '2023-11-23 10:00:00', False),
                                             (806, '2024-02-21 14:00:00', False),
                                             (833, '2024-03-15 14:00:00', False),
                                             (775, '2024-04-25 11:30:00', False),
                                             (793, '2024-05-13 10:00:00', False),
                                             (786, '2024-05-31 10:30:00', False),
                                             (783, '2024-06-19 13:30:00', False),
                                             (758, '2024-07-11 10:30:00', False),
                                             (733, '2024-07-30 10:00:00', False),
                                             (718, '2024-09-25 10:30:00', False),
                                             (1118, '2024-10-21 13:30:00', False),
                                             (1118, '2024-10-21 13:30:00', False),
                                             (1129, '2024-11-08 11:00:00', False),
                                             (1129, '2024-11-08 11:00:00', False),
                                             (1010, '2024-11-19 14:00:00', False),
                                             (1075, '2024-12-02 11:00:00', False),
                                             (1016, '2024-12-17 13:30:00', False),
                                             (981, '2025-01-06 15:00:00', False),
                                             (981, '2025-01-06 15:00:00', False),
                                             (1008, '2025-01-27 15:00:00', False),
                                             (1008, '2025-01-27 15:00:00', False),
                                             (1093, '2025-02-07 13:30:00', False),
                                             (1062, '2025-02-19 09:30:00', False),
                                             (1171, '2025-02-24 10:00:00', False)),
                      'published': (642,
                                    943,
                                    1017,
                                    1143,
                                    1244,
                                    1757,
                                    1919,
                                    2153,
                                    2235,
                                    2360,
                                    2472,
                                    2609,
                                    2739,
                                    3081,
                                    3198,
                                    3198,
                                    3323,
                                    3323,
                                    3391,
                                    3467,
                                    3572,
                                    3692,
                                    3692,
                                    3822,
                                    3822,
                                    3849,
                                    3913,
                                    3942)}},
 'events': ((38, 40, 1, 43),
            (41, 67, 1, 72),
            (68, 76, 1, 79),
            (77, 83, 1, 86),
            (84, 90, 1, 93),
            (91, 119, 1, 124),
            (120, 136, 1, 139),
            (137, 151, 1, 154),
            (152, 158, 1, 161),
            (159, 167, 1, 170),
            (168, 178, 1, 181),
            (179, 191, 1, 194),
            (192, 200, 1, 203),
            (201, 223, 1, 226),
            (224, 228, 2, 234),
            (229, 231, 1, 234),
            (232, 234, 2, 246),
            (235, 243, 1, 246),
            (244, 248, 1, 251),
            (249, 253, 1, 256),
            (254, 260, 1, 263),
            (261, 263, 2, 273),
            (264, 270, 1, 273),
            (271, 273, 2, 285),
            (274, 278, 1, 285),
            (279, 285, 1, 288),
            (286, 292, 1, 295),
            (293, 295, 1, 298)),
 'excluded': {38: (),
              41: (50, 56),
              68: (71,),
              77: (),
              84: (89,),
              91: (110,),
              120: (123, 127),
              137: (144,),
              152: (),
              159: (166,),
              168: (),
              179: (),
              192: (197,),
              201: (206, 208, 210, 212),
              224: (),
              229: (),
              232: (),
              235: (238, 240),
              244: (),
              249: (),
              254: (259,),
              261: (),
              264: (269,),
              271: (),
              274: (),
              279: (282, 284),
              286: (),
              293: ()},
 'f1': ((0, 3, 'consolidation', 'up', (1,), ((902, 944),), 4),
        (4, 7, 'consolidation', 'up', (5,), ((753, 867),), 8),
        (8, 10, 'consolidation', None, (8,), ((753, 804),), 11),
        (11, 13, 'consolidation', None, (11,), ((715, 792),), 14),
        (14, 16, 'consolidation', None, (14,), ((915, 1118),), 17),
        (17, 19, 'consolidation', None, (17,), ((991, 1118),), 20),
        (20, 22, 'consolidation', None, (20,), ((1016, 1099),), 23),
        (23, 25, 'consolidation', None, (23,), ((1001, 1048),), 26)),
 'f2': ((0, 7, 'up', 'up', (1, 5), ((753, 804), (991, 1099)), None),),
 'f2_spans': (((1, 3, 4), (5, 7, 7)),),
 'fixture': 'real_third_point_xd_margin0.json',
 'fixture_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'id': '588000-30m-20230501-20250228',
 'impact_contracts': ((4, 'all_current', 3942), (5, 'fixed_without_active', 3978)),
 'natural_event_index': 24,
 'natural_reaction': (280, 282, 1, 285),
 'production_merged': False,
 'rejected': {38: {},
              41: {44: 45, 46: 47, 48: 51, 52: 53, 54: 67, 58: 59, 60: 61, 62: 63, 64: 65, 66: 67},
              68: {73: 74, 75: 76},
              77: {80: 81, 82: 83},
              84: {87: 90},
              91: {94: 95,
                   96: 97,
                   98: 99,
                   100: 101,
                   102: 103,
                   104: 105,
                   106: 107,
                   108: 111,
                   112: 113,
                   114: 115,
                   116: 117,
                   118: 119},
              120: {125: 128, 129: 130, 131: 132, 133: 134, 135: 136},
              137: {140: 141, 142: 145, 146: 147, 148: 149, 150: 151},
              152: {155: 156, 157: 158},
              159: {162: 163, 164: 167},
              168: {171: 172, 173: 174, 175: 176, 177: 178},
              179: {182: 183, 184: 185, 186: 187, 188: 189, 190: 191},
              192: {195: 198, 199: 200},
              201: {204: 213, 214: 215, 216: 217, 218: 219, 220: 221, 222: 223},
              224: {227: 228},
              229: {},
              232: {},
              235: {242: 243},
              244: {247: 248},
              249: {252: 253},
              254: {257: 260},
              261: {},
              264: {267: 270},
              271: {},
              274: {},
              279: {},
              286: {289: 290, 291: 292},
              293: {}},
 'seed': 38,
 'source_origin_bridge_proven': False,
 'tail': (26, 27, 'incomplete', None, (), (), None),
 'units': (('up', '2023-07-28 10:00:00', '2023-08-07 09:30:00', 991, 1022, 991, 1022, 1, 43),
           ('down', '2023-08-07 09:30:00', '2023-09-22 10:00:00', 1022, 902, 902, 1022, 1, 72),
           ('up', '2023-09-22 10:00:00', '2023-10-12 15:00:00', 902, 944, 902, 944, 1, 79),
           ('down', '2023-10-12 15:00:00', '2023-10-26 14:00:00', 944, 879, 879, 944, 1, 86),
           ('up', '2023-10-26 14:00:00', '2023-11-15 10:00:00', 879, 956, 879, 956, 1, 93),
           ('down', '2023-11-15 10:00:00', '2024-02-05 11:00:00', 956, 666, 666, 956, 1, 124),
           ('up', '2024-02-05 11:00:00', '2024-03-12 10:00:00', 666, 867, 666, 867, 1, 139),
           ('down', '2024-03-12 10:00:00', '2024-04-22 10:00:00', 867, 753, 753, 867, 1, 154),
           ('up', '2024-04-22 10:00:00', '2024-05-06 10:30:00', 753, 821, 753, 821, 1, 161),
           ('down', '2024-05-06 10:30:00', '2024-05-27 11:30:00', 821, 753, 753, 821, 1, 170),
           ('up', '2024-05-27 11:30:00', '2024-06-13 14:00:00', 753, 804, 753, 804, 1, 181),
           ('down', '2024-06-13 14:00:00', '2024-07-05 11:30:00', 804, 715, 715, 804, 1, 194),
           ('up', '2024-07-05 11:30:00', '2024-07-22 11:30:00', 715, 792, 715, 792, 1, 203),
           ('down', '2024-07-22 11:30:00', '2024-09-18 13:30:00', 792, 671, 671, 792, 1, 226),
           ('up', '2024-09-18 13:30:00', '2024-10-09 14:00:00', 671, 1202, 671, 1202, 2, 234),
           ('down', '2024-10-09 14:00:00', '2024-10-16 10:00:00', 1202, 915, 915, 1202, 1, 234),
           ('up', '2024-10-16 10:00:00', '2024-10-21 13:30:00', 915, 1118, 915, 1118, 2, 246),
           ('down', '2024-10-21 13:30:00', '2024-11-04 09:30:00', 1118, 985, 985, 1118, 1, 246),
           ('up', '2024-11-04 09:30:00', '2024-11-12 10:00:00', 985, 1136, 985, 1136, 1, 251),
           ('down', '2024-11-12 10:00:00', '2024-11-25 14:30:00', 1136, 991, 991, 1136, 1, 256),
           ('up', '2024-11-25 14:30:00', '2024-12-10 09:30:00', 991, 1117, 991, 1117, 1, 263),
           ('down', '2024-12-10 09:30:00', '2024-12-17 13:30:00', 1117, 1016, 1016, 1117, 2, 273),
           ('up', '2024-12-17 13:30:00', '2024-12-27 11:30:00', 1016, 1099, 1016, 1099, 1, 273),
           ('down', '2024-12-27 11:30:00', '2025-01-06 15:00:00', 1099, 981, 981, 1099, 2, 285),
           ('up', '2025-01-06 15:00:00', '2025-01-16 10:00:00', 981, 1048, 981, 1048, 1, 285),
           ('down', '2025-01-16 10:00:00', '2025-01-27 15:00:00', 1048, 1008, 1001, 1048, 1, 288),
           ('up', '2025-01-27 15:00:00', '2025-02-13 10:00:00', 1008, 1100, 1008, 1100, 1, 295),
           ('down', '2025-02-13 10:00:00', '2025-02-19 09:30:00', 1100, 1062, 1062, 1100, 1, 298))}


def m1_full_suffix_input(contract):
    """M1给定38长链仅消费本合同上限；不拼接266局部起点。"""
    a=M3_M1_FULL_SUFFIX_AUDIT;clock=a['clocks'][contract]
    spec=dict(a,units=[tuple(u)+(clock['local'][i],clock['published'][i]) for i,u in enumerate(a['units'])])
    case,units=gap_revision_input(spec);rows=m3_xd_rows(dict(raw_rows=case['raw_rows'][:a['bounds'][contract]]))
    root='M1-given38:'+contract+':'+a['certificate_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'given-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           rows[u['confirmed_raw_count']-1]['available_dt']) for i,u in enumerate(units)]
    return case,units,a,rows,given


class TestM1FullSuffixConsumers(unittest.TestCase):
    """M1给seed38完整后缀的双时钟、同级F1及自动递归，保留自然源前提。"""

    @staticmethod
    def _types(units,a,arrivals,contract):
        out=[]
        for spec in a['f1']:
            known=max(arrivals[:spec[-1]+1]);width=sum(at<=known for at in arrivals)
            move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units[:width]),max(a['bounds'].values()))) if m.complete and m.seg_start==spec[0])
            out.append(m3_xd_type('M1-given38:'+contract+':'+a['certificate_sha256'],move,units[:width],known))
        return out

    def test_all_actual_prefixes_freeze_eight_F1_batches_and_preserve_entry_direction(self):
        total=0
        for contract in ('current','fixed'):
            _,units,a,rows,_=m1_full_suffix_input(contract);first={};types=[];previous=[]
            for count in range(1,len(rows)+1):
                total+=1;visible=[u for u in units if u['confirmed_raw_count']<=count]
                done=[m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete]
                shapes=[m3_xd_shape(m) for m in done];expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual(shapes,[m3_xd_expected(units,s) for s in expected]);self.assertEqual(shapes[:len(previous)],previous);previous=shapes
                for m in done:
                    if m.seg_start not in first:
                        first[m.seg_start]=count;types.append(m3_xd_type('M1-given38:'+contract+':'+a['certificate_sha256'],m,visible,rows[count-1]['available_dt']))
                self.assertEqual(chan.confirm_level_up(types,rows[count-1]['available_dt'],'F2'),[])
            clock=a['clocks'][contract];self.assertEqual(tuple(first[s[0]] for s in a['f1']),clock['f1_first'])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),clock['f1_evidence'])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),(5,9,12,16,18,21,25,27))
            for t in types[:2]:self.assertEqual(t.direction,'up');self.assertLess(t.end_price,t.start_price)
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,s) for s in a['f2']])
            self.assertEqual(m3_xd_shape(chan.same_level_decompose(m3_xd_parts(dict(units=units),len(rows)))[-1]),m3_xd_expected(units,a['tail']))
            self.assertFalse(chan.scan_strict_divergence(types,rows[-1]['available_dt'],'F2').results)
            self.assertFalse(any(chan.analyze_point_chain(types,rows,rows[-1]['available_dt'],'F2')))
        self.assertEqual(total,7920)

    def test_recursive_closed_consolidation_and_five_open_candidate_roles_remain_separate(self):
        def forbidden(a,b):raise AssertionError('开放候选不评估力度')
        for contract in ('current','fixed'):
            _,units,a,rows,given=m1_full_suffix_input(contract);snapshot=None;identity=None
            for size in range(1,29):
                now=given[size-1].confirmed_dt;scan=chan.scan_strict_divergence(given[:size],now,'auto-M1-F1',forbidden,'guard')
                self.assertEqual(scan.completed_types,int(size>8));skipped=('not_trend',) if size>8 else ()
                if size in a['candidates']:
                    point,=scan.results;c=a['candidates'][size]
                    self.assertEqual((point.status,point.reason),('candidate','trend_open'))
                    self.assertEqual((tuple(int(i.rsplit(':',1)[1]) for i in point.reference_ids),tuple(int(i.rsplit(':',1)[1]) for i in point.leave_ids)),(c['reference'],c['leave']))
                    self.assertEqual(dict(point.conditions),dict(trend=None,separated_centers=True,new_extreme=None,leave_third_point=None))
                    self.assertEqual((point.force_method,point.force_reference,point.force_leave),(None,None,None))
                    if identity is None:identity=point.divergence_id
                    else:self.assertEqual(point.divergence_id,identity)
                else:
                    self.assertFalse(scan.results);skipped+=('no_compare_legs' if size>=18 else 'not_two_separated_centers',)
                self.assertEqual(tuple(r for _,r in scan.skipped),skipped)
                types=chan.confirm_level_up(given[:size],now,'auto-M1-F1')
                if types:
                    if snapshot is None:snapshot=types[0]
                    self.assertEqual(types,[snapshot]);self.assertEqual((snapshot.kind,len(snapshot.evidence_ids)),('consolidation',9))
                    self.assertEqual(snapshot.direction,'up');self.assertLess(snapshot.end_price,snapshot.start_price)
                first=chan.scan_first_points(given[:size],rows,now,'auto-M1-F1')
                self.assertEqual((first.points,tuple(r for _,r in first.exclusions)),([],('not_trend',) if size>8 else ()))
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,s) for s in a['auto']])
            self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-M1-F1')))

    def test_actual_batches_and_late_proofs_do_not_backfill_candidates_or_completed_snapshots(self):
        for contract in ('current','fixed'):
            _,units,a,rows,given=m1_full_suffix_input(contract);arrivals=[g.confirmed_dt for g in given];base=self._types(units,a,arrivals,contract)
            sizes={sum(at<=n for at in a['clocks'][contract]['published']) for n in range(1,len(rows)+1)}
            self.assertEqual(set(range(29))-sizes,{15,17,22,24})
            for proof,target in ((14,3),(23,6)):
                delayed=list(arrivals);late=arrivals[proof]+timedelta(days=1);delayed[proof]=late
                for i in range(proof+1,len(delayed)):delayed[i]=max(delayed[i-1],arrivals[i])
                after=self._types(units,a,delayed,contract)
                self.assertEqual(after[:target],base[:target]);self.assertEqual((after[target].confirmed_dt,len(after[target].evidence_ids)),(late,a['clocks'][contract]['f1_evidence'][target]))
            now=rows[-1]['available_dt'];tail=list(given);tail[-1]=given[-1]._replace(confirmed_dt=now+timedelta(days=1))
            final=chan.scan_strict_divergence(given,now,'auto-M1-F1');self.assertFalse(final.results)
            candidate,=chan.scan_strict_divergence(tail,now,'auto-M1-F1').results
            self.assertEqual((candidate.status,candidate.reason),('candidate','trend_open'))
            self.assertEqual(candidate.leave_ids,(given[26].move_id,))
            after_tail=chan.scan_strict_divergence(tail,tail[-1].confirmed_dt,'auto-M1-F1');self.assertFalse(after_tail.results)
            delayed_arrivals=list(arrivals);delayed_arrivals[-1]=tail[-1].confirmed_dt;self.assertEqual(self._types(units,a,delayed_arrivals,contract),base)
            future=given[-1]._replace(move_id=None,level=None,high=float('nan'),confirmed_dt=now+timedelta(days=10))
            self.assertEqual(chan.scan_strict_divergence(given+[future],now,'auto-M1-F1'),final)
            poisoned=rows+[dict(dt=now+timedelta(days=10),closed_dt=now+timedelta(days=10),available_dt=now+timedelta(days=11),high=float('nan'))]
            self.assertEqual(chan.scan_first_points(given+[future],poisoned,now,'auto-M1-F1'),chan.scan_first_points(given,rows,now,'auto-M1-F1'))



class TestConditionedOriginRawContracts(unittest.TestCase):
    """已冻结给定后缀的显式起点接线；不借用旧整窗自然划分标签。"""

    def _check_conditional_clock(self,case,units,rows,seed,contract,f1=()):
        boundaries = {1,len(rows)}
        for u in units:
            for count in (u['confirmed_raw_count']-1,u['confirmed_raw_count'],u['confirmed_raw_count']+1):
                if 1<=count<=len(rows):boundaries.add(count)
        for count in sorted(boundaries):
            _,_,bis = chan.chan_fx_bi(rows[:count],standard='106')
            pens = bis if contract=='current' else bis[:-1]
            given = pens[seed:]
            if len(given)<3:
                self.assertFalse([u for u in units if u['confirmed_raw_count']<=count])
                continue
            origin = dict(basis='given_recent',anchor=(0,given[0].direction,given[0].start_value),available_bi=0)
            actual = [x for x in chan.find_xds(given,origin_premise=origin) if x.complete]
            visible = [u for u in units if u['confirmed_raw_count']<=count]
            self.assertEqual(len(actual),len(visible),(case['id'],contract,count))
            publication_bi = 0
            for x,u in zip(actual,visible):
                self.assertEqual((x.direction,str(x.start_dt),str(x.end_dt),round(x.start_value*1000),round(x.end_value*1000),round(x.low*1000),round(x.high*1000),x.mode),
                                 tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode')))
                publication_bi = max(publication_bi,u['proof_bi'])
                self.assertEqual((x.evidence_end_index,x.evidence_dt),(pens[publication_bi].end_index,pens[publication_bi].end_dt))
            if f1:
                expected = [m3_xd_expected(units,s) for s in f1 if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual([m3_xd_shape(m) for m in chan.same_level_decompose(actual) if m.complete],expected)

    def test_given_m1_s3_t_raw_proof_boundaries_match_independent_tables(self):
        for contract in ('current','fixed'):
            case,units,a,rows,_ = m1_full_suffix_input(contract)
            self._check_conditional_clock(case,units,rows,a['seed'],contract,a['f1'])
        for key,a in M3_EXPANDED_SUFFIX_AUDIT.items():
            for contract in a['bounds']:
                case,units,a,rows,_ = expanded_suffix_input(key,contract)
                self._check_conditional_clock(case,units,rows,a['seed'],contract,a['f1'])

    def test_given_m2_serial_publication_does_not_use_child_local_proof_early(self):
        for contract,limit in (('current',4848),('fixed',5586)):
            case,units,_ = m2_suffix_input(contract)
            rows = m3_xd_rows(dict(raw_rows=case['raw_rows'][:limit]))
            self._check_conditional_clock(case,units,rows,M3_M2_JOINED_ROLE_AUDIT['seed'],contract)


# G1源窗口的两项显式起点假设；接通前部后重新核F1，不替换旧BI35表。
M3_G1_SOURCE_BRIDGE_AUDIT = {
    'head_reference_sha256': 'd4b124587f01a5938c6ffc5be1fe4af0b61b33d95a29137047dcde35395c6b55',
    'f1_reference_sha256': '785f52e6d7d5e8e4a5247096b28009c9ad913bf44aa640cad343eb448efd9fb0',
    'basis': 'given_recent', 'contract': 'all_current', 'limit': 1623,
    'automatic_origin_proven': False, 'global_unique_origin_proven': False,
    'heads': {
        0: {'anchor': ('down',1159), 'events': ((0,34,2,52),),
            'units': (('down','2022-08-02 10:30:00','2022-10-12 10:30:00',1159,910,910,1230,2,52,606,606),),
            'f1': ((0,2,'consolidation',None,(0,),((1027,1126),),3),
                   (3,5,'consolidation',None,(3,),((1027,1066),),6)),
            'f1_first': (777,1535), 'f1_evidence': (4,7),
            'tail': (6,8,'incomplete',None,(),(),None)},
        1: {'anchor': ('up',1141), 'events': ((1,7,1,10),(8,34,2,52)),
            'units': (('up','2022-08-03 10:00:00','2022-08-11 15:00:00',1141,1230,1141,1230,1,10,138,138),
                      ('down','2022-08-11 15:00:00','2022-10-12 10:30:00',1230,910,910,1230,2,52,606,606)),
            'f1': ((0,3,'consolidation','up',(1,),((1027,1126),),4),
                   (4,6,'consolidation',None,(4,),((1027,1066),),7)),
            'f1_first': (777,1535), 'f1_evidence': (5,8),
            'tail': (7,9,'incomplete',None,(),(),None)},
    },
    'f2': (0,1,'incomplete',None,(),(),None),
    'root1_first_candidates': ((4,13,5),(6,-14,7),(8,-44,None)),
    'root8_candidates': ((11,11,12),(13,40,14),(15,-14,16),(17,-10,18),
                         (19,-46,24),(21,-28,22),(23,-12,24),(25,6,26),
                         (27,6,28),(29,-12,30),(31,-12,34),(33,-16,34),(35,13,None)),
    'active_proof52': (606,1076,'2022-11-10 10:00:00',1058,'2022-11-14 10:00:00'),
}


def g1_source_bridge_input(seed):
    """源起点为显式条件；前部声明与既有共同后缀共享原始输入。"""
    old=M3_G1_CONSUMERS_AUDIT;case,suffix=gap_revision_input(old)
    a=M3_G1_SOURCE_BRIDGE_AUDIT['heads'][seed]
    names=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks',
           'mode','proof_bi','local_raw_count','confirmed_raw_count')
    units=[dict(zip(names,row)) for row in a['units']]+suffix
    rows=m3_xd_rows(dict(raw_rows=case['raw_rows'][:old['limit']]))
    return case,units,a,rows


class TestG1SourceBridge(unittest.TestCase):
    """课67/71/78：显式源起点至BI35接线及全窗F1；不自动裁定0/1归属。"""

    def test_raw_prefixes_join_both_declared_heads_and_rebuild_whole_chain_F1(self):
        inputs={seed:g1_source_bridge_input(seed) for seed in (0,1)}
        rows=inputs[0][3];first={seed:[] for seed in inputs};first_f1={seed:{} for seed in inputs}
        previous={seed:[] for seed in inputs};previous_f1={seed:[] for seed in inputs}
        for count in range(1,len(rows)+1):
            _,_,bis=chan.chan_fx_bi(rows[:count],standard='106')
            for seed,(_,units,a,_) in inputs.items():
                origin=dict(basis='given_recent',anchor=(0,a['anchor'][0],a['anchor'][1]/1000.),available_bi=0)
                actual=[x for x in chan.find_xds(bis[seed:],origin_premise=origin) if x.complete]
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                self.assertEqual(len(actual),len(visible),(seed,count))
                shapes=[]
                for x,u in zip(actual,visible):
                    shape=(x.direction,str(x.start_dt),str(x.end_dt),round(x.start_value*1000),round(x.end_value*1000),round(x.low*1000),round(x.high*1000),x.mode)
                    self.assertEqual(shape,tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode')))
                    proof=bis[u['proof_bi']]
                    self.assertEqual((x.evidence_end_index,x.evidence_dt),(proof.end_index,proof.end_dt))
                    shapes.append(shape)
                self.assertEqual(shapes[:len(previous[seed])],previous[seed]);previous[seed]=shapes
                first[seed].extend([count]*(len(actual)-len(first[seed])))
                moves=[m for m in chan.same_level_decompose(actual) if m.complete]
                specs=[spec for spec in a['f1'] if units[spec[-1]]['confirmed_raw_count']<=count]
                f1=[m3_xd_shape(m) for m in moves]
                self.assertEqual(f1,[m3_xd_expected(units,spec) for spec in specs])
                self.assertEqual(f1[:len(previous_f1[seed])],previous_f1[seed]);previous_f1[seed]=f1
                for m in moves:first_f1[seed].setdefault(m.seg_start,count)
                if count==len(rows):self.assertEqual(m3_xd_shape(chan.same_level_decompose(actual)[-1]),m3_xd_expected(units,a['tail']))
        for seed,(_,units,a,_) in inputs.items():
            self.assertEqual(first[seed],[u['confirmed_raw_count'] for u in units])
            self.assertEqual(tuple(first_f1[seed][s[0]] for s in a['f1']),a['f1_first'])
        self.assertFalse(M3_G1_SOURCE_BRIDGE_AUDIT['automatic_origin_proven'])
        self.assertFalse(M3_G1_SOURCE_BRIDGE_AUDIT['global_unique_origin_proven'])

    def test_late_root_premise_waits_for_BI52_and_preserves_active_proof_snapshot(self):
        _,units,a,rows=g1_source_bridge_input(1);snapshots=[]
        for count in (137,138,139,605,606,607,777,1623):
            _,_,bis=chan.chan_fx_bi(rows[:count],standard='106')
            origin=dict(basis='given_recent',anchor=(0,'up',1.141),available_bi=51)
            done=[x for x in chan.find_xds(bis[1:],origin_premise=origin) if x.complete]
            visible=[u for u in units if max(606,u['confirmed_raw_count'])<=count]
            self.assertEqual(len(done),len(visible))
            for x,u in zip(done,visible):
                proof=bis[max(52,u['proof_bi'])]
                self.assertEqual((x.evidence_end_index,x.evidence_dt),(proof.end_index,proof.end_dt))
            if count==606:
                self.assertEqual(len(done),2);snapshots=[x.to_dict() for x in done]
                self.assertEqual(done[0].evidence_dt,date('2022-11-10 10:00:00'))
            if count==1623:
                self.assertEqual(done[0].evidence_dt,date('2022-11-14 10:00:00'))
        self.assertEqual(snapshots[0]['evidence_dt'],'2022-11-10 10:00:00')
        self.assertEqual(units[0]['confirmed_raw_count'],138)
        self.assertLess(units[0]['proof_bi'],52)

    def test_whole_chain_F1_is_not_the_given35_role_and_does_not_create_F2_points(self):
        def forbidden(a,b):raise AssertionError('不足三个完整F1不得评估F2严格力度')
        for seed in (0,1):
            _,units,a,rows=g1_source_bridge_input(seed);types=[]
            root='G1-source-given'+str(seed)+':'+M3_G1_SOURCE_BRIDGE_AUDIT['head_reference_sha256']
            for spec,count in zip(a['f1'],a['f1_first']):
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),count)) if m.complete and m.seg_start==spec[0])
                types.append(m3_xd_type(root,move,visible,rows[count-1]['available_dt']))
            self.assertEqual(tuple(len(t.evidence_ids) for t in types),a['f1_evidence'])
            self.assertEqual(tuple((round(x*1000),round(y*1000)) for x,y in types[0].centers),((1027,1126),))
            self.assertNotEqual(a['f1_first'],M3_G1_CONSUMERS_AUDIT['f1_first'])
            if seed==1:
                self.assertEqual(types[0].direction,'up')
                self.assertEqual(types[0].to_confirmed_move().direction,'down')
            for count in (126,776,777,778,1534,1535,1536,1623):
                now=rows[count-1]['available_dt']
                self.assertEqual(chan.confirm_level_up(types,now,'F2'),[])
                self.assertEqual(chan.scan_strict_divergence(types,now,'F2',forbidden,'guard').results,())
                self.assertFalse(chan.scan_first_points(types,rows[:count],now,'F2').points)
                self.assertFalse(any(chan.analyze_point_chain(types,rows[:count],now,'F2')))
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types)],[m3_xd_expected(records,M3_G1_SOURCE_BRIDGE_AUDIT['f2'])])


# M2给定源BI0的前部；既有BI16链及后续角色继续独立保留。
M3_M2_SOURCE_BRIDGE_AUDIT = {
    'reference_sha256': 'bac1312fe05134afaeea70f483fcd11c6289b20099f92234c16a828032eb4b44',
    'basis': 'given_recent', 'anchor': (0,'down',1207),
    'limits': {'current': 4848, 'fixed': 5586},
    'events': ((0,10,1,13),(11,15,1,18)),
    'units': (('down','2026-02-02 10:10:00','2026-02-06 09:50:00',1207,1183,1163,1207,1,13,277,277),
              ('up','2026-02-06 09:50:00','2026-02-10 10:10:00',1183,1200,1183,1200,1,18,546,546)),
    'head_counts': {'current': (258,398), 'fixed': (277,546)},
    'proof18_first': {'current': (398,1186,'2026-02-12 09:50:00'),
                      'fixed': (546,1171,'2026-02-24 10:10:00')},
    'nonprotruding0': (3,5,7,9), 'revoked_gap': (11,14,2,15),
    'first_f1': ((0,5,'down','down',(0,3),((1183,1200),(1113,1135)),6),
                 (6,8,'consolidation',None,(6,),((1031,1060),),9)),
    'first_f1_counts': {'current': (1639,1764), 'fixed': (1648,1775)},
    'first_f1_evidence': (8,10), 'retained_shift': 2,
    'first_f1_waves': ((1113,1207),(1100,1140)), 'wave_overlap_ticks': 27,
    'f2': (0,5,'consolidation','down',(1,),((1029,1056),),6),
    'f2_first': {'current': 3940, 'fixed': 3956},
    'f2_evidence': 7,
    'tails': {'current': (32,32,'incomplete',None,(),(),None),
              'fixed': (35,36,'incomplete',None,(),(),None)},
    'f2_tails': {'current': (6,8,'consolidation',None,(6,),((1015,1048),),None),
                 'fixed': (6,9,'consolidation',None,(6,),((1015,1048),),None)},
    'automatic_origin_proven': False, 'global_unique_origin_proven': False,
}


def m2_source_bridge_input(contract):
    """仅平移既有保留组坐标；首两项完整窗口F1另有独立声明。"""
    a=M3_M2_SOURCE_BRIDGE_AUDIT;case,suffix,old=m2_suffix_input(contract)
    names=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks',
           'mode','proof_bi','local_raw_count','confirmed_raw_count')
    head=[dict(zip(names,row)) for row in a['units']]
    for u,count in zip(head,a['head_counts'][contract]):
        u['local_raw_count']=count;u['confirmed_raw_count']=count
    def shift(spec):
        x,z,kind,direction,triples,centers,proof=spec
        return (x+2,z+2,kind,direction,tuple(i+2 for i in triples),centers,None if proof is None else proof+2)
    specs=a['first_f1']+tuple(shift(x) for x in M3_M2_JOINED_ROLE_AUDIT['f1'][2:]+old['f1'])
    rows=m3_xd_rows(dict(raw_rows=case['raw_rows'][:a['limits'][contract]]))
    return case,head+suffix,specs,rows


class TestM2SourceBridge(unittest.TestCase):
    """课67/71/78及35/38：指定源BI0后桥接BI16，按原双合同窗口核F1/F2。"""

    def test_original_raw_contracts_join_the_source_head_and_rebuild_complete_F1(self):
        a=M3_M2_SOURCE_BRIDGE_AUDIT;inputs={k:m2_source_bridge_input(k) for k in ('current','fixed')}
        rows=inputs['fixed'][3];previous={k:[] for k in inputs};first={k:[] for k in inputs};f1_first={k:{} for k in inputs}
        prior_f1={k:[] for k in inputs};cache={k:(None,[]) for k in inputs}
        for count in range(1,len(rows)+1):
            _,_,all_bis=chan.chan_fx_bi(rows[:count],standard='106')
            for contract,(_,units,specs,observed) in inputs.items():
                if count>len(observed):continue
                bis=all_bis if contract=='current' else all_bis[:-1]
                # 相邻raw若公开BI输入完全相同，复用纯函数结果，时钟断言仍逐raw执行。
                key=tuple((b.direction,b.start_index,b.end_index,b.start_dt,b.end_dt,b.start_value,b.end_value) for b in bis)
                if key!=cache[contract][0]:
                    cache[contract]=(key,[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',1.207),available_bi=0)) if x.complete])
                actual=cache[contract][1]
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                self.assertEqual(len(actual),len(visible),(contract,count));shapes=[];publication=0
                for x,u in zip(actual,visible):
                    shape=(x.direction,str(x.start_dt),str(x.end_dt),round(x.start_value*1000),round(x.end_value*1000),round(x.low*1000),round(x.high*1000),x.mode)
                    self.assertEqual(shape,tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode')))
                    publication=max(publication,u['proof_bi']);proof=bis[publication]
                    self.assertEqual((x.evidence_end_index,x.evidence_dt),(proof.end_index,proof.end_dt));shapes.append(shape)
                self.assertEqual(shapes[:len(previous[contract])],previous[contract]);previous[contract]=shapes
                first[contract].extend([count]*(len(actual)-len(first[contract])))
                moves=[m for m in chan.same_level_decompose(actual) if m.complete]
                expected=[x for x in specs if units[x[-1]]['confirmed_raw_count']<=count]
                f1=[m3_xd_shape(m) for m in moves]
                self.assertEqual(f1,[m3_xd_expected(units,x) for x in expected])
                self.assertEqual(f1[:len(prior_f1[contract])],prior_f1[contract]);prior_f1[contract]=f1
                for m in moves:f1_first[contract].setdefault(m.seg_start,count)
                if count==len(observed):self.assertEqual(m3_xd_shape(chan.same_level_decompose(actual)[-1]),m3_xd_expected(units,a['tails'][contract]))
        for contract,(_,units,specs,rows) in inputs.items():
            self.assertEqual(first[contract],[u['confirmed_raw_count'] for u in units if u['confirmed_raw_count']<=len(rows)])
            self.assertEqual(tuple(f1_first[contract][x[0]] for x in a['first_f1']),a['first_f1_counts'][contract])
            self.assertEqual(len(f1_first[contract]),9 if contract=='current' else 10)
        self.assertFalse(a['automatic_origin_proven']);self.assertFalse(a['global_unique_origin_proven'])

    def test_late_BI18_premise_and_parent72_keep_current_fixed_evidence_versions(self):
        a=M3_M2_SOURCE_BRIDGE_AUDIT;saved={}
        for contract in ('current','fixed'):
            _,units,_,rows=m2_source_bridge_input(contract);at,price,dt=a['proof18_first'][contract]
            for count in sorted({257,258,277,397,398,545,546,at-1,at,1582,1618,1639,1648,len(rows)}):
                _,_,all_bis=chan.chan_fx_bi(rows[:count],standard='106');bis=all_bis if contract=='current' else all_bis[:-1]
                actual=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',1.207),available_bi=18)) if x.complete]
                expected=[u for u in units if max(at,u['confirmed_raw_count'])<=count]
                self.assertEqual(len(actual),len(expected),(contract,count));publication=18
                for x,u in zip(actual,expected):
                    publication=max(publication,u['proof_bi']);proof=bis[publication]
                    self.assertEqual((x.evidence_end_index,x.evidence_dt),(proof.end_index,proof.end_dt))
                if count==at:
                    self.assertEqual(len(actual),2);self.assertEqual((round(bis[18].end_value*1000),str(bis[18].end_dt)),(price,dt))
                    saved[contract]=actual[0].to_dict()
                if count==(1582 if contract=='current' else 1618):self.assertEqual(len(actual),6)
                if count==(1639 if contract=='current' else 1648):self.assertEqual(len(actual),8)
            self.assertEqual(saved[contract]['evidence_dt'],dt)
        self.assertNotEqual(saved['current']['evidence_dt'],saved['fixed']['evidence_dt'])

    def test_whole_F1_F2_identity_and_core_down_do_not_supply_strict_wave_separation(self):
        def forbidden(a,b):raise AssertionError('盘整F2不评估严格力度')
        a=M3_M2_SOURCE_BRIDGE_AUDIT
        for contract in ('current','fixed'):
            _,units,specs,rows=m2_source_bridge_input(contract);types=[]
            for s in specs:
                known=units[s[-1]]['confirmed_raw_count']
                if known>len(rows):continue
                visible=[u for u in units if u['confirmed_raw_count']<=known]
                move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),known)) if m.complete and m.seg_start==s[0])
                types.append(m3_xd_type('M2-source0:'+contract,move,visible,rows[known-1]['available_dt']))
            self.assertEqual(tuple(len(t.evidence_ids) for t in types[:2]),a['first_f1_evidence'])
            self.assertEqual((types[0].kind,types[0].direction,round(types[0].high*1000)),('down','down',1207))
            self.assertEqual(types[1].direction,None)
            waves=[(min(u['low_ticks'] for u in units[i:i+3]),max(u['high_ticks'] for u in units[i:i+3])) for i in a['first_f1'][0][4]]
            self.assertEqual(tuple(waves),a['first_f1_waves'])
            self.assertEqual(min(w[1] for w in waves)-max(w[0] for w in waves),a['wave_overlap_ticks'])
            frozen=None
            for count in (1329,1349,a['first_f1_counts'][contract][0],a['f2_first'][contract]-1,a['f2_first'][contract],len(rows)):
                now=rows[count-1]['available_dt'];f2=chan.confirm_level_up(types,now,'F2')
                self.assertEqual(len(f2),int(count>=a['f2_first'][contract]))
                if f2:
                    if frozen is None:frozen=f2[0]
                    self.assertEqual(f2[0],frozen)
                    self.assertEqual((f2[0].kind,f2[0].direction,round(f2[0].high*1000),len(f2[0].evidence_ids)),('consolidation','down',1207,7))
                    self.assertEqual(f2[0].confirmed_dt,rows[a['f2_first'][contract]-1]['available_dt'])
                    self.assertEqual(chan.confirm_level_up(f2,now,'F3'),[])
                self.assertEqual(chan.scan_strict_divergence(types,now,'F2',forbidden,'guard').results,())
                self.assertFalse(chan.scan_first_points(types,rows[:count],now,'F2').points)
                self.assertFalse(any(chan.analyze_point_chain(types,rows[:count],now,'F2')))
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types]
            f2=chan.level_up(types)
            self.assertEqual([m3_xd_shape(m) for m in f2],[m3_xd_expected(records,s) for s in (a['f2'],a['f2_tails'][contract])])


# 源BI0完整原窗口的XD级条件；P为新增前部中枢，旧seed16表保持。
M3_M2_SOURCE_CONSUMERS_AUDIT = {'attempts': {'A': (('sell3', 6, 7, 53, 1060, 'before_center_known'),
                    ('buy3', 29, 30, -35, 1100, 'fail'),
                    ('sell3', 30, 31, -78, 1191, 'fail'),
                    ('buy3', 31, 32, 4, 1139, 'established')),
              'B': (('sell3', 10, 11, -25, 1056, 'before_center_known'),
                    ('buy3', 11, 12, -20, 1029, 'fail'),
                    ('sell3', 12, 13, -60, 1086, 'fail'),
                    ('buy3', 13, 14, 21, 1070, 'established')),
              'C': (('sell3', 18, 19, -30, 1100, 'before_center_known'),
                    ('buy3', 19, 20, -6, 1073, 'before_center_known'),
                    ('buy3', 21, 22, -40, 1039, 'fail'),
                    ('sell3', 22, 23, -22, 1092, 'fail'),
                    ('buy3', 23, 24, -64, 1015, 'fail'),
                    ('sell3', 24, 25, 22, 1048, 'established')),
              'N': (('sell3', 34, 35, 0, 1139, 'before_center_known'),),
              'P': (('sell3', 32, 33, 6, 1177, 'established'),),
              'R': (('sell3', 24, 25, 25, 1048, 'before_center_known'),
                    ('buy3', 29, 30, 0, 1100, 'established'))},
 'automatic_origin_proven': False,
 'contexts': {'A': (3, 5, 1113, 1135, None),
              'B': (7, 9, 1031, 1049, None),
              'C': (15, 17, 1070, 1079, None),
              'N': (31, 33, 1139, 1177, 'R'),
              'P': (0, 2, 1183, 1200, None),
              'R': (20, 22, 1073, 1100, None)},
 'known_raw': {'current': {'A': 1329, 'B': 1764, 'C': 2740, 'N': None, 'P': 924, 'R': 3343},
               'fixed': {'A': 1349, 'B': 1775, 'C': 2759, 'N': 4894, 'P': 940, 'R': 3362}},
 'limits': {'current': 4848, 'fixed': 5586},
 'parent_N_pull': 30,
 'pending': {'current': ('P', 'sell3', 32), 'fixed': ('N', 'sell3', 36)},
 'point_order': ('B', 'C', 'R', 'A', 'P'),
 'point_raw': {'current': {'A': 4842, 'B': 2356, 'C': 3940, 'P': None, 'R': 4716},
               'fixed': {'A': 4848, 'B': 2365, 'C': 3956, 'P': 4894, 'R': 4727}},
 'points': {'A': ('buy3', 31, 32, 1139, 4),
            'B': ('buy3', 13, 14, 1070, 21),
            'C': ('sell3', 24, 25, 1048, 22),
            'P': ('sell3', 32, 33, 1177, 6),
            'R': ('buy3', 29, 30, 1100, 0)},
 'reference_sha256': 'fff4d79562d9124e45e1b29a771432e9c796d422f57f6bb57b4acbee1c94d001',
 'relation_ticks': {'AB_gap': 9, 'BC_overlap': 52, 'PA_overlap': 27},
 'roles': {'A': {'closed_by': 7,
                 'core_basis': 'three_units',
                 'dd': 1100,
                 'frozen_by_departure': False,
                 'gg': 1140,
                 'zd': 1113,
                 'zg': 1135,
                 'zn': (3, 5)},
           'B': {'closed_by': 15,
                 'core_basis': 'three_units',
                 'dd': 1010,
                 'frozen_by_departure': False,
                 'gg': 1091,
                 'zd': 1031,
                 'zg': 1049,
                 'zn': (7, 9, 11, 13)},
           'C': {'closed_by': 25,
                 'core_basis': 'three_units',
                 'dd': 1039,
                 'frozen_by_departure': False,
                 'gg': 1111,
                 'zd': 1070,
                 'zg': 1079,
                 'zn': (15, 17, 19, 21, 23)},
           'P': {'closed_by': 4,
                 'core_basis': 'three_units',
                 'dd': 1113,
                 'frozen_by_departure': False,
                 'gg': 1207,
                 'zd': 1183,
                 'zg': 1200,
                 'zn': (0, 2)},
           'R': {'closed_by': 26,
                 'core_basis': 'three_units',
                 'dd': 1015,
                 'frozen_by_departure': False,
                 'gg': 1111,
                 'zd': 1073,
                 'zg': 1100,
                 'zn': (20, 22, 24)}},
 'schema': 'M2-source0-XD-consumers-v01',
 'scope': 'explicit_given_recent_source0_not_automatic_theory_levels',
 'source_reference_sha256': 'bac1312fe05134afaeea70f483fcd11c6289b20099f92234c16a828032eb4b44',
 'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'terminal_counts': {'current': 4, 'fixed': 5},
 'totals': {'current': {'before_center_known': 5, 'established': 4, 'fail': 7},
            'fixed': {'before_center_known': 6, 'established': 5, 'fail': 7}}}


def m2_source_consumers_input(contract):
    """按原合同裁剪已验XD；当前N未形成，不制造窗外确认上下文。"""
    case,units,_,rows=m2_source_bridge_input(contract);a=M3_M2_SOURCE_CONSUMERS_AUDIT
    if (a['source_reference_sha256']!=M3_M2_SOURCE_BRIDGE_AUDIT['reference_sha256'] or
            a['source_sha256']!=M3_M2_JOINED_ROLE_AUDIT['fixture_sha256']):
        raise AssertionError('源点消费者须绑定同一源BI0证书')
    units=[u for u in units if u['confirmed_raw_count']<=a['limits'][contract]]
    root='M2-source0-third:'+contract+':'+a['reference_sha256']
    moves=[chan.ConfirmedMove(root+':xd:'+str(i),'source0-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           gap_revision_time(case,u['confirmed_raw_count'])) for i,u in enumerate(units)]
    contexts=[]
    for name,(first,formed,zd,zg,parent) in a['contexts'].items():
        if formed>=len(units):continue
        known=a['known_raw'][contract][name]
        if parent:known=max(known,units[a['parent_N_pull']]['confirmed_raw_count'])
        contexts.append(chan.ThirdPointContext(root+':context:'+name,'source0-center','source0-XD',
                        chan.ConfirmedCenter(root+':center:'+name,'source0-center',zd/1000.,zg/1000.,
                                             gap_revision_time(case,known))))
    return case,units,a,moves,contexts


class TestM2SourceConsumers(unittest.TestCase):
    """课20/29/101：显式源BI0的中枢/三类，按原current/fixed边界独立验收。"""

    def test_source0_raw_boundaries_bind_actual_XDs_centers_and_first_points(self):
        observations=0
        for contract in ('current','fixed'):
            case,units,a,_,contexts=m2_source_consumers_input(contract)
            rows=m3_xd_rows(dict(raw_rows=case['raw_rows'][:a['limits'][contract]]))
            counts=sorted({1,len(rows)}|{n for u in units for n in (u['confirmed_raw_count']-1,u['confirmed_raw_count']) if n>0})
            first={};formed_first={};frozen={}
            for count in counts:
                _,_,bs=chan.chan_fx_bi(rows[:count],standard='106');bis=bs if contract=='current' else bs[:-1]
                actual=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',1.207),available_bi=0)) if x.complete]
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                self.assertEqual(len(actual),len(visible));moves=[]
                for i,(x,u) in enumerate(zip(actual,visible)):
                    self.assertEqual(tuple(round(v*1000) for v in (x.start_value,x.end_value,x.low,x.high)),
                                     tuple(u[k] for k in ('start_ticks','end_ticks','low_ticks','high_ticks')))
                    moves.append(chan.ConfirmedMove('source0:'+contract+':'+str(i),'source0-XD',x.direction,
                                 x.start_dt,x.end_dt,x.start_value,x.end_value,x.low,x.high,
                                 gap_revision_time(case,u['confirmed_raw_count'])))
                active=[]
                for context in contexts:
                    name=context.context_id.rsplit(':',1)[1];start,formed,zd,zg,_=a['contexts'][name]
                    if formed>=len(actual):continue
                    center=chan.find_zs(actual[start:formed+1])[0]
                    self.assertEqual((round(center.zd*1000),round(center.zg*1000)),(zd,zg))
                    formed_first.setdefault(name,count);active.append(context)
                points=chan.find_third_points(moves,active,rows[count-1]['available_dt']);observations+=1
                names=[n for n in a['point_order'] if a['point_raw'][contract][n] is not None and a['point_raw'][contract][n]<=count]
                self.assertEqual(len(points),len(names),(contract,count))
                for point,name in zip(points,names):
                    kind,leave,pull,price,margin=a['points'][name]
                    self.assertEqual((point.kind,point.leave_move_id,point.pull_move_id,round(point.price*1000)),
                                     (kind,moves[leave].move_id,moves[pull].move_id,price))
                    self.assertEqual((point.dt,point.confirmed_dt),(moves[pull].end_dt,gap_revision_time(case,a['point_raw'][contract][name])))
                    self.assertLess(point.dt,point.confirmed_dt)
                    if name in frozen:self.assertEqual(point,frozen[name])
                    frozen[name]=point;first.setdefault(name,count)
            self.assertEqual(first,{k:v for k,v in a['point_raw'][contract].items() if v is not None})
            self.assertEqual(formed_first,{k:v for k,v in a['known_raw'][contract].items() if v is not None})
        self.assertEqual(observations,122)

    def test_new_P_core_and_whole_wave_prevent_promoting_source0_to_strict_trend(self):
        _,units,a,_,_=m2_source_consumers_input('fixed');parts=m3_xd_parts(dict(units=units),5586);centers={}
        for name,spec in a['roles'].items():
            first,last=spec['zn'][0],spec['zn'][-1]
            z=chan.find_zs(parts[first:last+1])[0];centers[name]=z
            self.assertEqual(tuple(round(v*1000) for v in (z.zd,z.zg,z.dd,z.gg)),tuple(spec[k] for k in ('zd','zg','dd','gg')))
        self.assertEqual(chan.zs_relation(centers['P'],centers['A']),'expand')
        self.assertEqual(chan.zs_relation(centers['A'],centers['B']),'down_continue')
        self.assertEqual(chan.zs_relation(centers['B'],centers['C']),'expand')
        self.assertEqual(round((centers['A'].gg-centers['P'].dd)*1000),a['relation_ticks']['PA_overlap'])
        self.assertEqual(round((centers['A'].dd-centers['B'].gg)*1000),a['relation_ticks']['AB_gap'])
        # A/B局部严格分离不补c14：其低1070高于B上沿1049，16低1050仍差1格。
        self.assertEqual((units[14]['low_ticks']-a['roles']['B']['zg'],units[16]['low_ticks']-a['roles']['B']['zg']),(21,1))
        self.assertFalse(a['automatic_origin_proven'])

    def test_new_P_six_tick_sell_and_touch_mirror_obey_center_known_time(self):
        case,units,a,moves,contexts=m2_source_consumers_input('fixed')
        context=next(c for c in contexts if c.context_id.endswith(':P'));now=gap_revision_time(case,5586)
        point,=chan.find_third_points(moves,[context],now)
        self.assertEqual((point.kind,round(point.price*1000),point.pull_move_id),('sell3',1177,moves[33].move_id))
        self.assertEqual(a['roles']['P']['zd']-units[33]['high_ticks'],6)
        for delta in (-1,0,1):
            changed=list(moves[:34]);edge=(1183+delta)/1000.
            changed[33]=changed[33]._replace(end_price=edge,high=edge)
            for mirror in (False,True):
                supplied=changed;active=context
                if mirror:
                    flip=lambda v:(3000-round(v*1000))/1000.
                    supplied=[m._replace(direction='down' if m.direction=='up' else 'up',start_price=flip(m.start_price),
                              end_price=flip(m.end_price),low=flip(m.high),high=flip(m.low)) for m in changed]
                    active=context._replace(center=context.center._replace(zd=flip(context.center.zg),zg=flip(context.center.zd)))
                result=chan.find_third_points(supplied,[active],now)
                self.assertEqual(len(result),int(delta<=0))
                if result:self.assertEqual(result[0].kind,'buy3' if mirror else 'sell3')
            delayed=context._replace(center=context.center._replace(confirmed_dt=moves[32].start_dt+timedelta(microseconds=delta)))
            self.assertEqual(len(chan.find_third_points(moves,[delayed],now)),int(delta<=0))

    def test_original_window_limits_late_returns_and_future_poison_keep_new_identity(self):
        for contract in ('current','fixed'):
            case,units,a,moves,contexts=m2_source_consumers_input(contract);now=gap_revision_time(case,a['limits'][contract])
            named={c.context_id.rsplit(':',1)[1]:c for c in contexts};points=chan.find_third_points(moves,contexts,now)
            self.assertEqual(len(points),a['terminal_counts'][contract])
            self.assertEqual(len(units),33 if contract=='current' else 37)
            if contract=='current':
                self.assertNotIn('N',named)
                self.assertEqual(chan.find_third_points(moves,[named['P']],now),[])
                self.assertEqual((moves[-1].direction,round(moves[-1].end_price*1000)),('down',1139))
            else:
                self.assertEqual(chan.find_third_points(moves,[named['N']],now),[])
                self.assertEqual((moves[-1].direction,round(moves[-1].end_price*1000)),('down',1094))
            _,_,_,old_moves,old_contexts=m2_third_input(contract)
            self.assertTrue({m.move_id for m in moves}.isdisjoint(m.move_id for m in old_moves))
            self.assertTrue({c.center.center_id for c in contexts}.isdisjoint(c.center.center_id for c in old_contexts))
            for name,at in a['point_raw'][contract].items():
                if at is None:continue
                context=named[name];_,leave,pull,_,_=a['points'][name];late=moves[pull].confirmed_dt+timedelta(days=1)
                delayed=list(moves);delayed[pull]=moves[pull]._replace(confirmed_dt=late)
                for i in range(pull+1,len(moves)):delayed[i]=moves[i]._replace(confirmed_dt=max(moves[i].confirmed_dt,delayed[i-1].confirmed_dt))
                self.assertEqual(chan.find_third_points(delayed,[context],late-timedelta(microseconds=1)),[])
                point,=chan.find_third_points(delayed,[context],late)
                self.assertEqual((point.leave_move_id,point.pull_move_id,point.confirmed_dt),(moves[leave].move_id,moves[pull].move_id,late))
                future=moves[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=late+timedelta(days=10))
                future_context=context._replace(context_id=None,center=context.center._replace(center_id=None,zd=float('nan'),confirmed_dt=late+timedelta(days=10)))
                self.assertEqual(chan.find_third_points(delayed+[future],[context,future_context],late),[point])


# M1源BI1近期顶的前部桥接；原BI38给定后缀及旧角色表保持。
M3_M1_SOURCE_BRIDGE_AUDIT = {'anchor': (1, 'down', 1107),
 'automatic_origin_proven': False,
 'available_bi': 1,
 'events': ((1, 3, 1, 6), (4, 12, 1, 23), (13, 23, 1, 28), (24, 28, 1, 31), (29, 37, 1, 40)),
 'excluded': ((4, 9), (13, 16), (13, 18), (13, 20), (24, 27)),
 'f1': ((0, 2, 'consolidation', None, (0,), ((1048, 1107),), 3),
        (3, 6, 'consolidation', 'up', (4,), ((991, 1022),), 9),
        (7, 9, 'consolidation', None, (7,), ((902, 944),), 10),
        (10, 12, 'consolidation', None, (10,), ((753, 867),), 13),
        (13, 15, 'consolidation', None, (13,), ((753, 804),), 16),
        (16, 18, 'consolidation', None, (16,), ((715, 792),), 19),
        (19, 21, 'consolidation', None, (19,), ((915, 1118),), 22),
        (22, 24, 'consolidation', None, (22,), ((991, 1118),), 25),
        (25, 27, 'consolidation', None, (25,), ((1016, 1099),), 28),
        (28, 30, 'consolidation', None, (28,), ((1001, 1048),), 31)),
 'f1_evidence': {'current': (4, 10, 11, 14, 17, 21, 23, 26, 30, 32),
                 'fixed': (4, 10, 11, 14, 17, 21, 23, 26, 30, 32)},
 'f1_first': {'current': (434, 1236, 1754, 2226, 2593, 3188, 3317, 3544, 3815, 3908),
              'fixed': (441, 1244, 1757, 2235, 2609, 3198, 3323, 3572, 3822, 3913)},
 'f2': ((0, 5, 'consolidation', None, (1,), ((902, 956),), 6),
        (6, 9, 'consolidation', None, (6,), ((991, 1117),), None)),
 'f2_envelope': (666, 1113),
 'f2_evidence': 7,
 'f2_first': {'current': 3317, 'fixed': 3323},
 'first_overlap': (1061, 1083),
 'global_unique_origin_proven': False,
 'head_counts': {'current': (97, 337, 376, 434, 579), 'fixed': (116, 342, 390, 441, 599)},
 'head_proof_first': {'current': ((97, 1081, '2023-05-18 13:30:00', True),
                                  (337, 1041, '2023-06-28 10:30:00', True),
                                  (376, 1067, '2023-07-04 13:30:00', True),
                                  (434, 1028, '2023-07-13 09:30:00', True),
                                  (579, 1021, '2023-08-04 10:00:00', True)),
                      'fixed': ((116, 1092, '2023-05-19 14:30:00', True),
                                (342, 1041, '2023-06-28 10:30:00', True),
                                (390, 1067, '2023-07-04 13:30:00', True),
                                (441, 1028, '2023-07-13 09:30:00', True),
                                (599, 1022, '2023-08-07 09:30:00', True))},
 'head_reference_sha256': 'cb4f9ab615a53ee3dc771a43d403e23a3a37652861ea7d3185e0b226b2b28289',
 'initial_empty_overlap_ticks': 7,
 'limits': {'current': 3942, 'fixed': 3978},
 'proof_high_excluded': 1202,
 'reference_sha256': '4fa3621c81a27cc74b5153f7fbb64d0b10d21ffc9ca66f0073632b2401559e11',
 'rejected': ((4, 7, -26, 12),
              (4, 11, 1, 12),
              (13, 22, 25, 23),
              (29, 32, -12, 33),
              (29, 34, 5, 35),
              (29, 36, 5, 37)),
 'schema': 'M1-source-BI1-whole-F1-F2-v01',
 'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'suffix_certificate_sha256': '203d72ee106711ff44e535492735200f5914bbe6f3f23e447a4d899fa41f7562',
 'tail': (31, 32, 'incomplete', None, (), (), None),
 'units': ({'direction': 'down',
            'end_dt': '2023-05-15 11:30:00',
            'end_index': 40,
            'end_ticks': 1048,
            'evidence_dt': '2023-05-19 14:30:00',
            'evidence_end_index': 63,
            'high_ticks': 1107,
            'low_ticks': 1048,
            'mode': 1,
            'proof_bi': 6,
            'start_dt': '2023-05-09 10:00:00',
            'start_index': 13,
            'start_ticks': 1107},
           {'direction': 'up',
            'end_dt': '2023-06-01 14:00:00',
            'end_index': 112,
            'end_ticks': 1113,
            'evidence_dt': '2023-06-28 10:30:00',
            'evidence_end_index': 197,
            'high_ticks': 1113,
            'low_ticks': 1048,
            'mode': 1,
            'proof_bi': 23,
            'start_dt': '2023-05-15 11:30:00',
            'start_index': 40,
            'start_ticks': 1048},
           {'direction': 'down',
            'end_dt': '2023-06-28 10:30:00',
            'end_index': 197,
            'end_ticks': 1041,
            'evidence_dt': '2023-07-04 13:30:00',
            'evidence_end_index': 215,
            'high_ticks': 1113,
            'low_ticks': 1041,
            'mode': 1,
            'proof_bi': 28,
            'start_dt': '2023-06-01 14:00:00',
            'start_index': 112,
            'start_ticks': 1113},
           {'direction': 'up',
            'end_dt': '2023-07-04 13:30:00',
            'end_index': 215,
            'end_ticks': 1067,
            'evidence_dt': '2023-07-13 09:30:00',
            'evidence_end_index': 246,
            'high_ticks': 1067,
            'low_ticks': 1041,
            'mode': 1,
            'proof_bi': 31,
            'start_dt': '2023-06-28 10:30:00',
            'start_index': 197,
            'start_ticks': 1041},
           {'direction': 'down',
            'end_dt': '2023-07-28 10:00:00',
            'end_index': 296,
            'end_ticks': 991,
            'evidence_dt': '2023-08-07 09:30:00',
            'evidence_end_index': 322,
            'high_ticks': 1067,
            'low_ticks': 991,
            'mode': 1,
            'proof_bi': 40,
            'start_dt': '2023-07-04 13:30:00',
            'start_index': 215,
            'start_ticks': 1067})}


def m1_source_bridge_input(contract):
    """保留输入首残笔，不由截断窗口声明无前史；最早交集锚定BI1。"""
    case,suffix,old,rows,_=m1_full_suffix_input(contract);a=M3_M1_SOURCE_BRIDGE_AUDIT
    if (a['suffix_certificate_sha256']!=old['certificate_sha256'] or
            a['source_sha256']!=old['fixture_sha256']):
        raise AssertionError('M1源桥接须绑定同一BI38后缀与行情')
    # units为全源固定装配；实际证明版本由head_proof_first及逐raw的BI核对。
    heads=[dict(u,local_raw_count=n,confirmed_raw_count=n) for u,n in zip(a['units'],a['head_counts'][contract])]
    return case,heads+suffix,a,rows


class TestM1SourceBridge(unittest.TestCase):
    """课67/71/78及35/38：显式BI1源锚点接通BI38，按原窗口重验F1/F2。"""

    def test_original_raw_contracts_join_five_heads_and_rebuild_whole_F1_F2(self):
        inputs={c:m1_source_bridge_input(c) for c in ('current','fixed')};rows=inputs['fixed'][3]
        first={c:[] for c in inputs};f1_first={c:{} for c in inputs};types={c:[] for c in inputs}
        previous={c:[] for c in inputs};prior_f1={c:[] for c in inputs};frozen_f2={};cache={};total=0
        for count in range(1,len(rows)+1):
            _,_,bs=chan.chan_fx_bi(rows[:count],standard='106')
            for contract,(_,units,a,observed) in inputs.items():
                if count>len(observed):continue
                total+=1;bis=bs if contract=='current' else bs[:-1]
                key=tuple((b.direction,b.start_index,b.end_index,b.start_dt,b.end_dt,b.start_value,b.end_value) for b in bis)
                if contract not in cache or cache[contract][0]!=key:
                    xs=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(1,'down',1.107),available_bi=1)) if x.complete]
                    cache[contract]=(key,xs)
                else:xs=cache[contract][1]
                visible=[u for u in units if u['confirmed_raw_count']<=count]
                self.assertEqual(len(xs),len(visible),(contract,count));shapes=[];pub=1
                for x,u in zip(xs,visible):
                    shape=(x.direction,str(x.start_dt),str(x.end_dt),round(x.start_value*1000),round(x.end_value*1000),round(x.low*1000),round(x.high*1000),x.mode)
                    self.assertEqual(shape,tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode')))
                    pub=max(pub,u['proof_bi']);self.assertEqual((x.evidence_end_index,x.evidence_dt),(bis[pub].end_index,bis[pub].end_dt));shapes.append(shape)
                self.assertEqual(shapes[:len(previous[contract])],previous[contract]);previous[contract]=shapes
                first[contract].extend([count]*(len(xs)-len(first[contract])))
                moves=[m for m in chan.same_level_decompose(xs) if m.complete]
                f1=[m3_xd_shape(m) for m in moves];expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual(f1,[m3_xd_expected(units,s) for s in expected]);self.assertEqual(f1[:len(prior_f1[contract])],prior_f1[contract]);prior_f1[contract]=f1
                for m in moves:
                    if m.seg_start not in f1_first[contract]:
                        f1_first[contract][m.seg_start]=count
                        types[contract].append(m3_xd_type('M1-source1:'+contract,m,visible,rows[count-1]['available_dt']))
                f2=chan.confirm_level_up(types[contract],rows[count-1]['available_dt'],'F2')
                self.assertEqual(len(f2),int(count>=a['f2_first'][contract]))
                if f2:
                    if contract not in frozen_f2:frozen_f2[contract]=f2[0]
                    self.assertEqual(f2[0],frozen_f2[contract])
                    self.assertEqual((f2[0].kind,f2[0].direction,round(f2[0].low*1000),round(f2[0].high*1000),len(f2[0].evidence_ids)),('consolidation',None,666,1113,7))
                    self.assertEqual(f2[0].confirmed_dt,rows[a['f2_first'][contract]-1]['available_dt'])
                if count==len(observed):self.assertEqual(m3_xd_shape(chan.same_level_decompose(xs)[-1]),m3_xd_expected(units,a['tail']))
        self.assertEqual(total,7920)
        for contract,(_,units,a,_) in inputs.items():
            self.assertEqual(first[contract],[u['confirmed_raw_count'] for u in units])
            self.assertEqual(tuple(f1_first[contract][s[0]] for s in a['f1']),a['f1_first'][contract])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types[contract]),a['f1_evidence'][contract])
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types[contract]]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types[contract])],[m3_xd_expected(records,s) for s in a['f2']])

    def test_empty_initial_triple_anchor_and_late_premise_keep_active_proofs_separate(self):
        for contract in ('current','fixed'):
            _,units,a,rows=m1_source_bridge_input(contract);late=a['head_counts'][contract][-1]
            for count in sorted({1,96,97,115,116,336,337,342,376,390,434,441,578,579,598,599,637,642,930,943,len(rows)}):
                _,_,bs=chan.chan_fx_bi(rows[:count],standard='106');bis=bs if contract=='current' else bs[:-1]
                actual=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(1,'down',1.107),available_bi=40)) if x.complete]
                expected=[u for u in units if max(late,u['confirmed_raw_count'])<=count]
                self.assertEqual(len(actual),len(expected),(contract,count));pub=40
                for x,u in zip(actual,expected):
                    pub=max(pub,u['proof_bi']);self.assertEqual((x.evidence_end_index,x.evidence_dt),(bis[pub].end_index,bis[pub].end_dt))
                if count==late:
                    self.assertEqual(len(actual),5)
                    self.assertEqual((round(bis[40].end_value*1000),str(bis[40].end_dt)),a['head_proof_first'][contract][-1][1:3])
            self.assertEqual(round((max(b.low for b in bis[:3])-min(b.high for b in bis[:3]))*1000),7)
            self.assertEqual(tuple(round(v*1000) for v in (max(b.low for b in bis[1:4]),min(b.high for b in bis[1:4]))),(1061,1083))
            with self.assertRaisesRegex(ValueError,'selected boundary'):
                chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'up',1.09),available_bi=0))
            with self.assertRaisesRegex(ValueError,'input beginning'):
                chan.find_xds(bis,origin_premise=dict(basis='no_prior_history',anchor=(1,'down',1.107),available_bi=1))
            self.assertFalse(any(x.complete for x in chan.find_xds(bis,origin_premise=dict(basis='unknown',anchor=(1,'down',1.107),available_bi=None))))
        self.assertFalse(a['automatic_origin_proven']);self.assertFalse(a['global_unique_origin_proven'])

    def test_new_F2_excludes_successor_extreme_and_does_not_supply_strict_points(self):
        def forbidden(a,b):raise AssertionError('盘整F2不得评估严格力度')
        for contract in ('current','fixed'):
            _,units,a,rows=m1_source_bridge_input(contract);types=[]
            for s,at in zip(a['f1'],a['f1_first'][contract]):
                visible=[u for u in units if u['confirmed_raw_count']<=at]
                move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),at)) if m.complete and m.seg_start==s[0])
                types.append(m3_xd_type('M1-source1:'+contract,move,visible,rows[at-1]['available_dt']))
            self.assertEqual((types[1].direction,types[3].direction),('up',None))
            self.assertLess(types[1].end_price,types[1].start_price)
            self.assertEqual(round(types[6].high*1000),a['proof_high_excluded'])
            for count in (a['f2_first'][contract]-1,a['f2_first'][contract],len(rows)):
                now=rows[count-1]['available_dt'];f2=chan.confirm_level_up(types,now,'F2')
                self.assertEqual(len(f2),int(count>=a['f2_first'][contract]))
                if f2:
                    self.assertEqual(round(f2[0].high*1000),1113)
                    self.assertEqual(chan.confirm_level_up(f2,now,'F3'),[])
                self.assertEqual(chan.scan_strict_divergence(types,now,'F2',forbidden,'guard').results,())
                self.assertFalse(chan.scan_first_points(types,rows[:count],now,'F2').points)
                self.assertFalse(any(chan.analyze_point_chain(types,rows[:count],now,'F2')))
            _,_,old,_,_=m1_full_suffix_input(contract)
            self.assertEqual(len(old['f1']),8);self.assertIsNone(old['f2'][0][-1])


# 源BI1的自动递归和显式中枢条件消费；Q仅作旧几何上下文，不冒充A后新生。
M3_M1_SOURCE_CONSUMERS_AUDIT = {'attempt_totals': {'before_center_known': 4, 'established': 3, 'fail': 11},
 'attempts': {'A': (('sell3', 4, 5, 26, 1022, 'before_center_known'),
                    ('buy3', 19, 20, -192, 915, 'fail'),
                    ('sell3', 20, 21, -70, 1118, 'fail'),
                    ('buy3', 21, 22, -122, 985, 'fail'),
                    ('sell3', 22, 23, -88, 1136, 'fail'),
                    ('buy3', 23, 24, -116, 991, 'fail'),
                    ('sell3', 24, 25, -69, 1117, 'fail'),
                    ('buy3', 25, 26, -91, 1016, 'fail'),
                    ('sell3', 26, 27, -51, 1099, 'fail'),
                    ('sell3', 28, 29, 0, 1048, 'established')),
              'B': (('buy3', 9, 10, -278, 666, 'before_center_known'),
                    ('sell3', 10, 11, 35, 867, 'established')),
              'C': (('sell3', 16, 17, -39, 792, 'fail'),
                    ('sell3', 18, 19, -449, 1202, 'fail'),
                    ('buy3', 19, 20, 94, 915, 'established')),
              'D': (('buy3', 23, 24, -127, 991, 'before_center_known'), ('sell3', 28, 29, -63, 1048, 'fail')),
              'Q': (('buy3', 31, 32, 14, 1062, 'before_center_known'),)},
 'auto': ((0, 19, 'down', 'down', (0, 6, 11), ((1048, 1107), (902, 944), (753, 821)), 22),
          (20, 32, 'consolidation', None, (20,), ((985, 1118),), None)),
 'auto_envelope': (666, 1202),
 'auto_evidence': 23,
 'auto_first': {'current': 3317, 'fixed': 3323},
 'auto_net_direction': 'up',
 'auto_spans': (((0, 2, 4), (6, 8, 10), (11, 13, 19)), ((20, 22, 32),)),
 'automatic_origin_proven': False,
 'candidates': ((11, (4, 5), (10,), 19, True, None),
                (12, (4, 5), (10, 11), 19, True, True),
                (13, (4, 5), (10, 11, 12), 19, True, True),
                (15, (10,), (14,), 12, None, None),
                (17, (10,), (16,), 12, None, None),
                (19, (10,), (18,), 12, None, None)),
 'completed_leave': (),
 'completed_reference': (10,),
 'contexts': {'A': (0, 2, 1048, 1107, None),
              'B': (6, 8, 902, 944, None),
              'C': (11, 13, 753, 821, None),
              'D': (20, 22, 985, 1118, None),
              'Q': (28, 30, 1001, 1048, None)},
 'first_exclusion': 'no_directional_compare_legs',
 'initial_wave_overlap_ticks': 31,
 'known_raw': {'current': {'A': 376, 'B': 1123, 'C': 2226, 'D': 3317, 'Q': 3831},
               'fixed': {'A': 390, 'B': 1143, 'C': 2235, 'D': 3323, 'Q': 3849}},
 'legacy_Q_is_newborn_proven': False,
 'limits': {'current': 3942, 'fixed': 3978},
 'missing_actual_sizes': (20, 22, 27, 29),
 'newborn_after_A': (30, 32, 14),
 'point_order': ('B', 'C', 'A'),
 'point_raw': {'current': {'A': 3815, 'B': 1895, 'C': 3188}, 'fixed': {'A': 3822, 'B': 1919, 'C': 3198}},
 'points': {'A': ('sell3', 28, 29, 1048, 0), 'B': ('sell3', 10, 11, 867, 35), 'C': ('buy3', 19, 20, 915, 94)},
 'reference_sha256': 'c64ff7a8e7fd373d06a617210964d1a8a345f944e7ea2785d00a5e621c8d3844',
 'roles': {'A': {'closed_by': 6,
                 'core_basis': 'three_units',
                 'dd': 991,
                 'frozen_by_departure': False,
                 'gg': 1113,
                 'zd': 1048,
                 'zg': 1107,
                 'zn': (0, 2, 4)},
           'B': {'closed_by': 12,
                 'core_basis': 'three_units',
                 'dd': 666,
                 'frozen_by_departure': False,
                 'gg': 1022,
                 'zd': 902,
                 'zg': 944,
                 'zn': (6, 8, 10)},
           'C': {'closed_by': 21,
                 'core_basis': 'three_units',
                 'dd': 666,
                 'frozen_by_departure': False,
                 'gg': 1202,
                 'zd': 753,
                 'zg': 821,
                 'zn': (11, 13, 15, 17, 19)},
           'D': {'closed_by': None,
                 'core_basis': 'three_units',
                 'dd': 915,
                 'frozen_by_departure': False,
                 'gg': 1202,
                 'zd': 985,
                 'zg': 1118,
                 'zn': (20, 22, 24, 26, 28, 30, 32)},
           'Q': {'closed_by': 32,
                 'core_basis': 'three_units',
                 'dd': 981,
                 'frozen_by_departure': False,
                 'gg': 1099,
                 'zd': 1001,
                 'zg': 1048,
                 'zn': (28, 30)}},
 'schema': 'M1-source-BI1-XD-consumers-v02',
 'scope': 'given_recent_source_BI1_and_explicit_centers_not_automatic_theory_levels',
 'source_reference_sha256': '4fa3621c81a27cc74b5153f7fbb64d0b10d21ffc9ca66f0073632b2401559e11',
 'source_sha256': '5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
 'strict_reasons': ((),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('no_comparable_center_tail',),
                    ('no_compare_legs',),
                    (),
                    (),
                    (),
                    ('no_compare_legs',),
                    (),
                    ('no_compare_legs',),
                    (),
                    ('no_compare_legs',),
                    (),
                    ('no_compare_legs',),
                    ('center_waves_overlap',),
                    ('center_waves_overlap',),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers'),
                    ('no_compare_legs', 'not_two_separated_centers')),
 'terminal_counts': {'current': 3, 'fixed': 3}}


def m1_source_consumers_input(contract):
    """保留实际确认时刻与给定中枢身份；条件三类不自动归入一类组合链。"""
    case,units,source,rows=m1_source_bridge_input(contract);a=M3_M1_SOURCE_CONSUMERS_AUDIT
    if (a['source_reference_sha256']!=source['reference_sha256'] or a['source_sha256']!=source['source_sha256']):
        raise AssertionError('M1消费者须绑定同一显式源BI1证书')
    root='M1-source1-consumers:'+contract+':'+a['reference_sha256']
    moves=[chan.ConfirmedMove(root+':xd:'+str(i),'source1-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           rows[u['confirmed_raw_count']-1]['available_dt']) for i,u in enumerate(units)]
    contexts=[chan.ThirdPointContext(root+':context:'+name,'source1-center','source1-XD',
              chan.ConfirmedCenter(root+':center:'+name,'source1-center',spec[2]/1000.,spec[3]/1000.,
              rows[a['known_raw'][contract][name]-1]['available_dt'])) for name,spec in a['contexts'].items()]
    return case,units,a,rows,moves,contexts


class TestM1SourceConsumers(unittest.TestCase):
    """课20/29/35/37/101：源BI1条件递归、显式中枢与首次回试的独立角色。"""

    def _assert_strict(self,moves,now,a):
        def forbidden(x,y):raise AssertionError('开放候选或缺比较腿不评估力度')
        size=len(moves);scan=chan.scan_strict_divergence(moves,now,'auto-source1-F1',forbidden,'guard')
        c=next((c for c in a['candidates'] if c[0]==size),None)
        self.assertEqual(len(scan.results),int(c is not None))
        self.assertEqual(tuple(r for _,r in scan.skipped),a['strict_reasons'][size])
        self.assertEqual(scan.completed_types,int(size>=23))
        if c:
            _,reference,leave,gap,new_extreme,third=c;point,=scan.results
            self.assertEqual((point.kind,point.status,point.reason),('buy1','candidate','trend_open'))
            self.assertEqual(point.reference_ids,tuple(moves[i].move_id for i in reference))
            self.assertEqual(point.leave_ids,tuple(moves[i].move_id for i in leave))
            self.assertEqual(dict(point.conditions),dict(trend=None,separated_centers=True,new_extreme=new_extreme,leave_third_point=third))
            self.assertEqual((point.force_method,point.force_reference,point.force_leave),(None,None,None))
            self.assertEqual(point.confirmed_dt,moves[-1].confirmed_dt)
        return scan

    def test_given_prefixes_keep_six_open_candidates_separate_from_completed_engineering_down(self):
        for contract in ('current','fixed'):
            _,units,a,rows,moves,_=m1_source_consumers_input(contract);saved=None;identity=None
            # Widths are given-input prefixes; raw same-batch impossibilities are checked separately.
            for size in range(34):
                now=moves[size-1].confirmed_dt if size else rows[0]['available_dt'];visible=moves[:size]
                scan=self._assert_strict(visible,now,a)
                if scan.results:
                    if identity is None:identity=scan.results[0].divergence_id
                    self.assertEqual(scan.results[0].divergence_id,identity)
                types=chan.confirm_level_up(visible,now,'auto-source1-F1')
                self.assertEqual(len(types),int(size>=23))
                if types:
                    if saved is None:saved=types[0]
                    self.assertEqual(types,[saved])
                    self.assertEqual((saved.kind,saved.direction,round(saved.start_price*1000),round(saved.end_price*1000),len(saved.evidence_ids)),('down','down',1107,1202,23))
                    self.assertEqual(saved.to_confirmed_move().direction,'up')
                first=chan.scan_first_points(visible,rows,now,'auto-source1-F1')
                self.assertEqual(first.points,[])
                self.assertEqual(tuple(r for _,r in first.exclusions),(a['first_exclusion'],) if size>=23 else ())
                self.assertFalse(any(chan.analyze_point_chain(visible,rows,now,'auto-source1-F1')))
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(moves)],[m3_xd_expected(units,s) for s in a['auto']])
            self.assertEqual(saved.confirmed_dt,rows[a['auto_first'][contract]-1]['available_dt'])
            self.assertEqual(a['auto_first'][contract],M3_M1_SOURCE_BRIDGE_AUDIT['f2_first'][contract])
            self.assertNotEqual((round(saved.low*1000),round(saved.high*1000)),M3_M1_SOURCE_BRIDGE_AUDIT['f2_envelope'])
            for name,spec in a['roles'].items():
                actual=chan.find_zs(m3_xd_parts(dict(units=units),len(rows))[spec['zn'][0]:spec['zn'][-1]+1])[0]
                self.assertEqual(tuple(round(v*1000) for v in (actual.zd,actual.zg,actual.dd,actual.gg)),tuple(spec[k] for k in ('zd','zg','dd','gg')))

    def test_raw_boundaries_bind_actual_XDs_causal_centers_and_three_first_points(self):
        total=0
        for contract in ('current','fixed'):
            _,units,a,rows,given,contexts=m1_source_consumers_input(contract);first={};previous={};saved=None;sizes=set()
            counts=sorted({1,len(rows)}|{n for u in units for n in (u['confirmed_raw_count']-1,u['confirmed_raw_count']) if 0<n<=len(rows)})
            for count in counts:
                _,_,bs=chan.chan_fx_bi(rows[:count],standard='106');bis=bs if contract=='current' else bs[:-1]
                xs=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(1,'down',1.107),available_bi=1)) if x.complete]
                expected=[u for u in units if u['confirmed_raw_count']<=count];self.assertEqual(len(xs),len(expected));visible=[];sizes.add(len(xs))
                for i,(x,u) in enumerate(zip(xs,expected)):
                    self.assertEqual(tuple(round(v*1000) for v in (x.start_value,x.end_value,x.low,x.high)),tuple(u[k] for k in ('start_ticks','end_ticks','low_ticks','high_ticks')))
                    visible.append(given[i]._replace(direction=x.direction,start_dt=x.start_dt,end_dt=x.end_dt,
                                   start_price=x.start_value,end_price=x.end_value,low=x.low,high=x.high))
                now=rows[count-1]['available_dt'];self._assert_strict(visible,now,a)
                types=chan.confirm_level_up(visible,now,'auto-source1-F1')
                self.assertEqual(len(types),int(count>=a['auto_first'][contract]))
                if types:
                    if saved is None:saved=types[0]
                    self.assertEqual(types,[saved])
                active=[]
                for context in contexts:
                    name=context.context_id.rsplit(':',1)[1];start,formed,zd,zg,_=a['contexts'][name]
                    if formed>=len(xs):continue
                    center=chan.find_zs(xs[start:formed+1])[0]
                    self.assertEqual((round(center.zd*1000),round(center.zg*1000)),(zd,zg));active.append(context)
                points=chan.find_third_points(visible,active,now)
                names=[n for n in a['point_order'] if a['point_raw'][contract][n]<=count]
                self.assertEqual(len(points),len(names))
                for point,name in zip(points,names):
                    kind,leave,pull,price,margin=a['points'][name]
                    self.assertEqual((point.kind,point.leave_move_id,point.pull_move_id,round(point.price*1000)),(kind,given[leave].move_id,given[pull].move_id,price))
                    self.assertEqual((point.dt,point.confirmed_dt),(given[pull].end_dt,rows[a['point_raw'][contract][name]-1]['available_dt']))
                    if name in previous:self.assertEqual(point,previous[name])
                    previous[name]=point;first.setdefault(name,count)
                total+=1
            self.assertEqual(first,a['point_raw'][contract]);self.assertEqual(set(range(34))-sizes,set(a['missing_actual_sizes']))
        self.assertEqual(total,120)

    def test_old_Q_geometry_cannot_backfill_confirmation_or_replace_A_newborn(self):
        for contract in ('current','fixed'):
            _,units,a,rows,moves,contexts=m1_source_consumers_input(contract);now=rows[-1]['available_dt'];named={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            self.assertEqual(len(chan.find_third_points(moves,contexts,now)),3)
            self.assertEqual(units[32]['low_ticks']-a['roles']['Q']['zg'],14)
            self.assertEqual(chan.find_third_points(moves,[named['Q']],now),[])
            self.assertGreater(named['Q'].center.confirmed_dt,moves[31].start_dt)
            for delta in (-1,0,1):
                changed=named['Q']._replace(center=named['Q'].center._replace(confirmed_dt=moves[31].start_dt+timedelta(microseconds=delta)))
                points=chan.find_third_points(moves,[changed],now)
                self.assertEqual(len(points),int(delta<=0))
                if points:self.assertEqual((points[0].kind,points[0].leave_move_id,points[0].pull_move_id),('buy3',moves[31].move_id,moves[32].move_id))
            start,end,gap=a['newborn_after_A'];self.assertEqual(start,a['points']['A'][2]+1)
            self.assertEqual(max(u['low_ticks'] for u in units[start:end+1])-min(u['high_ticks'] for u in units[start:end+1]),gap)
            self.assertEqual(chan.find_zs(m3_xd_parts(dict(units=units),len(rows))[start:end+1]),[])
            self.assertNotEqual(a['contexts']['Q'][0],start)
            self.assertFalse(a['legacy_Q_is_newborn_proven']);self.assertFalse(a['automatic_origin_proven'])

    def test_touch_A_late_returns_and_future_payloads_preserve_confirmed_identities(self):
        for contract in ('current','fixed'):
            _,_,a,rows,moves,contexts=m1_source_consumers_input(contract);now=rows[-1]['available_dt'];named={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            for delta in (-1,0,1):
                changed=list(moves[:30]);edge=(1048+delta)/1000.;changed[29]=changed[29]._replace(end_price=edge,high=edge)
                for mirror in (False,True):
                    supplied=changed;context=named['A']
                    if mirror:
                        flip=lambda v:(3000-round(v*1000))/1000.
                        supplied=[m._replace(direction='down' if m.direction=='up' else 'up',start_price=flip(m.start_price),end_price=flip(m.end_price),low=flip(m.high),high=flip(m.low)) for m in changed]
                        context=context._replace(center=context.center._replace(zd=flip(context.center.zg),zg=flip(context.center.zd)))
                    points=chan.find_third_points(supplied,[context],now);self.assertEqual(len(points),int(delta<=0))
                    if points:self.assertEqual(points[0].kind,'buy3' if mirror else 'sell3')
            base=chan.confirm_level_up(moves,now,'auto-source1-F1');late=moves[22].confirmed_dt+timedelta(days=1);delayed=list(moves)
            for i in range(22,len(moves)):delayed[i]=moves[i]._replace(confirmed_dt=max(late,moves[i].confirmed_dt))
            self.assertEqual(chan.confirm_level_up(delayed,late-timedelta(microseconds=1),'auto-source1-F1'),[])
            after,=chan.confirm_level_up(delayed,late,'auto-source1-F1')
            self.assertEqual(after,base[0]._replace(confirmed_dt=late))
            for name,(kind,leave,pull,price,margin) in a['points'].items():
                delayed=list(moves);late=moves[pull].confirmed_dt+timedelta(days=1);delayed[pull]=moves[pull]._replace(confirmed_dt=late)
                for i in range(pull+1,len(moves)):delayed[i]=moves[i]._replace(confirmed_dt=max(moves[i].confirmed_dt,delayed[i-1].confirmed_dt))
                context=named[name]
                self.assertEqual(chan.find_third_points(delayed,[context],late-timedelta(microseconds=1)),[])
                point,=chan.find_third_points(delayed,[context],late)
                self.assertEqual((point.leave_move_id,point.pull_move_id,point.confirmed_dt),(moves[leave].move_id,moves[pull].move_id,late))
                future=moves[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=late+timedelta(days=10))
                future_context=context._replace(context_id=None,center=context.center._replace(center_id=None,zd=float('nan'),confirmed_dt=late+timedelta(days=10)))
                self.assertEqual(chan.find_third_points(delayed+[future],[context,future_context],late),[point])
            future=moves[-1]._replace(move_id=None,level=None,high=float('nan'),confirmed_dt=now+timedelta(days=10))
            self.assertEqual(chan.scan_strict_divergence(moves+[future],now,'auto-source1-F1'),chan.scan_strict_divergence(moves,now,'auto-source1-F1'))
            poisoned=rows+[dict(dt=now+timedelta(days=10),closed_dt=now+timedelta(days=10),available_dt=now+timedelta(days=11),high=float('nan'))]
            self.assertEqual(chan.scan_first_points(moves+[future],poisoned,now,'auto-source1-F1'),chan.scan_first_points(moves,rows,now,'auto-source1-F1'))


# S3给定源BI0的两段头部；原BI10后缀及其旧角色继续保留。
M3_S3_SOURCE_BRIDGE_AUDIT = {'anchor': (0, 'down', 3939),
 'auto': (0, 13, 'up', 'up', (0, 8), ((3579, 3865), (4602, 4642)), None),
 'auto_spans': ((0, 2, 7), (8, 10, 11)),
 'automatic_origin_proven': False,
 'available_bi': 0,
 'candidates': ((12, (7,), (11,), 411, True, None),
                (13, (7,), (11, 12), 411, True, True),
                (14, (7,), (11, 12, 13), 411, True, True)),
 'f1': ((0, 2, 'consolidation', None, (0,), ((3579, 3865),), 3),
        (3, 6, 'consolidation', None, (3,), ((3550, 3745),), 7),
        (7, 9, 'consolidation', None, (7,), ((4488, 4642),), 10)),
 'f1_evidence': {'current': (4, 8, 11), 'fixed': (4, 8, 11)},
 'f1_first': {'current': (232, 701, 771), 'fixed': (239, 705, 776)},
 'f2': (0, 2, 'consolidation', None, (0,), ((3615, 3939),), None),
 'gap_ticks': 124,
 'global_unique_origin_proven': False,
 'head_counts': {'current': (112, 112), 'fixed': (126, 126)},
 'head_events': ((0, 2, 2, 12), (3, 9, 1, 12)),
 'head_proof_first': {'current': ((112, 3604, '2021-06-21 00:00:00'), (112, 3604, '2021-06-21 00:00:00')),
                      'fixed': ((126, 3579, '2021-06-30 00:00:00'), (126, 3579, '2021-06-30 00:00:00'))},
 'head_units': ({'direction': 'down',
                 'end_dt': '2021-03-05 00:00:00',
                 'end_index': 36,
                 'end_ticks': 3463,
                 'evidence_dt': '2021-06-30 00:00:00',
                 'evidence_end_index': 102,
                 'high_ticks': 3939,
                 'low_ticks': 3463,
                 'mode': 2,
                 'proof_bi': 12,
                 'start_dt': '2021-01-06 00:00:00',
                 'start_index': 2,
                 'start_ticks': 3939},
                {'direction': 'up',
                 'end_dt': '2021-05-26 00:00:00',
                 'end_index': 83,
                 'end_ticks': 3865,
                 'evidence_dt': '2021-06-30 00:00:00',
                 'evidence_end_index': 102,
                 'high_ticks': 3865,
                 'low_ticks': 3463,
                 'mode': 1,
                 'proof_bi': 12,
                 'start_dt': '2021-03-05 00:00:00',
                 'start_index': 36,
                 'start_ticks': 3463}),
 'limits': {'current': 1349, 'fixed': 1350},
 'reference_sha256': '14de7d5386a27111aede0fa1d9807d4c942779975a6e52a3666cc4da9c09bd52',
 'rejected': ((3, 6, -27, 7), (3, 8, -39, 9)),
 'schema': 'S3-source0-whole-F1-F2-auto-v01',
 'scope': 'given_recent_BI0_not_automatic_global_origin',
 'source_sha256': 'ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
 'strict_reasons': ((),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('not_two_separated_centers',),
                    ('no_compare_legs',),
                    (),
                    (),
                    ()),
 'suffix_certificate_sha256': '16ed57fbacc688fdc552b82ad16ee41b820fe3ea3db5de8eaffe9ecbae2d0161',
 'tail': (10, 13, 'consolidation', 'down', (11,), ((5231, 5586),), None)}


def s3_source_bridge_input(contract):
    """原日线双合同；头部固定几何与实际活动证明版本分开。"""
    case,suffix,old,rows,_=expanded_suffix_input('S3',contract);a=M3_S3_SOURCE_BRIDGE_AUDIT
    if (a['source_sha256']!=old['fixture_sha256'] or a['suffix_certificate_sha256']!=old['certificate_sha256']):
        raise AssertionError('S3源桥接须绑定同一已验BI10后缀')
    head=[dict(u,local_raw_count=n,confirmed_raw_count=n) for u,n in zip(a['head_units'],a['head_counts'][contract])]
    units=head+suffix;root='S3-source0:'+contract+':'+a['reference_sha256']
    given=[chan.ConfirmedMove(root+':xd:'+str(i),'source0-XD',u['direction'],date(u['start_dt']),date(u['end_dt']),
           u['start_ticks']/1000.,u['end_ticks']/1000.,u['low_ticks']/1000.,u['high_ticks']/1000.,
           rows[u['confirmed_raw_count']-1]['available_dt']) for i,u in enumerate(units)]
    return case,units,a,rows,given


class TestS3SourceBridge(unittest.TestCase):
    """课67/71/78及35/38：显式源BI0的第二种头部、完整F1及开放F2/自动类型。"""

    def test_original_raw_contracts_join_same_batch_heads_and_rebuild_three_complete_F1(self):
        inputs={c:s3_source_bridge_input(c) for c in ('current','fixed')};rows=inputs['fixed'][3]
        first={c:[] for c in inputs};first_f1={c:{} for c in inputs};types={c:[] for c in inputs}
        previous={c:[] for c in inputs};previous_f1={c:[] for c in inputs};cache={};total=0
        for count in range(1,len(rows)+1):
            _,_,bs=chan.chan_fx_bi(rows[:count],standard='106')
            for contract,(_,units,a,observed,_) in inputs.items():
                if count>len(observed):continue
                total+=1;bis=bs if contract=='current' else bs[:-1]
                key=tuple((b.direction,b.start_index,b.end_index,b.start_dt,b.end_dt,b.start_value,b.end_value) for b in bis)
                if contract not in cache or cache[contract][0]!=key:
                    xs=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',3.939),available_bi=0)) if x.complete];cache[contract]=(key,xs)
                else:xs=cache[contract][1]
                visible=[u for u in units if u['confirmed_raw_count']<=count];self.assertEqual(len(xs),len(visible));shapes=[];pub=0
                for x,u in zip(xs,visible):
                    shape=(x.direction,str(x.start_dt),str(x.end_dt),round(x.start_value*1000),round(x.end_value*1000),round(x.low*1000),round(x.high*1000),x.mode)
                    self.assertEqual(shape,tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode')))
                    pub=max(pub,u['proof_bi']);self.assertEqual((x.evidence_end_index,x.evidence_dt),(bis[pub].end_index,bis[pub].end_dt));shapes.append(shape)
                self.assertEqual(shapes[:len(previous[contract])],previous[contract]);previous[contract]=shapes
                first[contract].extend([count]*(len(xs)-len(first[contract])))
                moves=[m for m in chan.same_level_decompose(xs) if m.complete];f1=[m3_xd_shape(m) for m in moves]
                expected=[s for s in a['f1'] if units[s[-1]]['confirmed_raw_count']<=count]
                self.assertEqual(f1,[m3_xd_expected(units,s) for s in expected]);self.assertEqual(f1[:len(previous_f1[contract])],previous_f1[contract]);previous_f1[contract]=f1
                for move in moves:
                    if move.seg_start not in first_f1[contract]:
                        first_f1[contract][move.seg_start]=count
                        types[contract].append(m3_xd_type('S3-source0:'+contract,move,visible,rows[count-1]['available_dt']))
                self.assertEqual(chan.confirm_level_up(types[contract],rows[count-1]['available_dt'],'F2'),[])
                if count==len(observed):self.assertEqual(m3_xd_shape(chan.same_level_decompose(xs)[-1]),m3_xd_expected(units,a['tail']))
        self.assertEqual(total,2699)
        for contract,(_,units,a,_,_) in inputs.items():
            self.assertEqual(first[contract],[u['confirmed_raw_count'] for u in units])
            self.assertEqual(tuple(first_f1[contract][s[0]] for s in a['f1']),a['f1_first'][contract])
            self.assertEqual(tuple(len(t.evidence_ids) for t in types[contract]),a['f1_evidence'][contract])
            records=[dict(start_dt=str(t.start_dt),end_dt=str(t.end_dt),low_ticks=round(t.low*1000),high_ticks=round(t.high*1000)) for t in types[contract]]
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(types[contract])],[m3_xd_expected(records,a['f2'])])
            self.assertEqual(len(types[contract]),3);self.assertEqual(len(units),14)

    def test_BI12_proof_versions_and_late_origin_wait_without_backfilling_F1(self):
        for contract in ('current','fixed'):
            _,units,a,rows,_=s3_source_bridge_input(contract);old=M3_EXPANDED_SUFFIX_AUDIT['S3']
            at=a['head_counts'][contract][0];late=old['clocks'][contract]['published'][3]
            saved=None
            for count in sorted({at-1,at,a['f1_first'][contract][0],late-1,late,len(rows)}):
                _,_,bs=chan.chan_fx_bi(rows[:count],standard='106');bis=bs if contract=='current' else bs[:-1]
                normal=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',3.939),available_bi=0)) if x.complete]
                if count==at:
                    self.assertEqual(len(normal),2)
                    self.assertEqual((count,round(bis[12].end_value*1000),str(bis[12].end_dt)),a['head_proof_first'][contract][0])
                    self.assertEqual((normal[0].evidence_dt,normal[1].evidence_dt),(bis[12].end_dt,bis[12].end_dt))
                actual=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',3.939),available_bi=42)) if x.complete]
                visible=[u for u in units if max(late,u['confirmed_raw_count'])<=count]
                self.assertEqual(len(actual),len(visible));pub=42
                for x,u in zip(actual,visible):
                    pub=max(pub,u['proof_bi']);self.assertEqual((x.evidence_end_index,x.evidence_dt),(bis[pub].end_index,bis[pub].end_dt))
                completed=[m for m in chan.same_level_decompose(actual) if m.complete]
                if count<late:self.assertEqual(completed,[])
                if count==late:
                    self.assertEqual(len(actual),6);self.assertEqual(len(completed),1)
                    saved=m3_xd_type('S3-late42:'+contract,completed[0],visible,rows[count-1]['available_dt'])
                    self.assertEqual((saved.confirmed_dt,len(saved.evidence_ids)),(rows[late-1]['available_dt'],6))
            self.assertGreater(late,a['f1_first'][contract][0]);self.assertIsNotNone(saved)
            self.assertFalse(any(x.complete for x in chan.find_xds(bis,origin_premise=dict(basis='unknown',anchor=(0,'down',3.939),available_bi=None))))
        self.assertFalse(a['automatic_origin_proven']);self.assertFalse(a['global_unique_origin_proven'])

    def test_source_whole_automatic_type_is_open_with_three_sell_candidates(self):
        def forbidden(x,y):raise AssertionError('开放候选不评估力度')
        for contract in ('current','fixed'):
            _,units,a,rows,given=s3_source_bridge_input(contract);identity=None;candidate_sizes=[]
            for width in range(15):
                now=given[width-1].confirmed_dt if width else rows[0]['available_dt'];moves=given[:width]
                scan=chan.scan_strict_divergence(moves,now,'auto-source0-F1',forbidden,'guard')
                expected=next((c for c in a['candidates'] if c[0]==width),None)
                self.assertEqual((scan.completed_types,len(scan.results)),(0,int(expected is not None)))
                self.assertEqual(tuple(r for _,r in scan.skipped),a['strict_reasons'][width])
                if expected:
                    _,reference,leave,gap,made,third=expected;p,=scan.results;candidate_sizes.append(width)
                    self.assertEqual((p.kind,p.status,p.reason),('sell1','candidate','trend_open'))
                    self.assertEqual((p.reference_ids,p.leave_ids),(tuple(moves[i].move_id for i in reference),tuple(moves[i].move_id for i in leave)))
                    self.assertEqual(dict(p.conditions),dict(trend=None,separated_centers=True,new_extreme=made,leave_third_point=third))
                    self.assertEqual((p.force_method,p.force_reference,p.force_leave),(None,None,None))
                    if identity is None:identity=p.divergence_id
                    self.assertEqual(p.divergence_id,identity)
                self.assertEqual(chan.confirm_level_up(moves,now,'auto-source0-F1'),[])
                first=chan.scan_first_points(moves,rows,now,'auto-source0-F1')
                self.assertEqual((first.points,first.exclusions,first.completed_types),([],(),0))
                self.assertFalse(any(chan.analyze_point_chain(moves,rows,now,'auto-source0-F1')))
            self.assertEqual(candidate_sizes,[12,13,14])
            self.assertEqual([m3_xd_shape(m) for m in chan.level_up(given)],[m3_xd_expected(units,a['auto'])])
            self.assertEqual(set(range(15))-{sum(u['confirmed_raw_count']<=n for u in units) for n in range(1,len(rows)+1)},{1})
            _,_,old,_,_=expanded_suffix_input('S3',contract)
            self.assertIsNotNone(old['auto'][0][-1]);self.assertIsNone(a['auto'][-1])

    def test_F2_three_types_and_delayed_tail_keep_open_candidates_and_future_prices_separate(self):
        for contract in ('current','fixed'):
            _,units,a,rows,given=s3_source_bridge_input(contract);now=rows[-1]['available_dt'];types=[]
            for s,at in zip(a['f1'],a['f1_first'][contract]):
                visible=[u for u in units if u['confirmed_raw_count']<=at]
                move=next(m for m in chan.same_level_decompose(m3_xd_parts(dict(units=units),at)) if m.complete and m.seg_start==s[0])
                types.append(m3_xd_type('S3-source0:'+contract,move,visible,rows[at-1]['available_dt']))
            self.assertEqual(chan.confirm_level_up(types,now,'F2'),[])
            self.assertEqual(chan.scan_strict_divergence(types,now,'F2').results,())
            self.assertFalse(chan.scan_first_points(types,rows,now,'F2').points)
            delayed=list(given);late=now+timedelta(days=1);delayed[-1]=given[-1]._replace(confirmed_dt=late)
            point,=chan.scan_strict_divergence(delayed,now,'auto-source0-F1').results
            self.assertEqual(point.leave_ids,tuple(g.move_id for g in given[11:13]))
            after,=chan.scan_strict_divergence(delayed,late,'auto-source0-F1').results
            self.assertEqual(point.divergence_id,after.divergence_id)
            self.assertEqual(after.leave_ids,tuple(g.move_id for g in given[11:14]))
            self.assertEqual(chan.confirm_level_up(delayed,late,'auto-source0-F1'),[])
            future=given[-1]._replace(move_id=None,level=None,high=float('nan'),confirmed_dt=now+timedelta(days=10))
            self.assertEqual(chan.scan_strict_divergence(given+[future],now,'auto-source0-F1'),chan.scan_strict_divergence(given,now,'auto-source0-F1'))
            poisoned=rows+[dict(dt=now+timedelta(days=10),closed_dt=now+timedelta(days=10),available_dt=now+timedelta(days=11),high=float('nan'))]
            self.assertEqual(chan.scan_first_points(given+[future],poisoned,now,'auto-source0-F1'),chan.scan_first_points(given,rows,now,'auto-source0-F1'))


# 源BI0显式中枢的双合同时间门控与自动谱系分层；不继承旧A身份。
M3_S3_SOURCE_CONSUMERS_AUDIT = {'attempt_totals': {'current': {'before_center_known': 2, 'established': 2, 'fail': 2},
                    'fixed': {'before_center_known': 3, 'established': 1, 'fail': 2}},
 'attempts': {'current': {'A': (('sell3', 4, 5, -498, 4077, 'fail'),
                                ('buy3', 5, 6, -73, 3834, 'fail'),
                                ('buy3', 7, 8, 623, 4488, 'established')),
                          'B': (('buy3', 11, 12, 589, 5231, 'before_center_known'),),
                          'C': (),
                          'P': (('buy3', 7, 8, 743, 4488, 'established'),),
                          'R': (('buy3', 11, 12, 589, 5231, 'before_center_known'),)},
              'fixed': {'A': (('sell3', 4, 5, -498, 4077, 'fail'),
                              ('buy3', 5, 6, -73, 3834, 'fail'),
                              ('buy3', 7, 8, 623, 4488, 'established')),
                        'B': (('buy3', 11, 12, 589, 5231, 'before_center_known'),),
                        'C': (),
                        'P': (('buy3', 7, 8, 743, 4488, 'before_center_known'),),
                        'R': (('buy3', 11, 12, 589, 5231, 'before_center_known'),)}},
 'automatic_origin_proven': False,
 'contexts': {'A': (0, 2, 3579, 3865, None),
              'B': (8, 10, 4602, 4642, None),
              'C': (11, 13, 5231, 5586, None),
              'P': (3, 5, 3550, 3745, None),
              'R': (7, 9, 4488, 4642, None)},
 'empty_triples': ((4, 47), (6, 411), (10, 544)),
 'f1_lineage': {'core': (3615, 3939),
                'directions_known': False,
                'first_raw': {'current': 771, 'fixed': 776},
                'version': 0,
                'wave': (3463, 4687)},
 'known_raw': {'current': {'A': 141, 'B': 771, 'C': 1344, 'P': 329, 'R': 745},
               'fixed': {'A': 149, 'B': 776, 'C': 1349, 'P': 334, 'R': 751}},
 'legacy_A_identity_inherited': False,
 'limits': {'current': 1349, 'fixed': 1350},
 'missing_actual_sizes': (1,),
 'old_event_mapping': ((0, 0),
                       (1, 1),
                       (2, 2),
                       (6, 4),
                       (8, 6),
                       (12, 8),
                       (13, 9),
                       (14, 10),
                       (15, 11),
                       (16, 12),
                       (17, 13)),
 'old_proof_change': (7, 5, 45, 42),
 'platform_verified': False,
 'point_order': ('A', 'P'),
 'point_raw': {'current': {'A': 726, 'P': 726}, 'fixed': {'A': 730}},
 'points': {'A': ('buy3', 7, 8, 4488, 623), 'P': ('buy3', 7, 8, 4488, 743)},
 'raw_boundaries': {'current': (1,
                                111,
                                112,
                                140,
                                141,
                                231,
                                232,
                                245,
                                246,
                                328,
                                329,
                                347,
                                348,
                                700,
                                701,
                                725,
                                726,
                                744,
                                745,
                                770,
                                771,
                                825,
                                826,
                                899,
                                900,
                                1343,
                                1344,
                                1349),
                    'fixed': (1,
                              125,
                              126,
                              148,
                              149,
                              238,
                              239,
                              255,
                              256,
                              333,
                              334,
                              354,
                              355,
                              704,
                              705,
                              729,
                              730,
                              750,
                              751,
                              775,
                              776,
                              829,
                              830,
                              910,
                              911,
                              1348,
                              1349,
                              1350)},
 'reference_sha256': '189cf1ac126a39fac0387018b1c7f38ce8e6175f208776f7f638e4d0dcb241bc',
 'roles': {'A': {'closed_by': 8,
                 'core_basis': 'three_units',
                 'dd': 3463,
                 'frozen_by_departure': False,
                 'gg': 4077,
                 'zd': 3579,
                 'zg': 3865,
                 'zn': (0, 2, 4, 6)},
           'B': {'closed_by': 12,
                 'core_basis': 'three_units',
                 'dd': 4488,
                 'frozen_by_departure': False,
                 'gg': 4687,
                 'zd': 4602,
                 'zg': 4642,
                 'zn': (8, 10)},
           'C': {'closed_by': None,
                 'core_basis': 'three_units',
                 'dd': 4602,
                 'frozen_by_departure': False,
                 'gg': 11977,
                 'zd': 5231,
                 'zg': 5586,
                 'zn': (11, 13)},
           'P': {'closed_by': 9,
                 'core_basis': 'three_units',
                 'dd': 3541,
                 'frozen_by_departure': False,
                 'gg': 4642,
                 'zd': 3550,
                 'zg': 3745,
                 'zn': (3, 5, 7)},
           'R': {'closed_by': 13,
                 'core_basis': 'three_units',
                 'dd': 3615,
                 'frozen_by_departure': False,
                 'gg': 5586,
                 'zd': 4488,
                 'zg': 4642,
                 'zn': (7, 9, 11)}},
 'schema': 'S3-source-BI0-XD-centers-third-lineage-v01',
 'scope': 'given_recent_BI0_with_explicit_centers_not_automatic_theory_levels',
 'source_reference_sha256': '14de7d5386a27111aede0fa1d9807d4c942779975a6e52a3666cc4da9c09bd52',
 'source_sha256': 'ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
 'terminal_counts': {'current': 2, 'fixed': 1},
 'xd_lineage_names': ('A', 'B'),
 'xd_versions': (('A', 2, 0, 3463, 3939, None),
                 ('A', 3, 1, 3463, 3939, None),
                 ('A', 4, 2, 3463, 3939, None),
                 ('A', 5, 3, 3463, 3939, None),
                 ('A', 6, 4, 3463, 4077, None),
                 ('A', 7, 5, 3463, 4077, None),
                 ('B', 10, 0, 4488, 4687, 'up_continue'),
                 ('B', 11, 1, 4488, 4687, None))}


def s3_source_consumers_input(contract):
    """沿用同一源BI0与原raw上限；形成时刻、中枢身份和自动级别分别给定。"""
    case,units,source,rows,moves=s3_source_bridge_input(contract);a=M3_S3_SOURCE_CONSUMERS_AUDIT
    if (a['source_reference_sha256'],a['source_sha256'])!=(source['reference_sha256'],source['source_sha256']):
        raise AssertionError('S3消费者须绑定同一显式源BI0证书')
    root='S3-source0-consumers:'+contract+':'+a['reference_sha256']
    contexts=[chan.ThirdPointContext(root+':context:'+name,'source0-center','source0-XD',
              chan.ConfirmedCenter(root+':center:'+name,'source0-center',spec[2]/1000.,spec[3]/1000.,
              rows[a['known_raw'][contract][name]-1]['available_dt'])) for name,spec in a['contexts'].items()]
    return case,units,a,rows,moves,contexts


class TestS3SourceConsumers(unittest.TestCase):
    """课20/35/101：源BI0的Zn、两时钟首回试和形成谱系不混用身份。"""

    def _assert_xd_lineage(self,moves,now,a):
        lineage=chan.track_center_lineage(moves,now,'source0-center','source0-upper');by_name={}
        expected=[s for s in a['xd_versions'] if s[1]<len(moves) and moves[s[1]].confirmed_dt<=now]
        self.assertEqual(len(lineage.events),len(expected));self.assertEqual(len(lineage.centers),len(expected))
        for event,(name,end,version,dd,gg,relation) in zip(lineage.events,expected):
            start=a['contexts'][name][0];snap=lineage.snapshot(event.center_id,event.version)
            self.assertEqual((event.kind,event.version,event.relation),('formed' if version==0 else 'extended',version,relation))
            self.assertEqual((event.source_center_ids,event.basis),((),None))
            if version==0:
                self.assertEqual(event.prev_center_id,by_name.get('A') if name=='B' else None);by_name[name]=event.center_id
            self.assertEqual(event.center_id,by_name[name]);self.assertEqual(event.confirmed_dt,moves[end].confirmed_dt)
            self.assertEqual(snap.unit_ids,tuple(m.move_id for m in moves[start:end+1]))
            self.assertEqual((round(snap.zd*1000),round(snap.zg*1000),round(snap.dd*1000),round(snap.gg*1000)),a['contexts'][name][2:4]+(dd,gg))
            self.assertEqual((snap.start_dt,snap.end_dt,snap.confirmed_dt),(moves[start].start_dt,moves[end].end_dt,moves[end].confirmed_dt))
        return lineage

    def test_actual_raw_boundaries_keep_explicit_first_points_and_both_lineage_layers_separate(self):
        total=0
        for contract in ('current','fixed'):
            _,units,a,rows,given,contexts=s3_source_consumers_input(contract);first={};saved={};types=[];seen=set();history=();snapshots={};sizes=set()
            for count in a['raw_boundaries'][contract]:
                _,_,bs=chan.chan_fx_bi(rows[:count],standard='106');bis=bs if contract=='current' else bs[:-1]
                xs=[x for x in chan.find_xds(bis,origin_premise=dict(basis='given_recent',anchor=(0,'down',3.939),available_bi=0)) if x.complete]
                expected=[u for u in units if u['confirmed_raw_count']<=count];self.assertEqual(len(xs),len(expected));sizes.add(len(xs));visible=[]
                for i,(x,u) in enumerate(zip(xs,expected)):
                    self.assertEqual(tuple(round(v*1000) for v in (x.start_value,x.end_value,x.low,x.high)),tuple(u[k] for k in ('start_ticks','end_ticks','low_ticks','high_ticks')))
                    self.assertEqual((x.start_dt,x.end_dt),(given[i].start_dt,given[i].end_dt))
                    visible.append(given[i]._replace(direction=x.direction,start_dt=x.start_dt,end_dt=x.end_dt,start_price=x.start_value,end_price=x.end_value,low=x.low,high=x.high))
                now=rows[count-1]['available_dt'];active=[]
                for context in contexts:
                    name=context.context_id.rsplit(':',1)[1];start,formed,zd,zg,_=a['contexts'][name]
                    if formed>=len(xs):continue
                    center=chan.find_zs(xs[start:formed+1])[0]
                    self.assertEqual((round(center.zd*1000),round(center.zg*1000)),(zd,zg));active.append(context)
                points=chan.find_third_points(visible,active,now);names=[name for name in a['point_order'] if a['point_raw'][contract].get(name,len(rows)+1)<=count]
                self.assertEqual(len(points),len(names))
                for point,name in zip(points,names):
                    kind,leave,pull,price,_=a['points'][name]
                    self.assertEqual((point.kind,point.leave_move_id,point.pull_move_id,round(point.price*1000)),(kind,given[leave].move_id,given[pull].move_id,price))
                    self.assertEqual((point.dt,point.confirmed_dt),(given[pull].end_dt,rows[a['point_raw'][contract][name]-1]['available_dt']))
                    if name in saved:self.assertEqual(point,saved[name])
                    first.setdefault(name,count);saved[name]=point
                lineage=self._assert_xd_lineage(visible,now,a);self.assertEqual(lineage.events[:len(history)],history)
                for identity,snap in snapshots.items():self.assertEqual(lineage.snapshot(*identity),snap)
                history=lineage.events;snapshots={(s.center_id,s.version):s for s in lineage.centers}
                for move in chan.same_level_decompose(xs):
                    if move.complete and move.seg_start not in seen:
                        seen.add(move.seg_start);types.append(m3_xd_type('S3-source0:'+contract,move,expected,now))
                f1_lineage,f1_contexts,f1_points=m3_xd_lineage_third(types,now);ready=count>=a['f1_lineage']['first_raw'][contract]
                self.assertEqual((len(f1_lineage.events),len(f1_contexts),len(f1_points)),(int(ready),int(ready),0))
                if ready:
                    snap,=f1_lineage.centers
                    self.assertEqual((round(snap.zd*1000),round(snap.zg*1000)),a['f1_lineage']['core'])
                    self.assertEqual((round(snap.dd*1000),round(snap.gg*1000)),a['f1_lineage']['wave'])
                    self.assertEqual(snap.confirmed_dt,rows[a['f1_lineage']['first_raw'][contract]-1]['available_dt'])
                self.assertEqual(chan.confirm_level_up(types,now,'F2'),[]);total+=1
            self.assertEqual(first,a['point_raw'][contract]);self.assertEqual(set(range(15))-sizes,set(a['missing_actual_sizes']))
            self.assertEqual(len(saved),a['terminal_counts'][contract])
            self.assertFalse(any(chan.analyze_point_chain(given,rows,rows[-1]['available_dt'],'auto-source0-F1')))
        self.assertEqual(total,56)

    def test_Zn_and_formed_snapshots_preserve_wave_roles_and_do_not_inherit_legacy_A(self):
        for contract in ('current','fixed'):
            case,units,a,rows,moves,contexts=s3_source_consumers_input(contract);now=rows[-1]['available_dt'];parts=m3_xd_parts(dict(units=units),len(rows))
            for name,role in a['roles'].items():
                center=chan.find_zs(parts[role['zn'][0]:role['zn'][-1]+1])[0]
                self.assertEqual((round(center.zd*1000),round(center.zg*1000)),(role['zd'],role['zg']))
                if name=='P':
                    # find_zs在XD6离开时封口；显式Zn逐同向触沿包含XD7，二者波动范围不同。
                    self.assertEqual((round(center.dd*1000),round(center.gg*1000),center.xd_count,center.end_dt),(3541,4077,3,moves[5].end_dt))
                    self.assertEqual((role['zn'],role['gg']),((3,5,7),4642))
                else:
                    self.assertEqual((round(center.dd*1000),round(center.gg*1000)),(role['dd'],role['gg']))
            lineage=self._assert_xd_lineage(moves,now,a);auto_contexts=[]
            for event in lineage.events:
                if event.kind!='formed':continue
                snap=lineage.snapshot(event.center_id,0);center=chan.ConfirmedCenter(snap.center_id,'source0-center',snap.zd,snap.zg,snap.confirmed_dt)
                auto_contexts.append(chan.ThirdPointContext('formed:'+snap.center_id,'source0-center','source0-XD',center))
            self.assertEqual(len(auto_contexts),2);auto_point,=chan.find_third_points(moves,auto_contexts,now)
            self.assertEqual((auto_point.kind,auto_point.leave_move_id,auto_point.pull_move_id),('buy3',moves[7].move_id,moves[8].move_id))
            self.assertEqual((a['roles']['A']['gg'],round(max(m.high for m in moves[:8])*1000)),(4077,4642))
            self.assertEqual(round(lineage.centers[3].gg*1000),3939)  # XD5反向高4077尚未成为Z成员。
            self.assertEqual(a['roles']['B']['dd']-a['roles']['A']['gg'],411)
            self.assertEqual((case['roles']['A']['zd'],case['roles']['A']['zg']),(3579,3865))
            self.assertNotEqual(tuple(case['roles']['A']['zn']),a['roles']['A']['zn'])
            self.assertFalse(a['legacy_A_identity_inherited']);self.assertFalse(a['automatic_origin_proven'])
            self.assertEqual(chan.confirm_level_up(moves,now,'auto-source0-F1'),[])
            self.assertEqual(chan.scan_first_points(moves,rows,now,'auto-source0-F1').points,[])
            for start,gap in a['empty_triples']:
                self.assertEqual(max(m.low for m in moves[start:start+3])>min(m.high for m in moves[start:start+3]),True)
                self.assertGreater(gap,0)

    def test_confirmation_gate_and_entire_first_return_have_distinct_mirrored_boundaries(self):
        for contract in ('current','fixed'):
            _,units,a,rows,moves,contexts=s3_source_consumers_input(contract);now=rows[-1]['available_dt'];named={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            self.assertEqual(round((moves[6].end_price-named['A'].center.zg)*1000),-31)
            self.assertEqual(round((moves[6].low-named['A'].center.zg)*1000),-73)
            for name in ('P','R','B'):
                leave,pull=(7,8) if name=='P' else (11,12);context=named[name]
                for delta in (-1,0,1):
                    changed=context._replace(center=context.center._replace(confirmed_dt=moves[leave].start_dt+timedelta(microseconds=delta)))
                    points=chan.find_third_points(moves,[changed],now);self.assertEqual(len(points),int(delta<=0))
                    if points:self.assertEqual((points[0].leave_move_id,points[0].pull_move_id),(moves[leave].move_id,moves[pull].move_id))
            self.assertEqual(named['P'].center.confirmed_dt<=moves[7].start_dt,contract=='current')
            for delta in (-1,0,1):
                changed=list(moves);changed[8]=moves[8]._replace(low=(3865+delta)/1000.)
                for mirror in (False,True):
                    supplied=changed;context=named['A']
                    if mirror:
                        flip=lambda v:(30000-round(v*1000))/1000.
                        supplied=[m._replace(direction='down' if m.direction=='up' else 'up',start_price=flip(m.start_price),end_price=flip(m.end_price),low=flip(m.high),high=flip(m.low)) for m in changed]
                        context=context._replace(center=context.center._replace(zd=flip(context.center.zg),zg=flip(context.center.zd)))
                    points=chan.find_third_points(supplied,[context],now);self.assertEqual(len(points),int(delta>=0))
                    if points:self.assertEqual((points[0].kind,points[0].pull_move_id),('sell3' if mirror else 'buy3',moves[8].move_id))
            # 首回试5、6破沿各保留；不跳过失败项，实际重新离开7才由8确认。
            self.assertEqual(chan.find_third_points(moves[:7],[named['A']],moves[6].confirmed_dt),[])
            point,=chan.find_third_points(moves[:9],[named['A']],moves[8].confirmed_dt)
            self.assertEqual((point.leave_move_id,point.pull_move_id),(moves[7].move_id,moves[8].move_id))

    def test_delayed_returns_future_payloads_and_F1_center_proof_do_not_backfill_identities(self):
        for contract in ('current','fixed'):
            _,units,a,rows,moves,contexts=s3_source_consumers_input(contract);now=rows[-1]['available_dt'];named={c.context_id.rsplit(':',1)[1]:c for c in contexts}
            base=chan.find_third_points(moves,contexts,now);late=moves[8].confirmed_dt+timedelta(days=1);delayed=list(moves)
            for i in range(8,len(moves)):delayed[i]=moves[i]._replace(confirmed_dt=max(late,moves[i].confirmed_dt))
            self.assertEqual(chan.find_third_points(delayed,contexts,late-timedelta(microseconds=1)),[])
            after=chan.find_third_points(delayed,contexts,late);self.assertEqual(after,[p._replace(confirmed_dt=late) for p in base])
            for at in (late-timedelta(microseconds=1),late,now):
                visible=[m for m in delayed if m.confirmed_dt<=at];expected=chan.find_third_points(visible,contexts,at)
                future=moves[-1]._replace(move_id=None,level=None,low=float('nan'),confirmed_dt=now+timedelta(days=10))
                context=named['A']._replace(context_id=None,center=named['A'].center._replace(center_id=None,zd=float('nan'),confirmed_dt=now+timedelta(days=10)))
                self.assertEqual(chan.find_third_points(delayed+[future],contexts+[context],at),expected)
                self.assertEqual(chan.track_center_lineage(delayed+[future],at,'source0-center','source0-upper'),chan.track_center_lineage(visible,at,'source0-center','source0-upper'))
            types=[]
            for spec in M3_S3_SOURCE_BRIDGE_AUDIT['f1']:
                count=rows[a['f1_lineage']['first_raw'][contract]-1]['available_dt'];parts=m3_xd_parts(dict(units=units),len(rows))
                move=next(m for m in chan.same_level_decompose(parts) if m.complete and m.seg_start==spec[0]);first=units[spec[-1]]['confirmed_raw_count']
                types.append(m3_xd_type('S3-source0:'+contract,move,[u for u in units if u['confirmed_raw_count']<=first],rows[first-1]['available_dt']))
            actual=m3_xd_lineage_third(types,count);self.assertEqual(len(actual[0].events),1)
            later=types[-1].confirmed_dt+timedelta(days=1);types[-1]=types[-1]._replace(confirmed_dt=later)
            self.assertEqual(m3_xd_lineage_third(types,later-timedelta(microseconds=1))[0].events,())
            frozen=m3_xd_lineage_third(types,later);self.assertEqual(len(frozen[0].events),1)
            self.assertEqual(frozen[0].centers[0].confirmed_dt,later);self.assertEqual(frozen[2],[])
            self.assertEqual(chan.find_third_points(moves,contexts,now),base)


if __name__ == '__main__':
    unittest.main()
