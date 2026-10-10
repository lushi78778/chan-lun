# -*- coding: utf-8 -*-
"""一类点后的因果中枢与二/三类点组合(课18/101/108)。

课101的二三合一使用原趋势最后中枢; 课108底部完成使用该一买
引发的中枢。这里分别保留previous_center和causal_center, 不将时间
最近的任意中枢指派给点位。引发中枢取锚点起连续已完成次级走势
中首次三段交集, 形成边界和身份冻结; 后续扩展不回写此中枢。
不处理更大级别中枢重组的身份继承, 不自动证明基础走势的真实性。
"""
from collections import namedtuple
import json

from chan.bars import _bar_time
from chan.bottom import FormationEvent, formation_state
from chan.completion import _visible_units
from chan.first import FirstPoint, find_first_points
from chan.second import (ConfirmedCenter, ConfirmedMove, SecondPointContext,
                         _price, _text, _time, find_second_points)
from chan.third import ThirdPointContext, find_third_points


class PointContext(namedtuple('PointContextBase',
                             'first_point second_context previous_center causal_center')):
    """同一轮反转的两个中枢身份; causal_center未形成时为None。"""
    __slots__ = ()


class PointChain(namedtuple('PointChainBase', 'first_points contexts second_points third_points formations')):
    """纯函数组合结果, 自动一类点继续保留MACD辅助候选性质。"""
    __slots__ = ()


def _moves(units):
    """不丢平端点走势; 二三类有向接口无法表达则明确报错。"""
    return [u if isinstance(u, ConfirmedMove) else u.to_confirmed_move() for u in units]


def first_point_contexts(units, first_points, as_of, level):
    """自动关联原趋势末中枢、反转锚点与锚点后首次形成中枢。

    只接受FirstPoint及确认次级类型。锚点须与反转首走势起点价格/
    时间一致; 每轮身份取point_id, 不使用数组下标。形成时间为三段
    证据最晚确认时间, 不使用第三段端点; 未来点位/价格不读取。
    """
    visible, kind = _visible_units(units, as_of, level)
    cutoff, _ = _bar_time(as_of)
    if not isinstance(first_points, (list, tuple)):
        raise TypeError('first_points须为list或tuple')
    out, ids = [], set()
    for point in first_points:
        if not isinstance(point, FirstPoint):
            raise ValueError('点位须为FirstPoint')
        known = _time(point.confirmed_dt, kind)
        if known > cutoff:
            continue
        _text(point.point_id)
        if point.point_id in ids:
            raise ValueError('可见点位身份不能重复')
        ids.add(point.point_id)
        if point.kind not in ('buy1', 'sell1') or point.level != level or (
                visible and point.sub_level != visible[0].level):
            raise ValueError('一类点类型和相邻级别须匹配输入')
        anchor = _time(point.dt, kind)
        price = _price(point.price)
        if anchor > known:
            raise ValueError('点位确认不能早于端点')
        previous = point.center
        if not isinstance(previous, ConfirmedCenter) or previous.level != level:
            raise ValueError('原趋势中枢级别须匹配')
        _text(previous.center_id)
        if not _price(previous.zd) < _price(previous.zg) or _time(previous.confirmed_dt, kind) > known:
            raise ValueError('原趋势中枢须已形成且ZD<ZG')
        post = [u for u in visible if _time(u.start_dt, kind) >= anchor]
        causal = None
        if post:
            if post[0].start_dt != point.dt or post[0].start_price != price:
                raise ValueError('不能跳过锚点后未接线走势或使用不一致价格')
            for i in range(len(post)-2):
                triple = post[i:i+3]
                zd, zg = max(u.low for u in triple), min(u.high for u in triple)
                if zd < zg:  # 三类接口尚不能表达零宽中枢, 不跳过去另选。
                    identity = json.dumps([level, point.point_id, triple[0].move_id],
                                          ensure_ascii=False, separators=(',', ':'))
                    causal = ConfirmedCenter(identity, level, zd, zg,
                                             max([u.confirmed_dt for u in triple]+[point.confirmed_dt],
                                                 key=lambda v: _time(v, kind)))
                    break
                if zd == zg:
                    break
        second = SecondPointContext(point.point_id, 'buy' if point.kind == 'buy1' else 'sell',
                                    level, point.sub_level, point.dt, price, point.confirmed_dt)
        out.append(PointContext(point, second, previous, causal))
    return out


def analyze_point_chain(units, bars, as_of, level, zero_axis_ratio=0.005):
    """自动一类候选→上下文→二三类条件→底/顶构造的薄组合入口。

    基础类型由调用方声明; level是递归相邻名, 不推断分钟周期。
    一类由MACD辅助法产生, 因果中枢由确认次级前缀形成。三类输出
    使用一买/一卖后首次中枢; 二三合一另用原趋势中枢。未知中枢时
    底/顶保持构造中; 更大级别重组身份继承不在本入口中。
    """
    points = find_first_points(units, bars, as_of, level, zero_axis_ratio)
    contexts = first_point_contexts(units, points, as_of, level)
    visible, _ = _visible_units(units, as_of, level)
    moves = _moves(visible)
    third_contexts = [ThirdPointContext(c.first_point.point_id, level,
                       c.first_point.sub_level, c.causal_center) for c in contexts if c.causal_center]
    thirds = find_third_points(moves, third_contexts, as_of)
    formations, seconds, centers = [], [], {}
    for c in contexts:
        p = c.first_point
        event = FormationEvent(p.kind, p.confirmed_dt, level,
                               c.causal_center.center_id if c.causal_center else None)
        events = [FormationEvent(t.kind, t.confirmed_dt, t.level, t.center_id)
                  for t in thirds if t.context_id == p.point_id]
        state = formation_state(event, event.center_id, events, as_of)
        formations.append(state)
        seconds.append(c.second_context._replace(ended_dt=state.end_dt))
        if c.previous_center.confirmed_dt <= p.dt:
            centers[p.point_id] = c.previous_center
    second_points = find_second_points(moves, seconds, as_of, centers=centers)
    return PointChain(points, contexts, second_points, thirds, formations)
