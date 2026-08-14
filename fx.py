# -*- coding: utf-8 -*-
"""
chan.fx —— K线包含关系处理与分型识别

理论依据: doc/缠论知识库/02-走势分解基础-分型笔线段.md

  1. 包含关系: 相邻两K线, 一K线高低点全在另一K线范围内。
     - 向上处理(后K线高点 >= 前K线高点): 新K线 = [max(高), max(低)]
     - 向下处理(后K线低点 <= 前K线低点): 新K线 = [min(低), min(高)]
     - 顺序原则: 依次两两处理, 包含关系不满足传递律。
  2. 分型: 无包含的三相邻K线
     - 顶分型: 中间K线高点是三者最高, 低点也是三者最高
     - 底分型: 中间K线低点是三者最低, 高点也是三者最低

兼容: Python 3.6, 仅用 numpy/pandas 基础能力。
"""

from __future__ import print_function


class NewBar(object):
    """包含处理后的合并K线"""

    __slots__ = ["dt", "open", "high", "low", "close", "volume", "elements"]

    def __init__(self, dt, open_, high, low, close, volume, elements=None):
        self.dt = dt
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.elements = elements if elements is not None else []  # 原始bar索引

    def to_dict(self):
        return {"dt": self.dt, "open": self.open, "high": self.high,
                "low": self.low, "close": self.close, "volume": self.volume,
                "elements": list(self.elements)}


def remove_includes(bars):
    """包含关系处理 -> 无包含的 NewBar 列表(顺序原则)

    bars: list of dict, 每项含 open/high/low/close/volume/dt(由 bars.normalize_bars 产出)
    """
    if not bars:
        return []
    if len(bars) == 1:
        b = bars[0]
        return [NewBar(b["dt"], b["open"], b["high"], b["low"], b["close"],
                       b["volume"], [0])]

    out = []
    b0 = bars[0]
    out.append(NewBar(b0["dt"], b0["open"], b0["high"], b0["low"],
                      b0["close"], b0["volume"], [0]))
    for i in range(1, len(bars)):
        b = bars[i]
        last = out[-1]
        # 判断包含关系: 一K线高低点全在另一K线范围内
        a_contains_b = (last.high >= b["high"] and last.low <= b["low"])
        b_contains_a = (b["high"] >= last.high and b["low"] <= last.low)
        if not (a_contains_b or b_contains_a):
            # 无包含, 直接追加
            out.append(NewBar(b["dt"], b["open"], b["high"], b["low"],
                              b["close"], b["volume"], [i]))
            continue
        # 有包含, 按方向合并
        if len(out) >= 2:
            prev = out[-2]
            direction_up = (last.high >= prev.high)
        else:
            # 只有一根合并K线时, 用后K线与前K线高点比
            direction_up = (b["high"] >= last.high)
        if direction_up:
            new_high = max(last.high, b["high"])
            new_low = max(last.low, b["low"])
        else:
            new_high = min(last.high, b["high"])
            new_low = min(last.low, b["low"])
        # 合并K线的 open/close: 取首根open、末根close(近似; 形态学只用高低点)
        new_open = last.open
        new_close = b["close"]
        new_vol = last.volume + b["volume"]
        new_elems = last.elements + [i]
        out[-1] = NewBar(b["dt"], new_open, new_high, new_low, new_close,
                         new_vol, new_elems)
    return out


class FX(object):
    """分型对象"""

    __slots__ = ["kind", "dt", "high", "low", "bar_index", "elements"]

    def __init__(self, kind, dt, high, low, bar_index, elements):
        self.kind = kind        # 'top' 顶 / 'bottom' 底
        self.dt = dt            # 分型中间K线时间
        self.high = high        # 顶分型: 顶; 底分型: 分型区间高点
        self.low = low          # 底分型: 底; 顶分型: 分型区间低点
        self.bar_index = bar_index   # 中间K线在无包含序列中的索引
        self.elements = elements     # 对应原始bars索引(三根)

    @property
    def value(self):
        """分型的极值(顶或底)"""
        return self.high if self.kind == "top" else self.low

    def to_dict(self):
        return {"kind": self.kind, "dt": str(self.dt), "high": self.high,
                "low": self.low, "bar_index": self.bar_index,
                "elements": list(self.elements), "value": self.value}


def find_fxs(new_bars):
    """在无包含序列中识别全部顶/底分型

    new_bars: remove_includes 的输出
    返回: list of FX
    """
    fxs = []
    n = len(new_bars)
    if n < 3:
        return fxs
    for i in range(1, n - 1):
        a, b, c = new_bars[i - 1], new_bars[i], new_bars[i + 1]
        # 顶分型: b 的高点是三者最高, 低点也是三者最高
        if b.high > a.high and b.high > c.high and b.low > a.low and b.low > c.low:
            elems = a.elements + b.elements + c.elements
            fxs.append(FX("top", b.dt, b.high, min(a.low, b.low, c.low), i, elems))
        # 底分型: b 的低点是三者最低, 高点也是三者最低
        elif b.low < a.low and b.low < c.low and b.high < a.high and b.high < c.high:
            elems = a.elements + b.elements + c.elements
            fxs.append(FX("bottom", b.dt, max(a.high, b.high, c.high), b.low, i, elems))
    return fxs
