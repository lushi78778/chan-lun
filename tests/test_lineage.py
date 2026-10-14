# -*- coding: utf-8 -*-
"""课20/35: 中枢演化谱系 formed/extended 事件与快照版本链(计划§11.7, 0.11.1)。

合成样本全部价格由闭区间端点连续构造, 期望值按课20 ZG/ZD、GG/DD
与中心定理二手工推导冻结; 事件不回写与批到达口径单独验证。
"""
import json
import unittest
from datetime import datetime, timedelta

from chan import (CenterEvent, CenterLineage, CenterVersion, ConfirmedMove,
                  track_center_lineage)

T = datetime(2025, 1, 1)
# 22 个单元: 四个中枢 C1[110,115]/C2[90,94]/C3[70,72]/C4[70,76],
# C1 延伸两次(u3/u4), C2/C3 各一次, C4 四次(u18-u21)。
PRICES = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 69, 65, 76, 70, 78, 75, 82, 76, 86]


def sample(prices=PRICES, n=20):
    units = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        s = T + timedelta(hours=i * n)
        e = T + timedelta(hours=(i + 1) * n)
        units.append(ConfirmedMove('u%d' % i, 'base', 'up' if b > a else 'down',
                                   s, e, a, b, min(a, b), max(a, b),
                                   e + timedelta(minutes=2)))
    now = T + timedelta(hours=(len(prices) - 1) * n) + timedelta(days=1)
    return units, now


def center_ids(lineage):
    """形成顺序去重后的中枢身份列表。"""
    out = []
    for event in lineage.events:
        if event.kind == 'formed' and event.center_id not in out:
            out.append(event.center_id)
    return out


class TestLineageStructure(unittest.TestCase):
    def test_sample_four_centers_twelve_events(self):
        """四中枢十二事件, formed/extended 序列与版本链一致。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        self.assertIsInstance(lineage, CenterLineage)
        self.assertIsInstance(lineage.events[0], CenterEvent)
        self.assertIsInstance(lineage.centers[0], CenterVersion)
        self.assertEqual(len(lineage.centers), 12)
        self.assertEqual([e.kind for e in lineage.events],
                         ['formed', 'extended', 'extended',
                          'formed', 'extended',
                          'formed', 'extended',
                          'formed', 'extended', 'extended', 'extended', 'extended'])
        ids = center_ids(lineage)
        self.assertEqual(ids, ['["main","u0"]', '["main","u5"]',
                               '["main","u9"]', '["main","u15"]'])
        for center_id, versions in (('["main","u0"]', 3), ('["main","u5"]', 2),
                                    ('["main","u9"]', 2), ('["main","u15"]', 5)):
            chain = [c for c in lineage.centers if c.center_id == center_id]
            self.assertEqual([c.version for c in chain], list(range(versions)))

    def test_frozen_range_and_z_metrics(self):
        """zd/zg 形成时冻结不变; gg/dd 按 Z 走势段极值逐版本更新(课20)。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        c1 = [c for c in lineage.centers if c.center_id == '["main","u0"]']
        self.assertEqual([(c.zd, c.zg) for c in c1], [(110.0, 115.0)] * 3)
        self.assertEqual(c1[0].unit_ids, ('u0', 'u1', 'u2'))
        self.assertEqual((c1[0].gg, c1[0].dd), (120.0, 108.0))
        self.assertEqual((c1[1].gg, c1[1].dd), (120.0, 108.0))  # u3 非 Z 段
        self.assertEqual(c1[1].unit_ids, ('u0', 'u1', 'u2', 'u3'))
        self.assertEqual((c1[2].gg, c1[2].dd), (120.0, 90.0))  # u4 为 Z 段
        c4 = [c for c in lineage.centers if c.center_id == '["main","u15"]']
        self.assertEqual([(c.zd, c.zg) for c in c4], [(70.0, 76.0)] * 5)
        self.assertEqual([c.gg for c in c4], [78.0, 78.0, 82.0, 82.0, 86.0])
        self.assertEqual(c4[0].unit_ids, ('u15', 'u16', 'u17'))
        self.assertEqual(c4[4].unit_ids,
                         ('u15', 'u16', 'u17', 'u18', 'u19', 'u20', 'u21'))

    def test_span_times_from_units(self):
        """快照起止时间取自组成单元端点, 不虚构中枢自身时间。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        c1 = lineage.snapshot('["main","u0"]', 0)
        self.assertEqual((c1.start_dt, c1.end_dt), (units[0].start_dt, units[2].end_dt))
        c1v2 = lineage.snapshot('["main","u0"]', 2)
        self.assertEqual(c1v2.end_dt, units[4].end_dt)

    def test_snapshot_lookup_and_missing(self):
        """snapshot 按身份与版本取快照, 不存在时报错不猜测。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        self.assertIs(lineage.snapshot('["main","u5"]', 0), lineage.centers[3])
        with self.assertRaises(KeyError):
            lineage.snapshot('["main","u5"]', 9)
        with self.assertRaises(KeyError):
            lineage.snapshot('["main","nope"]', 0)


