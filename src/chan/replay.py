# -*- coding: utf-8 -*-
"""观察时点分析及候选修订账本(课65/68/101的当下识别工程支持)。

课68强调分型后的走势仍有延续可能; 课101的二类点须等次级走势结束。
因此端点时间不等于信息可见时间。本模块先截断原始行情再计算, 不能
以全样本结构的端点过滤代替。first_seen 只是本次观察网格首次出现,
不是理论确认、成交时间或永久稳定承诺。所有结构仍消费已收盘行情。

本模块不取数、不复权、不推断收盘; 复权因子及跨周期数据同样须先按
观察时间取可见版本。观察间隔较粗会漏掉期间出现又撤销的候选。
"""

from collections import namedtuple
from copy import deepcopy

from chan.analysis import analyze_bars
from chan.bars import _bar_time


class ObservationChange(namedtuple("ObservationChangeBase",
                                  "kind field identity first_seen observed_dt before after")):
    """appeared/revised/withdrawn; 同身份重现沿用首次观察时间。

    identity 是观察账本键: 分型以原始中间包含组首索引、笔以原始起点
    组首索引和方向、信号以类型/端点/来源中枢起点关联。它不是跨数据
    修订或重采样的全局中枢身份。before/after 是独立字典快照。
    """
    __slots__ = ()

    def to_dict(self):
        return {"kind": self.kind, "field": self.field,
                "identity": list(self.identity), "first_seen": str(self.first_seen),
                "observed_dt": str(self.observed_dt),
                "before": deepcopy(self.before), "after": deepcopy(self.after)}


class ReplaySnapshot(namedtuple("ReplaySnapshotBase", "observed_dt result changes")):
    """observed_dt 为请求截止; result.as_of 为最后可见行情时间(可为空)。"""
    __slots__ = ()

    def to_dict(self):
        return {"observed_dt": str(self.observed_dt), "result": self.result.to_dict(),
                "changes": [change.to_dict() for change in self.changes]}


def _visible_bars(bars, as_of):
    if not isinstance(bars, (list, tuple)):
        raise TypeError("bars 须为 list 或 tuple")
    cutoff, kind = _bar_time(as_of)
    visible = []
    previous = None
    for bar in bars:
        try:
            current, current_kind = _bar_time(bar["dt"])
            if current_kind != kind:
                raise ValueError("as_of 与行情时间须同类型、格式及UTC偏移")
            if previous is not None and current <= previous:
                raise ValueError("行情时间须严格递增")
            previous = current
            if current <= cutoff:
                # 未来 OHLCV 不校验、不数值化、不参与包含/指标/结构计算。
                visible.append(bar)
        except (KeyError, TypeError) as error:
            raise ValueError("行情须含有效且可比较的dt") from error
    return visible


def analyze_at(bars, as_of, min_k_gap=None, bi_standard="81"):
    """先取 dt<=as_of 原始行情, 再调用 analyze_bars; 空前缀合法。

    as_of 与 dt 使用一致表示(含固定时区偏移), 不猜测日期的收盘时间。
    全序列时间索引用于截断, 只校验可见 OHLCV; 未来价格任意改变都不
    影响结果。输入必须已按观察时点可用因子复权, 本函数不自动复权。
    不可把已经用未来行情算出的 NewBar/笔作为本入口原始行情。
    """
    return analyze_bars(_visible_bars(bars, as_of), min_k_gap, bi_standard)


def _records(result):
    records = {}
    for fx in result.fxs:
        anchor = result.new_bars[fx.bar_index].elements[0]
        records[("fx", fx.kind, anchor)] = fx.to_dict()
    for bi in result.bis:
        anchor = result.new_bars[bi.start_index].elements[0]
        records[("bi", bi.direction, anchor)] = bi.to_dict()
    for field, events in (("buy", result.buy_points), ("sell", result.sell_points)):
        for event in events:
            zi = event.get("zs_idx")
            center = (str(result.bi_zss[zi].start_dt)
                      if zi is not None else None)
            key = (field, event["type"], str(event["dt"]), center)
            if key in records and records[key] != event:
                raise ValueError("同一观察身份对应多个不同信号, 须先消歧")
            records[key] = deepcopy(event)
    return records


def replay_bars(bars, observations=None, min_k_gap=None, bi_standard="81"):
    """逐观察时点独立重算, yield ReplaySnapshot(含分型/笔/买卖候选变更)。

    observations 默认每根原始bar的dt; 显式序列须严格递增, 稀疏回放的
    first_seen 仅对应该网格。迭代期间不得修改输入行情。尾部修改会产生
    revised/withdrawn, 不自动确认任何事件; 无变更也返回当时快照。
    回放只用前缀计算, 不调用一次全样本计算再过滤。无输入/观察返回空。
    历史数据版本变化需独立重建账本, 本入口没有全局缓存。
    """
    if not isinstance(bars, (list, tuple)):
        raise TypeError("bars 须为 list 或 tuple")
    observations = ([bar["dt"] for bar in bars] if observations is None
                    else list(observations))
    previous_time, previous_kind = None, None
    previous, first_seen = {}, {}
    for as_of in observations:
        time, kind = _bar_time(as_of)
        if previous_time is not None and (kind != previous_kind or time <= previous_time):
            raise ValueError("观察时间须同口径且严格递增")
        previous_time, previous_kind = time, kind
        result = analyze_at(bars, as_of, min_k_gap, bi_standard)
        current = _records(result)
        changes = []
        for key, record in current.items():
            if key not in previous:
                first_seen.setdefault(key, as_of)
                action = "appeared"
            elif record != previous[key]:
                action = "revised"
            else:
                continue
            changes.append(ObservationChange(action, key[0], key[1:], first_seen[key],
                                             as_of, deepcopy(previous.get(key)),
                                             deepcopy(record)))
        for key in previous:
            if key not in current:
                changes.append(ObservationChange("withdrawn", key[0], key[1:],
                                                 first_seen[key], as_of,
                                                 deepcopy(previous[key]), None))
        # 与交付的result/changes隔离, 消费者修改快照不会污染下一次计算。
        previous = deepcopy(current)
        yield ReplaySnapshot(as_of, result, changes)
