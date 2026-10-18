# -*- coding: utf-8 -*-
"""
chan.cross30 —— 日线事件与 30 分钟行情的两级辅助条件核对。

参考导航（维护者私有工作区）: doc/缠论知识库/04-背驰与区间套.md。
理论最终依据为 108 课原文；课 108/99 的导航关联和原文覆盖状态见实现计划。
本模块沿用既有工程规则，不将固定日线/30m 周期等同于理论相邻级别，
不由两级结果推断收益或可靠度。

输入: 调用方截断至观察时刻的 30m 行情，以及同标的、同复权基准的
日线事件、中枢边界或一类点价格。跨周期对齐、可用时间由调用方保证。
输出: 带 status、note 与力度/位置明细的 dict；空输入返回 no_data。
confirmed/weak 仅表示本模块条件满足，不等同于严格理论背驰或交易确认。

实现: 30m 行情识别笔，将连续同向笔合为 run，比较末段与前段的 DIF
摆动并要求端点创新极值；MACD 柱面积只作参考。三类点再核对中枢位置，
二类点采用分型和一类点价格规则，具体差异与参数见各函数 docstring。
weak_tol、stale_days、对照段幅度等为工程阈值，不冒充原文量化要求。

兼容: Python 3.6。依赖 chan.bi / chan.zs / chan.bc。
"""

from __future__ import print_function

import datetime

from typing import Any, Dict, List, Optional

from chan.bi import chan_fx_bi
from chan.zs import find_zs
from chan.bc import macd_series, segment_area, _dt_index


def _date_of(dt: Any) -> str:
    return str(dt)[:10]


def _days_diff(dt_a: Any, dt_b: Any) -> int:
    """两个时间点相差的自然日天数(dt_a - dt_b)"""
    da = datetime.datetime.strptime(_date_of(dt_a), "%Y-%m-%d")
    db = datetime.datetime.strptime(_date_of(dt_b), "%Y-%m-%d")
    return (da - db).days


def _group_runs(bis: List[Any]) -> List[Any]:
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


def find_run_exhaustion(bis30: List[Any], bars30: List[Dict[str, Any]],
                        run_dir: str, end_dt: Any, stale_days: int = 1,
                        min_prev_swing_ratio: Optional[float] = None) -> Dict[str, Any]:
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
        status: 'ok'(工程衰竭条件满足) / 'no_exhaustion'(无背驰) /
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


def confirm_buy3_30m(bars30: List[Dict[str, Any]], zd: float, zg: float,
                     signal_dt: Any,
                     zg_tol: float = 0.01, weak_tol: float = 0.02,
                     stale_days: int = 1,
                     min_prev_swing_ratio: Optional[float] = None) -> Dict[str, Any]:
    """日线三买 -> 30 分钟跨级别确认

    参数:
        bars30: 30m bars(升序, 拉到信号日为止)
        zd/zg: 日线中枢下/上沿(与 30m 同一前复权基准)
        signal_dt: 日线三买信号日(str 或 date)
        zg_tol: 保留参数(历史兼容, 当前判定不使用); confirmed 条件固定为
            30m 低点不破 ZG(low30 >= zg), 不设贴近容忍。
        weak_tol: 允许 30m 低点跌破 ZG 的比例(zg*(1-weak_tol) 以内算弱确认)
        stale_days: 30m 回抽段终点允许早于信号日的自然日数
        min_prev_swing_ratio: 前一对照段 DIF 摆动最小幅度(占价格中位数比例,
            默认 None = 不设门槛)

    返回 dict:
        status: confirmed(辅助条件满足) / weak(容差条件满足) / no_exhaustion(无背驰) /
                broke(30m 跌破 ZG, 三买存疑) / stale / none / no_data
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


def confirm_sell3_30m(bars30: List[Dict[str, Any]], zd: float, zg: float,
                      signal_dt: Any,
                      zd_tol: float = 0.01, weak_tol: float = 0.02,
                      stale_days: int = 1,
                      min_prev_swing_ratio: Optional[float] = None) -> Dict[str, Any]:
    """日线三卖 -> 30 分钟跨级别确认(镜像)

    反弹笔内部 30m 出现顶背驰, 且 30m 高点不升破 ZD(允许轻微刺破)。

    参数: 同 confirm_buy3_30m 镜像; zd_tol 为保留参数(历史兼容,
    当前判定不使用), confirmed 条件固定为 30m 高点不升破 ZD。

    返回 dict:
        status: confirmed(辅助条件满足) / weak / no_exhaustion /
                broke(30m 升破 ZD, 三卖存疑) / stale / none / no_data
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


