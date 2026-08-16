# -*- coding: utf-8 -*-
"""
chan.bi —— 笔的识别

理论依据: doc/缠论知识库/02-走势分解基础-分型笔线段.md §2.3

  笔: 相邻顶底分型之间的波动(其他波动忽略)。必须一顶一底交替。
  精化标准(课77/81):
    - 顶分型极值 > 底分型极值(顶必须高于底);
    - 顶最高K线与底最低K线之间(不考虑包含)至少 3 根独立K线,
      即无包含序列中两个分型中间K线的索引差 >= 4(中间隔 3 根);
    - 同向连续分型取极端者(顶取更高、底取更低)。

本模块是管线第二层: 无包含序列 + 分型 -> 笔(BI)。
成笔间隔 MIN_K_GAP 为模块级常量, 亦可经参数按标的流动性/级别微调。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple

from chan.fx import FX, NewBar, find_fxs, remove_includes

# 成笔的最小独立K线间隔数(课81: 至少3根, 即索引差 >= 4)
MIN_K_GAP = 3


class BI(object):
    """笔对象

    属性:
        direction: 'up' 向上笔 / 'down' 向下笔。
        start_dt / end_dt: 起点/终点分型的 dt。
        start_value / end_value: 起点/终点分型极值(笔的端点价格)。
        start_index / end_index: 两端分型中间K线在无包含序列中的索引
            (线段/中枢的区间计算用)。
        fx_a / fx_b: 起点/终点 FX 对象(可回溯分型的完整信息)。
        high / low: 属性, 笔区间高低点 = max/min(两端点值)。
    """

    __slots__ = ["direction", "start_dt", "end_dt", "start_value",
                 "end_value", "start_index", "end_index", "fx_a", "fx_b"]

    def __init__(self, direction: str, fx_a: FX, fx_b: FX,
                 start_index: int, end_index: int):
        self.direction = direction      # 'up' 向上笔 / 'down' 向下笔
        self.fx_a = fx_a                # 起点分型
        self.fx_b = fx_b                # 终点分型
        self.start_dt = fx_a.dt
        self.end_dt = fx_b.dt
        self.start_value = fx_a.value
        self.end_value = fx_b.value
        self.start_index = start_index  # 无包含序列索引(起点分型中间K线)
        self.end_index = end_index      # 无包含序列索引(终点分型中间K线)

    @property
    def high(self) -> float:
        """笔区间高点(中枢重叠计算用)"""
        return max(self.start_value, self.end_value)

    @property
    def low(self) -> float:
        """笔区间低点(中枢重叠计算用)"""
        return min(self.start_value, self.end_value)

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"direction": self.direction,
                "start_dt": str(self.start_dt), "end_dt": str(self.end_dt),
                "start": self.start_value, "end": self.end_value,
                "high": self.high, "low": self.low,
                "start_index": self.start_index, "end_index": self.end_index}


def find_bis(new_bars: List[NewBar],
             fxs: Optional[List[FX]] = None,
             min_k_gap: int = MIN_K_GAP) -> List[BI]:
    """识别笔

    参数:
        new_bars: remove_includes 的输出(无包含K线序列)。
        fxs: 分型列表; None = 用 find_fxs(new_bars) 现算。
        min_k_gap: 成笔的最小独立K线间隔数(课81 标准为 3)。
            调小(如 2)会得到更灵敏、数量更多的笔, 调大则笔更稳健;
            仅用于不同级别/流动性的适配, 默认即标准。

    返回:
        list of BI, 按时间顺序, 顶底交替。

    规则要点:
        - 反向分型满足成笔条件(中间独立K线数 >= min_k_gap 且
          顶高于底 / 底低于顶) -> 确认新笔, last 指针移到该分型;
        - 同向分型取极端(顶取更高、底取更低): 替换 last 指针, 同时
          **更新最后一笔的终点**(若该分型是最后一笔终点)——
          顶分型后未出有效底分型而继续新高, 上一笔终点应随新顶延伸;
          反之新低同理;
        - 反向分型不满足成笔条件 -> 忽略该分型, 继续向后找。
    """
    if fxs is None:
        fxs = find_fxs(new_bars)
    if len(fxs) < 2:
        return []

    bis = []
    last = fxs[0]
    for fx in fxs[1:]:
        if fx.kind == last.kind:
            # 同向分型取极端: 顶取更高, 底取更低
            if fx.kind == "top":
                better = fx.high > last.high
            else:
                better = fx.low < last.low
            if better:
                old = last
                last = fx
                # 若 last 是最后一笔的终点分型, 同步延伸该笔终点
                if bis and bis[-1].fx_b is old:
                    b = bis[-1]
                    b.fx_b = fx
                    b.end_dt = fx.dt
                    b.end_value = fx.value
                    b.end_index = fx.bar_index
            continue
        # 反向分型: 检查成笔条件
        gap = abs(fx.bar_index - last.bar_index) - 1  # 中间独立K线数
        if last.kind == "top":
            cond_value = last.high > fx.low
            direction = "down"
        else:
            cond_value = fx.high > last.low
            direction = "up"
        if gap >= min_k_gap and cond_value:
            a, b = (last, fx) if last.bar_index < fx.bar_index else (fx, last)
            bis.append(BI(direction, a, b,
                          min(last.bar_index, fx.bar_index),
                          max(last.bar_index, fx.bar_index)))
            last = fx
        # 不满足成笔条件: 忽略该分型, 继续向后找
    return bis


def chan_fx_bi(bars: List[Dict[str, Any]],
               min_k_gap: int = MIN_K_GAP) -> Tuple[List[NewBar], List[FX], List[BI]]:
    """完整入口: 原始 bars -> (无包含序列, 分型列表, 笔列表)

    参数:
        bars: 标准 bar 列表(chan.bars.normalize_bars 产出)。
        min_k_gap: 透传给 find_bis 的成笔间隔(默认 MIN_K_GAP=3)。

    返回:
        三元组 (new_bars, fxs, bis):
            new_bars: 包含处理后的无包含K线序列;
            fxs: 分型列表;
            bis: 笔列表(按时间顺序)。
    """
    new_bars = remove_includes(bars)
    fxs = find_fxs(new_bars)
    bis = find_bis(new_bars, fxs, min_k_gap=min_k_gap)
    return new_bars, fxs, bis
