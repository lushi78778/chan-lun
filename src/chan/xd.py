# -*- coding: utf-8 -*-
"""
chan.xd —— 线段的识别(特征序列两种标准)

理论依据: doc/缠论知识库/02-走势分解基础-分型笔线段.md §2.4

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
(缺口 + 第二特征序列确认); 序列末尾未完成的线段 mode=1 且无确认终点。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple

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
        gg / dd: 线段内部高低极值(所有构成笔的范围),
            中枢重叠计算用 high/low 属性即返回它们。
    """

    __slots__ = ["direction", "start_dt", "end_dt", "start_value",
                 "end_value", "start_index", "end_index", "mode",
                 "gg", "dd"]

    def __init__(self, direction: str,
                 start: Tuple[Any, float, int], end: Tuple[Any, float, int],
                 mode: int, gg: Optional[float] = None,
                 dd: Optional[float] = None):
        self.direction = direction    # 'up' / 'down'
        self.start_dt, self.start_value, self.start_index = start
        self.end_dt, self.end_value, self.end_index = end
        self.mode = mode              # 1 第一种情况 / 2 第二种情况(缺口确认)
        # 线段内部高低极值(所有构成笔的范围), 中枢重叠计算用
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
                "mode": self.mode}


def _merge_feats(feats: List[Tuple[float, float, BI]]) -> List[Tuple[float, float, BI]]:
    """特征序列包含处理(元素 = (low, high, bi))

    参数:
        feats: 特征序列元素列表, 每项 (low, high, 对应笔对象)。

    返回:
        合并后的特征序列(顺序原则, 同K线包含规则):
        向上(后元素高点 >= 前元素高点): 新元素 = [max(low), max(high)];
        向下: 新元素 = [min(low), min(high)];
        合并时保留高点更高(向上)或低点更低(向下)一侧的笔引用。
    """
    out = [feats[0]]
    for e in feats[1:]:
        last = out[-1]
        # 包含关系: 一元素区间全在另一元素区间内
        last_contains_e = (last[0] <= e[0] and last[1] >= e[1])
        e_contains_last = (e[0] <= last[0] and e[1] >= last[1])
        if not (last_contains_e or e_contains_last):
            out.append(e)
            continue
        if len(out) >= 2:
            direction_up = (last[1] >= out[-2][1])
        else:
            direction_up = (e[1] >= last[1])
        if direction_up:
            nl = max(last[0], e[0])
            nh = max(last[1], e[1])
            bi = e[2] if e[1] >= last[1] else last[2]
        else:
            nl = min(last[0], e[0])
            nh = min(last[1], e[1])
            bi = e[2] if e[0] <= last[0] else last[2]
        out[-1] = (nl, nh, bi)
    return out


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


def find_xds(bis: List[BI]) -> List[XD]:
    """识别线段(增量状态机, 支持第二种情况的缺口确认)

    参数:
        bis: find_bis 输出的笔列表(顶底交替、首尾衔接)。

    返回:
        list of XD, 按时间顺序; 最后一个可能为未完成线段
        (mode=1 且终点未获特征序列分型确认, 属正常现象)。

    算法要点:
        - 同向笔延伸当前线段端点, 同时把笔区间并入 gg/dd;
        - 反向笔构成第一特征序列: 合并后检查顶/底分型;
          无缺口(第一种情况) -> 线段结束于分型极值点;
          有缺口(第二种情况) -> 记录待确认终点(pending),
          等待第二特征序列(与线段同向的笔)出现对应分型才确认;
        - 线段结束后, 方向翻转, 以确认点为新起点继续。
    """
    if not bis:
        return []
    if len(bis) < 3:
        # 不足三笔无法构成线段(或直接以一笔为未完成线段)
        b = bis[0]
        return [XD(bis[0].direction,
                   (b.start_dt, b.start_value, b.start_index),
                   (b.end_dt, b.end_value, b.end_index), 1)]

    xds = []
    direction = bis[0].direction
    start = (bis[0].start_dt, bis[0].start_value, bis[0].start_index)
    cur_end = (bis[0].end_dt, bis[0].end_value, bis[0].end_index)
    cur_gg = max(bis[0].start_value, bis[0].end_value)
    cur_dd = min(bis[0].start_value, bis[0].end_value)
    feats = []       # 第一特征序列(与线段反向的笔)
    pending = None   # 第二种情况待确认终点 (dt, value, index)
    second = []      # 第二特征序列(缺口后, 与线段同向的笔)

    def flip(d):
        return "down" if d == "up" else "up"

    for bi in bis:
        # 无论同向反向, 笔区间都纳入线段内部极值
        cur_gg = max(cur_gg, bi.high)
        cur_dd = min(cur_dd, bi.low)
        if bi.direction == direction:
            # 同向笔: 更新线段当前端点
            cur_end = (bi.end_dt, bi.end_value, bi.end_index)
            if pending is not None:
                # 第二种情况: 第二特征序列收集同向笔
                second.append((bi.low, bi.high, bi))
                second = _merge_feats(second)
                kind2 = "bottom" if direction == "up" else "top"
                if _has_fx(second, kind2) is not None:
                    xds.append(XD(direction, start, pending, 2,
                                  gg=cur_gg, dd=cur_dd))
                    direction = flip(direction)
                    start = pending
                    pending = None
                    second = []
                    feats = []
                    cur_end = (bi.end_dt, bi.end_value, bi.end_index)
                    cur_gg = bi.high
                    cur_dd = bi.low
            continue
        # 反向笔: 第一特征序列元素
        elem = (bi.low, bi.high, bi)
        feats.append(elem)
        feats = _merge_feats(feats)
        if pending is not None:
            # 第二种情况确认期间: 只等第二特征序列分型, 不再检查第一序列
            continue
        kind = "top" if direction == "up" else "bottom"
        idx = _has_fx(feats, kind)
        if idx is None:
            continue
        a, b, c = feats[idx], feats[idx + 1], feats[idx + 2]
        if direction == "up":
            # 顶分型; 缺口: 第一元素高点 < 第二元素低点(无重叠)
            gap = (a[1] < b[0])
            point = (b[2].start_dt, b[1], b[2].start_index)
        else:
            # 底分型; 缺口: 第一元素低点 > 第二元素高点
            gap = (a[0] > b[1])
            point = (b[2].start_dt, b[0], b[2].start_index)
        if not gap:
            # 第一种情况: 线段结束
            xds.append(XD(direction, start, point, 1,
                          gg=cur_gg, dd=cur_dd))
            direction = flip(direction)
            start = point
            feats = []
            cur_end = (bi.end_dt, bi.end_value, bi.end_index)
            cur_gg = bi.high
            cur_dd = bi.low
        else:
            # 第二种情况: 记录待确认终点, 第二特征序列从下一同向笔开始收集
            pending = point
            second = []

    # 末尾未完成线段
    xds.append(XD(direction, start, cur_end, 1, gg=cur_gg, dd=cur_dd))
    return xds


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
