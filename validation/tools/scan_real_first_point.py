# -*- coding: utf-8 -*-
"""0.9.9 一类买卖点成立候选发现扫描（课24/17/20/27/29/33）。

发现工具，导入核心库计算笔/线段后按冻结口径分类，不产出独立真值；
独立标注由 gen_real_first_point.py 的人工表另行冻结，扫描结果仅作
候选发现，入选窗一律以窗内重跑冻结验证。

候选口径（课24 行31-33 面积判据）：
- 前提=完成严格趋势（0.9.3 冻结口径）：A 闭合 + b 离开 + gap>0 +
  B 在首个离开核心的中间反向单元处冻结（课29 行20-26）+ c 离开 +
  proof=c+1 自外侧回核心；与 validation/tools/gen_real_strict_trend.py 的
  validate_zhongshu/validate_roles 逐条对齐；
- 背驰=0 < area_c < area_b：b=A.zn[-1]+1、c=B.zn[-1]+1 同方向柱
  正幅值和，区间(start,end]；MACD(12,26,9) 固定 EMA 自窗口首行
  起算（out[0]=values[0]，k=2/(n+1)），hist=(DIF-DEA)*2；
  EMA 起点是测试约定，不证明窗口前历史对指标无影响；
- 新极值=c 创全趋势新极值（先验极值=a 或 A 首 Zn 成员..B.zn[-1]
  单元范围）；
- 零轴回拉=max(|DIF|,|DEA|)/close 于 B zn 行区间最小值，仅登记
  （课24 明示 MACD"不绝对精确"，工程零轴门槛不作裁定依据）。

扫描范围：十标的因子恒1区间各月1日自然起点；窗口终点为起点后
1..18 个月首日，最少60行；1d/60m/30m 全分区，5m 为 2026 分区；
分钟粒度截到 2026-07-27 前干净边界（0.9.6 供应末端裁定）。
不移动自然起点、无窗口前暖机、不复制镜像。

MACD 指标是辅助证据定位，候选不等于一类点成立；成立/不成立由
人工表冻结后经编译器与测试验收（理论裁定见
validation/chan-real-first-point-theory-0.9.9.md）。
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / 'src'

CODES = ['510300.SH', '510500.SH', '512880.SH', '512480.SH', '159915.SZ',
         '513100.SH', '518880.SH', '511010.SH', '588000.SH', '516160.SH']

# 分区加载计划：1d/60m/30m 全分区，5m 为 2026 分区。
PARTITION_PLAN = {'1d': None, '60m': None, '30m': None, '5m': ('2026',)}


def import_chan():
    """显式使用工作区核心库源码，拒绝陈旧安装版。"""
    if not (CORE_SRC / 'chan' / '__init__.py').is_file():
        raise SystemExit('核心库子模块未检出；先 git submodule update --init')
    sys.path.insert(0, str(CORE_SRC))
    import chan
    real = os.path.realpath(chan.__file__)
    if real != os.path.realpath(CORE_SRC / 'chan' / '__init__.py'):
        raise SystemExit('实际导入不是工作区核心库源码: ' + real)
    return chan


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_frames(dataset, period, codes, partitions):
    import pyarrow.parquet as pq
    import pandas as pd
    manifest = json.loads((dataset / 'manifest.json').read_text())
    files = manifest['datasets'][period]['files']
    if period != '1d' and partitions is not None:
        files = [i for i in files if i.get('partition') in partitions]
    time_key = 'trade_date' if period == '1d' else 'trade_time'
    frames = []
    for item in files:
        table = pq.read_table(dataset / item['path'],
                              columns=['ts_code', time_key, 'open', 'high',
                                       'low', 'close', 'vol', 'adj_factor'],
                              filters=[('ts_code', 'in', codes)])
        frames.append(table.to_pandas())
    frame = pd.concat(frames, ignore_index=True)
    return {code: group.sort_values(time_key).reset_index(drop=True)
            for code, group in frame.groupby('ts_code')}, time_key


def clean_rows(group):
    bad = ((group['open'] <= 0) | (group['high'] <= 0) |
           (group['low'] <= 0) | (group['close'] <= 0) |
           group[['open', 'high', 'low', 'close']].isna().any(axis=1) |
           group['adj_factor'].isna() | (group['adj_factor'] <= 0))
    return group[~bad].reset_index(drop=True)


def factor_spans_list(group, time_key, min_rows=60):
    spans, start = [], None
    values = list(group['adj_factor'])
    for i, factor in enumerate(values):
        if factor == 1:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= min_rows:
                spans.append((start, i - 1))
            start = None
    if start is not None and len(values) - start >= min_rows:
        spans.append((start, len(values) - 1))
    return spans


def month_grid(first, last):
    out = []
    year, month = int(first[:4]), int(first[5:7])
    while '%04d-%02d-01' % (year, month) <= last:
        out.append('%04d-%02d-01' % (year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def ema(values, n):
    out = [0.0] * len(values)
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def macd_lists(closes):
    ef, es = ema(closes, 12), ema(closes, 26)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema(dif, 9)
    hist = [(a - b) * 2.0 for a, b in zip(dif, dea)]
    return dif, dea, hist


def zn_run_v3(units, s, zdir, allow_freeze):
    """冻结口径 zn 运行; 返回 None 或 dict(zn, last, zd, zg, gg, dd,
    dep, succ_touch, closed_by, frozen)。与 gen_real_strict_trend.py
    的 validate_zhongshu/validate_roles 逐条对齐。"""
    n = len(units)
    if units[s].direction != zdir or s + 2 >= n:
        return None
    if units[s + 2].direction != zdir:
        return None
    zd = max(units[s].low, units[s + 2].low)
    zg = min(units[s].high, units[s + 2].high)
    if zd > zg:
        return None
    middle = units[s + 1]
    if middle.low > zd or middle.high < zg:
        return None
    zn = [s, s + 2]
    last = s + 2
    dep = None
    succ_touch = None
    closed_by = None
    frozen = False
    while True:
        succ_touch = None
        mid_i = last + 1
        if mid_i >= n:
            break
        mid = units[mid_i]
        mid_departs = mid.high > zg if zdir == 'down' else mid.low < zd
        succ_i = last + 2
        if succ_i >= n:
            if mid_departs and allow_freeze:
                dep = mid_i
            break
        succ = units[succ_i]
        succ_touch = succ.low <= zg and succ.high >= zd
        if not succ_touch:
            closed_by = succ_i
            if mid_departs:
                dep = mid_i
            break
        if mid_departs and allow_freeze:
            dep = mid_i
            frozen = True
            break
        zn.append(succ_i)
        last = succ_i
    span = units[s:last + 1]
    return dict(zn=zn, last=last, zd=zd, zg=zg,
                gg=max(u.high for u in span),
                dd=min(u.low for u in span),
                dep=dep, succ_touch=succ_touch, closed_by=closed_by,
                frozen=frozen)


def scan_strict_v3(units):
    """完成严格趋势检测: A(闭合)+b+B(离开冻结)+c+proof。"""
    n = len(units)
    found = []
    for s in range(n):
        zdir = units[s].direction
        trend_dir = 'up' if zdir == 'down' else 'down'
        if s + 5 >= n:
            break
        if s >= 2 and units[s - 2].direction == zdir:
            zd0 = max(units[s - 2].low, units[s].low)
            zg0 = min(units[s - 2].high, units[s].high)
            if (zd0 <= zg0 and units[s - 1].low <= zd0
                    and units[s - 1].high >= zg0):
                continue
        if s > 0:
            p0, p1, p2 = units[s - 1], units[s], units[s + 1]
            if max(p0.low, p1.low, p2.low) <= min(p0.high, p1.high, p2.high):
                continue
        a_run = zn_run_v3(units, s, zdir, allow_freeze=False)
        if a_run is None or a_run['closed_by'] is None or a_run['dep'] is None:
            continue
        b = a_run['dep']
        b_run = zn_run_v3(units, a_run['last'] + 2, zdir, allow_freeze=True)
        if b_run is None:
            continue
        c = b_run['dep']
        gap = (b_run['dd'] - a_run['gg']) if trend_dir == 'up' \
            else (a_run['dd'] - b_run['gg'])
        item = dict(s=s, trend_dir=trend_dir, a_run=a_run, b_run=b_run,
                    b_units=[b], c_units=[c] if c is not None else [],
                    gap=gap)
        if not b_run['frozen'] or c is None:
            item['status'] = 'ongoing'
            found.append(item)
            continue
        proof_i = c + 1
        item['proof'] = proof_i
        if proof_i >= n:
            item['status'] = 'ongoing'
            found.append(item)
            continue
        proof = units[proof_i]
        if trend_dir == 'up':
            proof_ok = proof.high > b_run['zg'] and proof.low <= b_run['zg']
        else:
            proof_ok = proof.low < b_run['zd'] and proof.high >= b_run['zd']
        if gap <= 0:
            item['status'] = 'gap_fail'
            found.append(item)
            continue
        if not proof_ok:
            item['status'] = 'proof_pending'
            found.append(item)
            continue
        item['status'] = 'completed'
        found.append(item)
    return found


def analyze(bars, units, closes, dif, dea, hist, path):
    """对每个 completed 严格趋势计算面积/新极值/零轴候选字段。"""
    dt_index = {}
    for i, bar in enumerate(bars):
        key = str(bar['dt'])[:16]
        dt_index[key] = i
        dt_index.setdefault(key[:10], i)
    out = []
    for item in scan_strict_v3(units):
        if item['status'] != 'completed':
            continue
        up = item['trend_dir'] == 'up'
        sign = 1 if up else -1
        b = item['b_units'][0]
        c = item['c_units'][0]
        b_start = str(units[b].start_dt)[:16]
        b_end = str(units[b].end_dt)[:16]
        c_start = str(units[c].start_dt)[:16]
        c_end = str(units[c].end_dt)[:16]
        if any(k not in dt_index for k in (b_start, b_end, c_start, c_end)):
            continue
        b0, b1 = dt_index[b_start], dt_index[b_end]
        c0, c1 = dt_index[c_start], dt_index[c_end]
        area_b = math.fsum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
        area_c = math.fsum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
        trend_first = max(0, item['s'] - 1)
        prior = units[trend_first:item['b_run']['last'] + 1]
        if up:
            prior_ext = max(u.high for u in prior)
            c_ext = units[c].high
            b_ext = units[b].high
        else:
            prior_ext = min(u.low for u in prior)
            c_ext = units[c].low
            b_ext = units[b].low
        new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
        beyond_b = c_ext > b_ext if up else c_ext < b_ext
        beyond_env = (c_ext > item['b_run']['gg'] if up
                      else c_ext < item['b_run']['dd'])
        z_start = str(units[item['b_run']['zn'][0]].start_dt)[:16]
        z_end = str(units[item['b_run']['zn'][-1]].end_dt)[:16]
        z0, z1 = dt_index[z_start], dt_index[z_end]
        zero = min(max(abs(dif[i]), abs(dea[i])) / closes[i]
                   for i in range(z0, z1 + 1))
        out.append(dict(
            path=path, trend_dir=item['trend_dir'],
            a_zn=item['a_run']['zn'], b_zn=item['b_run']['zn'],
            b_units=item['b_units'], c_units=item['c_units'],
            proof=item['proof'],
            b_span=[b_start, b_end], c_span=[c_start, c_end],
            area_b=round(area_b, 8), area_c=round(area_c, 8),
            divergence=bool(0 < area_c < area_b),
            new_extreme=bool(new_extreme), beyond_b=bool(beyond_b),
            beyond_env=bool(beyond_env), zero_axis=round(zero, 8),
            candidate=bool(new_extreme and 0 < area_c < area_b),
            s=item['s']))
    return out


def scan_code_period(code, frames, period, chan, minute_cap, max_months):
    if code not in frames:
        return []
    time_key = 'trade_date' if period == '1d' else 'trade_time'
    group = clean_rows(frames[code])
    keys_all = [str(v)[:16] for v in group[time_key]]
    results = []
    for s, e in factor_spans_list(group, time_key):
        if period != '1d':
            cap = next((i for i in range(s, e + 1)
                        if keys_all[i][:10] >= minute_cap[:10]), None)
            if cap is not None:
                e = cap - 1
        first_key, last_key = keys_all[s][:10], keys_all[e][:10]
        grid = month_grid(first_key, last_key)
        for gi, start_key in enumerate(grid):
            s0 = s
            while s0 <= e and keys_all[s0] < start_key:
                s0 += 1
            if s0 > e:
                continue
            keys = keys_all[s0:e + 1]
            opens = list(group['open'][s0:e + 1])
            highs = list(group['high'][s0:e + 1])
            lows = list(group['low'][s0:e + 1])
            closes_r = list(group['close'][s0:e + 1])
            vols = list(group['vol'][s0:e + 1])
            bars = []
            for i, key in enumerate(keys):
                day = datetime.strptime(key[:10], '%Y-%m-%d')
                if len(key) > 10:
                    day = datetime.strptime(key, '%Y-%m-%d %H:%M')
                bars.append(dict(dt=day, open=float(opens[i]),
                                 high=float(highs[i]), low=float(lows[i]),
                                 close=float(closes_r[i]),
                                 volume=float(vols[i])))
            closes = [bb['close'] for bb in bars]
            dif, dea, hist = macd_lists(closes)
            _, _, bis = chan.chan_fx_bi(bars, standard='106')
            fixed_full = bis[:-1]
            xds_full = [xd for xd in chan.find_xds(fixed_full)
                        if xd.complete]
            for end_key in grid[gi + 1:gi + 1 + max_months]:
                n_rows = 0
                while n_rows < len(keys) and keys[n_rows] < end_key:
                    n_rows += 1
                if n_rows < 60:
                    continue
                for path, units_full in (('bi', fixed_full),
                                         ('xd', xds_full)):
                    units = [u for u in units_full
                             if str(u.end_dt)[:16] < end_key]
                    if len(units) < 6:
                        continue
                    for rec in analyze(bars[:n_rows], units,
                                       closes[:n_rows],
                                       dif[:n_rows], dea[:n_rows],
                                       hist[:n_rows], path):
                        rec.update(code=code, period=period,
                                   start=start_key, end=end_key,
                                   rows=n_rows)
                        results.append(rec)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--codes', nargs='+', default=CODES)
    parser.add_argument('--periods', nargs='+',
                        default=['1d', '60m', '30m', '5m'])
    parser.add_argument('--max-months', type=int, default=18)
    parser.add_argument('--minute-cap', default='2026-07-27')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('拒绝覆盖已归档发现输出；请使用新文件名')
    for period in args.periods:
        if period not in PARTITION_PLAN:
            parser.error('未知周期(本轮扫描计划外): ' + period)
    chan = import_chan()
    dataset = args.dataset.resolve()
    all_completed, all_hits = [], []
    summary = {}
    for period in args.periods:
        frames, _ = load_frames(dataset, period, args.codes,
                                PARTITION_PLAN[period])
        records = []
        for code in args.codes:
            recs = scan_code_period(code, frames, period, chan,
                                    args.minute_cap, args.max_months)
            records.extend(recs)
            print('--- %s %s: %d completed, %d hits' % (
                period, code, len(recs),
                sum(1 for r in recs if r['candidate'])))
        hits = [r for r in records if r['candidate']]
        unique = set((r['code'], r['period'], r['path'], r['trend_dir'],
                      r['b_span'][0]) for r in hits)
        summary[period] = dict(completed=len(records), hits=len(hits),
                               unique_hits=len(unique))
        all_completed.extend(records)
        all_hits.extend(hits)
    total_unique = set((r['code'], r['period'], r['path'], r['trend_dir'],
                        r['b_span'][0]) for r in all_hits)
    result = dict(
        schema_version='chan-real-first-point-discovery-v1',
        version='0.9.9',
        annotation='first_point_completed_strict_trend_scan',
        independent_labels_frozen=False, theoretical_acceptance=False,
        core_version=chan.__version__,
        generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        dataset=str(dataset),
        manifest_sha256=digest(dataset / 'manifest.json'),
        pipeline='原始bar→chan_fx_bi106→bis[:-1]固定笔→find_xds(fixed)仅complete→'
                 'zn_run_v3/scan_strict_v3完成严格趋势(0.9.3最后中枢离开冻结)→'
                 'MACD(12,26,9)面积/新极值/零轴回拉',
        verdict_criteria=[
            '完成严格趋势(0.9.3冻结口径): A闭合+b离开+gap>0+B离开冻结+c离开+proof=c+1自外侧回核心',
            '背驰=0<area_c<area_b(课24行31-33; b/c单元同方向柱正幅值和, 区间(start,end])',
            '新极值=c创全趋势新极值(先验极值=a或A首Zn成员..B.zn[-1]单元范围)',
            'candidate=完成+背驰+新极值; 零轴回拉max(|DIF|,|DEA|)/close仅登记(课24不绝对精确)',
        ],
        discovery_grid='十标的因子恒1区间各月1日自然起点; 窗口终点为起点后1..%d个月首日, '
                       '最少60行; 1d/60m/30m全分区, 5m为2026分区; '
                       '分钟粒度截到%s前干净边界(0.9.6供应末端裁定); '
                       '不移动自然起点, 无窗口前暖机, 不复制镜像' % (
                           args.max_months, args.minute_cap),
        unique_key='(code, period, path, trend_dir, b单元起点)',
        summary=summary,
        completed=all_completed,
        hits=all_hits,
        conclusion='')
    result['conclusion'] = (
        '所扫范围(1d/60m/30m全分区与5m 2026分区、bi/xd两路径、涨跌两方向)'
        '完成严格趋势=%d、候选hits=%d、唯一成立趋势=%d(按%s去重); '
        '扫描仅作发现, 不产生独立真值; 成立/不成立由人工表冻结后经编译器'
        '与测试验收, 不调宽门槛、不移动起点或复制镜像补齐。' % (
            len(all_completed), len(all_hits), len(total_unique),
            result['unique_key']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                      allow_nan=False) + '\n')
    print(args.output.resolve())
    print(result['conclusion'])
    for period in args.periods:
        print(period, summary[period])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
