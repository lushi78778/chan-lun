# -*- coding: utf-8 -*-
"""课106: 本轮反弹的均线类别与板块强弱算术平均。

原文按“本次反弹目前为止未曾攻克的最小周期均线”分类, 八条均线
分九类; 板块成员类别数的平均值越大越强。曾攻克后回落不降类,
不能用当下价格之上的均线数量替代本轮反弹的历史状态。

工程口径: “攻克”量化为连续 confirm 根收盘严格高于同期均线,
默认 confirm=1, 原文未规定根数。周期默认5/13/21/34/55/89/144/233,
可按走势选其他周期。反弹起点由调用方显式给定, 不回看未来找底。
缺测不当作未攻克, 无法确定最小未攻克线时类别为None; 均值提供
覆盖率, 不把未知成员填第1类。只提供识别结果, 不调仓或判买卖点。

原书398页的600578图注类别6与正文类别7存在差异; 本模块依照
分类定义计算, 不将个别历史图示的类别数字硬编码为验收结论。
"""

from collections import namedtuple
import math
from numbers import Integral
from typing import Any, Mapping, Sequence

from chan._series import _finite_number


MA_PERIODS = (5, 13, 21, 34, 55, 89, 144, 233)


class MaClassResult(namedtuple("MaClassResultBase",
                              "class_no periods states conquered_at start_index end_index confirm")):
    """不可变类别结果, 按周期升序的 states=True/False/None。

    True=本轮已攻克; False=观察区间完整且未攻克; None=存在缺测,
    尚不能证明未攻克。conquered_at 为首次达到确认根数的原始下标。
    第一条非True状态若False则类别为其序号(1起), 若None则未知;
    全部True则为 len(periods)+1。高周期未知不否定已知低周期阻挡。
    """
    __slots__ = ()

    @property
    def unconquered_period(self):
        if self.class_no is None or self.class_no > len(self.periods):
            return None
        return self.periods[self.class_no - 1]

    def to_dict(self):
        return {"class_no": self.class_no,
                "unconquered_period": self.unconquered_period,
                "period_states": [{"period": period, "conquered": state,
                                   "confirmed_index": index}
                                  for period, state, index in
                                  zip(self.periods, self.states, self.conquered_at)],
                "start_index": self.start_index, "end_index": self.end_index,
                "confirm": self.confirm}


class SectorStrength(namedtuple("SectorStrengthBase",
                               "mean_class valid_count total_count coverage distribution periods confirm")):
    """等权算术均值与覆盖率; distribution 是第1..N+1类有效计数。

    无有效成员时 mean_class=None; 空板块 coverage=0。
    不同周期系统或攻克确认口径不可直接平均, 消费函数会拒绝混合。
    """
    __slots__ = ()

    def to_dict(self):
        return {"mean_class": self.mean_class, "valid_count": self.valid_count,
                "total_count": self.total_count, "coverage": self.coverage,
                "distribution": list(self.distribution),
                "periods": list(self.periods), "confirm": self.confirm}


def _periods(periods):
    values = tuple(periods)
    if not values or any(isinstance(n, bool) or not isinstance(n, Integral)
                         or n < 1 for n in values):
        raise ValueError("周期须为非空正整数序列")
    if any(left >= right for left, right in zip(values, values[1:])):
        raise ValueError("周期须严格递增且唯一")
    return tuple(int(n) for n in values)


def _parameters(length, start_index, confirm):
    if (isinstance(start_index, bool) or not isinstance(start_index, Integral)
            or not 0 <= start_index <= length):
        raise ValueError("start_index 须为0..序列长度的整数")
    if isinstance(confirm, bool) or not isinstance(confirm, Integral) or confirm < 1:
        raise ValueError("confirm 须为正整数")


def _prices(values):
    numbers = [_finite_number(value) for value in values]
    if any(value is not None and value <= 0 for value in numbers):
        raise ValueError("收盘/均线须为正数或缺测")
    return numbers


