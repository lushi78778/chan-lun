# -*- coding: utf-8 -*-
"""课11/12/15: 均线版四类辅助候选, 与中枢版点位分别命名。

课12:「没有人百分百确认那是最后一次缠绕」; 第二次起才可能是
趋势中的最后缠绕。因而本模块不回看未来挑“最后一次”, 第一类
仅称post_kiss_divergence候选。课15稳妥力度口径须再次相交封闭,
确认时间为封闭K线的实际到达, 不回填面积末端或最低/最高点。
第二类取已观察到体位转化之后的首次已了结同体位中继, 不要求湿吻
(课15回复明确飞吻/唇吻也可以), 不把左截断窗口的首次吻当首次。

量化取舍: 用既有find_kisses的差值回撤、续创新极值/转化阈值;
第一类保守要求第二次及以后已完成湿吻后的同向面积衰减, 并且该
面积内价格高点和低点均顺趋势移动(课15趋势定义的区间近似),
没有价格新极值不产生候选。第二类前腿强度默认>=2%, 前腿均量
不超过此前long_period根均量的2倍, 均为工程参数。面积法不能
覆盖所有飞/唇吻后的背驰, 即时平均力度预警仍由strength独立提供。
这些是可复现的保守辅助条件, 不证明最终趋势反转或理论精确点位。
"""
from collections import namedtuple
from numbers import Integral

from chan.availability import _available_bars
from chan.bars import _bar_time, validate_bars
from chan.kiss import find_kisses
from chan.strength import find_ma_bc, ma_areas, sma_series
from chan._series import _finite_number


class MaPoint(namedtuple('MaPointBase',
                        'kind dt price confirmed_dt pattern kiss_start_dt kiss_end_dt '
                        'kiss_index kiss_kind reference_strength current_strength pre_gain volume_ratio '
                        'reference_start_dt reference_end_dt evidence_start_dt evidence_end_dt')):
    """不可变辅助候选, kind为ma_buy1_candidate等四类, 均带candidate后缀。

    dt/price是证据区间内先出现的最低/最高点, 不保证精确转折点;
    confirmed_dt是全部所需证据实际到达时间。first类不宣称吻为最终
    最后一次, second类不要求本模块此前已经产生first类。
    strength以均线价格面积或平均面积表示, second类为None。
    """
    __slots__ = ()

    @property
    def last_kiss_proven(self):
        """first类不能把当时最近一吻说成最终最后一吻。"""
        return False if self.pattern == 'post_kiss_divergence' else None

    def to_dict(self):
        result = dict(self._asdict())
        for key in ('dt', 'confirmed_dt', 'kiss_start_dt', 'kiss_end_dt',
                    'reference_start_dt', 'reference_end_dt', 'evidence_start_dt', 'evidence_end_dt'):
            result[key] = None if result[key] is None else str(result[key])
        result['last_kiss_proven'] = self.last_kiss_proven
        return result


def _parameters(short_period, long_period, proximity, min_depth, flip_confirm,
                min_pre_gain, max_volume_ratio):
    for period in (short_period, long_period):
        if isinstance(period, bool) or not isinstance(period, Integral) or period < 1:
            raise ValueError('均线周期须为正整数')
    if short_period >= long_period:
        raise ValueError('须short_period<long_period')
    for name, value, zero in (('proximity', proximity, True),
                              ('min_depth', min_depth, True),
                              ('flip_confirm', flip_confirm, False)):
        number = _finite_number(value)
        if number is None or not (0 <= number <= 1 if zero else 0 < number <= 1):
            raise ValueError('{}须为有效比例'.format(name))
    gain = _finite_number(min_pre_gain)
    if gain is None or gain < 0:
        raise ValueError('min_pre_gain须为有限非负数')
    if max_volume_ratio is not None:
        ratio = _finite_number(max_volume_ratio)
        if ratio is None or ratio <= 0:
            raise ValueError('max_volume_ratio须为有限正数或None')


def _point(rows, kiss, start, end, confirmation, kind, pattern,
           previous=None, current=None, volume_ratio=None, reference_range=None):
    buying = kind.startswith('ma_buy')
    key = 'low' if buying else 'high'
    # 同价多次出现取最早, 避免以后同价重现重写已识别端点。
    index = min(range(start, end + 1), key=lambda i: rows[i][key]) if buying else max(
        range(start, end + 1), key=lambda i: rows[i][key])
    return MaPoint(kind, rows[index]['dt'], rows[index][key],
                   rows[confirmation]['available_dt'], pattern,
                   rows[kiss.start_idx]['dt'], rows[kiss.end_idx]['dt'],
                   kiss.kiss_index, kiss.kind, previous, current, kiss.pre_gain, volume_ratio,
                   None if reference_range is None else rows[reference_range[0]]['dt'],
                   None if reference_range is None else rows[reference_range[1]]['dt'],
                   rows[start]['dt'], rows[end]['dt'])


