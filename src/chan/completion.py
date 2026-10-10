# -*- coding: utf-8 -*-
"""完成走势类型的递归确认(课35/84/102, 工程证据时间契约)。

课35: “三个连续的最低级别走势类型之间, 如果发生重叠关系”形成
高一级别中枢。课84: “级别, 本质上与时间无关”; f1和f2可不同。
因此输入须是调用方已确认的最低层走势类型, 或本入口的上层结果,
不是单笔/线段或全样本MoveType.complete。本模块沿用level_up的
允许延伸f2切分, 不采用课38不延伸的同级切分, 不新增背驰完成规则。

每批证据到达后重算可见前缀, 首次complete才冻结结果。完成所用
证据可能在走势端点之后、甚至属于下一走势; confirmed_dt不能只
取组成单元的最晚确认时间。输入身份、价格坐标与完成版本须冻结,
本入口不证明提供者的基础走势识别正确或自动建立一类点/因果中枢。
"""
from collections import namedtuple
import json

from chan.bars import _bar_time
from chan.recurse import level_up
from chan.second import ConfirmedMove, _price, _text, _time


class ConfirmedMoveType(namedtuple('ConfirmedMoveTypeBase',
                                  'move_id level kind direction start_dt end_dt '
                                  'start_price end_price low high confirmed_dt '
                                  'unit_ids evidence_ids centers')):
    """已确认f2走势的不可变快照, 数值单位沿用输入价格坐标。

    direction保留原f2进入方向, 可为None, 不等于端点净涨跌方向。
    unit_ids为覆盖的次级单元; evidence_ids为首次完成时的全部可见
    次级前缀(保守完整证据), 含可能处于端点之后的确认单元。
    centers为冻结的(zd,zg)元组, 触沿交集可退化为一个价格。
    调用方也可按声明的f1规则冻结最低层完整类型, 须有真实完成时间
    及全部字段; 不能仅改名包装单笔/线段。move_id只在同一标的、
    输入版本及级别链内稳定, 不是全局身份。
    """
    __slots__ = ()

    @property
    def complete(self):
        return True

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('start_dt', 'end_dt', 'confirmed_dt'):
            out[key] = str(out[key])
        for key in ('unit_ids', 'evidence_ids', 'centers'):
            out[key] = [list(v) if isinstance(v, tuple) else v for v in out[key]]
        out['complete'] = True
        return out

    def to_confirmed_move(self):
        """转二/三类点输入, 以端点净涨跌表示整体回抽/回试方向。

        保留身份、全程极值及实际确认时间; 不生成点位上下文、中枢
        或背驰证据。平端点的盘整无法用up/down表达, 显式报错,
        调用方不能丢弃该段后拼接两侧走势。原进入方向仍在本对象。
        """
        start, end = _price(self.start_price), _price(self.end_price)
        if start == end:
            raise ValueError('平端点走势不能转换为有向ConfirmedMove')
        return ConfirmedMove(self.move_id, self.level, 'up' if end > start else 'down',
                             self.start_dt, self.end_dt, start, end, self.low,
                             self.high, self.confirmed_dt)


def _visible_units(units, as_of, next_level):
    if not isinstance(units, (list, tuple)):
        raise TypeError('units须为list或tuple')
    _text(next_level)
    cutoff, time_kind = _bar_time(as_of)
    visible, future, ids, level = [], False, set(), None
    for unit in units:
        if not isinstance(unit, (ConfirmedMove, ConfirmedMoveType)):
            raise ValueError('只接受已确认走势类型, 不接受笔/线段或裸MoveType')
        known = _time(unit.confirmed_dt, time_kind)
        if known > cutoff:
            future = True
            continue  # 未来身份、价格、级别和区间不读取。
        if future:
            raise ValueError('可见单元须为连续前缀, 乱序到达须由调用方重建版本')
        _text(unit.move_id)
        _text(unit.level)
        if unit.move_id in ids:
            raise ValueError('可见单元身份须唯一')
        ids.add(unit.move_id)
        if level is None:
            level = unit.level
        if unit.level != level or next_level == level:
            raise ValueError('输入须同级, next_level须为不同的递归相邻级别名')
        start, end = _time(unit.start_dt, time_kind), _time(unit.end_dt, time_kind)
        if not start < end <= known:
            raise ValueError('须start_dt<end_dt<=confirmed_dt')
        low, high = _price(unit.low), _price(unit.high)
        s, e = _price(unit.start_price), _price(unit.end_price)
        if not low <= min(s, e) <= max(s, e) <= high:
            raise ValueError('端点价格须在全程极值内')
        if isinstance(unit, ConfirmedMove):
            if (unit.direction not in ('up', 'down') or
                    (unit.direction == 'up' and e <= s) or
                    (unit.direction == 'down' and e >= s)):
                raise ValueError('基础走势方向须与端点价格一致')
        else:
            _validate_type(unit)
        if visible:
            previous = visible[-1]
            if (previous.end_dt != unit.start_dt or previous.end_price != s):
                raise ValueError('次级走势时间与端点价格须连续, 不能跳段')
            if _time(previous.confirmed_dt, time_kind) > known:
                raise ValueError('确认时间须随走势顺序非递减')
        visible.append(unit)
    return visible, time_kind


