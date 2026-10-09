# -*- coding: utf-8 -*-
"""中枢状态机测试(课 20 中枢中心定理一/二、课 69 九段升级、课 70 当下判定)

覆盖分支:
    zs_relation(定理二, 纯函数):
        - down_continue: 后 GG < 前 DD(严格)
        - up_continue:   后 DD > 前 GG(严格)
        - expand:        区间不重叠但波动区间重叠(定理二扩展两分支)
        - expand:        [ZD,ZG] 区间自身重叠
        - 触及边界(后 GG == 前 DD)属 expand, 非下跌延续(严格不等号)

    build_expanded_zs(课 20 中枢公式, 纯函数):
        - 三单元重叠公式主口径(前中枢/连接段/后中枢)
        - 连接段撑破重叠 -> 退回两中枢波动区间重叠口径(n=2)
        - 两波动区间仅端点相触 -> None

    track_zs(状态机端到端):
        - form -> extend -> upgrade_9(恰一次) -> extend -> complete 全链
        - 12 段延伸 extended_9 与既有 find_zs 口径一致(回归锚)
        - complete 的 leave_dir(向上/向下离开)
        - new 事件 relation=up_continue(后 DD > 前 GG, 跳价构造)
        - new 事件 relation=expand 且携带高级别中枢候选 expand_zs
        - find_zs == track_zs[0](薄包装零回归)
        - 短输入(<3 段)返回空
        - 前缀截断: 事件流 = 完整事件流按 index 过滤(逐段推进无未来)
        - 事件 index 严格递增(当下判定的时序单调性)
"""

import unittest


def mk_zs(zd, zg, gg, dd, direction="up"):
    """直接构造 ZS(绕过线段, 用于纯函数测试)"""
    from chan.zs import ZS
    return ZS(zd, zg, gg, dd, "d0", "d1", direction, 3)


def mk_xds(rows):
    """按 (direction, start_value, end_value, start_idx, end_idx) 造 XD

    与 test_chan.py TestFindZS.mk_xds 同款约定; 行间不强制价格连续
    (既有 fixtures 亦允许跳价, 如 test_no_overlap_no_zs)。
    """
    from chan.xd import XD
    xds = []
    for d, s, e, si, ei in rows:
        start = ("d%d" % si, float(s), si)
        end = ("d%d" % ei, float(e), ei)
        xds.append(XD(d, start, end, 1))
    return xds


class TestZsRelation(unittest.TestCase):
    """课 20 中枢中心定理二: 前后同级别中枢的方向关系(纯函数)"""

    def test_down_continue(self):
        # 后 GG(9) < 前 DD(10) 严格 -> 下跌及其延续
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)     # 波动区间 [10, 20]
        curr = mk_zs(4, 8, 9, 5)         # 波动区间 [5, 9]
        self.assertEqual(zs_relation(prev, curr), "down_continue")

    def test_up_continue(self):
        # 后 DD(21) > 前 GG(20) 严格 -> 上涨及其延续
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(22, 26, 27, 21)
        self.assertEqual(zs_relation(prev, curr), "up_continue")

    def test_expand_wave_overlap(self):
        # 定理二扩展分支一: 后 ZD(21) > 前 ZG(18) 但后 DD(19) <= 前 GG(20)
        # -> 波动区间重叠 -> 更大级别走势中枢
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(21, 25, 27, 19)
        self.assertEqual(zs_relation(prev, curr), "expand")

    def test_expand_wave_overlap_below(self):
        # 定理二扩展分支二: 后 ZG(8) < 前 ZD(12) 且后 GG(11) >= 前 DD(10)
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(5, 8, 11, 4)
        self.assertEqual(zs_relation(prev, curr), "expand")

    def test_expand_interval_overlap(self):
        # [ZD,ZG] 区间自身重叠(课20: 趋势里同级别前后中枢不能有任何
        # 重叠, 重叠即归入更大级别中枢情形)
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(13, 17, 19, 11)
        self.assertEqual(zs_relation(prev, curr), "expand")

    def test_touch_boundary_is_expand(self):
        # 后 GG == 前 DD(恰好触及, 非严格小于) -> 不算下跌延续, 属扩展
        from chan.zs import zs_relation
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(4, 8, 10, 5)         # GG == 前 DD == 10
        self.assertEqual(zs_relation(prev, curr), "expand")
        # 镜像: 后 DD == 前 GG -> 不算上涨延续
        curr2 = mk_zs(22, 26, 27, 20)     # DD == 前 GG == 20
        self.assertEqual(zs_relation(prev, curr2), "expand")


