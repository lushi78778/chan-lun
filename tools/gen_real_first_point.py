# -*- coding: utf-8 -*-
"""课17/20/24/27/29/106：R2 一类买卖点真实正反例标注编译。

本地开发工具，不导入chan。固定链、完成XD、严格趋势角色与台账
复用0.9.2-0.9.6冻结编译算术（gen_real_strict_trend），本工具不
重推已冻结的结构。新增一类裁定算术：MACD(12,26,9)固定EMA自窗口
首行起算，hist=(DIF-DEA)*2；面积=b/c单元同方向柱正幅值和，区间
(start,end]（课24行31-33）；新极值=c极值超越全趋势先验极值
（a或A首Zn成员..B.zn[-1]）；成立=完成严格趋势+0<area_c<area_b+
c创新极值；不成立二分no_divergence/no_new_extreme；零轴回拉
max(|DIF|,|DEA|)/close于B zn区间最小值仅记录性登记，不作裁定
门槛（课24明示MACD不绝对精确）。面积/零轴/极值与人工声明全精度
一致；裁定可见时刻=证明段单元首确认，first_raw_count按逐原始
bar前缀首次可见冻结。非法索引、角色冲突、前缀漂移、声明与复算
不一致直接拒绝。
"""
import argparse
import json
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, records
from gen_real_strict_trend import (arrival_dt, check_adjacency, derive_ledger,
                                   replay_confirmations, validate_roles,
                                   validate_xd_audit, validate_xd_events,
                                   xd_units)


def ema(values, n):
    """固定EMA: 首值种子values[0], k=2/(n+1); 不猜窗口前历史。"""
    out = [0.0] * len(values)
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def macd_tables(rows):
    """DIF/DEA/HIST按窗口首行固定EMA起算; 不导入chan。"""
    closes = [row['close'] for row in rows]
    fast, slow = ema(closes, 12), ema(closes, 26)
    dif = [a - b for a, b in zip(fast, slow)]
    dea = ema(dif, 9)
    hist = [(a - b) * 2.0 for a, b in zip(dif, dea)]
    return dif, dea, hist


def raw_index(rows, unit_dt, granularity, last=False):
    """单元端点映射原始行下标: 日线按日期, 分钟按完整bar标签。"""
    key = unit_dt if granularity != 'day' else unit_dt[:10]
    hits = [i for i, row in enumerate(rows)
            if (row['dt'] if granularity != 'day'
                else row['dt'][:10]) == key]
    if not hits:
        raise ValueError('单元端点不在原始行: ' + str(unit_dt))
    return hits[-1] if last else hits[0]


def derive_first_point(case, units, centers, rows, granularity, unit_seen,
                       dif, dea, hist):
    """一类裁定算术复算; 与人工声明全精度一致否则拒绝。"""
    roles = case['roles']
    trend = case['trend']
    declared = case['first_point']
    if trend['status'] != 'completed' or roles.get('proof') is None:
        raise ValueError('一类裁定仅施于完成严格趋势（证明段已确认）')
    up = trend['direction'] == 'up'
    sign = 1 if up else -1
    side = 'sell1' if up else 'buy1'
    if declared['side'] != side:
        raise ValueError('声明方向与趋势方向不一致')
    b_unit = roles['b']['unit']
    c_unit = roles['c']['unit']
    proof_unit = roles['proof']['unit']
    b, c = units[b_unit], units[c_unit]
    b0 = raw_index(rows, b['start_dt'], granularity)
    b1 = raw_index(rows, b['end_dt'], granularity, last=True)
    c0 = raw_index(rows, c['start_dt'], granularity)
    c1 = raw_index(rows, c['end_dt'], granularity, last=True)
    area_b = sum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
    area_c = sum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
    divergence = 0 < area_c < area_b
    trend_first = (roles['a']['unit'] if roles['a']
                   else centers['A']['zn'][0])
    prior = units[trend_first:centers['B']['zn'][-1] + 1]
    prior_ext = (max(u['high_ticks'] for u in prior) if up
                 else min(u['low_ticks'] for u in prior))
    c_ext = c['high_ticks'] if up else c['low_ticks']
    new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
    z0 = raw_index(rows, units[centers['B']['zn'][0]]['start_dt'], granularity)
    z1 = raw_index(rows, units[centers['B']['zn'][-1]]['end_dt'], granularity,
                   last=True)
    zero = min(max(abs(dif[i]), abs(dea[i])) / rows[i]['close']
               for i in range(z0, z1 + 1))
    if divergence and new_extreme:
        verdict, reason = 'established', None
    elif not divergence:
        verdict, reason = 'not_established', 'no_divergence'
    else:
        verdict, reason = 'not_established', 'no_new_extreme'
    if declared['verdict'] != verdict or declared['reason'] != reason:
        raise ValueError('声明裁定与复算不一致: ' + str(declared['verdict']))
    checks = (('area_b', area_b), ('area_c', area_c), ('zero_axis', zero),
              ('prior_extreme_ticks', prior_ext),
              ('c_extreme_ticks', c_ext), ('new_extreme', new_extreme))
    for name, value in checks:
        if declared[name] != value:
            raise ValueError('声明' + name + '与复算不一致: ' +
                             str(declared[name]) + ' != ' + str(value))
    count = unit_seen[proof_unit]
    return dict(side=side, verdict=verdict, reason=reason,
                b_unit=b_unit, c_unit=c_unit, proof_unit=proof_unit,
                trend_first_unit=trend_first,
                prior_extreme_ticks=prior_ext, c_extreme_ticks=c_ext,
                new_extreme=new_extreme, area_b=area_b, area_c=area_c,
                zero_axis=zero, b_span_raw=[b0, b1], c_span_raw=[c0, c1],
                zero_span_raw=[z0, z1], first_raw_count=count,
                first_dt=arrival_dt(rows[count - 1]['dt'], granularity))


