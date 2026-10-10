# -*- coding: utf-8 -*-
"""自动趋势一类候选(课24/27/101), 保守完成确认与MACD辅助证据。

课24明确MACD方法“不绝对精确”: B把双线拉回零轴附近, C完成时
同方向柱面积小于A。这里A取最后两中枢的连接段、C取最后离开段;
课27排除单中枢盘整背驰。输入为真实已完成的相邻次级走势, 先用
confirm_level_up生成完成趋势; 不能把单笔、末段或历史端点当确认。
只覆盖能从f2追溯两个波动区间严格分离中枢及同向连接/离开段的
保守子集。输出method=macd_area, 是辅助候选, 不是严格背驰证明。
"""
from collections import namedtuple
import json

from chan.availability import _available_bars
from chan.bars import _bar_time, validate_bars
from chan.bc import macd_series
from chan.completion import _visible_units, confirm_level_up
from chan.recurse import _level_up_traced
from chan.second import ConfirmedCenter, _price, _time
from chan._series import _finite_number


class FirstPoint(namedtuple('FirstPointBase',
                           'point_id kind level sub_level dt price confirmed_dt '
                           'trend_id center reference_ids leave_ids '
                           'reference_area leave_area zero_axis_ratio method')):
    """自动MACD辅助一类候选及组成证据; center为原趋势最后中枢。

    dt为已完成离开段端点; confirmed_dt取趋势完成与价格证据最晚
    到达时刻。下游自动上下文沿用候选性质, 不赋予交易许可。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('dt', 'confirmed_dt'):
            out[key] = str(out[key])
        out['center'] = dict(self.center._asdict())
        out['center']['confirmed_dt'] = str(self.center.confirmed_dt)
        return out


class FirstPointScan(namedtuple('FirstPointScanBase', 'points exclusions completed_types')):
    """辅助扫描结果; exclusions保存完成走势身份和未通过的首个条件。"""
    __slots__ = ()


def find_first_points(units, bars, as_of, level, zero_axis_ratio=0.005):
    """自动MACD辅助一类候选列表, 完整契约见scan_first_points。"""
    return scan_first_points(units, bars, as_of, level, zero_axis_ratio).points


def _net(unit):
    return ('up' if unit.end_price > unit.start_price else
            'down' if unit.end_price < unit.start_price else None)


def _tail(units, span, direction):
    """中枢最后反向回试结束为比较边界, 不把跨沿离开腿归入B。"""
    a, formed, extended = span
    opposite = 'down' if direction == 'up' else 'up'
    for i in range(extended, formed-1, -1):
        if _net(units[i]) == opposite:
            return i
    return None


def scan_first_points(units, bars, as_of, level, zero_axis_ratio=0.005):
    """从已确认次级类型自动构造MACD辅助一类候选, 买卖镜像。

    units与confirm_level_up同契约。bars须标准OHLCV且有closed_dt和
    available_dt, dt与走势端点精确对应、价格坐标一致。仅消费已到达
    连续前缀; 固定EMA从所给历史首根起算, 不猜供应历史版本。
    零轴“附近”量化为同一B行情上max(abs(DIF),abs(DEA))/close
    <=zero_axis_ratio(默认0.5%, 可配置, 原文没有数值)。A/C面积用
    同方向柱的正幅值求和, 区间(start,end], 共用端点不重复计数。
    无完成趋势、严格分离中枢、同向比较段、新极值、零轴回拉或正
    面积减弱则不输出。端点不在行情显式报错。走势极值不要求等于
    对应行情close; 同标的/复权坐标由调用方保证。
    """
    ratio = _finite_number(zero_axis_ratio)
    if ratio is None or ratio < 0:
        raise ValueError('zero_axis_ratio须为有限非负数')
    visible, time_kind = _visible_units(units, as_of, level)
    rows = _available_bars(bars, as_of)
    # 迟到的历史缺口不能改变此前EMA; 须由调用方提交新的输入版本。
    if any(a is not b for a, b in zip(rows, bars[:len(rows)])):
        raise ValueError('可见行情须为连续前缀, 不允许跳过迟到历史行')
    validate_bars(rows)
    if not rows or not visible:
        return FirstPointScan([], (), 0)
    for a, b in zip(rows, rows[1:]):
        if _time(a['available_dt'], time_kind) > _time(b['available_dt'], time_kind):
            raise ValueError('行情到达时间须按序非递减')
    dt_map = {row['dt']: i for i, row in enumerate(rows)}
    dif, dea, hist = macd_series(rows)
    out, excluded = [], []
    completed = confirm_level_up(visible, as_of, level)
    for trend in completed:
        if trend.kind not in ('up', 'down'):
            excluded.append((trend.move_id, 'not_trend'))
            continue
        prefix = [u for u in visible if u.move_id in trend.evidence_ids]
        decomposed, traces = _level_up_traced(prefix)
        pair = next((m, spans) for m, spans in zip(decomposed, traces)
                    if m.complete and m.start_dt == trend.start_dt)
        move, spans = pair
        previous, last = spans[-2:]
        prev_end, last_end = _tail(prefix, previous, trend.kind), _tail(prefix, last, trend.kind)
        if prev_end is None or last_end is None:
            excluded.append((trend.move_id, 'no_comparable_center_tail'))
            continue
        reference = prefix[prev_end+1:last[0]]
        leave = prefix[last_end+1:move.seg_end+1]
        if not reference or not leave or _net(reference[0]) != trend.kind or _net(leave[-1]) != trend.kind:
            excluded.append((trend.move_id, 'no_directional_compare_legs'))
            continue
        # 课20: 不仅ZD/ZG, 中枢周围波动也不得重叠。
        p = prefix[previous[0]:prev_end+1]
        c = prefix[last[0]:last_end+1]
        p_low, p_high = min(u.low for u in p), max(u.high for u in p)
        c_low, c_high = min(u.low for u in c), max(u.high for u in c)
        up = trend.kind == 'up'
        if not (c_low > p_high if up else c_high < p_low):
            excluded.append((trend.move_id, 'center_waves_overlap'))
            continue
        price = _price(leave[-1].end_price)
        if not (price > c_high if up else price < c_low):
            excluded.append((trend.move_id, 'no_new_extreme'))
            continue
        if price != (max(u.high for u in leave) if up else min(u.low for u in leave)):
            excluded.append((trend.move_id, 'internal_extreme_time_unknown'))
            continue  # 内部极值不猜发生时刻, 不把净端点叫背驰极值。
        boundaries = [reference[0].start_dt, reference[-1].end_dt,
                      c[0].start_dt, c[-1].end_dt, leave[0].start_dt, leave[-1].end_dt]
        if any(_time(dt, time_kind) > _time(rows[-1]['dt'], time_kind) for dt in boundaries):
            excluded.append((trend.move_id, 'waiting_price_evidence'))
            continue  # 结构先到、末端行情尚未到达, 等待价格证据。
        if any(dt not in dt_map for dt in boundaries):
            raise ValueError('比较段与中枢端点须有精确行情, 不近似匹配')
        a, b, z0, z1, c0, c1 = [dt_map[dt] for dt in boundaries]
        sign = 1 if up else -1
        area_a = float(sum(max(sign*float(v), 0.) for v in hist[a+1:b+1]))
        area_c = float(sum(max(sign*float(v), 0.) for v in hist[c0+1:c1+1]))
        zero = min(max(abs(float(dif[i])), abs(float(dea[i])))/rows[i]['close']
                   for i in range(z0, z1+1))
        if not 0 < area_c < area_a:
            excluded.append((trend.move_id, 'area_not_positive_and_weaker'))
            continue
        if zero > ratio:
            excluded.append((trend.move_id, 'no_zero_axis_pull'))
            continue
        if trend.centers[-1][0] == trend.centers[-1][1]:
            excluded.append((trend.move_id, 'zero_width_center'))
            continue  # 二三类接口当前不表达零宽中枢。
        formed = prefix[last[1]].confirmed_dt
        center = ConfirmedCenter(json.dumps([level, prefix[last[0]].move_id],
                    ensure_ascii=False, separators=(',', ':')), level,
                    trend.centers[-1][0], trend.centers[-1][1], formed)
        known = max([trend.confirmed_dt]+[r['available_dt'] for r in rows[:c1+1]],
                    key=lambda v: _time(v, time_kind))
        identity = json.dumps([level, trend.move_id, 'first'], ensure_ascii=False, separators=(',', ':'))
        out.append(FirstPoint(identity, 'sell1' if up else 'buy1', level,
                             visible[0].level, leave[-1].end_dt, price, known,
                             trend.move_id, center, tuple(u.move_id for u in reference),
                             tuple(u.move_id for u in leave), area_a, area_c, zero, 'macd_area'))
    return FirstPointScan(out, tuple(excluded), len(completed))
