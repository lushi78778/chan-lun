# -*- coding: utf-8 -*-
"""
chan.bs —— 兼容的笔级三类买卖候选(基于笔级中枢)

理论依据: doc/缠论知识库/05-三类买卖点.md

  第一类买点: 下跌趋势背驰点(最后一个中枢 DD 之下的背驰段终点);
  第二类买点: 第一类买点后第一次次级别回调的低点(不破一买低点);
  第三类买点: 次级别向上离开中枢后回抽, 低点不破 ZG;
  卖点镜像。

  上述是不破一类点的旧笔级简化口径, 不是第101课完整定义。
  课101允许弱二买低于一买; 已确认次级走势的新条件入口见
  chan.second.find_second_points。这里保留既有计算行为, 不把单笔
  自动视为已完成次级走势, 也不提供真实确认时间。

  本模块输出"信号事件"列表, 每个事件含类型、时间、价格、依据。

设计约定:
    - 一买/一卖事件由 bc.find_trend_bc 的候选列表注入(trend_bc 参数);
      即便上层策略禁用一买开仓, 也应传入 trend_bc——二买/二卖由
      一买/一卖派生, "禁用一买"不等于"不计算一买";
    - 三买/三卖事件自带力度过滤与中枢边界字段(zs_zd/zs_zg 等),
      供 chan.cross30 做 30 分钟跨级别确认。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional


def find_buy_points(bis: List[Any], zss: List[Any],
                    trend_bc: Optional[List[Dict[str, Any]]] = None,
                    min_power_ratio: Optional[float] = None) -> List[Dict[str, Any]]:
    """三类买点识别(基于笔列表与笔级中枢)

    参数:
        bis: 笔列表(chan.bi.find_bis 输出)。
        zss: 中枢列表(通常由 find_zs(bis) 生成, 笔级中枢)。
        trend_bc: 趋势底背驰候选列表(可选, 来自 bc.find_trend_bc)。
            不传则只产生第三类买点(一买/二买需要背驰候选作为锚)。
        min_power_ratio: 三买力度过滤下限(离开笔涨幅 / 回抽笔跌幅)。
            None = 保持默认行为(比值必须 > 1.0, 即回拉力度小于离开力度);
            传入数值 n = 比值必须 >= n(回测敏感性测试用, 如 1.5/2.0)。

    返回:
        list of dict, 按判定顺序, 每项:
            type: 1 / 2 / 3(一买 / 二买 / 三买);
            dt / price: 信号时间与价格;
            basis: 人类可读的判定依据;
            zs_idx: 依据中枢在 zss 中的下标;
            power_ratio: 三买的离开/回抽力度比(二买无此键);
            二买事件额外携带 b1_price(对应一买低点, 供 30m 轻量确认);
            三买事件额外携带 zs_zd / zs_zg / pull_start_dt / pull_end_dt /
            pull_start / pull_end(中枢上下沿与回抽笔端点, 供跨级别确认)。

    规则:
        - 三买: 向上离开中枢(笔终点 > ZG)后的第一根回抽笔, 低点不破
          ZG, 且离开力度大于回拉力度(或满足 min_power_ratio); 每个中枢
          只判定第一次回抽;
        - 一买: trend_bc 中第一个 direction='down' 的背驰候选;
        - 二买: 一买事件之后, 第一根向上笔之后的回抽笔, 低点不破
          一买低点(b1_price)。
    """
    out = []

    # ---- 第三类买点: 向上离开中枢, 回抽笔不破 ZG(力度过滤 + 只取第一次) ----
    for zi, zs in enumerate(zss):
        zg = zs.zg
        state = None   # 'left' 已离开
        leave_bi = None
        for bi in bis:
            if str(bi.start_dt) < str(zs.start_dt):
                continue   # 中枢成立前的笔不参与判定
            if bi.direction == "up" and bi.end_value > zg and state != "left":
                state = "left"
                leave_bi = bi
                continue
            if state == "left" and bi.direction == "down":
                if bi.end_value >= zg and leave_bi is not None:
                    # 力度比较: 离开笔涨幅 vs 回抽笔跌幅
                    leave_power = leave_bi.end_value / leave_bi.start_value - 1.0
                    pull_power = abs(bi.end_value / bi.start_value - 1.0)
                    ratio = round(leave_power / pull_power, 2) if pull_power > 0 else None
                    ok_power = (ratio > 1.0) if min_power_ratio is None \
                        else (ratio is not None and ratio >= min_power_ratio)
                    if ok_power:
                        # 附带中枢上下沿与回抽笔端点, 供跨级别(30m)确认
                        out.append({"type": 3, "dt": str(bi.end_dt),
                                    "price": bi.end_value,
                                    "basis": "中枢[{0:.2f},{1:.2f}]向上离开后回抽不破ZG".format(zs.zd, zg),
                                    "zs_idx": zi, "power_ratio": ratio,
                                    "zs_zd": round(zs.zd, 4), "zs_zg": round(zg, 4),
                                    "pull_start_dt": str(bi.start_dt),
                                    "pull_end_dt": str(bi.end_dt),
                                    "pull_start": round(bi.start_value, 4),
                                    "pull_end": round(bi.end_value, 4)})
                    break   # 每个中枢只判定第一次回抽
                state = None

    # ---- 第一类买点: 下跌趋势背驰点 ----
    buy1 = None
    if trend_bc:
        for bc in trend_bc:
            if bc.get("direction") == "down":
                out.append({"type": 1, "dt": bc["dt"], "price": bc["price"],
                            "basis": "下跌趋势背驰({0})".format(bc["note"]),
                            "zs_idx": bc.get("zs_idx")})
                buy1 = bc
                break

    # ---- 第二类买点: 一买后第一次回调不破一买低点 ----
    if buy1 is not None:
        b1_price = buy1["price"]
        state = 0
        found = False
        for bi in bis:
            if found:
                break
            if state == 0:
                if str(bi.end_dt) == buy1["dt"]:
                    state = 1
                continue
            if state == 1 and bi.direction == "up":
                state = 2
                continue
            if state == 2 and bi.direction == "down":
                if bi.end_value >= b1_price:
                    out.append({"type": 2, "dt": str(bi.end_dt),
                                "price": bi.end_value,
                                "basis": "一买后第一次回调不破前低",
                                "zs_idx": buy1.get("zs_idx"),
                                "b1_price": round(b1_price, 4)})
                    found = True
                state = 0

    return out


def find_sell_points(bis: List[Any], zss: List[Any],
                     trend_bc: Optional[List[Dict[str, Any]]] = None,
                     min_power_ratio: Optional[float] = None) -> List[Dict[str, Any]]:
    """三类卖点识别(镜像)

    参数与返回结构同 find_buy_points, 方向取反:
        - 三卖: 向下离开中枢(笔终点 < ZD)后的第一根回抽笔, 高点不升破
          ZD, 且离开力度大于回拉力度(或满足 min_power_ratio);
        - 一卖: trend_bc 中第一个 direction='up' 的背驰候选;
        - 二卖: 一卖事件之后, 第一根向下笔之后的回抽笔, 高点不升破
          一卖高点; 事件额外携带 s1_price(对应一卖高点)。
    """
    out = []

    # 第三类卖点: 向下离开中枢, 回抽笔高点不升破 ZD(力度过滤 + 只取第一次)
    for zi, zs in enumerate(zss):
        zd = zs.zd
        state = None
        leave_bi = None
        for bi in bis:
            if str(bi.start_dt) < str(zs.start_dt):
                continue
            if bi.direction == "down" and bi.end_value < zd and state != "left":
                state = "left"
                leave_bi = bi
                continue
            if state == "left" and bi.direction == "up":
                if bi.end_value <= zd and leave_bi is not None:
                    # 力度比较: 离开笔跌幅 vs 回抽笔涨幅
                    leave_power = abs(leave_bi.end_value / leave_bi.start_value - 1.0)
                    pull_power = bi.end_value / bi.start_value - 1.0
                    ratio = round(leave_power / pull_power, 2) if pull_power > 0 else None
                    ok_power = (ratio > 1.0) if min_power_ratio is None \
                        else (ratio is not None and ratio >= min_power_ratio)
                    if ok_power:
                        # 附带中枢上下沿与回抽笔端点, 供跨级别(30m)确认
                        out.append({"type": 3, "dt": str(bi.end_dt),
                                    "price": bi.end_value,
                                    "basis": "中枢[{0:.2f},{1:.2f}]向下离开后回抽不升破ZD".format(zd, zs.zg),
                                    "zs_idx": zi, "power_ratio": ratio,
                                    "zs_zd": round(zs.zd, 4), "zs_zg": round(zs.zg, 4),
                                    "pull_start_dt": str(bi.start_dt),
                                    "pull_end_dt": str(bi.end_dt),
                                    "pull_start": round(bi.start_value, 4),
                                    "pull_end": round(bi.end_value, 4)})
                    break   # 每个中枢只判定第一次回抽
                state = None

    # 第一类卖点: 上涨趋势背驰点
    sell1 = None
    if trend_bc:
        for bc in trend_bc:
            if bc.get("direction") == "up":
                out.append({"type": 1, "dt": bc["dt"], "price": bc["price"],
                            "basis": "上涨趋势背驰({0})".format(bc["note"]),
                            "zs_idx": bc.get("zs_idx")})
                sell1 = bc
                break

    # 第二类卖点
    if sell1 is not None:
        s1_price = sell1["price"]
        state = 0
        found = False
        for bi in bis:
            if found:
                break
            if state == 0:
                if str(bi.end_dt) == sell1["dt"]:
                    state = 1
                continue
            if state == 1 and bi.direction == "down":
                state = 2
                continue
            if state == 2 and bi.direction == "up":
                if bi.end_value <= s1_price:
                    out.append({"type": 2, "dt": str(bi.end_dt),
                                "price": bi.end_value,
                                "basis": "一卖后第一次反弹不破前高",
                                "zs_idx": sell1.get("zs_idx"),
                                "s1_price": round(s1_price, 4)})
                    found = True
                state = 0

    return out
