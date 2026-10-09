# -*- coding: utf-8 -*-
"""走势的多级唯一分解——记数法(课 102)

课 102「再说走势必完美」的理论内核:
    "本 ID 的理论给出的递归函数, 完美地给出市场走势一个类似记数法
    一样的唯一分解"——任何走势都可以唯一地表示为
        a1A1 + a5A5 + a30A30
    的形式, 即各级别走势(类型)的加和式; 级别依次升大, 从 1 分钟到
    年对应 8 个级别("级别的名字是可以随意取的"), 加上线段与笔可以
    有更精细的分解。完全分类是级别性的、有明确点位界限的。

    级别的必然结论(本模块以 change_starts_low 落为可执行校验):
    "任何高级别的改变都必须先从低级别开始。例如, 绝对不可能出现
    5 分钟从下跌转折为上涨, 而 1 分钟还在下跌段中。"

本模块在 recurse.level_up(递归函数 f2)之上提供:
    - decompose_levels: 自最低级别单元(笔/线段/走势类型)出发一次性
      逐级上推, 输出各级分解(LevelDecomposition 列表);
    - level_reading: 给定多级分解与任意时点, 读出各级别当前走势
      (记数法的"读数");
    - change_starts_low: 校验高级别方向切换必先从低级别开始
      (结构自洽性校验——真实递归分解天然满足, 用于校验调用方
      自行拼接/裁剪的分解)。
"""

from typing import Any, Dict, List, Optional

from chan.decompose import MoveType
from chan.recurse import level_up

__all__ = [
    "LevelDecomposition",
    "decompose_levels",
    "level_reading",
    "change_starts_low",
]

#: 课 102: "从 1 分钟一直到年, 对应着 8 个级别"——默认最多上推 8 级。
MAX_LEVELS_DEFAULT = 8

#: 上推一级至少需要 3 个连续单元(高一级别中枢 = 三单元重叠)。
MIN_UNITS_FOR_NEXT = 3


