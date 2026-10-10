# -*- coding: utf-8 -*-
"""前缀回放时严禁使用未来行情; first_seen不冒充理论确认。"""
import math
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from chan import analyze_at, analyze_bars, replay_bars


def prices(length=140):
    out = []
    for i in range(length):
        value = 20 + 3 * math.sin(i / 5.0) + i / 90.0
        out.append(dict(dt=datetime(2025, 1, 1) + timedelta(days=i),
                        open=value, close=value, high=value+.2,
                        low=value-.2, volume=1000))
    return out


class TestReplay(unittest.TestCase):
    def test_cut_before_computation(self):
        """完整输入按观察日截断后与直接分析该前缀逐字段相等。"""
        bars = prices()
        self.assertEqual(analyze_at(bars, bars[69]['dt']).to_dict(),
                         analyze_bars(bars[:70]).to_dict())

    def test_future_price_poison(self):
        """未来的极值/NaN/缺字段不改变历史包含、MACD、结构及候选。"""
        bars = prices()
        expected = analyze_at(bars, bars[69]['dt']).to_dict()
        for row in bars[70:]:
            row.update(high=1e12, low=float('nan'), close=-100)
            del row['open']
        self.assertEqual(analyze_at(bars, bars[69]['dt']).to_dict(), expected)

    def test_before_input_and_empty(self):
        """观察日早于首根行情不借用以后价格。"""
        bars = prices(5)
        self.assertIsNone(analyze_at(bars, datetime(2024, 1, 1)).as_of)
        self.assertEqual(list(replay_bars([])), [])
        self.assertEqual(len(list(replay_bars([], [datetime(2024, 1, 1)]))), 1)

    def test_request_time_differs_last_bar(self):
        """请求时刻与最后可见bar分别保留, 不补造未开市行情。"""
        bars = prices(2)
        requested = bars[-1]['dt'] + timedelta(hours=12)
        snap = next(replay_bars(bars, [requested]))
        self.assertEqual(snap.observed_dt, requested)
        self.assertEqual(snap.result.as_of, bars[-1]['dt'])

    def test_right_neighbor_required(self):
        """顶分型端点在第二根, 第三根收盘前不可见。"""
        bars = prices(3)
        for row, value in zip(bars, [10., 13., 11.]):
            row.update(open=value, close=value, high=value+1, low=value-1)
        snapshots = list(replay_bars(bars))
        self.assertEqual(snapshots[1].result.fxs, [])
        event = snapshots[2].changes[0]
        self.assertEqual(event.field, 'fx')
        self.assertEqual(event.first_seen, bars[2]['dt'])
        self.assertEqual(event.after['dt'], str(bars[1]['dt']))

    def test_every_snapshot_is_prefix(self):
        """全部观察快照等于独立前缀计算, 覆盖含尾部修订的走势。"""
        bars = prices(80)
        for i, snap in enumerate(replay_bars(bars)):
            self.assertEqual(snap.result.to_dict(), analyze_bars(bars[:i+1]).to_dict())

    def test_revisions_and_withdrawals_match_snapshot_diff(self):
        """逐笔应用账本变更可重建状态; 修订不倒填first_seen。"""
        state, seen, actions = {}, {}, set()
        bars = prices(19)
        # 反向分型间距不足成笔, 随后的同向更高分型修订末笔终点。
        for row, value in zip(bars, [12, 10, 11, 12, 13, 14, 15, 16, 17,
                                   18, 20, 18, 19, 22, 21, 20, 19, 18, 17]):
            row.update(open=value, close=value, high=value+.2, low=value-.2)
        for snap in replay_bars(bars):
            for change in snap.changes:
                key = (change.field,) + change.identity
                actions.add(change.kind)
                self.assertLessEqual(change.first_seen, change.observed_dt)
                self.assertEqual(change.before, state.get(key))
                seen.setdefault(key, change.first_seen)
                self.assertEqual(change.first_seen, seen[key])
                if change.kind == 'withdrawn':
                    del state[key]
                else:
                    state[key] = change.after
        self.assertIn('appeared', actions)
        self.assertIn('revised', actions)

    def test_returned_snapshots_do_not_pollute_tracker(self):
        """消费方改动一次输出不污染之后的候选账本。"""
        bars = prices()
        observations = [row['dt'] for row in bars]
        expected = [s.to_dict() for s in replay_bars(bars, observations)]
        stream = replay_bars(bars, observations)
        for i, snap in enumerate(stream):
            self.assertEqual(snap.to_dict(), expected[i])
            if snap.result.fxs:
                snap.result.fxs[0].high = 999
            for change in snap.changes:
                if change.after is not None:
                    change.after.clear()

    def test_sparse_first_seen(self):
        """稀疏观察只能给出本网格首次出现, 不能提前到端点日。"""
        bars = prices(80)
        dates = [bars[39]['dt'], bars[79]['dt']]
        for snap in replay_bars(bars, dates):
            for change in snap.changes:
                self.assertIn(change.first_seen, dates)

    def test_input_unchanged(self):
        """前缀计算不修改行情。"""
        bars = prices(40)
        copy = deepcopy(bars)
        list(replay_bars(bars))
        self.assertEqual(bars, copy)

    def test_duplicate_unsorted_observations(self):
        """重复或倒序观察时点拒绝, 不按输入顺序猜可见时间。"""
        bars = prices(4)
        for dates in ([bars[1]['dt']]*2, [bars[3]['dt'], bars[2]['dt']]):
            with self.assertRaises(ValueError):
                list(replay_bars(bars, dates))

    def test_time_representation(self):
        """混合日期/时间及不同UTC偏移不能隐式字符串比较。"""
        bars = prices(4)
        with self.assertRaises(ValueError):
            analyze_at(bars, '2025-01-02')
        with self.assertRaises(ValueError):
            analyze_at(bars, bars[1]['dt'].replace(tzinfo=timezone(timedelta(hours=8))))
        with self.assertRaises(ValueError):
            analyze_at(bars, None)

    def test_bad_visible_price_and_unsorted_time(self):
        """可见坏行情和未来索引乱序拒绝, 不静默修正数据。"""
        bars = prices(4)
        bars[0]['close'] = -1
        with self.assertRaises(ValueError):
            analyze_at(bars, bars[1]['dt'])
        bars = prices(4)
        bars[-1]['dt'] = bars[0]['dt']
        with self.assertRaises(ValueError):
            analyze_at(bars, bars[1]['dt'])

    def test_standard106(self):
        """106成笔的原始SMA亦只能读取观察日之前。"""
        bars = prices(80)
        self.assertEqual(analyze_at(bars, bars[49]['dt'], bi_standard='106').to_dict(),
                         analyze_bars(bars[:50], bi_standard='106').to_dict())


if __name__ == '__main__':
    unittest.main()