class TestNewBornRelation(unittest.TestCase):
    def test_theorem_two_relations(self):
        """课20定理二: C2 波动重叠为 higher_level, C3 为 down_continue,
        C4 为 overlap; prev 链按形成顺序, 首中枢无前驱。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        formed = [e for e in lineage.events if e.kind == 'formed']
        self.assertEqual([e.relation for e in formed],
                         [None, 'higher_level', 'down_continue', 'overlap'])
        self.assertEqual([e.prev_center_id for e in formed],
                         [None, '["main","u0"]', '["main","u5"]', '["main","u9"]'])
        extended = [e for e in lineage.events if e.kind == 'extended']
        self.assertTrue(all(e.prev_center_id is None and e.relation is None
                            for e in extended))

    def test_relation_frozen_against_later_extension(self):
        """新生关系以形成当时前中枢最新快照为基准, 前中枢此后延伸不回改。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        # C2 形成时(u7 批)C1 最新为 v2(gg=120, dd=90): 后ZG<前ZD 且
        # 后GG>=前DD -> higher_level; C1 此后无新版本, 关系仍冻结。
        e_c2 = [e for e in lineage.events if e.kind == 'formed'][1]
        self.assertEqual(e_c2.relation, 'higher_level')
        c1_latest = lineage.snapshot('["main","u0"]', 2)
        self.assertEqual((c1_latest.gg, c1_latest.dd), (120.0, 90.0))

    def test_mirror_relations(self):
        """镜像样本: down/up 延续互换, higher_level/overlap 保持,
        zd/zg 与 gg/dd 按镜像变换(课20定理二对称性)。"""
        units, now = sample([230 - p for p in PRICES])
        lineage = track_center_lineage(units, now, 'main')
        formed = [e for e in lineage.events if e.kind == 'formed']
        self.assertEqual([e.relation for e in formed],
                         [None, 'higher_level', 'up_continue', 'overlap'])
        c1 = [c for c in lineage.centers if c.center_id == '["main","u0"]']
        self.assertEqual([(c.zd, c.zg) for c in c1], [(115.0, 120.0)] * 3)
        self.assertEqual((c1[0].gg, c1[0].dd), (122.0, 110.0))
        self.assertEqual((c1[2].gg, c1[2].dd), (140.0, 110.0))


