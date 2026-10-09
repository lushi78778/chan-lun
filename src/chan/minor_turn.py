# -*- coding: utf-8 -*-
"""小级别背驰引发大级别转折(缠中说禅技术理论 第 44/53 课)

课 44 原文(定理):

    "缠中说禅小背驰-大转折定理: 小级别顶背驰引发大级别向下的必要
    条件是该级别走势的最后一个次级别中枢出现第三类卖点; 小级别底
    背驰引发大级别向上的必要条件是该级别走势的最后一个次级别中枢
    出现第三类买点。"

    "注意, 关于这种情况, 只有必要条件, 而没有充分条件, 也就是说
    不能有一个充分的判断使得一旦出现某种情况, 就必然导致大级别的
    转折。"

课 44 结构剖析(以向上 30 分钟 a+A+b+B+c、c 内含最后次级别中枢 c`、
c 之后小级别顶背驰为例): 整个运动可看成围绕 c` 的震荡; 该震荡要出
现大的向下变动, 显然要出现 c` 的第三类卖点——"对于那些小级别背驰
后能在最后一个次级别中枢正常震荡的, 都不可能转化成大级别的转折"。

课 44 全仓操作程序(以 30 分钟操作级别、5 分钟回调在承受范围内为
例), 四档响应:

    1. 次级别向下走势未跌破"构成最后一个 30 分钟中枢第三类买点那
       个 5 分钟回试走势类型的高点" -> 不必要理睬(可接受范围内);
    2. 最强走势: 甚至不接触"包含最后大级别中枢三买的那次 5 分钟
       向上走势的最后一个 5 分钟中枢" -> 更无须理睬;
    3. 次级别中枢出现第三类卖点 -> 先出一部分(筹码较多时; 未出现
       破位情形可回补, 权当短差);
    4. 跌破三买回试段高点 -> 任何的向上回抽都必须先离开(全仓离场
       信号)。

课 53 补充(定位):

    "当小级别背驰时, 并触及该级别的第一类买卖点(按: 原文意为'并
    未触及'), 所以就无须操作。对这种情况, 就需要第二类买卖点来补
    充...但在小级别转大级别的情况下, 第二类买卖点就是最佳的, 因为
    在这种情况下, 没有该级别的第一类买卖点。"

    即小转大情形下该级别不存在一买卖, 二买卖(高点一次级别向下后
    一次级别向上不创新高或盘整背驰)是该情形的最佳操作点。

端点触及口径与包内一致: 相等算触及/跌破。
"""

from typing import Any, Dict, Optional

__all__ = [
    "STAGE_WITHIN", "STAGE_STRONG", "STAGE_SUB_BS3", "STAGE_BREAKOUT",
    "classify_minor_turn",
]

# 一档: 反向走势未破三买/三卖回试段极值, 可接受范围内, 无须理睬
STAGE_WITHIN = "within"
# 二档: 反向走势连最后次级别中枢区间都未触及, 最强走势, 无须理睬
STAGE_STRONG = "strong"
# 三档: 最后次级别中枢已现第三类买卖点(小转大必要条件满足),
#     先出一部分; 未破位前可回补(短差)
STAGE_SUB_BS3 = "sub_bs3"
# 四档: 反向走势跌破三买/三卖回试段极值, 全仓口径任何回抽先离场
STAGE_BREAKOUT = "breakout"


