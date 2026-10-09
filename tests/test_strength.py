# -*- coding: utf-8 -*-
"""strength(趋势力度与平均力度, 课 15)单元测试

覆盖分支:
- sma_series: 暖机 None / 周期 1 / 周期 n / 非法周期;
- ma_areas: 基本分段(金叉-死叉封闭)/ 单点触零即相交 / 末段未封闭
  (closed=False)/ 首段始于数据起点 / None 暖机位跳过 / 恒零与
  数据不足返回空 / 面积与平均力度数值;
- find_ma_bc: 同号相邻后弱 -> 顶/底背驰事件 / 异号相邻跳过 /
  未封闭末段不参与(稳妥口径)/ use_avg 平均力度口径 / 空输入;
- avg_strength_state: 即时比较(当下未封闭段弱于前次同向段 ->
  forming_weak=True)/ 前段异向隔开时仍取再前同向段 / 无同向前
 段 forming_weak=None / stretch 与 stretch_shortening / 无效
  数据返回 None;
- 集成: 合成"强-弱"两段上涨(短均线围成面积递减)触发顶背驰,
  下跌镜像触发底背驰。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.strength import (MaStrengthState, avg_strength_state,  # noqa: E402
                           find_ma_bc, ma_areas, sma_series)


def cross_series(signs):
    """按段符号序列造两均线: 差值段内恒为符号 x 1.0

    signs: 每段符号列表如 [+1, -1, +1], 每段 5 根。
    返回 (short, long): 短线 = 长线 + diff。
    """
    diff = []
    for s in signs:
        diff.extend([1.0 * s] * 5)
    long_ma = [10.0] * len(diff)
    short_ma = [10.0 + d for d in diff]
    return short_ma, long_ma


class TestSmaSeries(unittest.TestCase):
    """sma_series 简单移动平均"""

    def test_basic(self):
        out = sma_series([1.0, 2.0, 3.0, 4.0], 2)
        self.assertEqual(out, [None, 1.5, 2.5, 3.5])

    def test_period_one(self):
        out = sma_series([5.0, 6.0], 1)
        self.assertEqual(out, [5.0, 6.0])

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            sma_series([1.0], 0)


class TestMaAreas(unittest.TestCase):
    """ma_areas 相邻封闭面积"""

    def test_basic_segmentation(self):
        # +5 根 / -5 根 / +5 根: 三段, 前两段封闭, 末段未封闭
        short, long_ma = cross_series([+1, -1, +1])
        areas = ma_areas(short, long_ma)
        self.assertEqual(len(areas), 3)
        self.assertEqual([a.sign for a in areas], [1, -1, 1])
        # 段边界: 0-4 / 5-9 / 10-14
        self.assertEqual(areas[0].start_idx, 0)
        self.assertEqual(areas[0].end_idx, 4)
        self.assertEqual(areas[1].start_idx, 5)
        self.assertEqual(areas[1].end_idx, 9)
        self.assertEqual(areas[2].end_idx, 14)
        # 面积: +5x1.0 / -5x1.0 / +5x1.0; 平均力度 = 1.0
        self.assertAlmostEqual(areas[0].area, 5.0)
        self.assertAlmostEqual(areas[1].area, -5.0)
        self.assertAlmostEqual(areas[0].avg_area, 1.0)
        # 封闭性: 前两段已接吻封闭, 末段数据耗尽未封闭
        self.assertTrue(areas[0].closed)
        self.assertTrue(areas[1].closed)
        self.assertFalse(areas[2].closed)

    def test_touch_zero_is_crossing(self):
        # 单点触零 = 均线相交(吻), 分段边界
        diff = [1.0] * 4 + [0.0] + [1.0] * 4
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        areas = ma_areas(short, long_ma)
        self.assertEqual(len(areas), 2)
        self.assertTrue(areas[0].closed)
        self.assertEqual(areas[0].end_idx, 3)
        self.assertEqual(areas[1].start_idx, 5)

    def test_none_warmup_skipped(self):
        # sma 暖机位 None: 首段始于首个有效位
        short = [None, None, 11.0, 11.0, 10.0, 9.0]
        long_ma = [None, None, 10.0, 10.0, 10.0, 10.0]
        areas = ma_areas(short, long_ma)
        self.assertEqual(len(areas), 2)
        self.assertEqual(areas[0].start_idx, 2)

    def test_empty_cases(self):
        # 恒零 / 数据不足 / 全 None -> []
        self.assertEqual(ma_areas([10.0] * 6, [10.0] * 6), [])
        self.assertEqual(ma_areas([11.0], [10.0]), [])
        self.assertEqual(ma_areas([None, None], [None, None]), [])

    def test_data_ends_at_zero_closed(self):
        # 数据恰终于零点: 末段已封闭
        diff = [1.0] * 4 + [0.0]
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        areas = ma_areas(short, long_ma)
        self.assertEqual(len(areas), 1)
        self.assertTrue(areas[0].closed)


class TestFindMaBc(unittest.TestCase):
    """find_ma_bc 均线趋势背驰(稳妥口径)"""

    def test_top_divergence(self):
        # 同向段后弱(中间异向段跳过): 上涨段面积 5.0 -> 3.0 -> 顶背驰
        diff = [1.0] * 5 + [-1.0] * 5 + [0.6] * 5 + [-1.0] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        evts = find_ma_bc(short, long_ma)
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0]["direction"], "up")
        self.assertAlmostEqual(evts[0]["area_prev"], 5.0)
        self.assertAlmostEqual(evts[0]["area_last"], 3.0)

    def test_bottom_divergence(self):
        # 下跌段面积 -5.0 -> -3.0 -> 底背驰
        diff = [-1.0] * 5 + [1.0] * 5 + [-0.6] * 5 + [1.0] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        evts = find_ma_bc(short, long_ma)
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0]["direction"], "down")

    def test_stronger_no_event(self):
        # 后段更强: 无背驰
        diff = [0.6] * 5 + [-1.0] * 5 + [1.0] * 5 + [-1.0] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        self.assertEqual(find_ma_bc(short, long_ma), [])

    def test_intervening_opposite_skipped(self):
        # 课 15 回复: 中间的异向段(盘整/反向)不算, 跳过后仍与前面
        # 同向段比较——异向段更弱(-0.5)不产生事件, 同向比较照常
        diff = [1.0] * 5 + [-0.5] * 5 + [0.6] * 5 + [-1.0] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        evts = find_ma_bc(short, long_ma)
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0]["direction"], "up")
        self.assertAlmostEqual(evts[0]["area_last"], 3.0)

    def test_unclosed_excluded(self):
        # 末段未再接吻(数据耗尽): 稳妥口径不比较
        diff = [1.0] * 5 + [-1.0] * 5 + [0.6] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        self.assertEqual(find_ma_bc(short, long_ma), [])
        # 补一次反向穿越使末段封闭 -> 事件出现
        diff2 = diff + [-1.0] * 5
        long2 = [10.0] * len(diff2)
        short2 = [10.0 + d for d in diff2]
        evts = find_ma_bc(short2, long2)
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0]["direction"], "up")

    def test_use_avg(self):
        # use_avg=True: 平均力度比较——面积更小但每根更厚的段不背驰
        # 段 A: 10 根 x 1.0(面积 10, 平均 1.0); 段 B: 3 根 x 0.9
        # (面积 2.7, 平均 0.9 < 1.0 -> 两种口径都背驰)
        # 再造: 段 B 3 根 x 0.95(面积 2.85 < 10 但平均 0.95 < 1.0)
        # -> 双口径背驰; 关键对照: 面积口径背驰而平均口径不背驰
        # 需 avg_cur > avg_prev 且 area_cur < area_prev:
        # 段 A: 10 根 x 0.5(面积 5, 平均 0.5)
        # 段 B: 3 根 x 0.9(面积 2.7 < 5, 平均 0.9 > 0.5)
        diff = [0.5] * 10 + [-1.0] * 5 + [0.9] * 3 + [-1.0] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        by_area = find_ma_bc(short, long_ma, use_avg=False)
        by_avg = find_ma_bc(short, long_ma, use_avg=True)
        self.assertEqual(len(by_area), 1)  # 面积口径: 2.7 < 5 -> 背驰
        self.assertEqual(by_avg, [])       # 平均口径: 0.9 > 0.5 -> 不背驰

    def test_empty_input(self):
        self.assertEqual(find_ma_bc([], []), [])
        self.assertEqual(find_ma_bc([None, None], [None, None]), [])


class TestAvgStrengthState(unittest.TestCase):
    """avg_strength_state 即时平均力度"""

    def test_forming_weak(self):
        # 当下未封闭段(面积 3.0/5 根, 平均 0.6)弱于前次同向段
        # (5.0/5 根, 平均 1.0) -> forming_weak=True
        diff = [1.0] * 5 + [-1.0] * 5 + [0.6] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        st = avg_strength_state(short, long_ma)
        self.assertIsNotNone(st)
        self.assertEqual(st.direction, "up")
        self.assertAlmostEqual(st.avg_cur, 0.6)
        self.assertAlmostEqual(st.avg_prev, 1.0)
        self.assertTrue(st.forming_weak)
        self.assertAlmostEqual(st.stretch, 0.6)
        self.assertFalse(st.stretch_shortening)  # 恒 0.6 不缩短

    def test_opposite_between_still_finds_prev(self):
        # 异向段隔开: 仍取再前的同向段比较
        diff = [1.0] * 5 + [-1.0] * 5 + [1.0] * 5 + [-1.0] * 5 + [0.5] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        st = avg_strength_state(short, long_ma)
        self.assertEqual(st.direction, "up")
        # 前一同向段 = 第 3 段(+1.0 x 5), 不是相邻的 -1 段
        self.assertAlmostEqual(st.avg_prev, 1.0)
        self.assertTrue(st.forming_weak)

    def test_no_prev_same_sign(self):
        # 无同向前段(首段即当下): forming_weak=None
        diff = [1.0] * 5
        long_ma = [10.0] * 5
        short = [10.0 + d for d in diff]
        st = avg_strength_state(short, long_ma)
        self.assertEqual(st.direction, "up")
        self.assertIsNone(st.avg_prev)
        self.assertIsNone(st.forming_weak)

    def test_stretch_shortening(self):
        # 延伸长度缩短: 末两根差值 0.6 -> 0.4
        diff = [1.0] * 5 + [-1.0] * 5 + [0.6, 0.6, 0.6, 0.6, 0.4]
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        st = avg_strength_state(short, long_ma)
        self.assertAlmostEqual(st.stretch, 0.4)
        self.assertTrue(st.stretch_shortening)

    def test_no_valid_data(self):
        self.assertIsNone(avg_strength_state([], []))
        self.assertIsNone(avg_strength_state([10.0] * 6, [10.0] * 6))
        self.assertIsNone(avg_strength_state([None, None], [None, None]))


class TestIntegration(unittest.TestCase):
    """集成: 强-弱两段走势触发背驰"""

    def test_up_down_round_trip(self):
        # 上涨(强)->下跌->上涨(弱): 顶背驰; 下跌(弱)后进入上涨,
        # 即时口径应先于稳妥口径预警
        diff = [1.0] * 8 + [-1.0] * 8 + [0.5] * 8
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        # 即时: 当下段弱 -> forming_weak
        st = avg_strength_state(short, long_ma)
        self.assertTrue(st.forming_weak)
        self.assertEqual(st.direction, "up")
        # 稳妥: 末段未封闭 -> 无事件; 封闭后出现
        self.assertEqual(find_ma_bc(short, long_ma), [])
        diff2 = diff + [-1.0] * 5
        long2 = [10.0] * len(diff2)
        short2 = [10.0 + d for d in diff2]
        evts = find_ma_bc(short2, long2)
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0]["direction"], "up")
        self.assertAlmostEqual(evts[0]["area_last"], 4.0)  # 0.5 x 8
        self.assertAlmostEqual(evts[0]["area_prev"], 8.0)  # 1.0 x 8

    def test_state_to_dict(self):
        diff = [1.0] * 5 + [-1.0] * 5 + [0.6] * 5
        long_ma = [10.0] * len(diff)
        short = [10.0 + d for d in diff]
        st = avg_strength_state(short, long_ma)
        d = st.to_dict()
        self.assertIn("direction", d)
        self.assertIn("forming_weak", d)
        self.assertIn("open_area", d)
        self.assertIsNotNone(d["prev_area"])


if __name__ == "__main__":
    unittest.main()