class LevelDecomposition(object):
    """一个级别的分解结果

    属性:
        level: 级别序号, 1 = 输入单元级(笔/线段等配件或最低级别
            走势类型), 2 = level_up 一次后的高一级别, 依此类推。
        moves: 该级别的走势类型序列(List[MoveType]; 第 1 级输入
            若为笔/线段则原样保存——课 91 二分: 笔是不构成中枢的
            "配件", 但作为记数法的最低位参与分解)。
    """

    __slots__ = ["level", "moves"]

    def __init__(self, level: int, moves: List[Any]):
        self.level = level
        self.moves = moves

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用)"""
        return {
            "level": self.level,
            "count": len(self.moves),
            "moves": [m.to_dict() if isinstance(m, MoveType) else str(m)
                      for m in self.moves],
        }


def decompose_levels(units: List[Any],
                     max_levels: int = MAX_LEVELS_DEFAULT
                     ) -> List[LevelDecomposition]:
    """多级唯一分解: 自 units 起逐级上推(课 102 记数法)

    参数:
        units: 最低级别单元序列(笔/线段/XD/MoveType, 具备
            direction / start_dt / end_dt / high / low 即可)。
        max_levels: 最多分解到第几级(含第 1 级), 默认 8
            (课 102: 1 分钟到年共 8 个级别)。

    返回:
        List[LevelDecomposition], 第 1 项为输入单元级, 之后每级为
        level_up 上推一级的结果。停止条件:
        - 某级走势类型数 < 3(再上推无中枢可言);
        - 某级上推后与上级数量相同(无聚合, 防御性终止);
        - 达到 max_levels;
        - 上推结果为空。

    唯一性: 完全由 recurse.level_up 的无未来函数递归保证——同输入
        下各级分解唯一, 任意前缀的已确认项在更长前缀下不变。
    """
    out: List[LevelDecomposition] = []
    if not units:
        return out
    out.append(LevelDecomposition(1, list(units)))
    while len(out) < max_levels:
        cur = out[-1].moves
        if len(cur) < MIN_UNITS_FOR_NEXT:
            break
        nxt = level_up(cur)
        if not nxt:
            break
        if len(nxt) == len(cur):
            # 无聚合(理论上 f2 必聚合, 防御第三方单元输入)
            break
        out.append(LevelDecomposition(out[-1].level + 1, nxt))
    return out


def level_reading(levels: List[LevelDecomposition],
                  at_dt: Any) -> List[Optional[str]]:
    """记数法读数: 时点 at_dt 处各级别的当前走势类型

    参数:
        levels: decompose_levels 的输出(或手工构造的同构列表)。
        at_dt: 读数时点(与各级 start_dt/end_dt 同类型可比)。

    返回:
        List[Optional[str]], 第 k 项 = 第 k 级在 at_dt 当下的走势
        kind('up'/'down'/'consolidation'/'incomplete'); 该级无
        覆盖 at_dt 的走势(时点在首段之前/末段之后的缝隙)时为 None。

    语义: 覆盖判断 = start_dt <= at_dt <= end_dt(端点触及算覆盖)。
    """
    reading: List[Optional[str]] = []
    for ld in levels:
        found: Optional[str] = None
        for m in ld.moves:
            if m is None:
                continue
            try:
                if m.start_dt <= at_dt <= m.end_dt:
                    found = m.kind if isinstance(m, MoveType) else \
                        getattr(m, "kind", None)
                    break
            except TypeError:
                # dt 类型不可比: 无法判定
                found = None
                break
        reading.append(found)
    return reading


def change_starts_low(low_moves: List[Any],
                      high_moves: List[Any]) -> Optional[bool]:
    """校验(课 102 必然结论): 高级别的改变必先从低级别开始

    "任何高级别的改变都必须先从低级别开始。例如, 绝对不可能出现
    5 分钟从下跌转折为上涨, 而 1 分钟还在下跌段中。"

    参数:
        low_moves: 低级别走势类型(或单元)序列。
        high_moves: 高级别走势类型序列(其 seg_start/seg_end 为
            低级别序列的索引区间——level_up 输出天然如此; 第三方
            拼接的序列若无索引信息则退化为按 dt 覆盖判断)。

    返回:
        True: high_moves 中每个方向切换处, 低级别在切换起点
            (含)已存在与新方向同向的段——先行成立;
        False: 存在违背(高级别转了向而低级别仍在旧方向, 结构
            不自洽);
        None: 输入不足以判定(空序列/无切换点/dt 不可比)。
    """
    if not low_moves or not high_moves:
        return None
    checked = False
    for i in range(len(high_moves) - 1):
        h_prev = high_moves[i]
        h_next = high_moves[i + 1]
        d_prev = getattr(h_prev, "direction", None)
        d_next = getattr(h_next, "direction", None)
        if d_prev is None or d_next is None or d_prev == d_next:
            # 无进入段方向或未切换: 非切换点
            continue
        checked = True
        # 优先用索引区间: 高级别新走势的进入段起点
        seg_start = getattr(h_next, "seg_start", None)
        hit = False
        if seg_start is not None and 0 <= seg_start < len(low_moves):
            seg_end = getattr(h_next, "seg_end", seg_start)
            for j in range(seg_start, min(seg_end + 1, len(low_moves))):
                if getattr(low_moves[j], "direction", None) == d_next:
                    hit = True
                    break
            if not hit and seg_start < len(low_moves) and \
                    getattr(low_moves[seg_start], "direction", None) is None:
                # 进入段单元无方向属性(配件级): 该单元不构成反证
                hit = True
        else:
            # 退化为 dt 覆盖: 切换时点低级别已在新方向段中
            t = getattr(h_next, "start_dt", None)
            if t is None:
                return None
            try:
                for m in low_moves:
                    if m.start_dt <= t <= m.end_dt and \
                            getattr(m, "direction", None) == d_next:
                        hit = True
                        break
            except TypeError:
                return None
        if not hit:
            return False
    return True if checked else None
