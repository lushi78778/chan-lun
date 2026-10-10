# -*- coding: utf-8 -*-
"""
chan.xd —— 线段的识别(特征序列两种标准)

理论依据: 课67定义、课71分界包含、课78延续与极值、课81图例更正。

  线段由至少三笔构成, 前三笔必须有重叠。
  以向上线段为例(向下对称):
    - 特征序列: 向下笔序列 X1X2X3...(每笔区间 [low, high]);
    - 标准特征序列: 特征序列按包含关系处理后;
    - 只考察顶分型(向下线段只考察底分型);
    - 第一种情况: 顶分型第一、二元素间无缺口 -> 线段在该顶分型
      的高点处结束;
    - 第二种情况: 第一、二元素间有缺口 -> 必须等"从该分型最高点
      开始的向下一笔开始的序列的特征序列(向上笔序列)出现底分型",
      线段才在该顶分型高点处结束(第二序列的分型不分一、二种情况)。

XD.mode 标记线段结束方式: 1 = 第一种情况(无缺口), 2 = 第二种情况
(缺口 + 第二特征序列确认); complete区分完成与尾部, mode不作完成标志。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple
import math
from numbers import Real

from chan.bi import BI


class XD(object):
    """线段对象

    属性:
        direction: 'up' / 'down'。
        start_dt / start_value / start_index: 起点(时间/价格/笔索引)。
        end_dt / end_value / end_index: 终点(时间/价格/笔索引)。
        mode: 1 = 第一种情况(特征序列分型直接确认),
              2 = 第二种情况(缺口, 由第二特征序列分型确认)。
              序列末尾未完成线段的 mode 恒为 1。
        complete: 给定笔前缀下是否已满足线段破坏定义。
        evidence_dt/evidence_end_index: 最后一笔证据端点(不等于行情确认时间)。
        gg / dd: 线段内部高低极值(所有构成笔的范围),
            中枢重叠计算用 high/low 属性即返回它们。
    """

    __slots__ = ["direction", "start_dt", "end_dt", "start_value",
                 "end_value", "start_index", "end_index", "mode",
                 "gg", "dd", "complete", "evidence_end_index", "evidence_dt"]

    def __init__(self, direction: str,
                 start: Tuple[Any, float, int], end: Tuple[Any, float, int],
                 mode: int, gg: Optional[float] = None,
                 dd: Optional[float] = None, complete: bool = False,
                 evidence_end_index: Optional[int] = None, evidence_dt: Any = None):
        self.direction = direction    # 'up' / 'down'
        self.start_dt, self.start_value, self.start_index = start
        self.end_dt, self.end_value, self.end_index = end
        self.mode = mode              # 1 第一种情况 / 2 第二种情况(缺口确认)
        self.complete = complete
        self.evidence_end_index = evidence_end_index
        self.evidence_dt = evidence_dt
        # 只计算线段组成笔的范围, 确认用的后续笔另记证据。
        if gg is None:
            gg = max(self.start_value, self.end_value)
        if dd is None:
            dd = min(self.start_value, self.end_value)
        self.gg = gg
        self.dd = dd

    @property
    def high(self) -> float:
        """线段内部最高点"""
        return self.gg

    @property
    def low(self) -> float:
        """线段内部最低点"""
        return self.dd

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"direction": self.direction,
                "start": [str(self.start_dt), self.start_value],
                "end": [str(self.end_dt), self.end_value],
                "gg": self.gg, "dd": self.dd,
                "mode": self.mode, "complete": self.complete,
                "evidence_end_index": self.evidence_end_index,
                "evidence_dt": None if self.evidence_dt is None else str(self.evidence_dt)}


def _has_fx(feats: List[Tuple[float, float, BI]], kind: str) -> Optional[int]:
    """检查末尾三元素是否构成分型; 返回起始索引或 None

    参数:
        feats: 已合并的标准特征序列。
        kind: 'top' 顶分型 / 'bottom' 底分型。

    返回:
        构成分型的第一个元素在 feats 中的下标; 不构成返回 None。
        (分型判定只看区间: 顶分型 = 中间元素 high/low 均三者最高;
         底分型 = 中间元素 low/high 均三者最低。)
    """
    if len(feats) < 3:
        return None
    a, b, c = feats[-3], feats[-2], feats[-1]
    if kind == "top":
        if b[1] > a[1] and b[1] > c[1] and b[0] > a[0] and b[0] > c[0]:
            return len(feats) - 3
    else:
        if b[0] < a[0] and b[0] < c[0] and b[1] < a[1] and b[1] < c[1]:
            return len(feats) - 3
    return None


def _feature_append(out, elem, direction_up):
    """同一特征序列顺序包含; 初始方向由假设转折后的走势给定。"""
    if not out:
        return [elem]
    last = out[-1]
    contained = (last[0] <= elem[0] and last[1] >= elem[1] or
                 elem[0] <= last[0] and elem[1] >= last[1])
    if not contained:
        return out + [elem]
    if len(out) > 1:
        direction_up = last[1] > out[-2][1]
    low = max(last[0], elem[0]) if direction_up else min(last[0], elem[0])
    high = max(last[1], elem[1]) if direction_up else min(last[1], elem[1])
    ref = (elem[2] if (elem[1] > last[1] if direction_up else elem[0] < last[0])
           else last[2])
    return out[:-1] + [(low, high, ref)]


def _segment_end(bis, start):
    """从一个已给定起点找最早确认的分界(课67/71/78/81)。

    分界前的最后特征元素和分界开始的一笔不合并; 分界后同类元素
    可以合并。第二特征序列从分界开始完整收集, 不从发现分型以后
    才收集。第二分型尚未成立而原方向新极值出现时, 假设分界撤销。
    """
    up = bis[start].direction == "up"
    counter = "down" if up else "up"
    candidate, left, right, second = None, None, [], []
    features = []
    extreme = bis[start].start_value
    for i in range(start, len(bis)):
        bi = bis[i]
        if bi.direction != counter:
            if candidate is not None:
                second = _feature_append(second, (bi.low, bi.high, bi), not up)
                # 第二序列至少三元素; 不再分缺口的两种情况(课67)。
                if left is not None and len(right) >= 2:
                    a, b = left, right[0]
                    gap = a[1] < b[0] if up else a[0] > b[1]
                    kind = "bottom" if up else "top"
                    if gap and _has_fx(second, kind) is not None:
                        return candidate, i, 2
                if bi.end_value > extreme if up else bi.end_value < extreme:
                    candidate, right, second = None, [], []
            continue
        price = bi.start_value
        new_extreme = price > extreme if up else price < extreme
        if new_extreme:
            # 课78: 未确认前直接新高/新低, A+B+C只能算原方向一段。
            left = features[-1] if features else None
            candidate, extreme = i, price
            right, second = [(bi.low, bi.high, bi)], []
            features = _feature_append(features, (bi.low, bi.high, bi), up)
            continue
        if candidate is None:
            continue
        right = _feature_append(right, (bi.low, bi.high, bi), not up)
        if left is None or len(right) < 2:
            continue
        a, b, c = left, right[0], right[1]
        gap = a[1] < b[0] if up else a[0] > b[1]
        lower_right = (c[1] < b[1] and c[0] < b[0] if up else
                       c[0] > b[0] and c[1] > b[1])
        if not lower_right:
            continue
        if not gap:
            # 课71: 首笔破坏的中间地带不可跨分界包含, 包括b包含a。
            return candidate, i, 1
        # 第二种情况的第一分型已成立, 第二序列可能更早已收集。
        kind = "bottom" if up else "top"
        if _has_fx(second, kind) is not None:
            return candidate, i, 2
    return None


def find_xds(bis: List[BI]) -> List[XD]:
    """课67/71/78/81线段: 至少三笔、前三笔闭区间重叠。

    输入是按顺序首尾衔接的交替笔; 仅消费给定前缀。不足三笔或
    首三笔无重叠不输出伪线段; 若窗口从趋势中间开始, 向后寻找最早
    三笔重叠起点, 不保证覆盖前面的残笔。末段complete=False。
    complete=True只表示给定笔序列已满足线段破坏定义, 不证明输入
    笔在该端点日已经最终确认。evidence_dt是最后证据笔的端点,
    不是原始行情的实际可用时间; 回放仍须逐原始行情前缀计算。

    完成段的gg/dd只含起点至终点的笔, 不把确认用的后续笔纳入。
    分界后从终点重新处理全部已读取笔, 不丢弃新段前部。构造器
    XD(...,mode)默认complete=False, 手工对象需显式提供完成证据。
    """
    if not isinstance(bis, (list, tuple)):
        raise TypeError("bis须为list或tuple")
    for i, bi in enumerate(bis):
        if not all(isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (bi.start_value, bi.end_value)):
            raise ValueError("笔端点价须为有限数值")
        if bi.direction not in ("up", "down") or not bi.start_index < bi.end_index:
            raise ValueError("笔须有有效方向和递增端点索引")
        if (bi.direction == "up") != (bi.end_value > bi.start_value) or bi.end_value == bi.start_value:
            raise ValueError("笔方向须与端点价一致")
        if i and (bis[i-1].direction == bi.direction or
                  bis[i-1].end_dt != bi.start_dt or
                  bis[i-1].end_value != bi.start_value or
                  bis[i-1].end_index != bi.start_index):
            raise ValueError("笔须交替且时间、价格、索引首尾衔接")
    out, start = [], 0
    while start + 2 < len(bis):
        first = bis[start:start+3]
        if max(b.low for b in first) > min(b.high for b in first):
            start += 1
            continue
        ending = _segment_end(bis, start)
        if ending is None:
            # 未完成段保留已达到的同向极值, 不用回落后的同向笔反转方向。
            # 最少三笔且顶须高于底(课78); 不满足的起始残笔继续向后搜索。
            eligible = [j for j in range(start+2, len(bis), 2)
                        if (bis[j].end_value > bis[start].start_value
                            if bis[start].direction == "up" else
                            bis[j].end_value < bis[start].start_value)]
            if not eligible:
                start += 1
                continue
            end = (max(eligible, key=lambda j: bis[j].end_value)
                   if bis[start].direction == "up" else
                   min(eligible, key=lambda j: bis[j].end_value))
            stop, evidence, mode, complete = end+1, None, 1, False
        else:
            stop, evidence, mode = ending
            complete = True
        units = bis[start:stop]
        a, b = units[0], units[-1]
        out.append(XD(a.direction, (a.start_dt, a.start_value, a.start_index),
                      (b.end_dt, b.end_value, b.end_index), mode,
                      max(u.high for u in units), min(u.low for u in units),
                      complete, None if evidence is None else bis[evidence].end_index,
                      None if evidence is None else bis[evidence].end_dt))
        if ending is None:
            break
        start = stop  # 完整重放分界后已消耗的笔, 不直接跳到证据末尾。
    return out


def chan_bis_xds(bars: List[Dict[str, Any]], standard: str = "81") -> Tuple[List[Any], List[Any], List[BI], List[XD]]:
    """完整入口: 原始 bars -> (无包含序列, 分型, 笔, 线段)

    参数:
        bars: 标准 bar 列表(chan.bars.normalize_bars 产出)。
        standard: 笔标准 '81'(默认)或'106', 透传给chan_fx_bi。

    返回:
        四元组 (new_bars, fxs, bis, xds):
            new_bars: 无包含K线序列(NewBar 列表);
            fxs: 分型列表(FX 列表);
            bis: 笔列表(BI 列表);
            xds: 线段列表(XD 列表, 末个可能未完成)。
    """
    from chan.bi import chan_fx_bi
    new_bars, fxs, bis = chan_fx_bi(bars, standard=standard)
    xds = find_xds(bis)
    return new_bars, fxs, bis, xds
