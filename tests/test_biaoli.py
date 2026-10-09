# -*- coding: utf-8 -*-
"""biaoli(表里关系, 课 91/93/99)单元测试

覆盖分支:
- bi_state: 六种输入组合(笔延伸/反向分型构造/同向分型=新笔展开)
  + 非法输入返回 None;
- bi_transition_valid: 课 91 连接约束全部 4 个合法迁移 +
  非法迁移(如 (1,1)->(-1,1) 反向直达)+ 非法状态;
- disease_stage: 16 种组合全枚举(trend=+1 上涨之病), 含未病/预警/
  欲病/关键位/向已病发展/四档恶劣排序/修复; trend=-1 镜像抽样;
  非法输入返回 None;
- followup_quality: 围绕中枢=strong / 跌出=weak / 顺侧=reverse,
  端点触及算重叠, 上下沿颠倒容错, down 镜像, 非法输入;
- zhongyin_health: 落最后中枢=healthy / 回第二中枢=dangerous /
  全脱离=extreme / 空序列=None / ZS 对象与元组双格式;
- 集成: 课 91 演进序列(healthy->warning->prodromal->onset->
  sick_worst)按连接约束逐步迁移。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chan.biaoli import (BI_TRANSITIONS, SEVERITY_RANKS, bi_state,
                         bi_transition_valid, disease_stage,
                         followup_quality, zhongyin_health)


class TestBiState(unittest.TestCase):
    """课 91 笔定理四状态"""

    def test_up_extending(self):
        # 向上笔延伸中, 无反向分型 -> (1,1)
        self.assertEqual(bi_state("up", None), (1, 1))

    def test_up_top_forming(self):
        # 向上笔 + 顶分型构造中 -> (1,0)
        self.assertEqual(bi_state("up", "top"), (1, 0))

    def test_up_bottom_confirmed(self):
        # 向上笔 + 底分型(说明顶分型已确认, 向下笔展开)-> (-1,1)
        self.assertEqual(bi_state("up", "bottom"), (-1, 1))

    def test_down_extending(self):
        # 向下笔延伸中 -> (-1,1)
        self.assertEqual(bi_state("down", None), (-1, 1))

    def test_down_bottom_forming(self):
        # 向下笔 + 底分型构造中 -> (-1,0)
        self.assertEqual(bi_state("down", "bottom"), (-1, 0))

    def test_down_top_confirmed(self):
        # 向下笔 + 顶分型(底分型已确认, 向上笔展开)-> (1,1)
        self.assertEqual(bi_state("down", "top"), (1, 1))

    def test_invalid_inputs(self):
        # 非法方向/非法分型类型 -> None
        self.assertIsNone(bi_state("flat", None))
        self.assertIsNone(bi_state("up", "side"))
        self.assertIsNone(bi_state("up", "unknown"))


class TestBiTransitionValid(unittest.TestCase):
    """课 91 连接约束"""

    def test_all_legal_transitions(self):
        # BI_TRANSITIONS 落表与课 91 原文一致
        self.assertEqual(BI_TRANSITIONS[(1, 1)], ((1, 0),))
        self.assertEqual(BI_TRANSITIONS[(-1, 1)], ((-1, 0),))
        self.assertEqual(BI_TRANSITIONS[(1, 0)], ((1, 1), (-1, 1)))
        self.assertEqual(BI_TRANSITIONS[(-1, 0)], ((1, 1), (-1, 1)))
        for prev, nxts in BI_TRANSITIONS.items():
            for nxt in nxts:
                self.assertTrue(bi_transition_valid(prev, nxt))

    def test_illegal_transitions(self):
        # (1,1) 不能直达 (-1,1)/(1,1);分型构造不能直达另一个分型构造
        self.assertFalse(bi_transition_valid((1, 1), (-1, 1)))
        self.assertFalse(bi_transition_valid((1, 1), (1, 1)))
        self.assertFalse(bi_transition_valid((-1, 1), (1, 1)))
        self.assertFalse(bi_transition_valid((1, 0), (-1, 0)))
        self.assertFalse(bi_transition_valid((-1, 0), (1, 0)))
        self.assertFalse(bi_transition_valid((1, 0), (1, 0)))

    def test_invalid_states(self):
        # 非法状态 -> False
        self.assertFalse(bi_transition_valid((0, 0), (1, 1)))
        self.assertFalse(bi_transition_valid((1, 1), (2, 1)))


class TestDiseaseStage(unittest.TestCase):
    """课 91 双级别病情矩阵(16 组合)"""

    def test_healthy_and_warning(self):
        # 未病: 双级别同向延伸; 预警: 低级别分型构造(小警告)
        self.assertEqual(disease_stage((1, 1), (1, 1), 1), "healthy")
        self.assertEqual(disease_stage((1, 1), (1, 0), 1), "warning")

    def test_prodromal(self):
        # 欲病: 低级别反向笔延伸(低级别 (1,0) 已确认, 重要警告成立)
        self.assertEqual(disease_stage((1, 1), (-1, 1), 1), "prodromal")
        self.assertEqual(disease_stage((1, 1), (-1, 0), 1), "prodromal")

    def test_critical_and_onset(self):
        # 关键位: 高级别分型构造中 + 低级别重新同向
        self.assertEqual(disease_stage((1, 0), (1, 1), 1), "critical")
        self.assertEqual(disease_stage((1, 0), (1, 0), 1), "critical")
        # 欲病向已病发展: 高级别分型构造中 + 低级别反向延伸
        self.assertEqual(disease_stage((1, 0), (-1, 1), 1), "onset")
        self.assertEqual(disease_stage((1, 0), (-1, 0), 1), "onset")

    def test_sick_ranks(self):
        # 课 91 下跌四档恶劣排序(trend=+1, 高级别已反向)
        self.assertEqual(disease_stage((-1, 1), (-1, 1), 1), "sick_worst")
        self.assertEqual(disease_stage((-1, 1), (-1, 0), 1), "sick_second")
        self.assertEqual(disease_stage((-1, 0), (-1, 1), 1), "sick_third")
        # 第 4 档: 可能出现转机的窗口
        self.assertEqual(disease_stage((-1, 0), (-1, 0), 1), "turn_window")
        # SEVERITY_RANKS 落表
        self.assertEqual(SEVERITY_RANKS["sick_worst"], 1)
        self.assertEqual(SEVERITY_RANKS["turn_window"], 4)

    def test_recovering(self):
        # 修复中: 高级别已反向但低级别重新沿原趋势延伸
        self.assertEqual(disease_stage((-1, 1), (1, 1), 1), "recovering")
        self.assertEqual(disease_stage((-1, 1), (1, 0), 1), "recovering")
        self.assertEqual(disease_stage((-1, 0), (1, 1), 1), "recovering")
        self.assertEqual(disease_stage((-1, 0), (1, 0), 1), "recovering")

    def test_all_16_combinations_valid(self):
        # 16 种组合全部有合法标签(不抛异常/不为 None)
        states = [(1, 1), (-1, 1), (1, 0), (-1, 0)]
        labels = set()
        for high in states:
            for low in states:
                r = disease_stage(high, low, 1)
                self.assertIsNotNone(r)
                labels.add(r)
        # 10 个标签全部出现
        self.assertEqual(len(labels), 10)

    def test_downtrend_mirror(self):
        # trend=-1(监控下跌之病, 病=上涨/踏空)镜像抽样
        self.assertEqual(disease_stage((-1, 1), (-1, 1), -1), "healthy")
        self.assertEqual(disease_stage((-1, 1), (1, 1), -1), "prodromal")
        self.assertEqual(disease_stage((1, 1), (1, 1), -1), "sick_worst")
        self.assertEqual(disease_stage((1, 0), (1, 0), -1), "turn_window")
        self.assertEqual(disease_stage((1, 1), (-1, 1), -1), "recovering")

    def test_invalid_inputs(self):
        # 非法状态/非法 trend -> None
        self.assertIsNone(disease_stage((0, 1), (1, 1), 1))
        self.assertIsNone(disease_stage((1, 1), (2, 0), 1))
        self.assertIsNone(disease_stage((1, 1), (1, 1), 0))


class TestFollowupQuality(unittest.TestCase):
    """课 93 (1,0) 后震荡强弱(以最后中枢为依据)"""

    def test_strong_around_center(self):
        # 震荡段与最后中枢有重叠 -> 强震荡
        self.assertEqual(followup_quality(10.0, 12.0, 11.0, 13.0, "up"), "strong")
        self.assertEqual(followup_quality(10.0, 12.0, 9.5, 10.0, "up"), "strong")

    def test_weak_below_center(self):
        # 向上走势: 震荡段整体在中枢下方 -> 弱震荡(将向 (-1,1) 发展)
        self.assertEqual(followup_quality(10.0, 12.0, 8.0, 9.5, "up"), "weak")

    def test_reverse_above_center(self):
        # 向上走势: 震荡段整体在中枢上方 -> 顶分型构造失败, 回 (1,1)
        self.assertEqual(followup_quality(10.0, 12.0, 12.5, 14.0, "up"), "reverse")

    def test_down_mirror(self):
        # 向下走势镜像: 上方=弱, 下方=底分型失败
        self.assertEqual(followup_quality(10.0, 12.0, 12.5, 14.0, "down"), "weak")
        self.assertEqual(followup_quality(10.0, 12.0, 8.0, 9.5, "down"), "reverse")

    def test_swapped_bounds_tolerance(self):
        # 上下沿颠倒容错
        self.assertEqual(followup_quality(12.0, 10.0, 11.0, 13.0, "up"), "strong")

    def test_invalid_direction(self):
        self.assertIsNone(followup_quality(10.0, 12.0, 11.0, 13.0, "flat"))


class _FakeZS(object):
    """带 zd/zg 属性的桩对象(模拟 zs.ZS)"""

    def __init__(self, zd, zg):
        self.zd = zd
        self.zg = zg


class TestZhongyinHealth(unittest.TestCase):
    """课 99 中阴健康度"""

    def test_healthy_in_last_center(self):
        # 中阴中枢与最后一个前中枢重叠 -> 健康
        prev = [(10.0, 12.0), (13.0, 15.0)]
        self.assertEqual(zhongyin_health(prev, (14.0, 16.0)), "healthy")
        # 端点触及算重叠
        self.assertEqual(zhongyin_health(prev, (15.0, 17.0)), "healthy")

    def test_dangerous_back_to_earlier_center(self):
        # 与最后中枢无重叠, 回到第二(更早)中枢 -> 危险
        prev = [(10.0, 12.0), (13.0, 15.0)]
        self.assertEqual(zhongyin_health(prev, (10.5, 11.5)), "dangerous")

    def test_extreme_no_overlap(self):
        # 与全部前中枢均无重叠 -> 脱离常态, 划分需重审
        prev = [(10.0, 12.0), (13.0, 15.0)]
        self.assertEqual(zhongyin_health(prev, (20.0, 22.0)), "extreme")

    def test_object_format(self):
        # ZS 对象与元组混用
        prev = [_FakeZS(10.0, 12.0), _FakeZS(13.0, 15.0)]
        self.assertEqual(zhongyin_health(prev, _FakeZS(14.0, 16.0)), "healthy")
        self.assertEqual(zhongyin_health(prev, (10.5, 11.5)), "dangerous")

    def test_empty_centers(self):
        # 空中枢序列 -> None
        self.assertIsNone(zhongyin_health([], (10.0, 12.0)))

    def test_single_center(self):
        # 只有一个前中枢: 重叠=健康, 无重叠=extreme(无更早中枢可回)
        self.assertEqual(zhongyin_health([(10.0, 12.0)], (11.0, 13.0)), "healthy")
        self.assertEqual(zhongyin_health([(10.0, 12.0)], (14.0, 16.0)), "extreme")


class TestCourse91Progression(unittest.TestCase):
    """课 91 未病->已病演进序列的集成验证"""

    def test_progression_with_legal_transitions(self):
        # 演进: 高(1,1)低(1,1) -> 低出现(1,0) -> 低确认(-1,1) ->
        # 高分型构造(1,0)+低(-1,1) -> 高确认(-1,1)+低(-1,1)
        # 每步低级别状态迁移必须满足连接约束
        seq = [(1, 1), (1, 0), (-1, 1)]
        stages = []
        for i in range(1, len(seq)):
            self.assertTrue(bi_transition_valid(seq[i - 1], seq[i]),
                            "step %d: %s -> %s 非法" % (i, seq[i - 1], seq[i]))
        # 病情标签单调恶化
        stages.append(disease_stage((1, 1), (1, 1), 1))
        stages.append(disease_stage((1, 1), (1, 0), 1))
        stages.append(disease_stage((1, 1), (-1, 1), 1))
        stages.append(disease_stage((1, 0), (-1, 1), 1))
        stages.append(disease_stage((-1, 1), (-1, 1), 1))
        self.assertEqual(stages, ["healthy", "warning", "prodromal",
                                  "onset", "sick_worst"])

    def test_relief_path(self):
        # 缓解路径: 低级别分型构造失败 -> 回到延伸, 病情回退
        self.assertTrue(bi_transition_valid((1, 0), (1, 1)))
        self.assertEqual(disease_stage((1, 0), (1, 1), 1), "critical")
        self.assertEqual(disease_stage((1, 1), (1, 1), 1), "healthy")


if __name__ == "__main__":
    unittest.main()
