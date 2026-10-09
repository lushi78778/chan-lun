# -*- coding: utf-8 -*-
"""中枢震荡监视器(课 92)

课 92 原文要点(理论部分, 解盘部分不编码):
    "一个中枢确立后, 中枢区间的一半位置, 称为震荡中轴 Z。而每一个
    次级震荡区间的一半位置, 依次用 Zn 表示"
    "Zn 在 Z 之上, 证明这个震荡是偏强的, 反之偏弱。震荡的中枢区间
    是 [A, B], 那么, A、Z、B 这三条直线刚好是等距的, Zn 的波动连成
    曲线, 构成一个监视中枢震荡的技术指标。"
    "存在着一种必然的关系, 就是最终, Zn 肯定要超越 A 或 B ...
    如果不这样, 就永远不会出现第三类买卖点了"
    "反过来, Zn 超越 A 或 B 并不意味着一定要出现第三类买卖点 ...
    这种超越可以是多次的, 只有最后一次才构成第三类买卖点 ...
    一般一旦有这类似的超越, 就是一个很大的提醒, 也就是这震荡面临
    变盘了。"
    "如果这超越没有构成第三类买卖点, 那么一般都将构成中枢震荡级别
    的扩展, 这没有 100% 的绝对性, 但概率是极为高的。"
    "Zn 的数量不会过于庞大, 不会超过 9 个数据, 超过了, 次级别就要
    升级了"
    "那些 Zn 缓慢提高, 但又没力量突破 B 的, 要小心其中蕴藏的突然
    变盘风险, 一般这种走势, 都会构成所谓的上升楔型之类的诱多图形。
    这种情况, 反着, 同样存在下降楔型的诱空"
    "中枢震荡中次级别的类型其实是很重要的, 如果是一个趋势类型,
    Zn 又出现相应的配合, 那么一定要注意变盘的发生, 特别那种最后
    一个次级别中枢在中枢之外的, 一旦下一个次级别走势在该次级别
    中枢区间完成, 震荡就会出现变盘。"
    "Zn 的变动都是相对平滑的, 因此, 可以大致预计其下一个的区间,
    这样, 当下震荡的低点或高点, 就可以大致算出下一个震荡的高低点"

本模块提供:
    - oscillation_monitor(center, units): 中枢震荡监视报告
      (Zn 序列/强弱偏移/超越事件/升级提示/楔型诱多诱空/次级别
      趋势类型与中枢外配合)
    - zn_next_estimate: Zn 平滑线性外推 + 近期平均半振幅, 估计
      下一个次级震荡的高低点(课 92"小学数学")

时间把握配合布林通道收口提示(课 90), 见 chan.zhongyin.boll_events。
"""

from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "OscReport",
    "oscillation_monitor",
    "zn_next_estimate",
    "osc_strength",
]

# Zn 数量达 9 即次级别升级提示(课 92/20/69 口径一致)
OSC_UPGRADE_N = 9

# 楔型判定的最少单调 Zn 个数(含自身)
WEDGE_MIN_RUN = 4


class OscReport(object):
    """中枢震荡监视报告(纯数据)

    字段:
        center    -- (A, B) = (zd, zg) 被监视中枢区间
        z         -- 震荡中轴 Z = (A+B)/2
        zns       -- [(unit_idx, zn)] 次级震荡中轴序列(每单元区间
                     的一半位置)
        positions -- 每个 Zn 的位置标签: "above_B"(>B 超越) /
                     "below_A"(<A 超越) / "above_Z"(Z..B 偏强) /
                     "below_Z"(A..Z 偏弱)
        n_above_z / n_below_z -- Zn 在 Z 上/下的个数(强弱统计)
        breaks    -- [(unit_idx, "break_up"/"break_down")] Zn 超越
                     A/B 事件(课 92: 很大的提醒, 震荡面临变盘;
                     可多次, 只有最后一次才构成第三类买卖点)
        status    -- "empty" 无单元 / "in_range" 全部 Zn 未超越
                     (课 92 必然关系: Zn 终须超越 A 或 B, 否则
                     永无第三类买卖点) / "breaking" 已有超越
        upgrade_hint -- Zn 数达 9, 次级别将升级
        wedge     -- "rising_wedge": Zn 持续抬升但从未超越 B
                     (上升楔型诱多, 突然变盘风险); "falling_wedge"
                     镜像(下降楔型诱空); None 无
        trend_unit_idx -- 次级别为趋势类型(走势类型 kind=up/down)
                     的单元索引(课 92: 趋势类型 + Zn 配合 = 变盘
                     注意); XD 输入无 kind 不判
        outer_center_unit_idx -- 最后一个次级别中枢整体在被监视
                     中枢区间之外的单元索引(课 92: 一旦下一个
                     次级别走势在该次级别中枢区间完成, 震荡就会
                     变盘)
    """

    def __init__(self, center, z, zns, positions, n_above_z, n_below_z,
                 breaks, status, upgrade_hint, wedge, trend_unit_idx,
                 outer_center_unit_idx):
        # type: (Tuple[float, float], float, List[Tuple[int, float]], List[str], int, int, List[Tuple[int, str]], str, bool, Optional[str], List[int], List[int]) -> None
        self.center = center
        self.z = z
        self.zns = zns
        self.positions = positions
        self.n_above_z = n_above_z
        self.n_below_z = n_below_z
        self.breaks = breaks
        self.status = status
        self.upgrade_hint = upgrade_hint
        self.wedge = wedge
        self.trend_unit_idx = trend_unit_idx
        self.outer_center_unit_idx = outer_center_unit_idx

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "center": self.center,
            "z": self.z,
            "zns": list(self.zns),
            "positions": list(self.positions),
            "n_above_z": self.n_above_z,
            "n_below_z": self.n_below_z,
            "breaks": list(self.breaks),
            "status": self.status,
            "upgrade_hint": self.upgrade_hint,
            "wedge": self.wedge,
            "trend_unit_idx": list(self.trend_unit_idx),
            "outer_center_unit_idx": list(self.outer_center_unit_idx),
        }


