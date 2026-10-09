# -*- coding: utf-8 -*-
"""走势结构的两重表里关系(课 91/93/99)

课 91「走势结构的两重表里关系 1」的理论内核——缠中说禅笔定理:
    "任何的当下,任何在不在的走势中的任何在,都唯一地对应着当下的
    一个确定方向的笔当中"——当下位置只有两种:
    0 = 分型构造中 / 1 = 分型确认后延伸为笔的过程中。
    由 (方向 d=±1, 位置 e=0/1) 构成四状态数组:
        (1,1)   向上笔延伸中
        (-1,1)  向下笔延伸中
        (1,0)   向上笔中顶分型构造中
        (-1,0)  向下笔中底分型构造中
    四状态连接约束(本模块以 BI_TRANSITIONS 显式落表):
        (1,1) -> 只能 (1,0);  (-1,1) -> 只能 (-1,0);
        (1,0) -> (1,1) 或 (-1,1);  (-1,0) -> (1,1) 或 (-1,1)。

课 91 双级别病情矩阵:高级别与低级别状态组合刻画"未病-欲病-已病"
的演进(界限即相应级别的第一、二、三类买卖点),并给出下跌走势的
四档恶劣排序(周/日线为例,镜像适用于上涨的"踏空病"):
    第 1 最恶劣  高(-1,1) 低(-1,1)
    第 2 次恶劣  高(-1,1) 低(-1,0)
    第 3 恶劣    高(-1,0) 低(-1,1)
    第 4 转机窗  高(-1,0) 低(-1,0)
本模块以 disease_stage(high, low, trend) 把 4x4=16 种组合映射为
10 个阶段标签,severity 由 SEVERITY_RANKS 落表。

课 93「走势结构的两重表里关系 2」:(1,0)/(-1,0) 之后都有 (1,1) 与
(-1,1) 两种可能;若对应走势明确背驰结束,则其后的震荡区间"以上涨
的最后一个中枢为依据":围绕该中枢 = 强震荡,跌出 = 弱震荡(将向
(-1,1) 发展)。本模块以 followup_quality() 落地"围绕最后中枢"判强
弱。(1,0) 区间上下两段的 (1,1) 力度比较属"趋势力度"范畴,由力度
模块(课 15)承接,不在本模块。

课 99「走势结构的两重表里关系 3」:连接中枢的走势级别一定小于中
枢,任何走势类型完成后必然面临至少大一级别的中枢震荡(中阴);且
"后续的更大级别中枢震荡,必然至少要落在前一走势类型的最后一个中
枢范围里"——落在最后中枢内 = 健康的中阴,回到第二甚至更后的中枢
= 不健康/危险。本模块以 zhongyin_health() 落地该判据(结构标签,
不预设多空方向:原文明言"危险是相对的,对原下跌走势的中阴危险,
就是意味着回升的力度够强,对多头意味着好事情")。
"""

from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "bi_state",
    "BI_TRANSITIONS",
    "bi_transition_valid",
    "disease_stage",
    "SEVERITY_RANKS",
    "followup_quality",
    "zhongyin_health",
]

# ---------------------------------------------------------------------------
# 课 91:笔定理四状态
# ---------------------------------------------------------------------------

#: 四状态连接约束(课 91):键/值均为 (d, e) 元组。
#: (1,1) 与 (-1,1) 只能转入分型构造;分型构造的结局只有两种——
#: 延伸确认回原方向 (d,1),或反转确认 (-d,1)。
BI_TRANSITIONS: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {
    (1, 1): ((1, 0),),
    (-1, 1): ((-1, 0),),
    (1, 0): ((1, 1), (-1, 1)),
    (-1, 0): ((1, 1), (-1, 1)),
}


def bi_state(bi_direction: str,
             fx_forming: Optional[str]) -> Optional[Tuple[int, int]]:
    """(课 91 笔定理)当下笔状态 (d, e)

    参数:
        bi_direction: 当下延伸中的笔方向, 'up' / 'down'。
        fx_forming: 尾部反向分型候选, None(无)/ 'top'(顶分型)/
            'bottom'(底分型)。
            - None: 笔仍在延伸, 无反向分型;
            - 与笔反向的分型候选: 分型构造中(e=0);
            - 与笔同向的分型候选: 说明反向分型已被后续走势确认、
              新笔已展开(如向上笔后出现底分型 = 顶分型已确认、
              向下笔延伸中), 返回新笔 (d', 1)。

    返回:
        (d, e): d=+1 向上 / -1 向下; e=1 延伸为笔中 / 0 分型构造中。
        bi_direction 非法时返回 None。

    映射表:
        up   + None      -> (1, 1)    向上笔延伸中
        up   + 'top'     -> (1, 0)    顶分型构造中(课 91: 顶分型
                                      构造意味着上涨告一段落的可能)
        up   + 'bottom'  -> (-1, 1)   向下笔延伸中(顶分型已确认)
        down + None      -> (-1, 1)   向下笔延伸中
        down + 'bottom'  -> (-1, 0)   底分型构造中
        down + 'top'     -> (1, 1)    向上笔延伸中(底分型已确认)
    """
    if bi_direction not in ("up", "down"):
        return None
    if fx_forming is not None and fx_forming not in ("top", "bottom"):
        return None
    if bi_direction == "up":
        if fx_forming == "top":
            return (1, 0)
        if fx_forming == "bottom":
            return (-1, 1)
        return (1, 1)
    # bi_direction == "down"
    if fx_forming == "bottom":
        return (-1, 0)
    if fx_forming == "top":
        return (1, 1)
    return (-1, 1)


