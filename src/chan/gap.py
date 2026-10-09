# -*- coding: utf-8 -*-
"""
chan.gap —— 缺口识别与力度三分类

理论依据: 《教你炒股票 108 课》第 77 课「一些概念的再分辨」(2007-09-05)。

原文关键定义(课 77, 直接引文):
    「何谓缺口, 就是在该单位 K 线图上两相邻的 K 线间出现没有成交的区间。
    例如, 在上海指数日线单位的 K 线图里, 1994 年的 7 月 29 日与 8 月 1 日,
    就出现 [339,377] 这个区间没有成交。那就说, [339,377] 是一缺口。」

    「而缺口的回补, 就是在缺口出现后, 该缺口区间最终全部再次出现成交的
    过程。这个过程, 可能在下一 K 线就出现, 也可能永远不再出现。」

力度三分类(课 77, 直接引文):
    「根据缺口的是否回补, 就构成了对走势行情力度的一个分类。
    一、不回补, 这显然是强势的;
    二、回补后继续新高或新低, 这是平势的;
    三、回补后不能新高、新低, 因而出现原来走势的转折, 这是弱势的。」

衰竭性缺口(课 77, 直接引文):
    「而一旦缺口回补后不再新高、新低, 那么就意味着原来的趋势发生逆转,
    这是衰竭性缺口的特征, 一旦出现这种情况, 就一定至少出现较大级别的
    调整, 这级别至少大于缺口时所延续的趋势的级别。」

实现口径声明(与理论的差异/取舍):
    1. 缺口识别使用**原始 K 线**(两相邻 bar 的高低点), 不使用包含处理
       后的合并 K 线——原文明确说"该单位 K 线图上两相邻的 K 线", 合并
       K 线不是"单位 K 线图上的 K 线";
    2. 相邻两 K 线取严格不等式判定(向上缺口: 前高 < 后低)。若前高恰好
       等于后低, 则该价位在两根 K 线上都出现过成交, 不构成"没有成交的
       区间", 不算缺口;
    3. 回补采用**忠实原文的区间覆盖判定**: 缺口区间 [lower, upper] 内的
       每个价位都要在此后某根 K 线的 [low, high] 范围内再次出现成交,
       即后续 K 线区间的并集完全覆盖缺口区间, 才算回补完成。常见简化
       口径"回补 = 价格触及缺口远端边界"(如向上缺口回补 = 后续某根
       K 线 low <= lower)在绝大多数场景下与本判定等价, 但当后续行情以
       反向缺口"跳过"缺口区间的一部分且该部分此后再未成交时, 两者结论
       不同——此时按原文"该缺口区间**全部**再次出现成交"的字面定义,
       应判为**未回补**, 本模块以覆盖判定为准;
    4. K 线内部价格路径不可知(OHLC 只有极值), 回补完成时刻定位到"完成
       覆盖的那根 K 线"; "回补后继续新高/新低"的判定同样出于时序保守
       起见, 只统计**回补完成 K 线之后**的 K 线(不含当根), 详见
       classify_gap 的 docstring;
    5. 突破性/中继性/普通缺口的三分性质(课 77: 突破性极少回补、中继性
       回补几率对半但一定继续新高新低、盘整中的普通缺口一般都回补且
       意义仅在"中枢震荡回拉目标")依赖缺口所处的**走势类型上下文**
       (趋势还是盘整), 属走势类型层(1c/阶段 2)的判定, 本模块只输出
       力度三分类, 不做性质三分;
    6. 「这里的级别和缺口所在的 K 线图无关, 只和理论中的走势类型级别
       有关」(课 77)——衰竭性缺口"至少制造更大级别调整"的级别推断
       同样依赖走势类型级别, 本模块仅在 weak 分类上标注衰竭特征,
       不推断调整级别。

兼容: Python 3.6, 仅标准库 + typing。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["Gap", "find_gaps", "classify_gap"]


class Gap(object):
    """缺口对象: 两相邻 K 线间没有成交的区间(课 77 定义)

    属性:
        direction: 缺口方向。"up" = 向上缺口(前高 < 后低, 缺口在上方),
            对应原文以向上为例的定义; "down" = 向下缺口(前低 > 后高)。
        lower: 缺口区间下沿(float)。向上缺口 = 前一根 K 线的 high,
            向下缺口 = 后一根 K 线的 high。
        upper: 缺口区间上沿(float)。向上缺口 = 后一根 K 线的 low,
            向下缺口 = 前一根 K 线的 low。
            区间 [lower, upper] 即原文"没有成交的区间"(边界价位本身
            在形成缺口的两根 K 线上是有成交的, 无成交的是区间内部)。
        dt_a / dt_b: 形成缺口的前/后两根 K 线的 dt(原类型透传)。
        index_a / index_b: 前/后两根 K 线在 bars 序列中的下标(int)。
    """

    def __init__(self, direction: str, lower: float, upper: float,
                 dt_a: Any, dt_b: Any, index_a: int, index_b: int) -> None:
        self.direction = direction
        self.lower = lower
        self.upper = upper
        self.dt_a = dt_a
        self.dt_b = dt_b
        self.index_a = index_a
        self.index_b = index_b

    def __repr__(self) -> str:
        return "Gap({0}[{1}, {2}] a={3} b={4})".format(
            self.direction, self.lower, self.upper, self.dt_a, self.dt_b)

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(存档/序列化用, 字段与属性一一对应)"""
        return {
            "direction": self.direction,
            "lower": self.lower,
            "upper": self.upper,
            "dt_a": self.dt_a,
            "dt_b": self.dt_b,
            "index_a": self.index_a,
            "index_b": self.index_b,
        }


