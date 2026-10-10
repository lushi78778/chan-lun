# -*- coding: utf-8 -*-
"""批量分析门面: 组合既有算法, 将结构与信号按级别命名返回。

本模块是工程接线层, 理论与判定规则见各算法模块。每次只分析调用方
提供的行情前缀, 没有全局缓存、取数或策略执行。兼容 Python 3.6。
"""

from collections import namedtuple
from copy import deepcopy
from typing import Any, Dict, List

from chan.bars import BAR_KEYS, validate_bars
from chan.bi import MIN_K_GAP, chan_fx_bi
from chan.xd import find_xds
from chan.zs import classify_trend, find_zs
from chan.bc import find_pan_bc, find_trend_bc, macd_series
from chan.bs import find_buy_points, find_sell_points


_Result = namedtuple("AnalysisResult", [
    "as_of", "new_bars", "fxs", "bis", "xds", "bi_zss", "xd_zss",
    "bi_trends", "trend_bc", "pan_bc", "buy_points", "sell_points",
    "dif", "dea", "hist",
])


class AnalysisResult(_Result):
    """一次批量计算的命名结果, 字段不可重新绑定。

    as_of: 最后一根输入 bar 的 dt; 空输入为 None。它标识输入截止,
        不代表每个结构的确认时间, 也不证明输入 K 线已经收盘。
    new_bars/fxs/bis/xds: 包含处理、分型、笔和线段的现有对象列表。
    bi_zss/xd_zss: 笔级与线段级中枢; bi_trends 为笔级走势分类。
    trend_bc/pan_bc/buy_points/sell_points: 现有笔级候选与事件列表。
    dif/dea/hist: 与原始 bars 等长的 MACD 数组, 参数 12/26/9。

    列表、数组与结构对象仍可由结果持有者修改; 每次计算独立分配,
    不与输入行情或其他计算共享状态。to_dict 生成独立的 JSON 可写快照。
    """

    __slots__ = ()

    def to_dict(self) -> Dict[str, Any]:
        """生成 JSON 可写的深拷贝; 保留各算法原有字段与数值精度。"""
        output = {"as_of": None if self.as_of is None else str(self.as_of)}
        for field in ("new_bars", "fxs", "bis", "xds", "bi_zss", "xd_zss"):
            records = [item.to_dict() for item in getattr(self, field)]
            # NewBar.to_dict 保留原始 dt, 在此只转换快照的表示。
            if field == "new_bars":
                for record in records:
                    record["dt"] = str(record["dt"])
            output[field] = records
        for field in ("bi_trends", "trend_bc", "pan_bc", "buy_points", "sell_points"):
            output[field] = getattr(self, field)
        for field in ("dif", "dea", "hist"):
            output[field] = getattr(self, field).tolist()
        return deepcopy(output)


def analyze_bars(bars: List[Dict[str, Any]],
                 min_k_gap: int = MIN_K_GAP) -> AnalysisResult:
    """标准原始行情 -> AnalysisResult, 按现有默认规则进行批量分析。

    DataFrame 先用 normalize_bars 转换; 本入口执行 validate_bars,
    再独立复制 OHLCV。成笔间隔 min_k_gap 为非负整数, 默认 3,
    含义与 chan_fx_bi 一致。需要自定义 MACD/信号参数或其他理论辅助
    系统时, 使用各模块函数组合, 避免在此复制全部算法参数。

    笔级中枢只与笔级背驰、买卖点相连; 线段级中枢另行返回。
    MACD 只计算一次并传给两类背驰函数。无数据时返回各字段为空的结果。
    未完成尾部会随输入前缀变化, 历史回放应逐日前缀重算。
    """
    validate_bars(bars)
    if isinstance(min_k_gap, bool) or not isinstance(min_k_gap, int) or min_k_gap < 0:
        raise ValueError("min_k_gap 必须为非负整数")
    raw = [{key: (bar[key] if key == "dt" else float(bar[key]))
            for key in BAR_KEYS} for bar in bars]
    new_bars, fxs, bis = chan_fx_bi(raw, min_k_gap=min_k_gap)
    xds = find_xds(bis)
    bi_zss = find_zs(bis)
    xd_zss = find_zs(xds)
    dif, dea, hist = macd_series(raw)
    trend_bc = find_trend_bc(bis, bi_zss, raw, hist=hist)
    pan_bc = find_pan_bc(bis, bi_zss, raw, hist=hist)
    return AnalysisResult(
        raw[-1]["dt"] if raw else None, new_bars, fxs, bis, xds, bi_zss, xd_zss,
        classify_trend(bi_zss), trend_bc, pan_bc,
        find_buy_points(bis, bi_zss, trend_bc),
        find_sell_points(bis, bi_zss, trend_bc), dif, dea, hist,
    )
