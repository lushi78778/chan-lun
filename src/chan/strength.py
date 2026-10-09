# -*- coding: utf-8 -*-
"""趋势力度与平均力度(课 15)

课 15「没有趋势, 没有背驰」的理论内核:
    "定义一个概念, 称为缠中说禅趋势力度: 前一'吻'的结束与后一'吻'
    开始由短线均线与长期均线相交所形成的面积。在前后两个同向趋势
    中, 当缠中说禅趋势力度比上一次缠中说禅趋势力度要弱, 就形成
    '背驰'。"——本模块以两条均线差值序列的相邻封闭面积落为可执行
    口径(ma_areas / find_ma_bc)。

    "还有一种方法, 技巧比较高, 首先再定义一个概念, 称为缠中说禅
    趋势平均力度: 当下与前一'吻'的结束时短线均线与长期均线形成的
    面积除以时间。因为这个概念是即时的, 马上就可以判断当下的...
    平均力度与前一次...的强弱对比, 一旦这次比上次弱, 就可以判断
    '背驰'即将形成, 然后再根据短线均线与长期均线的距离, 一旦延伸
    长度缩短, 就意味着真正的低部马上形成。"——本模块以
    avg_strength_state 落为即时口径(开放式面积/时间 + 延伸长度
    缩短标志)。

    "没有趋势, 没有背驰。在盘整中是无所谓'背驰'的"——比较对象
    只取同向的两段(回复确认: "中间有盘整区的话, 是否可跳过盘整区
    与前面比较? —— 是, 盘整不是趋势, 当然不算"), 两个同向趋势段
    之间的反向段跳过; 异向段之间不构成背驰比较。

    口径说明: 本模块的"吻"边界 = 短长均线差值穿越零轴(含单点触
    零, 触零即相交); "吻"的反抗程度分类(飞吻/唇吻/湿吻)属均线
    系统形态学, 不在本模块(由均线系统模块承接)。判断只涉及两条
    均线与走势, 与任何技术指标无关。
"""

from typing import Any, Dict, List, Optional

__all__ = [
    "sma_series",
    "MaArea",
    "ma_areas",
    "find_ma_bc",
    "MaStrengthState",
    "avg_strength_state",
]


def sma_series(values: Any, n: int) -> List[Optional[float]]:
    """简单移动平均(SMA), 暖机期置 None

    参数:
        values: 收盘价序列(list / tuple / ndarray, 数值元素)。
        n: 均线周期(n >= 1)。

    返回:
        List[Optional[float]], 与输入等长; 前 n-1 位为 None,
        第 i 位 = mean(values[i-n+1 : i+1])。
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    out: List[Optional[float]] = []
    vals = list(values)
    for i in range(len(vals)):
        if i < n - 1:
            out.append(None)
        else:
            window = vals[i - n + 1:i + 1]
            out.append(sum(window) / float(n))
    return out


class MaArea(object):
    """一段同向的均线围成面积(两相邻"吻"之间的趋势段, 课 15)

    属性:
        sign: 段内短线均线相对长期均线的位置, +1(短线在上, 上涨
            段) / -1(短线在下, 下跌段);
        start_idx / end_idx: 段首/段末索引(含端点, 对应输入序列);
        area: 有向面积 = Σ(短线 - 长线), 上涨段为正、下跌段为负;
        bars: 段内K线数;
        avg_area: 平均力度 = area / bars(课 15 "面积除以时间");
        closed: 是否已由后续相交封闭("必须等再次接吻后才能判断"——
            末段未封闭时 closed=False, 不参与稳妥背驰比较)。
    """

    __slots__ = ["sign", "start_idx", "end_idx", "area", "bars",
                 "avg_area", "closed"]

    def __init__(self, sign: int, start_idx: int, end_idx: int,
                 area: float, bars: int, closed: bool):
        self.sign = sign
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.area = area
        self.bars = bars
        self.avg_area = area / float(bars) if bars else 0.0
        self.closed = closed

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用)"""
        return {
            "sign": self.sign,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "area": self.area,
            "bars": self.bars,
            "avg_area": self.avg_area,
            "closed": self.closed,
        }


