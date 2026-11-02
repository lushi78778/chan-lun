# -*- coding: utf-8 -*-
"""0.9.3 严格两中枢趋势修正口径发现扫描（课20/29/33）。

发现工具，导入核心库计算笔/线段后按修正口径分类，不产出独立真值；
独立标注由 gen_real_strict_trend.py 的人工表另行冻结。

完成口径（课29，R1读法）：
- c 必须离开 B 核心区间（up: c 内存在 up 段 high > B.ZG；down 镜像）。
  课29原文行41-48"最后的背驰段，跌破该中枢后"；
- 证明段必须自外侧回到 B 核心（up: 其后 down 段 low <= B.ZG 且此前
  中间 down 段均 low > B.ZG，保证来自上方；down 镜像）。
  课29原文"反弹至少要重新触及最后一个中枢"；
- 0.9.3 修正：0.9.2 字面贪婪延伸在共享端点链上使证明段必被吸收
  （中间反向单元对延伸循环不可见），completed 结构性不可达；
  最后中枢 B 的 Zn 延伸在首个离开核心的中间反向单元处停止
  （课29行20-26：c 离开后最后中枢定界，返回段按转折证明分类）；
  前中枢 A 维持课20定理一字面延伸（离开-证明读法只针对最后中枢）；
- b 区/c 区禁任意方向三段重叠（第三中枢 => 非两中枢形态，课17）；
- 恰两中枢：A 不得同时是另一有效对的 B（否则为三中枢趋势后缀）；
- A 首Zn前三段不得重叠（A 不得是前一中枢的延伸段）。

分类：completed / ongoing(离开无证明) / no_departure / third_center_b
/ third_center_c / multi_center_prefix。

Zn 延伸用 <=/>= 闭区间触沿口径；中枢存在性=任意方向三连续次级走势
重叠（课17），与 Zn 方向约定无关；Zn 约定仅用于核心计算
（回调形成 Zn=down 段、回升形成 Zn=up 段）。

扫描范围（0.9.4 扩展，口径与 0.9.3 完全一致）：
- 1d/60m：单分区全历史，因子恒1区间内各年 1 月 1 日自然起点；
- 30m/15m/5m/1m：2026 分区，因子恒1区间内各月 1 日自然起点；
- 不移动自然起点、无窗口前暖机、不复制镜像；完成判定不随频率放宽。

R2 读法（课33"a和c并不是必然存在的"）为待判边界，本工具不裁一：
R2 下 completed 计数不增（c 离开+证明仍为必要），缺口如实登记。
"""

# 输入完整性与收据写入采用当前工程规则，分类/发现口径仍为上述冻结版本。

import argparse
import json
import math
from numbers import Real
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / 'src'

CODES = ['510300.SH', '510500.SH', '512880.SH', '512480.SH', '159915.SZ',
         '513100.SH', '518880.SH', '511010.SH', '588000.SH', '516160.SH']


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
    """分块计算分区摘要，不把完整大文件读入内存。"""
    import hashlib
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def read_discovery_partition(dataset, item, columns, codes, receipt=None):
    """所选Parquet解析前后均核manifest摘要，记录实际读入的分区。"""
    expected = item.get('sha256')
    if (not isinstance(expected, str) or len(expected) != 64 or
            any(c not in '0123456789abcdef' for c in expected.lower())):
        raise ValueError('发现分区缺少有效SHA-256: '+str(item.get('path')))
    path = Path(dataset) / item['path']
    actual = digest(path)
    if actual != expected.lower():
        raise ValueError('发现分区SHA-256不匹配，禁止解析: '+str(path))
    import pyarrow.parquet as pq
    table = pq.read_table(path, columns=columns, filters=[('ts_code', 'in', codes)])
    if digest(path) != actual:
        raise ValueError('发现分区在读取期间改变: '+str(path))
    if receipt is not None:
        receipt.append(dict(path=item['path'], partition=item.get('partition'), sha256=actual,
                            columns=list(columns), codes=list(codes), rows_read=table.num_rows))
    return table