def classify_ma_strength(closes: Sequence[Any], ma_by_period: Mapping[int, Sequence[Any]],
                         start_index: int, confirm: int = 1) -> MaClassResult:
    """已给定同期均线时, 按本轮历史攻克状态分类(课106)。

    closes 与各周期均线等长, 时间顺序与周期由调用方保证; 均线不得
    居中或使用未来数据。MA字典键为周期, 自动按数值升序(不靠键顺序)。
    start_index 明确本轮反弹开始的原始下标, 可等于长度表示尚无观察。
    只读取该下标至末尾的攻克证据, 之前攻克不沿用。
    缺测(None/NaN/inf)打断连续确认, 已攻克状态保留, 未攻克状态变未知。
    """
    if not isinstance(ma_by_period, Mapping):
        raise ValueError("ma_by_period 须为周期到序列的映射")
    try:
        periods = _periods(sorted(ma_by_period))
    except TypeError as error:
        raise ValueError("周期须为可排序的正整数") from error
    prices = _prices(closes)
    _parameters(len(prices), start_index, confirm)
    lines = {}
    for period in periods:
        lines[period] = _prices(ma_by_period[period])
        if len(lines[period]) != len(prices):
            raise ValueError("所有均线须与收盘序列等长")
    states, indices = [], []
    for period in periods:
        streak, missing, conquered = 0, False, None
        for i in range(start_index, len(prices)):
            price, ma = prices[i], lines[period][i]
            if price is None or ma is None:
                missing, streak = True, 0
            elif price > ma:
                streak += 1
                if streak >= confirm and conquered is None:
                    conquered = i
            else:
                streak = 0
        states.append(True if conquered is not None else
                      None if missing or start_index == len(prices) else False)
        indices.append(conquered)
    class_no = len(periods) + 1
    for i, state in enumerate(states):
        if state is not True:
            class_no = i + 1 if state is False else None
            break
    return MaClassResult(class_no, periods, tuple(states), tuple(indices),
                         int(start_index), len(prices) - 1 if prices else None, int(confirm))


def ma_strength_class(closes: Sequence[Any], start_index: int,
                      periods: Sequence[int] = MA_PERIODS,
                      confirm: int = 1) -> MaClassResult:
    """从原始收盘因果SMA生成类别(课106), 不先截断均线暖机历史。

    每周期使用当前及之前的完整窗口; 前n-1位与含缺测窗口为None,
    不填充。start_index只裁定本轮攻克统计起点, 前置收盘仍参与SMA。
    必须在相同周期、复权基准和明确反弹起点下比较成员类别。
    """
    periods = _periods(periods)
    prices = _prices(closes)
    _parameters(len(prices), start_index, confirm)
    lines = {}
    for n in periods:
        line = []
        for i in range(len(prices)):
            window = prices[i - n + 1:i + 1] if i >= n - 1 else []
            if len(window) != n or any(v is None for v in window):
                line.append(None)
            elif all(v == window[0] for v in window):
                line.append(window[0])  # 常价均线保持相等, 不产生舍入假突破。
            else:
                try:
                    line.append(math.fsum(window) / n)
                except OverflowError:
                    line.append(math.fsum(v / n for v in window))
        lines[n] = line
    return classify_ma_strength(prices, lines, start_index, confirm)


def sector_strength(members: Mapping[str, MaClassResult]) -> SectorStrength:
    """板块成员类别等权平均(课106), 以唯一标的键避免重复计数。

    输入标的标识->MaClassResult, 必须同周期系统、同confirm。
    调用方确保同观察时刻、同反弹定义与复权口径(下标不能证明日期相同)。
    未知类别排除分子分母, 通过 coverage/total_count 暴露缺失; 没有
    有效成员不返回0。空板块 periods=(), confirm=None。
    """
    if not isinstance(members, Mapping):
        raise ValueError("members 须为唯一标的到类别结果的映射")
    periods, confirm, valid, distribution = (), None, [], []
    for code, result in members.items():
        if not isinstance(code, str) or not code.strip() or not isinstance(result, MaClassResult):
            raise ValueError("成员须使用非空标的字符串和 MaClassResult")
        if not periods:
            periods, confirm = result.periods, result.confirm
            _periods(periods)
            _parameters(0, 0, confirm)
            distribution = [0] * (len(periods) + 1)
        if (result.periods, result.confirm) != (periods, confirm):
            raise ValueError("成员须采用相同周期系统与攻克确认口径")
        cls = result.class_no
        if cls is not None:
            if isinstance(cls, bool) or not isinstance(cls, Integral) or not 1 <= cls <= len(periods) + 1:
                raise ValueError("无效成员类别")
            valid.append(int(cls))
            distribution[cls - 1] += 1
    count, total = len(valid), len(members)
    return SectorStrength(sum(valid) / float(count) if count else None,
                          count, total, count / float(total) if total else 0.0,
                          tuple(distribution), periods, confirm)
