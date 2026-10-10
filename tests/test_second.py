# -*- coding: utf-8 -*-
"""课20/21/53/101二类点定义与确认时间边界。"""
import unittest

from chan import (ConfirmedCenter, ConfirmedDivergence, ConfirmedMove,
                  SecondPointContext, find_second_points)


def pair(side='buy', price=11):
    start, peak = (10, 15) if side == 'buy' else (20, 15)
    direction = 'up' if side == 'buy' else 'down'
    reverse = 'down' if side == 'buy' else 'up'
    first = ConfirmedMove('first', 'sub', direction, '2026-01-01', '2026-01-03',
                          start, peak, min(start, peak), max(start, peak), '2026-01-04')
    pull = ConfirmedMove('pull', 'sub', reverse, '2026-01-03', '2026-01-05',
                         peak, price, min(peak, price), max(peak, price), '2026-01-06')
    context = SecondPointContext('cycle', side, 'main', 'sub', '2026-01-01',
                                 start, '2026-01-02')
    return [first, pull], context


def points(moves, context, as_of='2026-01-10', **kwargs):
    return find_second_points(moves, [context], as_of, **kwargs)


class TestSecondPoints(unittest.TestCase):
    def test_weak_buy(self):
        """课101最弱二买允许低于一买, 无旧bs价格门槛。"""
        moves, context = pair(price=9)
        point = points(moves, context)[0]
        self.assertEqual((point.kind, point.strength, point.price), ('buy2', 'weak', 9))

    def test_weak_sell_mirror(self):
        """弱二卖镜像允许高于一卖。"""
        moves, context = pair('sell', 21)
        self.assertEqual(points(moves, context)[0].strength, 'weak')

    def test_normal_and_equal(self):
        """一般二类点及等于一类点的边界归普通分支。"""
        for side, price in [('buy', 11), ('buy', 10), ('sell', 19), ('sell', 20)]:
            moves, context = pair(side, price)
            self.assertEqual(points(moves, context)[0].strength, 'normal')

    def test_strong_buy_touch_zg(self):
        """课20回试触ZG允许, 课101二三合一是最强情形。"""
        moves, context = pair(price=12)
        center = ConfirmedCenter('last-down-center', 'main', 11, 12, '2025-12-20')
        point = points(moves, context, centers={'cycle': center})[0]
        self.assertEqual((point.strength, point.also_third, point.center_id),
                         ('strong', True, 'last-down-center'))

    def test_strong_sell_touch_zd(self):
        """二三卖合一镜像, 回抽全区间高点不升破ZD。"""
        moves, context = pair('sell', 18)
        point = points(moves, context,
                       centers={'cycle': ConfirmedCenter('c', 'main', 18, 19, '2025-12-20')})[0]
        self.assertTrue(point.also_third)

    def test_full_range_not_endpoint_for_third(self):
        """回试内最低价破ZG即不合一, 不以末端价遮蔽途中破位。"""
        moves, context = pair(price=12)
        moves[1] = moves[1]._replace(low=11)
        point = points(moves, context,
                       centers={'cycle': ConfirmedCenter('c', 'main', 11, 12, '2025-12-20')})[0]
        self.assertFalse(point.also_third)

    def test_center_missing_late_or_future(self):
        """没有反转前可见因果中枢不能回看标记二三合一。"""
        moves, context = pair(price=12)
        for center in [None, ConfirmedCenter('c', 'main', 11, 12, '2026-01-04'),
                       ConfirmedCenter('c', 'main', float('nan'), -1, '2027-01-01')]:
            point = points(moves, context, centers={'cycle': center})[0]
            self.assertFalse(point.also_third)

    def test_endpoint_before_confirmation(self):
        """回试端点已过但未确认完成时不提前产生二买。"""
        moves, context = pair()
        self.assertEqual(points(moves, context, '2026-01-05'), [])
        point = points(moves, context, '2026-01-06')[0]
        self.assertEqual(point.dt, '2026-01-05')
        self.assertEqual(point.confirmed_dt, '2026-01-06')

    def test_latest_required_evidence(self):
        """上下文晚于次级走势确认时按最晚可见时间输出。"""
        moves, context = pair()
        context = context._replace(confirmed_dt='2026-01-08')
        self.assertEqual(points(moves, context, '2026-01-07'), [])
        self.assertEqual(points(moves, context)[0].confirmed_dt, '2026-01-08')

    def test_no_incomplete_pair(self):
        """仅反弹完成而回试未完成时, 不从末笔猜二买。"""
        moves, context = pair()
        self.assertEqual(points(moves[:1], context), [])

    def test_formation_end_and_same_time_merge(self):
        """课101中阴结束后排除新二买, 同刻二三合一仍允许。"""
        moves, context = pair()
        self.assertEqual(points(moves, context._replace(ended_dt='2026-01-05')), [])
        self.assertEqual(len(points(moves, context._replace(ended_dt='2026-01-06'))), 1)
        self.assertEqual(points(moves, context._replace(ended_dt='2027-01-01')),
                         points(moves, context))

    def test_historical_point_retained_after_end(self):
        """已在中阴内确认的二类点, 后来中阴结束不删历史。"""
        moves, context = pair()
        context = context._replace(ended_dt='2026-01-08')
        self.assertEqual(points(moves, context, '2026-01-07'), points(moves, context))

    def test_small_to_large_without_first_point(self):
        """课53小转大没有本级一类点, 不创新极值可成立。"""
        moves, context = pair()
        point = points(moves, context._replace(source='minor_turn'))[0]
        self.assertEqual(point.source, 'minor_turn')

    def test_minor_weak_requires_confirmed_divergence(self):
        """小转大创新低须盘整背驰, 未确认及别的走势证据不算。"""
        moves, context = pair(price=9)
        context = context._replace(source='minor_turn')
        evidence = ConfirmedDivergence('pull', 'sub', 'down', '2026-01-08')
        self.assertEqual(points(moves, context), [])
        self.assertEqual(points(moves, context, '2026-01-07', divergences=[evidence]), [])
        point = points(moves, context, divergences=[evidence])[0]
        self.assertEqual((point.strength, point.confirmed_dt), ('weak', '2026-01-08'))
        self.assertEqual(points(moves, context, divergences=[evidence._replace(move_id='other')]), [])

    def test_minor_sell_mirror(self):
        """小转大二卖创新高而盘整背驰的镜像分支。"""
        moves, context = pair('sell', 21)
        point = points(moves, context._replace(source='minor_turn'),
                       divergences=[ConfirmedDivergence('pull', 'sub', 'up', '2026-01-07')])[0]
        self.assertEqual(point.kind, 'sell2')

    def test_first_attempt_only(self):
        """失败的第一次回试不能跳过, 以后回试不补称第二类点。"""
        moves, context = pair(price=9)
        moves += [ConfirmedMove('next-up', 'sub', 'up', '2026-01-05', '2026-01-07',
                                9, 16, 9, 16, '2026-01-08'),
                  ConfirmedMove('next-down', 'sub', 'down', '2026-01-07', '2026-01-09',
                                16, 12, 12, 16, '2026-01-10')]
        self.assertEqual(points(moves, context._replace(source='minor_turn')), [])

    def test_multiple_contexts(self):
        """多个反转分别判定, 不再只取首个同向一类锚点。"""
        moves, context = pair()
        second = [m._replace(move_id=m.move_id+'B', start_dt=m.start_dt.replace('01-', '02-'),
                            end_dt=m.end_dt.replace('01-', '02-'),
                            confirmed_dt=m.confirmed_dt.replace('01-', '02-')) for m in moves]
        other = context._replace(context_id='B', anchor_dt='2026-02-01', confirmed_dt='2026-02-02')
        output = find_second_points(moves+second, [context, other], '2026-02-10')
        self.assertEqual([p.context_id for p in output], ['cycle', 'B'])

    def test_future_poison(self):
        """未来走势价格、未来上下文锚价不影响历史输出。"""
        moves, context = pair()
        expected = points(moves, context)
        future = moves[0]._replace(move_id='future', confirmed_dt='2027-01-01', low=-1, high=float('nan'))
        future_context = context._replace(context_id='future', confirmed_dt='2027-01-01', anchor_price=-1)
        self.assertEqual(find_second_points(moves+[future], [context, future_context], '2026-01-10'), expected)

    def test_empty_and_unknown_level(self):
        """无上下文/次级走势时不制造一类点, 其他级别不误接。"""
        moves, context = pair()
        self.assertEqual(find_second_points([], [], '2026-01-10'), [])
        self.assertEqual(points(moves, context._replace(sub_level='other')), [])

    def test_discontinuity(self):
        """时间或价格缺口不猜测相邻次级走势关系。"""
        moves, context = pair()
        for change in [dict(start_dt='2026-01-04'), dict(start_price=14)]:
            with self.assertRaises(ValueError):
                points([moves[0], moves[1]._replace(**change)], context)

    def test_invalid_prices_and_confirmation(self):
        """可见非法价格、确认早于端点或方向不符须拒绝。"""
        moves, context = pair()
        for change in [dict(high=float('nan')), dict(end_price=0),
                       dict(confirmed_dt='2026-01-04'), dict(direction='up')]:
            with self.assertRaises(ValueError):
                points([moves[0], moves[1]._replace(**change)], context)

    def test_duplicate_ids_and_order(self):
        """稳定身份必须唯一, 同级倒序或重叠不能静默重排。"""
        moves, context = pair()
        for bad in [moves+[moves[1]], moves[::-1]]:
            with self.assertRaises(ValueError):
                points(bad, context)
        with self.assertRaises(ValueError):
            find_second_points(moves, [context, context], '2026-01-10')

    def test_invalid_context_and_center(self):
        """级别/侧别/来源、中枢顺序非法时不猜理论含义。"""
        moves, context = pair()
        for change in [dict(side='unknown'), dict(source='guess'), dict(sub_level='main'),
                       dict(anchor_dt='2026-01-03'), dict(ended_dt='2025-01-01')]:
            with self.assertRaises(ValueError):
                points(moves, context._replace(**change))
        for center in [ConfirmedCenter('c', 'other', 11, 12, '2025-12-20'),
                       ConfirmedCenter('c', 'main', 12, 11, '2025-12-20')]:
            with self.assertRaises(ValueError):
                points(moves, context, centers={'cycle': center})

    def test_mixed_time_and_untyped_input(self):
        """无确认快照的鸭子类型笔与混合时间表示拒绝。"""
        moves, context = pair()
        with self.assertRaises(ValueError):
            points([{}], context)
        with self.assertRaises(ValueError):
            points(moves, context, '2026-01-10 00:00:00')

    def test_snapshot_serialization(self):
        """结果存档分别保留端点与确认时间, 数据对象不可重绑字段。"""
        moves, context = pair()
        point = points(moves, context)[0]
        self.assertEqual(point.to_dict()['confirmed_dt'], '2026-01-06')
        with self.assertRaises(AttributeError):
            point.price = 999


if __name__ == '__main__':
    unittest.main()
