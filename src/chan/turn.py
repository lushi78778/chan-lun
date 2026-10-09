# -*- coding: utf-8 -*-
"""背驰-转折定理(缠中说禅技术理论 第 29 课)

课 29 原文(定理):

    "缠中说禅背驰-转折定理: 某级别趋势的背驰将导致该趋势最后一个
    中枢的级别扩展、该级别更大级别的盘整或该级别以上级别的反趋势。"

即某级别趋势背驰(第一类买/卖点)后, 完全分类为三种结果:

    一、该趋势最后一个中枢的级别扩展——最弱反弹: 反弹只触及最后
        一个中枢的 DD(下跌情形)/GG(上涨情形), 未重新回到中枢区间
        [ZD, ZG] 内, 最后中枢将扩展成更大级别中枢;
    二、该级别更大级别的盘整——反弹至少重新回抽到最后一个中枢里,
        "下跌+盘整", 盘整的中枢级别一定大于下跌中的中枢级别;
    三、该级别以上级别的反趋势——"下跌+上涨", 上涨中枢不一定大于
        下跌中枢。

判别关键(课 29 明示):

    "关键就是看反弹中第 1 个前趋势最后一个中枢级别的次级别走势
    (例如前面的下跌是 5 分钟级别, 就看 1 分钟级别的第 1 次反弹),
    是否重新回抽最后一个中枢里, 如果不能, 那第一种情况的可能就很
    大了, 而且也证明反弹的力度值得怀疑"(有效性很大但非绝对; 原文
    备注: 第一次次级别回抽即使回到中枢, 也有可能是级别扩展)。

第一波回抽回到中枢只排除第一种最弱情况, 二/三之间的区分要看后续
演化(课 29: "关键看突破第一个中枢后是否形成第三类买点"), 由调用
方结合中枢/买卖点模块判定, 本模块返回 candidates 候选。

端点触及口径与包内一致: 端点相等算触及/覆盖。
"""

from typing import Any, Dict, List, Optional

__all__ = [
    "TURN_EXPANSION", "TURN_BREAK", "TURN_SUB_FLOOR",
    "TURN_CANDIDATES", "classify_bc_turn", "guaranteed_rebound_gap",
]

# 结果一: 该趋势最后一个中枢的级别扩展(最弱反弹, 只触及 DD/GG)
TURN_EXPANSION = "expansion"
# 结果二/三: 转折(第一波回抽重新回到最后中枢里)
#     二/三的进一步区分要看后续演化, 见 TURN_CANDIDATES
TURN_BREAK = "turn"
# 反弹/回落连 DD/GG 都触及不到——定理保证"反弹一定达到 DD 之上",
# 该情形在理论完备分类之外, 标记供调用方核查(次级别单元未走完/
# 数据不完整/中枢识别有误)
TURN_SUB_FLOOR = "sub_floor"

# 转折(二/三)的两种候选: 更大级别盘整 / 该级别以上级别的反趋势
TURN_CANDIDATES: List[str] = ["consolidation", "counter_trend"]


def _center_bounds(center: Any) -> tuple:
    """取中枢四界 (zd, zg, gg, dd), 兼容 ZS 实例与鸭子对象。"""
    zd = float(center.zd)
    zg = float(center.zg)
    gg = float(center.gg)
    dd = float(center.dd)
    return zd, zg, gg, dd