class TestConfirmationAndOrdering(unittest.TestCase):
    def test_event_confirmation_equals_evidence_arrival(self):
        """事件确认时刻等于证据到达时刻, 不早于组成单元确认。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        kinds = [(e.center_id, e.version, e.kind) for e in lineage.events]
        self.assertEqual(kinds[:3],
                         [('["main","u0"]', 0, 'formed'),
                          ('["main","u0"]', 1, 'extended'),
                          ('["main","u0"]', 2, 'extended')])
        self.assertEqual(lineage.events[0].confirmed_dt, units[2].confirmed_dt)
        self.assertEqual(lineage.events[1].confirmed_dt, units[3].confirmed_dt)
        self.assertEqual(lineage.events[-1].confirmed_dt, units[21].confirmed_dt)

    def test_batch_formed_and_extended_same_arrival(self):
        """同批到达时 formed 先于 extended, 两者同确认时刻(课20延伸)。"""
        units, now = sample()
        units[2] = units[2]._replace(confirmed_dt=units[3].confirmed_dt)
        lineage = track_center_lineage(units, now, 'main')
        c1_events = [e for e in lineage.events if e.center_id == '["main","u0"]']
        self.assertEqual([e.kind for e in c1_events], ['formed', 'extended', 'extended'])
        self.assertEqual(c1_events[0].confirmed_dt, units[3].confirmed_dt)
        self.assertEqual(c1_events[1].confirmed_dt, units[3].confirmed_dt)
        v0 = lineage.snapshot('["main","u0"]', 0)
        v1 = lineage.snapshot('["main","u0"]', 1)
        self.assertEqual(v0.unit_ids, ('u0', 'u1', 'u2'))  # 首三段仍冻结
        self.assertEqual(v1.unit_ids, ('u0', 'u1', 'u2', 'u3'))

    def test_batch_multi_unit_extension_single_event(self):
        """一批多单元延伸合并为一次 extended 事件, 不虚构批内到达。"""
        units, now = sample()
        units[19] = units[19]._replace(confirmed_dt=units[21].confirmed_dt)
        units[20] = units[20]._replace(confirmed_dt=units[21].confirmed_dt)
        lineage = track_center_lineage(units, now, 'main')
        c4_events = [e for e in lineage.events if e.center_id == '["main","u15"]']
        self.assertEqual([e.version for e in c4_events], [0, 1, 2])
        self.assertEqual(c4_events[2].confirmed_dt, units[21].confirmed_dt)
        v2 = lineage.snapshot('["main","u15"]', 2)
        self.assertEqual(v2.unit_ids,
                         ('u15', 'u16', 'u17', 'u18', 'u19', 'u20', 'u21'))
        self.assertEqual((v2.gg, v2.dd), (86.0, 65.0))

    def test_zero_rewrite_across_as_of(self):
        """事件不回写: 更晚 as_of 下早前事件为严格前缀, 内容不变。"""
        units, now = sample()
        prefix8 = track_center_lineage(units, units[8].confirmed_dt, 'main')
        prefix14 = track_center_lineage(units, units[14].confirmed_dt, 'main')
        full = track_center_lineage(units, now, 'main')
        self.assertEqual(len(prefix8.events), 5)
        self.assertEqual(len(prefix14.events), 7)
        self.assertEqual(full.events[:5], prefix8.events)
        self.assertEqual(full.events[:7], prefix14.events)
        self.assertEqual(full.centers[:5], prefix8.centers)
        self.assertEqual(full.centers[:7], prefix14.centers)

    def test_future_units_not_read(self):
        """as_of 之后确认的单元不读取, 不改变已产生谱系。"""
        units, now = sample()
        poisoned = list(units)
        s = T + timedelta(hours=len(PRICES) * 20)
        e = s + timedelta(hours=20)
        poisoned.append(ConfirmedMove('u22', 'base', 'down', s, e, 86.0, 5.0,
                                      5.0, 86.0, e + timedelta(minutes=2)))
        at = track_center_lineage(poisoned, units[21].confirmed_dt, 'main')
        base = track_center_lineage(units, units[21].confirmed_dt, 'main')
        self.assertEqual(at, base)


class TestBoundaries(unittest.TestCase):
    def test_empty_and_no_overlap_input(self):
        """空输入与无三单元重叠不产生事件, 返回空谱系。"""
        _, now = sample()
        empty = track_center_lineage([], now, 'main')
        self.assertEqual((empty.centers, empty.events), ((), ()))
        units, now2 = sample([100, 90, 80, 70, 60, 50])
        lineage = track_center_lineage(units, now2, 'main')
        self.assertEqual((lineage.centers, lineage.events), ((), ()))

    def test_zero_width_center_registered(self):
        """零宽中枢(交集退化为一点)照常登记(课20闭区间含端点)。"""
        units, now = sample(PRICES[:12] + [70, 67, 69, 65, 76])
        lineage = track_center_lineage(units, now, 'main')
        ids = center_ids(lineage)
        self.assertEqual(ids, ['["main","u0"]', '["main","u5"]', '["main","u9"]'])
        v0 = lineage.snapshot('["main","u9"]', 0)
        self.assertEqual((v0.zd, v0.zg), (70.0, 70.0))
        self.assertEqual(v0.unit_ids, ('u9', 'u10', 'u11'))

    def test_visible_prefix_validation(self):
        """乱序、重复身份与非法级别沿用 confirm_level_up 契约拒绝。"""
        units, now = sample()
        with self.assertRaises(ValueError):
            track_center_lineage(units, now, 'base')
        with self.assertRaises(TypeError):
            track_center_lineage(123, now, 'main')
        dup = list(units)
        dup[3] = dup[3]._replace(move_id='u2')
        with self.assertRaises(ValueError):
            track_center_lineage(dup, now, 'main')
        late = list(units)
        late[5] = late[5]._replace(confirmed_dt=units[3].confirmed_dt)
        with self.assertRaises(ValueError):
            track_center_lineage(late, now, 'main')

    def test_to_dict_roundtrip(self):
        """to_dict 输出时间为字符串、组成为列表, 可 JSON 序列化。"""
        units, now = sample()
        lineage = track_center_lineage(units, now, 'main')
        data = lineage.to_dict()
        self.assertEqual(len(data['centers']), 12)
        self.assertEqual(len(data['events']), 12)
        self.assertEqual(data['events'][0]['kind'], 'formed')
        self.assertIsInstance(data['events'][0]['confirmed_dt'], str)
        self.assertEqual(data['centers'][0]['unit_ids'], ['u0', 'u1', 'u2'])
        self.assertIsInstance(data['centers'][0]['confirmed_dt'], str)
        json.dumps(data)


if __name__ == '__main__':
    unittest.main()
