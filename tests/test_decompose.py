# -*- coding: utf-8 -*-
"""同级别分解测试(课 38/39: 走势类型连接的同级别分解)

覆盖分支:
    - 空输入 / 不足三段: 残段 incomplete
    - 无重叠单边走势: 残段(无本级别中枢不成走势类型)
    - 三段重叠 + 延伸段: 盘整完成于中枢末段, 延伸段开启下一单元
      (课 38 原文: 次级别延伸 6 段 = 两个盘整类型的连接)
    - 上涨/下跌趋势: a + 中枢 + 离开段 + 第二中枢(整体上移/下移)
      → 同向延续吸收, 回抽段出现时完成(两中枢趋势)
    - 离开后回抽回中枢(课 39 A3 跌回 a 高点): 完成于回抽段前一段
      (含离开段)
    - 第二中枢与进入段方向相反: 完成于离开段前, 离开段归下一单元
    - 离开后段耗尽: 含中枢但未确认结束(complete=False)
    - 进入段 a 多段: 中枢前全部段归入 a(课 39 a+A 模型)
    - 覆盖无缝: 相邻项 seg_end + 1 == seg_start, 首末覆盖全序列
    - 前缀一致性: 已确认项(complete=True)在更长前缀下保持不变
      (分解无未来函数的单调性)
    - to_dict 结构

fixture 约定: mk_xds 行间允许跳价(与 test_zs_state.py 同款,
"离开段 = 整段区间脱离 [ZD,ZG]"与 track_zs 中枢完成判定同口径)。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))


def mk_xds(rows):
    """按 (direction, start_value, end_value, start_idx, end_idx) 造 XD

    与 test_zs_state.py 同款约定; 行间不强制价格连续(跳价构造离开段)。
    """
    from chan.xd import XD
    xds = []
    for d, s, e, si, ei in rows:
        start = ("d%d" % si, float(s), si)
        end = ("d%d" % ei, float(e), ei)
        xds.append(XD(d, start, end, 1))
    return xds


# --- fixtures -----------------------------------------------------------

# F1 六段延伸: 课 38 原文场景(延伸 6 段 = 两个盘整的连接)
# s0 [1,4]u s1 [2,4]d s2 [2,5]u -> Z1=(2,4); s3 [3,5]d 重叠 ->
# 盘整1 完成 [0..2]; s3 [3,5]d s4 [3,6]u s5 [3.5,6]d -> Z2'=(3.5,5)
F1 = [("up", 1, 4, 0, 1), ("down", 4, 2, 1, 2), ("up", 2, 5, 2, 3),
      ("down", 5, 3, 3, 4), ("up", 3, 6, 4, 5), ("down", 6, 3.5, 5, 6)]

# F2 上涨趋势: a=s0 + Z1=(2.2,3.5) + 离开 s4 [4,6] + Z2=(4.2,6)
# + 回抽 s7 重叠 Z2 -> up 趋势(两中枢)完成 [0..6], s7 残段
F2 = [("up", 0.5, 1.2, 0, 1), ("down", 3.5, 2.0, 1, 2),
      ("up", 2.0, 3.8, 2, 3), ("down", 3.8, 2.2, 3, 4),
      ("up", 4.0, 6.0, 4, 5), ("down", 6.0, 4.2, 5, 6),
      ("up", 4.2, 6.5, 6, 7), ("down", 6.5, 4.5, 7, 8)]

# F2M 下跌趋势: F2 全镜像(价格取负, 方向翻转)
F2M = [("down", -1.2, -0.5, 0, 1), ("up", -2.0, -3.5, 1, 2),
       ("down", -2.0, -3.8, 2, 3), ("up", -3.8, -2.2, 3, 4),
       ("down", -4.0, -6.0, 4, 5), ("up", -6.0, -4.2, 5, 6),
       ("down", -4.2, -6.5, 6, 7), ("up", -6.5, -4.5, 7, 8)]

# F3 离开后跌回(课 39 A3 跌回 a 高点): Z1=(2.2,3.5), s4 [4,6] 离开,
# s5 [3,6] 回抽进 Z1 -> 盘整完成于 s4(含离开段) [0..4];
# s5,s6,s7 构成下一单元中枢 (3.5,5)
F3 = [("up", 0.5, 1.2, 0, 1), ("down", 3.5, 2.0, 1, 2),
      ("up", 2.0, 3.8, 2, 3), ("down", 3.8, 2.2, 3, 4),
      ("up", 4.0, 6.0, 4, 5), ("down", 6.0, 3.0, 5, 6),
      ("up", 3.0, 5.0, 6, 7), ("down", 5.0, 3.5, 7, 8)]

# F4 反向中枢: entry up + Z1=(2.2,3.5) + 离开 s4 [4,6](跳价)+
# Z2=(1.2,2) 整体在 Z1 下方 -> 完成于离开段前 [0..3],
# 离开段 s4 归下一单元(作为其进入段 a)
F4 = [("up", 0.5, 1.2, 0, 1), ("down", 3.5, 2.0, 1, 2),
      ("up", 2.0, 3.8, 2, 3), ("down", 3.8, 2.2, 3, 4),
      ("up", 4.0, 6.0, 4, 5), ("down", 2.0, 1.0, 5, 6),
      ("up", 1.0, 2.0, 6, 7), ("down", 2.0, 1.2, 7, 8)]

# F7 无重叠单边: 任何三段窗口均无重叠 -> 残段
F7 = [("up", 1, 2, 0, 1), ("down", 2, 1.5, 1, 2), ("up", 3, 5, 2, 3),
      ("down", 5, 3.5, 3, 4), ("up", 6, 8, 4, 5), ("down", 8, 6.5, 5, 6)]

# F10 离开后段耗尽: Z1=(2,4), s3 [10,12] 跳价离开, 尾段不成中枢
F10 = [("up", 1, 4, 0, 1), ("down", 4, 2, 1, 2), ("up", 2, 5, 2, 3),
       ("up", 10, 12, 3, 4), ("down", 12, 11, 4, 5)]

# F11 进入段 a 多段: 前两段不成中枢, 中枢 j=2 -> a = s0,s1
F11 = [("up", 0.5, 1.2, 0, 1), ("down", 1.2, 0.8, 1, 2),
       ("up", 2.0, 3.5, 2, 3), ("down", 3.5, 2.2, 3, 4),
       ("up", 2.2, 3.8, 4, 5)]


class TestSameLevelDecompose(unittest.TestCase):
    """same_level_decompose: 课 38/39 同级别分解"""

    def test_empty(self):
        from chan.decompose import same_level_decompose
        self.assertEqual(same_level_decompose([]), [])

    def test_short_input_incomplete(self):
        # 不足三段: 残段, 不成走势类型
        from chan.decompose import same_level_decompose
        segs = mk_xds([("up", 1, 2, 0, 1), ("down", 2, 1.5, 1, 2)])
        out = same_level_decompose(segs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "incomplete")
        self.assertFalse(out[0].complete)
        self.assertEqual((out[0].seg_start, out[0].seg_end), (0, 1))
        self.assertEqual(out[0].centers, [])

    def test_six_seg_two_consolidations(self):
        # 课 38 原文: 次级别延伸 6 段 = 两个盘整类型的连接
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F1))
        self.assertEqual(len(out), 2)
        m1, m2 = out
        # 盘整1: 中枢 s0-s2, s3 重叠 -> 完成于 s2
        self.assertEqual(m1.kind, "consolidation")
        self.assertTrue(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 2))
        self.assertEqual(m1.centers, [(2.0, 4.0)])
        self.assertIsNone(m1.direction)   # a 为空(序列起点)
        # 盘整2: s3-s5 构成新中枢, 段耗尽未确认结束
        self.assertEqual(m2.kind, "consolidation")
        self.assertFalse(m2.complete)
        self.assertEqual((m2.seg_start, m2.seg_end), (3, 5))
        self.assertEqual(m2.centers, [(3.5, 5.0)])

    def test_uptrend_two_centers(self):
        # a + Z1 + 离开 + Z2(上移) -> up 趋势延续, 回抽段完成
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F2))
        self.assertEqual(len(out), 2)
        m1, m2 = out
        self.assertEqual(m1.kind, "up")
        self.assertTrue(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 6))
        self.assertEqual(m1.direction, "up")
        self.assertEqual(m1.centers, [(2.2, 3.5), (4.2, 6.0)])
        self.assertEqual(m1.high, 6.5)   # 覆盖段极值
        self.assertEqual(m1.low, 0.5)
        # 尾残段
        self.assertEqual(m2.kind, "incomplete")
        self.assertEqual((m2.seg_start, m2.seg_end), (7, 7))

    def test_downtrend_mirror(self):
        # F2 镜像: 下跌趋势(两中枢)对称成立
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F2M))
        self.assertEqual(len(out), 2)
        m1 = out[0]
        self.assertEqual(m1.kind, "down")
        self.assertTrue(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 6))
        self.assertEqual(m1.direction, "down")
        self.assertEqual(m1.centers, [(-3.5, -2.2), (-6.0, -4.2)])

    def test_pullback_after_leave_completes(self):
        # 课 39 A3 跌回 a 高点: 离开后回抽进中枢区间
        # -> 走势完成于回抽段前一段(含离开段)
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F3))
        self.assertEqual(len(out), 2)
        m1, m2 = out
        self.assertEqual(m1.kind, "consolidation")
        self.assertTrue(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 4))
        self.assertEqual(m1.centers, [(2.2, 3.5)])
        # 回抽段 s5 开启下一单元, s5-s7 构成其中枢
        self.assertFalse(m2.complete)
        self.assertEqual((m2.seg_start, m2.seg_end), (5, 7))
        self.assertEqual(m2.centers, [(3.5, 5.0)])

    def test_opposite_center_completes_before_leave(self):
        # 第二中枢整体反向(下移)且与进入段方向相反:
        # 完成于离开段前, 离开段归下一单元作为其进入段 a
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F4))
        self.assertEqual(len(out), 2)
        m1, m2 = out
        self.assertEqual(m1.kind, "consolidation")
        self.assertTrue(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 3))
        self.assertEqual(m1.direction, "up")
        # 下一单元: a = 离开段 s4(up), 中枢 s5-s7
        self.assertEqual((m2.seg_start, m2.seg_end), (4, 7))
        self.assertEqual(m2.direction, "up")
        self.assertEqual(m2.centers, [(1.2, 2.0)])

    def test_leave_then_exhaust_incomplete(self):
        # 离开后段耗尽: 含中枢但未确认结束(complete=False)
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F10))
        self.assertEqual(len(out), 1)
        m1 = out[0]
        self.assertEqual(m1.kind, "consolidation")
        self.assertFalse(m1.complete)
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 4))
        self.assertEqual(m1.centers, [(2.0, 4.0)])

    def test_multi_segment_entry(self):
        # 课 39 a+A 模型: 中枢前的段全部归入进入段 a(可为多段)
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F11))
        self.assertEqual(len(out), 1)
        m1 = out[0]
        self.assertEqual(m1.direction, "up")    # a = s0, s1 两段
        self.assertFalse(m1.complete)           # 段耗尽未确认
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 4))
        self.assertEqual(m1.centers, [(2.2, 3.5)])

    def test_no_overlap_single_move(self):
        # 单边无重叠: 同级别分解视角下无中枢不成走势类型
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F7))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "incomplete")
        self.assertEqual(out[0].centers, [])
        self.assertIsNone(out[0].direction)

    def test_coverage_no_gap(self):
        # 覆盖无缝: 相邻项 seg_end + 1 == seg_start, 首末覆盖全序列
        from chan.decompose import same_level_decompose
        for rows in (F1, F2, F2M, F3, F4, F7, F10, F11):
            segs = mk_xds(rows)
            out = same_level_decompose(segs)
            self.assertEqual(out[0].seg_start, 0)
            self.assertEqual(out[-1].seg_end, len(segs) - 1)
            for a, b in zip(out, out[1:]):
                self.assertEqual(b.seg_start, a.seg_end + 1)

    def test_prefix_consistency(self):
        # 无未来函数的单调性: 前缀分解中 complete=True 的项,
        # 在更长前缀/完整序列中保持不变(to_dict 逐位一致)
        from chan.decompose import same_level_decompose
        for rows in (F1, F2, F3, F4):
            segs = mk_xds(rows)
            full = same_level_decompose(segs)
            full_done = [m.to_dict() for m in full if m.complete]
            n = len(segs)
            for p in range(1, n + 1):
                pre = same_level_decompose(segs[:p])
                pre_done = [m.to_dict() for m in pre if m.complete]
                # 前缀的已确认项是完整序列已确认项的前缀(单调不减)
                self.assertEqual(
                    pre_done, full_done[:len(pre_done)],
                    "prefix=%d rows_len=%d" % (p, n))

    def test_to_dict(self):
        from chan.decompose import same_level_decompose
        out = same_level_decompose(mk_xds(F1))
        d = out[0].to_dict()
        self.assertEqual(d["kind"], "consolidation")
        self.assertTrue(d["complete"])
        self.assertEqual(d["direction"], None)
        self.assertEqual(d["seg_start"], 0)
        self.assertEqual(d["seg_end"], 2)
        self.assertEqual(d["centers"], [[2.0, 4.0]])
        self.assertEqual(d["start_dt"], "d0")
        self.assertEqual(d["end_dt"], "d3")


if __name__ == "__main__":
    unittest.main()
