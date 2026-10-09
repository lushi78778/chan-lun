# -*- coding: utf-8 -*-
"""中阴阶段测试(课 89/90)

覆盖分支:
    - 空输入/不足三单元/无重叠: 高一级别中枢未成(stage="before")
    - 三单元重叠: 中枢现(stage="center"), (zd, zg) 与三段重叠区间一致
    - 延伸: 后续单元与中枢区间重叠 -> extend 事件 + 参与计数递增
    - 九段参与: upgrade 事件 + upgraded 标记(课 20/69 口径)
    - 离开挂起后单元耗尽: leave_start 记录, 中阴持续(stage="center")
    - 离开后回抽进中枢: 离开失败(return_to_center), 中枢震荡继续
    - 回抽不回中枢(上方/下方): 第三类买卖点结束中阴(课 89/101),
      bs3 单元不计入中阴 seg
    - 布林通道: 常数序列带宽 0 / 前 n-1 根 None / 线性序列单边递增
    - 超强状态与进退事件(课 90 上轨上/下轨下)
    - 轨道滞后转向: 上轨连续上升后回落 -> upper_turn_down, 下轨镜像
    - 收口: 带宽收缩至历史窗口最小值的比例阈值以下 -> squeeze
      (课 90: 中阴结束时间的最好提示)
    - 一买辅助: 超强 -> 跌回一般区域 -> 创新高但未回超强 ->
      bs1_sell_hint; 买端镜像(课 90, 辅助判断非绝对判断)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.zhongyin import (  # noqa: E402
    UPGRADE_UNITS, ZhongYinResult, boll_bands, boll_bs1_hints,
    boll_events, boll_state, track_zhongyin)


class U(object):
    """测试桩: 只需 low/high 的次级别单元"""

    def __init__(self, low, high):
        self.low = float(low)
        self.high = float(high)


# --- track_zhongyin(课 89) ------------------------------------------------

class TestTrackZhongYin(unittest.TestCase):

    def test_before_too_few_units(self):
        """空输入/不足三单元: 中枢未成"""
        for units in ([], [U(1, 2)], [U(1, 2), U(1.5, 2.5)]):
            r = track_zhongyin(units)
            self.assertEqual(r.stage, "before")
            self.assertIsNone(r.center)
            self.assertEqual(r.n_units, 0)

    def test_before_no_overlap(self):
        """三单元无共同重叠: 中枢仍未成(等待'必然先有的中枢')"""
        units = [U(0, 1), U(2, 3), U(4, 5)]
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "before")
        self.assertIsNone(r.center)

    def test_center_formed(self):
        """三单元重叠: 高一级别中枢现, (zd, zg) = 重叠区间"""
        units = [U(0, 4), U(1, 5), U(2, 6)]  # 重叠 (2, 4)
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "center")
        self.assertEqual(r.center, (2.0, 4.0))
        self.assertEqual(r.n_units, 3)
        self.assertIn((0, "center_formed"), r.events)
        self.assertIsNone(r.end_signal)

    def test_extend(self):
        """后续单元与中枢重叠: 延伸 + 参与计数"""
        units = [U(0, 4), U(1, 5), U(2, 6), U(2.5, 5)]
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "center")
        self.assertEqual(r.n_units, 4)
        self.assertIn((3, "extend"), r.events)

    def test_upgrade_nine_units(self):
        """参与单元达 9 段: 升级标记(课 89'搞成30分钟中枢')"""
        # Z=(2,4), 再叠 6 个重叠单元 -> 参与数 3+6=9
        rows = [(0, 4), (1, 5), (2, 6)] + [(2.1, 3.9)] * 6
        r = track_zhongyin([U(a, b) for a, b in rows])
        self.assertTrue(r.upgraded)
        self.assertEqual(r.n_units, UPGRADE_UNITS)
        self.assertIn((8, "upgrade"), r.events)
        self.assertEqual(r.stage, "center")  # 升级不结束中阴

    def test_leave_pending_exhausted(self):
        """离开挂起后单元耗尽: 中阴持续"""
        units = [U(0, 4), U(1, 5), U(2, 6), U(5, 7)]  # m3 脱离 (2,4)
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "center")
        self.assertEqual(r.leave_start, 3)
        self.assertIn((3, "leave_pending"), r.events)
        self.assertIsNone(r.end_signal)

    def test_return_to_center(self):
        """离开后回抽进中枢: 离开失败, 中枢震荡继续"""
        units = [U(0, 4), U(1, 5), U(2, 6), U(5, 7), U(2.5, 4.5)]
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "center")
        self.assertIsNone(r.leave_start)
        self.assertIn((4, "return_to_center"), r.events)

    def test_bs3_up(self):
        """回抽不回中枢(整体在上方): 第三类买点, 中阴向上结束"""
        units = [U(0, 4), U(1, 5), U(2, 6), U(5, 7), U(4.5, 6.5)]
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "ended")
        self.assertEqual(r.end_signal, ("bs3", "up"))
        self.assertIn((4, "bs3"), r.events)
        self.assertEqual(r.seg, (0, 3))  # bs3 单元归下一走势

    def test_bs3_down(self):
        """回抽不回中枢(整体在下方): 第三类卖点, 中阴向下结束"""
        units = [U(2, 6), U(1, 5), U(0, 4), U(-2, 0), U(-1, 1.5)]
        r = track_zhongyin(units)
        self.assertEqual(r.stage, "ended")
        self.assertEqual(r.end_signal, ("bs3", "down"))
        self.assertEqual(r.seg, (0, 3))

    def test_to_dict(self):
        """to_dict 落档口径"""
        units = [U(0, 4), U(1, 5), U(2, 6)]
        d = track_zhongyin(units).to_dict()
        self.assertEqual(d["stage"], "center")
        self.assertEqual(d["center"], (2.0, 4.0))
        self.assertIn("events", d)


# --- 布林通道(课 90) ------------------------------------------------------

class TestBoll(unittest.TestCase):

    def test_boll_bands_constant(self):
        """常数序列: 标准差 0, 三轨合一; 前 n-1 根 None"""
        closes = [5.0] * 30
        bands = boll_bands(closes, n=5)
        self.assertEqual(len(bands), 30)
        self.assertTrue(all(b is None for b in bands[:4]))
        self.assertTrue(all(b == (5.0, 5.0, 5.0) for b in bands[4:]))

    def test_boll_bands_linear(self):
        """线性递增序列: mid 递增, 上下轨对称(带宽>0)"""
        closes = [float(i) for i in range(40)]
        bands = boll_bands(closes, n=5)
        self.assertIsNone(bands[3])
        mids = [b[0] for b in bands[4:]]
        self.assertTrue(all(a < b for a, b in zip(mids, mids[1:])))
        for mid, up, lo in bands[4:]:
            self.assertAlmostEqual(mid - lo, up - mid)  # k=2 对称

    def test_boll_state(self):
        """超强状态: 上轨上/下轨下/一般(课 90)"""
        band = (10.0, 12.0, 8.0)
        self.assertEqual(boll_state(12.5, band), "super_up")
        self.assertEqual(boll_state(7.5, band), "super_down")
        self.assertEqual(boll_state(11.0, band), "normal")
        self.assertIsNone(boll_state(11.0, None))

    def test_super_events(self):
        """超强进退事件: 冲上上轨 -> 跌回"""
        closes = [10.0] * 20 + [11.0, 13.0, 13.5, 11.5, 10.5]
        ev = boll_events(closes, n=20, k=2.0)
        kinds = [k for _, k in ev]
        self.assertIn("super_up_enter", kinds)
        self.assertIn("super_up_exit", kinds)

    def test_upper_turn_down(self):
        """上轨连续上升后首次回落: upper_turn_down(二买阻力辅助)"""
        # 缓升造上轨连升, 再缓降
        closes = ([10.0] * 20 + [10.0 + 0.5 * i for i in range(1, 11)] +
                  [15.0 - 0.5 * i for i in range(1, 11)])
        ev = boll_events(closes, n=20, k=2.0, turn_run=2)
        kinds = [k for _, k in ev]
        self.assertIn("upper_turn_down", kinds)
        # 下轨镜像: 先降后升 -> lower_turn_up
        closes2 = ([15.0] * 20 + [15.0 - 0.5 * i for i in range(1, 11)] +
                   [10.0 + 0.5 * i for i in range(1, 11)])
        ev2 = boll_events(closes2, n=20, k=2.0, turn_run=2)
        self.assertIn("lower_turn_up", [k for _, k in ev2])

    def test_squeeze(self):
        """收口: 大波动后波动骤缩 -> squeeze(中阴结束提示)"""
        closes = ([10.0] * 20 +
                  [10.0 + 2.0 * ((-1) ** i) for i in range(30)] +  # 大带宽
                  [10.0] * 30)                                     # 收口
        ev = boll_events(closes, n=20, k=2.0,
                         squeeze_win=20, squeeze_ratio=0.6)
        kinds = [k for _, k in ev]
        self.assertIn("squeeze", kinds)

    def test_bs1_sell_hint(self):
        """一卖辅助(课 90): 超强推升(exit_high=14) -> 深回撤+宽幅
        震荡拉大带宽 -> 收盘创新高 14.1 但 upper≈14.20 压制, 回不到
        超强区 -> bs1_sell_hint"""
        closes = ([10.0] * 20 +
                  [11, 12, 13, 14,              # 持续超强, 极值 14
                   8.5, 12, 9, 13, 8.8, 12.5,   # 深回撤+宽幅震荡(一般区)
                   14.1])                       # 新高但未回超强
        hints = boll_bs1_hints(closes, n=20, k=2.0)
        self.assertIn("bs1_sell_hint", [h for _, h in hints])

    def test_bs1_buy_hint(self):
        """一买辅助镜像: 超跌砸出 6 -> 反抽+宽幅震荡 -> 创新低 5.9
        但未回超强区"""
        closes = ([10.0] * 20 +
                  [9, 8, 7, 6,
                   11.5, 8, 11, 7, 11.2, 7.5,
                   5.9])
        hints = boll_bs1_hints(closes, n=20, k=2.0)
        self.assertIn("bs1_buy_hint", [h for _, h in hints])

    def test_bs1_no_hint_when_back_to_super(self):
        """跌回后再创新高且回到超强: 不触发(仍超强, 非中阴)"""
        closes = [10.0] * 20 + [11.0, 12.0, 14.0, 13.0, 11.0, 16.0]
        hints = boll_bs1_hints(closes, n=20, k=2.0)
        self.assertNotIn("bs1_sell_hint", [h for _, h in hints])


if __name__ == "__main__":
    unittest.main()