def find_ma_points(bars, as_of, short_period=5, long_period=10, proximity=0.5,
                   min_depth=0.2, flip_confirm=0.5, min_pre_gain=0.02,
                   max_volume_ratio=2.0, use_avg=False):
    """实际可用原始行情->均线版辅助候选列表(课11/12/15)。

    bars须同标的同周期同价格基准, 附closed_dt/available_dt; 先截断
    实际到达再计算SMA/吻/面积。未来OHLC不读取, 空前缀返回[]。
    到达非降序, 乱序交付/历史修订由输入方先建立版本快照。
    short_period/long_period是SMA周期; 吻参数与find_kisses同口径。
    min_pre_gain、max_volume_ratio只约束second类; None量比开关
    明确表示不筛量, 不把未知量当正常量。use_avg须bool, 选择面积
    或平均面积, 两者不混用。first类仅用完整同向面积及湿吻, 不
    使用当前未封闭面积猜测结束。只作识别, 不持仓、下单或计算收益。
    """
    _parameters(short_period, long_period, proximity, min_depth, flip_confirm,
                min_pre_gain, max_volume_ratio)
    if not isinstance(use_avg, bool):
        raise ValueError('use_avg须为bool')
    rows = _available_bars(bars, as_of)
    validate_bars(rows)
    times = [_bar_time(row['available_dt'])[0] for row in rows]
    if any(right < left for left, right in zip(times, times[1:])):
        raise ValueError('状态行情available_dt须非降序')
    short = sma_series([row['close'] for row in rows], short_period)
    long = sma_series([row['close'] for row in rows], long_period)
    kisses = [kiss for kiss in find_kisses(short, long, [row['volume'] for row in rows],
                                         proximity, min_depth, flip_confirm) if not kiss.open]
    points, flip_index = [], None
    for kiss in kisses:
        if not kiss.resumed:
            flip_index = kiss.end_idx
            continue  # 转化尚不是“新体位第一次中继”, 不能直接充当second。
        if flip_index is None or kiss.kiss_index != 1 or kiss.leg_start_idx < flip_index:
            continue  # 左截断状态不证明第一次; 第二次以后也不重命名为second。
        if kiss.pre_gain is None or kiss.pre_gain < min_pre_gain:
            continue  # 课12前腿须有力; 阈值为显式工程参数。
        volume_ratio = None
        if max_volume_ratio is not None:
            baseline = rows[max(0, kiss.leg_start_idx - long_period):kiss.leg_start_idx]
            mean = sum(row['volume'] for row in baseline) / len(baseline) if baseline else 0
            if mean <= 0 or kiss.vol_leg is None:
                continue  # 没有可比量能不冒充通过量能过滤。
            volume_ratio = kiss.vol_leg / mean
            if volume_ratio > max_volume_ratio:
                continue  # 课12前腿过量骗线风险, 不用后续缩量替代前腿证据。
        kind = 'ma_buy2_candidate' if kiss.direction == 'up' else 'ma_sell2_candidate'
        points.append(_point(rows, kiss, kiss.start_idx + 1, kiss.end_idx,
                             kiss.end_idx, kind, 'first_continuation', volume_ratio=volume_ratio))
    areas = ma_areas(short, long)
    for bc in find_ma_bc(short, long, use_avg):
        current = next(area for area in areas if area.start_idx == bc['start_idx'])
        previous = next(area for area in reversed(areas)
                        if area.end_idx < current.start_idx and area.sign == current.sign)
        preceding = [kiss for kiss in kisses if kiss.end_idx <= current.start_idx]
        if not preceding:
            continue
        kiss = preceding[-1]
        if (kiss.direction != bc['direction'] or not kiss.resumed or
                kiss.kiss_index < 2 or kiss.kind != 'wet'):
            continue  # 不跳过最近吻寻找更早的有利吻, 不使用第一次或未了结吻。
        ref = rows[previous.start_idx:previous.end_idx + 1]
        cur = rows[current.start_idx:current.end_idx + 1]
        if bc['direction'] == 'down':
            trending = max(row['high'] for row in cur) < max(row['high'] for row in ref) and \
                       min(row['low'] for row in cur) < min(row['low'] for row in ref)
        else:
            trending = max(row['high'] for row in cur) > max(row['high'] for row in ref) and \
                       min(row['low'] for row in cur) > min(row['low'] for row in ref)
        if not trending:
            continue  # 课15没有趋势没有背驰, 仅面积小不满足价格趋势条件。
        confirmation = current.end_idx + 1
        kind = 'ma_buy1_candidate' if current.sign < 0 else 'ma_sell1_candidate'
        prior_strength = bc['avg_prev'] if use_avg else bc['area_prev']
        cur_strength = bc['avg_last'] if use_avg else bc['area_last']
        points.append(_point(rows, kiss, current.start_idx, current.end_idx,
                             confirmation, kind, 'post_kiss_divergence', prior_strength, cur_strength,
                             reference_range=(previous.start_idx, previous.end_idx)))
    return sorted(points, key=lambda point: (_bar_time(point.confirmed_dt)[0], point.kind,
                                            _bar_time(point.dt)[0]))
