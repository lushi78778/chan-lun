# -*- coding: utf-8 -*-
"""已确认次级走势的二类买卖点(课20/21/53/101), 独立于旧笔级bs。

课101: 二买是“一买的次级别回抽结束后再次探底或回试的那个次级别
走势的结束点”; “第二类买点比第一类买点低, 这是完全可以的”。最强
情形与原下跌最后中枢三买合一; 中阴结束后不再产生本次一、二类点。
课53: 小转大可无本级别一类点; 不创新低(卖点不创新高)或盘整背驰
的回试同样构成二类点。卖点镜像。

本模块是条件判定器, 不是从K线自动推导全部级别/背驰的引擎。调用方
必须提供当时确认的次级走势、转折上下文与因果中枢; 不允许把末笔或
全样本MoveType.complete倒填到端点日。confirmed_dt分别保留各证据
实际可见时间, 输出取所需证据的最晚时间, 不是端点时间。
"""

from collections import namedtuple

from chan.bars import _bar_time
from chan._series import _finite_number


class ConfirmedMove(namedtuple("ConfirmedMoveBase", "move_id level direction start_dt end_dt "
                              "start_price end_price low high confirmed_dt")):
    """调用方已确认结束的次级走势不可变快照, 价格与时间同一数据口径。

    只能提供真实走势类型(可为上涨/下跌/盘整), 不能将单笔自动称作次级
    走势。direction 是回抽/回试的整体方向; low/high 是全走势极值,
    start/end_price 是端点价, 不要求极值恰好发生在端点(课53)。
    身份/级别须非空, 确認时间须不早于终点。未完成单元不要输入。
    """
    __slots__ = ()


class SecondPointContext(namedtuple("SecondPointContextBase", "context_id side level sub_level "
                                   "anchor_dt anchor_price confirmed_dt source ended_dt")):
    """独立反转上下文: source=first(一类点)/minor_turn(无本级一类点)。

    anchor 是反弹/回落的起点, confirmed_dt 是当时上下文成立时间。
    ended_dt 为本次中阴结束的实际确认时间, 未知时None。该时刻之前
    已成立的二类点保留, 同时刻二三合一允许; 后来的二类点被排除。
    context_id不是中枢数组下标; 多次反转使用不同身份。
    """
    __slots__ = ()

    def __new__(cls, context_id, side, level, sub_level, anchor_dt, anchor_price,
                confirmed_dt, source="first", ended_dt=None):
        return super(SecondPointContext, cls).__new__(
            cls, context_id, side, level, sub_level, anchor_dt, anchor_price,
            confirmed_dt, source, ended_dt)


class ConfirmedCenter(namedtuple("ConfirmedCenterBase", "center_id level zd zg confirmed_dt")):
    """已在反转前形成的同级因果中枢; ZD<ZG, 不使用未来扩展后边界。"""
    __slots__ = ()


class ConfirmedDivergence(namedtuple("ConfirmedDivergenceBase", "move_id level direction confirmed_dt")):
    """候选回试走势的已确认盘整背驰证据, 按稳定move_id关联。"""
    __slots__ = ()