def _diff_series(short: Any, long: Any) -> List[Optional[float]]:
    """两均线差值序列(短线-长线), 任一侧无效(NaN/None)处置 None"""
    n = min(len(short), len(long))
    out: List[Optional[float]] = []
    for i in range(n):
        s, l = short[i], long[i]
        if s is None or l is None:
            out.append(None)
            continue
        try:
            if s != s or l != l:  # NaN 检查(不依赖 math)
                out.append(None)
            else:
                out.append(float(s) - float(l))
        except TypeError:
            out.append(None)
    return out


def ma_areas(short: Any, long: Any) -> List[MaArea]:
    """两均线的相邻封闭面积序列(课 15 趋势力度)

    参数:
        short / long: 短线 / 长线均线序列(等长或取公共长度; 元素
            数值或 None——sma_series 暖机位 None 自动跳过)。

    返回:
        List[MaArea], 按时间序; 段边界 = 差值穿越零轴或触零(吻 =
            均线相交, 单点触零亦为相交)。末段若因序列耗尽而未再
            相交, closed=False。差值恒为零或数据不足时返回 []。
    """
    diffs = _diff_series(short, long)
    # 首个有效位
    first = None
    for i, d in enumerate(diffs):
        if d is not None:
            first = i
            break
    if first is None or first >= len(diffs) - 1:
        return []

    areas: List[MaArea] = []
    cur_sign = 0
    cur_start = -1
    cur_area = 0.0
    cur_bars = 0
    for i in range(first, len(diffs)):
        d = diffs[i]
        if d is None:
            # 无效位: 视为数据耗尽, 封闭当前段
            if cur_sign != 0:
                areas.append(MaArea(cur_sign, cur_start, i - 1,
                                    cur_area, cur_bars, True))
                cur_sign = 0
            break
        if d == 0.0:
            # 触零即相交(课 15: 吻 = 均线相交): 封闭当前段
            if cur_sign != 0:
                areas.append(MaArea(cur_sign, cur_start, i - 1,
                                    cur_area, cur_bars, True))
                cur_sign = 0
            continue
        s = 1 if d > 0 else -1
        if s != cur_sign:
            if cur_sign != 0:
                # 反向穿越: 前段封闭于 i-1, 新段自 i 起
                areas.append(MaArea(cur_sign, cur_start, i - 1,
                                    cur_area, cur_bars, True))
            cur_sign = s
            cur_start = i
            cur_area = 0.0
            cur_bars = 0
        cur_area += d
        cur_bars += 1
    if cur_sign != 0:
        # 末段因序列耗尽: 未再接吻, 不封闭
        areas.append(MaArea(cur_sign, cur_start, len(diffs) - 1,
                            cur_area, cur_bars, False))
    return areas


def find_ma_bc(short: Any, long: Any,
               use_avg: bool = False) -> List[Dict[str, Any]]:
    """均线趋势背驰(课 15 稳妥口径: 等再次接吻后判断)

    规则:
        - 对每个已封闭(closed=True)的面积段, 取其之前最近的同号
          (sign 相同)封闭段比较, 后段面积绝对值小于前段 -> 背驰;
        - 中间的异向段跳过("盘整不是趋势, 当然不算"——两个同向
          趋势段之间的反向段不参与比较);
        - use_avg=True 时改用平均力度(avg_area, 面积/时间)比较;
        - direction: 'up' = 上涨段力度转弱(顶背驰候选) /
            'down' = 下跌段力度转弱(底背驰候选)。

    返回:
        list of dict: direction / idx(后段末索引) / area_prev /
            area_last / avg_prev / avg_last / note。
    """
    areas = ma_areas(short, long)
    out: List[Dict[str, Any]] = []
    for k in range(len(areas)):
        cur = areas[k]
        # 课 15 稳妥口径: 必须等再次接吻后才能判断(末段未封闭不比)
        if not cur.closed:
            continue
        # 前一同向封闭段(跳过中间的异向段)
        prev = None
        for j in range(k - 1, -1, -1):
            if areas[j].sign == cur.sign:
                prev = areas[j]
                break
        if prev is None:
            continue
        a_prev = prev.avg_area if use_avg else prev.area
        a_cur = cur.avg_area if use_avg else cur.area
        if abs(a_cur) < abs(a_prev):
            direction = "up" if cur.sign > 0 else "down"
            note = ("均线趋势顶背驰(上涨段力度转弱)" if direction == "up"
                    else "均线趋势底背驰(下跌段力度转弱)")
            out.append({
                "direction": direction,
                "idx": cur.end_idx,
                "start_idx": cur.start_idx,
                "area_prev": abs(prev.area),
                "area_last": abs(cur.area),
                "avg_prev": abs(prev.avg_area),
                "avg_last": abs(cur.avg_area),
                "note": note,
            })
    return out