def find_gaps(bars: List[Dict[str, Any]]) -> List[Gap]:
    """识别序列中全部缺口(课 77 定义)

    理论依据(课 77): 「何谓缺口, 就是在该单位 K 线图上两相邻的 K 线间
    出现没有成交的区间。」

    参数:
        bars: 标准 bar 序列(normalize_bars 输出, 按 dt 升序)。应为
            **原始 K 线**且已剔除停牌 bar(normalize_bars 的
            drop_paused=True 默认行为)——停牌 bar 与相邻 bar 之间的
            "缺口"是停牌伪影而非市场缺口, 不应进入统计。

    返回:
        list of Gap, 按 index_a 升序(即按时间顺序)。相邻两 K 线:
        - 向上缺口: bars[i].high < bars[i+1].low, 区间
          [bars[i].high, bars[i+1].low](前高 < 后低, 中间无成交);
        - 向下缺口: bars[i].low > bars[i+1].high, 区间
          [bars[i+1].high, bars[i].low](后高 < 前低, 中间无成交);
        - 前高 == 后低(或前低 == 后高)不算缺口: 该价位在两根 K 线上
          都有成交, 不存在"没有成交的区间"。

    边界行为: 少于 2 根 K 线返回 []。
    """
    gaps: List[Gap] = []
    if len(bars) < 2:
        # 少于两根 K 线不存在"两相邻 K 线", 自然没有缺口
        return gaps

    for i in range(len(bars) - 1):
        a = bars[i]
        b = bars[i + 1]
        if a["high"] < b["low"]:
            # 向上缺口: 前根最高价低于后根最低价, [前高, 后低] 无成交。
            # 原文示例: 1994-07-29 高点 339 与 1994-08-01 低点 377 之间
            # 的 [339,377] 即此类缺口。
            gaps.append(Gap("up", a["high"], b["low"],
                            a["dt"], b["dt"], i, i + 1))
        elif a["low"] > b["high"]:
            # 向下缺口: 前根最低价高于后根最高价, [后高, 前低] 无成交
            gaps.append(Gap("down", b["high"], a["low"],
                            a["dt"], b["dt"], i, i + 1))
        # else: 两根 K 线价格区间相接或重叠, 无缺口
    return gaps


