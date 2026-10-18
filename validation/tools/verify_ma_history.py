# -*- coding: utf-8 -*-
"""均线辅助候选真实前缀验收, 工程/算术核对不替代原图点位标注。

十ETF日线2026观察及30m末20交易日, 因子锁定在各序列2026首观察日。
日线15:00闭合/15:05到达, 30m trade_time视为结束/+1分钟为测试约定。
源无历史发布版本; 不证明实际时效、理论全部点位、收益或成交有效性。
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_core_history import CODES, bars_from, digest, load_frames
from verify_core_available import prepare_prices
import chan


def timed(rows, period):
    for row in rows:
        row['closed_dt'] = row['dt'] + timedelta(hours=15) if period == '1d' else row['dt']
        row['available_dt'] = row['closed_dt'] + timedelta(minutes=5 if period == '1d' else 1)
    return rows


def audit(event, rows, short, long, indices):
    """独立核对已输出候选的极值、面积算术、趋势与确认行, 不调用内部组合。"""
    start, end = indices[event.evidence_start_dt], indices[event.evidence_end_dt]
    confirming = next(i for i, row in enumerate(rows) if row['available_dt'] == event.confirmed_dt)
    price_key = 'low' if event.kind.startswith('ma_buy') else 'high'
    span = rows[start:end+1]
    target = min(span, key=lambda row: row[price_key]) if price_key == 'low' else max(
        span, key=lambda row: row[price_key])
    assert (event.dt, event.price) == (target['dt'], target[price_key])
    if event.pattern == 'first_continuation':
        assert event.kiss_index == 1 and event.pre_gain >= .02
        assert event.volume_ratio is not None and event.volume_ratio <= 2
        assert rows[confirming]['dt'] == event.kiss_end_dt
        return
    # 0.12.1 起飞吻/唇吻前置的均线第一类候选放开(见 ma-points-0121
    # 行为差异收据), 三分类均为合法吻种; 面积与趋势核对对三种吻同构。
    assert event.kiss_index >= 2 and event.kiss_kind in ('wet', 'fly', 'lip')
    ref_start, ref_end = indices[event.reference_start_dt], indices[event.reference_end_dt]
    previous = rows[ref_start:ref_end+1]
    # 默认面积模式; 独立滑窗SMA和直接求和, 不用ma_areas/find_ma_bc输出自证。
    previous_area = abs(sum(short[i]-long[i] for i in range(ref_start, ref_end+1)))
    current_area = abs(sum(short[i]-long[i] for i in range(start, end+1)))
    assert math.isclose(event.reference_strength, previous_area, rel_tol=1e-10, abs_tol=1e-10)
    assert math.isclose(event.current_strength, current_area, rel_tol=1e-10, abs_tol=1e-10)
    assert current_area < previous_area
    assert confirming == end+1
    sign = -1 if price_key == 'low' else 1
    assert sign*(short[confirming]-long[confirming]) <= 0
    if sign < 0:
        assert min(r['low'] for r in span) < min(r['low'] for r in previous)
        assert max(r['high'] for r in span) < max(r['high'] for r in previous)
    else:
        assert min(r['low'] for r in span) > min(r['low'] for r in previous)
        assert max(r['high'] for r in span) > max(r['high'] for r in previous)


def check(frame, period):
    key = 'trade_date' if period == '1d' else 'trade_time'
    first = next(i for i, time in enumerate(frame[key]) if time.year == 2026)
    anchor = float(frame['adj_factor'].iloc[first])
    precision = None
    if period != '1d':
        frame, precision = prepare_prices(frame)
    fixed = timed(bars_from(frame, period, anchor=anchor), period)
    if period == '1d':
        stops = list(range(first+1, len(frame)+1))
    else:
        days = sorted(set(row['dt'].date() for row in fixed))[-20:]
        stops = [i+1 for i, row in enumerate(fixed) if row['dt'].date() in days]
    previous, snapshots, unique, examples = set(), Counter(), {}, {}
    for stop in stops:
        now = fixed[stop-1]['available_dt']
        actual = chan.find_ma_points(fixed, now)
        independent = timed(bars_from(frame.iloc[:stop], period, anchor=anchor), period)
        assert actual == chan.find_ma_points(independent, now), '独立原始前缀不一致'
        future = [{key: row[key] for key in ('dt','closed_dt','available_dt')}
                  for row in fixed[stop:]]
        assert actual == chan.find_ma_points(independent+future, now), '未来OHLC缺失污染'
        current = set(actual)
        assert previous.issubset(current), '既有候选记录修订/撤销'
        previous = current
        indices = {row['dt']: i for i, row in enumerate(independent)}
        closes = [row['close'] for row in independent]
        short = [None if i<4 else sum(closes[i-4:i+1])/5 for i in range(len(closes))]
        long = [None if i<9 else sum(closes[i-9:i+1])/10 for i in range(len(closes))]
        for event in actual:
            if event.confirmed_dt < fixed[first]['available_dt']:
                continue  # 暖机历史不计2026新候选; 它仍参加稳定性校验。
            audit(event, independent, short, long, indices)
            snapshots[event.kind] += 1
            identity = (event.kind,str(event.dt),str(event.confirmed_dt),str(event.kiss_start_dt))
            unique[identity] = event.kind
            examples.setdefault(event.kind, event.to_dict())
        before = fixed[stop-1]['closed_dt']-timedelta(microseconds=1)
        assert chan.find_ma_points(fixed, before) == chan.find_ma_points(fixed[:stop-1], before)
    return dict(period=period, rows=len(frame), observations=len(stops), anchor_factor=anchor,
                anchor_dt=str(fixed[first]['dt']), independent_prefix_checks=len(stops),
                future_poison_checks=len(stops), pre_close_checks=len(stops),
                candidate_record_revisions=0, unique_candidates=dict(Counter(unique.values())),
                state_snapshot_counts=dict(snapshots), examples=examples, price_precision=precision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, receipt = args.dataset.resolve(), []
    daily = load_frames(root, '1d', CODES, receipt)
    minutes = load_frames(root, '30m', CODES, receipt)
    report = dict(version=chan.__version__, dataset=str(root), manifest_sha256=digest(root/'manifest.json'),
                  files=receipt, scope=__doc__, parameters=dict(short_period=5,long_period=10,
                  min_pre_gain=.02,max_volume_ratio=2,proximity=.5,min_depth=.2,flip_confirm=.5),
                  assets=[],errors=[])
    for code in CODES:
        try:
            result = dict(code=code, day=check(daily[code], '1d'), minute=check(minutes[code], '30m'))
            report['assets'].append(result)
            print(code,result['day']['unique_candidates'],result['minute']['unique_candidates'],'OK',flush=True)
        except Exception as error:
            report['errors'].append(dict(code=code,error=repr(error)))
            print(code,repr(error),flush=True)
    report['ok'] = len(report['assets']) == len(CODES) and not report['errors']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    sys.exit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
