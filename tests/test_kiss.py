# -*- coding: utf-8 -*-
"""chan.kiss 均线吻系统(课 11/12)单元测试

覆盖分支:
  纯分类(TestClassifyKiss):
    - 湿吻优先(有穿越即湿吻)/唇吻含边界(<=)/飞吻/自定义 proximity
  体位序列(TestAlignment):
    - 暖机 None/女上位/男上位/触零沿用前一体位/空输入
  吻事件(TestFindKisses):
    - 飞吻中继(resumed=True)/唇吻中继/湿吻中继(反复缠绕 crossings)
    - 湿吻转折(体位转化, 方向=转化前宿主, 恰达 flip_confirm 边界)
    - down 镜像(闭合唇吻 + pre_gain 下跌方向同样为正)/down 转折
    - 体位段内计数 1,2,3(课 12 缠绕计数)/转化后计数清零
    - 微扰过滤(视为峰值延续, 后续吻 start_idx 前移)
    - open 吻(数据耗尽)/深度不足的 open 不产出
    - 单调不回撤/数据不足/全 None -> []
    - 暖机 None 前缀/序列中 None 视为数据耗尽
    - pre_gain 数值验证 + vol_leg/vol_kiss/vol_prior 三段均量
    - volumes=None 全 None/长均线值为 0 时 pre_gain=None
"""

from __future__ import print_function

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.kiss import (ALIGN_DOWN, ALIGN_UP, KISS_FLY, KISS_LIP,  # noqa: E402
                       KISS_WET, KissEvent, alignment_series,
                       classify_kiss, find_kisses)


def _series(diffs, base=10.0):
    """由差值序列构造 (short, long): long 恒为 base, short = base + d

    测试 fixture 直接以差值(短-长)驱动, 峰值/回撤/穿越一目了然;
    base=10 非零保证 pre_gain 归一分母可用。
    """
    long = [base] * len(diffs)
    short = [None if d is None else base + d for d in diffs]
    return short, long


class TestClassifyKiss(unittest.TestCase):
    """classify_kiss 纯函数边界(课 11 三分类)"""

    def test_wet_priority(self):
        # 有触零/穿零即湿吻, 距离判定不再参与
        self.assertEqual(classify_kiss(1, 0.0, 1.0), KISS_WET)
        self.assertEqual(classify_kiss(3, 0.9, 1.0), KISS_WET)

    def test_lip_boundary_inclusive(self):
        # 恰等 proximity x peak 仍为唇吻(<= 含边界)
        self.assertEqual(classify_kiss(0, 0.5, 1.0), KISS_LIP)
        self.assertEqual(classify_kiss(0, 0.49, 1.0), KISS_LIP)

    def test_fly(self):
        # 靠近不足: 略走平即续势为飞吻
        self.assertEqual(classify_kiss(0, 0.51, 1.0), KISS_FLY)

    def test_custom_proximity(self):
        self.assertEqual(classify_kiss(0, 0.6, 1.0, proximity=0.7),
                         KISS_LIP)
        self.assertEqual(classify_kiss(0, 0.6, 1.0, proximity=0.5),
                         KISS_FLY)


class TestAlignment(unittest.TestCase):
    """alignment_series 体位序列(课 12 "首要判断的是体位")"""

    def test_warmup_none(self):
        out = alignment_series([None, None, 11.0], [10.0, 10.0, 10.0])
        self.assertEqual(out, [None, None, ALIGN_UP])

    def test_up_down(self):
        out = alignment_series([11.0, 9.0], [10.0, 10.0])
        self.assertEqual(out, [ALIGN_UP, ALIGN_DOWN])

    def test_zero_touch_carries_prev(self):
        # 差值恰为零: 逐棒体位沿用前一体位(触零属吻事件, 不改体位)
        out = alignment_series([11.0, 10.0, 9.0], [10.0, 10.0, 10.0])
        self.assertEqual(out, [ALIGN_UP, ALIGN_UP, ALIGN_DOWN])

    def test_empty_and_all_none(self):
        self.assertEqual(alignment_series([], []), [])
        self.assertEqual(alignment_series([None], [None]), [None])


