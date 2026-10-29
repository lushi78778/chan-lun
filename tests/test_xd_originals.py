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
from chan.xd import _feature_append


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


# 首三笔交集退化为起价；同向合法端点后到时不能恢复已跳过的种子。
SEED_TOUCH_WAIT_CASES = (
    (100, 102, 99, 100, 88, 89, 79, 87, 79, 82, 65, 83, 67, 86, 85, 96, 89, 104, 93, 105, 96, 113, 103, 106, 102, 109, 103, 118, 112, 129, 114, 125, 116),
    (100, 103, 84, 100, 86, 88, 81, 89, 81, 92, 89, 97, 81, 85, 78, 92, 90, 109, 103, 120, 119, 135, 118, 130, 110, 113, 104, 120, 104, 105, 99, 101, 91),
    (100, 101, 94, 100, 89, 90, 77, 91, 84, 98, 92, 111, 106, 108, 93, 109, 90, 91, 77, 79, 60, 79, 74, 79, 63, 71, 54, 58, 57, 72, 65, 82, 80),
    (100, 111, 98, 100, 84, 85, 71, 84, 65, 77, 71, 83, 74, 82, 81, 87, 82, 87, 76, 96, 80, 84, 83, 90, 85, 94, 79, 95, 94, 101, 93, 108, 106),
    (100, 114, 98, 100, 92, 97, 82, 90, 80, 96, 85, 93, 81, 95, 93, 95, 84, 91, 84, 95, 79, 89, 79, 82, 76, 95, 89, 98, 82, 102, 82, 85, 74),
    (100, 103, 96, 100, 90, 99, 81, 96, 95, 100, 80, 97, 95, 114, 102, 121, 103, 108, 98, 110, 100, 108, 106, 119, 107, 114, 108, 121, 109, 119, 115, 117, 99),
)


