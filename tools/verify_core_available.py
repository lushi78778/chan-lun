# -*- coding: utf-8 -*-
"""0.7阶段实际可用时间/保守结构真实回放; 只读Parquet, 输出独立JSON。

该数据集没有实际发布版本, 到达时间为明示测试约定, 不作为平台实测。
浮点价格在复权前保留12位小数, 摘要/归一化幅度均存档; 核心不放宽校验。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_core_history import load_frames, bars_from, CODES, digest, check_asset, check_second_conditions
import chan
from collections import Counter
from datetime import timedelta
import json
import argparse

def prepare_prices(frame):
    """仅作明示的12位精度适配; 物质性坏数据在bars_from仍会报错。"""
    keys = ['open', 'high', 'low', 'close']
    out = frame.copy()
    before = frame[keys]
    after = before.round(12)
    delta = (after - before).abs()
    maximum = float(delta.max().max())
    assert maximum <= 1e-12, '精度归一化超过约定幅度'
    bad = (before['low'] > before[['open', 'close']].min(axis=1)) | (before['high'] < before[['open', 'close']].max(axis=1)) | (before['low'] > before['high'])
    out[keys] = after
    return (out, {'decimals': 12, 'max_absolute_change': maximum, 'changed_rows': int((delta > 0).any(axis=1).sum()), 'original_envelope_violations': int(bad.sum()), 'original_violation_times': [str(v) for v in frame.loc[bad, 'trade_time']]})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--modules-only', action='store_true', help='只跑全模块计算冒烟与二类点条件接线, 不重跑逐日前缀')
    args = parser.parse_args()
    root = args.dataset.resolve()
    receipt = []
    daily = load_frames(root, '1d', CODES, receipt)
    minutes = load_frames(root, '30m', CODES, receipt)
    report = {'version': chan.__version__, 'dataset': str(root), 'manifest_sha256': digest(root / 'manifest.json'), 'files': receipt, 'availability_scope': '测试约定日线15:00收盘并15:05可用; 30m按存储trade_time视为周期结束并延迟1分钟。源文件无发布到达版本，此约定不证明真实盘中到达或供应数据从未修订。', 'adjustment': '每个价格前缀OHLC*factor[t]/factor[as_of];账本另用固定锚比较形态修订', 'scope': '10只ETF全部日线冒烟、2026逐日观察及30m末20交易日前缀;非全池、非收益验证', 'assets': [], 'errors': []}
    if args.modules_only:
        report['scope'] = '十ETF全模块计算冒烟;二类点仅条件接线,旧cross30仅候选接线;不证明理论自动识别或历史端点可见'
    for code in CODES:
        try:
            frame = daily[code]
            if args.modules_only:
                minute, precision = prepare_prices(minutes[code])
                asset, _ = check_asset(code, frame, minute)
                asset['second_conditions'] = check_second_conditions(frame)
                asset['minute_precision'] = precision
                report['assets'].append(asset)
                print(code, 'module smoke OK', flush=True)
                continue
            fixed = bars_from(frame, '1d')
            for b in fixed:
                b['closed_dt'] = b['dt'] + timedelta(hours=15)
                b['available_dt'] = b['closed_dt'] + timedelta(minutes=5)
            stops = [i + 1 for i, t in enumerate(frame['trade_date']) if t.year == 2026]
            counts = Counter()
            mode = Counter()
            revisions = Counter()
            prior = {}
            completed_changes = Counter()
            for stop, snap in zip(stops, chan.replay_available(fixed, [fixed[i - 1]['available_dt'] for i in stops])):
                prefix = bars_from(frame.iloc[:stop], '1d')
                for row, meta in zip(prefix, fixed[:stop]):
                    row['closed_dt'] = meta['closed_dt']
                    row['available_dt'] = meta['available_dt']
                tail = [{'dt': r['dt'], 'closed_dt': r['closed_dt'], 'available_dt': r['available_dt'], 'low': float('nan'), 'high': 1000000000000.0} for r in fixed[stop:]]
                actual = chan.analyze_available(prefix + tail, snap.observed_dt)
                independent = chan.analyze_bars(prefix)
                assert actual.to_dict() == independent.to_dict(), '未来价格扰动'
                assert [(x.direction, x.start_dt, x.end_dt, x.complete) for x in actual.xds] == [(x.direction, x.start_dt, x.end_dt, x.complete) for x in snap.result.xds]
                same = chan.analyze_available(prefix, snap.observed_dt).to_dict()
                assert actual.to_dict() == same
                beforeclose = chan.analyze_available(prefix + tail, prefix[-1]['closed_dt'] - timedelta(minutes=1))
                assert beforeclose.as_of == (prefix[-2]['dt'] if len(prefix) > 1 else None)
                structural = {tuple([x.kind] + list(x.identity)): x.record for x in snap.structures}
                for k, r in prior.items():
                    if k[0] in ['bi', 'xd'] and structural.get(k) != r:
                        completed_changes[k[0]] += 1
                for item in snap.structures:
                    counts[item.kind] += 1
                    assert item.first_seen <= item.observed_dt
                    if item.kind == 'xd':
                        mode[str(item.record['mode'])] += 1
                for change in snap.changes:
                    revisions[change.field + ':' + change.kind] += 1
                prior = structural
            minute = minutes[code]
            minute, precision = prepare_prices(minute)
            mbars = bars_from(minute, '30m')
            for b in mbars:
                b['closed_dt'] = b['dt']
                b['available_dt'] = b['dt'] + timedelta(minutes=1)
            trading_days = sorted({b['dt'].date() for b in mbars})[-20:]
            observations = [b['available_dt'] for b in mbars if b['dt'].date() in trading_days]
            mtail = {}
            mcounts = Counter()
            mc = Counter()
            for snap in chan.replay_available(mbars, observations):
                prefix = [b for b in mbars if b['available_dt'] <= snap.observed_dt]
                future = [{'dt': b['dt'], 'closed_dt': b['closed_dt'], 'available_dt': b['available_dt']} for b in mbars if b['available_dt'] > snap.observed_dt]
                assert chan.analyze_available(prefix + future, snap.observed_dt).to_dict() == chan.analyze_bars(prefix).to_dict()
                now = {tuple([x.kind] + list(x.identity)): x.record for x in snap.structures}
                for k, r in mtail.items():
                    if k[0] in ['bi', 'xd'] and now.get(k) != r:
                        mc[k[0]] += 1
                mtail = now
                for x in snap.structures:
                    mcounts[x.kind] += 1
            asset = {'code': code, 'daily_rows': len(frame), 'daily_observations': len(stops), 'pre_close_exclusions': len(stops), 'future_poison_checks': len(stops), 'structural_snapshot_counts': dict(counts), 'xd_modes_snapshot_counts': dict(mode), 'changes': dict(revisions), 'confirmed_structure_revisions': dict(completed_changes), 'minute_price_precision': precision, 'minute_rows': len(mbars), 'minute_observations': len(observations), 'minute_structure_snapshot_counts': dict(mcounts), 'minute_confirmed_revisions': dict(mc)}
            report['assets'].append(asset)
            print(code, asset['daily_observations'], asset['minute_observations'], 'OK', flush=True)
        except Exception as e:
            report['errors'].append({'code': code, 'error': repr(e)})
            print(code, repr(e), flush=True)
    report['ok'] = len(report['assets']) == len(CODES) and (not report['errors'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    sys.exit(0 if report['ok'] else 1)
if __name__ == '__main__':
    main()
