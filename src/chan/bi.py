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

可选课106标准(2008-07-10及08-14解盘):
  「必须至少延伸6个基本K线单位」「如果5日线都不能碰到,
  那就不会是笔的反弹了」「如果抛去包含关系,6根K线就可以构成笔」。
  实现选无包含序列中完整两个三K分型的跨度: 端点索引差+3>=6,
  因此中间至少2根; 仍要求顶底交替、顶高于底。向上笔在端点时间区间
  内至少一次 high>=MA5, 向下镜像 low<=MA5, 触及即满足必要辅助条件。
  这不是'有效站稳'确认, 也不将均线条件当成充分成笔条件。默认仍为
  课81标准; 不根据行情自动切换标准。MA5由原始K线收盘计算, 包含组
  按最后原始bar下标对齐, 不用合并后的序列重新定义5个原始周期。

兼容: Python 3.6。
"""

from __future__ import print_function

import math
from numbers import Integral, Real
from typing import Any, Dict, List, Optional, Tuple

from chan.fx import FX, NewBar, find_fxs, remove_includes

# 成笔的最小独立K线间隔数(课81: 至少3根, 即索引差 >= 4)
MIN_K_GAP = 3
BI_STANDARD_81 = "81"
BI_STANDARD_106 = "106"


def _bi_inputs(new_bars, min_k_gap, standard, ma5):
    """两套规则显式选择, 不允许缺失均线静默退回课81。"""
    if standard not in (BI_STANDARD_81, BI_STANDARD_106):
        raise ValueError("standard 须为 '81' 或 '106'")
    if min_k_gap is None:
        min_k_gap = MIN_K_GAP if standard == BI_STANDARD_81 else 2
    if isinstance(min_k_gap, bool) or not isinstance(min_k_gap, Integral) or min_k_gap < 0:
        raise ValueError("min_k_gap 须为非负整数或 None")
    if standard == BI_STANDARD_106:
        if ma5 is None or len(ma5) != len(new_bars):
            raise ValueError("课106须传入与 new_bars 等长的原始MA5对齐序列")
        for value in ma5:
            if value is not None and (isinstance(value, bool) or not isinstance(value, Real)):
                raise ValueError("ma5 须为数值或 None")
    return min_k_gap


def _touch_ma5(new_bars, ma5, start, end, direction):
    """课106至少碰5均线: 端点区间内的方向性触及, 不借用确认邻K。"""
    for index in range(start, end + 1):
        value = ma5[index]
        # 暖机/缺测没有均线证据; 不填值也不从未来反向补齐。
        if value is None or not math.isfinite(value):
            continue
        if direction == "up" and new_bars[index].high >= value:
            return True
        if direction == "down" and new_bars[index].low <= value:
            return True
    return False


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
             min_k_gap: Optional[int] = None,
             standard: str = BI_STANDARD_81,
             ma5: Optional[List[Optional[float]]] = None) -> List[BI]:
    """识别笔

    参数:
        new_bars: remove_includes 的输出(无包含K线序列)。
        fxs: 分型列表; None = 用 find_fxs(new_bars) 现算。
        min_k_gap: 成笔的最小独立K线间隔数; None按标准选择(81为3,
            106为2)。显式参数可额外限制间隔, 106始终保留六K必要条件。
            调小(如 2)会得到更灵敏、数量更多的笔, 调大则笔更稳健;
            仅用于不同级别/流动性的适配, 默认即标准。
        standard: '81'(默认精化标准) / '106'(可选六K+MA5辅助标准)。
        ma5: 仅106需要, 与new_bars等长, 每个包含组按其最后原始K线
            对齐原始5周期均线。None/NaN/inf按缺测; 缺整个序列报错。

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
    min_k_gap = _bi_inputs(new_bars, min_k_gap, standard, ma5)
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
        standard_ok = True
        if standard == BI_STANDARD_106:
            start, end = sorted((last.bar_index, fx.bar_index))
            # 两个完整三K分型不共用K线: j-i+3>=6; 邻K须已在前缀中。
            standard_ok = (start >= 1 and end + 1 < len(new_bars) and end - start >= 3)
            if standard_ok:
                standard_ok = _touch_ma5(new_bars, ma5, start, end, direction)
        if gap >= min_k_gap and cond_value and standard_ok:
            a, b = (last, fx) if last.bar_index < fx.bar_index else (fx, last)
            bis.append(BI(direction, a, b,
                          min(last.bar_index, fx.bar_index),
                          max(last.bar_index, fx.bar_index)))
            last = fx
        # 不满足成笔条件: 忽略该分型, 继续向后找
    return bis


def chan_fx_bi(bars: List[Dict[str, Any]],
               min_k_gap: Optional[int] = None,
               standard: str = BI_STANDARD_81) -> Tuple[List[NewBar], List[FX], List[BI]]:
    """完整入口: 原始 bars -> (无包含序列, 分型列表, 笔列表)

    参数:
        bars: 标准 bar 列表(chan.bars.normalize_bars 产出)。
        min_k_gap: 透传给 find_bis; 默认81为3, 106为2。
        standard: '81' / '106', 后者自动用原始收盘计算并对齐MA5。

    返回:
        三元组 (new_bars, fxs, bis):
            new_bars: 包含处理后的无包含K线序列;
            fxs: 分型列表;
            bis: 笔列表(按时间顺序)。
    """
    new_bars = remove_includes(bars)
    fxs = find_fxs(new_bars)
    ma5 = None
    if standard == BI_STANDARD_106:
        from chan.strength import sma_series
        raw_ma5 = sma_series([bar["close"] for bar in bars], 5)
        ma5 = [raw_ma5[bar.elements[-1]] for bar in new_bars]
    bis = find_bis(new_bars, fxs, min_k_gap=min_k_gap, standard=standard, ma5=ma5)
    return new_bars, fxs, bis
