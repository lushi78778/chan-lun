# -*- coding: utf-8 -*-
"""反转轮次: 新一类新轮次、同侧移交与跨轮点位归属(课101/108)。

课101: 只有在回升/回落的中阴状态下才有第一、二类买卖点, 中阴
结束后只剩三类点与中枢震荡买卖点; 课108: 一类点后至其引发中枢
首次三类点前均为底/顶构造, 顺向三类点完成、逆向三类点失败。
新一类点开启新轮次; 同侧后继一类点确认后旧轮中阴被新锚点接管
(移交), 其二类点停发, 已确认点位保留原轮标签不回写; 旧轮构造
判定独立继续, 不被新轮改写。多轮并存按point_id关联、按锚点
时间消歧, 不用数组下标。
"""
from collections import namedtuple

from chan.point_chain import _handover_dt, analyze_point_chain
from chan.second import _text


class Round(namedtuple('RoundBase',
                       'round_id side level anchor previous_center causal_center '
                       'formation second_points third_points handed_over_dt')):
    """一次反转轮次: 锚点一类点、双中枢、课108构造与归属点位。

    round_id即锚点point_id; previous_center为原趋势末中枢,
    causal_center为一类后因果中枢(未形成为None)。formation为课108
    构造状态, handed_over_dt为同侧后继一类点确认时刻(移交), None
    表示移交尚未发生。构造与移交相互独立: 构造可在移交后才完成/
    失败, 也可保持构造中。点位按context_id=round_id归属, 不跨轮
    补标签; handed_over_dt由后继证据登记, 不改写已确认点位。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        out['anchor'] = self.anchor.to_dict()
        for name in ('previous_center', 'causal_center'):
            center = getattr(self, name)
            if center is not None:
                item = dict(center._asdict())
                item['confirmed_dt'] = str(center.confirmed_dt)
                out[name] = item
        out['formation'] = self.formation.to_dict()
        out['second_points'] = [p.to_dict() for p in self.second_points]
        out['third_points'] = [p.to_dict() for p in self.third_points]
        out['handed_over_dt'] = (None if self.handed_over_dt is None
                                 else str(self.handed_over_dt))
        return out


class RoundChain(namedtuple('RoundChainBase', 'rounds unresolved_move_ids')):
    """轮次视图: rounds按锚点时间升序; 平端点原样上报不删段拼接。"""
    __slots__ = ()

    def to_dict(self):
        return {'rounds': [r.to_dict() for r in self.rounds],
                'unresolved_move_ids': list(self.unresolved_move_ids)}


def track_rounds(units, bars, as_of, level, zero_axis_ratio=0.005):
    """analyze_point_chain的轮次分组视图(课101/108)。

    每个自动一类候选开启一轮: 锚点、原趋势末中枢、因果中枢、
    构造状态与按context_id归属的二/三类点; 移交时刻经_handover_dt
    登记。轮次按锚点时间升序输出; 点位归属不全时报错, 不静默
    丢弃。输入契约与analyze_point_chain一致, 参数含义见其docstring。
    """
    chain = analyze_point_chain(units, bars, as_of, level, zero_axis_ratio)
    rounds = []
    for context, formation in zip(chain.contexts, chain.formations):
        point = context.first_point
        _text(point.point_id)
        rounds.append(Round(point.point_id,
                            'buy' if point.kind == 'buy1' else 'sell',
                            point.level, point, context.previous_center,
                            context.causal_center, formation,
                            tuple(p for p in chain.second_points
                                  if p.context_id == point.point_id),
                            tuple(p for p in chain.third_points
                                  if p.context_id == point.point_id),
                            _handover_dt(chain.first_points, point)))
    rounds.sort(key=lambda r: r.anchor.dt)  # 多轮并存按锚点时间消歧。
    ids = set(r.round_id for r in rounds)
    if len(ids) != len(rounds):
        raise ValueError('轮次身份不能重复')
    for point in chain.second_points:
        if point.context_id not in ids:
            raise ValueError('二类点归属不全: ' + point.context_id)
    for point in chain.third_points:
        if point.context_id not in ids:
            raise ValueError('三类点归属不全: ' + point.context_id)
    return RoundChain(tuple(rounds), chain.unresolved_move_ids)
