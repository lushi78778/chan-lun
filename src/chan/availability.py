# -*- coding: utf-8 -*-
"""实际可用行情与保守结构确认(课65/68/67的当下识别工程契约)。

日线dt常是交易日标签, 不代表当天00:00已知OHLC。每根原始bar须附
closed_dt(本周期结束时间)、available_dt(本版本数据实际可用时间),
满足dt<=closed_dt<=available_dt。先按两种时间截断, 再校验价格和计算。
时间元数据由调用方提供, 本库不猜交易日历、行情延迟或复权发布版本。
"""
from collections import namedtuple
from copy import deepcopy

from chan.analysis import analyze_bars
from chan.bars import _bar_time
from chan.replay import ObservationChange, _records
from chan.xd import find_xds
from chan.zs import find_zs


class StructureObservation(namedtuple('StructureObservationBase',
                                     'kind identity first_seen observed_dt record')):
    """本次网格首次符合保守确认口径的结构, record为独立快照。

    bi: 已出现后继笔, 不含可延伸末笔。
    xd: 只用上述笔计算且complete=True, 不把线段当作完成走势类型。
    xd_center: 至少三个上述线段形成的中枢(线段构造层, 不猜分钟级别)。
    first_seen是该观察网格确认可见时间, 不是端点或成交时间, 也不是
    供应历史数据从未修订的证明。中枢延伸会更新record, 保留形成时点。
    """
    __slots__ = ()

    def to_dict(self):
        return {'kind': self.kind, 'identity': list(self.identity),
                'first_seen': str(self.first_seen), 'observed_dt': str(self.observed_dt),
                'record': deepcopy(self.record)}


class AvailableSnapshot(namedtuple('AvailableSnapshotBase',
                                  'observed_dt result structures changes')):
    """已关闭且已到达行情的组合结果、保守结构记录及候选/结构变更。"""
    __slots__ = ()

    def to_dict(self):
        return {'observed_dt': str(self.observed_dt), 'result': self.result.to_dict(),
                'structures': [item.to_dict() for item in self.structures],
                'changes': [item.to_dict() for item in self.changes]}


def _available_bars(bars, as_of):
    """全量时间元数据用于选择; 未来OHLCV不读取。"""
    if not isinstance(bars, (list, tuple)):
        raise TypeError('bars须为list或tuple')
    cutoff, kind = _bar_time(as_of)
    out, previous = [], None
    for i, bar in enumerate(bars):
        try:
            values = [_bar_time(bar[key]) for key in ('dt', 'closed_dt', 'available_dt')]
            if any(k != kind for _, k in values):
                raise ValueError('时间须与as_of同表示、格式及UTC偏移')
            dt, closed, available = [v for v, _ in values]
            if not dt <= closed <= available:
                raise ValueError('须dt<=closed_dt<=available_dt')
            if previous is not None and dt <= previous:
                raise ValueError('行情dt须严格递增')
            previous = dt
            if available <= cutoff:
                out.append(bar)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('bars[{}]时间元数据无效: {}'.format(i, error)) from error
    return out


def analyze_available(bars, as_of, min_k_gap=None, bi_standard='81'):
    """按实际可用时间计算, 可用于盘中观察日线/分钟线(含交付延迟)。

    必须传带closed_dt/available_dt的原始bar；字段缺失报错, 不退回
    dt标签过滤。dt与观察/元数据使用同类型同格式, 支持空可见前缀。
    所有价格和复权因子须是as_of可得版本, 元数据不是自动版本仓库。
    若历史数据事后修订, 调用方必须保存/重建对应输入版本及观察账本。
    """
    return analyze_bars(_available_bars(bars, as_of), min_k_gap, bi_standard)


def _structure_records(result):
    """结构确认级联只消费已完成配件, 不给旧bs候选添加确认标志。"""
    records = {}
    stable = result.bis[:-1]
    for bi in stable:
        anchor = result.new_bars[bi.start_index].elements[0]
        records[('confirmed_bi', bi.direction, anchor)] = bi.to_dict()
    xds = [x for x in find_xds(stable) if x.complete]
    for xd in xds:
        anchor = result.new_bars[xd.start_index].elements[0]
        records[('confirmed_xd', xd.direction, anchor)] = xd.to_dict()
    for center in find_zs(xds):
        records[('formed_xd_center', center.direction, str(center.start_dt))] = center.to_dict()
    return records


def replay_available(bars, observations=None, min_k_gap=None, bi_standard='81'):
    """逐实际观察时点重算并记录保守确认结构, yield AvailableSnapshot。

    observations缺省取全部available_dt去重排序; 显式观察须严格递增。
    包含原replay_bars的分型/笔/旧bs候选账本, 另加confirmed_bi/
    confirmed_xd/formed_xd_center出现、修订、撤销。尾部仍是候选,
    不把若干天没变化当确认。先有后继笔才固定前笔, 再确认线段,
    三个已确认线段才进入中枢形成记录; 确认延迟比候选识别更长。
    此入口不生成自动一类点上下文或真实分钟级别次级走势; 不应把
    结构确认记录直接转换为ConfirmedMove。无全局缓存, 快照互不污染。
    """
    if not isinstance(bars, (list, tuple)):
        raise TypeError('bars须为list或tuple')
    if observations is None:
        # 先验证元数据, 避免缺失时间被静默丢弃。
        if bars:
            try:
                _available_bars(bars, bars[-1]['available_dt'])
            except KeyError as error:
                raise ValueError('缺少available_dt') from error
        observations = sorted(set(bar['available_dt'] for bar in bars), key=lambda v: _bar_time(v)[0])
    previous, first_seen = {}, {}
    previous_time, previous_kind = None, None
    for as_of in observations:
        time, kind = _bar_time(as_of)
        if previous_time is not None and (kind != previous_kind or time <= previous_time):
            raise ValueError('观察时间须同口径且严格递增')
        previous_time, previous_kind = time, kind
        result = analyze_available(bars, as_of, min_k_gap, bi_standard)
        structural = _structure_records(result)
        current = _records(result)
        current.update(structural)
        changes = []
        for key, record in current.items():
            if key not in previous:
                first_seen.setdefault(key, as_of)
                action = 'appeared'
            elif record != previous[key]:
                action = 'revised'
            else:
                continue
            changes.append(ObservationChange(action, key[0], key[1:], first_seen[key],
                                             as_of, deepcopy(previous.get(key)), deepcopy(record)))
        for key, record in previous.items():
            if key not in current:
                changes.append(ObservationChange('withdrawn', key[0], key[1:], first_seen[key],
                                                 as_of, deepcopy(record), None))
        names = {'confirmed_bi': 'bi', 'confirmed_xd': 'xd', 'formed_xd_center': 'xd_center'}
        structures = [StructureObservation(names[key[0]], key[1:], first_seen[key],
                                           as_of, deepcopy(record))
                      for key, record in structural.items()]
        previous = deepcopy(current)
        yield AvailableSnapshot(as_of, result, structures, changes)
