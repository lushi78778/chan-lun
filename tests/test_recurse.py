# -*- coding: utf-8 -*-
"""级别递归 f2 测试(课 35/63/84/102: 三个连续次级别走势类型重叠
= 高一级别中枢, 逐级上推)

覆盖分支:
    - 空输入 / 不足三单元: 残段 incomplete
    - 中枢延伸(与同级别分解的核心差异): 单元与中枢区间重叠归并
      继续, 不切分(课 17/20)
    - 同输入对照: same_level_decompose 切成两个盘整(课 38 不延伸),
      level_up 全归并(允许延伸)——两种切分语义的直接对照
    - 离开后回抽进中枢区间(课 39 A3 跌回): 完成于回抽单元前
    - 上涨/下跌趋势: 第二中枢整体上移/下移 + 进入方向同向 → 吸收
    - 三中枢依次上移(课 35 N 中枢延续): up 三个 centers
    - 第二中枢与进入方向相反: 完成于离开单元前, 离开单元归下一单元
    - 单元耗尽: 含中枢但未确认结束(complete=False)
    - 进入段 a 多单元: 中枢前全部单元归入 a
    - 覆盖无缝: 相邻项 seg_end + 1 == seg_start, 首末覆盖全序列
    - 前缀一致性: 已确认项(complete=True)在更长前缀下保持不变
    - 递归链端到端: xds -> level_up -> 再 level_up, 二级复合
      (课 102 记数法: 任何走势唯一表示为各级别的连接)

fixture 约定: mk_moves 直接造次级别 MoveType 单元(rows 给
kind/low/high/起止单元索引), 单元间无需价格连续; mk_xds 与
test_decompose.py 同款(行间允许跳价)。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan.decompose import MoveType, same_level_decompose  # noqa: E402
from chan.recurse import level_up  # noqa: E402


def mk_moves(rows):
    """按 (kind, low, high, start_idx, end_idx) 造次级别走势类型"""
    out = []
    for kind, lo, hi, si, ei in rows:
        out.append(MoveType(kind, True,
                            kind if kind in ("up", "down") else None,
                            "d%d" % si, "d%d" % ei, float(hi), float(lo),
                            si, ei, []))
    return out


def mk_xds(rows):
    """按 (direction, start_value, end_value, start_idx, end_idx) 造 XD

    与 test_decompose.py 同款约定(行间允许跳价构造离开单元)。
    """
    from chan.xd import XD
    xds = []
    for d, s, e, si, ei in rows:
        start = ("d%d" % si, float(s), si)
        end = ("d%d" % ei, float(e), ei)
        xds.append(XD(d, start, end, 1))
    return xds


def assert_gapless(test, moves, units):
    """覆盖无缝: 首起 0, 末达 n-1, 相邻 seg_end + 1 == seg_start"""
    if not moves:
        return
    test.assertEqual(moves[0].seg_start, 0)
    test.assertEqual(moves[-1].seg_end, len(units) - 1)
    for a, b in zip(moves, moves[1:]):
        test.assertEqual(b.seg_start, a.seg_end + 1)


# --- fixtures(MoveType 输入, 记 (kind, low, high, i, j)) -----------------

# F1 中枢延伸: m0..m2 -> Z1=(2,4); m3/m4 与 Z1 重叠 = 延伸归并
# (同级别分解口径下 m3 已切分, 本模块不切)
F1 = [("up", 0, 4, 0, 0), ("down", 1, 5, 1, 1), ("up", 2, 6, 2, 2),
      ("down", 2.5, 5, 3, 3), ("up", 1.5, 4.5, 4, 4)]

# F2 离开后回抽(课 39 A3 跌回): Z1=(2,4) + m3 离开 + m4 回抽重叠
# -> 盘整完成 [0..3](含离开单元), m4 残段
F2 = [("up", 0, 4, 0, 0), ("down", 1, 5, 1, 1), ("up", 2, 6, 2, 2),
      ("down", 4.5, 8, 3, 3), ("up", 3, 6, 4, 4)]

# F3 上涨趋势: Z1=(3,4) + 离开组 -> Z2=(6,9) 整体上移 -> up(两中枢),
# 单元耗尽 complete=False
F3 = [("up", 2, 4, 0, 0), ("down", 2.5, 5, 1, 1), ("up", 3, 6, 2, 2),
      ("down", 5, 9, 3, 3), ("up", 5.5, 9.5, 4, 4), ("down", 6, 10, 5, 5)]

# F3M 下跌趋势镜像: Z1=(-4,-3) + Z2=(-9,-6) 整体下移 -> down
F3M = [("down", -4, -2, 0, 0), ("up", -5, -2.5, 1, 1),
       ("down", -6, -3, 2, 2), ("up", -9, -5, 3, 3),
       ("down", -9.5, -5.5, 4, 4), ("up", -10, -6, 5, 5)]

# F4 三中枢依次上移(课 35: 依次保持第 N 个中枢比 N-1 个高 = 上涨
# 延续): Z1=(3,4) Z2=(6,9) Z3=(11,14), m6 为 Z2 的延伸单元
F4 = F3 + [("up", 6.5, 11, 6, 6), ("down", 10, 14, 7, 7),
           ("up", 10.5, 14.5, 8, 8), ("down", 11, 15, 9, 9)]

# F5 第二中枢与进入方向相反: a=m0(up) + Z1=(2,4) + 离开组 Z2=(0,1)
# 整体下移 -> up 进入遇 down 新中枢, 盘整完成 [0..3](a 为空补定情形
# 的对照组, 此处 entry_dir=up), 离开组归第二单元
F5 = [("up", 5, 8, 0, 0), ("down", 0, 4, 1, 1), ("up", 1, 5, 2, 2),
      ("down", 2, 6, 3, 3), ("up", -1, 1.5, 4, 4),
      ("down", -0.5, 1, 5, 5), ("up", 0, 1.5, 6, 6)]

# F7 前缀一致性: 单元1 盘整完成 [0..3], 单元2 up 耗尽 [4..9]
F7 = [("up", 0, 4, 0, 0), ("down", 1, 5, 1, 1), ("up", 2, 6, 2, 2),
      ("down", 4.5, 8, 3, 3), ("up", 3, 6, 4, 4), ("down", 5, 7, 5, 5),
      ("up", 5.5, 8, 6, 6), ("down", 6.5, 9, 7, 7), ("up", 7, 10, 8, 8),
      ("down", 7.5, 11, 9, 9)]

# F8 进入段 a 多单元: m0+m1 为 a(entry=up), Z1=(2,4) 起于 m2
F8 = [("up", 8, 10, 0, 0), ("down", 1.5, 4, 1, 1), ("up", 1, 5, 2, 2),
      ("down", 2, 6, 3, 3), ("up", 3, 7, 4, 4), ("down", 4.5, 8, 5, 5),
      ("up", 5, 9, 6, 6)]

# F9 同输入对照(与 test_decompose.py F1 同款 XD 序列): 课 38 口径
# 切成两个盘整, 递归口径全归并(中枢延伸)
F9 = [("up", 1, 4, 0, 1), ("down", 4, 2, 1, 2), ("up", 2, 5, 2, 3),
      ("down", 5, 3, 3, 4), ("up", 3, 6, 4, 5), ("down", 6, 3.5, 5, 6)]


class TestLevelUpBasics(unittest.TestCase):
    """基础分支: 残段/延伸/回抽/趋势/反向/耗尽"""

    def test_empty_and_too_few(self):
        """空输入与不足三单元: 残段 incomplete"""
        self.assertEqual(level_up([]), [])
        mv = level_up(mk_moves(F1[:2]))
        self.assertEqual(len(mv), 1)
        self.assertEqual(mv[0].kind, "incomplete")
        self.assertFalse(mv[0].complete)
        self.assertEqual(mv[0].centers, [])
        self.assertEqual((mv[0].seg_start, mv[0].seg_end), (0, 1))

    def test_extension_no_split(self):
        """中枢延伸: 与中枢区间重叠的单元归并继续, 不切分(课 17/20)"""
        units = mk_moves(F1)
        mv = level_up(units)
        # 全部 5 个单元归并为一个走势类型: Z1=(2,4), m3/m4 重叠延伸
        self.assertEqual(len(mv), 1)
        m = mv[0]
        self.assertEqual(m.kind, "consolidation")
        self.assertEqual(m.centers, [(2.0, 4.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 4))
        self.assertFalse(m.complete)  # 单元耗尽, 未确认结束
        assert_gapless(self, mv, units)

    def test_pullback_after_leave(self):
        """离开后回抽进中枢区间: 完成于回抽单元前(含离开单元), 课 39"""
        units = mk_moves(F2)
        mv = level_up(units)
        self.assertEqual(len(mv), 2)
        m1, m2 = mv
        self.assertEqual(m1.kind, "consolidation")
        self.assertTrue(m1.complete)
        self.assertEqual(m1.centers, [(2.0, 4.0)])
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 3))  # 含离开 m3
        self.assertEqual(m2.kind, "incomplete")  # 仅剩回抽单元
        self.assertEqual((m2.seg_start, m2.seg_end), (4, 4))
        assert_gapless(self, mv, units)

    def test_uptrend_two_centers(self):
        """上涨趋势: 第二中枢整体上移 + 同向吸收(两中枢), 耗尽未确认"""
        units = mk_moves(F3)
        mv = level_up(units)
        self.assertEqual(len(mv), 1)
        m = mv[0]
        self.assertEqual(m.kind, "up")
        self.assertEqual(m.direction, "up")  # a 为空, 由中枢上移补定
        self.assertEqual(m.centers, [(3.0, 4.0), (6.0, 9.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 5))
        self.assertFalse(m.complete)  # 离开后单元耗尽
        assert_gapless(self, mv, units)

    def test_downtrend_mirror(self):
        """下跌趋势镜像: 第二中枢整体下移 -> down"""
        units = mk_moves(F3M)
        mv = level_up(units)
        self.assertEqual(len(mv), 1)
        m = mv[0]
        self.assertEqual(m.kind, "down")
        self.assertEqual(m.direction, "down")
        self.assertEqual(m.centers, [(-4.0, -3.0), (-9.0, -6.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 5))
        self.assertFalse(m.complete)

    def test_three_centers_uptrend(self):
        """课 35 N 中枢延续: 三中枢依次上移 = 上涨延续(含 Z2 延伸单元)"""
        units = mk_moves(F4)
        mv = level_up(units)
        self.assertEqual(len(mv), 1)
        m = mv[0]
        self.assertEqual(m.kind, "up")
        self.assertEqual(m.centers,
                         [(3.0, 4.0), (6.0, 9.0), (11.0, 14.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 9))
        self.assertFalse(m.complete)  # 末段离开后耗尽
        assert_gapless(self, mv, units)

    def test_reverse_direction_completes(self):
        """第二中枢与进入方向相反: 完成于离开单元前, 离开组归下单元"""
        units = mk_moves(F5)
        mv = level_up(units)
        self.assertEqual(len(mv), 2)
        m1, m2 = mv
        self.assertEqual(m1.kind, "consolidation")  # 单中枢不成趋势
        self.assertTrue(m1.complete)
        self.assertEqual(m1.direction, "up")  # a=m0 进入方向
        self.assertEqual(m1.centers, [(2.0, 4.0)])
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 3))
        # 离开组 m4..m6 自成中枢 (0,1), a 为空故 direction=None, 耗尽未确认
        self.assertEqual(m2.kind, "consolidation")
        self.assertFalse(m2.complete)
        self.assertIsNone(m2.direction)
        self.assertEqual(m2.centers, [(0.0, 1.0)])
        self.assertEqual((m2.seg_start, m2.seg_end), (4, 6))
        assert_gapless(self, mv, units)

    def test_entry_a_multiple_units(self):
        """进入段 a 多单元: 中枢前全部单元归入 a, entry 取首单元方向"""
        units = mk_moves(F8)
        mv = level_up(units)
        self.assertEqual(len(mv), 1)
        m = mv[0]
        self.assertEqual(m.direction, "up")  # a = m0 + m1, 取 m0 方向
        self.assertEqual(m.centers, [(2.0, 4.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 6))
        self.assertFalse(m.complete)
        assert_gapless(self, mv, units)


class TestLevelUpSemantics(unittest.TestCase):
    """语义性质: 与同级别分解对照 / 前缀一致性 / 递归链"""

    def test_vs_same_level_decompose(self):
        """同输入两种切分: 课 38 切两个盘整 vs 递归口径延伸归并"""
        xds = mk_xds(F9)
        sld = same_level_decompose(xds)
        rec = level_up(xds)
        # 课 38 口径: s3 重叠 -> 盘整1 完成 [0..2]; s3..s5 Z2' 盘整2
        self.assertEqual(len(sld), 2)
        self.assertTrue(sld[0].complete)
        self.assertEqual(sld[0].centers, [(2.0, 4.0)])
        self.assertEqual((sld[0].seg_start, sld[0].seg_end), (0, 2))
        # 递归口径: s3/s4/s5 全部与 Z1 重叠 -> 中枢延伸归并, 不切分
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0].kind, "consolidation")
        self.assertEqual(rec[0].centers, [(2.0, 4.0)])
        self.assertEqual((rec[0].seg_start, rec[0].seg_end), (0, 5))
        self.assertFalse(rec[0].complete)

    def test_prefix_consistency(self):
        """前缀一致性: 已确认项在更长前缀下保持不变(无未来函数)"""
        units = mk_moves(F7)
        full = level_up(units)
        full_done = [m.to_dict() for m in full if m.complete]
        for p in range(1, len(units) + 1):
            pre_done = [m.to_dict() for m in level_up(units[:p])
                        if m.complete]
            self.assertEqual(
                pre_done, full_done[:len(pre_done)],
                "前缀 %d 下已确认项漂移" % p)

    def test_f7_expected_result(self):
        """F7 全序列精确结果: 盘整完成 + up 耗尽(两中枢)"""
        units = mk_moves(F7)
        mv = level_up(units)
        self.assertEqual(len(mv), 2)
        m1, m2 = mv
        self.assertEqual(m1.kind, "consolidation")
        self.assertTrue(m1.complete)
        self.assertEqual(m1.centers, [(2.0, 4.0)])
        self.assertEqual((m1.seg_start, m1.seg_end), (0, 3))
        self.assertEqual(m2.kind, "up")
        self.assertFalse(m2.complete)
        self.assertEqual(m2.centers, [(5.5, 6.0), (7.5, 9.0)])
        self.assertEqual((m2.seg_start, m2.seg_end), (4, 9))

    def test_recursion_chain(self):
        """递归链端到端: xds -> l1 -> l2 二级复合(课 102 记数法)"""
        # 12 段交替: 三个三段重叠组依次上移 + 回抽收尾
        xds = mk_xds([
            ("up", 1, 4, 0, 1), ("down", 4, 2, 1, 2), ("up", 2, 5, 2, 3),
            ("down", 5, 3, 3, 4), ("up", 3, 6, 4, 5), ("down", 6, 3, 5, 6),
            ("up", 4, 7, 6, 7), ("down", 7, 5, 7, 8), ("up", 5, 8, 8, 9),
            ("down", 8, 5, 9, 10), ("up", 6, 9, 10, 11),
            ("down", 9, 6.5, 11, 12)])
        l1 = level_up(xds)
        assert_gapless(self, l1, xds)
        self.assertEqual(len(l1), 1)  # 全序列一个高一级别走势类型
        # Z1=(2,4) 起于 s0..s2; s3/s4/s5 重叠延伸; s6 [4,7]? s6 与
        # (2,4) 重叠(4<=4) 延伸; s7 [5,7] 离开; s8 [5,8] s9 [5,8]
        # -> Z2=(5,7) 上移; s10 [6,9] 与 Z2 重叠延伸; s11 [6.5,9]
        # 与 Z2 重叠延伸 -> up 两中枢耗尽
        self.assertEqual(l1[0].kind, "up")
        self.assertEqual(l1[0].centers, [(2.0, 4.0), (5.0, 7.0)])
        # 二级复合: l1 单元再升一级
        l2 = level_up(l1)
        assert_gapless(self, l2, l1)
        # 仅 1 个次级别单元, 不成高一级别中枢 -> 残段
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0].kind, "incomplete")
        self.assertEqual((l2[0].seg_start, l2[0].seg_end), (0, 0))
        self.assertEqual(l2[0].high, l1[0].high)
        self.assertEqual(l2[0].low, l1[0].low)

    def test_incomplete_unit_as_input(self):
        """incomplete 单元可作输入(区间极值有效), 参与重叠判定"""
        # 末尾残段(1 个单元) + 三个成中枢单元: 残段在前作进入段 a
        tail = MoveType("incomplete", False, None, "x0", "x0",
                        8.0, 6.0, 0, 0, [])
        core = mk_moves([("down", 0, 4, 1, 1), ("up", 1, 5, 2, 2),
                         ("down", 2, 6, 3, 3), ("up", 2.5, 5, 4, 4)])
        units = [tail] + core
        mv = level_up(units)
        self.assertEqual(len(mv), 1)
        m = mv[0]
        # a = 残段 tail(direction None, kind incomplete -> 方向 None)
        self.assertIsNone(m.direction)
        self.assertEqual(m.centers, [(2.0, 4.0)])
        self.assertEqual((m.seg_start, m.seg_end), (0, 4))


if __name__ == "__main__":
    unittest.main()