def compile_case(case, packet, packet_path):
    """全窗口结构、严格趋势与一类裁定算术一并复算冻结。"""
    rows = packet['rows']
    granularity = case.get('granularity', 'day')
    dt_slice = 10 if granularity == 'day' else None
    nonzero = [row['dt'][11:] != '00:00:00' for row in rows]
    if granularity == 'day':
        if any(nonzero):
            raise ValueError('day粒度原始行含非零时刻，粒度声明与行情不符')
    elif any(not value for value in nonzero):
        raise ValueError('分钟粒度原始行须为非零时刻bar标签')
    if any(row['adj_factor'] != 1 for row in rows):
        raise ValueError('本轮整数标注仅接受因子恒为1，不修价或补因子')
    _, _, bis = foundation(rows, case['standard'])
    if records(bis) != case['expected_bis']:
        raise ValueError('独立复算笔与人工全链records不一致')
    fixed = components(rows, bis[:-1], dt_slice)
    events = []
    if case['level'] == 'xd':
        events = validate_xd_events(case, fixed)
        validate_xd_audit(case)
        units = xd_units(fixed, events)
    elif case['level'] == 'bi':
        units = fixed
    else:
        raise ValueError('标注层级无效')
    check_adjacency(units)
    centers = validate_roles(case, units)
    if derive_ledger(case['roles'], centers) != case['ledger']:
        raise ValueError('台账事件序列与角色推导不一致')
    bi_seen, xd_seen = replay_confirmations(rows, case, events)
    unit_seen = xd_seen if case['level'] == 'xd' else bi_seen
    for unit, count in zip(units, unit_seen):
        unit['confirmed_raw_count'] = count
        unit['confirmed_dt'] = arrival_dt(rows[count - 1]['dt'], granularity)
    ledger = []
    for name, unit in case['ledger']:
        count = unit_seen[unit]
        ledger.append(dict(event=name, unit=unit, first_raw_count=count,
                           first_dt=arrival_dt(rows[count - 1]['dt'],
                                               granularity)))
    dif, dea, hist = macd_tables(rows)
    first_point = derive_first_point(case, units, centers, rows, granularity,
                                     unit_seen, dif, dea, hist)
    foundation_out = dict(bis=records(bis), bis_confirmed_raw_count=bi_seen)
    if events:
        foundation_out['xd_events'] = events
    out = dict(id=case['id'], window_key=case['window_key'],
               standard=case['standard'], level=case['level'],
               trend=case['trend'], raw_rows=rows,
               source=dict(packet=packet_path.name, sha256=digest(packet_path),
                           dataset_manifest_sha256=packet['manifest_sha256']),
               foundation=foundation_out, units=units,
               roles=case['roles'], ledger=ledger, first_point=first_point)
    if granularity != 'day':
        out['granularity'] = granularity
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', type=Path, required=True)
    parser.add_argument('--packets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('拒绝覆盖冻结fixture，使用新输出路径')
    manual = json.loads(args.manual.read_text())
    cases = []
    for case in manual['cases']:
        packet = (args.packets / case['packet']).resolve()
        if digest(packet) != case['packet_sha256']:
            raise ValueError('人工表原始包摘要漂移')
        cases.append(compile_case(case, json.loads(packet.read_text()), packet))
    result = dict(schema_version='chan-real-first-point-v1',
                  version=manual['version'], manual_sha256=digest(args.manual),
                  annotation=manual['annotation'],
                  minimum_rule=manual['minimum_rule'],
                  availability=manual['availability'], limits=manual['limits'],
                  cases=cases)
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
