# -*- coding: utf-8 -*-
"""课11/12/15辅助点的独立差值盘面, 不由现有输出生成预期。"""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import find_ma_points


FIRST = [-10, -8, 1, -11, -10, 1, -12, -1, 0]
SECOND = [-2, -1, 2, 3, 1, 4]
BASE = datetime(2026, 1, 1)


def bars(diffs, mirror=False):
    """1/2均线差等于相邻收盘差一半, 可手算吻及面积。"""
    values = [500.]
    for diff in diffs:
        values.append(values[-1] + 2 * diff)
    if mirror:
        values = [1000 - price for price in values]
    return [dict(dt=BASE + timedelta(days=i), open=price, high=price+1,
                 low=price-1, close=price, volume=1.,
                 closed_dt=BASE + timedelta(days=i, hours=15),
                 available_dt=BASE + timedelta(days=i, hours=15, minutes=5))
            for i, price in enumerate(values)]


def points(rows, **kwargs):
    return find_ma_points(rows, rows[-1]['available_dt'] if rows else BASE,
                          short_period=1, long_period=2, **kwargs)


class TestMaPoints(unittest.TestCase):
    def test_closed_area_buy1_after_second_wet_kiss(self):
        """第二湿吻后下降腿21->13, 两个价格极值均下移。"""
        rows = bars(FIRST)
        event = points(rows)[0]
        self.assertEqual(event.kind, 'ma_buy1_candidate')
        self.assertEqual((event.reference_strength, event.current_strength), (21., 13.))
        self.assertEqual((event.kiss_index, event.kiss_kind), (2, 'wet'))
        self.assertEqual((event.dt, event.price), (BASE+timedelta(days=8), 399.))
        self.assertEqual(event.confirmed_dt, rows[9]['available_dt'])
        self.assertFalse(event.to_dict()['last_kiss_proven'])

    def test_closed_area_sell1_mirror(self):
        """上涨力度衰减与价格新高为卖端镜像, 不反转买端标签。"""
        event = points(bars(FIRST, mirror=True))[0]
        self.assertEqual((event.kind, event.price), ('ma_sell1_candidate', 601.))

    def test_unclosed_area_is_not_confirmed_at_extreme(self):
        """面积末端不是可见确认时刻, 必须等后一相交行。"""
        rows = bars(FIRST)
        self.assertEqual(points(rows[:-1]), [])
        self.assertEqual(find_ma_points(rows, rows[-1]['closed_dt'], 1, 2), [])

    def test_first_kiss_cannot_be_last_kiss_candidate(self):
        """趋势初次湿吻后虽力度减弱, 课12不称最后缠绕。"""
        self.assertEqual(points(bars([-10,-8,1,-11,-1,0])), [])

    def test_stronger_or_equal_area_is_not_divergence(self):
        """严格弱于才比较成立; 相等或更强不触发first。"""
        for tail in ([-12,-9,0], [-12,-12,-12,0]):
            self.assertEqual(points(bars(FIRST[:6]+tail)), [])

    def test_area_weakness_without_both_price_extremes_is_rejected(self):
        """课15没有趋势没有背驰, 面积单独变小不足。"""
        rows = bars(FIRST); rows[7]['high'] = 500.
        self.assertEqual(points(rows), [])

    def test_average_strength_has_explicit_separate_units(self):
        """平均力度与面积选择显式, 两段平均10.5->6.5。"""
        event = points(bars(FIRST), use_avg=True)[0]
        self.assertEqual((event.reference_strength, event.current_strength), (10.5,6.5))

    def test_first_up_continuation_buy2_not_required_to_follow_buy1(self):
        """已观察转化后的第一次中继, 不要求本模块此前出一买。"""
        rows = bars(SECOND)
        event = points(rows, min_pre_gain=0)[0]
        self.assertEqual((event.kind, event.kiss_index), ('ma_buy2_candidate',1))
        self.assertEqual((event.dt,event.price), (BASE+timedelta(days=5),505.))
        self.assertEqual(event.confirmed_dt, rows[6]['available_dt'])
        self.assertEqual(event.volume_ratio,1.)

    def test_first_down_continuation_sell2_mirror(self):
        """新男上位第一次中继高位是卖端镜像。"""
        event = points(bars(SECOND,mirror=True),min_pre_gain=0)[0]
        self.assertEqual((event.kind,event.price), ('ma_sell2_candidate',495.))

    def test_second_pattern_accepts_fly_lip_and_wet(self):
        """课15回复: second不必湿吻, 飞吻/唇吻同样可用。"""
        for diff, expected in ((2,'fly'),(1,'lip'),(-.4,'wet')):
            rows = bars(SECOND[:4]+[diff,4])
            event = points(rows,min_pre_gain=0)[0]
            self.assertEqual(event.kiss_kind,expected)

    def test_open_kiss_or_flip_is_not_first_continuation(self):
        """吻尚在进行或最终转折不是已完成中继。"""
        self.assertEqual(points(bars(SECOND[:-1]),min_pre_gain=0),[])
        self.assertEqual(points(bars(SECOND[:4]+[1,-2]),min_pre_gain=0),[])

    def test_left_censored_alignment_does_not_prove_first(self):
        """窗口直接始于女上位, 无转化记录就不伪称第一次。"""
        self.assertEqual(points(bars([2,3,1,4]),min_pre_gain=0),[])

    def test_second_or_later_kiss_is_not_relabelled_as_first(self):
        """同一体位只有第一次中继取second, 不随尾部增补改写。"""
        rows = bars(SECOND+[2,5])
        events = points(rows,min_pre_gain=0)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0],points(bars(SECOND),min_pre_gain=0)[0])

    def test_front_leg_gain_threshold_is_inclusive_and_configurable(self):
        """有力前腿工程门槛独立设置, 等于阈值通过。"""
        rows = bars(SECOND); event = points(rows,min_pre_gain=0)[0]
        self.assertEqual(points(rows,min_pre_gain=event.pre_gain),[event])
        self.assertEqual(points(rows,min_pre_gain=event.pre_gain+.001),[])
        self.assertEqual(points(rows),[])

    def test_front_leg_volume_burst_is_rejected_before_later_shrink(self):
        """前腿放量不能以之后吻中缩量证明正常。"""
        rows = bars(SECOND); rows[3]['volume']=100.; rows[4]['volume']=100.
        self.assertEqual(points(rows,min_pre_gain=0),[])
        self.assertEqual(len(points(rows,min_pre_gain=0,max_volume_ratio=None)),1)

    def test_unknown_volume_baseline_does_not_pass_volume_gate(self):
        """零可比均量不做除零或将缺证据补为正常。"""
        rows = bars(SECOND)
        for row in rows: row['volume']=0.
        self.assertEqual(points(rows,min_pre_gain=0),[])

    def test_every_prefix_future_poison_and_closed_evidence_stability(self):
        """逐可见前缀已输出事件保持, 未来缺失/NaN价格不读取。"""
        rows = bars(FIRST + [-2,-1,2,3,1,4])
        old = set()
        for stop in range(1,len(rows)+1):
            visible=rows[:stop]
            future=[{key:row[key] for key in ('dt','closed_dt','available_dt')} for row in rows[stop:]]
            current=points(visible,min_pre_gain=0)
            self.assertEqual(current,find_ma_points(visible+future,visible[-1]['available_dt'],1,2,min_pre_gain=0))
            self.assertTrue(old.issubset(set(current)))
            old=set(current)

    def test_invalid_periods_thresholds_and_time_metadata(self):
        """非法周期、比例和时间字段必须明确拒绝。"""
        rows=bars(SECOND)
        for kwargs in ({'short_period':True},{'short_period':2,'long_period':2},
                       {'flip_confirm':0},{'proximity':float('nan')},
                       {'min_depth':2},{'min_pre_gain':-1},{'max_volume_ratio':0},
                       {'use_avg':1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                find_ma_points(rows,rows[-1]['available_dt'],**kwargs)
        del rows[0]['closed_dt']
        with self.assertRaises(ValueError): points(rows)

    def test_delivery_order_and_material_price_errors(self):
        """乱序到达需版本快照; 原始坏价格不放宽。"""
        rows=bars(SECOND); rows[0]['available_dt']=rows[-1]['available_dt']
        with self.assertRaises(ValueError): points(rows,min_pre_gain=0)
        rows=bars(SECOND); rows[0]['high']=1.
        with self.assertRaises(ValueError): points(rows)

    def test_empty_warmup_mutability_and_serialization(self):
        """空/暖机无候选, 输入不修改, 公开结果不可变且便于归档。"""
        self.assertEqual(points([]),[])
        self.assertEqual(find_ma_points(bars([1,2]),BASE+timedelta(days=20)),[])
        rows=bars(FIRST); original=[dict(row) for row in rows]
        event=points(rows)[0]
        self.assertEqual(rows,original)
        self.assertEqual(event.to_dict()['dt'],str(event.dt))
        with self.assertRaises(AttributeError): event.price=1


if __name__ == '__main__':
    unittest.main()
