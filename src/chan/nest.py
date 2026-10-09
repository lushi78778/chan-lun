# -*- coding: utf-8 -*-
"""
chan.nest —— 多级区间套定位(动力学, 课 61/37)

理论依据: doc/_extracted/课061.txt / 课037.txt(原文为准)

  课 61(区间套定位标准图解):
    - "只要是围绕一中枢的两段走势都可以比较力度"——进入段与(未走完的)
      离开段围绕同一中枢构成一重力度比较;
    - "都可以先假设是进入背驰段。而当走势实际走出来,一旦力度大于前者,
      那么就可以断定背驰段不成立"——离开段未走完前按背驰段假设跟踪,
      力度不弱于对照段即证伪(实时判读由调用方按此立场使用本模块);
    - "背驰如果没有创新高,是不存在的"——创新高/新低是背驰存在前提;
    - "这种方法可以逐次下去,这就是区间套的定位方法,这方法,可以在当下
      精确地定位走势的转折点"——背驰段的背驰段的背驰段……逐级嵌套,
      各重全部成立时转折点被最内一级精确定位(课 61 例: 72 点由
      "65 开始背驰段的背驰段的背驰段的背驰段"四重嵌套当下定位)。

  课 37(背驰的再分辨):
    - a+A+b+B+c 必须是趋势(A、B 同级别)才有背驰, 否则至多盘整背驰
      (趋势前提由调用方保证, 本模块只做围绕同一中枢的两段力度比较);
    - "c 必然是次级别的……上涨, c 一定要创出新高; ……下跌, c 一定要
      创出新低"——离开段创新高新低是背驰判定前提;
    - "就可以继续套用 a+A+b+B+c 的形式进行次级别分析确定 c 中内部
      结构里次级别趋势的背驰问题, 形成类似区间套的状态, 这样对其后
      的背驰就可以更精确地进行定位了"——相邻级别同构递归。

  本模块把固定两级(日线→30 分钟)的跨级别确认泛化为任意相邻级别的
  嵌套背驰段链: 调用方自大级别到小级别逐级给出"围绕同一中枢的
  对照段/候选段 + 该级别 K 线序列", 逐级判定背驰段是否成立。任何
  一级被证伪(力度不弱于对照段/未创新高新低/柱面积符号异常/相邻
  级别区间不嵌套)则链在该级断裂; 全部成立则区间套定位成立, 转折点
  = 最内一级候选段端点。

  力度默认口径: MACD 柱面积(chan.bc.segment_area, 带符号: 上涨段
  红柱主导为正/下跌段绿柱主导为负), 与 chan.bc.find_trend_bc 同源;
  可注入自定义 strength_fn(bars, move) -> float。

兼容: Python 3.6, 仅标准库 + numpy(经 chan.bc)。
"""

from __future__ import print_function

from typing import Any, Callable, Dict, List, Optional

from chan.bc import _dt_index, macd_series, segment_area

__all__ = [
    "BcNestInput",
    "BcNestLevel",
    "NestBcState",
    "nested_bc",
]


# 各级判定返回原因
REASON_BC = "bc"                    # 该重背驰段成立
REASON_STRONGER = "stronger"        # 力度不弱于对照段, 背驰段不成立(课 61)
REASON_NO_EXTREME = "no_new_extreme"  # 未创新高/新低, 背驰不存在(课 61)
REASON_WEAK_SIGN = "weak_sign"      # 候选段柱面积符号与方向不符(动能异常)
REASON_NOT_NESTED = "not_nested"    # 相邻级别候选段区间不嵌套(结构断裂)
REASON_EMPTY = "empty"              # 空输入


class BcNestInput(object):
    """一重区间套层级的原始输入(一个级别的视图)

    参数:
        direction: 该级别走势方向 'up' / 'down'。
        ref_move: 对照段(围绕中枢的进入段或前一同向段)。鸭子类型,
            需 .high/.low/.start_dt/.end_dt, 笔/线段/走势类型通吃。
        cand_move: 候选段(假设中的背驰段, 通常为未走完的离开段)。
        bars: 该级别 K 线序列(list of dict), 默认力度口径(MACD 柱
            面积)用; 注入 strength_fn 时可不传(None)。
        center: 该级别中枢(可选, 有 .zd/.zg 属性即可), 仅落档供
            调用方核对"围绕同一中枢", 不参与判定。
    """

    def __init__(self, direction: str, ref_move: Any, cand_move: Any,
                 bars: Optional[List[Dict[str, Any]]] = None,
                 center: Any = None) -> None:
        self.direction = direction
        self.ref_move = ref_move
        self.cand_move = cand_move
        self.bars = bars
        self.center = center


