# -*- coding: utf-8 -*-
"""课101/108: 反转轮次移交与跨轮点位归属, 已确认点位零回写。"""
import unittest
from datetime import datetime, timedelta

from chan import (ConfirmedMove, ConfirmedMoveType, Round, RoundChain,
                  analyze_point_chain, find_first_points, track_rounds)
from chan.point_chain import _handover_dt

PRICES = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 69,
          65, 76, 70, 78, 75, 82, 76, 86]
# 第二段同形下跌(0.6缩放)到新低53再回升: 两个同侧一类点、两轮并存。
PART2 = [80, 83, 78.8, 82.4, 68, 71, 66.8, 70.4, 56, 58.4, 54.8,
         57.2, 54.2, 55.4, 53]
PART3 = [59.6, 56, 60.8, 59, 63.2, 59.6, 65.6]
DOUBLE = PRICES + PART2 + PART3
FLAT_BASE = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 69,
             65, 76, 70, 78, 75, 75, 82, 76, 86]
T = datetime(2025, 1, 1)


def sample(prices=PRICES, n=20):
    rows = []
    units = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        for j in range(n):
            dt = T + timedelta(hours=i * n + j)
            p = a + (b - a) * j / n
            rows.append(dict(dt=dt, open=p, high=p, low=p, close=p, volume=100.,
                             closed_dt=dt, available_dt=dt + timedelta(minutes=1)))
        s = T + timedelta(hours=i * n)
        e = T + timedelta(hours=(i + 1) * n)
        units.append(ConfirmedMove('u%d' % i, 'base', 'up' if b > a else 'down',
                                   s, e, a, b, min(a, b), max(a, b),
                                   e + timedelta(minutes=2)))
    dt = T + timedelta(hours=(len(prices) - 1) * n)
    p = prices[-1]
    rows.append(dict(dt=dt, open=p, high=p, low=p, close=p, volume=100.,
                     closed_dt=dt, available_dt=dt + timedelta(minutes=1)))
    return units, rows, dt + timedelta(days=1)


def flat_at(units, index):
    """把指定单元冻结为平端点盘整类型, 不删段拼接。"""
    flat = units[index]
    units[index] = ConfirmedMoveType(flat.move_id, 'base', 'consolidation', None,
                                     flat.start_dt, flat.end_dt, flat.start_price,
                                     flat.end_price, flat.low, flat.high,
                                     flat.confirmed_dt, ('part',), ('part',),
                                     ((flat.low, flat.high),))
    return units[index]


def points_of(u, b, now):
    return sorted(find_first_points(u, b, now, 'main'), key=lambda p: p.dt)


