# -*- coding: utf-8 -*-
"""
chan.cross30 —— 30 分钟跨级别确认(区间套基础)

理论依据: doc/缠论知识库/04-背驰与区间套.md

区间套思想(课 108/99): 大级别信号出现后, 到次级别里找背驰确认,
两级别同时成立才叫"共振", 可靠度远高于单级别信号。

  日线第三类买点 = 向上离开日线中枢 [ZD, ZG] 后, 回抽笔不破 ZG。
  区间套确认: 回抽笔的内部(30 分钟级别)应呈现一段下跌走势,
  且该下跌末端出现**底背驰**(最后一段下跌 MACD 面积比前一段小、
  却创新低); 同时 30 分钟低点不破日线 ZG(允许轻微刺破)。
  -> 满足 = "跨级别共振"(强确认); 不满足 = 日线信号未获次级别背书。

  日线第三类卖点镜像: 反弹笔内部 30 分钟出现**顶背驰**,
  且 30 分钟高点不升破日线 ZD。

实现: 30m bars -> 笔 -> 连续同向 run(段), 比较最后一段下跌(上涨)
与前一对照段的力度(DIF 摆动 = 段首末 DIF 差; MACD 柱面积作参考),
叠加日线中枢位置过滤。

力度度量为什幺用 DIF 摆动: 柱面积受前段动量惯性污染(强涨后的
反弹段里 DIF 仍为负, 面积会被抵消), DIF 在段内的变化量只反映
本段自身的推动力, 对 EMA 滞后更稳健。

兼容: Python 3.6。依赖 chan.bi / chan.zs / chan.bc。
"""

from __future__ import print_function

import datetime

from chan.bi import chan_fx_bi
from chan.zs import find_zs
from chan.bc import macd_series, segment_area, _dt_index


def _date_of(dt):
    return str(dt)[:10]


def _days_diff(dt_a, dt_b):
    """两个时间点相差的自然日天数(dt_a - dt_b)"""
    da = datetime.datetime.strptime(_date_of(dt_a), "%Y-%m-%d")
    db = datetime.datetime.strptime(_date_of(dt_b), "%Y-%m-%d")
    return (da - db).days


def _group_runs(bis):
    """把笔列表按方向合并成连续同向段(run)

    返回: list of (direction, [bi, ...]), 时间有序
    """
    runs = []
    for bi in bis:
        if runs and runs[-1][0] == bi.direction:
            runs[-1][1].append(bi)
        else:
            runs.append((bi.direction, [bi]))
    return runs


