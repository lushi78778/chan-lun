# -*- coding: utf-8 -*-
"""课35/84/102递归与实际证据时间, 连续独立价格路径的边界验收。"""
from datetime import datetime, timedelta
import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import ConfirmedMove, SecondPointContext, find_second_points, level_up
from chan.completion import ConfirmedMoveType, confirm_level_up

T = datetime(2026, 1, 1)
PATH = [10,14,11,15,13,18,16,20,14,18,12,8,10,16]


def units(prices=PATH):
    return [ConfirmedMove('u%d'%i, 'base', 'up' if b>a else 'down',
                          T+timedelta(days=i), T+timedelta(days=i+1),
                          a,b,min(a,b),max(a,b),T+timedelta(days=i+2))
            for i,(a,b) in enumerate(zip(prices,prices[1:]))]


class TestCompletion(unittest.TestCase):
    def test_endpoint_does_not_confirm_type(self):
        """7单元已有形态端点, 第8个回入单元未到达时不能确认。"""
        data=units()
        self.assertEqual(confirm_level_up(data,data[6].confirmed_dt,'L1'),[])
        out=confirm_level_up(data,data[7].confirmed_dt,'L1')
        self.assertEqual(len(out),1)
        self.assertEqual((out[0].start_dt,out[0].end_dt),(T,T+timedelta(days=7)))
        self.assertEqual(out[0].confirmed_dt,T+timedelta(days=9))
        self.assertGreater(out[0].confirmed_dt,data[6].confirmed_dt)

    def test_composition_and_external_evidence_are_separate(self):
        """组成0..6, 完成证据0..7, 下一走势首单元不回填价格极值。"""
        out=confirm_level_up(units(),T+timedelta(days=9),'L1')[0]
        self.assertEqual(out.unit_ids,tuple('u%d'%i for i in range(7)))
        self.assertEqual(out.evidence_ids,tuple('u%d'%i for i in range(8)))
        self.assertEqual((out.low,out.high,out.start_price,out.end_price),(10,20,10,20))
        self.assertEqual(out.centers,((11,14),))

    def test_extension_is_not_same_level_cut(self):
        """课84的f2允许中枢延伸, 第4个重叠单元不按课38立即完成。"""
        data=units()
        for stop in [3,4,5,6,7]:
            self.assertEqual(confirm_level_up(data,data[stop-1].confirmed_dt,'L1'),[])

    def test_mirror_and_point_input_direction(self):
        """盘整无进入方向仍可净上涨/下跌, 卖向镜像保留确认时间。"""
        a=confirm_level_up(units(),T+timedelta(days=9),'L1')[0]
        b=confirm_level_up(units([40-p for p in PATH]),T+timedelta(days=9),'L1')[0]
        self.assertIsNone(a.direction)
        self.assertEqual(a.to_confirmed_move().direction,'up')
        self.assertEqual(b.to_confirmed_move().direction,'down')
        self.assertEqual(b.confirmed_dt,a.confirmed_dt)
        self.assertEqual((b.low,b.high),(40-a.high,40-a.low))

    def test_flat_endpoint_not_dropped_or_guessed(self):
        """平端点盘整可参与递归, 不能猜回试方向供二三类点使用。"""
        prices=list(PATH);prices[0]=20
        out=confirm_level_up(units(prices),T+timedelta(days=9),'L1')[0]
        self.assertEqual(out.start_price,out.end_price)
        with self.assertRaises(ValueError):out.to_confirmed_move()
        self.assertEqual(confirm_level_up([out],T+timedelta(days=30),'L2'),[])

    def test_second_point_uses_recursive_confirmation(self):
        """两完成类型可接二类点, 保留实际确认而非回试端点日。"""
        points=[x.to_confirmed_move() for x in confirm_level_up(units(),T+timedelta(days=15),'L1')]
        context=SecondPointContext('cycle','buy','main','L1',T,10,T)
        self.assertEqual(find_second_points(points,[context],T+timedelta(days=13)),[])
        out=find_second_points(points,[context],T+timedelta(days=14))
        self.assertEqual((out[0].dt,out[0].confirmed_dt),(T+timedelta(days=12),T+timedelta(days=14)))

    def test_same_time_batch(self):
        """到达时间相同的证据整批进入, 保留完整批而非列表虚构先后。"""
        data=[u._replace(confirmed_dt=T+timedelta(days=30)) for u in units()]
        self.assertEqual(confirm_level_up(data,T+timedelta(days=29),'L1'),[])
        out=confirm_level_up(data,T+timedelta(days=30),'L1')
        self.assertEqual(len(out),2)
        for item in out:
            self.assertEqual(item.confirmed_dt,T+timedelta(days=30))
            self.assertEqual(item.evidence_ids,tuple(u.move_id for u in data))

    def test_coarse_as_of_preserves_earlier_confirmation(self):
        """只在月末调用也逐历史到达重算, 不将实际确认延到调用日。"""
        out=confirm_level_up(units(),T+timedelta(days=30),'L1')
        self.assertEqual(out[0].confirmed_dt,T+timedelta(days=9))
        self.assertEqual(out[1].confirmed_dt,T+timedelta(days=14))

    def test_delayed_confirmation_and_future_poison(self):
        """确认迟到时未来价格/级别/身份不读取, 未见证据不补历史结果。"""
        data=units()[:8];data[-1]=data[-1]._replace(confirmed_dt=T+timedelta(days=20))
        poison=data[-1]._replace(move_id=None,level=None,start_price=float('nan'),low=None)
        self.assertEqual(confirm_level_up(data[:-1]+[poison],T+timedelta(days=19),'L1'),[])
        self.assertEqual(confirm_level_up(data,T+timedelta(days=20),'L1')[0].confirmed_dt,T+timedelta(days=20))

    def test_every_prefix_and_existing_records_are_stable(self):
        """独立逐到达前缀与全输入截止一致, 已完成记录不可撤销或修订。"""
        data=units();previous=set()
        for stop,u in enumerate(data,1):
            actual=confirm_level_up(data,u.confirmed_dt,'L1')
            self.assertEqual(actual,confirm_level_up(data[:stop],u.confirmed_dt,'L1'))
            self.assertTrue(previous.issubset(set(actual)))
            previous=set(actual)

    def test_recursive_two_levels(self):
        """真正通过本入口产生的L1可再升L2, 包含层层实际证据时间。"""
        rng=random.Random(1);prices=[1000.]
        for i in range(200):prices.append(prices[-1]+(1 if i%2==0 else -1)*rng.randint(3,60))
        data=units(prices);seen=set()
        for stop in range(1,len(data)+1):
            now=data[stop-1].confirmed_dt
            first=confirm_level_up(data,now,'L1')
            second=confirm_level_up(first,now,'L2')
            self.assertTrue(seen.issubset(set(second)))
            seen=set(second)
        self.assertEqual(len(first),12)
        self.assertEqual(len(second),1)
        self.assertEqual(second[0].confirmed_dt,T+timedelta(days=109))
        self.assertEqual(len(second[0].unit_ids),5)
        self.assertEqual(len(second[0].evidence_ids),6)

    def test_trend_centers_and_mirror(self):
        """课35多个严格上移中枢的趋势, 与严格下移镜像同样确认。"""
        prices=[5,10,8,12,9,15,13,18,16,20,18,22,21,25,23,28,19,31,29,35,24]
        for path,kind in [(prices,'up'),([50-p for p in prices],'down')]:
            out=confirm_level_up(units(path),T+timedelta(days=25),'L1')
            self.assertEqual(out[0].kind,kind)
            self.assertEqual(len(out[0].centers),3)

    def test_reject_bare_move_type_and_parts(self):
        """裸complete不携带实际确认, 不能把单笔/线段作为走势证明。"""
        data=units()
        for wrong in [level_up(data)[0],object(),{}]:
            with self.assertRaises(ValueError):confirm_level_up([wrong],T+timedelta(days=30),'L1')

    def test_bad_identity_and_level(self):
        """同级输入和不同递归目标明确声明, 不根据K线时长猜邻接。"""
        data=units()
        for wrong in [data[1]._replace(move_id='u0'),data[1]._replace(level='other'),
                      data[1]._replace(move_id='')]:
            with self.assertRaises(ValueError):confirm_level_up([data[0],wrong],T+timedelta(days=30),'L1')
        for name in ['',None,'base']:
            with self.assertRaises(ValueError):confirm_level_up(data,T+timedelta(days=30),name)

    def test_gap_and_endpoint_mismatch(self):
        """时间断段或价格断点不允许产生跨缺失区间的递归结构。"""
        data=units()
        for wrong in [data[1]._replace(start_dt=T),data[1]._replace(start_price=13)]:
            with self.assertRaises(ValueError):confirm_level_up([data[0],wrong],T+timedelta(days=30),'L1')

    def test_arrival_disorder_and_visible_hole(self):
        """较早单元迟于较晚单元确认须重建版本, 不排序后偷补前缀。"""
        data=units()[:2];data[0]=data[0]._replace(confirmed_dt=T+timedelta(days=20))
        for now in [T+timedelta(days=10),T+timedelta(days=30)]:
            with self.assertRaises(ValueError):confirm_level_up(data,now,'L1')

    def test_bad_time_price_and_direction(self):
        """非正/非有限价格、未来端点和混用日期表示不能作为完成证据。"""
        data=units()
        for wrong in [data[0]._replace(low=float('nan')),data[0]._replace(high=0),
                      data[0]._replace(start_dt=data[0].end_dt),data[0]._replace(end_dt=T+timedelta(days=5)),
                      data[0]._replace(direction='down'),data[0]._replace(confirmed_dt='2026-01-03')]:
            with self.assertRaises(ValueError):confirm_level_up([wrong],T+timedelta(days=30),'L1')

    def test_frozen_input_shape(self):
        """递归结果须有中枢和证据元组, 不接受伪完成残段或可变嵌套。"""
        out=confirm_level_up(units(),T+timedelta(days=9),'L1')[0]
        for wrong in [out._replace(kind='incomplete'),out._replace(centers=[]),
                      out._replace(centers=((1,2),)),out._replace(unit_ids=['u0']),
                      out._replace(evidence_ids=('other',))]:
            with self.assertRaises(ValueError):confirm_level_up([wrong],T+timedelta(days=30),'L2')

    def test_serialization_and_immutability(self):
        """输出无嵌套可变字段, 导出的dict修改不会污染后续递归。"""
        out=confirm_level_up(units(),T+timedelta(days=9),'L1')[0]
        self.assertIsInstance(out,ConfirmedMoveType)
        with self.assertRaises(AttributeError):out.level='bad'
        doc=out.to_dict();json.dumps(doc);doc['centers'][0][0]=0
        self.assertEqual(out.centers,((11,14),))

    def test_empty_and_container(self):
        """空和不足三单元没有完成输出, 不静默消费一次性流对象。"""
        for data in [[],units()[:2]]:self.assertEqual(confirm_level_up(data,T+timedelta(days=30),'L1'),[])
        with self.assertRaises(TypeError):confirm_level_up(iter([]),T,'L1')


if __name__=='__main__':unittest.main()
