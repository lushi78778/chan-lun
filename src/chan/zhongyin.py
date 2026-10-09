# -*- coding: utf-8 -*-
"""中阴阶段(课 89/90)

课 89 原文要点:
    "中阴阶段的存在, 就在于市场发展具体形式在级别上的各种可能性"
    "其后的行情发展, 一定是一个超 1 分钟级别的走势"
    "必须先出现一个 5 分钟中枢, 因为无论后面是什么级别的走势,
    只要是超 1 分钟级别的, 就一定先有一个 5 分钟中枢, 这没有任何
    特例的可能。而这个 100% 成立的结论, 就构成我们操作中最大也是
    100% 准确的基本依据。"
    "而这5分钟中枢成立后, 就必然100%面临一个破坏的问题, 也就是一个
    延伸或者第三买卖点的问题"
    "如果这中枢不断延伸, 搞成30分钟中枢了, 那就按30分钟中枢的第三
    买卖点来处理, 如此类推, 总要面临某一个级别的第三买卖点去结束
    这个中枢震荡。"

即: 某级别走势类型完成后进入中阴阶段, 表现为(高一级别)中枢震荡但
不是一般性中枢震荡; 其演化 100% 遵循 ——
    ① 必然先构造高一级别中枢(三个连续次级别单元重叠);
    ② 之后面临中枢延伸(可升级, 九段口径见 zs 模块)或第三类买卖点
       (回抽不回中枢区间)结束中阴。

课 90 原文要点(结束时间辅助判断, 非绝对判断):
    "布林通道的收口, 就是对中阴结束时间的最好提示"
    "某一级别的布林通道收口, 就意味着比这低级别的某个中阴过程要
    级别扩展或结束了, 一般都对应着有相应的第三类买卖点。"
    "一般性地, 在上轨以上和下轨以下运行是超强状态"
    "从上轨上跌回其下或从下轨下涨回其上, 都是从超强区域转向一般性
    区域, 这时候, 如果再次的上涨或回跌创出新高或新低但不能重新有效
    回到超强区域, 那么就意味着进入中阴状态了, 也就是第一类买卖点
    出现了。"
    "等第一次回跌或回升后再次向上或下跌时, 上轨和下轨才会转向,
    而这时候转向的上轨和下轨, 往往成为最大的阻力和支持, 使得第二
    类买卖点在其下或其上被构造出来。"

本模块提供:
    - track_zhongyin(units): 中阴阶段状态机(高一级别中枢构造/延伸/
      升级/第三类买卖点结束), 输入次级别单元(线段或次级别走势类型)
    - boll_bands / boll_state: 布林通道与超强状态
    - boll_events: 超强进退/轨道滞后转向/收口事件流(课 90 辅助判断)
    - boll_bs1_hints: 第一类买卖点辅助提示(课 90)

陷阱注(课 89/90 附文): "陷阱必须由中枢而来, 所谓陷阱, 归根结底都是
中枢震荡的结果。如果不是中枢震荡, 而是中枢移动, 那就不可能是陷阱"
—— 陷阱/真突破的判别 = 中枢震荡 vs 中枢移动 + 力度前后比较(背驰),
 由 bc/bs 模块承接, 本模块的 bs3 结束信号即"真突破"的结构确认。
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from chan.decompose import _find_center, _overlap_center, _range3

__all__ = [
    "ZhongYinResult",
    "track_zhongyin",
    "boll_bands",
    "boll_state",
    "boll_events",
    "boll_bs1_hints",
]

# 中枢参与单元数达 9 即升级提示(课 20/69 九段口径, 与 zs 模块一致)
UPGRADE_UNITS = 9


class ZhongYinResult(object):
    """中阴阶段跟踪结果(纯数据)

    字段:
        stage       -- "before": 高一级别中枢未成(单元不足或无重叠)
                       "center": 中枢已现(含延伸/离开挂起, 中阴持续)
                       "ended":  第三类买卖点出现, 中阴结束
        center      -- (zd, zg) 高一级别中枢区间, 未成为 None
        n_units     -- 中枢参与单元数(组成 3 段 + 延伸段)
        upgraded    -- 参与单元数达 9 段(中枢升级, 课 89"搞成30分钟
                       中枢就按 30 分钟的第三买卖点处理")
        leave_start -- 离开段首单元索引(挂起未确认), 无则 None
        end_signal  -- ("bs3", "up"/"down"): 第三类买卖点方向; 未结束 None
        events      -- [(unit_idx, kind)] 事件流:
                       center_formed / extend / leave_pending /
                       return_to_center(离开失败) / upgrade / bs3
        seg         -- (start, end) 已消费的单元索引范围
    """

    def __init__(self, stage, center=None, n_units=0, upgraded=False,
                 leave_start=None, end_signal=None, events=None,
                 seg=(0, -1)):
        # type: (str, Optional[Tuple[float, float]], int, bool, Optional[int], Optional[Tuple[str, str]], Optional[List[Tuple[int, str]]], Tuple[int, int]) -> None
        self.stage = stage
        self.center = center
        self.n_units = n_units
        self.upgraded = upgraded
        self.leave_start = leave_start
        self.end_signal = end_signal
        self.events = events if events is not None else []
        self.seg = seg

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "stage": self.stage,
            "center": self.center,
            "n_units": self.n_units,
            "upgraded": self.upgraded,
            "leave_start": self.leave_start,
            "end_signal": self.end_signal,
            "events": list(self.events),
            "seg": self.seg,
        }


def track_zhongyin(units):
    # type: (List[Any]) -> ZhongYinResult
    """中阴阶段状态机(课 89)

    输入: 某级别走势类型完成后的次级别单元序列(线段 XD 或次级别
    走势类型 MoveType, 只需 low/high/direction 属性)。

    演化:
        1. 等待高一级别中枢: 最早三个连续单元价格区间重叠(课 35/
           89, 100% 必然先出现) -> stage="center";
        2. 后续单元与中枢区间重叠 -> 延伸(离开挂起时 = 离开失败
           回抽进中枢, 中枢震荡继续);
        3. 单元脱离中枢区间 -> 离开挂起(leave_pending);
        4. 离开后的回抽单元不回中枢区间 -> 第三类买卖点:
           回抽整体在中枢上方 -> ("bs3", "up"), 下方 -> ("bs3",
           "down"), stage="ended"(课 89"总要面临某一个级别的第三
           买卖点去结束这个中枢震荡");
        5. 参与单元数达 9 -> 升级提示(按升级后级别继续同样处理)。
        6. 单元耗尽 -> 终态即当前阶段(无未来函数)。
    """
    n = len(units)
    if n < 3:
        return ZhongYinResult("before", seg=(0, n - 1))

    j = _find_center(units, 0)  # 最早三单元重叠组, 与 decompose 同口径
    if j is None:
        # 无重叠: 高一级别中枢未成, 中阴仍在"必然先有中枢"的路上
        return ZhongYinResult("before", seg=(0, n - 1))

    center = _range3(units, j)
    events = [(j, "center_formed")]  # type: List[Tuple[int, str]]
    n_units = 3                       # 组成三段
    leave_start = None                # 离开段首单元索引(挂起)
    end_signal = None                 # type: Optional[Tuple[str, str]]
    k = j + 3  # 组成三段已计入, 从其后继续
    last = n - 1

    while k < n:
        u = units[k]
        if _overlap_center(u, center):
            # 课 89: 离开后回抽进中枢 = 离开失败(中枢震荡继续)
            if leave_start is not None:
                events.append((k, "return_to_center"))
                leave_start = None
            else:
                events.append((k, "extend"))
            n_units += 1
            if n_units == UPGRADE_UNITS:
                # 恰 9 段一次升级标记(与 zs.track_zs 口径一致)
                events.append((k, "upgrade"))
        else:
            if leave_start is None:
                # 首个脱离中枢区间的单元: 离开挂起
                leave_start = k
                events.append((k, "leave_pending"))
            else:
                # 离开后的下一单元仍不回中枢 = 回抽不回中枢区间,
                # 第三类买卖点(课 101 语义): 中阴结束
                if u.low > center[1]:
                    end_signal = ("bs3", "up")     # 回抽在中枢上方
                elif u.high < center[0]:
                    end_signal = ("bs3", "down")   # 回抽在中枢下方
                else:  # 防御: 几何上不可达(_overlap_center 已覆盖)
                    end_signal = ("bs3", "none")
                events.append((k, "bs3"))
                last = k - 1  # bs3 单元属于下一走势, 不计入中阴
                k = n         # 结束
                break
        last = k
        k += 1

    upgraded = n_units >= UPGRADE_UNITS
    if end_signal is not None:
        stage = "ended"
    else:
        stage = "center"
    return ZhongYinResult(
        stage, center=center, n_units=n_units, upgraded=upgraded,
        leave_start=leave_start, end_signal=end_signal, events=events,
        seg=(0, last))


# --- 布林通道辅助判断(课 90) -------------------------------------------


def boll_bands(closes, n=20, k=2.0):
    # type: (List[float], int, float) -> List[Optional[Tuple[float, float, float]]]
    """布林通道: (mid, upper, lower) 滚动 SMA +/- k 倍总体标准差

    前 n-1 根为 None(窗口不满); 纯标准库实现。
    """
    out = []  # type: List[Optional[Tuple[float, float, float]]]
    for i in range(len(closes)):
        if i + 1 < n:
            out.append(None)
            continue
        win = closes[i + 1 - n:i + 1]
        mid = sum(win) / float(n)
        var = sum((c - mid) ** 2 for c in win) / float(n)
        sd = math.sqrt(var)
        out.append((mid, mid + k * sd, mid - k * sd))
    return out


def boll_state(close, band):
    # type: (float, Optional[Tuple[float, float, float]]) -> Optional[str]
    """超强状态(课 90): 上轨以上 "super_up" / 下轨以下 "super_down" /
    其余 "normal"; 窗口不满 None"""
    if band is None:
        return None
    if close > band[1]:
        return "super_up"
    if close < band[2]:
        return "super_down"
    return "normal"


def boll_events(closes, n=20, k=2.0, squeeze_win=20, squeeze_ratio=0.6,
                turn_run=2):
    # type: (List[float], int, float, int, float, int) -> List[Tuple[int, str]]
    """布林通道事件流(课 90 辅助判断)

    事件:
        super_up_enter / super_up_exit -- 进入/离开上轨上超强区域
        super_down_enter / super_down_exit -- 下轨下镜像
        upper_turn_down -- 上轨在连续 turn_run 期上升后首次回落
            (课 90: "等第一次回跌或回升后再次向上或下跌时, 上轨和
            下轨才会转向"—— 滞后转向的上轨构成最大阻力, 第二类
            买卖点在其下被构造)
        lower_turn_up -- 下轨镜像(最大支持)
        squeeze -- 带宽收缩至过去 squeeze_win 期最小带宽的
            squeeze_ratio 倍以下(课 90: "布林通道的收口, 就是对中阴
            结束时间的最好提示"——比该级别低的某个中阴过程将级别
            扩展或结束, 一般对应第三类买卖点)
    """
    bands = boll_bands(closes, n, k)
    events = []  # type: List[Tuple[int, str]]
    prev_state = None  # type: Optional[str]
    up_run = 0       # 上轨连续上升期数
    lo_down_run = 0  # 下轨连续下降期数

    for i, band in enumerate(bands):
        if band is None:
            continue
        state = boll_state(closes[i], band)
        if state != prev_state:
            if state == "super_up":
                events.append((i, "super_up_enter"))
            elif prev_state == "super_up":
                events.append((i, "super_up_exit"))
            if state == "super_down":
                events.append((i, "super_down_enter"))
            elif prev_state == "super_down":
                events.append((i, "super_down_exit"))
            prev_state = state

        prev = bands[i - 1] if i > 0 and bands[i - 1] is not None else None
        if prev is not None:
            # 上轨拐头: 连续上升后首次回落
            if band[1] > prev[1]:
                up_run += 1
            elif band[1] < prev[1]:
                if up_run >= turn_run:
                    events.append((i, "upper_turn_down"))
                up_run = 0
            # 下轨拐头: 连续下降后首次回升
            if band[2] < prev[2]:
                lo_down_run += 1
            elif band[2] > prev[2]:
                if lo_down_run >= turn_run:
                    events.append((i, "lower_turn_up"))
                lo_down_run = 0

        # 收口检测
        if i >= n - 1 + squeeze_win:
            hist = [b[1] - b[2] for b in
                    bands[i - squeeze_win:i] if b is not None]
            if hist:
                bw = band[1] - band[2]
                if bw <= min(hist) * squeeze_ratio:
                    events.append((i, "squeeze"))

    return events


def boll_bs1_hints(closes, n=20, k=2.0):
    # type: (List[float], int, float) -> List[Tuple[int, str]]
    """第一类买卖点辅助提示(课 90)

    "从上轨上跌回其下或从下轨下涨回其上, 都是从超强区域转向一般性
    区域, 这时候, 如果再次的上涨或回跌创出新高或新低但不能重新有效
    回到超强区域, 那么就意味着进入中阴状态了, 也就是第一类买卖点
    出现了。"

    状态机(卖端):
        super_up 期间记录极值高点 -> 跌回一般区域 -> 之后收盘创出
        新高但仍未回超强区域 -> ("bs1_sell_hint")
    买端镜像: super_down 极值低点 -> 涨回 -> 创新低未回超强 ->
    ("bs1_buy_hint")。辅助判断, 非绝对判断(课 90 原文口径)。
    """
    bands = boll_bands(closes, n, k)
    hints = []  # type: List[Tuple[int, str]]
    exit_high = None  # type: Optional[float]  # 超强期间极值高点
    exit_low = None   # type: Optional[float]  # 超强期间极值低点

    for i, band in enumerate(bands):
        if band is None:
            continue
        state = boll_state(closes[i], band)
        if state == "super_up":
            if exit_high is None or closes[i] > exit_high:
                exit_high = closes[i]
            exit_low = None  # 镜像状态复位
        elif state == "super_down":
            if exit_low is None or closes[i] < exit_low:
                exit_low = closes[i]
            exit_high = None
        else:
            # 一般性区域: 检验"创新高/新低但不能回超强区域"
            if exit_high is not None and closes[i] > exit_high:
                hints.append((i, "bs1_sell_hint"))
                exit_high = None  # 一次提示后复位
            elif exit_low is not None and closes[i] < exit_low:
                hints.append((i, "bs1_buy_hint"))
                exit_low = None

    return hints