def bi_transition_valid(prev: Tuple[int, int],
                        nxt: Tuple[int, int]) -> bool:
    """(课 91 连接约束)状态 prev 之后出现 nxt 是否合法

    (1,1)->(1,0)、(-1,1)->(-1,0) 为唯一去向;分型构造的结局只有
    "延伸确认回原方向"或"反转确认"两种。prev 或 nxt 不在四状态
    集合中时返回 False。
    """
    if prev not in BI_TRANSITIONS or nxt not in ((1, 1), (-1, 1), (1, 0), (-1, 0)):
        return False
    return nxt in BI_TRANSITIONS[prev]


# ---------------------------------------------------------------------------
# 课 91:双级别病情矩阵
# ---------------------------------------------------------------------------

#: 下跌四档恶劣排序(课 91, 以周/日线为例; 上涨"踏空病"镜像适用):
#: 数值越小越恶劣, 第 4 档为"可能出现转机"的窗口。
SEVERITY_RANKS: Dict[str, int] = {
    "sick_worst": 1,      # 高(-1,1) 低(-1,1) 最恶劣
    "sick_second": 2,     # 高(-1,1) 低(-1,0) 次恶劣
    "sick_third": 3,      # 高(-1,0) 低(-1,1) 第三恶劣
    "turn_window": 4,     # 高(-1,0) 低(-1,0) 第四: 可能出现转机
}


def disease_stage(high: Tuple[int, int],
                  low: Tuple[int, int],
                  trend: int) -> Optional[str]:
    """(课 91 病情矩阵)双级别状态 -> 病情阶段标签

    参数:
        high: 高级别 (d, e) 状态。
        low: 低级别 (d, e) 状态。
        trend: 被监控的原趋势方向, +1(监控上涨之病, 病=下跌) /
            -1(监控下跌之病, 病=上涨/踏空)。

    返回:
        以下 10 个标签之一(16 种组合归并为 10 档; 输入非法返回 None):

        "healthy"        未病: 高低级别均沿原趋势延伸
        "warning"        未病预警: 低级别出现分型构造(小警告, 若仅
                         出现在单根高级别K线内不足以破坏结构)
        "prodromal"      欲病: 低级别反向笔延伸(低级别 (d,0) 已确认,
                         重要警告成立, 高级别 (t,0) 将形成)
        "critical"       关键位: 高级别分型构造中, 低级别重新沿原
                         趋势延伸(欲病未确认; 走强可回 (t,1))
        "onset"          欲病向已病发展: 高级别分型构造中且低级别
                         反向笔延伸(高级别 (t,0) 确认向 (-t,1) 发展)
        "sick_worst"     已病, 恶劣排序第 1 档(高(-t,1) 低(-t,1))
        "sick_second"    已病, 第 2 档(高(-t,1) 低(-t,0))
        "sick_third"     已病, 第 3 档(高(-t,0) 低(-t,1))
        "turn_window"    已病第 4 档: 可能出现转机的窗口
                         (高(-t,0) 低(-t,0))
        "recovering"     修复中: 高级别已反向但低级别重新沿原趋势
                         延伸(修复尝试, 高级别反向笔面临结束)
    """
    valid_states = ((1, 1), (-1, 1), (1, 0), (-1, 0))
    if high not in valid_states or low not in valid_states:
        return None
    if trend not in (1, -1):
        return None
    hd, he = high
    ld, le = low
    if hd == trend:
        # 高级别仍沿原趋势: 未病 -> 欲病
        if he == 1:
            if ld == trend:
                # 低级别同向: 延伸 = 未病, 分型构造 = 小警告(课 91:
                # "1 分钟出现 (1,0) 是一个小的警告")
                return "healthy" if le == 1 else "warning"
            # 低级别反向: 欲病(低级别反向笔已展开, 重要警告成立)
            return "prodromal"
        # he == 0: 高级别分型构造中(关键窗口)
        if ld == trend:
            # 低级别重新同向: 欲病未确认, 可回 (t,1)
            return "critical"
        # 低级别反向延伸: 欲病向已病发展
        return "onset"
    # hd == -trend: 高级别已反向(已病区间), 按四档恶劣排序/修复归类
    if hd == -trend and he == 1:
        if ld == -trend:
            return "sick_worst" if le == 1 else "sick_second"
        return "recovering"
    # he == 0: 高级别反向笔的分型构造中(转机窗)
    if ld == -trend:
        return "sick_third" if le == 1 else "turn_window"
    return "recovering"