class TestBuildExpandedZs(unittest.TestCase):
    """扩展时按课 20 中枢公式构造更高级别中枢候选(纯函数)"""

    def test_three_unit_formula(self):
        # 主口径: 前中枢/连接段/后中枢三单元重叠
        # zd = max(10, 13, 14) = 14, zg = min(20, 17, 22) = 17
        from chan.zs import build_expanded_zs
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(16, 18.5, 22, 14, direction="up")
        zs = build_expanded_zs(prev, curr, 13.0, 17.0,
                               start_dt="d0", end_dt="d9")
        self.assertIsNotNone(zs)
        self.assertEqual(zs.zd, 14.0)
        self.assertEqual(zs.zg, 17.0)
        self.assertEqual(zs.gg, 22.0)   # max(20, 17, 22)
        self.assertEqual(zs.dd, 10.0)   # min(10, 13, 14)
        self.assertEqual(zs.xd_count, 3)
        self.assertEqual(zs.start_dt, "d0")
        self.assertEqual(zs.end_dt, "d9")
        # 后中枢区间中点在前中枢之上(区间重叠时以中点定位) -> 方向 up
        self.assertEqual(zs.direction, "up")

    def test_fallback_two_unit(self):
        # 连接段 [19, 21] 撑破三单元重叠(zd=19 >= zg=15)
        # -> 退回两中枢波动区间重叠: zd = max(10, 5) = 10,
        #    zg = min(20, 15) = 15, n = 2
        from chan.zs import build_expanded_zs
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(7, 13, 15, 5, direction="down")
        zs = build_expanded_zs(prev, curr, 19.0, 21.0)
        self.assertIsNotNone(zs)
        self.assertEqual(zs.zd, 10.0)
        self.assertEqual(zs.zg, 15.0)
        self.assertEqual(zs.xd_count, 2)
        # 后中枢区间在前中枢之下 -> 方向 down
        self.assertEqual(zs.direction, "down")

    def test_touch_only_returns_none(self):
        # 两波动区间仅端点相触(后 DD == 前 GG == 20): 三单元与两单元
        # 口径均退化 -> None
        from chan.zs import build_expanded_zs
        prev = mk_zs(12, 18, 20, 10)
        curr = mk_zs(22, 26, 30, 20)
        self.assertIsNone(build_expanded_zs(prev, curr, 19.0, 21.0))