def _fill_gap(gap: Gap, bars: List[Dict[str, Any]]) -> Optional[int]:
    """计算缺口回补完成的 K 线下标(内部函数)

    理论依据(课 77): 「缺口的回补, 就是在缺口出现后, 该缺口区间最终
    全部再次出现成交的过程。」

    算法(区间覆盖判定, 见模块 docstring 口径声明第 3 条):
        维护"尚未再次出现成交"的缺口子区间集合 pieces(初始为整个缺口
        区间 [lower, upper]); 逐根扫描缺口之后的 K 线, 把该 K 线的
        价格区间 [low, high] 从 pieces 中减去(一根 K 线的 [low, high]
        视为已全部成交——K 线内部路径不可知, 取极值区间为成交范围,
        这是 K 线分析的通行假设); pieces 为空即回补完成, 返回当前
        K 线下标; 扫描结束 pieces 仍非空则未回补, 返回 None。

    为什么不能简化为"价格触及缺口远端边界即回补":
        若后续行情以反向缺口跳过缺口区间的一部分(该部分价位再未
        成交), 触及远端边界时缺口区间并未"全部再次出现成交", 按
        原文字面定义不算回补。
    """
    # pieces: 尚未再次成交的闭子区间列表(保持互不相交)。
    # 闭区间口径: 边界价位视为"触线即覆盖", 精确到价位的开闭差异
    # 在实数价格下无实际意义(见模块 docstring 口径声明)。
    pieces: List[Tuple[float, float]] = [(gap.lower, gap.upper)]

    for k in range(gap.index_b + 1, len(bars)):
        lo = bars[k]["low"]
        hi = bars[k]["high"]
        rest: List[Tuple[float, float]] = []
        for (a, b) in pieces:
            # 判断 K 线区间 [lo, hi] 与子区间 [a, b] 是否有重叠
            if hi < a or lo > b:
                # 无重叠(相接 hi == a 或 lo == b 视为触线覆盖,
                # 不落入此分支): 该子区间保持未成交
                rest.append((a, b))
                continue
            # 有重叠: 减去 [lo, hi] 后剩余左侧 [a, lo] / 右侧 [hi, b]
            # (仅当严格越过时存在剩余)
            if a < lo:
                # 左侧剩余: K 线区间左端 lo 高于子区间左端 a,
                # [a, lo] 这段仍未再次成交
                rest.append((a, lo))
            if hi < b:
                # 右侧剩余: K 线区间右端 hi 低于子区间右端 b,
                # [hi, b] 这段仍未再次成交
                rest.append((hi, b))
        pieces = rest
        if not pieces:
            # 全部价位都已再次出现成交——回补完成于第 k 根 K 线
            return k
    # 序列结束仍未全覆盖: 缺口未回补(原文: 「也可能永远不再出现」)
    return None


