# -*- coding: utf-8 -*-
"""
chan.bi —— 笔的识别

理论依据: doc/缠论知识库/02-走势分解基础-分型笔线段.md §2.3

  笔: 相邻顶底分型之间的波动(其他波动忽略)。必须一顶一底交替。
  精化标准(课77/81):
    - 顶分型极值 > 底分型极值(顶必须高于底);
    - 顶最高K线与底最低K线之间(不考虑包含)至少 3 根独立K线,
      即无包含序列中两个分型中间K线的索引差 >= 4;
    - 同向连续分型取极端者(顶取更高、底取更低)。

兼容: Python 3.6。
"""

from __future__ import print_function

from chan.fx import remove_includes, find_fxs

# 成笔的最小独立K线间隔数(课81: 至少3根)
MIN_K_GAP = 3


class BI(object):
    """笔对象"""

    __slots__ = ["direction", "start_dt", "end_dt", "start_value",
                 "end_value", "start_index", "end_index", "fx_a", "fx_b"]

    def __init__(self, direction, fx_a, fx_b, start_index, end_index):
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
    def high(self):
        return max(self.start_value, self.end_value)

    @property
    def low(self):
        return min(self.start_value, self.end_value)

    def to_dict(self):
        return {"direction": self.direction,
                "start_dt": str(self.start_dt), "end_dt": str(self.end_dt),
                "start": self.start_value, "end": self.end_value,
                "high": self.high, "low": self.low,
                "start_index": self.start_index, "end_index": self.end_index}


def find_bis(new_bars, fxs=None):
    """识别笔

    参数:
        new_bars: remove_includes 的输出(无包含K线序列)
        fxs: 分型列表(默认用 find_fxs 计算)

    返回: list of BI(按时间顺序)

    规则要点:
        - 反向分型满足成笔条件(间隔>=3根独立K线 且 顶高于底) -> 新笔;
        - 同向分型取极端(顶取更高、底取更低): 替换 last 指针, 同时
          **更新最后一笔的终点**(若 last 是最后一笔终点)——
          顶分型后未出有效底分型而继续新高, 上一笔终点应随新顶延伸;
        - 反向分型不满足成笔条件 -> 忽略, 继续向后。
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
        if gap >= MIN_K_GAP and cond_value:
            a, b = (last, fx) if last.bar_index < fx.bar_index else (fx, last)
            bis.append(BI(direction, a, b,
                          min(last.bar_index, fx.bar_index),
                          max(last.bar_index, fx.bar_index)))
            last = fx
        # 不满足成笔条件: 忽略该分型, 继续向后找
    return bis


def chan_fx_bi(bars):
    """完整入口: 原始bars -> (无包含序列, 分型列表, 笔列表)"""
    new_bars = remove_includes(bars)
    fxs = find_fxs(new_bars)
    bis = find_bis(new_bars, fxs)
    return new_bars, fxs, bis