class TestRoundTracking(unittest.TestCase):
    def test_single_round_grouping_and_mirror(self):
        """单轮分组与chain一致, 买卖镜像; 无移交。"""
        for mirror in (False, True):
            u, b, now = sample([200 - p for p in PRICES] if mirror else PRICES)
            chain = analyze_point_chain(u, b, now, 'main')
            rounds = track_rounds(u, b, now, 'main')
            self.assertIsInstance(rounds, RoundChain)
            self.assertEqual(len(rounds.rounds), 1)
            r = rounds.rounds[0]
            self.assertIsInstance(r, Round)
            self.assertEqual(r.side, 'sell' if mirror else 'buy')
            self.assertEqual(r.round_id, chain.first_points[0].point_id)
            self.assertEqual(r.anchor, chain.first_points[0])
            self.assertEqual(r.previous_center, chain.contexts[0].previous_center)
            self.assertEqual(r.causal_center, chain.contexts[0].causal_center)
            self.assertEqual(r.formation, chain.formations[0])
            self.assertEqual(r.second_points, tuple(chain.second_points))
            self.assertEqual(r.third_points, tuple(chain.third_points))
            self.assertIsNone(r.handed_over_dt)
            self.assertEqual(rounds.unresolved_move_ids, chain.unresolved_move_ids)

    def test_two_rounds_attribution_and_handover_registration(self):
        """两轮同侧并存: 点位按context_id归属不串轮, 旧轮登记移交。"""
        u, b, now = sample(DOUBLE)
        points = points_of(u, b, now)
        self.assertEqual([p.kind for p in points], ['buy1', 'buy1'])
        self.assertEqual([p.price for p in points], [65, 53])
        chain = analyze_point_chain(u, b, now, 'main')
        rounds = track_rounds(u, b, now, 'main')
        self.assertEqual([r.side for r in rounds.rounds], ['buy', 'buy'])
        r1, r2 = rounds.rounds
        # 旧轮前缀稳定: 与单轮样本一致的二买/三买与构造完成。
        self.assertEqual([p.kind for p in r1.second_points], ['buy2'])
        self.assertEqual([p.kind for p in r1.third_points], ['buy3'])
        self.assertEqual(r1.formation.phase, 'completed')
        # 移交登记: 旧轮移交=新锚点确认, 新轮无移交。
        self.assertEqual(r1.handed_over_dt, points[1].confirmed_dt)
        self.assertIsNone(r2.handed_over_dt)
        # 旧轮二类点窗口仍为构造终态(早于移交), 不因移交回改。
        self.assertEqual(chain.contexts[0].second_context.ended_dt,
                         r1.formation.end_dt)
        # 跨轮归属: 各轮点位与三类中枢身份不串轮。
        self.assertEqual({p.context_id for p in r1.second_points + r1.third_points},
                         {r1.round_id})
        self.assertEqual({p.context_id for p in r2.second_points + r2.third_points},
                         {r2.round_id})
        self.assertEqual({t.center_id for t in r1.third_points},
                         {r1.causal_center.center_id})
        self.assertEqual({t.center_id for t in r2.third_points},
                         {r2.causal_center.center_id})
        # 新轮自身链条完整。
        self.assertEqual((r2.causal_center.zd, r2.causal_center.zg), (56, 59.6))
        self.assertEqual([p.kind for p in r2.second_points], ['buy2'])
        self.assertEqual([p.kind for p in r2.third_points], ['buy3'])
        self.assertEqual(r2.formation.phase, 'completed')

    def test_handover_cuts_old_round_second_window(self):
        """旧轮构造中移交: 二类点窗口截止新锚点确认, 构造独立继续。"""
        u, b, now = sample(FLAT_BASE + PART2 + PART3)
        flat = flat_at(u, 19)
        points = points_of(u, b, now)
        self.assertEqual([p.price for p in points], [65, 53])
        chain = analyze_point_chain(u, b, now, 'main')
        rounds = track_rounds(u, b, now, 'main')
        r1, r2 = rounds.rounds
        # 平端点截断旧轮三类判定: 有二类点、无三类点、构造保持中。
        self.assertEqual([p.kind for p in r1.second_points], ['buy2'])
        self.assertEqual(r1.third_points, ())
        self.assertEqual(r1.formation.phase, 'constructing')
        self.assertEqual(rounds.unresolved_move_ids, (flat.move_id,))
        # 移交生效: 旧轮二类点停发窗口=新锚点确认时刻。
        self.assertEqual(r1.handed_over_dt, points[1].confirmed_dt)
        self.assertEqual(chain.contexts[0].second_context.ended_dt,
                         points[1].confirmed_dt)
        # 新轮不受平端点影响, 链条完整且无移交。
        self.assertIsNone(r2.handed_over_dt)
        self.assertEqual([p.kind for p in r2.second_points], ['buy2'])
        self.assertEqual([p.kind for p in r2.third_points], ['buy3'])
        self.assertEqual(r2.formation.phase, 'completed')

    def test_confirmed_points_zero_rewrite_across_cutoffs(self):
        """移交不回写: 早截止的已确认点位与构造终态与晚截止一致。"""
        u, b, now = sample(DOUBLE)
        early = track_rounds(u, b, u[20].confirmed_dt, 'main')
        full = track_rounds(u, b, now, 'main')
        self.assertEqual(len(early.rounds), 1)
        self.assertEqual(early.rounds[0].second_points,
                         full.rounds[0].second_points)
        self.assertEqual(early.rounds[0].third_points,
                         full.rounds[0].third_points)
        self.assertEqual(early.rounds[0].formation, full.rounds[0].formation)
        # 移交时刻由后继证据登记, 不改已确认点位与构造终态。
        self.assertIsNone(early.rounds[0].handed_over_dt)
        self.assertIsNotNone(full.rounds[0].handed_over_dt)

    def test_handover_rule_units(self):
        """移交只认同侧更晚锚点, 取最早确认; 跨侧与同锚点不停发。"""
        u, b, now = sample()
        p = find_first_points(u, b, now, 'main')[0]
        later = p._replace(point_id='["main","t2","first"]',
                           dt=p.dt + timedelta(hours=1),
                           confirmed_dt=p.confirmed_dt + timedelta(hours=5))
        other = p._replace(point_id='["main","t3","first"]',
                           dt=p.dt + timedelta(hours=2),
                           confirmed_dt=p.confirmed_dt + timedelta(hours=3))
        sell = p._replace(point_id='["main","t4","first"]', kind='sell1',
                          dt=p.dt + timedelta(hours=3),
                          confirmed_dt=p.confirmed_dt + timedelta(hours=1))
        same_anchor = p._replace(point_id='["main","t5","first"]',
                                 confirmed_dt=p.confirmed_dt + timedelta(hours=1))
        self.assertIsNone(_handover_dt([p], p))
        self.assertEqual(_handover_dt([p, later], p), later.confirmed_dt)
        self.assertEqual(_handover_dt([p, later, other], p), other.confirmed_dt)
        self.assertIsNone(_handover_dt([p, sell], p))
        self.assertIsNone(_handover_dt([p, same_anchor], p))

    def test_round_and_chain_dict(self):
        """轮次与链可序列化, 时间字段转字符串。"""
        u, b, now = sample()
        rounds = track_rounds(u, b, now, 'main')
        d = rounds.rounds[0].to_dict()
        self.assertEqual(d['round_id'], rounds.rounds[0].round_id)
        self.assertEqual(d['formation']['phase'], 'completed')
        self.assertTrue(d['second_points'])
        self.assertEqual(d['handed_over_dt'], None)
        cd = rounds.to_dict()
        self.assertEqual(len(cd['rounds']), 1)
        self.assertEqual(cd['unresolved_move_ids'], [])


if __name__ == '__main__':
    unittest.main()
