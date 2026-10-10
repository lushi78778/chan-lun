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

import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from numbers import Real
from typing import Any, Dict, List

# 标准 bar 字段(顺序即 normalize_bars 输出列序)
BAR_KEYS = ["dt", "open", "high", "low", "close", "volume"]


def _bar_time(dt):
    """校验当前算法可安全按 str(dt) 比较的时间表示。"""
    if dt is None or dt != dt:
        raise ValueError("dt 不能为空或 NaT")
    if isinstance(dt, datetime):
        # 固定 UTC 偏移使字符串排序与时间先后保持一致。
        return dt, ("datetime", dt.utcoffset())
    if isinstance(dt, date):
        return dt, ("date",)
    if isinstance(dt, str):
        match = re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?:([ T])\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)?", dt)
        if match is None:
            raise ValueError("字符串 dt 必须为 ISO 日期或带秒的 ISO 时间")
        separator = match.group(1)
        if separator is None:
            return datetime.strptime(dt, "%Y-%m-%d"), ("str", "date")
        fmt = "%Y-%m-%d" + separator + "%H:%M:%S"
        if "." in dt:
            fmt += ".%f"
        return datetime.strptime(dt, fmt), ("str", separator)
    raise ValueError("dt 必须为 date/datetime/Timestamp 或 ISO 字符串")


def validate_bars(bars: List[Dict[str, Any]]) -> None:
    """检查单标的、单周期的原始 OHLCV 序列, 不修改、排序或去重。

    输入为 list/tuple of mapping, 每行含 BAR_KEYS。OHLC 为有限正数,
    volume 为有限非负数, low <= open/close <= high。正价格约束对应
    本库买卖点力度的价格比例计算, 不是所有金融工具的通用假设。
    空序列合法; 数字字符串须先经 normalize_bars 数值化。

    dt 严格递增且唯一, 同序列使用同一种时间表示。支持 date、datetime、
    pandas Timestamp, 或 YYYY-MM-DD / YYYY-MM-DD[ T]HH:MM:SS[.微秒]
    字符串。datetime 的 UTC 偏移须一致; 字符串时间不带时区。调用方
    先统一时区, 以保证现有算法的 str(dt) 比较与真实时间先后相符。

    数量单位、复权基准、标的、周期及 K 线是否收盘由调用方保证。
    此校验只用于原始行情; NewBar 的包含合并区间不能按原始 OHLC 校验。

    异常: TypeError = 容器类型错误; ValueError = 带行号的数据错误。
    """
    if not isinstance(bars, (list, tuple)):
        raise TypeError("bars 必须为标准 bar 的 list 或 tuple")
    previous_time = None
    previous_kind = None
    for index, bar in enumerate(bars):
        try:
            if not isinstance(bar, Mapping):
                raise ValueError("每行必须为含 BAR_KEYS 的 mapping")
            missing = [key for key in BAR_KEYS if key not in bar]
            if missing:
                raise ValueError("缺少字段: {}".format(", ".join(missing)))
            current_time, current_kind = _bar_time(bar["dt"])
            if previous_kind is not None:
                if current_kind != previous_kind:
                    raise ValueError("dt 类型、字符串格式及 UTC 偏移须一致")
                if current_time <= previous_time:
                    raise ValueError("dt 必须严格递增, 不能重复或乱序")
            values = {}
            for key in BAR_KEYS[1:]:
                value = bar[key]
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise ValueError("{} 必须为数值".format(key))
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError("{} 必须为有限数值".format(key))
                if (key == "volume" and value < 0) or (key != "volume" and value <= 0):
                    raise ValueError("价格须为正数, volume 须为非负数")
                values[key] = value
            if not (values["low"] <= values["open"] <= values["high"] and
                    values["low"] <= values["close"] <= values["high"]):
                raise ValueError("OHLC 须满足 low <= open/close <= high")
            previous_time, previous_kind = current_time, current_kind
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError("bars[{}]: {}".format(index, error)) from error


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
    # 时间已成为 dt 列; 丢弃原索引避免命名索引 dt 与列 dt 排序歧义。
    out = out.reset_index(drop=True)
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