def load_frames(dataset, period, codes, receipt=None):
    import pandas as pd
    manifest = json.loads((dataset / 'manifest.json').read_text())
    files = manifest['datasets'][period]['files']
    if period not in ('1d', '60m'):
        files = [i for i in files if i.get('partition') == '2026']
    if not files:
        raise ValueError('请求发现周期无所选分区，不能写成零候选: '+period)
    time_key = 'trade_date' if period == '1d' else 'trade_time'
    frames = []
    for item in files:
        columns = ['ts_code', time_key, 'open', 'high', 'low', 'close', 'vol', 'adj_factor']
        table = read_discovery_partition(dataset, item, columns, codes, receipt)
        frames.append(table.to_pandas())
    frame = pd.concat(frames, ignore_index=True)
    return {code: group.sort_values(time_key).reset_index(drop=True)
            for code, group in frame.groupby('ts_code')}, time_key



def _discovery_clock(group):
    """只读标的与时间元数据，不读取观察截止之后的OHLC/因子/量。"""
    import pandas as pd
    required = ('ts_code', 'open', 'high', 'low', 'close', 'vol', 'adj_factor')
    missing = [key for key in required if key not in group.columns]
    times = [key for key in ('trade_date', 'trade_time') if key in group.columns]
    if missing or len(times) != 1 or group.empty:
        raise ValueError('发现输入须为非空单标的行情，含一个时间列及完整字段: '+str(missing))
    codes = list(group['ts_code'])
    if any(not isinstance(v, str) or not v or v != v.strip() for v in codes) or len(set(codes)) != 1:
        raise ValueError('发现输入须为单一非空代码，不混标的')
    values = list(group[times[0]])
    if any(not isinstance(v, (str, date, datetime)) for v in values):
        raise ValueError('发现输入时间须为日期或时间，不接受数值标签')
    try:
        clock = pd.to_datetime(group[times[0]], errors='raise')
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('发现输入时间无效: '+str(error))
    if clock.isna().any() or clock.duplicated().any() or not clock.is_monotonic_increasing:
        raise ValueError('发现输入时间须完整、唯一且严格递增，不排序或去重')
    return clock


def discovery_before(group, time_key, before):
    """先验完整时序，再按声明的日期上界取前缀；不按行情好坏删行。"""
    clock = _discovery_clock(group)
    if time_key not in group.columns:
        raise ValueError('发现周期与时间字段不符')
    import pandas as pd
    cutoff = pd.Timestamp(before)
    if pd.isna(cutoff):
        raise ValueError('发现截止日期无效')
    return group.loc[clock < cutoff].copy().reset_index(drop=True)


def clean_rows(group):
    """验证观察窗原行，保留函数名但不删坏行拼接；零量和原因子保留。"""
    _discovery_clock(group)
    required = ('ts_code', 'open', 'high', 'low', 'close', 'vol', 'adj_factor')
    for key in required[1:]:
        for i, value in enumerate(group[key]):
            if (isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)
                    or (value < 0 if key == 'vol' else value <= 0)):
                raise ValueError('发现输入无效，禁止删行拼接: '+key+' row '+str(i))
    for i, row in enumerate(group[['open', 'high', 'low', 'close']].itertuples(index=False, name=None)):
        opening, high, low, close = row
        if not low <= min(opening, close) <= max(opening, close) <= high:
            raise ValueError('发现输入OHLC包络无效，禁止修价: row '+str(i))
    return group.copy().reset_index(drop=True)


def write_discovery_result(path, result):
    """先完成严格序列化，再排他创建收据；不覆盖已有文件或链接。"""
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(payload)


def factor_spans(group, time_key, min_rows=40):
    spans, start = [], None
    values = list(group['adj_factor'])
    keys = list(group[time_key])
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
    return [(s, e, str(keys[s])[:16], str(keys[e])[:16]) for s, e in spans]


def month_starts(first, last):
    out = []
    year, month = int(first[:4]), int(first[5:7])
    while True:
        key = '%04d-%02d-01' % (year, month)
        if key > last:
            break
        if key >= first:
            out.append(key)
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def bars_of(group, time_key, s, e):
    bars = []
    keys = list(group[time_key])
    for i in range(s, e + 1):
        raw = str(keys[i])[:16]
        day = datetime.strptime(raw[:10], '%Y-%m-%d')
        if len(raw) > 10:
            day = datetime.strptime(raw, '%Y-%m-%d %H:%M')
        bars.append(dict(dt=day, open=float(group['open'][i]),
                         high=float(group['high'][i]), low=float(group['low'][i]),
                         close=float(group['close'][i]), volume=float(group['vol'][i])))
    return bars