class TestOriginalXD(unittest.TestCase):
    def test_78_editorial_twelve_figures_use_author_rules(self):
        """课78 PDF611/612: 十二编者补图覆盖, 实用提前选向不入核心。

        第一种(e)的首反向4→14之后9/12/7未破14或4, 旧下段
        待确认; 第二种(e)必须包含后取低低, (f)无第二分型续旧段。
        """
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'xd_originals.json')) as f:
            cases = {c['id']:c for c in json.load(f)}
        ids = ['78-editorial-'+mode+'-'+letter
               for mode in ['first','second'] for letter in 'abcdef']
        self.assertTrue(all(key in cases for key in ids))
        for key in ids:
            self.assertEqual(cases[key]['source_role'], 'editorial')
        e = cases['78-editorial-first-e']
        self.assertEqual(records(find_xds(strokes(e['values']))),
                         [[0,3,1,True],[3,6,1,False]])
        e = cases['78-editorial-second-e']
        result = find_xds(strokes(e['values']))
        self.assertEqual((result[0].mode,result[1].end_index), (2,8))

    def test_77_nested_first_break_is_not_a_completed_segment(self):
        """课71/77: 首反向笔内摆动与一笔反弹不能替代线段破坏。

        80-81在6后受2→10首笔破坏, 但6、8、4、9仍在该笔内;
        单笔4→9未破坏A, 再到1应延续旧下段, 不生成伪81-82。
        这是包含导致过早完成的最小回归, 同时检查上下两侧。
        """
        values = [1,6,3,12,5,9,2,10,6,8,4,9,1]
        for prices in [values,[30-v for v in values]]:
            bis = strokes(prices)
            self.assertEqual(records(find_xds(bis[:11])),
                             [[0,3,1,True],[3,6,1,False]])
            self.assertEqual(records(find_xds(bis)),
                             [[0,3,1,True],[3,12,1,False]])

    def test_77_three_stroke_rebound_selects_the_direction(self):
        """课77: 反弹三笔破坏A后, 首破坏笔+A+反弹合成81-82。

        在13反弹11高于首破坏笔顶10, 80-81才完成于6; 随后
        新低的反向三笔在16确认81-82于13结束。确认不向前回填。
        """
        bis = strokes([1,6,3,12,5,9,2,10,6,8,4,9,5,11,4,8,1])
        self.assertEqual([r for r in records(find_xds(bis[:11])) if r[3]],
                         [[0,3,1,True]])
        result = find_xds(bis)
        self.assertEqual(records(result),
                         [[0,3,1,True],[3,6,1,True],[6,13,1,True],[13,16,1,False]])
        self.assertEqual([x.evidence_end_index for x in result[:3]], [6,13,16])

    def test_78_backward_propagation_uses_later_actual_evidence(self):
        """课77/78: 后段破坏可逆时间传递, 证据不能逆时间可见。

        向下首笔12→2之后的6/8/4仍在该笔内, 8时不能完成
        旧上段; 新上段的4→8.5→6→14在11破坏下段, 才同时
        确认旧上段03及下段38。区间与内部最低2均保持。
        """
        bis = strokes([1,6,3,12,2,10,6,8,4,8.5,6,14])
        self.assertFalse(any(x.complete for x in find_xds(bis[:10])))
        result = find_xds(bis)
        self.assertEqual([x.evidence_end_index for x in result[:2]], [11,11])
        self.assertEqual((result[1].end_index,result[1].low), (8,2))

    def test_78_prior_break_is_visible_before_strange_extension(self):
        """课78: B已破坏A是前提; 上破笔未成段后先破其底, B延伸。

        6笔前缀已确认A, 不能借未来上破14反过来宣称B在当时成立。
        B起价12与内部最高14分开, 对称情况下内部最低也不能回填。
        """
        values = [1,6,3,12,2,8,1,14,6,10,0]
        for prices in [values,[30-v for v in values]]:
            bis = strokes(prices)
            old = find_xds(bis[:6])[0].to_dict()
            result = find_xds(bis)
            self.assertEqual(result[0].to_dict(), old)
            self.assertEqual(records(result), [[0,3,1,True],[3,10,1,False]])
            self.assertFalse(result[1].complete)
            self.assertEqual((result[1].low,result[1].high),
                             (min(prices[3:11]),max(prices[3:11])))
            self.assertNotIn(result[1].start_value,
                             [result[1].high] if prices is values else [result[1].low])

    def test_78_no_bottom_break_waits_for_reverse_confirmation(self):
        """课78: 不破反向首笔底才可延伸新段, 到11的证据不可提前。

        1→14之后6、2均未破1; 10笔观察仍只有A完成, 第11笔15
        经包含后的特征分型确认B终点6, 确认时刻保持在证据末笔。
        """
        bis = strokes([1,6,3,12,2,8,1,14,6,10,2,15])
        self.assertEqual([r for r in records(find_xds(bis[:10])) if r[3]],
                         [[0,3,1,True]])
        x = find_xds(bis)[1]
        self.assertEqual((x.start_index,x.end_index,x.evidence_end_index), (3,6,11))
        self.assertEqual((x.high,x.low), (12,1))

    def test_78_standardized_range_does_not_retime_extremes(self):
        """课78 PDF611-613/616: 分析用实际包络, 对象保留原分界时间。

        无前段时作者答案03/38/811。38的内部最高11出现在点4,
        净终点点8为10; range可标准化, 不把4的时间写成8的时间,
        也不在点8时把确认字段补成已完成。没有新增标准化公开API。
        """
        bis = strokes([8,3,7,2,11,3,8,5,10,2,4.5,0])
        result = find_xds(bis)
        self.assertEqual(records(result), [[0,3,1,True],[3,8,1,True],[8,11,1,False]])
        x = result[1]
        self.assertEqual((x.start_value,x.end_value,x.low,x.high), (2,10,2,11))
        self.assertEqual(x.end_dt, bis[7].end_dt)
        self.assertNotEqual(x.end_dt, bis[3].end_dt)
        self.assertEqual(x.evidence_dt, bis[10].end_dt)
        self.assertFalse(any(y.complete and y.start_index==3 for y in find_xds(bis[:8])))

    def test_71_complete_figure_inventory(self):
        """课71 PDF561/562: 作者两张新图、编者15+16张组合有独立预期。

        作者缺口两段及最后错误三段图分别复用67/81用例, 避免另造
        一套更正。编者顶/底标签不是完成标志, 单段/待确认均保留。
        """
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'xd_originals.json')) as f:
            cases = json.load(f)
        self.assertEqual(len([c for c in cases if c['id'].startswith('71-i-')]), 15)
        self.assertEqual(len([c for c in cases if c['id'].startswith('71-ii-')]), 16)
        for c in cases:
            if c['id'].startswith(('71-i-', '71-ii-')):
                self.assertEqual(c['source_role'], 'editorial')
                self.assertIn('不推测图外前段', c['assumptions'])

    def test_71_boundary_inclusion_and_sequential_inclusion(self):
        """课71: 跨假设分界不合并, 分界后的包含必须按先后处理。

        [2,8]和[1,12]有包含关系, 但属于假设分界两侧; 后侧
        第三反向笔0.5破首笔1, 顶分型直接成立。顺序包含不传递:
        [3,10]并[4,9]上行变[4,10], 再遇[3.5,9.5]应为新元素。
        """
        bis = strokes([0,8,2,12,1,9,.5])
        self.assertEqual(records(find_xds(bis)), [[0,3,1,True],[3,6,1,False]])
        features = []
        for lo, hi in [(3,10),(4,9),(3.5,9.5)]:
            features = _feature_append(features, (lo,hi,None), True)
        self.assertEqual([v[:2] for v in features], [(4,10),(3.5,9.5)])

    def test_71_broken_stroke_waits_for_a_segment(self):
        """课71: 第三笔仍在首笔内不能提前完成, 先破结束/开始分开。

        证据可见前缀10确认段端点5, 不是在端点5或中间前缀8确认。
        另一序列先创新高15, 全部前缀均不能倒填历史分界。
        """
        broken = strokes([1,4,2,8,5,12,2.5,10,4,9,1.5])
        self.assertFalse(any(x.complete for x in find_xds(broken[:8])))
        x = find_xds(broken[:10])[0]
        self.assertEqual((x.end_index,x.evidence_end_index), (5,10))
        continued = strokes([1,4,2,8,5,12,7,10,8,11,9,15])
        for n in range(len(continued)+1):
            self.assertFalse(any(x.complete for x in find_xds(continued[:n])))

    def test_71_editorial_names_do_not_assert_completion(self):
        """课71/78/81: 缺口顶底组合仍须第二序列, 不能仅看图名。

        顶4+底4即使最后上行超过旧段起价, 下段缺口第二序列只有
        一元素, 仍待确认。顶2+底3的第二序列包含后不够三个元素。
        """
        result = find_xds(strokes([1,4,3,10,6,8,0,4,2,12]))
        self.assertEqual(records(result), [[0,3,2,True],[3,6,1,False]])
        result = find_xds(strokes([1,3,2,8,5,7,1.5,8,3,10]))
        self.assertEqual(records(result), [[0,9,1,False]])

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

    def test_65_twelve_figures_strict_classification(self):
        """课65 PDF504十二题: 不构成/恰一段/至少两段的三类计数与图面一致。

        严格67/78口径、每划为一笔、图面即全部输入时, 十二图均为单一未完成
        线段(不构成=0, 恰一段=12, 至少两段=0)。65笔破坏口径(dj<=gi, j>=i+2)
        会判q2-q12已破坏, 但分解定理要求线段被另一线段破坏, 破坏笔未形成
        第二线段分界; 分类以特征序列分型为准。
        """
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'xd_originals.json')) as f:
            cases = json.load(f)
        quiz = [c for c in cases if c['id'].startswith('65-q')]
        self.assertEqual(len(quiz), 12)
        counts = {'none': 0, 'single': 0, 'multi': 0}
        for case in quiz:
            xds = find_xds(strokes(case['values']))
            if not xds:
                counts['none'] += 1
            elif len(xds) == 1:
                counts['single'] += 1
            else:
                counts['multi'] += 1
        self.assertEqual(counts, {'none': 0, 'single': 12, 'multi': 0})

    def test_65_two_figure_comparison_semantics(self):
        """课65 PDF506两图比较: 同输入标准下输出本质不同。

        课65回复(2007-07-19/20): 每划为笔时两图有本质区别(图A='上'一段,
        图B教学答案'上下上'); 每划为线段时无区别。笔/线段是操作性构造,
        与中枢/走势类型的递归存在性意义不同。严格67/78下图B为两记录
        (段1情况一完成, 段2未完成), 教学答案登记于fixture notes。
        """
        with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'xd_originals.json')) as f:
            cases = {c['id']: c for c in json.load(f)}
        first = find_xds(strokes(cases['65-compare-a']['values']))
        second = find_xds(strokes(cases['65-compare-b']['values']))
        self.assertEqual(len(first), 1)
        self.assertFalse(first[0].complete)
        self.assertEqual(len(second), 2)
        self.assertTrue(second[0].complete)
        self.assertFalse(second[1].complete)


    def test_touching_seed_waits_without_retracting_a_later_completed_chain(self):
        """课78顶高于底；首三笔触沿只给零净位移，不能从未来选回原起点。"""
        for original in SEED_TOUCH_WAIT_CASES:
            for values in (original,tuple(1000-v for v in original)):
                bis=strokes(values);up=bis[0].direction=='up'
                self.assertEqual(max(b.low for b in bis[:3]),min(b.high for b in bis[:3]))
                self.assertEqual(bis[2].end_value,bis[0].start_value)
                legal=next(i+1 for i in range(2,len(bis),2) if (bis[i].end_value>bis[0].start_value if up else bis[i].end_value<bis[0].start_value))
                previous=[]
                for count in range(3,len(bis)+1):
                    result=find_xds(bis[:count])
                    if count<legal:self.assertEqual(result,[])
                    elif result:self.assertEqual(result[0].start_index,0)
                    completed=[x.to_dict() for x in result if x.complete]
                    self.assertEqual(completed[:len(previous)],previous)
                    previous=completed
                    for x in result:self.assertTrue(x.end_value>x.start_value if x.direction=='up' else x.end_value<x.start_value)

    def test_nonoverlapping_initial_triple_still_searches_a_later_seed(self):
        """无交集与有交集但待定不同；前者仍按既有规则略过起始残笔。"""
        for values in ((100,110,90,95,80),tuple(1000-v for v in (100,110,90,95,80))):
            bis=strokes(values)
            self.assertGreater(max(b.low for b in bis[:3]),min(b.high for b in bis[:3]))
            result=find_xds(bis)
            self.assertEqual(len(result),1);self.assertEqual(result[0].start_index,1)
            self.assertFalse(result[0].complete)

    def test_conditioned_author_origin_uses_only_its_explicit_no_history_premise(self):
        """课78原文条件与未知截断、给定近期边界分开；不由窗口长度推断。"""
        with open(os.path.join(os.path.dirname(__file__),'fixtures','xd_originals.json')) as f:
            case = next(c for c in json.load(f) if c['id']=='78-reply-0-3-8-11')
        for values in (case['values'],[30-x for x in case['values']]):
            bs = strokes(values)
            anchor = (0,bs[0].direction,bs[0].start_value)
            for basis in ('unknown','given_recent','no_prior_history'):
                spec = dict(basis=basis,anchor=anchor,available_bi=None if basis=='unknown' else 0)
                for n in (6,7,8,10,11):
                    visible = [x for x in find_xds(bs[:n],origin_premise=spec) if x.complete]
                    expected = case['observations'][str(n)] if basis=='no_prior_history' else []
                    self.assertEqual([r[:3] for r in records(visible)],expected)
                if basis=='no_prior_history':
                    self.assertEqual([x.evidence_end_index for x in visible],[8,11])

    def test_conditioned_late_origin_does_not_backdate_public_evidence(self):
        """起点事实晚到时，最后所需证据随发布前提推迟；原分界保持。"""
        values = [8,3,7,2,11,3,8,5,10,2,4.5,0,3,1,5,2,6,3,7,4,9,5,10]
        for prices in (values,[30-x for x in values]):
            bs = strokes(prices)
            anchor = (0,bs[0].direction,bs[0].start_value)
            late = dict(basis='no_prior_history',anchor=anchor,available_bi=20)
            unknown = dict(basis='unknown',anchor=anchor,available_bi=None)
            for n in range(1,21):
                self.assertEqual([x.to_dict() for x in find_xds(bs[:n],origin_premise=late)],
                                 [x.to_dict() for x in find_xds(bs[:n],origin_premise=unknown)])
            complete = [x for x in find_xds(bs[:21],origin_premise=late) if x.complete]
            self.assertEqual([(x.start_index,x.end_index) for x in complete[:2]],[(0,3),(3,8)])
            self.assertEqual([x.evidence_end_index for x in complete[:2]],[21,21])
            self.assertEqual([x.evidence_dt for x in complete[:2]],[bs[20].end_dt]*2)
            self.assertLess(complete[1].end_dt,complete[1].evidence_dt)

    def test_conditioned_given_recent_boundary_can_complete_an_ordinary_segment(self):
        """声明近期边界只约束起点，普通原首笔选向仍可按实际证据确认。"""
        bs = strokes([1,6,3,12,2,8,1,14,6,10,0])
        spec = dict(basis='given_recent',anchor=(0,'up',1),available_bi=0)
        self.assertFalse(any(x.complete for x in find_xds(bs[:5],origin_premise=spec)))
        x = find_xds(bs[:6],origin_premise=spec)[0]
        self.assertEqual((x.start_index,x.end_index,x.complete,x.evidence_end_index),(0,3,True,6))
        future = dict(spec,available_bi=10)
        self.assertFalse(any(x.complete for x in find_xds(bs[:6],origin_premise=future)))

    def test_conditioned_origin_metadata_is_bound_and_not_shared_between_calls(self):
        """输入声明不被改写，条件调用不污染默认或未知模式，仍返回同一XD类型。"""
        from chan import XD
        bs = strokes([8,3,7,2,11,3,8,5,10,2,4.5,0])
        baseline = [x.to_dict() for x in find_xds(bs)]
        spec = dict(basis='no_prior_history',anchor=[0,'down',8],available_bi=0)
        before = json.loads(json.dumps(spec))
        known = find_xds(bs,origin_premise=spec)
        self.assertEqual(spec,before)
        self.assertTrue(all(isinstance(x,XD) for x in known))
        self.assertFalse(any(x.complete for x in find_xds(bs,origin_premise=dict(basis='unknown',anchor=(0,'down',8),available_bi=None))))
        self.assertEqual([x.to_dict() for x in find_xds(bs)],baseline)
        self.assertEqual([x.to_dict() for x in find_xds(bs,origin_premise=spec)],[x.to_dict() for x in known])
        self.assertEqual(set(known[0].to_dict()),set(('direction','start','end','gg','dd','mode','complete','evidence_end_index','evidence_dt')))

    def test_conditioned_origin_rejects_wrong_or_unavailable_identity(self):
        """无前史不能抹去已有输入，未知声明不携带到达计数，布尔值不作索引价格。"""
        bs = strokes([8,3,7,2,11,3,8,5,10,2,4.5,0])
        bad = [1,{},dict(basis='other',anchor=(0,'down',8),available_bi=0),
               dict(basis='unknown',anchor=(0,'down',8),available_bi=0),
               dict(basis='no_prior_history',anchor=(False,'down',8),available_bi=0),
               dict(basis='no_prior_history',anchor=(0,'down',True),available_bi=0),
               dict(basis='no_prior_history',anchor=(0,'down',8),available_bi=True),
               dict(basis='no_prior_history',anchor=(0,'down',8),available_bi=-1),
               dict(basis='no_prior_history',anchor=(1,'up',3),available_bi=0),
               dict(basis='given_recent',anchor=(0,'down',9),available_bi=0)]
        for spec in bad:
            with self.subTest(spec=spec),self.assertRaises(ValueError):
                find_xds(bs,origin_premise=spec)
        with self.assertRaises(TypeError):
            find_xds(None,origin_premise={})