def find_run_exhaustion(bis30, bars30, run_dir, end_dt, stale_days=1,
                        min_prev_swing_ratio=None):
    """找最后一段同向 run 并判断其末端背驰

    参数:
        bis30: 30m 笔列表
        bars30: 30m bars(升序)
        run_dir: 'down' 找底背驰 / 'up' 找顶背驰
        end_dt: run 终点允许的最晚时间(日线信号日),
                run 终点须落在 [end_dt - stale_days, end_dt]
        stale_days: 终点允许早于信号日的自然日数
        min_prev_swing_ratio: 前一对照段 DIF 摆动的最小幅度(占价格中位数比例)。
            对照段摆动过小(微型波动)时力度比较无意义, 直接判 no_exhaustion。
            None = 不设门槛(兼容旧行为)。

    返回 dict:
        status: 'ok'(背驰成立) / 'no_exhaustion'(无背驰) /
                'stale'(run 终点过旧, 未跟上信号日) / 'none'(无该方向段)
        run_end_dt / run_start_dt: 最后一段 run 的起止时间
        swing_last / swing_prev / swing_ratio: 末段与前段 DIF 摆动及比值
        area_last / area_prev / area_ratio: MACD 柱面积及比值(参考)
        extreme: 最后段极值(down=最低点, up=最高点)
        zs_count: 与最后段区间重叠的 30m 中枢个数
        note: 说明
    """
    out = {"status": "none", "note": "", "run_end_dt": None,
           "swing_last": None, "swing_prev": None, "swing_ratio": None,
           "area_last": None, "area_prev": None, "area_ratio": None,
           "extreme": None, "zs_count": 0}
    runs = _group_runs(bis30)
    if not runs:
        return out

    # 最后一段同向 run(允许其后再跟一段反向 run)
    cand = None
    for idx in range(len(runs) - 1, -1, -1):
        if runs[idx][0] == run_dir:
            cand = idx
            break
    if cand is None:
        out["note"] = "无{0}方向段".format(run_dir)
        return out

    run = runs[cand][1]
    end_date = _date_of(run[-1].end_dt)
    # 回抽段终点应落在 [信号日 - stale_days, 信号日] 内
    diff = _days_diff(end_dt, end_date)
    if diff > stale_days or diff < 0:
        out["status"] = "stale"
        out["note"] = "回抽段终点 {0} 距信号日 {1} 有 {2} 天(容差 {3} 天), 30m 未跟上".format(
            end_date, _date_of(end_dt), diff, stale_days)
        return out

    # 前一对照段(同方向, 中间隔一段反向)
    prev = None
    for idx in range(cand - 1, -1, -1):
        if runs[idx][0] == run_dir:
            prev = idx
            break

    dif, _, hist = macd_series(bars30)
    dt_map = _dt_index(bars30)

    # DIF 惯性尾: MACD 的 DIF 极值比价格极值滞后约 1-2 根K线,
    # 段的首末端各向后顺延 LAG 根, 把动量尾包进来, 度量才公平。
    lag = 2
    n_bars = len(bars30)

    def dif_swing(seg):
        i0 = dt_map.get(str(seg[0].start_dt))
        i1 = dt_map.get(str(seg[-1].end_dt))
        if i0 is None or i1 is None:
            return 0.0
        s = min(i0 + lag, n_bars - 1)
        e = min(i1 + lag, n_bars - 1)
        return float(abs(dif[e] - dif[s]))

    area_last = segment_area(hist, bars30, dt_map,
                             run[0].start_dt, run[-1].end_dt)
    out["run_start_dt"] = str(run[0].start_dt)
    out["run_end_dt"] = str(run[-1].end_dt)
    out["area_last"] = round(abs(area_last), 3)
    out["swing_last"] = round(dif_swing(run), 4)

    if run_dir == "down":
        out["extreme"] = min(b.low for b in run)
    else:
        out["extreme"] = max(b.high for b in run)

    # 30m 中枢覆盖情况(结构完整性)
    try:
        zss30 = find_zs(bis30)
        run_low = min(b.low for b in run)
        run_high = max(b.high for b in run)
        out["zs_count"] = sum(
            1 for z in zss30
            if not (z.zg < run_low or z.zd > run_high))
    except Exception:
        out["zs_count"] = 0

    if prev is None:
        out["status"] = "no_exhaustion"
        out["note"] = "无前一对照段, 无法比较力度"
        return out

    prev_run = runs[prev][1]
    area_prev = segment_area(hist, bars30, dt_map,
                             prev_run[0].start_dt, prev_run[-1].end_dt)
    out["area_prev"] = round(abs(area_prev), 3)
    if out["area_prev"] > 0:
        out["area_ratio"] = round(out["area_last"] / out["area_prev"], 3)
    out["swing_prev"] = round(dif_swing(prev_run), 4)

    # 对照段摆动幅度门槛(微型波动时力度比较无意义)
    if min_prev_swing_ratio is not None and min_prev_swing_ratio > 0:
        closes = sorted(b["close"] for b in bars30)
        mid = closes[len(closes) // 2]
        if mid > 0 and out["swing_prev"] < min_prev_swing_ratio * mid:
            out["status"] = "no_exhaustion"
            out["swing_ratio"] = None
            out["note"] = "前段DIF摆动过小(不足价格的 %.2f%%), 无法比较力度" % (
                min_prev_swing_ratio * 100.0)
            return out
    if out["swing_prev"] > 0:
        out["swing_ratio"] = round(out["swing_last"] / out["swing_prev"], 3)

    if run_dir == "down":
        new_extreme = run[-1].end_value < prev_run[-1].end_value
    else:
        new_extreme = run[-1].end_value > prev_run[-1].end_value

    if dif_swing(run) < dif_swing(prev_run) and new_extreme:
        out["status"] = "ok"
        out["note"] = "末端{0}背驰: DIF摆动 {1} < 前段 {2}".format(
            "底" if run_dir == "down" else "顶",
            round(dif_swing(run), 4), round(dif_swing(prev_run), 4))
    else:
        out["status"] = "no_exhaustion"
        out["note"] = "末段力度未衰竭(DIF摆动 {0} vs 前段 {1})".format(
            round(dif_swing(run), 4), round(dif_swing(prev_run), 4))
    return out


def confirm_buy3_30m(bars30, zd, zg, signal_dt,
                     zg_tol=0.01, weak_tol=0.02, stale_days=1,
                     min_prev_swing_ratio=None):
    """日线三买 -> 30 分钟跨级别确认

    参数:
        bars30: 30m bars(升序, 拉到信号日为止)
        zd/zg: 日线中枢下/上沿(与 30m 同一前复权基准)
        signal_dt: 日线三买信号日(str 或 date)
        zg_tol: 贴近 ZG 的比例(>= zg 即强确认)
        weak_tol: 允许 30m 低点跌破 ZG 的比例(zg*(1-weak_tol) 以内算弱确认)
        stale_days: 30m 回抽段终点允许早于信号日的自然日数
        min_prev_swing_ratio: 前一对照段 DIF 摆动最小幅度(占价格中位数比例,
            默认 None = 不设门槛)

    返回 dict:
        status: confirmed(强共振) / weak(弱确认) / no_exhaustion(无背驰) /
                broke(30m 跌破 ZG, 三买存疑) / stale / no_data
        + find_run_exhaustion 的明细字段 + low30 / dist_zg
    """
    out = {"status": "no_data", "note": "", "low30": None, "dist_zg": None}
    if not bars30:
        return out
    _, _, bis30 = chan_fx_bi(bars30)
    if len(bis30) < 2:
        out["note"] = "30m 笔不足, 无结构"
        return out

    ex = find_run_exhaustion(bis30, bars30, "down", signal_dt,
                             stale_days=stale_days,
                             min_prev_swing_ratio=min_prev_swing_ratio)
    out.update(ex)
    if ex["status"] in ("stale", "none"):
        return out

    low30 = ex["extreme"]
    out["low30"] = round(low30, 3)
    out["dist_zg"] = round((low30 - zg) / zg * 100.0, 3)
    exhausted = (ex["status"] == "ok")

    if low30 >= zg:
        if exhausted:
            out["status"] = "confirmed"
            out["note"] = "30m 底背驰 + 低点不破 ZG: 跨级别共振"
        else:
            out["status"] = "no_exhaustion"
            out["note"] = (ex.get("note") or "无背驰") + "; 低点不破 ZG"
    elif low30 >= zg * (1.0 - weak_tol):
        if exhausted:
            out["status"] = "weak"
            out["note"] = "30m 底背驰, 盘中轻微刺破 ZG(%.2f%% 以内)" % (
                weak_tol * 100.0)
        else:
            out["status"] = "no_exhaustion"
            out["note"] = (ex.get("note") or "无背驰") + "; 盘中轻微刺破 ZG"
    else:
        out["status"] = "broke"
        if exhausted:
            out["note"] = "30m 有背驰但低点跌破 ZG 超 %.2f%%, 三买结构存疑" % (
                weak_tol * 100.0)
        else:
            out["note"] = "30m 低点跌破 ZG 超 %.2f%%, 且无背驰" % (
                weak_tol * 100.0)
    return out


def confirm_sell3_30m(bars30, zd, zg, signal_dt,
                      zd_tol=0.01, weak_tol=0.02, stale_days=1,
                      min_prev_swing_ratio=None):
    """日线三卖 -> 30 分钟跨级别确认(镜像)

    反弹笔内部 30m 出现顶背驰, 且 30m 高点不升破 ZD(允许轻微刺破)。

    返回 dict:
        status: confirmed(强共振) / weak / no_exhaustion /
                broke(30m 升破 ZD, 三卖存疑) / stale / no_data
        + 明细字段 + high30 / dist_zd
    """
    out = {"status": "no_data", "note": "", "high30": None, "dist_zd": None}
    if not bars30:
        return out
    _, _, bis30 = chan_fx_bi(bars30)
    if len(bis30) < 2:
        out["note"] = "30m 笔不足, 无结构"
        return out

    ex = find_run_exhaustion(bis30, bars30, "up", signal_dt,
                             stale_days=stale_days,
                             min_prev_swing_ratio=min_prev_swing_ratio)
    out.update(ex)
    if ex["status"] in ("stale", "none"):
        return out

    high30 = ex["extreme"]
    out["high30"] = round(high30, 3)
    out["dist_zd"] = round((high30 - zd) / zd * 100.0, 3)
    exhausted = (ex["status"] == "ok")

    if high30 <= zd:
        if exhausted:
            out["status"] = "confirmed"
            out["note"] = "30m 顶背驰 + 高点不升破 ZD: 跨级别共振"
        else:
            out["status"] = "no_exhaustion"
            out["note"] = (ex.get("note") or "无背驰") + "; 高点不升破 ZD"
    elif high30 <= zd * (1.0 + weak_tol):
        if exhausted:
            out["status"] = "weak"
            out["note"] = "30m 顶背驰, 盘中轻微刺破 ZD(%.2f%% 以内)" % (
                weak_tol * 100.0)
        else:
            out["status"] = "no_exhaustion"
            out["note"] = (ex.get("note") or "无背驰") + "; 盘中轻微刺破 ZD"
    else:
        out["status"] = "broke"
        if exhausted:
            out["note"] = "30m 有背驰但高点升破 ZD 超 %.2f%%, 三卖结构存疑" % (
                weak_tol * 100.0)
        else:
            out["note"] = "30m 高点升破 ZD 超 %.2f%%, 且无背驰" % (
                weak_tol * 100.0)
    return out
