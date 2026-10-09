# -*- coding: utf-8 -*-
"""
chan.zs —— 中枢识别(线段重叠)、走势类型与中枢状态机

理论依据: doc/_extracted/课020.txt / 课069.txt / 课070.txt
          (导航: doc/缠论知识库/03-中枢与走势类型.md)

  中枢: 某级别走势类型中, 至少三个连续次级别走势类型(此处为线段)
        重叠的部分。
     前三个线段: ZG = min(三线段高点), ZD = max(三线段低点);
     (简化公式(课20): [max(a2,c2), min(a1,c1)], 用与中枢方向一致的
      第一、三线段区间重叠确定)
     另记录 GG = max(所有构成线段高点), DD = min(所有构成线段低点)。

  中枢延伸(课20 开篇/中枢中心定理一): "所有围绕走势中枢产生的前后
     两个次级波动都必须至少有一个触及走势中枢的区间"——延伸等价于
     任意后续次级段区间 [dn,gn] 与 [ZD,ZG] 有重叠; 若某段完全离开
     (dn>ZG 或 gn<ZD), "则必然产生高级别的走势中枢或趋势及延续"。
     延伸达 9 段(3x3)构成大一级别中枢(课69: "九段可延伸成5分钟中枢,
     可不等于5分钟中枢就一定是九段"——九段是升级的充分特例)。

  中枢新生(课20): 后续线段与中枢区间不重叠 -> 当前中枢完成, 开始
     构造新中枢。前后同级别中枢的方向关系由中枢中心定理二判定:
       后 GG < 前 DD  -> 下跌及其延续;
       后 DD > 前 GG  -> 上涨及其延续;
       区间不重叠但波动区间重叠(或区间自身重叠) -> 更大级别走势中枢。

  中枢扩展(课20/走势级别延续定理二): "更大级别缠中说禅走势中枢产生,
     当且仅当围绕连续两个同级别缠中说禅走势中枢产生的波动区间产生
     重叠"。扩展时按课20 中枢公式在高级别上重构: 前中枢(作为一个
     次级别单元, 区间=[DD,GG]) + 连接段 + 后中枢 三单元重叠。

  中枢状态机(track_zs, 课70 当下判定): 中枢形成后理论上只有三种
     走势——1、三买后新同级别中枢; 2、三卖后新同级别中枢;
     3、中枢延伸, 或出现三买三卖后扩展成大级别中枢。track_zs
     逐段推进并输出事件流(form/extend/upgrade_9/complete/new),
     最后一个事件即"当下"状态。

find_zs 为鸭子类型: 传入线段(XD)列表得线段级中枢, 传入笔(BI)列表
得笔级中枢——两者都有 direction/high/low/start_dt/end_dt 接口。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple


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


class ZsEvent(object):
    """中枢状态机事件(课20/69/70 当下判定的输出单元)

    kind 取值:
        "form"      中枢成立: 前三个连续次级别段重叠部分确定(课20);
        "extend"    中枢延伸: 某后续段区间与 [ZD,ZG] 有重叠(定理一);
        "upgrade_9" 延伸达 9 段, 构成大一级别中枢(课69 九段特例);
        "complete"  中枢完成: 某段完全离开 [ZD,ZG], "必然产生高级别的
                    走势中枢或趋势及延续"(定理一), detail.leave_dir
                    记录离开方向("up"/"down");
        "new"       新中枢成立: detail.relation 为与前中枢的定理二
                    关系("up_continue"/"down_continue"/"expand");
                    relation=="expand" 时 detail.expand_zs 携带按
                    课20 公式构造的更高级别中枢候选。

    属性:
        kind: 事件类型(上表);
        index: 触发事件的次级别段下标(0 起, 指向 xds 列表; form/new
            为确认重叠的第三段下标, detail.first_index 记录中枢首段
            下标);
        dt: 触发时间 = 确认该事件的段 end_dt(延伸/升级/完成取触发段,
            form/new 取第三段——中枢在第三段完成时才"当下可知",
            事件流时间单调, 无未来函数);
        detail: 事件明细 dict(见上表)。
    """

    __slots__ = ["kind", "index", "dt", "detail"]

    def __init__(self, kind: str, index: int, dt: Any,
                 detail: Optional[Dict[str, Any]] = None):
        self.kind = kind
        self.index = index
        self.dt = dt
        self.detail = detail if detail is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"kind": self.kind, "index": self.index, "dt": str(self.dt),
                "detail": self.detail}


def _overlap(xd_a: Any, xd_b: Any) -> bool:
    """两线段区间 [low, high] 是否有重叠(端点相等也算重叠)"""
    return not (xd_a.high < xd_b.low or xd_a.low > xd_b.high)


def _overlap_zs(xd: Any, zs: ZS) -> bool:
    """线段区间与中枢区间 [ZD, ZG] 是否有重叠"""
    return not (xd.high < zs.zd or xd.low > zs.zg)


def zs_relation(prev: ZS, curr: ZS) -> str:
    """前后同级别中枢的方向关系(课20 中枢中心定理二, 纯函数)

    原文: "前后同级别的两个缠中说禅走势中枢, 后 GG<前 DD 等价于下跌
    及其延续; 后 DD>前 GG 等价于上涨及其延续。后 ZG<前 ZD 且后 GG>=
    前 DD, 或后 ZD>前 ZG 且后 DD<=前 GG, 则等价于形成高级别的走势
    中枢。"

    返回:
        "down_continue": 后 GG < 前 DD(严格不等号, 按) —— 下跌及其延续;
        "up_continue":   后 DD > 前 GG —— 上涨及其延续;
        "expand":        其余情形 —— 区间不重叠但波动区间重叠(定理二
                         扩展两分支), 或 [ZD,ZG] 区间自身重叠(课20 开篇:
                         "在趋势里, 同级别的前后中枢是不能有任何重叠的",
                         重叠即非趋势, 归入更大级别中枢情形)。

    穷尽性: [ZD,ZG] 包含于 [DD,GG], 故波动区间不重叠时, 后中枢整体在
    前中枢之下(后 GG<前 DD)或之上(后 DD>前 GG), 三分支穷尽。
    """
    if curr.gg < prev.dd:
        # 严格小于才算下跌延续; 恰好触及(==)落入扩展分支(后 GG>=前 DD)
        return "down_continue"
    if curr.dd > prev.gg:
        return "up_continue"
    return "expand"


def build_expanded_zs(prev: ZS, curr: ZS, conn_low: float, conn_high: float,
                      start_dt: Any = None,
                      end_dt: Any = None) -> Optional[ZS]:
    """扩展时构造更高级别中枢候选(课20 中枢公式, 纯函数)

    原文依据(课20): 中枢由前三个连续次级别走势类型的重叠部分确定,
    区间 = [max(各单元低点), min(各单元高点)]。扩展发生时, 前中枢、
    连接段、后中枢构成高级别上的三个连续次级别单元——前/后中枢作为
    一个单元取其整个波动区间 [DD, GG](课20: "在5分钟中枢里, 看1分钟
    走势类型的重叠, 是把整个走势类型的波动区域算在一起看"——课70
    对中枢单元区间的口径说明)。

    参数:
        prev / curr: 前后两个同级别中枢(zs_relation 应为 "expand");
        conn_low / conn_high: 两中枢之间连接段的最低/最高价(多段时取
            并集; 若后中枢首段即离开段, 取该离开段区间);
        start_dt / end_dt: 高级别中枢起止时间(默认取 prev.start_dt /
            curr.end_dt)。

    返回:
        ZS 或 None。优先用三单元重叠公式: zd = max(prev.dd, conn_low,
        curr.dd), zg = min(prev.gg, conn_high, curr.gg); 若退化
        (zd >= zg, 连接段区间撑破了重叠), 退回两中枢波动区间重叠口径
        (定理二): zd = max(prev.dd, curr.dd), zg = min(prev.gg,
        curr.gg); 仍退化(如两波动区间仅端点相触)则返回 None。
    """
    gg = max(prev.gg, conn_high, curr.gg)
    dd = min(prev.dd, conn_low, curr.dd)
    # 课20 公式: 三次级别单元的重叠区间
    zd = max(prev.dd, conn_low, curr.dd)
    zg = min(prev.gg, conn_high, curr.gg)
    if zd >= zg:
        # 连接段口径退化 -> 退回定理二波动区间重叠口径
        zd = max(prev.dd, curr.dd)
        zg = min(prev.gg, curr.gg)
        n = 2
    else:
        n = 3
    if zd >= zg:
        return None
    # 扩展方向: 后中枢在前中枢之下为 down, 之上为 up(区间不重叠时),
    # 区间重叠时以中点相对位置定方向
    if curr.zd > prev.zg:
        direction = "up"
    elif curr.zg < prev.zd:
        direction = "down"
    else:
        direction = "up" if (curr.zd + curr.zg) > (prev.zd + prev.zg) \
            else "down"
    return ZS(zd, zg, gg, dd,
              start_dt if start_dt is not None else prev.start_dt,
              end_dt if end_dt is not None else curr.end_dt,
              direction, n)


def track_zs(xds: List[Any]) -> Tuple[List[ZS], List[ZsEvent]]:
    """中枢状态机: 逐段推进, 输出中枢列表 + 事件流(课20/69/70)

    参数:
        xds: find_xds 输出的线段列表(最后一个可能未完成);
            鸭子类型, 传笔(BI)列表即得笔级中枢。

    返回:
        (zss, events):
        zss: 与 find_zs 完全一致的中枢列表(按时间顺序, 最后一个可能
             仍在延伸中);
        events: ZsEvent 事件流, 按触发顺序; 最后一个事件即"当下"
             状态(课70: 形成中枢后理论上只有三种走势, 走势自然选择,
             只需要观察)。

    状态机转移(忠实课20 口径; form/new 事件在第三段完成时发出,
    即中枢"当下可知"的确认时点, 事件流时间单调):
        1. 滑动窗口取连续三段 a/b/c, 重叠(ZD<ZG) -> emit form;
        2. 后续段与 [ZD,ZG] 有重叠 -> 延伸, emit extend(课20: "所有
           围绕走势中枢产生的前后两个次级波动都必须至少有一个触及
           走势中枢的区间"; 交替段下与定理一 [dn,gn] 口径等价);
           段数达 9 -> emit upgrade_9(课69 九段特例, 仅发一次);
        3. 某段与 [ZD,ZG] 完全不重叠 -> 中枢完成, emit complete
           (leave_dir=离开方向; 定理一: "必然产生高级别的走势中枢
           或趋势及延续"), 该段参与下一中枢构造;
        4. 新中枢成立(其第三段完成) -> emit new, relation =
           zs_relation(前, 新)(定理二); relation=="expand" 时按课20
           公式构造高级别中枢候选(build_expanded_zs, 连接段取前中枢
           末段与后中枢首段之间全部段的并集区间, 为空时取后中枢首段
           区间)。
    """
    zss: List[ZS] = []
    events: List[ZsEvent] = []
    spans: List[Tuple[int, int]] = []  # 每个中枢的(首段下标, 末段下标)
    if len(xds) < 3:
        return zss, events
    i = 0
    n = len(xds)
    while i + 2 < n:
        a, b, c = xds[i], xds[i + 1], xds[i + 2]
        zd = max(a.low, b.low, c.low)
        zg = min(a.high, b.high, c.high)
        if zd >= zg:
            # 前三段无重叠: 不构成中枢, 向后滑动
            i += 1
            continue
        # 中枢成立
        gg = max(a.high, b.high, c.high)
        dd = min(a.low, b.low, c.low)
        zs = ZS(zd, zg, gg, dd, a.start_dt, c.end_dt, a.direction, 3)
        first_index = i
        if zss:
            # 新中枢与前中枢的定理二关系 + 扩展时构造高级别候选
            prev = zss[-1]
            relation = zs_relation(prev, zs)
            detail: Dict[str, Any] = {"relation": relation,
                                      "first_index": first_index,
                                      "zd": zd, "zg": zg, "gg": gg,
                                      "dd": dd, "direction": a.direction}
            if relation == "expand":
                # 连接段: 前中枢末段之后至新中枢首段之前的全部段
                lo = spans[-1][1] + 1
                hi = first_index - 1
                if lo <= hi:
                    conn_low = min(x.low for x in xds[lo:hi + 1])
                    conn_high = max(x.high for x in xds[lo:hi + 1])
                else:
                    # 后中枢首段即离开段: 取该段为连接段(结合律口径,
                    # 课70: "新的5分钟中枢, 暂时先从最后一个1分钟中枢
                    # 开始算起"——分解选择不影响操作)
                    conn_low = xds[first_index].low
                    conn_high = xds[first_index].high
                expanded = build_expanded_zs(prev, zs, conn_low, conn_high)
                detail["expand_zs"] = expanded.to_dict() \
                    if expanded is not None else None
            # 确认时点 = 第三段完成(中枢当下可知, 事件流时间单调)
            events.append(ZsEvent("new", i + 2, c.end_dt, detail))
        else:
            events.append(ZsEvent(
                "form", i + 2, c.end_dt,
                {"first_index": first_index, "zd": zd, "zg": zg,
                 "gg": gg, "dd": dd, "direction": a.direction}))
        i += 3
        # 中枢延伸/完成
        last_index = i - 1
        while i < n:
            xd = xds[i]
            if _overlap_zs(xd, zs):
                # 延伸: 更新 GG/DD/end_dt/xd_count
                zs.gg = max(zs.gg, xd.high)
                zs.dd = min(zs.dd, xd.low)
                zs.end_dt = xd.end_dt
                zs.xd_count += 1
                last_index = i
                if zs.xd_count == 9:
                    # 课69: 九段延伸构成大一级别中枢(仅此一次发事件)
                    zs.extended_9 = True
                    events.append(ZsEvent("upgrade_9", i, xd.end_dt,
                                          {"xd_count": 9}))
                else:
                    events.append(ZsEvent(
                        "extend", i, xd.end_dt,
                        {"seg_low": xd.low, "seg_high": xd.high,
                         "xd_count": zs.xd_count}))
                i += 1
                continue
            # 与中枢区间完全不重叠: 中枢完成, 该段参与下一中枢
            leave_dir = "up" if xd.low > zs.zg else "down"
            events.append(ZsEvent("complete", i, xd.end_dt,
                                  {"leave_dir": leave_dir}))
            break
        zss.append(zs)
        spans.append((first_index, last_index))
    return zss, events


def find_zs(xds: List[Any]) -> List[ZS]:
    """从线段序列识别中枢(增量式)——track_zs 的薄包装

    参数:
        xds: find_xds 输出的线段列表(最后一个可能未完成);
            鸭子类型, 传笔(BI)列表即得笔级中枢。

    返回:
        list of ZS, 按时间顺序(与 track_zs(xds)[0] 完全一致)。

    算法(即 track_zs 状态机, 详见其 docstring):
        1. 滑动窗口取连续三个线段 a/b/c, 若区间重叠(ZD=max(三低点) <
           ZG=min(三高点))则中枢成立, 记录 GG/DD 与前三个线段的边界;
        2. 中枢成立后逐个检查后续线段: 与 [ZD, ZG] 重叠 -> 延伸
           (更新 GG/DD/end_dt/xd_count, >=9 段标记 extended_9);
           不重叠 -> 中枢完成, 该线段参与下一中枢的构造;
        3. 前三线段无重叠 -> 窗口后移一位继续找。
    """
    return track_zs(xds)[0]


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