class BcNestLevel(object):
    """一重背驰段的判定结果(课 61: 65 第一重 / 69 第二重 / 71 第三重……)"""

    def __init__(self, level: int, direction: str, bc: bool, reason: str,
                 ref_strength: Optional[float],
                 cand_strength: Optional[float],
                 ratio: Optional[float], new_extreme: Optional[bool],
                 start_dt: Any, end_dt: Any,
                 zd: Optional[float] = None, zg: Optional[float] = None) -> None:
        self.level = level            # 第几重(1 起, 级别自大到小)
        self.direction = direction    # 'up' 顶背驰链 / 'down' 底背驰链
        self.bc = bc                  # 该重背驰段是否成立
        self.reason = reason          # REASON_* 之一
        self.ref_strength = ref_strength   # 对照段力度(带符号面积)
        self.cand_strength = cand_strength  # 候选段力度
        self.ratio = ratio            # cand / ref(ref 为 0 时 None)
        self.new_extreme = new_extreme     # 是否创新高/新低(None=未判定)
        self.start_dt = start_dt      # 候选段起点
        self.end_dt = end_dt          # 候选段终点(该重的定位端点)
        self.zd = zd                  # 所属中枢下沿(仅落档)
        self.zg = zg                  # 所属中枢上沿(仅落档)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "direction": self.direction,
            "bc": self.bc,
            "reason": self.reason,
            "ref_strength": self.ref_strength,
            "cand_strength": self.cand_strength,
            "ratio": self.ratio,
            "new_extreme": self.new_extreme,
            "start_dt": str(self.start_dt),
            "end_dt": str(self.end_dt),
            "zd": self.zd,
            "zg": self.zg,
        }


class NestBcState(object):
    """整条嵌套背驰段链的判定结果

    complete=True 表示各重全部成立——区间套定位成立, 转折点被最内
    一级候选段端点精确锁定(课 61: "可以在当下精确地定位走势的转折点")。
    """

    def __init__(self, levels: List[BcNestLevel], complete: bool,
                 break_level: Optional[int], break_reason: str,
                 turn_dt: Optional[str] = None,
                 turn_price: Optional[float] = None) -> None:
        self.levels = levels         # 已判定各重(断裂前)
        self.complete = complete     # 是否区间套定位成立
        self.break_level = break_level   # 断裂在第几重(None=未断裂)
        self.break_reason = break_reason
        self.depth = len([x for x in levels if x.bc])  # 成立的重数
        self.turn_dt = turn_dt       # complete 时 = 最内一级候选段终点
        self.turn_price = turn_price  # complete 时 = 最内一级候选段极值

    def to_dict(self) -> Dict[str, Any]:
        return {
            "complete": self.complete,
            "depth": self.depth,
            "break_level": self.break_level,
            "break_reason": self.break_reason,
            "turn_dt": self.turn_dt,
            "turn_price": self.turn_price,
            "levels": [x.to_dict() for x in self.levels],
        }


def _move_extreme(move: Any, direction: str) -> float:
    """段的极值: up 段取 high / down 段取 low(内部工具)"""
    return float(move.high) if direction == "up" else float(move.low)


def _default_strength(bars: List[Dict[str, Any]], move: Any,
                      hist: Any, dt_map: Dict[str, int]) -> float:
    """默认力度口径: 段区间的 MACD 柱面积(带符号, 与 chan.bc 同源)"""
    return segment_area(hist, None, dt_map, move.start_dt, move.end_dt)


def _judge_level(direction: str, ref_move: Any, cand_move: Any,
                 ref_strength: float, cand_strength: float) -> Dict[str, Any]:
    """单级背驰段判定(课 61 三条规则; 内部工具, 纯函数)

    规则(向上, 向下镜像):
      1. 未创新高(cand.high <= ref.high) -> 背驰不存在;
      2. 候选段柱面积符号与方向不符 -> 动能异常, 不判背驰;
      3. 候选段力度不弱于对照段 -> 背驰段不成立; 反之背驰段成立。
      力度带符号: 上涨段红柱为正/下跌段绿柱为负, "更弱" = 面积
      绝对值更小 = 带符号值更接近 0(up: cand < ref; down:
      cand > ref)。
    """
    if direction == "up":
        new_extreme = float(cand_move.high) > float(ref_move.high)
    else:
        new_extreme = float(cand_move.low) < float(ref_move.low)
    if not new_extreme:
        # 课 61: "背驰如果没有创新高,是不存在的"
        return {"bc": False, "reason": REASON_NO_EXTREME,
                "new_extreme": False}
    if direction == "up" and cand_strength <= 0.0:
        return {"bc": False, "reason": REASON_WEAK_SIGN,
                "new_extreme": True}
    if direction == "down" and cand_strength >= 0.0:
        return {"bc": False, "reason": REASON_WEAK_SIGN,
                "new_extreme": True}
    if direction == "up":
        stronger = cand_strength >= ref_strength
    else:
        # 向下: 绿柱面积为负, 力度更强 = 更负
        stronger = cand_strength <= ref_strength
    if stronger:
        # 课 61: "一旦力度大于前者,那么就可以断定背驰段不成立"
        return {"bc": False, "reason": REASON_STRONGER,
                "new_extreme": True}
    return {"bc": True, "reason": REASON_BC, "new_extreme": True}


