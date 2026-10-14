# -*- coding: utf-8 -*-
"""严格趋势背驰结构条件与四类返回语义(课24/27/37/53/61/101, R3)。

规格: doc/缠论理论逐一实现计划.md §11.6(2026-10-13草稿)。与
0.7.5 MACD辅助候选(first.py)的分别: 本模块只判结构必要条件,
不内置力度方法; 力度度量是显式注入证据, 未注入时结构闭合也只
登记证据不足, 不输出成立。MACD辅助候选不因本模块存在而改名
严格(课24明示MACD"不绝对精确")。

原文关键定义(直接引文):

    课37: "没有趋势, 没有背驰"。a+A+b+B+c 是趋势的前提是 A、B
    是同级别的中枢; "c 必然是次级别的", "c 中至少要包含对 B 的
    一个第三类买卖点", 否则整个走势只是围绕中枢 B 的震荡, "需要
    用盘整背驰"处理; "b 的级别, 最多不能大于 c 的级别"。
    课61: "背驰如果没有创新高, 是不存在的"; "只要是围绕一中枢的
    两段走势都可以比较力度"; 未完成段"都可以先假设是进入背驰段"。
    课53: 盘整背驰"只是利用前者相应的力度分析方法进行的一个推广
    用法"。

比较窗口(与first.py同构造): b=前中枢最后回抽之后至末中枢覆盖
起点之前, c=末中枢最后回抽之后至走势终点; 中枢周围波动分离按
课20用两中枢覆盖单元极值比较。与first.py的两处差异: 先验极值
窗口取本趋势c首单元之前的全部单元(课37"创新高"为整段新极值,
first.py只比末中枢波动); 不设比较段方向排除, c末单元为回抽时
由internal_extreme_time_unknown细分(first.py粗粒度排除)。

结构必要条件(违反即定语义; 条件码见conditions):

    trend          完成趋势且至少两个依次同向的同级别中枢(课27/37);
    separated_centers  前后中枢周围波动严格分离(课20/61);
    new_extreme    c极值超越全趋势先验极值且极值恰在c端点,
                   否则背驰不存在(课37/61); 极值在c内部时
                   单元级数据不能定位极值发生时刻, 登记待判;
    leave_third_point  c内含末中枢的次级别三类买卖点(课37)——
                   c内反向单元不与末中枢区间重叠(重叠则延伸
                   覆盖或提前完成切分), 其前一单元端点必在
                   区间外, 恰构成"离开结束于区间外+首次回试
                   不重回"的三类结构(check_leave_third),
                   触沿不发生。

返回语义(四类, 每项保留方法、比较单元身份、趋势/中枢身份、
证据身份与最晚确认时间):

    candidate           结构未闭合(开放尾部趋势), 登记当前依据
                        (课61"先假设进入背驰段"); 同一尾部起点
                        使用同一身份, 尾部完成后该身份落为最终
                        语义;
    confirmed           结构闭合+力度支持——本版本力度未接入,
                        恒不可达, 留给力度注入版本;
    insufficient_evidence  结构闭合但必需证据缺失(力度方法未
                        注入/内部极值时间未知/零宽中枢无法表达);
    rejected            任一必要结构条件被反例否定(无新极值、
                        c无三类点、中枢波动重叠)。

差异声明: b/c 均由同级输入单元组成, "b级别不大于c"由构造满足,
连续缺口等更小级别b不由本模块推断; 确认时间取完成趋势实际冻结
时刻, 不回填端点时间(课37/65口径, 分型/笔端点时间不等于确认
时间)。完成趋势结果冻结; 开放尾部候选随观察前缀演进。bars不
由本入口消费: 结构证据全部来自已确认单元, 力度方法注入属后续
版本。
"""

from collections import namedtuple
import json

from chan.completion import _visible_units, confirm_level_up
from chan.first import _net, _tail
from chan.recurse import _level_up_traced
from chan.second import _price

# 四类返回语义(R3规格§11.6): 候选/成立/证据不足/否决。
STRICT_CANDIDATE = 'candidate'
STRICT_CONFIRMED = 'confirmed'
STRICT_INSUFFICIENT = 'insufficient_evidence'
STRICT_REJECTED = 'rejected'