def classify_bc_turn(center: Any, first_pull: Any,
                     trend: str) -> Dict[str, Any]:
    """背驰-转折定理三分类(课 29)

    对某级别趋势背驰后的第一波次级别回抽/反弹分类:

    参数:
        center: 趋势最后一个中枢(需有 zd/zg/gg/dd 属性, 如 chan.ZS)
        first_pull: 第一波次级别回抽/反弹单元(需有 low/high 属性,
            笔/线段/走势类型通吃)
        trend: 被背驰趋势的方向——
            "down" = 下跌趋势背驰(第一类买点后, first_pull 为反弹);
            "up"   = 上涨趋势背驰(第一类卖点后, first_pull 为回落)。

    返回(dict):
        kind: TURN_EXPANSION / TURN_BREAK / TURN_SUB_FLOOR;
        candidates: kind==TURN_BREAK 时的两种候选
            (["consolidation", "counter_trend"]), 其余为 [];
        note: 中文说明。

    分类规则(trend="down", 反弹端点 high):
        high >= ZG   -> TURN_BREAK(回抽进中枢, 最弱情况排除);
        DD <= high < ZG -> TURN_EXPANSION(只触及 DD, 最后中枢级别
            扩展, 课 29 "背弛后最弱的反弹");
        high < DD    -> TURN_SUB_FLOOR(定理保证之外, 供核查)。
    trend="up" 镜像(回落端点 low, ZG/GG 与 ZD/DD 互换)。
    """
    zd, zg, gg, dd = _center_bounds(center)
    if trend == "down":
        # 下跌背驰后看反弹高点(第一波次级别反弹)
        high = float(first_pull.high)
        if high >= zg:
            # 课 29: "反弹至少要重新触及最后一个中枢, 这样, 将发生转折"
            return {
                "kind": TURN_BREAK,
                "candidates": list(TURN_CANDIDATES),
                "note": ("第一波次级别反弹回到最后中枢区间, 最弱情况"
                         "(级别扩展)基本排除; 更大级别盘整或该级别以"
                         "上反趋势, 区分看突破后是否第三类买点"),
            }
        if high >= dd:
            # 课 29: "只触及最后一个中枢的 DD=min(dn)的反弹, 就是背弛
            # 后最弱的反弹, 将把最后一个中枢变成一个级别上的扩展"
            return {
                "kind": TURN_EXPANSION,
                "candidates": [],
                "note": ("反弹只触及最后中枢 DD 未回区间, 最后中枢将"
                         "级别扩展(最弱反弹), 反弹力度值得怀疑"),
            }
        # 课 29: "该反弹一定触及最后一个中枢的 DD...否则就等于在下面
        # 又至少形成一个新的中枢, 与上中枢是最后一个矛盾"
        return {
            "kind": TURN_SUB_FLOOR,
            "candidates": [],
            "note": ("反弹未及最后中枢 DD, 超出定理保证(次级别单元未"
                     "完成/数据不完整/中枢识别有误), 请核查"),
        }
    if trend == "up":
        # 上涨背驰后看回落低点(第一波次级别回落), 镜像
        low = float(first_pull.low)
        if low <= zd:
            return {
                "kind": TURN_BREAK,
                "candidates": list(TURN_CANDIDATES),
                "note": ("第一波次级别回落回到最后中枢区间, 最弱情况"
                         "(级别扩展)基本排除; 更大级别盘整或该级别以"
                         "上反趋势, 区分看突破后是否第三类卖点"),
            }
        if low <= gg:
            return {
                "kind": TURN_EXPANSION,
                "candidates": [],
                "note": ("回落只触及最后中枢 GG 未回区间, 最后中枢将"
                         "级别扩展(最弱回落), 回落力度值得怀疑"),
            }
        return {
            "kind": TURN_SUB_FLOOR,
            "candidates": [],
            "note": ("回落未及最后中枢 GG, 超出定理保证(次级别单元未"
                     "完成/数据不完整/中枢识别有误), 请核查"),
        }
    raise ValueError("trend 必须为 'down' 或 'up', 实际: %r" % (trend,))


def guaranteed_rebound_gap(center: Any, price: float,
                           trend: str) -> Optional[float]:
    """定理保证的反弹空间占比(课 29 超跌标准)

    课 29: "在第一次抄底时, 最好就是买那些当下位置离最后一个中枢的
    DD=min(dn)幅度最大的, 所谓的超跌, 应该以此为标准。因为本章的
    定理保证了, 反弹一定达到 DD=min(dn)之上"。

    参数:
        center: 趋势最后一个中枢(zd/zg/gg/dd);
        price: 当下价格;
        trend: "down" 下跌背驰情形(一买抄底) / "up" 上涨背驰情形
            (一卖逃顶, 镜像: 距 GG 的回落空间)。

    返回:
        float: 保证空间占 DD(或 GG)的比例——
            trend="down": (DD - price) / DD, 价格越低于 DD 越大,
                为正即定理保证的反弹幅度;
            trend="up":   (price - GG) / GG;
        价格已在保证位内侧(无保证空间)时为负值, 比例无定义
        (DD<=0 或 GG<=0)时返回 None。
    """
    _, _, gg, dd = _center_bounds(center)
    p = float(price)
    if trend == "down":
        if dd <= 0.0:
            return None
        return (dd - p) / dd
    if trend == "up":
        if gg <= 0.0:
            return None
        return (p - gg) / gg
    raise ValueError("trend 必须为 'down' 或 'up', 实际: %r" % (trend,))