class MaStrengthState(object):
    """当下即时平均力度状态(课 15 平均力度口径)

    属性:
        direction: 当下段方向 'up'(短线在上) / 'down'(短线在下);
        avg_cur: 当下(可能未封闭)段的平均力度 = 面积/时间;
        avg_prev: 上一同向封闭段的平均力度(无同向前段时 None);
        forming_weak: 背驰酝酿中(当下平均力度弱于前一次同向段,
            "一旦这次比上次弱, 就可以判断背驰即将形成"); 无可比
            前段时 None;
        stretch: 当下两均线距离(短线 - 长线, 带符号);
        stretch_shortening: 延伸长度是否正在缩短("一旦延伸长度
            缩短, 就意味着真正的低部马上形成"——下跌段尾部信号,
            上涨段镜像为顶部); 数据不足时 None;
        open_area / prev_area: 对应 MaArea(供调用方取细节)。
    """

    __slots__ = ["direction", "avg_cur", "avg_prev", "forming_weak",
                 "stretch", "stretch_shortening", "open_area",
                 "prev_area"]

    def __init__(self, direction: str, avg_cur: float,
                 avg_prev: Optional[float], forming_weak: Optional[bool],
                 stretch: Optional[float],
                 stretch_shortening: Optional[bool],
                 open_area: Optional[MaArea],
                 prev_area: Optional[MaArea]):
        self.direction = direction
        self.avg_cur = avg_cur
        self.avg_prev = avg_prev
        self.forming_weak = forming_weak
        self.stretch = stretch
        self.stretch_shortening = stretch_shortening
        self.open_area = open_area
        self.prev_area = prev_area

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用)"""
        return {
            "direction": self.direction,
            "avg_cur": self.avg_cur,
            "avg_prev": self.avg_prev,
            "forming_weak": self.forming_weak,
            "stretch": self.stretch,
            "stretch_shortening": self.stretch_shortening,
            "open_area": (self.open_area.to_dict()
                          if self.open_area is not None else None),
            "prev_area": (self.prev_area.to_dict()
                          if self.prev_area is not None else None),
        }


def avg_strength_state(short: Any, long: Any) -> Optional[MaStrengthState]:
    """当下即时平均力度与前一次同向段的强弱对比(课 15 平均力度)

    "这个概念是即时的, 马上就可以判断当下的...平均力度与前一次
    ...的强弱对比"——当下段不需要等再次接吻封闭即可参与比较
    (与 find_ma_bc 的稳妥口径互补: 本函数承担"背驰即将形成"的
    预警, find_ma_bc 承担接吻后的确认)。

    返回:
        MaStrengthState; 无有效数据(均线未定义/差值恒零)时 None。
    """
    areas = ma_areas(short, long)
    if not areas:
        return None
    diffs = _diff_series(short, long)
    valid = [d for d in diffs if d is not None]

    open_seg = areas[-1]
    direction = "up" if open_seg.sign > 0 else "down"
    avg_cur = open_seg.avg_area

    # 前一次同向封闭段(跳过中间的异向段)
    prev_seg = None
    for seg in reversed(areas[:-1]):
        if seg.sign == open_seg.sign:
            prev_seg = seg
            break

    forming_weak: Optional[bool] = None
    avg_prev: Optional[float] = None
    if prev_seg is not None:
        avg_prev = prev_seg.avg_area
        # 课 15: 一旦这次比上次弱, 背驰即将形成
        forming_weak = abs(avg_cur) < abs(avg_prev)

    # 延伸长度: 当下两均线距离及是否缩短
    stretch = valid[-1] if valid else None
    stretch_shortening: Optional[bool] = None
    if len(valid) >= 2:
        stretch_shortening = abs(valid[-1]) < abs(valid[-2])

    return MaStrengthState(direction, avg_cur, avg_prev, forming_weak,
                           stretch, stretch_shortening, open_seg,
                           prev_seg)