class StrictDivergence(namedtuple('StrictDivergenceBase',
                                  'divergence_id kind level status reason trend_id '
                                  'center_id center_range reference_ids leave_ids '
                                  'conditions confirmed_dt dt price')):
    """严格趋势背驰单结果: 四类语义之一及完整证据链。

    kind为buy1/sell1; reason为该语义的最小条件码; conditions为
    已评估结构条件(code, passed/None)元组, 供逐项审计; 开放尾部
    候选中未决条件记None。center_id/center_range为末中枢身份与
    冻结(zd,zg); reference_ids/leave_ids为比较段单元身份; 价格
    单位沿用输入坐标。confirmed_dt为该结果所需证据的最晚确认
    时刻, 不早于任何被消费证据(课37/65口径)。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('confirmed_dt', 'dt'):
            out[key] = str(out[key])
        out['center_range'] = list(self.center_range)
        out['conditions'] = [list(pair) for pair in self.conditions]
        return out


class StrictScan(namedtuple('StrictScanBase',
                            'results skipped completed_types open_tail')):
    """扫描容器: results为四类语义结果, skipped为不构成趋势背驰
    问题的完成项/开放尾部(身份与原因码), completed_types为完成
    走势数, open_tail为是否存在未完成尾部。
    """
    __slots__ = ()


def _identity(parts):
    return json.dumps(list(parts), ensure_ascii=False, separators=(',', ':'))


def check_leave_third(leave, kind):
    """c内末中枢次级别三类买卖点判定(课37; 课20三类口径)。

    c由末中枢最后回抽之后的单元组成(_tail保证末中枢覆盖区间内
    其后无反向单元), c内反向单元不与末中枢区间重叠(重叠则该单元
    延伸覆盖或触发提前完成切分), 其前一单元端点必在区间外, 故
    恰构成"离开结束于区间外+首次回试不重回"的三类结构, 触沿不
    发生。返回c是否含三类回试。
    """
    opposite = 'down' if kind == 'up' else 'up'
    for unit in leave:
        if _net(unit) == opposite:
            return True
    return False


def _new_extreme_state(leave, kind, prior_high, prior_low):
    """新极值条件(课37/61): c极值超越先验极值为made, c端点即
    极值为at_endpoint; 端点非极值时单元级数据不能定位极值发生
    时刻, 由调用方登记待判, 不把净端点叫背驰极值。
    """
    price = _price(leave[-1].end_price)
    if kind == 'up':
        extreme = max(_price(u.high) for u in leave)
        return extreme > prior_high, price == extreme
    extreme = min(_price(u.low) for u in leave)
    return extreme < prior_low, price == extreme


def _pivot_extremes(prefix, span, end):
    units = prefix[span[0]:end+1]
    return (min(_price(u.low) for u in units),
            max(_price(u.high) for u in units))


def _evaluate_completed(trend, move, prefix, spans):
    """完成趋势结构条件评估: 依次判separated/new_extreme/
    leave_third_point, 首个否决即rejected; 结构闭合无力度方法
    登记insufficient/force_missing。不构成趋势背驰问题返回
    (None, skipped原因)。
    """
    previous, last = spans[-2:]
    direction = trend.kind
    prev_end = _tail(prefix, previous, direction)
    last_end = _tail(prefix, last, direction)
    if prev_end is None or last_end is None:
        return None, 'no_comparable_center_tail'
    reference = prefix[prev_end+1:last[0]]
    leave = prefix[last_end+1:move.seg_end+1]
    if not reference or not leave:
        return None, 'no_compare_legs'
    p_low, p_high = _pivot_extremes(prefix, previous, prev_end)
    c_low, c_high = _pivot_extremes(prefix, last, last_end)
    up = direction == 'up'
    conditions = [('trend', True)]
    if not (c_low > p_high if up else c_high < p_low):
        # 课20: 不仅ZD/ZG, 中枢周围波动也不得重叠。
        return (STRICT_REJECTED, 'center_waves_overlap',
                conditions + [('separated_centers', False)],
                reference, leave, None)
    conditions.append(('separated_centers', True))
    zd, zg = [_price(v) for v in trend.centers[-1]]
    if zd == zg:
        # 零宽中枢: 三类点围绕关系无法在当前接口表达, 登记证据
        # 不足而非否决(R3规格边界清单)。
        return (STRICT_INSUFFICIENT, 'zero_width_center',
                conditions + [('leave_third_point', None)],
                reference, leave, (zd, zg))
    prior = prefix[move.seg_start:last_end+1]
    prior_high = max(_price(u.high) for u in prior)
    prior_low = min(_price(u.low) for u in prior)
    made, at_endpoint = _new_extreme_state(leave, direction,
                                           prior_high, prior_low)
    if not made:
        # 课61: 背驰如果没有创新高新低, 是不存在的。
        return (STRICT_REJECTED, 'no_new_extreme',
                conditions + [('new_extreme', False)],
                reference, leave, (zd, zg))
    if not at_endpoint:
        # 内部极值不猜发生时刻, 不把净端点叫背驰极值。
        return (STRICT_INSUFFICIENT, 'internal_extreme_time_unknown',
                conditions + [('new_extreme', None)],
                reference, leave, (zd, zg))
    conditions.append(('new_extreme', True))
    third = check_leave_third(leave, direction)
    conditions.append(('leave_third_point', third))
    if not third:
        # 课37: c不含末中枢三类点则只是围绕B的震荡, 用盘整背驰。
        return (STRICT_REJECTED, 'no_third_point_in_leave',
                conditions, reference, leave, (zd, zg))
    # 结构全闭合; 力度证据未注入, 不冒充成立(R3规格: 单次面积
    # 减弱不作严格证明, 必要证据缺失登记证据不足)。
    return (STRICT_INSUFFICIENT, 'force_missing', conditions,
            reference, leave, (zd, zg))


def _evaluate_open_tail(move, spans, prefix):
    """开放尾部趋势候选(课61"先假设进入背驰段"): 两个及以上
    中枢且离开段已开始才登记, 未决条件记None随前缀演进; 其余
    返回(None, skipped原因)。
    """
    if len(spans) < 2 or move.kind not in ('up', 'down'):
        return None, 'not_two_separated_centers'
    previous, last = spans[-2:]
    direction = move.kind
    prev_end = _tail(prefix, previous, direction)
    last_end = _tail(prefix, last, direction)
    if prev_end is None or last_end is None:
        return None, 'no_comparable_center_tail'
    reference = prefix[prev_end+1:last[0]]
    leave = prefix[last_end+1:]
    if not reference or not leave:
        return None, 'no_compare_legs'
    p_low, p_high = _pivot_extremes(prefix, previous, prev_end)
    c_low, c_high = _pivot_extremes(prefix, last, last_end)
    up = direction == 'up'
    if not (c_low > p_high if up else c_high < p_low):
        return None, 'center_waves_overlap'
    zd, zg = [_price(v) for v in move.centers[-1]]
    if zd == zg:
        return None, 'zero_width_center'
    prior = prefix[move.seg_start:last_end+1]
    prior_high = max(_price(u.high) for u in prior)
    prior_low = min(_price(u.low) for u in prior)
    made, _ = _new_extreme_state(leave, direction, prior_high, prior_low)
    third = check_leave_third(leave, direction)
    conditions = [('trend', None), ('separated_centers', True),
                  ('new_extreme', True if made else None),
                  ('leave_third_point', True if third else None)]
    return ('candidate', 'trend_open', conditions, reference,
            leave, (zd, zg), direction)


def scan_strict_divergence(units, as_of, level):
    """已确认次级类型上的严格趋势背驰结构扫描(四类返回语义)。

    units与confirm_level_up同契约: 同标的/价格坐标、同级、时间
    及端点价格连续的ConfirmedMove/ConfirmedMoveType, 只消费
    as_of前已确认连续前缀。level为趋势级别名(不同于输入级别,
    不猜K线周期)。返回StrictScan: 每个完成上涨/下跌趋势一个
    冻结结果(结构闭合无力度方法时insufficient_evidence/
    force_missing, 条件否决时rejected并保留首个否决条件), 开放
    尾部两个及以上严格分离中枢且离开段已开始时登记candidate/
    trend_open(同一尾部起点同一身份, 随前缀演进, 完成后该身份
    落为最终语义)。盘整完成项与不满足两分离中枢的尾部记入
    skipped。确认不早于最后证据; 未来身份/价格不读取。复杂度
    O(n^2)最坏, 无跨调用缓存。
    """
    visible = _visible_units(units, as_of, level)[0]
    results, skipped = [], []
    completed = confirm_level_up(visible, as_of, level)
    for trend in completed:
        if trend.kind not in ('up', 'down'):
            skipped.append((trend.move_id, 'not_trend'))
            continue
        prefix = [u for u in visible if u.move_id in trend.evidence_ids]
        decomposed, traces = _level_up_traced(prefix)
        pair = next(((m, spans) for m, spans in zip(decomposed, traces)
                     if m.complete and m.start_dt == trend.start_dt), None)
        if pair is None:
            skipped.append((trend.move_id, 'no_matching_decomposition'))
            continue
        move, spans = pair
        outcome = _evaluate_completed(trend, move, prefix, spans)
        if outcome[0] is None:
            skipped.append((trend.move_id, outcome[1]))
            continue
        status, reason, conditions, reference, leave, center_range = outcome
        up = trend.kind == 'up'
        identity = _identity([level, prefix[move.seg_start].move_id, 'strict1'])
        results.append(StrictDivergence(
            identity, 'sell1' if up else 'buy1', level,
            status, reason, trend.move_id,
            _identity([level, prefix[spans[-1][0]].move_id]), center_range,
            tuple(u.move_id for u in reference), tuple(u.move_id for u in leave),
            tuple(conditions), trend.confirmed_dt,
            leave[-1].end_dt, _price(leave[-1].end_price)))
    open_tail = False
    if visible:
        decomposed, traces = _level_up_traced(visible)
        tail_move, tail_spans = decomposed[-1], traces[-1]
        open_tail = not tail_move.complete
        if open_tail:
            tail_id = _identity([level, visible[tail_move.seg_start].move_id])
            outcome = _evaluate_open_tail(tail_move, tail_spans, visible)
            if outcome[0] is None:
                skipped.append((tail_id, outcome[1]))
            else:
                _, reason, conditions, reference, leave, center_range, direction = outcome
                results.append(StrictDivergence(
                    _identity([level, visible[tail_move.seg_start].move_id,
                               'strict1']),
                    'sell1' if direction == 'up' else 'buy1', level,
                    STRICT_CANDIDATE, reason, tail_id,
                    _identity([level, visible[tail_spans[-1][0]].move_id]),
                    center_range,
                    tuple(u.move_id for u in reference),
                    tuple(u.move_id for u in leave),
                    tuple(conditions), visible[-1].confirmed_dt,
                    leave[-1].end_dt, _price(leave[-1].end_price)))
    return StrictScan(tuple(results), tuple(skipped), len(completed), open_tail)