def confirm_buy2_30m(bars30: List[Dict[str, Any]], buy1_price: float,
                     signal_dt: Any, stale_days: int = 1,
                     pierce_tol: float = 0.0) -> Dict[str, Any]:
    """二买轻量 30m 确认: 30m 底分型 + 回调低点不破一买低点

    二买没有"离开中枢"结构, 不套用三买的区间套背驰判定, 改用
    两条轻量确认: ①信号日窗口内 30m 出现底分型; ②该底分型低点
    (回调低点)不破日线一买低点(允许轻微刺破, 见 pierce_tol)。

    参数:
        bars30: 30m bars(升序, 拉到信号日为止)
        buy1_price: 日线一买(趋势底背驰)低点价格
        signal_dt: 日线二买信号日(str 或 date)
        stale_days: 底分型 dt 允许早于信号日的自然日数, 默认 1
            (30m 序列通常当日即可确认底分型; 个股日线级场景因合并K线
            取后一根 dt 的伪影, 实测建议放宽到 3)
        pierce_tol: 允许 30m 低点跌破一买低点的比例
            (默认 0 = 严格不破; 0.02 = 刺破 2% 以内算 weak)

    返回 dict:
        status: confirmed(底分型确认且不破一买低点) /
                weak(轻微刺破, pierce_tol 内) /
                broke(跌破一买低点超 pierce_tol, 二买结构失效) /
                stale(窗口内无底分型) / no_data
        + fx_dt / low30 / dist_b1(低点距一买低点的百分比) / note
    """
    out = {"status": "no_data", "note": "", "fx_dt": None,
           "low30": None, "dist_b1": None}
    if not bars30 or buy1_price is None:
        return out
    _, fxs30, _ = chan_fx_bi(bars30)
    if len(fxs30) < 1:
        out["note"] = "30m 分型不足, 无结构"
        return out

    # 窗口 [signal_dt - stale_days, signal_dt] 内最近一个底分型
    cand = None
    for fx in fxs30:
        if fx.kind != "bottom":
            continue
        diff = _days_diff(signal_dt, fx.dt)
        if 0 <= diff <= stale_days:
            if cand is None or str(fx.dt) >= str(cand.dt):
                cand = fx
    if cand is None:
        out["status"] = "stale"
        out["note"] = "信号日前 {0} 个自然日内无 30m 底分型, 未跟上".format(
            stale_days)
        return out

    low30 = cand.low
    out["fx_dt"] = str(cand.dt)
    out["low30"] = round(low30, 4)
    out["dist_b1"] = round((low30 - buy1_price) / buy1_price * 100.0, 3)

    if low30 >= buy1_price:
        out["status"] = "confirmed"
        out["note"] = "30m 底分型确认, 回调低点不破一买低点"
    elif low30 >= buy1_price * (1.0 - pierce_tol):
        out["status"] = "weak"
        out["note"] = "30m 底分型确认, 盘中轻微刺破一买低点({0:.2f}% 以内)".format(
            pierce_tol * 100.0)
    else:
        out["status"] = "broke"
        out["note"] = "30m 低点跌破一买低点超 {0:.2f}%, 二买结构失效".format(
            pierce_tol * 100.0)
    return out


def confirm_buy3_event_30m(evt: Dict[str, Any], bars30: List[Dict[str, Any]],
                           **kw: Any) -> Dict[str, Any]:
    """从 bs 模块的三买事件 dict 直接做 30m 跨级别确认(便捷桥接)

    参数:
        evt: chan.bs.find_buy_points 输出的 type=3 事件
             (读取 zs_zd/zs_zg/dt 字段)
        bars30 与其余参数同 confirm_buy3_30m。
    """
    if evt.get("zs_zd") is None or evt.get("zs_zg") is None:
        return {"status": "no_data", "note": "事件缺少中枢边界字段 zs_zd/zs_zg"}
    return confirm_buy3_30m(
        bars30,
        zd=evt.get("zs_zd"), zg=evt.get("zs_zg"),
        signal_dt=evt.get("pull_end_dt") or evt.get("dt"), **kw)


def confirm_sell3_event_30m(evt: Dict[str, Any], bars30: List[Dict[str, Any]],
                            **kw: Any) -> Dict[str, Any]:
    """从 bs 模块的三卖事件 dict 直接做 30m 跨级别确认(镜像桥接)"""
    if evt.get("zs_zd") is None or evt.get("zs_zg") is None:
        return {"status": "no_data", "note": "事件缺少中枢边界字段 zs_zd/zs_zg"}
    return confirm_sell3_30m(
        bars30,
        zd=evt.get("zs_zd"), zg=evt.get("zs_zg"),
        signal_dt=evt.get("pull_end_dt") or evt.get("dt"), **kw)