def classify_minor_turn(tri_pull: Any, counter_move: Any, trend: str,
                        sub_center: Any = None,
                        sub_bs3: bool = False) -> Dict[str, Any]:
    """小级别背驰引发大级别转折的四档响应(课 44 操作程序)

    参数:
        tri_pull: 构成最后一个大级别中枢第三类买卖点的那次次级别
            回试/回抽走势(需有 low/high 属性, 笔/线段/走势类型通吃)
            ——trend="up" 时为三买回试段(其高点是关键参照);
            trend="down" 时为三卖回抽段(其低点是关键参照);
        counter_move: 小级别背驰之后形成的次级别反向走势(需有
            low/high 属性)——trend="up" 时为向下走势(小顶背驰后);
            trend="down" 时为向上走势(小底背驰后);
        trend: 大级别走势方向 "up"(小顶背驰情形)/"down"(小底背驰
            情形);
        sub_center: 反向走势所围绕/对应的最后一个次级别中枢(需有
            zd/zg 属性, 如 chan.ZS), 可选——None 时跳过"未触及中枢"
            的最强档判定;
        sub_bs3: 该次级别中枢是否已出现第三类买卖点(小背驰-大转折
            定理的必要条件; 仅有必要没有充分, 课 44)。

    返回(dict):
        stage: 四档之一(优先级 breakout > sub_bs3 > strong > within);
        necessary_met: 小转大必要条件是否满足(= sub_bs3, 但出现
            三买卖点并不必然导致大级别转折);
        note: 中文说明。

    判定规则(trend="up", 大级别向上+小顶背驰, 看 counter_move 低点):
        low <= tri_pull.high -> STAGE_BREAKOUT(跌破三买回试段
            高点, 课 44 "任何的向上回抽都必须先离开");
        否则 sub_bs3=True -> STAGE_SUB_BS3(次级别中枢三卖, 先出
            一部分, 未破位可回补);
        否则 sub_center 且 low > sub_center.zg -> STAGE_STRONG
            (连次级别中枢都未触及, 最强走势, 无须理睬);
        否则 -> STAGE_WITHIN(可接受范围内, 无须理睬)。
    trend="down" 镜像(看 counter_move 高点, 参照=三卖回抽段低点,
    中枢下沿 zd)。
    """
    if trend == "up":
        # 大级别向上: 小顶背驰后的次级别向下走势, 关键参照=构成最后
        # 大级别中枢三买的那次回试段的高点(课 44)
        ref = float(tri_pull.high)
        extreme = float(counter_move.low)
        if extreme <= ref:
            return {
                "stage": STAGE_BREAKOUT,
                "necessary_met": sub_bs3,
                "note": ("次级别向下走势跌破最后大级别中枢三买回试"
                         "段高点, 全仓口径任何向上回抽先离场"),
            }
        if sub_bs3:
            return {
                "stage": STAGE_SUB_BS3,
                "necessary_met": True,
                "note": ("最后次级别中枢已现第三类卖点(小转大必要"
                         "条件满足, 但仅必要非充分), 先出一部分; "
                         "未破三买回试高点前可回补(短差)"),
            }
        if sub_center is not None and extreme > float(sub_center.zg):
            return {
                "stage": STAGE_STRONG,
                "necessary_met": False,
                "note": ("次级别向下走势未触及最后次级别中枢区间, "
                         "最强走势, 无须理睬"),
            }
        return {
            "stage": STAGE_WITHIN,
            "necessary_met": False,
            "note": "次级别向下走势在可接受范围内(未破三买回试段), 无须理睬",
        }
    if trend == "down":
        # 大级别向下: 小底背驰后的次级别向上走势, 镜像
        ref = float(tri_pull.low)
        extreme = float(counter_move.high)
        if extreme >= ref:
            return {
                "stage": STAGE_BREAKOUT,
                "necessary_met": sub_bs3,
                "note": ("次级别向上走势突破最后大级别中枢三卖回抽"
                         "段低点, 全仓口径任何向下回抽先离场(空)"),
            }
        if sub_bs3:
            return {
                "stage": STAGE_SUB_BS3,
                "necessary_met": True,
                "note": ("最后次级别中枢已现第三类买点(小转大必要"
                         "条件满足, 但仅必要非充分), 先补一部分; "
                         "未破三卖回抽低点前可减回(短差)"),
            }
        if sub_center is not None and extreme < float(sub_center.zd):
            return {
                "stage": STAGE_STRONG,
                "necessary_met": False,
                "note": ("次级别向上走势未触及最后次级别中枢区间, "
                         "最强走势, 无须理睬"),
            }
        return {
            "stage": STAGE_WITHIN,
            "necessary_met": False,
            "note": "次级别向上走势在可接受范围内(未破三卖回抽段), 无须理睬",
        }
    raise ValueError("trend 必须为 'up' 或 'down', 实际: %r" % (trend,))
