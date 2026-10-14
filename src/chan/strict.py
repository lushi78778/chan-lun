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
                        语义; 不评估力度(开放段力度单调性依
                        赖度量定义, 课61"力度大于比较段即不
                        成立"由力度方法自身语义处理);
    confirmed           结构闭合+注入力度方法支持(c段力度严格
                        弱于b段); 力度方法保留自身身份与局限,
                        不冒充理论证明(课24口径);
    insufficient_evidence  结构闭合但必需证据缺失(力度方法未
                        注入/力度方法对该输入不可用/内部极值
                        时间未知/零宽中枢无法表达);
    rejected            任一必要结构条件或注入力度被反例否定
                        (无新极值、c无三类点、中枢波动重叠、
                        力度不减)。

力度注入契约: force_fn(reference_units, leave_units)返回
(reference_force, leave_force)数值对; 返回None表示该方法在
该输入上不可用(数据缺失等), 登记证据不足不否决。注入时必须
以force_method声明方法身份字符串, 保留方法身份与局限。
travel_force为内置示例方法(单元行程和), 是工程示例度量,
不称走势真实力度(不含单元内部次级结构信息)。

差异声明: b/c 均由同级输入单元组成, "b级别不大于c"由构造满足,
连续缺口等更小级别b不由本模块推断; 确认时间取完成趋势实际冻结
时刻, 不回填端点时间(课37/65口径, 分型/笔端点时间不等于确认
时间)。完成趋势结果冻结; 开放尾部候选随观察前缀演进。bars不
由本入口消费: 结构证据全部来自已确认单元; 力度方法消费单元
序列, 消费K线的力度方法属调用方适配层。

区间套次级确认链(0.10.4): strict_nested_chain把课61区间套定位
显式化——重1为严格扫描结果, 重2起逐重显式供给更细级别单元,
在上一重背驰段区间内取最后一个次级中枢, 围绕它比较两段力度
(课61/课53盘整背驰推广, 不要求重2起内部再构成两个分离中枢)。
无否定证据继续下探(课61"在没有证据否定背驰之前"), 否决即断;
子单元须与上一重背驰段区间时间首尾相等且端点价格对齐; 转折
取最内bc重段终点与极值价格, 单元级数据不定位极值发生时刻。

次级走势完成级联确认(0.10.5): strict_completion_cascade复核
父级背驰段端点单元(含转折端点的次级别走势)的完成——课37
"c 必然是次级别的"; 课35"一个高级别的走势类型必然就是由几个
低级别的走势类型连接而成"、分解定理二"任何级别的任何走势
类型, 都至少由三段以上次级别走势类型构成", 完成由细级完成
证据到达时刻冻结(completion.py契约)。逐层细级切片与上层端点
单元区间时间首尾相等且端点价格对齐, 切片上重算完成类型, 恰
覆盖该区间的完成类型即该层复核通过并级联至其末组成单元;
无匹配完成类型登记unverified(调用方声明口径与细级证据不同
或证据不足以复核, 不判任一方错误), 不判实现或标注错误。
"""

from collections import namedtuple
import json

from chan._intervals import _range3
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
                                  'force_method force_reference force_leave '
                                  'conditions confirmed_dt dt price')):
    """严格趋势背驰单结果: 四类语义之一及完整证据链。

    kind为buy1/sell1; reason为该语义的最小条件码; conditions为
    已评估结构条件(code, passed/None)元组, 供逐项审计; 开放尾部
    候选中未决条件记None。center_id/center_range为末中枢身份与
    冻结(zd,zg); reference_ids/leave_ids为比较段单元身份; 价格
    单位沿用输入坐标。force_method为力度方法身份(未注入或候选
    未评估为None), force_reference/force_leave为注入方法返回的
    比较段力度值(未评估为None)。confirmed_dt为该结果所需证据的
    最晚确认时刻, 不早于任何被消费证据(课37/65口径)。
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


def travel_force(units):
    """单元行程力度示例方法: sum(high-low)。

    工程示例度量, 不称走势真实力度: 单元内部次级结构信息不
    由已确认单元端点表达, 中枢内回抽行程计入段力度。作为
    force_fn注入示例保留方法身份与局限(课24口径), 不冒充
    理论力度度量。
    """
    return float(sum(_price(u.high) - _price(u.low) for u in units))


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


def _evaluate_completed(trend, move, prefix, spans, force_fn):
    """完成趋势结构条件评估: 依次判separated/new_extreme/
    leave_third_point, 首个否决即rejected; 结构闭合后按注入
    力度方法判confirmed/rejected/insufficient。不构成趋势背驰
    问题返回(None, skipped原因)。
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
                reference, leave, None, None, None, None)
    conditions.append(('separated_centers', True))
    zd, zg = [_price(v) for v in trend.centers[-1]]
    if zd == zg:
        # 零宽中枢: 三类点围绕关系无法在当前接口表达, 登记证据
        # 不足而非否决(R3规格边界清单)。
        return (STRICT_INSUFFICIENT, 'zero_width_center',
                conditions + [('leave_third_point', None)],
                reference, leave, (zd, zg), None, None, None)
    prior = prefix[move.seg_start:last_end+1]
    prior_high = max(_price(u.high) for u in prior)
    prior_low = min(_price(u.low) for u in prior)
    made, at_endpoint = _new_extreme_state(leave, direction,
                                           prior_high, prior_low)
    if not made:
        # 课61: 背驰如果没有创新高新低, 是不存在的。
        return (STRICT_REJECTED, 'no_new_extreme',
                conditions + [('new_extreme', False)],
                reference, leave, (zd, zg), None, None, None)
    if not at_endpoint:
        # 内部极值不猜发生时刻, 不把净端点叫背驰极值。
        return (STRICT_INSUFFICIENT, 'internal_extreme_time_unknown',
                conditions + [('new_extreme', None)],
                reference, leave, (zd, zg), None, None, None)
    conditions.append(('new_extreme', True))
    third = check_leave_third(leave, direction)
    conditions.append(('leave_third_point', third))
    if not third:
        # 课37: c不含末中枢三类点则只是围绕B的震荡, 用盘整背驰。
        return (STRICT_REJECTED, 'no_third_point_in_leave',
                conditions, reference, leave, (zd, zg), None, None, None)
    if force_fn is None:
        # 力度方法未注入, 不冒充成立(R3规格: 结构闭合不等于力度
        # 证明, 必要证据缺失登记证据不足)。
        return (STRICT_INSUFFICIENT, 'force_missing', conditions,
                reference, leave, (zd, zg), None, None, None)
    forces = force_fn(reference, leave)
    if forces is None:
        # 方法对该输入不可用(数据缺失等), 登记证据不足不否决。
        return (STRICT_INSUFFICIENT, 'force_unavailable',
                conditions + [('force', None)],
                reference, leave, (zd, zg), None, None, None)
    ref_force, leave_force = forces
    if not leave_force < ref_force:
        # 注入力度不减即反例: 背驰段假设不成立(课61)。
        return (STRICT_REJECTED, 'force_not_declining',
                conditions + [('force', False)],
                reference, leave, (zd, zg), None, ref_force, leave_force)
    # 结构闭合+注入力度支持; 力度方法保留自身身份与局限,
    # 不冒充理论证明(课24口径)。
    return (STRICT_CONFIRMED, 'force_decline',
            conditions + [('force', True)],
            reference, leave, (zd, zg), None, ref_force, leave_force)


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


def scan_strict_divergence(units, as_of, level, force_fn=None,
                           force_method=None):
    """已确认次级类型上的严格趋势背驰结构扫描(四类返回语义)。

    units与confirm_level_up同契约: 同标的/价格坐标、同级、时间
    及端点价格连续的ConfirmedMove/ConfirmedMoveType, 只消费
    as_of前已确认连续前缀。level为趋势级别名(不同于输入级别,
    不猜K线周期)。force_fn为可选力度方法: 接收(reference_units,
    leave_units)返回(reference_force, leave_force)数值对, 返回
    None表示该方法对该输入不可用; 注入时必须以force_method声明
    非空方法身份字符串, 保留方法身份与局限(课24口径)。返回
    StrictScan: 每个完成上涨/下跌趋势一个冻结结果(结构闭合+
    注入力度减弱为confirmed, 力度不减为rejected, 方法不可用或
    未注入为insufficient_evidence, 条件否决时rejected并保留
    首个否决条件), 开放尾部两个及以上严格分离中枢且离开段已
    开始时登记candidate/trend_open(同一尾部起点同一身份, 随
    前缀演进, 完成后该身份落为最终语义; 不评估力度)。盘整完成
    项与不满足两分离中枢的尾部记入skipped。确认不早于最后证据;
    未来身份/价格不读取。复杂度O(n^2)最坏, 无跨调用缓存。
    """
    if force_fn is not None and not (isinstance(force_method, str)
                                     and force_method):
        raise ValueError('注入force_fn时必须以force_method声明方法身份')
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
        outcome = _evaluate_completed(trend, move, prefix, spans, force_fn)
        if outcome[0] is None:
            skipped.append((trend.move_id, outcome[1]))
            continue
        (status, reason, conditions, reference, leave, center_range,
         _, ref_force, leave_force) = outcome
        up = trend.kind == 'up'
        identity = _identity([level, prefix[move.seg_start].move_id, 'strict1'])
        results.append(StrictDivergence(
            identity, 'sell1' if up else 'buy1', level,
            status, reason, trend.move_id,
            _identity([level, prefix[spans[-1][0]].move_id]), center_range,
            tuple(u.move_id for u in reference), tuple(u.move_id for u in leave),
            force_method, ref_force, leave_force,
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
                    None, None, None,
                    tuple(conditions), visible[-1].confirmed_dt,
                    leave[-1].end_dt, _price(leave[-1].end_price)))
    return StrictScan(tuple(results), tuple(skipped), len(completed), open_tail)


class StrictChainLevel(namedtuple('StrictChainLevelBase',
                                  'depth level status reason reference_ids '
                                  'leave_ids center_range force_method '
                                  'force_reference force_leave confirmed_dt '
                                  'dt price')):
    """区间套单重结果: 该重围绕末次级中枢两段比较的状态与证据。

    status为该重结果码: bc(该重背驰段力度减弱, 课61)/
    no_new_extreme/force_not_declining(否决)/force_missing/
    force_unavailable/no_sub_center/no_compare_legs/not_covered
    (证据不足)。reason为语义归类: bc为None, 否决与证据不足沿用
    四类语义常量, 供按语义过滤。reference_ids/leave_ids为该重
    对照段与背驰段单元身份; center_range为该重末次级中枢冻结
    (zd,zg); force_*为注入方法身份与力度值(未注入或未评估为
    None)。dt/price为该重背驰段终点时刻与极值价格(单元级数据
    不定位极值发生时刻); confirmed_dt为该重所需证据的最晚确认
    时刻, 不早于任何被消费证据。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('confirmed_dt', 'dt'):
            out[key] = None if out[key] is None else str(out[key])
        out['center_range'] = (None if self.center_range is None
                               else list(self.center_range))
        out['reference_ids'] = list(self.reference_ids)
        out['leave_ids'] = list(self.leave_ids)
        return out


class StrictChain(namedtuple('StrictChainBase',
                             'divergence_id kind level levels depth complete '
                             'break_depth break_reason turn_dt turn_price '
                             'confirmed_dt')):
    """区间套次级确认链: 重1为传入严格背驰结果, levels为重2起逐重。

    levels/depth为已评估的重数(重2起); complete为最内一重bc
    (区间套定位完成); break_depth为否决重数(0为父级
    parent_rejected, None为无否决), break_reason为否决码;
    turn_dt/turn_price为最内bc重背驰段终点时刻与极值价格(无bc
    重为None); confirmed_dt为整链所需证据的最晚确认时刻。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('turn_dt', 'confirmed_dt'):
            out[key] = None if out[key] is None else str(out[key])
        out['levels'] = [level.to_dict() for level in self.levels]
        return out


def _chain_windows(units, direction):
    """区间内最后一个次级中枢与围绕它的对照/背驰段窗口(课61/53)。

    leave为末次级中枢最后反向回试之后的全部单元, 延伸至区间
    终点(含跨中枢移动单元); 中枢所在分解项单中枢时reference为
    其进入段a, 多中枢时为前中枢回试后段b(课61"只要是围绕一中枢
    的两段走势都可以比较力度"; 课53推广)。返回(code, reference,
    leave, center_range): code为None时窗口成立; no_sub_center为
    区间内无次级中枢; no_compare_legs为中枢存在但窗口不可建立
    (无回试边界或对照/背驰段为空)。中枢区间冻结于首三单元,
    延伸不改变(zd,zg)。
    """
    decomposed, traces = _level_up_traced(units)
    last = next((i for i in range(len(traces) - 1, -1, -1)
                 if traces[i]), None)
    if last is None:
        return 'no_sub_center', None, None, None
    spans = traces[last]
    last_end = _tail(units, spans[-1], direction)
    if last_end is None:
        return 'no_compare_legs', None, None, None
    leave = units[last_end + 1:]
    if not leave:
        return 'no_compare_legs', None, None, None
    if len(spans) == 1:
        reference = units[decomposed[last].seg_start:spans[-1][0]]
    else:
        previous_end = _tail(units, spans[-2], direction)
        if previous_end is None:
            return 'no_compare_legs', None, None, None
        reference = units[previous_end + 1:spans[-1][0]]
    if not reference:
        return 'no_compare_legs', None, None, None
    return None, reference, leave, _range3(units, spans[-1][0])


def _evaluate_chain_level(units, direction, force_fn):
    """围绕区间内末次级中枢的两段比较(课61/课53盘整背驰推广)。

    重2起不要求内部再构成两个分离中枢(课61原文只要求围绕一中枢
    的两段; 重1严格趋势结构由scan_strict_divergence承担)。返回
    七元组(status, reason, reference, leave, center_range,
    ref_force, leave_force)。先验极值取该重区间内背驰段窗口之前
    全部单元: 未创新极值即否决(课61"背驰如果没有创新高, 是不存
    在的"), 父级c端点为极值时子级结构上恒真; 注入力度不减即反例
    (课61"一旦力度大于前者, 那么就可以断定背驰段不成立");
    力度未注入或不可用登记证据不足不否决, 由调用方继续下探。
    """
    code, reference, leave, center_range = _chain_windows(units, direction)
    if code is not None:
        return code, STRICT_INSUFFICIENT, None, None, None, None, None
    prior = units[:len(units) - len(leave)]
    made, _ = _new_extreme_state(
        leave, direction,
        max(_price(u.high) for u in prior),
        min(_price(u.low) for u in prior))
    if not made:
        return 'no_new_extreme', STRICT_REJECTED, reference, leave, \
            center_range, None, None
    if force_fn is None:
        return 'force_missing', STRICT_INSUFFICIENT, reference, leave, \
            center_range, None, None
    forces = force_fn(reference, leave)
    if forces is None:
        return 'force_unavailable', STRICT_INSUFFICIENT, reference, leave, \
            center_range, None, None
    ref_force, leave_force = forces
    if not leave_force < ref_force:
        return 'force_not_declining', STRICT_REJECTED, reference, leave, \
            center_range, ref_force, leave_force
    return 'bc', None, reference, leave, center_range, ref_force, leave_force


def strict_nested_chain(divergence, units, layers, as_of,
                        force_fn=None, force_method=None):
    """严格趋势背驰的区间套次级确认链(课27定理/课61图解, R3)。

    课61: "在没有证据否定背驰之前，就要观察从65开始的一段其内部
    结构中的背驰情况，这种方法可以逐次下去，这就是区间套的定位
    方法"。重1为传入的scan_strict_divergence结果(任意语义, 开放
    尾部候选可当下定位); 重2起每重在上一重背驰段区间内取最后
    一个次级中枢, 围绕它比较对照段与背驰段力度(课61/课53推广,
    不要求重2起内部两个分离中枢)。

    输入: units为产生divergence的父级单元(同一次扫描输入);
    layers为逐重显式供给的(级别名, 单元表)序列, 级别邻接由调用
    方明示, 不按K线周期名猜级别; 第k重单元须与第k-1重背驰段
    区间时间首尾相等(否则not_covered)且端点价格对齐(否则报错,
    价格坐标契约违反), 单元契约与scan_strict_divergence相同
    (已确认走势, as_of前连续前缀)。force_fn/force_method注入
    契约同scan_strict_divergence, 作用于每一重。

    返回StrictChain: 每重status: bc(该重力度减弱)/
    no_new_extreme/force_not_declining(否决, 停止下探),
    force_missing/force_unavailable(力度证据缺失, 无否定证据
    继续下探)/no_sub_center/no_compare_legs/not_covered(窗口
    不可建立, 停止)。complete为最内一重bc; turn取最内bc重背驰
    段终点时刻与极值价格(单元级数据不定位极值发生时刻, 父级
    极值在c端点时两者重合); 父级已否决时break_depth=0/
    parent_rejected, 重内否决时break_depth为该重重数;
    confirmed_dt不早于任何被消费证据。输入修订须使用独立输入
    版本, 不混用身份; 本入口不证明子单元识别正确, 真实性由
    调用方声明。复杂度O(n^2)最坏(每重一次分解), 无跨调用缓存。
    """
    if not isinstance(divergence, StrictDivergence):
        raise ValueError('divergence须为scan_strict_divergence结果')
    if force_fn is not None and not (isinstance(force_method, str)
                                     and force_method):
        raise ValueError('注入force_fn时必须以force_method声明方法身份')
    if not isinstance(layers, (list, tuple)):
        raise TypeError('layers须为list或tuple')
    for layer in layers:
        if not isinstance(layer, (list, tuple)) or len(layer) != 2:
            raise ValueError('layers项须为(级别名, 单元表)二元组')
    parent_visible = _visible_units(units, as_of, divergence.level)[0]
    parent_ids = dict((u.move_id, u) for u in parent_visible)
    if any(name not in parent_ids for name in divergence.leave_ids):
        raise ValueError('divergence.leave_ids须在as_of可见父级单元中')
    parent_leave = [parent_ids[name] for name in divergence.leave_ids]
    direction = 'down' if divergence.kind == 'buy1' else 'up'
    levels = []
    break_depth = break_reason = None
    if divergence.status == STRICT_REJECTED:
        break_depth, break_reason = 0, 'parent_rejected'
    else:
        interval = (parent_leave[0].start_dt, parent_leave[-1].end_dt,
                    parent_leave[0].start_price, parent_leave[-1].end_price)
        for depth, (layer_level, layer_units) in enumerate(layers, 1):
            upper = divergence.level if depth == 1 else layers[depth - 2][0]
            visible = _visible_units(layer_units, as_of, upper)[0]
            if visible and visible[0].level != layer_level:
                raise ValueError('声明的级别名须与该重单元级别一致')
            if not visible or visible[0].start_dt != interval[0] \
                    or visible[-1].end_dt != interval[1]:
                status, reason = 'not_covered', STRICT_INSUFFICIENT
                reference = leave = center_range = None
                ref_force = leave_force = None
            elif visible[0].start_price != interval[2] \
                    or visible[-1].end_price != interval[3]:
                raise ValueError('子单元端点价格须与上一重背驰段区间对齐')
            else:
                (status, reason, reference, leave, center_range,
                 ref_force, leave_force) = _evaluate_chain_level(
                    visible, direction, force_fn)
            dt = price = None
            if leave:
                dt = leave[-1].end_dt
                price = (min(_price(u.low) for u in leave)
                         if direction == 'down'
                         else max(_price(u.high) for u in leave))
            levels.append(StrictChainLevel(
                depth, layer_level, status, reason,
                tuple(u.move_id for u in reference) if reference else (),
                tuple(u.move_id for u in leave) if leave else (),
                center_range,
                force_method if force_fn is not None else None,
                ref_force, leave_force,
                visible[-1].confirmed_dt if visible else None,
                dt, price))
            if status in ('no_new_extreme', 'force_not_declining'):
                break_depth, break_reason = depth, status
                break
            if status not in ('bc', 'force_missing', 'force_unavailable'):
                break
            if depth < len(layers) and leave:
                interval = (leave[0].start_dt, leave[-1].end_dt,
                            leave[0].start_price, leave[-1].end_price)
    turn = next((level for level in reversed(levels)
                  if level.status == 'bc'), None)
    stamps = [divergence.confirmed_dt] + [level.confirmed_dt
                                           for level in levels
                                           if level.confirmed_dt is not None]
    return StrictChain(
        divergence.divergence_id, divergence.kind, divergence.level,
        tuple(levels), len(levels),
        bool(levels) and levels[-1].status == 'bc',
        break_depth, break_reason,
        turn.dt if turn is not None else None,
        turn.price if turn is not None else None,
        max(stamps))


class StrictCompletionLevel(namedtuple('StrictCompletionLevelBase',
                                       'depth level unit_id status '
                                       'unit_ids confirmed_dt')):
    """次级完成级联单层结果: 上层端点单元在该层细级证据下的复核。

    level为该层细级单元级别名; unit_id为被复核的上层端点单元身份;
    status为该层复核码: confirmed(该层完成类型恰覆盖上层端点单元
    区间与端点价格, 复核时刻为完成证据到达时刻)/unverified(该层
    分解不产出该区间完成类型, 调用方声明口径与细级证据不同或证据
    不足以复核)/not_covered(该层单元未覆盖上层端点单元区间)。
    unit_ids为匹配完成类型的组成单元身份(confirmed时, 否则为空);
    confirmed_dt为该层复核完成时刻(未通过为None)。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        out['confirmed_dt'] = (None if self.confirmed_dt is None
                               else str(self.confirmed_dt))
        out['unit_ids'] = list(self.unit_ids)
        return out


class StrictCompletion(namedtuple('StrictCompletionBase',
                                  'divergence_id kind level levels depth '
                                  'complete confirmed_dt')):
    """次级走势完成级联确认结果(课35/37)。

    levels为逐层复核结果(层1起, 首个未通过层即止, 其余声明层
    不消费); depth为已评估层数; complete为全部已评估层confirmed
    且至少一层(端点单元的完成沿声明级别链逐层由细级证据复核);
    confirmed_dt为整链最晚确认时刻(含父级结果, 不早于任何被
    消费证据)。父级语义不因本入口改变, 未声明层不复核。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        out['confirmed_dt'] = str(out['confirmed_dt'])
        out['levels'] = [level.to_dict() for level in self.levels]
        return out


def _cascade_match(visible, obj, as_of):
    """细级可见前缀中定位上层端点单元起点并复核其完成类型。

    返回(status, matched, pieces): 细级前缀未及上层端点单元起点为
    not_covered; 已及该时刻而无起点切分登记unverified(细级分解不
    在上层端点单元起点切开, 调用方声明口径与细级证据不同); 起点
    切分处端点价格不对齐报价格坐标契约错误。pieces为自起点切分至
    as_of的可见前缀(完成证据可能在走势端点之后, 属下一走势, 课35
    /completion契约), 其上重算完成类型, 恰覆盖上层端点单元区间与
    端点价格的完成类型为matched, 无匹配为unverified(证据未到达
    或分解口径不同)。pieces保留供级联至末组成单元。
    """
    starts = dict((unit.start_dt, i) for i, unit in enumerate(visible))
    low = starts.get(obj.start_dt)
    if low is None:
        reached = any(unit.end_dt > obj.start_dt for unit in visible)
        return ('unverified' if reached else 'not_covered'), None, None
    pieces = visible[low:]
    if _price(pieces[0].start_price) != _price(obj.start_price):
        raise ValueError('细级单元端点价格须与上层端点单元对齐')
    for typ in confirm_level_up(pieces, as_of, obj.level):
        if (typ.start_dt == obj.start_dt and typ.end_dt == obj.end_dt
                and _price(typ.start_price) == _price(obj.start_price)
                and _price(typ.end_price) == _price(obj.end_price)):
            return 'confirmed', typ, pieces
    return 'unverified', None, pieces


def strict_completion_cascade(divergence, units, layers, as_of):
    """严格背驰转折端点的次级走势完成级联确认(课35/37, R3)。

    课37: "c 必然是次级别的"——父级背驰段端点单元是次级别走势,
    其完成由更细级别完成证据冻结(课35: 高级别走势类型由低级别
    走势类型连接而成, 分解定理二; 完成证据可能在走势端点之后、
    属下一走势, completion.py契约)。本入口对divergence的leave
    末单元(含转折端点)逐层复核: 每层细级可见前缀自上层端点单元
    起点切分处起至as_of证据视野重算完成类型, 恰覆盖上层端点单元
    区间与端点价格的完成类型即该层confirmed并级联至其末组成单元
    作为下层复核对象; 细级前缀未及起点为not_covered, 已及而无
    起点切分、无匹配完成类型或完成证据未到达为unverified(调用方
    声明口径与细级证据不同或证据不足以复核, 不判任一方错误),
    首个未通过层即止; 起点价格不对齐报价格坐标契约错误。

    divergence为scan_strict_divergence结果(任意语义: 端点单元的
    完成复核与父级裁定正交); units为产生divergence的父级单元;
    layers为逐层(级别名, 细级单元表)序列, 级别邻接由调用方明示,
    不按K线周期名猜级别, 细级单元契约同scan_strict_divergence
    (as_of前已确认连续前缀)。返回StrictCompletion: 全部已评估层
    confirmed时complete为真; confirmed_dt不早于任何被消费证据;
    未来身份/价格不读取。复杂度每层O(n^2)最坏, 无跨调用缓存。
    """
    if not isinstance(divergence, StrictDivergence):
        raise ValueError('divergence须为scan_strict_divergence结果')
    if not isinstance(layers, (list, tuple)):
        raise TypeError('layers须为list或tuple')
    for layer in layers:
        if not isinstance(layer, (list, tuple)) or len(layer) != 2:
            raise ValueError('layers项须为(级别名, 单元表)二元组')
    if not divergence.leave_ids:
        raise ValueError('divergence.leave_ids不能为空')
    parent_visible = _visible_units(units, as_of, divergence.level)[0]
    parent_ids = dict((u.move_id, u) for u in parent_visible)
    if any(name not in parent_ids for name in divergence.leave_ids):
        raise ValueError('divergence.leave_ids须在as_of可见父级单元中')
    obj = parent_ids[divergence.leave_ids[-1]]
    levels = []
    for depth, (layer_level, layer_units) in enumerate(layers, 1):
        verified_id = obj.move_id
        visible = _visible_units(layer_units, as_of, obj.level)[0]
        if visible and visible[0].level != layer_level:
            raise ValueError('声明的级别名须与该层单元级别一致')
        if not visible:
            status, matched, pieces = 'not_covered', None, None
        else:
            status, matched, pieces = _cascade_match(visible, obj, as_of)
        unit_ids = ()
        confirmed = None
        if matched is not None:
            unit_ids = matched.unit_ids
            confirmed = matched.confirmed_dt
            by_id = dict((u.move_id, u) for u in pieces)
            obj = by_id[matched.unit_ids[-1]]
        levels.append(StrictCompletionLevel(
            depth, layer_level, verified_id, status, unit_ids, confirmed))
        if matched is None:
            break
    stamps = [divergence.confirmed_dt] + [level.confirmed_dt
                                          for level in levels
                                          if level.confirmed_dt is not None]
    return StrictCompletion(
        divergence.divergence_id, divergence.kind, divergence.level,
        tuple(levels), len(levels),
        bool(levels) and all(level.status == 'confirmed'
                             for level in levels),
        max(stamps))
