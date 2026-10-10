# -*- coding: utf-8 -*-
"""课108: 分型区间意义的底部/顶部构造, 与精确走势定义分别命名。

原文:「跌破分型最低点意味着底部构成失败」;「有效站住分型区间
上边沿」意味着成功; 顶部镜像。失败看盘中极值, 严格跌破/升破,
触沿不算失败。原文没有量化“有效”, 本模块约定连续confirm根收盘
严格越过成功边沿(默认2, 可调), 不将此约定或结果称为成笔证明。

区间由调用方在分型已确认时冻结, 可使用既有FX的三K线总区间。
区间边沿如何选取须由调用方明确, 不推定尚未形成的月分型已确认。
confirmed_dt为该冻结版本实际可见时间, 不是中间K线dt。
只消费在此之后闭合且观察时点已经到达的原始行情; 不使用NewBar
近似收盘、同一根形成分型的K线或事后修订后的分型替换旧构造。
终态表示本次构造首次成功/失败, 后续跌回或升回不改写该历史结论。
"""
from collections import namedtuple
from numbers import Integral

from chan.availability import _available_bars
from chan.bars import _bar_time, validate_bars
from chan._series import _finite_number


class ConfirmedFractalRange(namedtuple('ConfirmedFractalRangeBase',
                                      'kind dt low high confirmed_dt level')):
    """不可变区间版本: kind=bottom/top, dt为分型端点, level为周期标识。

    low/high是已知区间, 须为有限正数且low<high。对象本身不证明分型
    形成或级别有效, 调用方从逐前缀/当时存档建立确认版本。未来版本
    的价格在fractal_range_state中不可见, 不参与价格校验或判定。
    """
    __slots__ = ()

    def to_dict(self):
        return dict(kind=self.kind, dt=str(self.dt), low=self.low, high=self.high,
                    confirmed_dt=str(self.confirmed_dt), level=self.level)


class FractalRangeState(namedtuple('FractalRangeStateBase',
                                  'phase kind level start_dt end_dt first_test_dt streak recovered')):
    """waiting/constructing/testing/completed/failed, 时间均为可见时间。

    testing是未满足连续收盘次数; recovered表示一次未确认越沿被收回。
    start_dt为分型确认时间, end_dt为首个终态行情到达时间。streak在
    终态冻结; 空可见行情不会补造成功。相反边沿失守优先于本根成功。
    """
    __slots__ = ()

    def to_dict(self):
        return dict(phase=self.phase, kind=self.kind, level=self.level,
                    start_dt=None if self.start_dt is None else str(self.start_dt),
                    end_dt=None if self.end_dt is None else str(self.end_dt),
                    first_test_dt=None if self.first_test_dt is None else str(self.first_test_dt),
                    streak=self.streak, recovered=self.recovered)


def fractal_range_state(fractal, bars, as_of, confirm=2):
    """按可用行情前缀判定一次分型区间构造(课108), 不返回买卖信号。

    fractal: ConfirmedFractalRange或None; 未确认/None返回waiting。
    bars: 标准原始OHLCV加closed_dt/available_dt, 时间严格递增。
        行情同分型同级别、复权价格基准及供应版本由调用方保证。
    as_of: 截断实际到达时间, 时间表示/时区须与分型和行情一致。
    confirm: 正整数(禁bool); 连续收盘严格越沿的次数, 工程参数。

    底部low<区间low即failed, 否则close>区间high连续confirm根则
    completed; 顶部镜像。恰好触沿打断成功连续, 不宣告失败。
    在分型确认前已经闭合的行情不计入其后构造, 包括延迟到达的旧行。
    空前缀可返回constructing; 时间元数据始终校验, 未来OHLC不读取。
    """
    if isinstance(confirm, bool) or not isinstance(confirm, Integral) or confirm < 1:
        raise ValueError('confirm须为正整数')
    cutoff, time_kind = _bar_time(as_of)
    visible = _available_bars(bars, as_of)
    validate_bars(visible)
    arrivals = [_bar_time(bar['available_dt'])[0] for bar in visible]
    if any(right < left for left, right in zip(arrivals, arrivals[1:])):
        raise ValueError('状态行情available_dt须非降序, 乱序交付须先建立版本快照')
    if fractal is None:
        return FractalRangeState('waiting', None, None, None, None, None, 0, False)
    if not isinstance(fractal, ConfirmedFractalRange):
        raise ValueError('fractal须为ConfirmedFractalRange或None')
    if fractal.kind not in ('bottom', 'top'):
        raise ValueError('kind须为bottom/top')
    if not isinstance(fractal.level, str) or not fractal.level.strip():
        raise ValueError('level须为非空字符串')
    endpoint, endpoint_kind = _bar_time(fractal.dt)
    known, known_kind = _bar_time(fractal.confirmed_dt)
    if endpoint_kind != time_kind or known_kind != time_kind or endpoint > known:
        raise ValueError('分型时间须同口径且dt<=confirmed_dt')
    # 将未来区间的身份时间与价格分开: 不能因未来坏价格污染当前状态。
    if known > cutoff:
        return FractalRangeState('waiting', None, None, None, None, None, 0, False)
    low, high = _finite_number(fractal.low), _finite_number(fractal.high)
    if low is None or high is None or not 0 < low < high:
        raise ValueError('区间须为有限正价且low<high')
    phase, first_test, streak, recovered, end = 'constructing', None, 0, False, None
    for bar in visible:
        closed = _bar_time(bar['closed_dt'])[0]
        if closed <= known:
            continue  # 构成分型/延迟交付的旧K线不能充当其后独立确认。
        invalid = bar['low'] < low if fractal.kind == 'bottom' else bar['high'] > high
        if invalid:
            phase, end = 'failed', bar['available_dt']
            break  # 课108极值失守立即失败, 同根收盘再好也不挽回该次构造。
        beyond = bar['close'] > high if fractal.kind == 'bottom' else bar['close'] < low
        if beyond:
            first_test = bar['available_dt'] if first_test is None else first_test
            streak += 1
            phase = 'testing'
            if streak >= confirm:
                phase, end = 'completed', bar['available_dt']
                break  # 保留首次成功时间; 后续反向行情属于新的研究问题。
        else:
            recovered = recovered or streak > 0
            streak, phase = 0, 'constructing'
    return FractalRangeState(phase, fractal.kind, fractal.level,
                             fractal.confirmed_dt, end, first_test, streak, recovered)