def zn_run(units, s, zdir, stop_on_departure=False):
    """课20 Zn：首对同向段定 ZD/ZG；同向候选闭区间触沿延伸。

    0.9.3：stop_on_departure=True（仅用于最后中枢 B）时，中间反向单元
    离开核心（up: mid.high>ZG; down: mid.low<ZD）即停止延伸——课29
    将 c 离开后的最后中枢视为定界对象（行20-26），离开后的返回段按
    转折证明分类，不再吸收为 Zn。前中枢 A 维持定理一字面延伸
    （课29 的离开-证明读法只针对趋势"最后一个中枢"）。
    """
    if units[s].direction != zdir or s + 2 >= len(units):
        return None
    if units[s + 2].direction != zdir:
        return None
    zd = max(units[s].low, units[s + 2].low)
    zg = min(units[s].high, units[s + 2].high)
    if zd > zg:
        return None
    zn = [s, s + 2]
    last = s + 2
    trend_dir = 'up' if zdir == 'down' else 'down'
    while last + 2 < len(units) and units[last + 2].direction == zdir:
        if stop_on_departure:
            mid = units[last + 1]
            if (trend_dir == 'up' and mid.high > zg) or \
                    (trend_dir == 'down' and mid.low < zd):
                break
        cand = units[last + 2]
        if cand.low <= zg and cand.high >= zd:
            zn.append(last + 2)
            last += 2
        else:
            break
    return dict(zn=zn, span=(s, last), zd=zd, zg=zg,
                gg=max(units[i].high for i in zn),
                dd=min(units[i].low for i in zn))


def triple_overlap(units, lo, hi):
    """[lo,hi] 内首个任意方向三段重叠；闭区间触沿算重叠。"""
    for i in range(lo, min(hi, len(units) - 1) - 1):
        u1, u2, u3 = units[i], units[i + 1], units[i + 2]
        zd = max(u1.low, u2.low, u3.low)
        zg = min(u1.high, u2.high, u3.high)
        if zd <= zg:
            kind = 'strict' if zd < zg else 'touch'
            return (kind, zd, zg, [i, i + 1, i + 2])
    return None


def scan_strict(units):
    """修正口径扫描；返回候选列表（含分类），不含恰两中枢后缀过滤。"""
    n = len(units)
    found = []
    for s in range(n):
        if s + 5 >= n:
            break
        zdir = units[s].direction
        trend_dir = 'up' if zdir == 'down' else 'down'
        if s > 0:
            p0, p1, p2 = units[s - 1], units[s], units[s + 1]
            if max(p0.low, p1.low, p2.low) <= min(p0.high, p1.high, p2.high):
                continue
        a_run = zn_run(units, s, zdir)
        if a_run is None:
            continue
        m = a_run['span'][1]
        # b 推进：至 B 首个 Zn；途中同向段不得触回 A 核心。
        bs = m + 2
        while bs < n - 2:
            if units[bs].direction != zdir:
                bs += 1
                continue
            if units[bs].low <= a_run['zg'] and units[bs].high >= a_run['zd']:
                break
            if zn_run(units, bs, zdir) is not None:
                break
            bs += 2
        else:
            continue
        if bs >= n - 2:
            continue
        b_run = zn_run(units, bs, zdir, stop_on_departure=True)
        if b_run is None:
            continue
        gap = (b_run['dd'] - a_run['gg']) if trend_dir == 'up' \
            else (a_run['dd'] - b_run['gg'])
        if gap <= 0:
            continue
        b_first = b_run['zn'][0]
        base = dict(s=s, trend_dir=trend_dir, a_run=a_run, b_run=b_run,
                    gap=gap, b_units=list(range(m + 1, b_first)))
        tb = triple_overlap(units, m + 1, b_first - 1)
        if tb is not None:
            base['status'] = 'third_center_b'
            base['triple'] = tb
            found.append(base)
            continue
        mb = b_run['span'][1]
        departed = False
        dep_idx = None
        proof = None
        proof_idx = None
        i = mb + 1
        while i < n:
            u = units[i]
            if u.direction == trend_dir:
                if trend_dir == 'up' and u.high > b_run['zg']:
                    departed = True
                    if dep_idx is None:
                        dep_idx = i
                if trend_dir == 'down' and u.low < b_run['zd']:
                    departed = True
                    if dep_idx is None:
                        dep_idx = i
                if not departed:
                    # 未离开核心即回落：非完成形态（课29 c 须跌破/升破核心）。
                    base['status'] = 'no_departure'
                    base['fail_idx'] = None
                    found.append(base)
                    break
            else:
                back = (u.low <= b_run['zg']) if trend_dir == 'up' \
                    else (u.high >= b_run['zd'])
                if back:
                    if departed:
                        proof, proof_idx = u, i
                    break
            if departed and proof is not None:
                break
            i += 1
        else:
            if base.get('status') is None:
                base['status'] = 'ongoing' if departed else 'no_departure'
                base['dep_idx'] = dep_idx
                found.append(base)
            continue
        if base.get('status') is not None:
            continue
        if proof is None:
            base['status'] = 'ongoing' if departed else 'no_departure'
            base['dep_idx'] = dep_idx
            found.append(base)
            continue
        tc = triple_overlap(units, mb + 1, proof_idx - 1)
        base['dep_idx'] = dep_idx
        base['proof'] = proof_idx
        if tc is not None:
            base['status'] = 'third_center_c'
            base['triple'] = tc
        else:
            base['status'] = 'completed'
            base['c_units'] = list(range(mb + 1, proof_idx))
        found.append(base)
    return found


