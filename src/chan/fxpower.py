# -*- coding: utf-8 -*-
"""
chan.fxpower —— 分型力度判断: 三K线形态分类 + 有效破均线辅助判据

理论依据: 《教你炒股票 108 课》第 82 课「分型结构的心理因素」
(2007-09-24)与第 79 课「分型的辅助操作与一些问题的再解答」(2007-09-10)。

原文关键判据(课 82, 直接引文, 以顶分型为例, 底分型镜像):
    三次心理较量:
    「一个顶分型之所以成立, 是卖的分力最终战胜了买的分力, 而其中,
    买的分力有三次的努力, 而卖的分力, 有三次的阻击。」

    包含关系:
    「包含关系(只要不是直接把阳线以长阴线吃掉)意味着一种犹豫,
    一种不确定的观望」;「但这包含关系是直接把阳线以长阴线吃掉,
    是最坏的一种包含关系」。

    中继居多(意义不大):
    「如果第一 K 线是一长阳线, 而第二、三都是小阴、小阳, 那么这个
    分型结构的意义就不大了」「这种顶分型, 成为真正顶的可能性很小,
    绝大多数都是中继的。」

    力度较大(延续成笔可能性极大):
    「如果第二根 K 线是长上影甚至就是直接的长阴, 而第三根 K 线不能
    以阳线收在第二根 K 线区间的一半之上, 那么该顶分型的力度就比较大,
    最终要延续成笔的可能性就极大了。」

    最弱的一种(杀伤力较强):
    「非包含关系处理后的顶分型中, 第三根 K 线如果跌破第一根 K 线的底
    而且不能高收到第一根 K 线区间的一半之上, 属于最弱的一种, 也就是
    说这顶分型有着较强的杀伤力。」

    两种结构:
    「分型形成后, 无非两种结构: 一、成为中继型的, 最终不延续成笔;
    二、延续成笔。」

均线辅助判据(课 79, 直接引文):
    「如果顶分型后有效跌破 5日线, 那就没什么大戏了, 就算不用搞个笔
    出来, 也会用时间换空间, 折腾好一阵子」;
    「但如果没有有效跌破5日线, 那往往只是中继」;
    「000938, 20070904构成顶分型, 然后假突破5日线后继续上攻」
    (假突破 = 盘中触碰或未获确认的越线, 不算有效跌破)。

实现口径声明(与理论的差异/取舍):
    1. 「长阳/长阴/长上影/小阴小阳」原文未给出量化标准, 本模块以
       **三根 K 线的总区间**(max(high) - min(low))归一化:
       长实体 = |close - open| >= long_body x 总区间(默认 0.35);
       小实体 = |close - open| <= small_body x 总区间(默认 0.15);
       长上影(顶)/长下影(底) = b2 关键影线 >= shadow x 总区间
       (默认 0.25)。阈值均为参数, 可按级别/品种调整;
    2. severe 判据应用于无相邻包含的三K线, 与课82的非包含图例一致。
       分类优先级 severe > strong > weak > neutral: 原文三个案例
       (5/28-30、6/18-21、9/17-19)互不冲突, 但构造数据可能同时命中
       多案(如 K1 长阳而 K3 深破 K1 底), 以杀伤力最强者为准——力度
       判断取保守方向(宁可高估调整风险);
    3. 「一半之上」的口径: 区间中点 (high + low) / 2; 「高收」= 收盘价
       **严格高于**中点, 恰等于中点视为"未收上一半之上";
    4. 输入三根 K 线既可以是包含处理后的 NewBar(find_fxs 标准流程,
       bar_index 相邻三根), 也可以是原始 K 线(课 82 的包含关系讨论、
       课 79 的 600737 案例均为原始 K 线形态)。NewBar 的 open/close 为
       合并组近似(open 取组内首根 open, close 取末根 close, 见
       chan.fx), 原文形态案例为原始日线, 精细形态分析建议传原始 K 线。
       合并组首开末收落在形态区间之外时, 关键影线长度下限取0;
    5. 相邻两 K 线存在包含关系时 containment=True(课 82: 犹豫/观望);
       「阳线被长阴线整个吃掉」(顶)/「阴线被长阳整个吃掉」(底)标
       bad_containment 并把力度升档为不低于 strong(课 82 六月案例:
       最坏的一种包含关系)。包含处理后的 NewBar 序列相邻无包含,
       该标记仅在传入原始 K 线时可能为 True;
    6. 「有效跌破」原文未量化, 000938 案例表明盘中触碰与单日假突破
       不算 -> ma_break_state 只看**收盘价**, 需连续 confirm(默认 2)
       根收盘越线才判 effective; confirm=1 即"收盘越线即有效";
    7. 更精确的小级别确认(课 82: 「如果该5分钟中枢或1分钟中枢出现
       第三类卖点, 并该卖点不形成中枢扩张的情形, 那么几乎100%可以
       肯定, 一定在日线上要出现笔了」)与「中继分型, 有点类似刹车,
       一次不一定完全刹住, 但第一刹车后如果车速已明显减慢, 证明刹车
       系统是有效的, 那么第二次刹住的机会就极大了」的连刹逻辑, 以及
       课 79「大级别的分型和某小级别的第一、二买卖点并不是绝对的对应
       关系, 有前者一定有后者, 但有后者并不一定有前者, 所以前者只是
       一个辅助」——均依赖跨级别上下文, 本模块不实现, 由调用方组合
       chan.bs / chan.cross30 / chan.bc 使用;
    8. 课 79 建议「都至少用日线以上 K 线图上的分型」「那些变动太快
       的, 准确率就要大大有问题了」——本模块不限制 K 线级别, 级别
       选择由调用方负责。

兼容: Python 3.6, 仅标准库 + typing。
"""

