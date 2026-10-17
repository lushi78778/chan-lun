# -*- coding: utf-8 -*-
"""指定ETF历史Parquet的真实数据验收；只读输入，结果写入指定JSON。

现代本地工具需pyarrow；不纳入核心库运行依赖。不证明交易有效性或旧平台兼容。
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import chan

CODES = ['510300.SH', '510500.SH', '512880.SH', '512480.SH', '159915.SZ',
         '513100.SH', '518880.SH', '511010.SH', '588000.SH', '516160.SH']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_frames(dataset, period, codes, receipt):
    import pyarrow.parquet as pq
    import pandas as pd
    manifest = json.loads((dataset / 'manifest.json').read_text())
    files = manifest['datasets'][period]['files']
    if period != '1d':
        files = [item for item in files if item.get('partition') == '2026']
    time_key = 'trade_date' if period == '1d' else 'trade_time'
    frames = []
    for item in files:
        path = dataset / item['path']
        actual = digest(path)
        assert actual == item['sha256'], str(path)
        receipt.append({'path': item['path'], 'sha256': actual})
        table = pq.read_table(path, columns=['ts_code', time_key, 'open', 'high',
                                           'low', 'close', 'vol', 'adj_factor'],
                              filters=[('ts_code', 'in', codes)])
        frames.append(table.to_pandas())
    frame = pd.concat(frames, ignore_index=True)
    assert not frame.duplicated(['ts_code', time_key]).any()
    return {code: group.sort_values(time_key).reset_index(drop=True)
            for code, group in frame.groupby('ts_code')}


def bars_from(frame, period, anchor=None):
    # 缺省每前缀锚定最后因子; 显式anchor须由调用方提供当时已知的锁定基准。
    factor = frame['adj_factor']
    assert factor.notna().all() and (factor > 0).all(), '复权因子缺失或无效'
    anchor = float(factor.iloc[-1]) if anchor is None else float(anchor)
    if not math.isfinite(anchor) or anchor <= 0:
        raise ValueError('复权锚须为有限正数')
    adjusted = frame.copy()
    scale = factor / anchor
    for key in ('open', 'high', 'low', 'close'):
        adjusted[key] = adjusted[key] * scale
    key = 'trade_date' if period == '1d' else 'trade_time'
    bars = chan.normalize_bars(adjusted, dt_col=key, volume_col='vol')
    chan.validate_bars(bars)
    return bars


def check_asset(code, frame, minute_frame):
    bars = bars_from(frame, '1d')
    result = chan.analyze_bars(bars)
    result106 = chan.analyze_bars(bars, bi_standard='106')
    closes = [bar['close'] for bar in bars]
    ma5, ma10 = chan.sma_series(closes, 5), chan.sma_series(closes, 10)
    powers, breaks = Counter(), Counter()
    for fx in result.fxs:
        power = chan.classify_fx(fx, result.new_bars)
        powers[power.power] += 1
        # 分型右邻包含组完结之后观察均线突破。
        first = result.new_bars[fx.bar_index + 1].elements[-1] + 1
        breaks[chan.ma_break_state(closes[first:], ma5[first:], fx.kind).state] += 1
    guard = chan.macd_guard_series(result.dif, result.dea)
    assert len(guard) == len(bars)
    # 独立算术检查：最末SMA与原始窗口均值一致。
    assert math.isclose(ma5[-1], sum(closes[-5:]) / 5.0, rel_tol=1e-12)
    classification = chan.ma_strength_class(closes, max(233, len(closes)-120))
    levels = chan.decompose_levels(result.bis)
    moves = chan.same_level_decompose(result.bis)
    higher = chan.level_up(moves)
    zhongyin = chan.track_zhongyin(moves)
    gaps = chan.find_gaps(bars)
    for gap in gaps[-10:]:
        chan.classify_gap(gap, bars)
    chan.ma_areas(ma5, ma10)
    ma_bc = chan.find_ma_bc(ma5, ma10)
    chan.avg_strength_state(ma5, ma10)
    kisses = chan.find_kisses(ma5, ma10, [b['volume'] for b in bars])
    chan.boll_events(closes)
    chan.boll_bs1_hints(closes)
    chan.level_reading(levels, bars[-1]['dt'])
    chan.change_starts_low(result.bis, moves)
    if result.bis:
        state = chan.bi_state(result.bis[-1].direction, None)
        chan.bi_transition_valid(state, state)
        chan.disease_stage(state, state, 1)
    if result.bi_zss:
        z = result.bi_zss[-1]
        chan.oscillation_monitor((z.zd, z.zg), result.bis[-12:])
        chan.osc_strength(chan.oscillation_monitor((z.zd, z.zg), result.bis[-12:]))
        chan.zn_next_estimate(result.bis[-12:])
        chan.followup_quality(z.zd, z.zg, result.bis[-1].low, result.bis[-1].high, 'up')
        chan.zhongyin_health([(p.zd, p.zg) for p in result.bi_zss], (z.zd, z.zg))
        chan.classify_bc_turn(z, result.bis[-1], 'up')
        chan.guaranteed_rebound_gap(z, closes[-1], 'down')
        chan.classify_minor_turn(result.bis[-2], result.bis[-1], 'up')
    if len(result.bis) >= 2:
        chan.nested_bc([chan.BcNestInput(result.bis[-1].direction,
                                      result.bis[-2], result.bis[-1], bars)])
    # 只检查计算契约：旧bs候选首次可见不等于严格走势完成确认。
    candidates = result.buy_points + result.sell_points
    formation_count = 0
    for evt in candidates:
        if evt['type'] != 1:
            continue
        kind = 'buy1' if evt in result.buy_points else 'sell1'
        observation = chan.FormationEvent(kind, bars[-1]['dt'], 'day')
        assert chan.formation_state(observation, None, [], bars[-1]['dt']).in_formation
        formation_count += 1
    cross = Counter()
    if minute_frame is not None:
        for evt in result.buy_points:
            if evt['type'] == 3 and evt['dt'][:4] == '2026':
                cut = minute_frame[minute_frame['trade_time'] <= evt['dt'][:10] + ' 15:00:00']
                if len(cut):
                    r = chan.confirm_buy3_event_30m(evt, bars_from(cut, '30m'), stale_days=3)
                    cross[r['status']] += 1
    # 真实价格前缀验证：因复权锚缩放，MACD需按因子比例比较。
    prefixes = []
    for stop in [len(frame)-20, len(frame)-10, len(frame)]:
        prefix_bars = bars_from(frame.iloc[:stop], '1d')
        r = chan.analyze_bars(prefix_bars)
        assert str(r.as_of) <= str(prefix_bars[-1]['dt'])
        assert all(str(f.dt) <= str(r.as_of) for f in r.fxs)
        assert all(str(b.end_dt) <= str(r.as_of) for b in r.bis)
        prefixes.append({'as_of': str(r.as_of), 'bis': len(r.bis), 'signals': len(r.buy_points)+len(r.sell_points)})
    return {'code': code, 'input_rows': len(frame), 'bars': len(bars),
            'dropped_paused': len(frame)-len(bars), 'as_of': str(result.as_of),
            'fxs': len(result.fxs), 'bis81': len(result.bis), 'bis106': len(result106.bis),
            'xds': len(result.xds), 'zs': len(result.bi_zss), 'levels': len(levels),
            'moves': len(moves), 'higher': len(higher), 'gaps': len(gaps),
            'fx_power': dict(powers), 'ma_break': dict(breaks),
            'macd_below_zero': sum(x is True for x in guard),
            'class_no': classification.class_no, 'kisses': len(kisses), 'ma_bc': len(ma_bc),
            'legacy_buy_points': len(result.buy_points), 'legacy_sell_points': len(result.sell_points),
            'formation_observation_contracts': formation_count,
            'cross30': dict(cross), 'prefixes': prefixes}, classification


def check_replay(frame):
    """2026逐交易日独立复权前缀、未来价格扰动和观察账本验证。"""
    import numpy as np
    bars = bars_from(frame, '1d')
    stops = [i+1 for i, dt in enumerate(frame['trade_date']) if dt.year == 2026]
    observations = [frame.iloc[stop-1]['trade_date'] for stop in stops]
    full = chan.analyze_bars(bars)
    revisions, classes, breaks, formations = Counter(), Counter(), Counter(), Counter()
    fixed_start = stops[0]-1
    previous = {}
    completed_move_revisions = 0
    for stop, snapshot in zip(stops, chan.replay_bars(bars, observations)):
        prefix = bars_from(frame.iloc[:stop], '1d')
        # 行情与复权基准都先截断；未来只保留合法时间索引, 价格故意破坏。
        poisoned = prefix + [{'dt': row['trade_date'], 'high': 1e12, 'low': float('nan')}
                             for _, row in frame.iloc[stop:].iterrows()]
        current = chan.analyze_at(poisoned, prefix[-1]['dt'])
        independent = chan.analyze_bars(prefix)
        assert current.to_dict() == independent.to_dict(), '未来扰动改变历史结果'
        # 比较不同复权锚的指标, 线性MACD按锚比例缩放, 不能直接比绝对值。
        scale = float(frame['adj_factor'].iloc[-1] / frame['adj_factor'].iloc[stop-1])
        for key in ['dif', 'dea', 'hist']:
            np.testing.assert_allclose(getattr(current, key),
                                       getattr(full, key)[:len(prefix)] * scale,
                                       rtol=1e-9, atol=1e-10)
        assert [(b.direction, b.start_dt, b.end_dt) for b in current.bis] == [
            (b.direction, b.start_dt, b.end_dt) for b in snapshot.result.bis]
        for change in snapshot.changes:
            assert change.first_seen <= change.observed_dt
            revisions[change.field + ':' + change.kind] += 1
        closes = [bar['close'] for bar in prefix]
        classification = chan.ma_strength_class(closes, fixed_start)
        classes[str(classification.class_no)] += 1
        # 分型与均线突破只读取这个观察时点的行情。
        if current.fxs:
            fx = current.fxs[-1]
            first = current.new_bars[fx.bar_index+1].elements[-1]+1
            ma = chan.sma_series(closes, 5)
            breaks[chan.ma_break_state(closes[first:], ma[first:], fx.kind).state] += 1
        for side, events in [('buy', current.buy_points), ('sell', current.sell_points)]:
            for event in events:
                if event['type'] == 1:
                    seen = chan.FormationEvent(side+'1', current.as_of, 'BI-proxy')
                    formations[chan.formation_state(seen, None, [], current.as_of).phase] += 1
        # 记录批量complete声明的修订, 不把首次出现自动升级为不可撤销确认。
        complete = {str(m.start_dt): m.to_dict() for m in chan.same_level_decompose(snapshot.result.bis)
                    if m.complete}
        for identity, record in previous.items():
            if identity not in complete or complete[identity] != record:
                completed_move_revisions += 1
        previous = complete
    return {'observations': len(stops), 'start': str(observations[0]),
            'end': str(observations[-1]), 'future_price_poison_checks': len(stops),
            'macd_scaled_prefix_checks': len(stops)*3, 'changes': dict(revisions),
            'ma_classes': dict(classes), 'last_fx_ma_break': dict(breaks),
            'formation_candidate_contracts': dict(formations),
            'batch_complete_move_revisions': completed_move_revisions}


def check_second_conditions(frame):
    """真实完成分解单元的端点/极值输入, 明确仅检验条件接口。

    不把这些条件上下文宣称为自动识别的一买/小转大; 真实因果级别与
    背驰需要独立标注。本函数只记录可接线的真实价格样本及时间约束。
    """
    bars = bars_from(frame, '1d')
    result = chan.analyze_bars(bars)
    moves = [m for m in chan.same_level_decompose(result.bis) if m.complete]
    counts, skipped = Counter(), 0
    for i, (first, pull) in enumerate(zip(moves, moves[1:])):
        segments = [result.bis[m.seg_start:m.seg_end+1] for m in [first, pull]]
        endpoints = [(s[0].start_value, s[-1].end_value) for s in segments]
        if (first.end_dt != pull.start_dt or first.direction not in ('up', 'down')
                or pull.direction not in ('up', 'down') or first.direction == pull.direction
                or any((m.direction == 'up') != (end > start)
                       or start == end for m, (start, end) in zip([first, pull], endpoints))):
            skipped += 1
            continue
        observed = result.as_of
        confirmed = [chan.ConfirmedMove(str(i)+'-'+str(j), 'decomposed', m.direction,
                     m.start_dt, m.end_dt, start, end, m.low, m.high, observed)
                     for j, (m, (start, end)) in enumerate(zip([first, pull], endpoints))]
        side = 'buy' if first.direction == 'up' else 'sell'
        context = chan.SecondPointContext('conditional-'+str(i), side, 'parent-assumed',
                                          'decomposed', first.start_dt, endpoints[0][0], observed)
        output = chan.find_second_points(confirmed, [context], observed)
        assert len(output) == 1 and output[0].confirmed_dt == observed
        assert chan.find_second_points(confirmed, [context], bars[-2]['dt']) == []
        counts[output[0].kind+':'+output[0].strength] += 1
    return {'conditions': dict(counts), 'skipped_nonmatching_units': skipped,
            'scope': '真实分解端点及极值的条件接线; 上下文为验收输入, 非自动理论信号'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--replay', action='store_true', help='加跑2026逐日防未来与新二类点条件验收')
    args = p.parse_args()
    dataset = args.dataset.resolve()
    receipt = []
    frames = load_frames(dataset, '1d', CODES, receipt)
    minutes = load_frames(dataset, '30m', CODES, receipt)
    report = {'version': chan.__version__, 'dataset': str(dataset),
              'manifest_sha256': digest(dataset/'manifest.json'), 'files': receipt,
              'adjustment': 'OHLC * adj_factor[t] / adj_factor[as_of]; 每前缀独立锚定',
              'scope': '10只ETF日线全历史及2026年30m，计算契约与明确列出的前缀；非全池、非交易有效性验证',
              'formation_scope': '真实价格派生的旧bs候选输入契约，不验证因果中枢或理论确认',
              'source_time_scope': '使用存储的历史因子并逐前缀锚定; 数据集不含历史发布版本, 不证明来源当时未修订',
              'assets': [], 'errors': []}
    members = {}
    for code in CODES:
        try:
            item, classification = check_asset(code, frames[code], minutes.get(code))
            if args.replay:
                item['replay'] = check_replay(frames[code])
                item['second_conditions'] = check_second_conditions(frames[code])
            report['assets'].append(item)
            members[code] = classification
            print(code, item['bars'], 'bars OK', flush=True)
        except Exception as exc:
            report['errors'].append({'code': code, 'error': repr(exc)})
            print(code, repr(exc), flush=True)
    if members:
        sector = chan.sector_strength(members)
        report['sector'] = sector.to_dict()
    report['ok'] = not report['errors'] and len(report['assets']) == len(CODES)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
