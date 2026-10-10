# -*- coding: utf-8 -*-
"""内部价格区间运算, 供同级分解、级别递归与中阴状态机共用。

只计算课 20/35/38 使用的闭区间交集, 不决定走势何时完成或中枢
是否延伸。各状态机保留自身理论口径; 端点触及统一算重叠。
输入单元只需具有 low/high 属性, 不依赖笔、线段或走势类型类。
"""

from typing import Any, List, Optional, Tuple


def _range3(units: List[Any], start: int) -> Tuple[float, float]:
    """三连续单元的交集边界 (最大低点, 最小高点)。

    调用方保证 start..start+2 存在; 下沿大于上沿表示无共同交集。
    """
    a, b, c = units[start], units[start + 1], units[start + 2]
    return max(a.low, b.low, c.low), min(a.high, b.high, c.high)


def _overlap3(units: List[Any], start: int) -> bool:
    """课 35/38 三连续单元是否共同重叠, 含单点交集。"""
    zd, zg = _range3(units, start)
    return zd <= zg  # 闭区间端点相等仍有交集。


def _overlap_center(unit: Any, center: Tuple[float, float]) -> bool:
    """课 20 单元与中枢 [ZD,ZG] 是否重叠, 含端点触及。"""
    return not (unit.high < center[0] or unit.low > center[1])


def _find_center(units: List[Any], start: int) -> Optional[int]:
    """从 start 找最早三单元重叠组; 空输入或不足三单元返回 None。"""
    for index in range(start, len(units) - 2):
        if _overlap3(units, index):
            return index
    return None