from __future__ import print_function

import math
from numbers import Integral, Real
from typing import Any, Dict, List, Optional

from chan._series import _finite_number

__all__ = [
    "POWER_WEAK", "POWER_NEUTRAL", "POWER_STRONG", "POWER_SEVERE",
    "BREAK_NONE", "BREAK_TESTING", "BREAK_EFFECTIVE",
    "FxPowerResult", "MaBreakState",
    "classify_fx_power", "classify_fx", "ma_break_state",
]

# 三K线力度四分类(课 82, 以顶分型为例, 底分型镜像):
POWER_WEAK = "weak"          # 意义不大, 绝大多数中继
POWER_NEUTRAL = "neutral"    # 一般形态, 无明确倾向
POWER_STRONG = "strong"      # 力度较大, 延续成笔可能性极大
POWER_SEVERE = "severe"      # 最弱的一种, 杀伤力较强

# 分型后收盘价对均线的突破状态(课 79):
BREAK_NONE = "none"          # 从未出现收盘越线
BREAK_TESTING = "testing"    # 序列末端存在未确认的越线连续
BREAK_EFFECTIVE = "effective"  # 有效破位: 连续 confirm 根收盘越线


class FxPowerResult(object):
    """分型三K线力度分类结果(课 82)

    属性:
        direction: "top" / "bottom"(与 chan.fx.FX.kind 同口径)。
        power: POWER_WEAK / POWER_NEUTRAL / POWER_STRONG / POWER_SEVERE。
            顶分型语义: weak=中继居多 / neutral=无明确倾向 /
            strong=延续成笔可能性极大 / severe=杀伤力较强;
            底分型全部镜像(weak=中继居多 / severe=上攻力度较强)。
        reasons: list of str, 命中的判据说明(按判定顺序)。
        containment: 相邻两根 K 线(b1b2 或 b2b3)是否存在包含关系
            (课 82: 犹豫/不确定的观望)。
        bad_containment: 是否「直接把阳线以长阴线吃掉」(顶)/镜像
            (底)——课 82: 最坏的一种包含关系。
        metrics: dict, 判定所用的归一化指标(分母=三根K线总区间):
            k1_body / k2_body / k3_body: 三根 K 线实体占比;
            k2_shadow: b2 关键影线占比(顶=上影, 底=下影)。
    """

    __slots__ = ["direction", "power", "reasons", "containment",
                 "bad_containment", "metrics"]

    def __init__(self, direction: str, power: str, reasons: List[str],
                 containment: bool, bad_containment: bool,
                 metrics: Dict[str, float]) -> None:
        self.direction = direction
        self.power = power
        self.reasons = reasons
        self.containment = containment
        self.bad_containment = bad_containment
        self.metrics = metrics

    def __repr__(self) -> str:
        return "FxPowerResult({0} power={1})".format(
            self.direction, self.power)

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(存档/序列化用)"""
        return {
            "direction": self.direction,
            "power": self.power,
            "reasons": list(self.reasons),
            "containment": self.containment,
            "bad_containment": self.bad_containment,
            "metrics": dict(self.metrics),
        }


class MaBreakState(object):
    """分型后收盘价与参考均线(如 5 周期)的突破状态(课 79)

    属性:
        direction: "top"(监视收盘跌破均线) / "bottom"(监视收盘升破)。
        state: BREAK_NONE / BREAK_TESTING / BREAK_EFFECTIVE。
        ever_tested: 是否出现过收盘越线。
        recovered: 是否出现过「假突破」——收盘越线但未达 confirm 根即
            收回(课 79 的 000938: 假突破 5 日线后继续上攻, 往往中继)。
        break_idx: 首次收盘越线的下标(从未越线为 None)。
        confirm_idx: 达成「连续 confirm 根越线」的下标(未达成为 None)。
        streak: 序列末端连续越线根数(已确认后也计数, 0 = 末端未越线)。

    判读(课 79, 以顶分型 + 5 日线为例):
        state=effective -> 曾确认有效破位, 调整风险较高; 课79明确也可
            时间换空间, 此辅助条件不保证成笔;
        state=none 且 recovered=False -> 从未越线, 倾向中继;
        state=none 且 recovered=True -> 假突破后收回(000938), 倾向中继;
        state=testing -> 越线未确认, 等待后续 K 线。
    """

    __slots__ = ["direction", "state", "ever_tested", "recovered",
                 "break_idx", "confirm_idx", "streak"]

    def __init__(self, direction: str, state: str, ever_tested: bool,
                 recovered: bool, break_idx: Optional[int],
                 confirm_idx: Optional[int], streak: int) -> None:
        self.direction = direction
        self.state = state
        self.ever_tested = ever_tested
        self.recovered = recovered
        self.break_idx = break_idx
        self.confirm_idx = confirm_idx
        self.streak = streak

    def __repr__(self) -> str:
        return "MaBreakState({0} state={1} streak={2})".format(
            self.direction, self.state, self.streak)

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(存档/序列化用)"""
        return {
            "direction": self.direction,
            "state": self.state,
            "ever_tested": self.ever_tested,
            "recovered": self.recovered,
            "break_idx": self.break_idx,
            "confirm_idx": self.confirm_idx,
            "streak": self.streak,
        }


