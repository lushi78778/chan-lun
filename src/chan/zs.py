# -*- coding: utf-8 -*-
"""
chan.zs —— 中枢识别(线段重叠)与走势类型

理论依据: doc/缠论知识库/03-中枢与走势类型.md

  中枢: 某级别走势类型中, 至少三个连续次级别走势类型(此处为线段)
       重叠的部分。
    前三个线段: ZG = min(三线段高点), ZD = max(三线段低点);
    (简化公式(课20): [max(a2,c2), min(a1,c1)], 用与中枢方向一致的
     第一、三线段区间重叠确定)
    另记录 GG = max(所有构成线段高点), DD = min(所有构成线段低点)。

  中枢延伸: 后续线段波动区间与中枢区间 [ZD, ZG] 有重叠 -> 延伸,
    更新 GG/DD 与结束时间; 若延伸超过 9 个线段, 视为更大级别中枢
    (第一版仅标记 extended_9)。

  中枢新生: 后续线段与中枢区间不重叠(向上离开后回抽不回中枢内)
    -> 当前中枢完成, 开始构造新中枢。

find_zs 为鸭子类型: 传入线段(XD)列表得线段级中枢, 传入笔(BI)列表
得笔级中枢——两者都有 direction/high/low/start_dt/end_dt 接口。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List


class ZS(object):
    """中枢对象

    属性:
        zd / zg: 中枢下沿 / 上沿(区间 [ZD, ZG] = 前三段重叠区间)。
        gg / dd: 构成中枢的所有线段的最高点 / 最低点(含延伸段)。
            注意: GG >= ZG, DD <= ZD; "破位"通常指价格离开 [DD, GG]
            之外, 而"中枢有效"指重叠区间 [ZD, ZG]。
        start_dt / end_dt: 中枢形成时间 / 最后延伸段的结束时间。
        direction: 形成中枢的第一线段方向(记录中枢的"来源方向")。
        xd_count: 参与中枢的线段数(延伸会累加)。
        extended_9: 是否延伸超过 9 段(更大级别中枢, 仅标记不另处理)。
    """

    __slots__ = ["zd", "zg", "gg", "dd", "start_dt", "end_dt",
                 "direction", "xd_count", "extended_9"]

    def __init__(self, zd: float, zg: float, gg: float, dd: float,
                 start_dt: Any, end_dt: Any, direction: str, n: int):
        self.zd = zd          # 中枢下沿
        self.zg = zg          # 中枢上沿
        self.gg = gg          # 构成线段的最高点
        self.dd = dd          # 构成线段的最低点
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.direction = direction   # 形成中枢的第一线段方向
        self.xd_count = n
        self.extended_9 = False      # 是否延伸超过 9 段(更大级别)

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"zd": self.zd, "zg": self.zg, "gg": self.gg, "dd": self.dd,
                "start_dt": str(self.start_dt), "end_dt": str(self.end_dt),
                "direction": self.direction, "xd_count": self.xd_count,
                "extended_9": self.extended_9}


def _overlap(xd_a: Any, xd_b: Any) -> bool:
    """两线段区间 [low, high] 是否有重叠(端点相等也算重叠)"""
    return not (xd_a.high < xd_b.low or xd_a.low > xd_b.high)


def _overlap_zs(xd: Any, zs: ZS) -> bool:
    """线段区间与中枢区间 [ZD, ZG] 是否有重叠"""
    return not (xd.high < zs.zd or xd.low > zs.zg)


def find_zs(xds: List[Any]) -> List[ZS]:
    """从线段序列识别中枢(增量式)

    参数:
        xds: find_xds 输出的线段列表(最后一个可能未完成);
            鸭子类型, 传笔(BI)列表即得笔级中枢。

    返回:
        list of ZS, 按时间顺序。

    算法:
        1. 滑动窗口取连续三个线段 a/b/c, 若区间重叠(ZD=max(三低点) <
           ZG=min(三高点))则中枢成立, 记录 GG/DD 与前三个线段的边界;
        2. 中枢成立后逐个检查后续线段: 与 [ZD, ZG] 重叠 -> 延伸
           (更新 GG/DD/end_dt/xd_count, >=9 段标记 extended_9);
           不重叠 -> 中枢完成, 该线段参与下一中枢的构造;
        3. 前三线段无重叠 -> 窗口后移一位继续找。
    """
    if len(xds) < 3:
        return []

    zss = []
    i = 0
    n = len(xds)
    while i + 2 < n:
        a, b, c = xds[i], xds[i + 1], xds[i + 2]
        zd = max(a.low, b.low, c.low)
        zg = min(a.high, b.high, c.high)
        if zd >= zg:
            # 前三线段无重叠: 不构成中枢, 向后滑动
            i += 1
            continue
        # 中枢成立
        gg = max(a.high, b.high, c.high)
        dd = min(a.low, b.low, c.low)
        zs = ZS(zd, zg, gg, dd, a.start_dt, c.end_dt, a.direction, 3)
        i += 3
        # 中枢延伸/新生
        while i < n:
            xd = xds[i]
            if _overlap_zs(xd, zs):
                # 延伸: 线段区间与中枢区间有重叠
                zs.gg = max(zs.gg, xd.high)
                zs.dd = min(zs.dd, xd.low)
                zs.end_dt = xd.end_dt
                zs.xd_count += 1
                if zs.xd_count >= 9:
                    zs.extended_9 = True
                i += 1
                continue
            # 与中枢区间不重叠: 中枢结束, 该线段参与下一中枢
            break
        zss.append(zs)
    return zss


def classify_trend(zss: List[ZS]) -> List[Dict[str, Any]]:
    """走势类型粗分类(基于中枢列表)

    参数:
        zss: find_zs 输出的中枢列表(按时间顺序)。

    返回:
        list of dict, 每个元素描述一组连续的"走势":
            type: '趋势'(组内 >= 2 个中枢) / '盘整'(单中枢);
            zs_count: 组内中枢个数;
            start_dt / end_dt: 组内首个中枢开始 / 末个中枢结束时间;
            zd / zg: 组内首个中枢的上下沿(历史字段, 向后兼容);
            zs_list: 组内全部中枢的 to_dict() 明细(新增, 含各自的
                zd/zg/gg/dd/start_dt/end_dt/xd_count/extended_9),
                需要"第 k 个中枢边界"的调用方不再只能拿到第一个。

    简化规则:
        相邻两中枢满足"区间不重叠(zs.zg < prev.zd 或 zs.zd > prev.zg)
        **且方向一致(zs.direction == prev.direction)**"时, 视为同一
        趋势的延续, 归入同组;
        区间重叠或方向不一致 -> 归为新组(盘整或趋势转折, 第一版
        简化处理, 不做方向反转的细分)。
    """
    if not zss:
        return []
    groups = []
    for zs in zss:
        if not groups:
            groups.append([zs])
            continue
        prev = groups[-1][-1]
        # 相邻中枢区间不重叠且方向一致 -> 同向趋势延续
        if (zs.zg < prev.zd or zs.zd > prev.zg) \
                and zs.direction == prev.direction:
            groups[-1].append(zs)
        else:
            # 重叠或方向不一致 -> 归为新组(第一版简化处理)
            groups.append([zs])
    out = []
    for g in groups:
        out.append({
            "type": "趋势" if len(g) >= 2 else "盘整",
            "zs_count": len(g),
            "start_dt": str(g[0].start_dt),
            "end_dt": str(g[-1].end_dt),
            "zd": g[0].zd, "zg": g[0].zg,
            "zs_list": [z.to_dict() for z in g],
        })
    return out