def classify_gap(gap: Gap, bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """缺口力度三分类(课 77: 强势 / 平势 / 弱势)

    理论依据(课 77): 「根据缺口的是否回补, 就构成了对走势行情力度的
    一个分类。一、不回补, 这显然是强势的; 二、回补后继续新高或新低,
    这是平势的; 三、回补后不能新高、新低, 因而出现原来走势的转折,
    这是弱势的。」

    判定规则(以向上缺口为例, 向下缺口镜像):
        1. 未回补 -> strength="strong"(一、不回补, 强势);
        2. 回补完成后, 在**回补完成 K 线之后**的 K 线里出现 high 超过
           回补前趋势已达到的最高价(参照极值 ref, 含回补完成 K 线
           本身的高点) -> strength="neutral"(二、回补后继续新高, 平势);
        3. 已回补但此后未再出现新高 -> strength="weak"(三、回补后
           不能新高, 弱势; 即衰竭性缺口特征——原文: 「一旦缺口回补后
           不再新高、新低, 那么就意味着原来的趋势发生逆转」)。

    参照极值 ref 的取法(重要口径):
        ref = 缺口形成后(第 index_b 根起)至回补完成 K 线(含)之间,
              向上缺口取最高 high / 向下缺口取最低 low。
        即"新高/新低"的比较基准是**回补发生前趋势本身已经达到的极值**,
        而不是缺口区间的边界。
        例: 向上缺口 [10,12] 出现后行情最高涨到 15, 随后回落回补缺口,
        则"继续新高"要求此后再出现 high > 15, 而不是 > 12。

    为什么"回补后继续新高"只统计回补完成 K 线**之后**的 K 线:
        K 线内部价格路径不可知(OHLC 只有极值), 回补完成那根 K 线
        自身的高点无法区分"回补在前、冲高在后"(应算继续新高)还是
        "冲高在前、回落回补在后"(新高发生在回补之前, 不满足原文
        「回补**后**继续新高」的时序)。保守起见, 该根 K 线的极值计入
        参照基准 ref, 继续新高/新低必须在后续 K 线中体现。

    参数:
        gap: find_gaps 输出的缺口对象。
        bars: 与 find_gaps 相同的完整 bar 序列(gap 的下标基于它)。

    返回: dict, 字段:
        status: "unfilled"(未回补) / "filled_new_extreme"(回补后
            继续新高或新低) / "filled_no_new_extreme"(回补后不能
            新高、新低);
        strength: "strong" / "neutral" / "weak"(课 77 力度三分类,
            与 status 一一对应: 不回补=强势 / 回补后继续新高新低=
            平势 / 回补后不能新高新低=弱势);
        exhaustion: 布尔。True = 具备衰竭性缺口特征(仅 weak 时 True;
            原文: 衰竭性缺口意味着原趋势逆转, 至少出现更大级别调整,
            调整级别推断依赖走势类型上下文, 此处只标注特征);
        fill_index / fill_dt: 回补完成的 K 线下标与 dt, 未回补为 None;
        extreme_value: "新高/新低"的参照极值 ref(未回补时为 None;
            已回补时 = 缺口形成后至回补完成 K 线(含)的趋势极值,
            向上缺口为区间内最高 high, 向下缺口为区间内最低 low)。

    边界行为: 序列在缺口形成后立即结束(无后续 K 线)视为未回补。
    """
    result: Dict[str, Any] = {
        "status": "unfilled",
        "strength": "strong",
        "exhaustion": False,
        "fill_index": None,
        "fill_dt": None,
        "extreme_value": None,
    }

    # 第一步: 判定回补(课 77: 「该缺口区间最终全部再次出现成交」)
    fill_index = _fill_gap(gap, bars)
    if fill_index is None:
        # 「一、不回补, 这显然是强势的」——未回补即强势, 分类结束
        return result

    result["status"] = "filled_no_new_extreme"  # 先按三预设, 下面修正
    result["strength"] = "weak"
    result["fill_index"] = fill_index
    result["fill_dt"] = bars[fill_index]["dt"]

    # 第二步: 计算"新高/新低"参照极值 ref
    # 区间 = [index_b, fill_index] 闭区间: 从缺口后第一根 K 线起、
    # 到回补完成 K 线(含)为止——趋势在回补发生前已达到的极值
    if gap.direction == "up":
        # 向上缺口: 参照极值 = 该区间内最高 high(继续新高的基准)
        ref = max(bars[k]["high"] for k in range(gap.index_b, fill_index + 1))
    else:
        # 向下缺口: 参照极值 = 该区间内最低 low(继续新低的基准)
        ref = min(bars[k]["low"] for k in range(gap.index_b, fill_index + 1))
    result["extreme_value"] = ref

    # 第三步: 回补完成 K 线之后是否出现继续新高/新低
    # (时序口径见 docstring: 只统计 fill_index 之后的 K 线)
    made_new_extreme = False
    for k in range(fill_index + 1, len(bars)):
        if gap.direction == "up":
            # 向上缺口: 「回补后继续新高」= 后续出现 high 严格超过 ref
            # (等于 ref 不算新高)
            if bars[k]["high"] > ref:
                made_new_extreme = True
                break
        else:
            # 向下缺口: 「回补后继续新低」= 后续出现 low 严格低于 ref
            if bars[k]["low"] < ref:
                made_new_extreme = True
                break

    if made_new_extreme:
        # 「二、回补后继续新高或新低, 这是平势的」
        result["status"] = "filled_new_extreme"
        result["strength"] = "neutral"
    else:
        # 「三、回补后不能新高、新低, 因而出现原来走势的转折,
        # 这是弱势的」——衰竭性缺口特征(课 77), 调整级别推断
        # 依赖走势类型上下文, 此处只做标注
        result["status"] = "filled_no_new_extreme"
        result["strength"] = "weak"
        result["exhaustion"] = True

    return result