def _has_containment(a: Any, b: Any) -> bool:
    """相邻两 K 线包含关系: 一方高低点全在另一方范围内(标准定义)"""
    return ((a.high >= b.high and a.low <= b.low) or
            (b.high >= a.high and b.low <= a.low))


class _K(object):
    """内部 K 线视图: 统一对象属性 / dict 两种输入形态"""

    __slots__ = ["open", "high", "low", "close"]

    def __init__(self, open_: float, high: float, low: float,
                 close: float) -> None:
        self.open = open_
        self.high = high
        self.low = low
        self.close = close


def _as_k(bar: Any) -> _K:
    """bar -> _K: 支持 chan.fx.NewBar(属性访问)与原始 bar dict"""
    if isinstance(bar, dict):
        values = [bar[key] for key in ("open", "high", "low", "close")]
    else:
        values = [bar.open, bar.high, bar.low, bar.close]
    if any(isinstance(value, bool) or not isinstance(value, Real) or
           not math.isfinite(float(value)) for value in values):
        raise ValueError("OHLC 必须为有限数值")
    k = _K(*[float(value) for value in values])
    if k.high < k.low:
        raise ValueError("high 不能小于 low")
    # 原始实体须在区间内; NewBar 保留的首开末收为近似, 不套此条件。
    if isinstance(bar, dict) and not (k.low <= k.open <= k.high and
                                      k.low <= k.close <= k.high):
        raise ValueError("原始 OHLC 价格包络无效")
    return k


def _optional_number(value):
    """序列暖机/非有限值记为缺测; 错误的数值类型明确拒绝。"""
    return _finite_number(value)


