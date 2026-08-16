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

本模块是整条管线的第一层: 原始 bars -> 无包含序列(NewBar) -> 分型(FX),
后续的笔(chan.bi)在无包含序列与分型之上构建。

兼容: Python 3.6, 仅用 numpy/pandas 基础能力。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional


class NewBar(object):
    """包含处理后的合并K线

    属性:
        dt: 合并后K线的时间(取参与合并K线中最后一根的 dt)。
        open / high / low / close / volume: 合并后的 OHLCV。
            open 取合并组首根 open, close 取末根 close(近似),
            形态学判定只用 high/low;
            volume 为合并组 volume 之和。
        elements: list of int, 参与合并的原始 bar 索引(在原始 bars 中的下标),
            用于回溯"这根合并K线由哪几根原始K线组成"。
    """

    __slots__ = ["dt", "open", "high", "low", "close", "volume", "elements"]

    def __init__(self, dt: Any, open_: float, high: float, low: float,
                 close: float, volume: float,
                 elements: Optional[List[int]] = None):
        self.dt = dt
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        # 原始bar索引; None 等价于空列表
        self.elements = elements if elements is not None else []

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试与展示用), elements 拷贝一份防外部误改"""
        return {"dt": self.dt, "open": self.open, "high": self.high,
                "low": self.low, "close": self.close, "volume": self.volume,
                "elements": list(self.elements)}


def remove_includes(bars: List[Dict[str, Any]]) -> List[NewBar]:
    """包含关系处理 -> 无包含的 NewBar 列表(顺序原则)

    参数:
        bars: 标准 bar 列表(由 chan.bars.normalize_bars 产出),
            每项含 open/high/low/close/volume/dt, 按时间升序。

    返回:
        list of NewBar, 依次两两合并后的无包含K线序列。
        空输入返回 []。

    规则:
        - 相邻两K线存在包含(一K线高低点全在另一K线范围内)时, 按方向合并:
          向上(后者高点更高)取 [max(高), max(低)];
          向下(后者低点更低)取 [min(低), min(高)]。
        - 方向由前一根合并K线与再前一根比较决定; 只有一根时与当前K线比。
        - 顺序原则: 依次两两处理, 不跨步(包含关系不满足传递律)。
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
    """分型对象(无包含三相邻K线的中间K线)

    属性:
        kind: 'top' 顶分型 / 'bottom' 底分型。
        dt: 分型中间K线的时间(信号时间锚, 注意: 分型需后一根K线确认,
            因此 dt 天然早于"能确认它"的时刻一个周期)。
        high / low: 分型区间的高低点——
            顶分型: high = 顶(中间K线高点), low = 分型区间低点;
            底分型: low = 底(中间K线低点), high = 分型区间高点。
        bar_index: 中间K线在无包含序列中的索引(笔的成笔间隔用此计算)。
        elements: 对应原始 bars 的三根K线索引(左/中/右)。
    """

    __slots__ = ["kind", "dt", "high", "low", "bar_index", "elements"]

    def __init__(self, kind: str, dt: Any, high: float, low: float,
                 bar_index: int, elements: List[int]):
        self.kind = kind        # 'top' 顶 / 'bottom' 底
        self.dt = dt            # 分型中间K线时间
        self.high = high        # 顶分型: 顶; 底分型: 分型区间高点
        self.low = low          # 底分型: 底; 顶分型: 分型区间低点
        self.bar_index = bar_index   # 中间K线在无包含序列中的索引
        self.elements = elements     # 对应原始bars索引(三根)

    @property
    def value(self) -> float:
        """分型的极值(顶或底): 顶分型返回 high, 底分型返回 low。

        笔的端点、买卖点价格等一律以本属性为准。
        """
        return self.high if self.kind == "top" else self.low

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"kind": self.kind, "dt": str(self.dt), "high": self.high,
                "low": self.low, "bar_index": self.bar_index,
                "elements": list(self.elements), "value": self.value}


def find_fxs(new_bars: List[NewBar]) -> List[FX]:
    """在无包含序列中识别全部顶/底分型

    参数:
        new_bars: remove_includes 的输出(无包含K线序列)。

    返回:
        list of FX, 按时间顺序。少于 3 根K线时返回 []。

    规则:
        - 顶分型: 中间K线 b 满足
            b.high > a.high 且 b.high > c.high(高点三者最高),
            b.low > a.low 且 b.low > c.low(低点也是三者最高);
        - 底分型镜像: 低点三者最低且高点也是三者最低;
        - 逐K线滑窗, 同一K线既是某分型中间K线, 也可能参与相邻分型
          (本实现不做分型重叠过滤, 重叠交由笔层 MIN_K_GAP 约束)。
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
