# -*- coding: utf-8 -*-
"""0.13.5 固定样本性能基线(§11.9 第6条)。

确定性合成样本(显式线性同余生成器, 不用 random 模块)在代表性日线
(1,390根)与分钟(1,744根)规模上冻结管线与回放的规模计数: 相同种子在
任何 Python 3.6+ 环境逐字段一致, 是性能基线的可复现配置。内存边界
用 tracemalloc 峰值设上限, 防止结果对象意外放大。耗时与机器相关,
不作回归断言; 代表性真实数据耗时记录见本仓库 validation/ 收据
(perf-baseline-0135), 本测试只冻结规模与内存边界。

样本为纯合成行情, 只度量计算成本与计数稳定性, 不承担理论验证;
理论进度唯一登记在正式计划 §6。
"""
from datetime import datetime, time, timedelta
import os
import sys
import tracemalloc
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import analyze_bars, replay_bars
from chan.levels import decompose_levels


def synth_bars(n, start, seed, step_minutes=0):
    """确定性合成OHLCV: 显式LCG, 同参数跨版本逐字节一致。

    价格为围绕10元的小幅随机游走, 含wick与量能扰动; step_minutes为0
    生成跳过周末的日线, 否则生成30分钟网格(10:30-13:00, 跳过周末)。
    """
    bars = []
    state = seed & 0x7FFFFFFF
    price = 10.0
    dt = start

    def rand():
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return (state >> 16) / 32768.0

    for _ in range(n):
        open_ = price
        close = price * (1.0 + (rand() - 0.5) * 0.03 + (rand() - 0.5) * 0.02)
        high = max(open_, close) * (1.0 + rand() * 0.012)
        low = min(open_, close) * (1.0 - rand() * 0.012)
        volume = 1000000.0 + rand() * 900000.0
        bars.append(dict(dt=dt, open=open_, high=high, low=low,
                         close=close, volume=volume))
        price = close
        if step_minutes:
            dt = dt + timedelta(minutes=step_minutes)
            while dt.weekday() >= 5 or not (time(10, 30) <=
                                            time(dt.hour, dt.minute) <=
                                            time(13, 0)):
                dt = dt + timedelta(minutes=30)
        else:
            dt = dt + timedelta(days=1)
            while dt.weekday() >= 5:
                dt = dt + timedelta(days=1)
    return bars


DAILY_BARS = synth_bars(1390, datetime(2021, 1, 4, 15, 5), 20261017)
MINUTE_BARS = synth_bars(1744, datetime(2026, 1, 5, 10, 30), 20261018,
                         step_minutes=30)

FROZEN_SCALE = {
    ('daily', '81'): dict(new_bars=929, fxs=420, bis=101, xds=16, bi_zss=13,
                          xd_zss=3, buy=12, sell=4, levels=[101, 7, 1]),
    ('daily', '106'): dict(new_bars=929, fxs=420, bis=127, xds=18, bi_zss=19,
                           xd_zss=3, buy=17, sell=6, levels=[127, 7, 1]),
    ('minute', '81'): dict(new_bars=1153, fxs=527, bis=119, xds=15, bi_zss=11,
                           xd_zss=3, buy=10, sell=2, levels=[119, 5, 1]),
    ('minute', '106'): dict(new_bars=1153, fxs=527, bis=161, xds=21, bi_zss=19,
                            xd_zss=3, buy=18, sell=6, levels=[161, 7, 1]),
}
PIPELINE_MEMORY_CEILING = 32 * 1024 * 1024
REPLAY_MEMORY_CEILING = 16 * 1024 * 1024
REPLAY_TAIL_OBSERVATIONS = 200
REPLAY_TAIL_CHANGES = 598
REPLAY_TAIL_KINDS = dict(appeared=541, revised=53, withdrawn=4)


def pipeline_counts(bars, standard):
    result = analyze_bars(bars, bi_standard=standard)
    levels = decompose_levels(result.bis)
    return result, dict(
        new_bars=len(result.new_bars), fxs=len(result.fxs),
        bis=len(result.bis), xds=len(result.xds),
        bi_zss=len(result.bi_zss), xd_zss=len(result.xd_zss),
        buy=len(result.buy_points), sell=len(result.sell_points),
        levels=[len(level.moves) for level in levels])


class TestPerformanceBaseline(unittest.TestCase):
    def test_daily_pipeline_scale_frozen(self):
        """日线1,390根: 两标准管线与多级分解规模逐字段冻结。"""
        for standard in ('81', '106'):
            tracemalloc.start()
            result, counts = pipeline_counts(DAILY_BARS, standard)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(counts, FROZEN_SCALE[('daily', standard)])
            self.assertEqual(result.as_of, DAILY_BARS[-1]['dt'])
            self.assertLess(peak, PIPELINE_MEMORY_CEILING)

    def test_minute_pipeline_scale_frozen(self):
        """分钟1,744根: 两标准管线与多级分解规模逐字段冻结。"""
        for standard in ('81', '106'):
            tracemalloc.start()
            result, counts = pipeline_counts(MINUTE_BARS, standard)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(counts, FROZEN_SCALE[('minute', standard)])
            self.assertEqual(result.as_of, MINUTE_BARS[-1]['dt'])
            self.assertLess(peak, PIPELINE_MEMORY_CEILING)

    def test_daily_replay_tail_scale_and_memory_boundary(self):
        """末200观察回放: 快照/变更/三类动作冻结, 内存峰值设上限。"""
        observations = [bar['dt'] for bar in DAILY_BARS][-REPLAY_TAIL_OBSERVATIONS:]
        tracemalloc.start()
        snapshots = 0
        changes = 0
        kinds = dict(appeared=0, revised=0, withdrawn=0)
        first_observed = None
        for snapshot in replay_bars(DAILY_BARS, observations=observations):
            snapshots += 1
            if first_observed is None:
                first_observed = snapshot.observed_dt
            changes += len(snapshot.changes)
            for change in snapshot.changes:
                kinds[change.kind] += 1
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(snapshots, REPLAY_TAIL_OBSERVATIONS)
        self.assertEqual(changes, REPLAY_TAIL_CHANGES)
        self.assertEqual(kinds, REPLAY_TAIL_KINDS)
        self.assertEqual(first_observed, observations[0])
        self.assertLess(peak, REPLAY_MEMORY_CEILING)


if __name__ == '__main__':
    unittest.main()
