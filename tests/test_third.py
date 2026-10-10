# -*- coding: utf-8 -*-
"""课20三类点首次、触沿、全区间极值、真实可用时间与镜像。"""
import os
import sys
import unittest
sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(__file__)),'src'))
from chan.second import ConfirmedMove, ConfirmedCenter
from chan.third import ThirdPointContext, find_third_points


def move(name,start,end,s,e,confirmed=None,low=None,high=None):
    return ConfirmedMove(name,'sub','up' if e>s else 'down','2026-01-%02d'%start,
                         '2026-01-%02d'%end,s,e,min(s,e) if low is None else low,
                         max(s,e) if high is None else high,'2026-01-%02d'%(confirmed or end+1))


def context(known='2026-01-01',**kwargs):
    return ThirdPointContext('cycle','main','sub',ConfirmedCenter('center','main',10,12,known))


class TestThird(unittest.TestCase):
    def test_buy_and_touch(self):
        """向上离开后首回试, 低点触ZG也成立, 无力度比限制。"""
        for price in [12,12.2]:
            result=find_third_points([move('a',2,4,11,14),move('b',4,6,14,price)],
                                     [context()],'2026-01-07')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0].kind,'buy3')
            self.assertEqual(result[0].confirmed_dt,'2026-01-07')
            self.assertEqual(result[0].dt,'2026-01-06')

    def test_sell_mirror(self):
        """三卖首回抽不升破ZD, 等于ZD允许。"""
        result=find_third_points([move('a',2,4,11,8),move('b',4,6,8,10)],
                                 [context()],'2026-01-07')
        self.assertEqual(result[0].kind,'sell3')

    def test_full_return_range_not_endpoint_only(self):
        """回试端点守沿但内部已破沿不能判三买。"""
        self.assertEqual(find_third_points([move('a',2,4,11,14),
                         move('b',4,6,14,12.2,low=11.9)],[context()],'2026-01-07'),[])

    def test_no_signal_before_return_confirmation(self):
        """端点日不等于确认日, 未来已完成输入先截断。"""
        moves=[move('a',2,4,11,14),move('b',4,6,14,12)]
        for cutoff in ['2026-01-04','2026-01-06']:
            self.assertEqual(find_third_points(moves,[context()],cutoff),[])

    def test_do_not_skip_failed_first_return(self):
        """第一次破ZG后第二次守ZG不追认原离开的三买。"""
        moves=[move('a',2,4,11,14),move('b',4,6,14,11),
               move('c',6,8,11,11.8),move('d',8,10,11.8,11.5)]
        self.assertEqual(find_third_points(moves,[context()],'2026-01-11'),[])

    def test_new_departure_after_return_to_center(self):
        """首离开失败后重新进入中枢, 新离开与其首回试可重新成立。"""
        moves=[move('a',2,4,11,14),move('b',4,6,14,11),
               move('c',6,8,11,15),move('d',8,10,15,12.5)]
        out=find_third_points(moves,[context()],'2026-01-11')
        self.assertEqual(out[0].leave_move_id,'c')

    def test_repeated_pulls_are_not_repeated_signals(self):
        """同一中枢只输出第一个成立事件, 不再将趋势中回抽当三买。"""
        moves=[move('a',2,4,11,14),move('b',4,6,14,12),
               move('c',6,8,12,15),move('d',8,10,15,13)]
        out=find_third_points(moves,[context()],'2026-01-11')
        self.assertEqual(len(out),1)
        self.assertEqual(out[0].pull_move_id,'b')

    def test_center_must_be_known_before_departure(self):
        """已给定晚确认中枢不能倒填到历史离开起点。"""
        moves=[move('a',2,4,11,14),move('b',4,6,14,12)]
        self.assertEqual(find_third_points(moves,[context('2026-01-03')],'2026-01-07'),[])

    def test_future_center_and_prices_do_not_affect_past(self):
        """不可见中枢的毒边界和未来走势毒价格都不读取。"""
        future=ThirdPointContext('future','main','sub',ConfirmedCenter('future','main',float('nan'),0,'2026-02-01'))
        moves=[move('a',2,4,11,14),move('b',4,6,14,12),
               move('poison',10,12,float('nan'),float('inf'),confirmed=15)]
        self.assertEqual(len(find_third_points(moves,[context(),future],'2026-01-07')),1)

    def test_moves_already_outside_center_are_not_departures(self):
        """完全在中枢外的走势不能借旧中枢解释为新离开。"""
        self.assertEqual(find_third_points([move('a',2,4,13,16),move('b',4,6,16,14)],
                                         [context()],'2026-01-07'),[])

    def test_bad_level_and_duplicate_center(self):
        """级别名由调用方指定; 同级或重复中枢身份拒绝。"""
        for contexts in [[ThirdPointContext('x','main','main',context().center)],
                         [context(),context()]]:
            with self.assertRaises(ValueError):
                find_third_points([],contexts,'2026-01-07')

    def test_gap_and_invalid_price_rejected(self):
        """相邻走势时间/端点必须连续, 不能拼接不同片段伪造首回抽。"""
        for b in [move('b',5,6,14,12),move('b',4,6,15,12),
                  move('b',4,6,14,12,low=float('nan'))]:
            with self.assertRaises(ValueError):
                find_third_points([move('a',2,4,11,14),b],[context()],'2026-01-07')

    def test_empty_and_multiple_cycles(self):
        """空输入合法, 多个中枢按独立身份输出。"""
        self.assertEqual(find_third_points([],[],'2026-01-07'),[])
        other=ThirdPointContext('second-cycle','main','sub',ConfirmedCenter('second-center','main',11,13,'2026-01-01'))
        result=find_third_points([move('a',2,4,11,15),move('b',4,6,15,13)],
                                [context(),other],'2026-01-07')
        self.assertEqual(len(result),2)
