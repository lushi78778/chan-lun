# -*- coding: utf-8 -*-
"""
chan.bc —— 背驰识别(动力学, MACD 辅助)

理论依据: doc/缠论知识库/04-背驰与区间套.md

  标准背驰(趋势背驰): 趋势(至少两个同向不重叠中枢)中, 最后中枢
    之后的离开段力度比前一连接段弱(MACD 柱面积), 且价格创新高/新低。
  盘整背驰: 中枢震荡中, 两段同向波动力度比较(用于中枢震荡短差)。

  力度度量(课24 MACD 辅助): 段对应的 MACD 柱(hist=(DIF-DEA)*2)面积,
  上涨段看红柱面积, 下跌段看绿柱面积; 简化: sum(hist) 的绝对值。

兼容: Python 3.6, numpy。
"""

from __future__ import print_function

import numpy as np


def ema(values, n):
    """指数移动平均(纯 numpy 实现, 兼容老版本)"""
    values = np.asarray(values, dtype=float)
    out = np.empty(len(values))
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def macd_series(bars, fast=12, slow=26, signal=9):
    """MACD 指标序列

    返回: (dif, dea, hist) numpy 数组, hist = (dif - dea) * 2
    """
    closes = np.array([b["close"] for b in bars], dtype=float)
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = (dif - dea) * 2.0
    return dif, dea, hist


def _dt_index(bars):
    """bars 的 dt -> 索引 映射(用最后一个匹配)"""
    idx = {}
    for i, b in enumerate(bars):
        idx[str(b["dt"])] = i
    return idx


def segment_area(hist, bars_index, dt_map, start_dt, end_dt):
    """某段 [start_dt, end_dt] 的 MACD 柱面积(带符号 sum)

    返回: float(正=红柱主导/上涨, 负=绿柱主导/下跌)
    """
    i0 = dt_map.get(str(start_dt))
    i1 = dt_map.get(str(end_dt))
    if i0 is None or i1 is None:
        return 0.0
    if i0 > i1:
        i0, i1 = i1, i0
    i1 = min(i1 + 1, len(hist))
    return float(np.sum(hist[i0:i1]))


def find_trend_bc(bis, zss, bars, hist=None):
    """趋势背驰识别(基于笔级中枢)

    参数:
        bis: 笔列表
        zss: 中枢列表(通常由 find_zs(bis) 生成)
        bars: 原始 bars(list of dict)
        hist: MACD 柱序列(默认计算)

    返回: list of dict
        {direction: 'up'/'down', dt, price, zs_idx, area_prev, area_last,
         note}
    规则(向上趋势):
        - 相邻两中枢后 DD > 前 GG(向上);
        - 最后中枢之后离开段创新高;
        - 离开段 MACD 面积 < 前一连接段面积 -> 顶背驰。
      向下趋势镜像 -> 底背驰。
    """
    if hist is None:
        _, _, hist = macd_series(bars)
    dt_map = _dt_index(bars)
    out = []
    if len(zss) < 2:
        return out

    for k in range(1, len(zss)):
        prev, zs = zss[k - 1], zss[k]
        up_trend = (zs.dd > prev.gg)
        down_trend = (zs.gg < prev.dd)
        if not (up_trend or down_trend):
            continue
        # 最后中枢(第 k 个)之后的离开段: 中枢 end_dt 之后的第一段同向笔
        # 简化: 用最后一个中枢 end_dt 到最后一笔终点的区间
        last_dt = bis[-1].end_dt
        # 前一连接段: prev 中枢 end_dt -> zs 中枢 start_dt 之间
        area_prev = segment_area(hist, bars, dt_map, prev.end_dt, zs.start_dt)
        area_last = segment_area(hist, bars, dt_map, zs.end_dt, last_dt)
        if up_trend:
            # 离开段创新高
            last_high = bis[-1].end_value if bis[-1].direction == "up" else bis[-1].start_value
            prev_high = prev.gg
            if last_high > prev_high and abs(area_last) < abs(area_prev) and area_last > 0:
                out.append({"direction": "up", "dt": str(bis[-1].end_dt),
                            "price": last_high, "zs_idx": k,
                            "area_prev": abs(area_prev), "area_last": abs(area_last),
                            "note": "趋势顶背驰候选"})
        else:
            last_low = bis[-1].end_value if bis[-1].direction == "down" else bis[-1].start_value
            prev_low = prev.dd
            if last_low < prev_low and abs(area_last) < abs(area_prev) and area_last < 0:
                out.append({"direction": "down", "dt": str(bis[-1].end_dt),
                            "price": last_low, "zs_idx": k,
                            "area_prev": abs(area_prev), "area_last": abs(area_last),
                            "note": "趋势底背驰候选"})
    return out


def find_pan_bc(bis, zss, bars, hist=None, max_dev=0.15):
    """盘整背驰识别(中枢震荡内两段同向波动力度比较)

    对每个中枢: 比较围绕中枢的相邻两段同向波动(向上离开 vs 进入)
    简化: 中枢区间内, 取笔序列中相邻两段同向笔(方向向上/向下),
    后段创新高/新低但面积更小 -> 盘整背驰。

    v2 增强(位置过滤): 盘整背驰是"围绕中枢的波动"比较, 信号点必须
    距中枢不远; 创新高/新低后远离中枢(超过 max_dev 比例)的信号
    多为趋势延伸而非中枢震荡, 予以剔除。

    返回: list of dict
    """
    if hist is None:
        _, _, hist = macd_series(bars)
    dt_map = _dt_index(bars)
    out = []
    if not zss:
        return out

    for zi, zs in enumerate(zss):
        # 找出中枢区间内的笔(起点或终点在中枢区间内)
        segs = []
        i = 0
        n = len(bis)
        while i < n:
            bi = bis[i]
            # 同向笔合并成"段"
            seg = [bi]
            j = i + 1
            while j < n and bis[j].direction == bi.direction:
                seg.append(bis[j])
                j += 1
            i = j
            segs.append(seg)
        # 同向段比较(A/B/C 模式: 隔一个反向段): 方向同为 up 或同为 down
        for s in range(2, len(segs)):
            a, b = segs[s - 2], segs[s]
            if a[0].direction != b[0].direction:
                continue
            area_a = segment_area(hist, bars, dt_map,
                                  a[0].start_dt, a[-1].end_dt)
            area_b = segment_area(hist, bars, dt_map,
                                  b[0].start_dt, b[-1].end_dt)
            if abs(area_b) >= abs(area_a):
                continue
            if b[0].direction == "up":
                if b[-1].end_value > a[-1].end_value:
                    price = b[-1].end_value
                    # 位置过滤: 信号价距中枢 GG 不超过 max_dev
                    if price <= zs.gg * (1 + max_dev):
                        out.append({"zs_idx": zi, "direction": "up",
                                    "dt": str(b[-1].end_dt),
                                    "price": price,
                                    "area_prev": abs(area_a), "area_last": abs(area_b),
                                    "note": "盘整顶背驰候选"})
            else:
                if b[-1].end_value < a[-1].end_value:
                    price = b[-1].end_value
                    # 位置过滤: 信号价距中枢 DD 不低于 max_dev
                    if price >= zs.dd * (1 - max_dev):
                        out.append({"zs_idx": zi, "direction": "down",
                                    "dt": str(b[-1].end_dt),
                                    "price": price,
                                    "area_prev": abs(area_a), "area_last": abs(area_b),
                                    "note": "盘整底背驰候选"})
    return out