# ---------------------------------------------------------------------------
# 课 93:(1,0)/(-1,0) 之后的震荡强弱(以最后中枢为依据)
# ---------------------------------------------------------------------------

def followup_quality(zd: float, zg: float,
                     unit_low: float, unit_high: float,
                     direction: str) -> Optional[str]:
    """(课 93)分型构造后的回抽/震荡段强弱——以上涨(下跌)的最后一个
    中枢 [zd, zg] 为依据

    参数:
        zd / zg: 原走势最后一个中枢的下沿/上沿。
        unit_low / unit_high: (1,0)/(-1,0) 之后的震荡段(次级别回抽
            单元)区间。
        direction: 原走势方向, 'up' / 'down'。

    返回:
        "strong"   围绕最后中枢(与 [zd, zg] 有重叠, 端点触及算重叠)
                   ——课 93: "只要围绕着该区间, 就是强的震荡";
        "weak"     跌出(升破)中枢区间——弱震荡, 将向 (-1,1)((1,1))
                   发展, "一般一旦确认, 最好还是不参与";
        "reverse"  完全位于中枢顺趋势一侧——分型构造失败, 原走势
                   恢复延伸(回到 (1,1)/(-1,1));
        输入非法返回 None。
    """
    if direction not in ("up", "down"):
        return None
    if zg < zd:
        # 容错: 上下沿颠倒时自动纠正
        zd, zg = zg, zd
    if unit_high < zd or unit_low > zg:
        overlap = False
    else:
        overlap = True
    if overlap:
        return "strong"
    if direction == "up":
        # 向上走势: 震荡段整体在中枢下方 = 弱; 上方 = 顶分型失败
        if unit_high < zd:
            return "weak"
        return "reverse"
    # 向下走势镜像: 震荡段整体在中枢上方 = 弱; 下方 = 底分型失败
    if unit_low > zg:
        return "weak"
    return "reverse"


# ---------------------------------------------------------------------------
# 课 99:中阴阶段健康度(更大级别中枢震荡落点)
# ---------------------------------------------------------------------------

def zhongyin_health(prev_centers: List[Any],
                    new_center: Any) -> Optional[str]:
    """(课 99)中阴健康度:后续更大级别中枢震荡 vs 前一走势类型的中枢序列

    课 99 必然结论: "任何一个后续的更大级别中枢震荡, 必然至少要落
    在前一走势类型的最后一个中枢范围里"——落点正常 = 健康的中阴;
    一旦回到第二甚至更后的中枢, 对应的中阴状态不健康/危险。

    参数:
        prev_centers: 前一走势类型的中枢序列, 按时间顺序, 每项为
            (zd, zg) 二元组或带 zd/zg 属性的对象(如 zs.ZS)。
        new_center: 中阴阶段出现的中枢震荡, 同上格式。

    返回:
        "healthy"    与最后一个中枢有重叠(端点触及算重叠)——正常的
                     中阴状态;
        "dangerous"  与最后中枢无重叠, 但与更早的某个中枢重叠——
                     不健康/危险(注意原文: 危险是相对的, 对原下跌
                     走势的危险 = 回升力度强 = 对多头有利);
        "extreme"    与全部前中枢均无重叠——已脱离"必然至少落在最后
                     中枢范围里"的常态, 结构划分需重审;
        prev_centers 为空返回 None。
    """
    if not prev_centers:
        return None

    def _rng(c: Any) -> Tuple[float, float]:
        # 兼容 (zd, zg) 二元组与 ZS 对象两种输入
        if isinstance(c, (tuple, list)) and len(c) >= 2:
            return (float(c[0]), float(c[1]))
        return (float(getattr(c, "zd")), float(getattr(c, "zg")))

    nzd, nzg = _rng(new_center)

    def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        # 端点触及算重叠(与包内 _overlap_center 同口径)
        return not (a[1] < b[0] or a[0] > b[1])

    # 先看最后一个中枢(课 99 的"关键指标位置")
    lzd, lzg = _rng(prev_centers[-1])
    if _overlap((nzd, nzg), (lzd, lzg)):
        return "healthy"
    # 回到第二甚至更后的中枢 = 不健康/危险
    for c in prev_centers[:-1]:
        czd, czg = _rng(c)
        if _overlap((nzd, nzg), (czd, czg)):
            return "dangerous"
    return "extreme"
