# -*- coding: utf-8 -*-
"""多轮真实窗口发现扫描（课24/81/101/106/108, 笔级）。

发现工具, 不导入chan, 不产出独立真值。固定笔链与逐前缀确认复用
R2冻结算术（gen_real_f1_originals.foundation, 默认106、显式可选81）; 完成严格
趋势检测沿用0.9.9冻结口径（scan_real_first_point.scan_strict_v3,
属性包装适配字典单元）; 一类候选面积/新极值/零轴口径同0.9.9; 引发
中枢与三类尝试沿用0.9.11冻结算术（gen_real_causal_formation.
run_causal_zn, gen_real_third_point.enumerate_attempts）。本工具
在单个原始包窗口内扫描: 完成严格趋势→一类候选→轮次链（同侧后继
移交、二类停发=min(构造终态,移交), 课101; 构造结局映射课108）。
扫描结果仅作候选发现与标注辅助, 独立标注由人工表另行冻结,
入选窗一律以窗内重跑冻结验证; 不以扫描输出冒充独立标签。

单元为笔（R2标注口径）, 单元索引即固定笔序号; 价格为0.001整数
ticks。first_raw_count按逐原始bar前缀首次可见冻结; 日线15:05到达
仅测试约定。构造允许constructing结局（引发中枢未形成或三类尝试
全部fail）, 与0.9.11只冻结已裁定底顶的编译口径互补。
标准同时用于全窗分笔和每个原始前缀, 不能只换最终笔链而沿用106确认。
仅接受完整且为正的恒定因子; 当行/末因子为1, 原价和原因子均保留。
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from numbers import Real
from pathlib import Path
from types import SimpleNamespace

from gen_real_f1_originals import components, foundation, records
from gen_real_first_point import macd_tables
from gen_real_strict_trend import arrival_dt, replay_confirmations
from gen_real_third_point import enumerate_attempts
from gen_real_causal_formation import run_causal_zn
from scan_real_first_point import scan_strict_v3


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_index(rows, unit_dt, granularity, last=False):
    """单元端点映射原始行下标; 同键多行时last取末次(端点闭合口径)。"""
    key = unit_dt if granularity != 'day' else unit_dt[:10]
    hits = []
    for i, row in enumerate(rows):
        if (row['dt'] if granularity != 'day'
                else row['dt'][:10]) == key:
            hits.append(i)
    if not hits:
        raise ValueError('单元端点不在原始行: ' + str(unit_dt))
    return hits[-1] if last else hits[0]


def wrapped(units):
    """0.9.9冻结扫描器的属性视图; 不复制其算术。"""
    return [SimpleNamespace(direction=u['direction'], low=u['low_ticks'],
                            high=u['high_ticks'], start_dt=u['start_dt'],
                            end_dt=u['end_dt']) for u in units]


def first_point_fields(item, units, rows, granularity, hist, dif, dea):
    """0.9.9一类候选口径: 面积/新极值/零轴; established=背驰+新极值。"""
    up = item['trend_dir'] == 'up'
    sign = 1 if up else -1
    b, c = item['b_units'][0], item['c_units'][0]
    b0 = raw_index(rows, units[b]['start_dt'], granularity)
    b1 = raw_index(rows, units[b]['end_dt'], granularity, last=True)
    c0 = raw_index(rows, units[c]['start_dt'], granularity)
    c1 = raw_index(rows, units[c]['end_dt'], granularity, last=True)
    area_b = math.fsum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
    area_c = math.fsum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
    trend_first = max(0, item['s'] - 1)
    prior = units[trend_first:item['b_run']['last'] + 1]
    if up:
        prior_ext = max(u['high_ticks'] for u in prior)
        c_ext = units[c]['high_ticks']
    else:
        prior_ext = min(u['low_ticks'] for u in prior)
        c_ext = units[c]['low_ticks']
    new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
    z0 = raw_index(rows, units[item['b_run']['zn'][0]]['start_dt'], granularity)
    z1 = raw_index(rows, units[item['b_run']['zn'][-1]]['end_dt'], granularity,
                   last=True)
    zero = min(max(abs(dif[i]), abs(dea[i])) / rows[i]['close']
               for i in range(z0, z1 + 1))
    divergence = 0 < area_c < area_b
    return dict(area_b=area_b, area_c=area_c, divergence=divergence,
                new_extreme=bool(new_extreme),
                prior_extreme_ticks=prior_ext, c_extreme_ticks=c_ext,
                zero_axis=zero,
                established=bool(divergence and new_extreme))


def formation_fields(units, proof_unit, up, unit_seen, rows, granularity):
    """0.9.11引发中枢与三类尝试口径; 允许constructing结局。"""
    center = None
    for s in range(proof_unit, len(units) - 2):
        center = run_causal_zn(units, s)
        if center is not None:
            break
    if center is None:
        return dict(kind='top' if up else 'bottom', center=None,
                    attempts=[], resolution=None, outcome='constructing')
    attempts = []
    for enum in enumerate_attempts(units, center):
        count = unit_seen[enum['pull']]
        attempts.append(dict(side=enum['side'], leave=enum['leave'],
                             pull=enum['pull'],
                             established=bool(enum['holds']),
                             point_ticks=enum['point_ticks'],
                             margin_ticks=enum['margin_ticks'],
                             first_raw_count=count,
                             first_dt=arrival_dt(rows[count - 1]['dt'],
                                                 granularity)))
    resolution = attempts[-1] if attempts and attempts[-1]['established'] else None
    if resolution is None:
        outcome = 'constructing'
    else:
        is_buy3 = resolution['side'] == 'buy3'
        outcome = ('completed' if (is_buy3 != up) else 'failed')
    return dict(kind='top' if up else 'bottom', center=center,
                attempts=attempts, resolution=resolution, outcome=outcome)


def constant_factor(rows):
    """仅接受正的恒定数值因子; 保留原值, 不把因子改成1。

    任一观察前缀的当行因子/末因子均精确等于1, 故原始价格坐标不变。
    因子缺失、非有限或变化均拒绝; 本检查不证明供应版本或原价真伪。
    """
    if not rows:
        raise ValueError('原始包为空')
    factors = [row.get('adj_factor') for row in rows]
    if any(isinstance(value, bool) or not isinstance(value, Real) or
           not math.isfinite(value) or value <= 0 for value in factors):
        raise ValueError('发现扫描要求完整、有限且为正的数值因子')
    if any(value != factors[0] for value in factors):
        raise ValueError('发现扫描仅接受恒因子窗口;变化因子须先独立冻结复权坐标')
    return factors[0]


def scan(packet, granularity='day', standard='106'):
    if standard not in ('81', '106'):
        raise ValueError('不支持的笔标准: ' + str(standard))
    rows = packet['rows']
    constant_factor(rows)
    groups, fxs, bis = foundation(rows, standard)
    fixed = components(rows, bis[:-1], 10 if granularity == 'day' else None)
    pseudo = dict(expected_bis=records(bis), standard=standard)
    bi_seen, _ = replay_confirmations(rows, pseudo, [])
    units = []
    for unit, count in zip(fixed, bi_seen):
        item = dict(unit)
        item['confirmed_raw_count'] = count
        item['confirmed_dt'] = arrival_dt(rows[count - 1]['dt'], granularity)
        units.append(item)
    dif, dea, hist = macd_tables(rows)
    completed = []
    for item in scan_strict_v3(wrapped(fixed)):
        if item['status'] != 'completed':
            continue
        entry = dict(s=item['s'], trend_dir=item['trend_dir'],
                     a_zn=item['a_run']['zn'], b_zn=item['b_run']['zn'],
                     b_units=item['b_units'], c_units=item['c_units'],
                     proof=item['proof'], gap=item['gap'])
        entry.update(first_point_fields(item, fixed, rows, granularity,
                                        hist, dif, dea))
        if not entry['established']:
            entry['exclusion'] = ('no_new_extreme' if not entry['new_extreme']
                                  else 'no_divergence')
        completed.append(entry)
    rounds = []
    for entry in completed:
        if not entry['established']:
            continue
        up = entry['trend_dir'] == 'up'
        proof_unit = entry['proof']
        count = bi_seen[proof_unit]
        rounds.append(dict(side='sell1' if up else 'buy1',
                           s=entry['s'], proof=proof_unit,
                           first_raw_count=count,
                           first_dt=arrival_dt(rows[count - 1]['dt'],
                                               granularity),
                           formation=formation_fields(
                               fixed, proof_unit, up, bi_seen, rows,
                               granularity),
                           trend=entry))
    rounds.sort(key=lambda r: r['first_dt'])
    for i, item in enumerate(rounds):
        handover = None
        for later in rounds[i + 1:]:
            if later['side'] == item['side']:
                handover = dict(to_candidate=later['s'],
                                first_raw_count=later['first_raw_count'],
                                first_dt=later['first_dt'])
                break
        item['handover'] = handover
        formation_end = (item['formation']['resolution']['first_dt']
                         if item['formation']['resolution'] else None)
        candidates = [v for v in (formation_end,
                                  handover['first_dt'] if handover else None)
                      if v is not None]
        item['second_cutoff'] = min(candidates) if candidates else None
        item['round'] = i + 1
    return dict(bis=records(bis), units=units, completed_trends=completed,
                rounds=rounds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--standard', choices=('81', '106'), default='106',
                        help='全窗及逐前缀使用同一笔标准; 默认保持106')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('拒绝覆盖已有扫描报告, 使用新输出路径')
    packet = json.loads(args.packet.read_text())
    period = packet['sampling_rule']['periods'][0]
    granularity = 'day' if period == '1d' else period
    if granularity not in ('day', '60m', '30m', '5m'):
        parser.error('不支持的原始包粒度: ' + str(period))
    result = scan(packet, granularity, args.standard)
    report = dict(schema_version='chan-real-rounds-scan-v1',
                  annotation='rounds_discovery_scan_not_labels',
                  standard=args.standard,
                  factor_coordinate=dict(source_factor=constant_factor(packet['rows']),
                      rule='constant positive factor;factor/final_factor=1;raw prices unchanged'),
                  generated_at=datetime.now(
                      timezone(timedelta(hours=8))).isoformat(),
                  packet=args.packet.name, packet_sha256=digest(args.packet),
                  window=packet['sampling_rule']['window'],
                  the_warning='扫描结果仅作候选发现, 不是独立标注; 独立'
                              '标注由人工表冻结后经编译器与测试验收。',
                  **result)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(args.output.resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