def classify_fx_power(b1: Any, b2: Any, b3: Any, direction: str,
                      long_body: float = 0.35,
                      small_body: float = 0.15,
                      shadow: float = 0.25) -> FxPowerResult:
    """三K线分型力度四分类(课 82)

    理论依据(课 82, 以顶分型为例, 底分型镜像):
        severe: 「第三根 K 线如果跌破第一根 K 线的底而且不能高收到
            第一根 K 线区间的一半之上, 属于最弱的一种」;
        strong: 「如果第二根 K 线是长上影甚至就是直接的长阴, 而第三根
            K 线不能以阳线收在第二根 K 线区间的一半之上, 那么该顶分型
            的力度就比较大, 最终要延续成笔的可能性就极大了」;
        weak: 「如果第一 K 线是一长阳线, 而第二、三都是小阴、小阳,
            那么这个分型结构的意义就不大了」「绝大多数都是中继的」。

    参数:
        b1 / b2 / b3: 分型的左/中/右三根 K 线(时间升序), 需含
            open / high / low / close 属性——chan.fx.NewBar 或原始
            bar dict 均可。调用方提供已确认分型的上下文; 本函数只判断
            力度, 不代替分型识别。原始 dict 的 OHLC 须在价格包络内;
            NewBar 的首开末收为近似, 精细实体形态优先用原始行情。
        direction: "top" 顶分型 / "bottom" 底分型(与 FX.kind 同口径)。
        long_body: 长实体阈值(实体/三根K线总区间, 默认 0.35)。
        small_body: 小实体阈值(同上归一, 默认 0.15)。
        shadow: b2 关键影线阈值(顶=上影/底=下影, 同上归一, 默认 0.25)。

    返回: FxPowerResult(见类 docstring)。

    判定优先级: severe > strong > weak > neutral(口径声明第 2 条);
    bad_containment 可把 neutral/weak 升档为 strong(口径声明第 5 条)。

    边界行为:
        - 三根 K 线总区间为 0(高低点全部相同)返回 neutral;
        - direction 非 "top"/"bottom" 抛 ValueError;
        - 阈值须满足 0<=small_body<long_body<=1, 0<shadow<=1;
          OHLC非有限值/错误区间或原始行情的无效价格包络抛 ValueError。
    """
    if direction not in ("top", "bottom"):
        raise ValueError(
            "direction must be 'top' or 'bottom': {0!r}".format(direction))
    # 长/小/影线阈值为明示的工程参数, 不把无效比例当成理论判据。
    for name, value in (("long_body", long_body), ("small_body", small_body),
                        ("shadow", shadow)):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("{} 必须为有限比例".format(name))
    if not (0 <= small_body < long_body <= 1 and 0 < shadow <= 1):
        raise ValueError("须满足 0<=small_body<long_body<=1, 0<shadow<=1")

    # 统一输入形态(NewBar 对象 / 原始 bar dict -> 内部 _K 视图)
    b1 = _as_k(b1)
    b2 = _as_k(b2)
    b3 = _as_k(b3)

    # ---- 包含关系标记(课 82, 与力度分类独立) ----
    containment = _has_containment(b1, b2) or _has_containment(b2, b3)

    hi3 = max(b1.high, b2.high, b3.high)
    lo3 = min(b1.low, b2.low, b3.low)
    range3 = hi3 - lo3

    if range3 <= 0.0:
        # 三根K线高低点全部相同: 退化为一个价位, 无形态可言
        return FxPowerResult(
            direction, POWER_NEUTRAL, ["三根K线总区间为0, 无形态可言"],
            containment, False,
            {"k1_body": 0.0, "k2_body": 0.0, "k3_body": 0.0,
             "k2_shadow": 0.0})

    # ---- 归一化指标(分母 = 三根K线总区间, 口径声明第 1 条) ----
    r1 = abs(b1.close - b1.open) / range3
    r2 = abs(b2.close - b2.open) / range3
    r3 = abs(b3.close - b3.open) / range3
    if direction == "top":
        # 顶分型: 看中间K线的上影(卖分力阻击留下的痕迹)
        sh2 = max(0.0, b2.high - max(b2.open, b2.close)) / range3
    else:
        # 底分型: 看中间K线的下影(买分力阻击留下的痕迹)
        sh2 = max(0.0, min(b2.open, b2.close) - b2.low) / range3
    metrics = {"k1_body": r1, "k2_body": r2, "k3_body": r3,
               "k2_shadow": sh2}

    # 「一半之上」的区间中点(口径声明第 3 条)
    mid1 = (b1.high + b1.low) / 2.0
    mid2 = (b2.high + b2.low) / 2.0

    reasons: List[str] = []
    power = POWER_NEUTRAL

    if direction == "top":
        # severe: K3 跌破 K1 的底且收盘收不回 K1 区间一半之上
        # (课 82: 属于最弱的一种, 杀伤力较强)
        if not containment and b3.low < b1.low and b3.close <= mid1:
            power = POWER_SEVERE
            reasons.append(
                "K3跌破K1的底且收盘未收上K1区间一半(最弱的一种, 杀伤力较强)")
        # strong: K2 长上影甚至直接长阴, 且 K3 不能以阳线收在
        # K2 区间一半之上(课 82: 力度较大, 延续成笔可能性极大)
        elif ((sh2 >= shadow or (b2.open > b2.close and r2 >= long_body))
                and not (b3.close > b3.open and b3.close > mid2)):
            power = POWER_STRONG
            reasons.append(
                "K2长上影或长阴且K3未以阳线收上K2区间一半"
                "(力度较大, 延续成笔可能性极大)")
        # weak: K1 长阳 + K2/K3 小阴小阳(课 82: 意义不大, 绝大多数中继)
        elif (b1.close > b1.open and r1 >= long_body
                and r2 <= small_body and r3 <= small_body):
            power = POWER_WEAK
            reasons.append(
                "K1长阳而K2/K3小实体(分型意义不大, 绝大多数中继)")
    else:
        # 底分型: 全部镜像(课 82: 「底分型的情况, 反过来就是」)
        # severe: K3 升破 K1 的顶且收盘收不回 K1 区间一半之下
        if not containment and b3.high > b1.high and b3.close >= mid1:
            power = POWER_SEVERE
            reasons.append(
                "K3升破K1的顶且收盘未收回K1区间一半之下(最强的一种, "
                "上攻力度较强)")
        # strong: K2 长下影甚至直接长阳, 且 K3 不能以阴线收在
        # K2 区间一半之下
        elif ((sh2 >= shadow or (b2.close > b2.open and r2 >= long_body))
                and not (b3.close < b3.open and b3.close < mid2)):
            power = POWER_STRONG
            reasons.append(
                "K2长下影或长阳且K3未以阴线收下K2区间一半"
                "(力度较大, 延续成笔可能性极大)")
        # weak: K1 长阴 + K2/K3 小实体
        elif (b1.close < b1.open and r1 >= long_body
                and r2 <= small_body and r3 <= small_body):
            power = POWER_WEAK
            reasons.append(
                "K1长阴而K2/K3小实体(分型意义不大, 绝大多数中继)")

    # ---- 「最坏的一种包含关系」(课 82 六月案例, 口径声明第 5 条) ----
    # 顶: 长阴线整个吃掉前一根阳线; 底: 长阳线整个吃掉前一根阴线。
    bad_containment = False
    if direction == "top":
        for prev, cur, rcur in ((b1, b2, r2), (b2, b3, r3)):
            if (prev.close > prev.open and cur.open > cur.close
                    and cur.high >= prev.high and cur.low <= prev.low
                    and rcur >= long_body):
                bad_containment = True
    else:
        for prev, cur, rcur in ((b1, b2, r2), (b2, b3, r3)):
            if (prev.close < prev.open and cur.close > cur.open
                    and cur.high >= prev.high and cur.low <= prev.low
                    and rcur >= long_body):
                bad_containment = True

    if bad_containment:
        if power in (POWER_NEUTRAL, POWER_WEAK):
            power = POWER_STRONG
        reasons.append(
            "包含关系为'阳线被长阴线整个吃掉'一类(最坏的一种包含关系)")

    if containment and not bad_containment:
        reasons.append("相邻K线存在包含关系(课82: 犹豫/不确定的观望)")

    if not reasons:
        reasons.append("无明确形态倾向")

    return FxPowerResult(direction, power, reasons, containment,
                         bad_containment, metrics)