class TestTrackZs(unittest.TestCase):
    """中枢状态机端到端(课 70 当下判定)"""

    # 12 段延伸 + 向上离开(与 test_chan.py TestFindZS 同源 fixture,
    # 回归锚: zd=4, zg=9, gg=12, dd=0, extended_9=True)
    ROWS_EXTEND12 = [
        ("up", 0, 10, 0, 4),
        ("down", 10, 4, 4, 8),
        ("up", 4, 9, 8, 12),
        ("down", 9, 3, 12, 16),
        ("up", 3, 8, 16, 20),
        ("down", 8, 2, 20, 24),
        ("up", 2, 7, 24, 28),
        ("down", 7, 2.5, 28, 32),
        ("up", 2.5, 8, 32, 36),
        ("down", 8, 3, 36, 40),
        ("up", 3, 9.5, 40, 44),
        ("down", 9.5, 1.5, 44, 48),
        ("up", 1.5, 12, 48, 52),
        ("down", 12, 11, 52, 56),
    ]

    # 两中枢新生, 波动区间重叠 -> expand(定理二)
    ROWS_TWO_ZS = [
        ("up", 0, 10, 0, 4),
        ("down", 10, 4, 4, 8),
        ("up", 4, 9, 8, 12),     # zs1: [4, 9]
        ("down", 9, 5, 12, 16),  # 延伸 zs1
        ("up", 5, 15, 16, 20),   # 延伸 zs1(gg -> 15)
        ("down", 15, 12, 20, 24),  # 回抽不重叠(12>9) -> zs1 完成, 向上离开
        ("up", 12, 14, 24, 28),  # zs2 窗口: [5,6,7]
        ("down", 14, 12.5, 28, 32),
        ("up", 12.5, 14.5, 32, 36),
    ]

    # 两中枢新生, 后 DD > 前 GG(跳价构造) -> up_continue(定理二)
    ROWS_UP_CONTINUE = [
        ("up", 0, 10, 0, 4),
        ("down", 10, 4, 4, 8),
        ("up", 4, 9, 8, 12),      # zs1: [4, 9], 波动区间 [0, 10]
        ("down", 9, 5, 12, 16),   # 延伸 zs1
        ("down", 12, 10.5, 16, 20),  # 跳价, 区间 [10.5, 12] 不触 [4,9]
        # -> zs1 完成, 向上离开
        ("up", 10.5, 16, 20, 24),
        ("down", 16, 13, 24, 28),
        ("up", 13, 15, 28, 32),   # zs2 窗口: [5,6,7] -> [13, 15],
        # 波动区间 [10.5, 16], DD(10.5) > 前 GG(10)
    ]

    def test_full_event_chain_with_upgrade_9(self):
        # form -> extend*5 -> upgrade_9 -> extend*4 -> complete 全链
        from chan.zs import track_zs
        xds = mk_xds(self.ROWS_EXTEND12)
        zss, events = track_zs(xds)
        kinds = [e.kind for e in events]
        self.assertEqual(
            kinds,
            ["form"] + ["extend"] * 5 + ["upgrade_9"] + ["extend"] * 4
            + ["complete"])
        # upgrade_9 恰一次, 触发段 index=8(窗口 3 段 + 延伸 6 段 = 9 段)
        ups = [e for e in events if e.kind == "upgrade_9"]
        self.assertEqual(len(ups), 1)
        self.assertEqual(ups[0].index, 8)
        self.assertEqual(ups[0].detail["xd_count"], 9)
        # 中枢本身: 与既有 find_zs 口径一致(回归锚)
        self.assertEqual(len(zss), 1)
        self.assertEqual(zss[0].zd, 4.0)
        self.assertEqual(zss[0].zg, 9.0)
        self.assertEqual(zss[0].gg, 12.0)
        self.assertEqual(zss[0].dd, 0.0)
        self.assertTrue(zss[0].extended_9)
        # complete: 末段区间 [11, 12] 在中枢上方 -> 向上离开
        self.assertEqual(events[-1].detail["leave_dir"], "up")

    def test_form_event_confirmation_timing(self):
        # form 事件的 index = 确认重叠的第三段(2), dt = 第三段 end_dt
        # (中枢在第三段完成时才"当下可知", 事件流无未来函数)
        from chan.zs import track_zs
        xds = mk_xds(self.ROWS_EXTEND12)
        _, events = track_zs(xds)
        form = events[0]
        self.assertEqual(form.kind, "form")
        self.assertEqual(form.index, 2)
        self.assertEqual(form.dt, "d12")
        self.assertEqual(form.detail["zd"], 4.0)
        self.assertEqual(form.detail["zg"], 9.0)
        self.assertEqual(form.detail["direction"], "up")

    def test_two_zs_expand_with_candidate(self):
        # 新中枢与前中枢波动区间重叠([0,15] vs [12,15]) -> expand,
        # 且携带按课 20 公式构造的高级级别中枢候选
        from chan.zs import track_zs
        xds = mk_xds(self.ROWS_TWO_ZS)
        zss, events = track_zs(xds)
        self.assertEqual(len(zss), 2)
        new_events = [e for e in events if e.kind == "new"]
        self.assertEqual(len(new_events), 1)
        new = new_events[0]
        self.assertEqual(new.detail["relation"], "expand")
        cand = new.detail["expand_zs"]
        self.assertIsNotNone(cand)
        # 连接段: 前中枢末段(index 4)之后至新中枢首段(index 5)之前为空
        # -> 取新中枢首段(离开段)区间 [12, 15] 为连接段
        # 三单元: zd = max(0, 12, 12) = 12, zg = min(15, 15, 15) = 15
        self.assertEqual(cand["zd"], 12.0)
        self.assertEqual(cand["zg"], 15.0)
        self.assertEqual(cand["gg"], 15.0)
        self.assertEqual(cand["dd"], 0.0)
        self.assertEqual(cand["direction"], "up")
        self.assertEqual(cand["xd_count"], 3)
        # 中枢边界与既有 find_zs 口径一致(回归锚)
        self.assertEqual([z.zd for z in zss], [4.0, 12.5])
        self.assertEqual([z.zg for z in zss], [9.0, 14.0])

    def test_two_zs_up_continue(self):
        # 后中枢 DD(10.5) > 前中枢 GG(10) -> 上涨及其延续, 无扩展候选
        from chan.zs import track_zs
        xds = mk_xds(self.ROWS_UP_CONTINUE)
        zss, events = track_zs(xds)
        self.assertEqual(len(zss), 2)
        self.assertEqual(zss[0].zd, 4.0)
        self.assertEqual(zss[0].zg, 9.0)
        self.assertEqual(zss[1].zd, 13.0)
        self.assertEqual(zss[1].zg, 15.0)
        new_events = [e for e in events if e.kind == "new"]
        self.assertEqual(len(new_events), 1)
        self.assertEqual(new_events[0].detail["relation"], "up_continue")
        self.assertNotIn("expand_zs", new_events[0].detail)
        # 中枢完成事件: 离开段区间 [10.5, 12] 在 [4,9] 上方 -> 向上离开
        completes = [e for e in events if e.kind == "complete"]
        self.assertEqual(len(completes), 1)
        self.assertEqual(completes[0].detail["leave_dir"], "up")

    def test_down_leave_direction(self):
        # 向下离开: 离开段区间整体在中枢下方 -> leave_dir == "down"
        # (镜像的向下离开同样需要跳价: 连续交替段中向下离开段的
        #  high 必然 >= 前延伸段终点, 会先触 [ZD,ZG] 变成延伸)
        from chan.zs import track_zs
        rows = [
            ("down", 20, 12, 0, 4),
            ("up", 12, 17, 4, 8),
            ("down", 17, 13, 8, 12),     # zs1: [13, 17], 波动 [12, 20]
            ("up", 13, 16, 12, 16),      # 延伸(xd_count=4)
            ("down", 16, 13.5, 16, 20),  # 延伸(xd_count=5)
            ("up", 13.5, 16.8, 20, 24),  # 延伸(xd_count=6)
            ("down", 9, 7.5, 24, 28),    # 跳价, 区间 [7.5, 9] 不触 [13,17]
            # -> zs1 完成, 向下离开
        ]
        xds = mk_xds(rows)
        zss, events = track_zs(xds)
        completes = [e for e in events if e.kind == "complete"]
        self.assertEqual(len(completes), 1)
        self.assertEqual(completes[0].detail["leave_dir"], "down")
        self.assertEqual(completes[0].index, 6)
        # 事件链: form(2) + extend(3,4,5) + complete(6)
        self.assertEqual([e.kind for e in events],
                         ["form", "extend", "extend", "extend", "complete"])

    def test_find_zs_equals_track_zs(self):
        # find_zs 是 track_zs 的薄包装: 三组 fixture 逐位一致
        # (ZS 未定义 __eq__, 按 to_dict 比较)
        from chan.zs import find_zs, track_zs
        for rows in (self.ROWS_EXTEND12, self.ROWS_TWO_ZS,
                     self.ROWS_UP_CONTINUE):
            xds = mk_xds(rows)
            self.assertEqual([z.to_dict() for z in find_zs(xds)],
                             [z.to_dict() for z in track_zs(xds)[0]])

    def test_short_input_empty(self):
        # 少于 3 段: 无中枢无事件
        from chan.zs import track_zs
        self.assertEqual(track_zs([]), ([], []))
        self.assertEqual(track_zs(mk_xds([("up", 0, 10, 0, 4),
                                          ("down", 10, 4, 4, 8)])),
                         ([], []))

    def test_prefix_events_consistent(self):
        # 前缀截断(当下判定): 任意前缀 k 的事件流 == 完整事件流中
        # index < k 的子列(逐段推进, 不依赖未来段)
        from chan.zs import track_zs
        xds = mk_xds(self.ROWS_TWO_ZS)
        _, full = track_zs(xds)
        for k in range(len(xds) + 1):
            _, prefix = track_zs(xds[:k])
            expected = [e for e in full if e.index < k]
            self.assertEqual(
                [(e.kind, e.index) for e in prefix],
                [(e.kind, e.index) for e in expected],
                "prefix k=%d 事件流不一致" % k)

    def test_event_index_strictly_increasing(self):
        # 事件 index 严格递增(时序单调, "当下"语义的前提)
        from chan.zs import track_zs
        for rows in (self.ROWS_EXTEND12, self.ROWS_TWO_ZS,
                     self.ROWS_UP_CONTINUE):
            _, events = track_zs(mk_xds(rows))
            idx = [e.index for e in events]
            self.assertEqual(idx, sorted(idx))
            self.assertEqual(len(idx), len(set(idx)))


if __name__ == "__main__":
    unittest.main()
