# -*- coding: utf-8 -*-
"""
chan.bars —— 行情数据归一化

把聚宽 get_price / get_bars 返回的 DataFrame 转成标准的 bar 序列
(list of dict), 供缠论管线(分型/笔/线段)使用。

兼容: Python 3.6, pandas 0.23
"""

from __future__ import print_function

# 标准 bar 字段
BAR_KEYS = ["dt", "open", "high", "low", "close", "volume"]


def normalize_bars(df, dt_col="date", open_col="open", high_col="high",
                   low_col="low", close_col="close", volume_col="volume",
                   drop_paused=True):
    """DataFrame -> 按时间升序的标准 bar 列表

    参数:
        df: get_price/get_bars 返回的 DataFrame(单标的)
        dt_col 等: 列名映射(聚宽默认列名即默认参数)
        drop_paused: 丢弃停牌(成交量=0 且高低价持平)的 bar

    返回:
        list of dict, 每项含 dt/open/high/low/close/volume;
        dt 为原类型(datetime/Timestamp), 排序后保证时间递增。
    """
    if df is None or df.shape[0] == 0:
        return []

    # 时间列: get_bars 返回 date 列; get_price 返回时间为 index
    use_index_dt = (dt_col not in df.columns)

    price_cols = [open_col, high_col, low_col, close_col, volume_col]
    for c in price_cols:
        if c not in df.columns:
            raise ValueError("缺少列: {}".format(c))

    cols = price_cols
    if use_index_dt:
        out = df[cols].copy()
        out.insert(0, "dt", df.index)
    else:
        out = df[[dt_col] + cols].copy()
        out.columns = ["dt"] + price_cols
    out.columns = BAR_KEYS
    out = out.sort_values("dt")
    # 数值化
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = out[c].astype(float)

    bars = out.to_dict(orient="records")
    if drop_paused:
        bars = [b for b in bars
                if not (b["volume"] == 0 and b["high"] == b["low"])]
    return bars


def bars_to_df(bars):
    """bar 列表 -> DataFrame(测试与展示用)"""
    import pandas as pd
    return pd.DataFrame(bars)