def unit_table(units):
    return [dict(i=i, direction=u.direction, start=str(u.start_dt)[:16],
                 end=str(u.end_dt)[:16], low=round(u.low, 4),
                 high=round(u.high, 4)) for i, u in enumerate(units)]


def pattern_table(pattern, units):
    """候选证据表；浮点仅用于展示，冻结判定以整数标注为准。"""
    out = dict(status=pattern['status'], trend_dir=pattern['trend_dir'],
               a=dict(zn=pattern['a_run']['zn'], span=list(pattern['a_run']['span']),
                      zd=round(pattern['a_run']['zd'], 4), zg=round(pattern['a_run']['zg'], 4),
                      dd=round(pattern['a_run']['dd'], 4), gg=round(pattern['a_run']['gg'], 4)),
               b=dict(zn=pattern['b_run']['zn'], span=list(pattern['b_run']['span']),
                      zd=round(pattern['b_run']['zd'], 4), zg=round(pattern['b_run']['zg'], 4),
                      dd=round(pattern['b_run']['dd'], 4), gg=round(pattern['b_run']['gg'], 4)),
               gap=round(pattern['gap'], 4), b_units=pattern['b_units'])
    for key in ('dep_idx', 'proof', 'c_units', 'fail_idx'):
        if pattern.get(key) is not None:
            out[key] = pattern[key]
    if pattern.get('triple') is not None:
        kind, zd, zg, idx = pattern['triple']
        out['triple'] = dict(kind=kind, zd=round(zd, 4), zg=round(zg, 4), units=idx)
    return out


def yearly_starts(first, last):
    return ['%04d-01-01' % y for y in range(int(first[:4]), int(last[:4]) + 2)
            if first <= '%04d-01-01' % y <= last]


