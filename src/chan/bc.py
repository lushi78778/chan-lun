# -*- coding: utf-8 -*-
"""
chan.bc —— 背驰识别(动力学, MACD 辅助)

理论依据: doc/缠论知识库/04-背驰与区间套.md

  标准背驰(趋势背驰): 趋势(至少两个同向不重叠中枢)中, 最后中枢
    之后的离开段力度比前一连接段弱(MACD 柱面积), 且价格创新高/新低。
  盘整背驰: 中枢震荡中, 两段同向波动力度比较(用于中枢震荡短差)。

  力度度量(课24 MACD 辅助): 段对应的 MACD 柱(hist=(DIF-DEA)*2)面积,
  上涨段看红柱面积, 下跌段看绿柱面积; 简化: sum(hist) 的绝对值。

MACD 为内置纯 numpy 实现(ema), 不依赖 TA-Lib。

兼容: Python 3.6, numpy。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def ema(values: Any, n: int) -> Any:
    """指数移动平均(纯 numpy 实现, 兼容老版本)

    参数:
        values: 数组或列表(将转 float 数组)。
        n: 周期。k = 2/(n+1), 首元素用原值作种子(标准 EMA 做法)。

    返回:
        numpy 数组, 与输入等长。递推实现, 无 TA-Lib 依赖。
    """
    values = np.asarray(values, dtype=float)
    out = np.empty(len(values))
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def macd_series(bars: List[Dict[str, Any]], fast: int = 12, slow: int = 26,
                signal: int = 9) -> Tuple[Any, Any, Any]:
    """MACD 指标序列

    参数:
        bars: 标准 bar 列表(取 close 序列计算)。
        fast / slow / signal: EMA 周期, 默认 12/26/9(市场惯例)。

    返回:
        (dif, dea, hist) 三个 numpy 数组, 与 bars 等长;
        dif = EMA(fast) - EMA(slow), dea = EMA(dif, signal),
        hist = (dif - dea) * 2(柱 = 国内软件惯例的双倍)。
    """
    closes = np.array([b["close"] for b in bars], dtype=float)
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = (dif - dea) * 2.0
    return dif, dea, hist


def _dt_index(bars: List[Dict[str, Any]]) -> Dict[str, int]:
    """bars 的 dt -> 索引 映射(重复 dt 用最后一个匹配; 内部工具)"""
    idx = {}
    for i, b in enumerate(bars):
        idx[str(b["dt"])] = i
    return idx


def segment_area(hist: Any, bars_index: Any, dt_map: Dict[str, int],
                 start_dt: Any, end_dt: Any) -> float:
    """某段 [start_dt, end_dt] 的 MACD 柱面积(带符号 sum)

    参数:
        hist: macd_series 的柱序列。
        bars_index: 历史遗留参数(向后兼容保留, 未使用)。
        dt_map: _dt_index(bars) 的 dt -> 下标映射。
        start_dt / end_dt: 段的起止时间(闭区间, end 端含该根柱)。

    返回:
        float, 带符号面积: 正 = 红柱主导(上涨), 负 = 绿柱主导(下跌)。
        任一端点在 bars 中找不到时返回 0.0(不抛异常, 供健壮调用)。
    """
    i0 = dt_map.get(str(start_dt))
    i1 = dt_map.get(str(end_dt))
    if i0 is None or i1 is None:
        return 0.0
    if i0 > i1:
        i0, i1 = i1, i0
    i1 = min(i1 + 1, len(hist))
    return float(np.sum(hist[i0:i1]))


def find_trend_bc(bis: List[Any], zss: List[Any],
                  bars: List[Dict[str, Any]],
                  hist: Optional[Any] = None) -> List[Dict[str, Any]]:
    """趋势背驰识别(基于笔级中枢)

    参数:
        bis: 笔列表(chan.bi.find_bis 输出)。
        zss: 中枢列表(通常由 find_zs(bis) 生成, 笔级中枢)。
        bars: 原始 bars(list of dict, 与 bis 同一序列)。
        hist: MACD 柱序列(默认用 macd_series 现算; 复用可省一次计算)。

    返回:
        list of dict, 每项:
            direction: 'up' 顶背驰候选 / 'down' 底背驰候选;
            dt / price: 信号时间(最后一笔终点)与价格;
            zs_idx: 中枢列表下标(第 k 个, 即"最后中枢");
            area_prev / area_last: 前一连接段 / 最后离开段的柱面积(绝对值);
            note: 说明文字。

    规则(向上趋势):
        - 相邻两中枢满足 zs.dd > prev.gg(中枢不重叠且后高前低);
        - 最后中枢之后离开段创新高(超过前一中枢 gg);
        - 离开段 MACD 面积 < 前一连接段面积, 且柱为正(红柱)。
      向下趋势镜像 -> 底背驰候选。
      注: 至少两个中枢才可能产生趋势背驰; 离开段用"最后中枢 end_dt ->
      最后一笔终点"近似(简化)。
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


def find_pan_bc(bis: List[Any], zss: List[Any],
                bars: List[Dict[str, Any]], hist: Optional[Any] = None,
                max_dev: float = 0.15) -> List[Dict[str, Any]]:
    """盘整背驰识别(中枢震荡内两段同向波动力度比较)

    参数:
        bis: 笔列表。
        zss: 中枢列表。
        bars: 原始 bars。
        hist: MACD 柱序列(默认现算)。
        max_dev: 位置过滤——创新高/新低后偏离中枢边界超过该比例的信号
            多为趋势延伸而非中枢震荡, 予以剔除。默认 0.15。

    返回:
        list of dict, 每项:
            zs_idx: 中枢下标; direction: 'up' 顶背驰 / 'down' 底背驰;
            dt / price: 信号时间与价格(后段终点);
            area_prev / area_last: 前段 / 后段柱面积(绝对值);
            note: 说明文字。

    算法:
        对每个中枢, 把笔按同向合并成"段"(segs), 取 A/B/C 模式
        (隔一个反向段的两个同向段)比较: 后段创新高/新低但面积更小
        -> 盘整背驰; 再叠加位置过滤(顶背驰信号价距 GG 不超过
        max_dev, 底背驰距 DD 不低于 -max_dev)。
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
