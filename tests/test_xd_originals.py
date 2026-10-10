# -*- coding: utf-8 -*-
"""原图相对价位的独立标注; 数值为保留不等式的抽象, 不是市场报价。"""
import json
import os
import sys
import unittest
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import BI, FX, find_xds


def strokes(values):
    points = []
    for i, value in enumerate(values):
        up = values[1] > values[0]
        kind = ('bottom' if i % 2 == 0 else 'top') if up else ('top' if i % 2 == 0 else 'bottom')
        points.append(FX(kind, datetime(2025, 1, 1)+timedelta(days=i), value, value, i, [i]))
    return [BI('up' if b.value > a.value else 'down', a, b, i, i+1)
            for i, (a,b) in enumerate(zip(points, points[1:]))]


def records(xds):
    return [[x.start_index, x.end_index, x.mode, x.complete] for x in xds]


class TestOriginalXD(unittest.TestCase):
    def test_independent_original_labels_and_mirrors(self):
        """课67/71/81原图: 预期不从算法输出生成; 上下镜像相同分界。"""
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'xd_originals.json')) as f:
            cases = json.load(f)
        for case in cases:
            for mirror in [False, True]:
                with self.subTest(case=case['id'], mirror=mirror):
                    values = [30-v for v in case['values']] if mirror else case['values']
                    bis = strokes(values)
                    self.assertEqual(records(find_xds(bis)), case['expected'], case['reason'])
                    for n, expected in case.get('observations', {}).items():
                        actual = find_xds(bis[:int(n)])
                        self.assertEqual([r[:3] for r in records(actual) if r[3]], expected)

    def test_confirming_bars_do_not_enlarge_finished_range(self):
        """课78: 中枢采用段自身实际极值; 确认笔在下一段不应污染旧段。"""
        bis = strokes([2,7,4,12,3,9,1])
        x = find_xds(bis)[0]
        self.assertTrue(x.complete)
        self.assertEqual((x.dd, x.gg), (2,12))
        self.assertEqual((x.end_index, x.evidence_end_index), (3,6))
        self.assertGreater(x.evidence_dt, x.end_dt)

    def test_reprocess_consumed_bis_for_next_segment(self):
        """课67第二种情况: 同一次可见前缀可确认连续两段, 不丢中间笔。"""
        result = find_xds(strokes([1,6,3,12,8,10,6,8,7,11]))
        self.assertEqual([(x.start_index,x.end_index) for x in result], [(0,3),(3,6),(6,9)])
        self.assertEqual(result[0].evidence_dt, result[1].evidence_dt)

    def test_no_pseudo_segment_for_one_or_two_bis(self):
        """课62/67: 至少三笔才是线段; 没有半笔伪段。"""
        for values in [[],[1,5],[1,5,2]]:
            self.assertEqual(find_xds(strokes(values) if values else []), [])

    def test_first_three_overlap_and_closed_touch(self):
        """前三笔重叠且尾部未破坏时只输出未完成段。"""
        result = find_xds(strokes([1,5,2,7]))
        self.assertEqual(records(result), [[0,3,1,False]])

    def test_reject_discontinuous_or_nonalternating_strokes(self):
        """不修补非法笔输入; 避免下游中枢消费伪连续结构。"""
        bis = strokes([1,5,2,7])
        bis[1].start_value = 4
        with self.assertRaises(ValueError):
            find_xds(bis)

    def test_completed_prefixes_remain_fixed(self):
        """课78: 原始笔输入固定时, 已满足破坏定义的历史段不回写。"""
        bis = strokes([1,5,2,12,7,11,6,10,7,13,8,12,7,9,6])
        previous = []
        for n in range(len(bis)+1):
            current = [x.to_dict() for x in find_xds(bis[:n]) if x.complete]
            self.assertEqual(current[:len(previous)], previous)
            previous = current

    def test_unfinished_tail_keeps_direction_and_minimum_three_bis(self):
        """课78顶须高于底; 随机固定笔的每个前缀不输出反方向伪端点。"""
        rng = random.Random(8171)
        for sample in range(30):
            values = [200.0]
            for i in range(80):
                values.append(values[-1]+(1 if i % 2 == 0 else -1)*rng.uniform(.2,5))
            bis = strokes(values)
            previous = []
            for stop in range(len(bis)+1):
                current = find_xds(bis[:stop])
                complete = [x.to_dict() for x in current if x.complete]
                self.assertEqual(complete[:len(previous)], previous)
                previous = complete
                for x in current:
                    self.assertGreaterEqual(x.end_index-x.start_index,3)
                    self.assertEqual(x.direction == 'up', x.end_value > x.start_value)

    def test_all_original_prefixes_freeze_completed_segments(self):
        """全部独立标注和镜像逐笔进入; 完成证据及历史段不回写。"""
        with open(os.path.join(os.path.dirname(__file__),'fixtures','xd_originals.json')) as f:
            cases=json.load(f)
        for case in cases:
            for values in [case['values'],[30-v for v in case['values']]]:
                bis=strokes(values);previous=[]
                for n in range(len(bis)+1):
                    current=[x.to_dict() for x in find_xds(bis[:n]) if x.complete]
                    self.assertEqual(current[:len(previous)],previous,case['id'])
                    previous=current

    def test_original_internal_extreme_is_not_replaced_by_endpoint(self):
        """课67附图第八种/78: 第二段终点4, 区间最低仍是内部2。"""
        bis=strokes([1,6,3,12,2,10,6,8,4,8.5,6,14])
        x=find_xds(bis)[1]
        self.assertTrue(x.complete)
        self.assertEqual((x.start_index,x.end_index,x.end_value,x.low),(3,8,4,2))
        self.assertEqual(x.evidence_end_index,11)
