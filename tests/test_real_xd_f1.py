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
"""
from bisect import bisect_right
from datetime import datetime, timedelta
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


if __name__ == '__main__':
    unittest.main()
