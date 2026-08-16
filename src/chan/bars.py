# -*- coding: utf-8 -*-
"""
chan.bars —— 行情数据归一化

把聚宽 get_price / get_bars 等行情接口返回的 DataFrame 转成标准的
bar 序列(list of dict), 供缠论管线(分型/笔/线段/中枢/背驰/买卖点)使用。

标准 bar 字段(BAR_KEYS): dt / open / high / low / close / volume。
    - dt 保留原类型(datetime / pandas Timestamp / str 均可),
      管线内部统一按 str(dt) 做时间比较, 因此同一序列的 dt 格式必须一致;
    - 数量单位、复权方式由调用方决定, 本模块只做"列名映射 + 排序 + 数值化",
      不做任何价格变换。

兼容: Python 3.6, pandas 0.23。
"""

from __future__ import print_function

from typing import Any, Dict, List

# 标准 bar 字段(顺序即 normalize_bars 输出列序)
BAR_KEYS = ["dt", "open", "high", "low", "close", "volume"]


def normalize_bars(df: Any, dt_col: str = "date", open_col: str = "open",
                   high_col: str = "high", low_col: str = "low",
                   close_col: str = "close", volume_col: str = "volume",
                   drop_paused: bool = True) -> List[Dict[str, Any]]:
    """DataFrame -> 按时间升序的标准 bar 列表

    参数:
        df: 行情 DataFrame(单标的)。时间列既可以是列(dt_col 指定),
            也可以在 index 上(此时忽略 dt_col, 直接取 index 作 dt)。
            默认列名即聚宽 get_price / get_bars 返回列名, 其他数据源
            可用 *_col 参数做列名映射。
        dt_col: 时间列名; 若该列不存在则回退使用 index。
        open_col / high_col / low_col / close_col / volume_col:
            OHLCV 各列名映射。
        drop_paused: True = 丢弃停牌 bar(成交量=0 且高低价持平)。
            停牌日无成交、无波动, 直接剔除可以避免污染后续包含处理。

    返回:
        list of dict, 每项含 dt/open/high/low/close/volume 六键,
        按 dt 升序; OHLCV 已数值化(float), dt 为原类型。

    异常:
        ValueError: OHLCV 任一列在 df 中不存在且无法映射。
        (空输入/空 DataFrame 返回 [])

    用法示例:
        bars = normalize_bars(df)                        # 聚宽默认列名
        bars = normalize_bars(df2, dt_col="datetime")    # 自定义时间列
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


def bars_to_df(bars: List[Dict[str, Any]]) -> Any:
    """标准 bar 列表 -> DataFrame(测试与展示用)

    参数:
        bars: normalize_bars 的输出(或结构相同的 dict 列表)。

    返回:
        pandas DataFrame, 列 = BAR_KEYS。此函数才懒加载 pandas,
        normalize_bars 本身不 import pandas(保持对 Duck-type 输入的兼容)。
    """
    import pandas as pd
    return pd.DataFrame(bars)
