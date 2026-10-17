# -*- coding: utf-8 -*-
"""只读真实分型区间验收: 前缀冻结区间、独立边界预期与未来隔离。

日线闭合15:00、到达15:05是测试约定, 源数据没有真实交付版本。
分型右邻合并组经下一无包含K线固定后才登记; 仅观察2026新形成区间。
每个构造用发现时的因子锁定统一价格坐标, 后续只读取当时前缀因子。
不验证供应方历史因子版本, 不作收益/成笔/交易平台结论。
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_core_history import CODES, bars_from, digest, load_frames
import chan


def dated(rows):
    for row in rows:
        row['closed_dt'] = row['dt'] + timedelta(hours=15)
        row['available_dt'] = row['closed_dt'] + timedelta(minutes=5)
    return rows


def locked_bars(frame, anchor):
    """直接算锁定因子坐标, 避免观察锚->构造锚的重复浮点转换。"""
    return dated(bars_from(frame, '1d', anchor=anchor))


def reference(fractal, rows):
    """独立判定的三个原文/工程分支, 不调用核心内部状态函数。"""
    run = 0
    for row in rows:
        if row['closed_dt'] <= fractal.confirmed_dt:
            continue
        if ((fractal.kind == 'bottom' and row['low'] < fractal.low) or
                (fractal.kind == 'top' and row['high'] > fractal.high)):
            return 'failed', row['available_dt']
        close_out = (row['close'] > fractal.high if fractal.kind == 'bottom'
                     else row['close'] < fractal.low)
        run = run + 1 if close_out else 0
        if run == 2:
            return 'completed', row['available_dt']
    return ('testing' if run else 'constructing'), None


def check(frame):
    first = next(i for i, dt in enumerate(frame['trade_date']) if dt.year == 2026)
    active, identities, terminals = [], set(), {}
    counts, checks, seen = Counter(), 0, 0
    for stop in range(first + 1, len(frame) + 1):
        prefix = frame.iloc[:stop]
        rows = dated(bars_from(prefix, '1d'))
        new = chan.remove_includes(rows)
        now = rows[-1]['available_dt']
        for fx in chan.find_fxs(new):
            # 最末合并组可延伸, 未固定的右邻不能用来冻结分型版本。
            if fx.bar_index + 1 >= len(new) - 1 or fx.elements[-1] < first - 1:
                continue
            identity = (fx.kind, new[fx.bar_index].elements[0])
            if identity in identities:
                continue
            identities.add(identity)
            active.append((identity, stop, float(prefix['adj_factor'].iloc[-1]),
                           chan.ConfirmedFractalRange(fx.kind, fx.dt, fx.low, fx.high, now, 'day')))
            seen += 1
        for identity, created, anchor, fractal in active:
            # 同一原始价格在每次观察按同一路径求值, 不经当前锚二次转换。
            history = locked_bars(prefix.iloc[created:], anchor)
            result = chan.fractal_range_state(fractal, history, now)
            expected = reference(fractal, history)
            assert (result.phase, result.end_dt) == expected, (identity, now)
            future_dt = rows[-1]['dt'] + timedelta(days=1)
            future = dict(dt=future_dt, closed_dt=future_dt + timedelta(hours=15),
                          available_dt=future_dt + timedelta(hours=15, minutes=5),
                          high=float('nan'))
            assert chan.fractal_range_state(fractal, history + [future], now) == result
            if identity in terminals:
                # 比较状态/终态时间, 不比较每次不同坐标的价格表示。
                assert result == terminals[identity], (identity, '终态改写')
            elif result.phase in ('completed', 'failed'):
                terminals[identity] = result
            counts[fractal.kind + ':' + result.phase] += 1
            checks += 1
    examples = []
    for identity, created, anchor, fractal in active:
        result = terminals.get(identity)
        if result is not None and len(examples) < 8:
            examples.append(dict(fractal=fractal.to_dict(), result=result.to_dict(),
                                 anchor_factor=anchor))
    return dict(daily_rows=len(frame), observations=len(frame) - first,
                frozen_fractal_ranges=seen, prefix_checks=checks,
                future_poison_checks=checks, terminal_revisions=0,
                state_snapshot_counts=dict(counts), terminal_examples=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, receipt = args.dataset.resolve(), []
    frames = load_frames(root, '1d', CODES, receipt)
    report = dict(version=chan.__version__, dataset=str(root),
                  manifest_sha256=digest(root / 'manifest.json'), files=receipt,
                  scope=__doc__, confirm=2, assets=[], errors=[])
    for code in CODES:
        try:
            result = check(frames[code])
            report['assets'].append(dict(code=code, **result))
            print(code, result['frozen_fractal_ranges'], result['prefix_checks'], 'OK', flush=True)
        except Exception as error:
            report['errors'].append(dict(code=code, error=repr(error)))
            print(code, repr(error), flush=True)
    report['ok'] = len(report['assets']) == len(CODES) and not report['errors']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    sys.exit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