def main():
    known_periods = ('1d', '60m', '30m', '15m', '5m', '1m')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--codes', nargs='+', default=CODES)
    parser.add_argument('--periods', nargs='+', default=['1d', '30m'])
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('拒绝覆盖已归档发现输出；请使用新文件名')
    for period in args.periods:
        if period not in known_periods:
            parser.error('未知周期: ' + period)
    chan = import_chan()
    dataset = args.dataset.resolve()
    manifest = json.loads((dataset / 'manifest.json').read_text())
    missing = [p for p in args.periods if p not in manifest['datasets']]
    if missing:
        parser.error('请求周期缺少数据，不能写成零候选: '+str(missing))
    periods = [p for p in known_periods
               if p in args.periods and p in manifest['datasets']]
    out = dict((p, []) for p in periods)
    file_receipts = []
    for period in periods:
        frames, time_key = load_frames(dataset, period, args.codes, file_receipts)
        for code in args.codes:
            group = clean_rows(frames[code])
            starts_fn = yearly_starts if period in ('1d', '60m') \
                else month_starts
            for s, e, first_key, last_key in factor_spans(group, time_key):
                for start_key in starts_fn(first_key, last_key):
                    keys = [str(v)[:16] for v in group[time_key]]
                    s0 = s
                    while s0 <= e and keys[s0] < start_key:
                        s0 += 1
                    if s0 > e or e - s0 + 1 < 60:
                        continue
                    bars = bars_of(group, time_key, s0, e)
                    _, _, bis = chan.chan_fx_bi(bars, standard='106')
                    fixed = bis[:-1]
                    xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                    for path, units in (('xd', xds), ('bi', fixed)):
                        for item in scan_strict(units):
                            out[period].append(dict(
                                code=code, path=path, start=start_key,
                                span_end=keys[e], rows=e - s0 + 1,
                                n_units=len(units), pattern=item,
                                units=unit_table(units)))
    result = dict(
        schema_version='chan-real-strict-trend-discovery-v1', version='0.9.4',
        annotation='post_departure_freeze_scan_minute_extension',
        independent_labels_frozen=False, theoretical_acceptance=False,
        core_version=chan.__version__,
        input_quality='selected observation rows; no invalid-row deletion, repair or deduplication',
        invalid_rows_dropped=0,
        generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        dataset=str(dataset),
        manifest_sha256=digest(dataset / 'manifest.json'),
        input_files=file_receipts,
        pipeline='原始bar→chan_fx_bi106→bis[:-1]固定笔→find_xds(fixed)仅complete→'
                 'zn_run/triple_overlap/scan_strict修正口径(0.9.3最后中枢离开冻结)',
        completion_criteria=[
            'c离开B核心(up: c内up段high>B.ZG; down: c内down段low<B.ZD); 课29行41-48',
            '证明段自外侧回B核心(课29"反弹至少要重新触及最后一个中枢")',
            '0.9.3: 最后中枢B的Zn延伸在首个离开核心的中间反向单元处停止'
            '(up: mid.high>B.ZG; down: mid.low<B.ZD; 课29行20-26离开后最后中枢定界)',
            '前中枢A维持课20定理一字面延伸(课29离开-证明读法只针对最后中枢)',
            'b区/c区禁任意方向三段重叠(课17三连续次级走势重叠即中枢)',
            '恰两中枢: A首Zn前三段不重叠; A不得为另一有效对的B',
            'Zn延伸闭区间触沿(<=/>=); ZD/ZG由首对同向段固定',
        ],
        readings=dict(
            r1='a+A+b+B+c完整角色+转折证明=完成严格趋势; 课29行14-26/41-48',
            r2='课33行46"a和c并不是必然存在的"c可缺; 待判边界, 不强行裁一',
            note='R2下completed计数不增: c离开+证明仍为必要条件'),
        discovery_grid='十标的因子恒1区间自然起点(1d/60m为各年1月1日, '
                       '30m/15m/5m/1m为2026分区内各月1日), '
                       '至区间末端或供应末端; 不移动自然起点, 无窗口前暖机',
        candidates={}, summary={}, conclusion='')
    for period in periods:
        seen = {}
        unique = []
        for rec in out[period]:
            p = rec['pattern']
            u = rec['units']
            sig = (rec['code'], rec['path'], p['trend_dir'],
                   u[p['a_run']['zn'][0]]['start'],
                   u[p['b_run']['zn'][-1]]['end'])
            if sig in seen:
                continue
            seen[sig] = rec
            unique.append(dict(
                code=rec['code'], path=rec['path'], start=rec['start'],
                span_end=rec['span_end'], rows=rec['rows'],
                n_units=rec['n_units'],
                windows=sorted(set(r['start'] for r in out[period]
                                   if (r['code'], r['path'], r['pattern']['trend_dir'],
                                       r['units'][r['pattern']['a_run']['zn'][0]]['start'],
                                       r['units'][r['pattern']['b_run']['zn'][-1]]['end']) == sig)),
                pattern=pattern_table(p, u), units=rec['units']))
        result['candidates'][period] = sorted(
            unique, key=lambda r: (r['pattern']['status'], r['code'], r['path'],
                                   r['pattern']['trend_dir'], r['start']))
        result['summary'][period] = dict(
            total_records=len(out[period]), unique_candidates=len(unique),
            by_status=dict((status, sum(1 for r in unique
                                        if r['pattern']['status'] == status))
                           for status in ('completed', 'ongoing', 'no_departure',
                                          'third_center_b', 'third_center_c')))
    completed = sum(result['summary'][p]['by_status']['completed'] for p in result['summary'])
    result['conclusion'] = (
        '修正完成口径下所扫范围(各周期、bi/xd两路径、涨跌两方向)'
        '完成严格趋势计数=%d; 对该口径稳健(核心离开已是最宽读法, 更严读法c.low<B.DD只会更少), '
        '完成正例缺口如实登记, 不调宽门槛、不移动起点或复制镜像补齐。' % completed)
    write_discovery_result(args.output, result)
    print(args.output.resolve())
    print(result['conclusion'])
    for period in periods:
        print(period, result['summary'][period]['by_status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
