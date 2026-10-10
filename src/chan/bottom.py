# -*- coding: utf-8 -*-
"""课108: 精确走势类型意义上的底部/顶部构造过程。

原文: 一类买点出现后, 到其引发中枢的第一个三类买卖点之前,
均为底部构造; 先三卖则失败, 先三买则完成。顶部镜像。
这是时间区间与终态定义, 不等同于固定价格箱体或买入信号。

本模块消费调用方已经确认的事件, 不重新推断一买、中枢与三买。
level 与 center_id 明确同级别、同一因果中枢, 不用易漂移的列表下标
关联。confirmed_dt 必须是实际可见时间, 不能直接填 bs.py 的端点 dt。
回放时调用方用逐前缀识别或当时存档建立事件; 函数没有价格阈值。
分型区间的粗糙辅助定义与“有效站住”的量化不在本入口中混用。
"""

from collections import namedtuple
from numbers import Real
from typing import Any, Optional, Sequence

from chan._series import _finite_number


class FormationEvent(namedtuple("FormationEventBase",
                               "kind confirmed_dt level center_id")):
    """已确认事件: kind=buy1/sell1/buy3/sell3, 时间保持可比较原类型。

    level 为非空级别标识; 三类事件必须提供非空稳定 center_id。
    一类事件不要求中枢已出现, center_id 可为 None。有效性由消费函数
    校验; 同一确认时刻允许不同级别/中枢事件, 同中枢同级别的多个
    三类事件须先在上游消歧, 不以列表顺序决定底部成败。
    """
    __slots__ = ()

    def __new__(cls, kind, confirmed_dt, level, center_id=None):
        return super(FormationEvent, cls).__new__(
            cls, kind, confirmed_dt, level, center_id)

    def to_dict(self):
        return {"kind": self.kind, "confirmed_dt": str(self.confirmed_dt),
                "level": self.level, "center_id": self.center_id}


class FormationState(namedtuple("FormationStateBase",
                               "phase kind level center_id start_dt end_dt boundary_event")):
    """不可变构造结果: waiting/constructing/completed/failed。

    start_dt 为一类点的确认时间, end_dt 为首次相关三类点确认时间。
    构造区间为 [start_dt, end_dt), 未结束时 end_dt=None。
    一类点尚未可见时 waiting; 其后即使中枢还未出现也为 constructing。
    终态不被本次构造后续的相反信号改写, 新一类点开启独立构造。
    """
    __slots__ = ()

    @property
    def in_formation(self):
        return self.phase == "constructing"

    def to_dict(self):
        return {"phase": self.phase, "kind": self.kind, "level": self.level,
                "center_id": self.center_id,
                "start_dt": None if self.start_dt is None else str(self.start_dt),
                "end_dt": None if self.end_dt is None else str(self.end_dt),
                "boundary_event": (None if self.boundary_event is None
                                   else self.boundary_event.to_dict())}


def _validate_event(event):
    if not isinstance(event, FormationEvent):
        raise ValueError("事件须为 FormationEvent")
    if event.kind not in ("buy1", "sell1", "buy3", "sell3"):
        raise ValueError("不支持的构造事件 kind")
    if event.confirmed_dt is None:
        raise ValueError("confirmed_dt 不能为空")
    _validate_time(event.confirmed_dt)
    if not isinstance(event.level, str) or not event.level.strip():
        raise ValueError("level 须为非空字符串")
    if event.center_id is not None and (
            not isinstance(event.center_id, str) or not event.center_id.strip()):
        raise ValueError("center_id 须为非空字符串或 None")
    if event.kind.endswith("3") and event.center_id is None:
        raise ValueError("三类事件须关联稳定 center_id")


def _validate_time(value):
    if isinstance(value, bool) or (isinstance(value, Real) and _finite_number(value) is None):
        raise ValueError("时间不能是布尔值或非有限数")
    try:
        if not value <= value:
            raise ValueError("时间须具有有效的顺序关系")
    except TypeError as error:
        raise ValueError("时间须可比较") from error


def formation_state(first_point: Optional[FormationEvent],
                    center_id: Optional[str], events: Sequence[FormationEvent],
                    as_of: Any) -> FormationState:
    """根据确认事件前缀判定本次底/顶构造(课108)。

    first_point: 已识别的一买/一卖; None 表示尚无一类点。
    center_id: 该一类点引发中枢的稳定身份; 尚未形成可传 None。
    events: 按 confirmed_dt 非降序的确认事件; 其他级别、中枢及早于
        一类点的事件不改变本次构造。所有输入先校验, 不修改/排序。
    as_of: 观察时间, 只消费 confirmed_dt<=as_of 的事件(含一类点)。
        时间须可比较, 不自动解析、转换时区或用端点代替确认时间。

    已有一类点: constructing; 首个同级同中枢三类点: 底部 buy3 完成/
    sell3 失败, 顶部相反。相同可见时刻出现两个相关三类点报错, 不
    猜测盘中先后。一类点发生前/None: waiting。空事件不补造边界。
    """
    if as_of is None:
        raise ValueError("as_of 不能为空")
    _validate_time(as_of)
    events = list(events)
    if center_id is not None and (
            not isinstance(center_id, str) or not center_id.strip()):
        raise ValueError("center_id 须为非空字符串或 None")
    if first_point is not None:
        _validate_event(first_point)
        if first_point.kind not in ("buy1", "sell1"):
            raise ValueError("first_point 须为一类买卖点")
        if first_point.center_id is not None and first_point.center_id != center_id:
            raise ValueError("一类点的中枢关联与 center_id 不一致")
    try:
        previous = None
        for event in events:
            _validate_event(event)
            if previous is not None and event.confirmed_dt < previous:
                raise ValueError("events 确认时间须非降序")
            # 即使事件尚不可见, 也检查时间类型能否参与观察时刻比较。
            event.confirmed_dt <= as_of
            previous = event.confirmed_dt
        if first_point is None or first_point.confirmed_dt > as_of:
            return FormationState("waiting", None, None, center_id, None, None, None)
        kind = "bottom" if first_point.kind == "buy1" else "top"
        relevant = [event for event in events
                    if center_id is not None and event.center_id == center_id
                    and event.level == first_point.level and event.kind.endswith("3")
                    and first_point.confirmed_dt <= event.confirmed_dt <= as_of]
        for left, right in zip(relevant, relevant[1:]):
            if left.confirmed_dt == right.confirmed_dt:
                raise ValueError("同级同中枢同一确认时刻的三类事件须先消歧")
    except TypeError as error:
        raise ValueError("确认时间与 as_of 须可比较且使用一致表示") from error
    boundary = relevant[0] if relevant else None
    success = "buy3" if kind == "bottom" else "sell3"
    phase = ("constructing" if boundary is None else
             "completed" if boundary.kind == success else "failed")
    return FormationState(phase, kind, first_point.level, center_id,
                          first_point.confirmed_dt,
                          None if boundary is None else boundary.confirmed_dt, boundary)