def classify_fx(fx: Any, new_bars: List[Any],
                long_body: float = 0.35, small_body: float = 0.15,
                shadow: float = 0.25) -> FxPowerResult:
    """对 find_fxs 输出的分型做力度分类(便捷入口)

    取 new_bars[bar_index-1 : bar_index+2] 三根合并 K 线, 以 fx.kind
    为方向调用 classify_fx_power。

    参数:
        fx: chan.fx.FX(find_fxs 输出)。
        new_bars: 与 find_fxs 相同的无包含 K 线序列(remove_includes
            输出), fx.bar_index 基于它。

    返回: FxPowerResult。

    边界行为: fx.bar_index 越界(不在 [1, len-2])抛 ValueError——
    find_fxs 正常输出不会越界, 此为防御。
    """
    i = fx.bar_index
    if isinstance(i, bool) or not isinstance(i, Integral) or i < 1 or i + 2 > len(new_bars):
        raise ValueError(
            "fx.bar_index 越界: {0} (len(new_bars)={1})".format(
                i, len(new_bars)))
    return classify_fx_power(new_bars[i - 1], new_bars[i], new_bars[i + 1],
                             fx.kind, long_body, small_body, shadow)


def ma_break_state(closes: List[float], mas: List[Optional[float]],
                   direction: str, confirm: int = 2) -> MaBreakState:
    """分型后收盘价对均线的突破状态判定(课 79「有效跌破」)

    理论依据(课 79): 「如果顶分型后有效跌破 5日线, 那就没什么大戏了,
    就算不用搞个笔出来, 也会用时间换空间, 折腾好一阵子」「但如果没有
    有效跌破5日线, 那往往只是中继」; 000938 案例(「假突破5日线后继续
    上攻」)表明盘中触碰与未获确认的越线不算有效跌破。

    参数:
        closes: 收盘价序列(分型右侧 K 线**之后**的 K 线, 按 dt 升序;
            即只统计分型形成后的走势, 分型三根 K 线本身不参与)。
        mas: 与 closes 等长的参考均线序列(如 5 周期均线, 可用
            chan.strength.sma_series(closes_all, 5) 计算后按同样
            下标对齐截取)。元素可为 None(均线暖机期)——该下标不做
            判定, 并打断进行中的越线连续(保守处理)。
        direction: "top" 顶分型 -> 监视收盘**跌破**均线;
            "bottom" 底分型 -> 监视收盘**升破**均线(镜像)。
        confirm: 判定 effective 所需的连续收盘越线根数(默认 2,
            即连续两根收盘越线才算有效破位; 1 = 收盘越线即有效)。

    返回: MaBreakState(见类 docstring)。

    判定规则(以顶分型为例):
        - 收盘 < 均线记一次越线; 连续越线达 confirm 根 -> state=
          effective(曾确认有效跌破, 也可能时间换空间而不成笔; 一旦
          达成保持该历史事实不变, 其后
          收回不改写历史——课 79: 「那就没什么大戏了」);
        - 越线后未达 confirm 根即收盘收回 -> recovered=True(假突破,
          000938 口径, 往往中继);
        - 序列结束时仍有 1 <= 连续 < confirm 根越线 -> state=testing;
        - 从未越线 -> state=none。

    边界行为:
        - closes 与 mas 长度不等抛 ValueError; confirm < 1 抛
          ValueError; direction 非法抛 ValueError;
        - closes/mas 中 None、NaN、inf 均视为缺测, 打断连续确认;
          bool/字符串等错误数值类型抛 ValueError。
    """
    if direction not in ("top", "bottom"):
        raise ValueError(
            "direction must be 'top' or 'bottom': {0!r}".format(direction))
    if isinstance(confirm, bool) or not isinstance(confirm, Integral) or confirm < 1:
        raise ValueError("confirm must be >= 1: {0!r}".format(confirm))
    if len(closes) != len(mas):
        raise ValueError(
            "closes 与 mas 长度不等: {0} vs {1}".format(
                len(closes), len(mas)))

    down = (direction == "top")  # 顶分型: 监视收盘跌破; 底分型: 升破
    ever_tested = False
    recovered = False
    break_idx = None      # 首次收盘越线
    confirm_idx = None    # 达成连续 confirm 根越线
    run = 0               # 当前连续越线根数

    for i in range(len(closes)):
        c = _optional_number(closes[i])
        ma = _optional_number(mas[i])
        if c is None or ma is None:
            # 无数据下标不判定; 进行中的越线连续无法确认延续,
            # 保守按中断处理(不计假突破——与"收盘收回"不同, 此处
            # 只是观测缺失)
            run = 0
            continue
        beyond = (c < ma) if down else (c > ma)
        if beyond:
            run += 1
            if not ever_tested:
                ever_tested = True
                break_idx = i
            if run >= confirm and confirm_idx is None:
                # 有效破位达成(其后走势不改写该事实)
                confirm_idx = i
        else:
            if 0 < run < confirm:
                # 收盘越线但未达 confirm 根即收回 = 假突破(000938)
                recovered = True
            run = 0

    if confirm_idx is not None:
        state = BREAK_EFFECTIVE
    elif run > 0:
        state = BREAK_TESTING
    else:
        state = BREAK_NONE

    return MaBreakState(direction, state, ever_tested, recovered,
                        break_idx, confirm_idx, run)