def _validate_type(unit):
    """检查冻结f2快照的形状, 不将结构校验当作理论原图证明。"""
    if unit.kind not in ('up', 'down', 'consolidation') or unit.direction not in (None, 'up', 'down'):
        raise ValueError('无中枢残段不是完成走势类型')
    if not isinstance(unit.centers, tuple) or not unit.centers:
        raise ValueError('完成走势须有冻结中枢元组')
    previous = None
    for center in unit.centers:
        if not isinstance(center, tuple) or len(center) != 2:
            raise ValueError('中枢须为(zd,zg)元组')
        zd, zg = [_price(v) for v in center]
        if not unit.low <= zd <= zg <= unit.high:
            raise ValueError('中枢区间须在走势全程极值内')
        if previous is not None and (unit.kind == 'consolidation' or
                (unit.kind == 'up' and zd <= previous[1]) or
                (unit.kind == 'down' and zg >= previous[0])):
            raise ValueError('趋势中枢须严格同向移动, 盘整只有一个中枢')
        previous = center
    if unit.kind in ('up', 'down') and (len(unit.centers) < 2 or unit.direction != unit.kind):
        raise ValueError('趋势须至少两个同向中枢')
    for names in (unit.unit_ids, unit.evidence_ids):
        if not isinstance(names, tuple) or not names:
            raise ValueError('组成及证据身份须为非空冻结元组')
        for name in names:
            _text(name)
        if len(set(names)) != len(names):
            raise ValueError('组成及证据身份不能重复')
    if not set(unit.unit_ids).issubset(unit.evidence_ids):
        raise ValueError('组成单元须包含在确认证据中')


def confirm_level_up(units, as_of, next_level):
    """已确认次级类型按实际到达前缀升一级, 返回ConfirmedMoveType列表。

    units: 同标的/价格坐标、同级、时间及端点价格连续的已完成单元,
      ConfirmedMove或ConfirmedMoveType; 后者保留完整类型/进入方向,
      可由声明的f1规则冻结或由本入口产生。confirmed_dt按序非递减。基础
      走势真实性由调用方声明, 不允许裸MoveType或单笔/线段替代。
    as_of: 截止时刻, 同输入时间表示/格式/UTC偏移; 未来价格不读取。
    next_level: 非空且不同于输入的递归相邻级别名, 不猜K线周期。
      同一时刻多单元整批进入, 不虚构批内不同到达时间。

    沿用level_up允许延伸的切分, 只输出complete类型, 尾部与无中枢
    残段不升为确认结果。内部逐到达批重算并检查完成项没有修订或撤销。
    初次确认时间取完成证据到达时刻, 即使晚于所有组成单元。复杂度
    为O(n²)最坏时间, 输入应是走势类型序列, 不是逐笔原始行情。
    无跨调用缓存; 修订历史输入时须使用独立输入版本, 不能混淆身份。
    """
    visible, time_kind = _visible_units(units, as_of, next_level)
    frozen, records = {}, {}
    for stop in range(1, len(visible)+1):
        if stop < len(visible) and visible[stop-1].confirmed_dt == visible[stop].confirmed_dt:
            continue  # 同一到达时刻整批处理, 不按任意列表位置制造确认时刻。
        prefix = visible[:stop]
        current = {}
        for move in level_up(prefix):
            if not move.complete:
                continue  # 无中枢残段和未完成尾部均不作次级完成证据。
            first, last = prefix[move.seg_start], prefix[move.seg_end]
            identity = json.dumps([next_level, first.move_id], ensure_ascii=False, separators=(',', ':'))
            unit_ids = tuple(u.move_id for u in prefix[move.seg_start:move.seg_end+1])
            body = (move.kind, move.direction, move.start_dt, move.end_dt,
                    first.start_price, last.end_price, move.low, move.high,
                    unit_ids, tuple(move.centers))
            current[identity] = body
            if identity not in frozen:
                frozen[identity] = body
                records[identity] = ConfirmedMoveType(
                    identity, next_level, *body[:8], prefix[-1].confirmed_dt,
                    unit_ids, tuple(u.move_id for u in prefix), body[-1])
            elif frozen[identity] != body:
                raise ValueError('递归已完成项修订, 不能冻结为确认走势')
        if any(identity not in current for identity in frozen):
            raise ValueError('递归已完成项撤销, 不能冻结为确认走势')
    return sorted(records.values(), key=lambda item: _time(item.start_dt, time_kind))
