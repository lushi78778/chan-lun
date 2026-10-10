# -*- coding: utf-8 -*-
"""均线吻系统(课 11/12)

课 11「不会吻, 无以高潮」的完全分类:
    "任何两条均线的关系, 其实就是一个'吻'的问题。按'吻'的标准,
    可以把相应的关系进行一个完全分类: 飞吻、唇吻、湿吻。"
        飞吻: 短期均线略略走平后继续按原来趋势进行下去;
        唇吻: 短期均线靠近长期均线但不跌破或升破, 然后按原来
              趋势继续下去;
        湿吻: 短期均线跌破或升破长期均线甚至出现反复缠绕。
    体位: 短期在上 = 女上位(多头市场, 本模块记 "up"); 短期在下
    = 男上位(空头市场, 记 "down")。

课 12「一吻何能消魂」的操作语境(本模块只提供判定原料):
    "对于任种走势, 首要判断的是体位"——alignment_series;
    "女上位趋势出现的第一次缠绕是中继的可能性极大, 如果是第三、
    四次出现, 这个缠绕是转折的可能性就会加大"——KissEvent 的
    kiss_index(体位段内计数, 体位转化后清零);
    "出现第一次缠绕前, 5 日线的走势必须是十分有力的"——pre_gain
    (吻前一段短均线的趋势方向相对涨幅, 越大越"有力");
    "缠绕出现前的成交量不能放得过大"——vol_leg / vol_prior
    (吻前段/更前段的均量, 由调用方比较);
    两个买点(男上位最后一次缠绕后背驰的空头陷阱 / 女上位第一次
    缠绕的低位)需要价格级背驰配合, 不在本模块判定范围, 由调用
    方以 KissEvent 原料 + chan.bc 组合。

操作化口径(原文未量化的边界, 本模块以可调参数近似, 均在参数中
注明默认值):
    1. 吻 = 差值(短-长)自极值回撤、再创新极值(或体位转化)的一
       次完整过程; 回撤深度不足峰值差值 min_depth(默认 0.2)的
       微扰不构成吻;
    2. 湿吻 = 回撤期间差值触零或穿零(触零即相交, 与课 15 吻边界
       口径一致), crossings 记录穿越/触及次数(反复缠绕);
    3. 唇吻 = 未触零但最近距离 <= proximity(默认 0.5) x 峰值差值;
       其余为飞吻;
    4. 体位转化确认 = 差值反向行程 >= flip_confirm(默认 0.5) x
       原方向峰值差值(转化前的最后一次湿吻 resumed=False)。

判断只涉及两条均线(与任何技术指标无关); 吻的中继/转折属性由
resumed 字段给出(同体位新极值 = 中继; 体位转化 = 转折)。
"""

from typing import Any, Dict, List, Optional

from chan._series import _diff_series

__all__ = [
    "KISS_FLY",
    "KISS_LIP",
    "KISS_WET",
    "ALIGN_UP",
    "ALIGN_DOWN",
    "KissEvent",
    "alignment_series",
    "find_kisses",
    "classify_kiss",
]

KISS_FLY = "fly"    # 飞吻
KISS_LIP = "lip"    # 唇吻
KISS_WET = "wet"    # 湿吻
ALIGN_UP = "up"     # 女上位(短在上)
ALIGN_DOWN = "down"  # 男上位(短在下)


def classify_kiss(crossings: int, min_gap: float, peak_gap: float,
                  proximity: float = 0.5) -> str:
    """吻三分类(课 11; 纯函数)

    参数:
        crossings: 差值触零/穿零次数(>=1 即湿吻);
        min_gap: 回撤期间 |短-长| 的最小值(最近距离);
        peak_gap: 回撤起点的峰值差值;
        proximity: 唇吻的靠近判定比例。

    返回:
        KISS_WET / KISS_LIP / KISS_FLY。
    """
    if crossings > 0:
        return KISS_WET
    if min_gap <= proximity * peak_gap:
        return KISS_LIP
    return KISS_FLY