class TestFindKisses(unittest.TestCase):
    """find_kisses 吻事件序列(课 11 完全分类 + 课 12 判定原料)"""

    def test_fly_resume(self):
        # 飞吻: 回撤 0.25(>min_depth=0.2) 但最近距离 0.75 > 0.5x1.0
        short, long = _series([1.0, 0.75, 1.2])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_FLY)
        self.assertEqual(e.direction, ALIGN_UP)
        self.assertEqual((e.start_idx, e.end_idx), (0, 2))
        self.assertEqual(e.kiss_index, 1)
        self.assertEqual(e.crossings, 0)
        self.assertAlmostEqual(e.peak_gap, 1.0)
        self.assertAlmostEqual(e.min_gap, 0.75)
        self.assertAlmostEqual(e.depth, 0.25)
        self.assertTrue(e.resumed)
        self.assertFalse(e.open)

    def test_lip_resume(self):
        # 唇吻: 靠近不破(0.4 <= 0.5x1.0), 同体位新极值了结
        short, long = _series([1.0, 0.4, 1.5])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_LIP)
        self.assertTrue(e.resumed)
        self.assertAlmostEqual(e.min_gap, 0.4)
        self.assertAlmostEqual(e.depth, 0.6)

    def test_wet_resume(self):
        # 湿吻中继: 触零(1) + 回穿(2) 反复缠绕后同体位新极值
        short, long = _series([1.0, -0.3, 1.5])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_WET)
        self.assertEqual(e.crossings, 2)
        self.assertAlmostEqual(e.min_gap, 0.3)
        self.assertAlmostEqual(e.depth, 1.3)  # 含穿零行程
        self.assertTrue(e.resumed)

    def test_wet_flip_at_boundary(self):
        # 湿吻转折: 反向行程恰达 flip_confirm 边界(0.5 x 1.0)即确认
        short, long = _series([1.0, -0.2, -0.5, -0.9])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_WET)
        self.assertEqual(e.direction, ALIGN_UP)  # 宿主=转化前体位
        self.assertFalse(e.resumed)
        self.assertFalse(e.open)
        self.assertEqual(e.crossings, 1)
        self.assertAlmostEqual(e.depth, 1.5)

    def test_down_mirror_closed(self):
        # down 镜像: 闭合唇吻 + pre_gain 下跌方向同样为正(趋势符号口径)
        short, long = _series([-1.0, -1.5, -0.5, -2.0])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_LIP)
        self.assertEqual(e.direction, ALIGN_DOWN)
        self.assertTrue(e.resumed)
        self.assertEqual((e.start_idx, e.end_idx), (1, 3))
        self.assertAlmostEqual(e.min_gap, 0.5)
        self.assertAlmostEqual(e.depth, 1.0)
        self.assertAlmostEqual(e.pre_gain, 0.05)  # (8.5-9.0)/10 取负为正

    def test_down_flip(self):
        # down 转折: 湿吻确认体位转化, 新体位段首次吻计数已清零
        short, long = _series([-1.0, 0.6, 0.9, 0.4, 1.2])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 2)
        e1, e2 = evs
        self.assertEqual(e1.kind, KISS_WET)
        self.assertEqual(e1.direction, ALIGN_DOWN)
        self.assertFalse(e1.resumed)
        self.assertEqual(e2.kind, KISS_LIP)
        self.assertEqual(e2.direction, ALIGN_UP)
        self.assertEqual(e2.kiss_index, 1)  # 转化后清零重计
        self.assertTrue(e2.resumed)

    def test_kiss_index_counts(self):
        # 课 12: 体位段内缠绕计数 1,2,3(第三、四次转折可能加大)
        short, long = _series([1.0, 0.4, 1.5, 0.6, 2.0, 0.9, 2.5])
        evs = find_kisses(short, long)
        self.assertEqual([e.kiss_index for e in evs], [1, 2, 3])
        self.assertEqual([e.kind for e in evs],
                         [KISS_LIP, KISS_LIP, KISS_LIP])
        self.assertTrue(all(e.resumed for e in evs))
        self.assertTrue(all(e.direction == ALIGN_UP for e in evs))

    def test_kiss_index_reset_after_flip(self):
        # 同体位两吻后转化(第 2 次为湿吻) -> 新体位段计数清零
        short, long = _series(
            [1.0, 0.4, 1.5, 0.6, -0.2, -0.8, -0.3, -1.6])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 3)
        self.assertEqual([e.kiss_index for e in evs], [1, 2, 1])
        self.assertEqual([e.direction for e in evs],
                         [ALIGN_UP, ALIGN_UP, ALIGN_DOWN])
        self.assertEqual(evs[1].kind, KISS_WET)
        self.assertFalse(evs[1].resumed)

    def test_micro_perturbation_filtered(self):
        # 回撤深度不足 min_depth: 微扰不构成吻, 视为峰值延续
        short, long = _series([1.0, 0.95, 1.3])
        self.assertEqual(find_kisses(short, long), [])
        # 峰值延续后的真吻 start_idx 前移到新峰值位
        short, long = _series([1.0, 0.95, 1.3, 0.5, 1.8])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].start_idx, 2)
        self.assertAlmostEqual(evs[0].peak_gap, 1.3)

    def test_open_kiss(self):
        # 数据耗尽时吻未了结: open=True, resumed=False
        short, long = _series([1.0, 0.4])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertEqual(e.kind, KISS_LIP)
        self.assertTrue(e.open)
        self.assertFalse(e.resumed)
        self.assertEqual(e.end_idx, 1)

    def test_open_insufficient_depth_no_event(self):
        # 未了结且深度不足: 不产出事件
        short, long = _series([1.0, 0.95])
        self.assertEqual(find_kisses(short, long), [])

    def test_no_retracement_empty(self):
        # 差值单调不回撤: 无吻
        short, long = _series([1.0, 2.0, 3.0])
        self.assertEqual(find_kisses(short, long), [])

    def test_insufficient_data(self):
        self.assertEqual(find_kisses([], []), [])
        self.assertEqual(find_kisses([11.0], [10.0]), [])
        self.assertEqual(find_kisses([None, None], [None, None]), [])

    def test_warmup_none_prefix(self):
        # sma 暖机位 None 前缀: 有效数据起算
        short, long = _series([None, None, 1.0, 0.4, 1.5])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        self.assertEqual((evs[0].start_idx, evs[0].end_idx), (2, 4))
        self.assertEqual(evs[0].leg_start_idx, 2)

    def test_mid_none_breaks_as_exhausted(self):
        # 序列中 None: 视为数据耗尽, 进行中的吻以 open 收尾
        short, long = _series([1.0, 0.4, None, 1.5])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        self.assertTrue(evs[0].open)
        self.assertEqual(evs[0].end_idx, 1)

    def test_pre_gain_and_volumes(self):
        # pre_gain=吻前腿短均线相对涨幅; 三段均量按区间划分
        diffs = [1.0, 0.4, 1.5, 1.8, 0.6, 2.0]
        short, long = _series(diffs)
        volumes = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        evs = find_kisses(short, long, volumes=volumes)
        self.assertEqual(len(evs), 2)
        e1, e2 = evs
        # 第一吻: 腿=暖机起单点, pre_gain=0, 无更前段
        self.assertAlmostEqual(e1.pre_gain, 0.0)
        self.assertAlmostEqual(e1.vol_leg, 10.0)
        self.assertAlmostEqual(e1.vol_kiss, 25.0)  # mean(20,30)
        self.assertIsNone(e1.vol_prior)
        # 第二吻: 腿=2->3(11.5->11.8), pre_gain=0.03
        self.assertAlmostEqual(e2.pre_gain, 0.03)
        self.assertAlmostEqual(e2.vol_leg, 35.0)   # mean(30,40)
        self.assertAlmostEqual(e2.vol_kiss, 55.0)  # mean(50,60)
        self.assertAlmostEqual(e2.vol_prior, 15.0)  # mean(10,20)

    def test_volumes_none(self):
        short, long = _series([1.0, 0.4, 1.5])
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        e = evs[0]
        self.assertIsNone(e.vol_leg)
        self.assertIsNone(e.vol_kiss)
        self.assertIsNone(e.vol_prior)

    def test_pre_gain_none_on_zero_base(self):
        # 长均线值为 0: 不可归一, pre_gain=None
        short = [1.0, 0.4, 1.5]
        long = [0.0, 0.0, 0.0]
        evs = find_kisses(short, long)
        self.assertEqual(len(evs), 1)
        self.assertIsNone(evs[0].pre_gain)

    def test_to_dict_structure(self):
        short, long = _series([1.0, 0.4, 1.5])
        evs = find_kisses(short, long)
        d = evs[0].to_dict()
        self.assertEqual(len(d), 16)
        self.assertEqual(d["kind"], KISS_LIP)
        self.assertEqual(d["direction"], ALIGN_UP)
        self.assertTrue(d["resumed"])
        self.assertIsInstance(evs[0], KissEvent)


if __name__ == "__main__":
    unittest.main()