def _zn_of(unit):
    # type: (Any) -> float
    """次级震荡区间的一半位置 Zn = (low+high)/2(课 92)"""
    return (unit.low + unit.high) / 2.0


def osc_strength(report):
    # type: (OscReport) -> str
    """强弱结论: Zn 在 Z 上/下的占比(课 92 偏强/偏弱)"""
    n = len(report.zns)
    if n == 0:
        return "empty"
    if report.n_above_z * 2 > n:
        return "strong"
    if report.n_below_z * 2 > n:
        return "weak"
    return "balanced"


def oscillation_monitor(center, units):
    # type: (Tuple[float, float], List[Any]) -> OscReport
    """中枢震荡监视器(课 92)

    参数:
        center -- (A, B) = (zd, zg) 已确立中枢区间
        units  -- 中枢震荡中的次级别单元序列(线段 XD 或次级别走势
                  类型 MoveType), 只需 low/high; 带 kind 属性时
                  额外判趋势类型配合, 带 centers 属性时额外判
                  末中枢在中枢之外。

    输出口径见 OscReport; 原文"超越不构成三买三卖则大概率级别
    扩展"由调用方结合 chan.zs 升级事件确认, 本报告只给提示。
    """
    a, b = float(center[0]), float(center[1])
    z = (a + b) / 2.0
    zns = []  # type: List[Tuple[int, float]]
    positions = []  # type: List[str]
    breaks = []  # type: List[Tuple[int, str]]
    n_above_z = 0
    n_below_z = 0
    trend_unit_idx = []  # type: List[int]
    outer_center_unit_idx = []  # type: List[int]

    for i, u in enumerate(units):
        zn = _zn_of(u)
        zns.append((i, zn))
        if zn > b:
            positions.append("above_B")
            breaks.append((i, "break_up"))
        elif zn < a:
            positions.append("below_A")
            breaks.append((i, "break_down"))
        elif zn >= z:
            positions.append("above_Z")
            n_above_z += 1
        else:
            positions.append("below_Z")
            n_below_z += 1
        # 次级别类型配合: 趋势类型(走势类型口径)
        kind = getattr(u, "kind", None)
        if kind in ("up", "down"):
            trend_unit_idx.append(i)
        # 末次级别中枢整体在被监视中枢之外(课 92 变盘强征兆)
        centers = getattr(u, "centers", None)
        if centers:
            zd2, zg2 = centers[-1]
            if zg2 < a or zd2 > b:
                outer_center_unit_idx.append(i)

    if not zns:
        status = "empty"
    elif breaks:
        status = "breaking"
    else:
        status = "in_range"

    # 楔型: 最近 WEDGE_MIN_RUN 个 Zn 单调且全程未超越(课 92 诱多/诱空)
    wedge = None  # type: Optional[str]
    if len(zns) >= WEDGE_MIN_RUN:
        vals = [zn for _, zn in zns]
        diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
        if all(d > 0 for d in diffs) and max(vals) <= b:
            wedge = "rising_wedge"   # 缓慢抬升无力破 B: 诱多
        elif all(d < 0 for d in diffs) and min(vals) >= a:
            wedge = "falling_wedge"  # 镜像: 诱空

    return OscReport(
        center=(a, b), z=z, zns=zns, positions=positions,
        n_above_z=n_above_z, n_below_z=n_below_z, breaks=breaks,
        status=status, upgrade_hint=len(zns) >= OSC_UPGRADE_N,
        wedge=wedge, trend_unit_idx=trend_unit_idx,
        outer_center_unit_idx=outer_center_unit_idx)


def zn_next_estimate(units, m=4):
    # type: (List[Any], int) -> Optional[Tuple[float, float]]
    """估计下一个次级震荡的高低点区间(课 92"小学数学")

    Zn 变动相对平滑 -> 用最近 m 个 Zn 线性外推下一个 Zn;
    次级震荡区间的一半位置 = 近 m 个单元的平均半振幅 ->
    下一个震荡高低点估计区间 = (Zn_next - avg_half, Zn_next +
    avg_half)。单元不足 2 个返回 None; m 不足时用全部。
    """
    n = len(units)
    if n < 2:
        return None
    k = min(m, n)
    zns = [_zn_of(u) for u in units]
    recent = zns[n - k:]
    if k >= 2:
        slope = (recent[-1] - recent[0]) / float(k - 1)
    else:
        slope = 0.0
    zn_next = recent[-1] + slope
    half = sum((u.high - u.low) / 2.0 for u in units[n - k:]) / float(k)
    return (zn_next - half, zn_next + half)