class KissEvent(object):
    """一次吻事件(课 11 完全分类 + 课 12 判定原料)

    属性:
        kind: KISS_FLY / KISS_LIP / KISS_WET;
        direction: 宿主体位——ALIGN_UP(女上位)/ALIGN_DOWN(男上位);
        start_idx: 吻前峰值差值所在序号(回撤起点);
        end_idx: 吻了结序号(同体位新极值 / 体位转化确认 / 数据耗尽);
        leg_start_idx: 吻前一段(腿)的起点序号(pre_gain/量的区间);
        kiss_index: 当前体位段内第几次吻(1 起; 体位转化后清零);
        peak_gap: 回撤起点的峰值差值 |短-长|;
        min_gap: 回撤期间 |短-长| 最小值;
        depth: 趋势符号口径的回撤深度(含穿零行程);
        crossings: 触零/穿零次数(反复缠绕);
        resumed: True=同体位新极值(中继) / False=体位转化或未了结;
        open: True=数据耗尽时吻未了结(kind 为 provisional 判定);
        pre_gain: 吻前腿短均线的趋势方向相对涨幅(除以长均线值;
            None=长均线值为 0 不可归一), 课 12 "有力"判定的原料;
        vol_leg / vol_kiss / vol_prior: 吻前腿 / 回撤段 / 更前段均量
            (volumes 未提供时为 None; 区间内无有效量亦为 None)。
    """

    __slots__ = ["kind", "direction", "start_idx", "end_idx",
                 "leg_start_idx", "kiss_index", "peak_gap", "min_gap",
                 "depth", "crossings", "resumed", "open", "pre_gain",
                 "vol_leg", "vol_kiss", "vol_prior"]

    def __init__(self, kind: str, direction: str, start_idx: int,
                 end_idx: int, leg_start_idx: int, kiss_index: int,
                 peak_gap: float, min_gap: float, depth: float,
                 crossings: int, resumed: bool, open_: bool,
                 pre_gain: Optional[float],
                 vol_leg: Optional[float], vol_kiss: Optional[float],
                 vol_prior: Optional[float]):
        self.kind = kind
        self.direction = direction
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.leg_start_idx = leg_start_idx
        self.kiss_index = kiss_index
        self.peak_gap = peak_gap
        self.min_gap = min_gap
        self.depth = depth
        self.crossings = crossings
        self.resumed = resumed
        self.open = open_
        self.pre_gain = pre_gain
        self.vol_leg = vol_leg
        self.vol_kiss = vol_kiss
        self.vol_prior = vol_prior

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用)"""
        return {
            "kind": self.kind,
            "direction": self.direction,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "leg_start_idx": self.leg_start_idx,
            "kiss_index": self.kiss_index,
            "peak_gap": self.peak_gap,
            "min_gap": self.min_gap,
            "depth": self.depth,
            "crossings": self.crossings,
            "resumed": self.resumed,
            "open": self.open,
            "pre_gain": self.pre_gain,
            "vol_leg": self.vol_leg,
            "vol_kiss": self.vol_kiss,
            "vol_prior": self.vol_prior,
        }


def alignment_series(short: Any, long: Any) -> List[Optional[str]]:
    """逐体位状态序列(课 12 "首要判断的是体位")

    参数:
        short / long: 短/长均线序列(元素数值或 None, 暖机位 None)。

    返回:
        与公共长度等长的列表: ALIGN_UP(短在上=女上位) /
        ALIGN_DOWN(短在下=男上位) / None(暖机或差值恒零无先例)。
        差值恰为零的位视为原体位的瞬时接触(触零即相交属吻事件,
        见 find_kisses; 逐棒体位沿用前一有效状态)。
    """
    diffs = _diff_series(short, long)
    out: List[Optional[str]] = []
    prev: Optional[str] = None
    for d in diffs:
        if d is None:
            out.append(None)
            continue
        if d > 0:
            prev = ALIGN_UP
        elif d < 0:
            prev = ALIGN_DOWN
        out.append(prev)
    return out


def _mean(values: List[Any]) -> Optional[float]:
    """均值(过滤 None/NaN, 空则 None; 内部工具)"""
    acc = []
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
        except TypeError:
            continue
        if f != f:  # NaN
            continue
        acc.append(f)
    if not acc:
        return None
    return sum(acc) / float(len(acc))


def _vol_at(volumes: Any, i: int) -> Optional[float]:
    """取第 i 棒的量(越界/缺值 -> None; 内部工具)"""
    if volumes is None or i < 0 or i >= len(volumes):
        return None
    return volumes[i]


def _leg_pre_gain(short: Any, long: Any, leg_start: int,
                  peak_idx: int, trend: int) -> Optional[float]:
    """吻前腿的趋势方向相对涨幅(课 12 "缠绕前走势必须十分有力"原料)

    pre_gain = trend x (短[峰] - 短[腿起]) / 长均线值(腿起点),
    归一到价格尺度; 长均线值为 0 时返回 None。
    """
    base = long[leg_start]
    if base is None or float(base) == 0.0:
        return None
    delta = float(short[peak_idx]) - float(short[leg_start])
    return trend * delta / float(base)


def find_kisses(short: Any, long: Any, volumes: Any = None,
                proximity: float = 0.5, min_depth: float = 0.2,
                flip_confirm: float = 0.5) -> List[KissEvent]:
    """吻事件序列(课 11 完全分类; 课 12 中继/转折判定)

    参数:
        short / long: 短/长均线序列(等长或取公共长度; 元素数值或
            None——sma_series 暖机位 None 自动跳过);
        volumes: 可选的成交量序列(供 vol_leg/vol_kiss/vol_prior);
        proximity: 唇吻靠近判定比例(默认 0.5);
        min_depth: 吻的最小回撤深度比例(相对峰值差值, 默认 0.2),
            更浅的微扰不构成吻;
        flip_confirm: 体位转化确认比例(反向行程达峰值差值的该
            比例即确认转化, 默认 0.5)。

    返回:
        List[KissEvent], 按时间序。吻 = 差值自峰值回撤至同体位新
        极值(中继, resumed=True)或体位转化确认(转折, resumed=
        False)的完整过程; 数据耗尽时未了结的吻 open=True。差值
        单调不回撤或数据不足时返回 []。
    """
    diffs = _diff_series(short, long)
    first = -1
    for i, d in enumerate(diffs):
        if d is not None:
            first = i
            break
    if first < 0 or first >= len(diffs) - 1:
        return []

    events: List[KissEvent] = []
    trend = 1 if diffs[first] > 0 else -1
    t_peak = abs(float(diffs[first]))   # 趋势符号口径的峰值差值
    e_idx = first                       # 峰值差值所在序号
    leg_start = first                   # 吻前腿起点
    run_start = first                   # 当前体位段起点
    run_kiss = 0                        # 体位段内已成立吻计数
    in_kiss = False
    k_min_td = 0.0   # 回撤期间最小趋势符号差值(可穿零为负)
    k_min_gap = 0.0  # 回撤期间 |短-长| 最小值
    k_cross = 0
    k_start = -1
    prev_td = t_peak

    def _emit(end_i: int, resumed: bool, open_: bool) -> None:
        kind = classify_kiss(k_cross, k_min_gap, t_peak, proximity)
        depth = t_peak - k_min_td
        vol_leg = _mean([_vol_at(volumes, j)
                         for j in range(leg_start, k_start + 1)])
        vol_kiss = _mean([_vol_at(volumes, j)
                          for j in range(k_start + 1, end_i + 1)])
        vol_prior = None
        if leg_start > run_start:
            vol_prior = _mean([_vol_at(volumes, j)
                               for j in range(run_start, leg_start)])
        events.append(KissEvent(
            kind, "up" if trend > 0 else "down", k_start, end_i,
            leg_start, run_kiss + 1, t_peak, k_min_gap, depth,
            k_cross, resumed, open_,
            _leg_pre_gain(short, long, leg_start, k_start, trend),
            vol_leg, vol_kiss, vol_prior))

    last_i = first
    for i in range(first + 1, len(diffs)):
        d = diffs[i]
        if d is None:
            break  # 无效位: 数据耗尽
        td = trend * float(d)
        last_i = i
        if not in_kiss:
            if td >= t_peak:
                # 同体位新极值: 峰值前移
                t_peak = td
                e_idx = i
                prev_td = td
                continue
            # 回撤开始: 开启一次吻
            in_kiss = True
            k_start = e_idx
            k_min_td = td
            k_min_gap = abs(float(d))
            k_cross = 1 if td <= 0 else 0
            prev_td = td
            continue
        # 吻进行中: 累计回撤形态
        if (prev_td > 0 and td <= 0) or (prev_td <= 0 and td > 0):
            k_cross += 1
        if td < k_min_td:
            k_min_td = td
        if abs(float(d)) < k_min_gap:
            k_min_gap = abs(float(d))
        prev_td = td
        if td > t_peak:
            # 同体位新极值: 吻以中继了结(课 11 "按原来趋势继续")
            depth = t_peak - k_min_td
            if depth < min_depth * t_peak:
                # 微扰不构成吻: 视为峰值延续
                in_kiss = False
                t_peak = td
                e_idx = i
                continue
            _emit(i, True, False)
            run_kiss += 1
            in_kiss = False
            t_peak = td
            e_idx = i
            leg_start = i
            continue
        if -td >= flip_confirm * t_peak:
            # 体位转化确认: 吻以转折了结(必然为湿吻)
            _emit(i, False, False)
            trend = -trend
            run_kiss = 0
            in_kiss = False
            t_peak = -td
            e_idx = i
            leg_start = i
            run_start = i
            prev_td = t_peak
            continue
    # 数据耗尽: 未了结且深度足够的吻以 open 收尾
    if in_kiss and (t_peak - k_min_td) >= min_depth * t_peak:
        _emit(last_i, False, True)
    return events