def _nested_in(inner: Any, outer: Any) -> bool:
    """inner 段区间是否嵌套于 outer 段区间内(含相等; 内部工具)

    按字符串比较(ISO 日期/时间戳字典序即时间序); 课 37 相邻级别
    同构递归要求下一级候选段在上一级候选段内部。
    """
    return (str(inner.start_dt) >= str(outer.start_dt)
            and str(inner.end_dt) <= str(outer.end_dt))


def nested_bc(inputs: List[BcNestInput],
              strength_fn: Optional[Callable[[List[Dict[str, Any]], Any],
                                             float]] = None) -> NestBcState:
    """多级区间套判定: 自大到小逐级判定嵌套背驰段链

    参数:
        inputs: 级别自大到小的 BcNestInput 列表。第 i+1 级的候选段
            必须落在第 i 级候选段区间内(课 37: 对离开段内部做次级别
            同构分析; 课 61: 背驰段的背驰段), 违反则链以
            REASON_NOT_NESTED 断裂。
        strength_fn: 自定义力度函数 strength_fn(bars, move) -> float;
            默认 MACD 柱面积(带符号)。同级别对照段/候选段共用一次
            MACD 计算。

    返回:
        NestBcState:
          - 任一级证伪 -> complete=False, break_level/break_reason
            指出断裂位置(证伪级之后的更细级别无须再看);
          - 全部成立 -> complete=True, turn_dt/turn_price = 最内
            一级候选段终点/极值, 即区间套定位出的转折点。

    边界: inputs 为空 -> complete=False, break_reason=REASON_EMPTY。
    """
    if not inputs:
        return NestBcState([], False, None, REASON_EMPTY)

    levels: List[BcNestLevel] = []
    break_level: Optional[int] = None
    break_reason: str = REASON_BC
    prev_cand: Any = None

    for i, inp in enumerate(inputs):
        lv = i + 1
        # 结构校验: 第 2 重起, 候选段须嵌套于上一重候选段内
        if prev_cand is not None and not _nested_in(inp.cand_move, prev_cand):
            break_level = lv
            break_reason = REASON_NOT_NESTED
            break

        # 力度: 默认 MACD 柱面积(该级一次计算, 两段共用)
        if strength_fn is not None:
            ref_s = float(strength_fn(inp.bars, inp.ref_move))
            cand_s = float(strength_fn(inp.bars, inp.cand_move))
        else:
            hist = macd_series(inp.bars)[2]
            dt_map = _dt_index(inp.bars)
            ref_s = _default_strength(inp.bars, inp.ref_move, hist, dt_map)
            cand_s = _default_strength(inp.bars, inp.cand_move, hist, dt_map)

        judged = _judge_level(inp.direction, inp.ref_move, inp.cand_move,
                              ref_s, cand_s)
        ratio = (cand_s / ref_s) if ref_s != 0.0 else None
        zd = getattr(inp.center, "zd", None) if inp.center is not None else None
        zg = getattr(inp.center, "zg", None) if inp.center is not None else None
        levels.append(BcNestLevel(
            level=lv, direction=inp.direction, bc=judged["bc"],
            reason=judged["reason"], ref_strength=ref_s,
            cand_strength=cand_s, ratio=ratio,
            new_extreme=judged["new_extreme"],
            start_dt=inp.cand_move.start_dt,
            end_dt=inp.cand_move.end_dt, zd=zd, zg=zg))

        if not judged["bc"]:
            break_level = lv
            break_reason = judged["reason"]
            break
        prev_cand = inp.cand_move

    complete = break_level is None
    turn_dt = None
    turn_price = None
    if complete:
        # 课 61: 转折点 = 最内一级背驰段的端点, 当下精确定位
        last_inp = inputs[-1]
        turn_dt = str(last_inp.cand_move.end_dt)
        turn_price = _move_extreme(last_inp.cand_move, last_inp.direction)
    return NestBcState(levels, complete, break_level, break_reason,
                       turn_dt, turn_price)
