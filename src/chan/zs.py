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
    (第一版仅标记)。

  中枢新生: 后续线段与中枢区间不重叠(向上离开后回抽不回中枢内)
    -> 当前中枢完成, 开始构造新中枢。

兼容: Python 3.6。
"""

from __future__ import print_function


class ZS(object):
    """中枢对象"""

    __slots__ = ["zd", "zg", "gg", "dd", "start_dt", "end_dt",
                 "direction", "xd_count", "extended_9"]

    def __init__(self, zd, zg, gg, dd, start_dt, end_dt, direction, n):
        self.zd = zd          # 中枢下沿
        self.zg = zg          # 中枢上沿
        self.gg = gg          # 构成线段的最高点
        self.dd = dd          # 构成线段的最低点
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.direction = direction   # 形成中枢的第一线段方向
        self.xd_count = n
        self.extended_9 = False      # 是否延伸超过 9 段(更大级别)

    def to_dict(self):
        return {"zd": self.zd, "zg": self.zg, "gg": self.gg, "dd": self.dd,
                "start_dt": str(self.start_dt), "end_dt": str(self.end_dt),
                "direction": self.direction, "xd_count": self.xd_count,
                "extended_9": self.extended_9}


def _overlap(xd_a, xd_b):
    """两线段区间 [low, high] 是否有重叠"""
    return not (xd_a.high < xd_b.low or xd_a.low > xd_b.high)


def _overlap_zs(xd, zs):
    """线段区间与中枢区间 [ZD, ZG] 是否有重叠"""
    return not (xd.high < zs.zd or xd.low > zs.zg)


def find_zs(xds):
    """从中段序列识别中枢(增量式)

    参数:
        xds: find_xds 输出的线段列表(最后一个可能未完成)

    返回: list of ZS
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


def classify_trend(zss):
    """走势类型粗分类(基于中枢列表)

    返回: list of dict {type: '盘整'/'趋势', 中枢数, 起点, 终点}
    简化: 相邻中枢不重叠且方向一致 -> 趋势; 否则盘整。
    """
    if not zss:
        return []
    groups = []
    for zs in zss:
        if not groups:
            groups.append([zs])
            continue
        prev = groups[-1][-1]
        # 相邻中枢区间不重叠 -> 同向趋势延续
        if zs.zg < prev.zd or zs.zd > prev.zg:
            groups[-1].append(zs)
        else:
            # 重叠 -> 更大级别盘整, 归为新组(第一版简化处理)
            groups.append([zs])
    out = []
    for g in groups:
        out.append({
            "type": "趋势" if len(g) >= 2 else "盘整",
            "zs_count": len(g),
            "start_dt": str(g[0].start_dt),
            "end_dt": str(g[-1].end_dt),
            "zd": g[0].zd, "zg": g[0].zg,
        })
    return out