class SecondPoint(namedtuple("SecondPointBase", "kind context_id level dt price confirmed_dt "
                            "strength source first_move_id pull_move_id also_third center_id")):
    """二类点条件成立结果; strength=weak/normal/strong, 卖点镜像。

    also_third只标记给定因果中枢的首次离开回试条件同点成立, 不输出
    独立三类点流; 未提供对应中枢不能标记最强。dt为回试结束端点,
    confirmed_dt为实际可用时间。不是下单指令或收益保证。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        out["dt"] = str(self.dt)
        out["confirmed_dt"] = str(self.confirmed_dt)
        return out


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("身份、级别须为非空字符串")


def _price(value):
    number = _finite_number(value)
    if number is None or number <= 0:
        raise ValueError("价格须为有限正数")
    return number


def _time(value, kind):
    time, actual_kind = _bar_time(value)
    if actual_kind != kind:
        raise ValueError("所有时间与as_of须同表示、格式及UTC偏移")
    return time


def _visible(items, cls, cutoff, kind):
    out = []
    for item in items:
        if not isinstance(item, cls):
            raise ValueError("输入须为{}".format(cls.__name__))
        # 先按确认时间截断, 未来价格/边界不参与任何条件。
        if _time(item.confirmed_dt, kind) <= cutoff:
            out.append(item)
    return out


def find_second_points(moves, contexts, as_of, centers=None, divergences=None):
    """消费已确认的相邻次级走势, 返回全部上下文的二类点(课53/101)。

    moves按每个level的start_dt严格有序且不重叠; 每个上下文只能取
    anchor起始的第一次反向走势及紧接的第一次回试, 时间/端点价须
    连续, 不跳过失败回试寻找下一次。回试未确认则没有结果。
    centers是context_id->ConfirmedCenter映射; 缺省不判二三合一。
    divergences为盘整背驰证据序列, 仅小转大创新低/高分支需要。

    first上下文允许weak二买低于一买(卖点高于一卖), 不添加力度门槛。
    minor_turn上下文须回试不创新低/高或已有同方向盘整背驰证据。
    最强合一严格要求给定原中枢在anchor前可见, 首次反弹从中枢内/下
    穿到ZG上方且回试全区间低点>=ZG(卖点镜像)。触沿允许, 无额外
    工程力度比门槛。未来确认的走势/证据不参与; 空上下文返回[]。

    上下文、走势完成、级别邻接和背驰真实性仍由调用方负责; 本函数
    校验身份/时间/连续性与价格规则, 不凭字符串级别名猜周期关系。
    """
    cutoff, kind = _bar_time(as_of)
    visible_moves = _visible(moves, ConfirmedMove, cutoff, kind)
    visible_contexts = _visible(contexts, SecondPointContext, cutoff, kind)
    evidence = _visible(divergences or [], ConfirmedDivergence, cutoff, kind)
    groups, ids = {}, set()
    for move in visible_moves:
        _text(move.move_id)
        _text(move.level)
        if move.move_id in ids:
            raise ValueError("可见move_id须唯一")
        ids.add(move.move_id)
        if move.direction not in ("up", "down"):
            raise ValueError("次级走势direction须为up/down")
        start, end = _time(move.start_dt, kind), _time(move.end_dt, kind)
        if not start < end <= _time(move.confirmed_dt, kind):
            raise ValueError("走势须start_dt<end_dt<=confirmed_dt")
        low, high = _price(move.low), _price(move.high)
        if not (low <= _price(move.start_price) <= high
                and low <= _price(move.end_price) <= high):
            raise ValueError("端点价须落在走势极值区间内")
        if (move.direction == "up" and move.end_price <= move.start_price or
                move.direction == "down" and move.end_price >= move.start_price):
            raise ValueError("方向须与端点价格一致")
        group = groups.setdefault(move.level, [])
        if group and _time(group[-1].end_dt, kind) > start:
            raise ValueError("同级走势须有序且不重叠")
        group.append(move)
    for item in evidence:
        _text(item.move_id)
        _text(item.level)
        if item.direction not in ("up", "down"):
            raise ValueError("盘整背驰方向须为up/down")
    out, context_ids = [], set()
    for context in visible_contexts:
        for value in (context.context_id, context.level, context.sub_level):
            _text(value)
        if context.context_id in context_ids:
            raise ValueError("可见context_id须唯一")
        context_ids.add(context.context_id)
        if context.level == context.sub_level:
            raise ValueError("目标级别与次级别不能相同")
        if context.side not in ("buy", "sell") or context.source not in ("first", "minor_turn"):
            raise ValueError("side须为buy/sell; source须为first/minor_turn")
        anchor = _time(context.anchor_dt, kind)
        known = _time(context.confirmed_dt, kind)
        if anchor > known:
            raise ValueError("上下文确认时间不能早于anchor")
        _price(context.anchor_price)
        ended = None if context.ended_dt is None else _time(context.ended_dt, kind)
        if ended is not None and ended < known:
            raise ValueError("中阴结束不能早于上下文确认")
        group = groups.get(context.sub_level, [])
        pair = next(((first, pull) for first, pull in zip(group, group[1:])
                     if _time(first.start_dt, kind) == anchor), None)
        if pair is None:
            continue
        first, pull = pair
        direction = "up" if context.side == "buy" else "down"
        if first.direction != direction or pull.direction == direction:
            continue  # 只识别首次反弹/回落后的反向回试。
        if (first.start_price != context.anchor_price or first.end_dt != pull.start_dt
                or first.end_price != pull.start_price):
            raise ValueError("上下文及首段/回试端点须连续")
        confirmed = max(known, _time(first.confirmed_dt, kind),
                        _time(pull.confirmed_dt, kind))
        weak = (pull.end_price < context.anchor_price if context.side == "buy"
                else pull.end_price > context.anchor_price)
        if context.source == "minor_turn":
            made_extreme = (pull.low < context.anchor_price if context.side == "buy"
                            else pull.high > context.anchor_price)
            if made_extreme:
                matches = [e for e in evidence if e.move_id == pull.move_id
                           and e.level == pull.level and e.direction == pull.direction]
                if not matches:
                    continue  # 课53: 创新极值时须有盘整背驰, 不能凭涨跌幅猜。
                first_evidence = min(matches, key=lambda e: _time(e.confirmed_dt, kind))
                if _time(first_evidence.confirmed_dt, kind) < _time(pull.end_dt, kind):
                    raise ValueError("盘整背驰确认不能早于回试结束")
                confirmed = max(confirmed, _time(first_evidence.confirmed_dt, kind))
        if ended is not None and confirmed > ended:
            continue  # 课101: 本次中阴结束后不再生成二类点。
        also_third, center_id = False, None
        center = (centers or {}).get(context.context_id)
        if center is not None:
            if not isinstance(center, ConfirmedCenter):
                raise ValueError("中枢须为ConfirmedCenter")
            center_known = _time(center.confirmed_dt, kind)
            if center_known <= cutoff:
                _text(center.center_id)
                if center.level != context.level:
                    raise ValueError("因果中枢须与目标点同级")
                if not _price(center.zd) < _price(center.zg):
                    raise ValueError("中枢须ZD<ZG")
                if center_known <= anchor:
                    also_third = (first.start_price <= center.zg < first.end_price
                                  and pull.low >= center.zg if context.side == "buy" else
                                  first.start_price >= center.zd > first.end_price
                                  and pull.high <= center.zd)
                    if also_third:
                        center_id = center.center_id
        # 从原始时间取最晚可见值, 保持原表示与时区, 不用解析结果替换。
        times = [context.confirmed_dt, first.confirmed_dt, pull.confirmed_dt]
        if context.source == "minor_turn" and made_extreme:
            times.append(first_evidence.confirmed_dt)
        out.append(SecondPoint(context.side+"2", context.context_id, context.level,
                               pull.end_dt, pull.end_price,
                               max(times, key=lambda t: _time(t, kind)),
                               "strong" if also_third else "weak" if weak else "normal",
                               context.source, first.move_id, pull.move_id,
                               also_third, center_id))
    return sorted(out, key=lambda point: _time(point.confirmed_dt, kind))
