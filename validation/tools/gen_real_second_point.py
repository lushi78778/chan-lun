# -*- coding: utf-8 -*-
"""课17/21/53/101：R2 二类买卖点真实正反例标注编译。

本地开发工具，不导入chan。固定链、完成XD、严格趋势角色、台账与
一类裁定复用0.9.9冻结编译算术（gen_real_first_point），本工具不
重推已冻结的结构。新增二类裁定算术：锚定极值=趋势域（a或A首Zn
成员..c单元）顺趋势极值，趋势域内首次触及单元为锚定单元，锚值
为其端点值时boundary、严格落在单元内部时interior（差距
interior_gap_ticks如实登记，不为凑边界调结构）；离开方向与趋势
相反，锚定单元方向与离开方向一致且锚值为其起点时腿1=锚定单元、
否则腿1=锚定单元之后首个单元，腿2=腿1后首个反向单元；二类买卖
点=腿2锚向极值（买取腿2低、卖取腿2高，课17:74-78/课101:9-12）；
三档（课101:13-24）：最弱=腿2破锚、最强=二三合一（买腿1高>B.zg
且腿2低>=B.zg、卖腿1低<B.zd且腿2高<=B.zd，触沿允许沿用
0.9.7/0.9.8，课21:57-59）、一般=之间；位置below/within/above相对
B核心仅登记（课21:51-53）；盘整背驰consolidation_divergence=
leg2_area<anchor_area（MACD口径同0.9.9，区间(start,end]）仅登记
不作门槛（课101:20"一般都"为倾向性表述）；可见=腿2单元首确认，
first_raw_count按逐原始bar前缀首次可见冻结；later_break登记腿2
后首个严格超越二类点极值的单元（课101:25-35），不改窗内裁定。
非法索引、角色冲突、前缀漂移、声明与复算不一致直接拒绝。
"""
import argparse
import json
import math
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, records
from gen_real_strict_trend import (arrival_dt, check_adjacency, derive_ledger,
                                   replay_confirmations, validate_roles,
                                   validate_xd_audit, validate_xd_events,
                                   xd_units)
from gen_real_first_point import derive_first_point, macd_tables, raw_index


def derive_second_point(case, units, centers, rows, granularity, hist,
                        unit_seen, first_point):
    """二类裁定算术复算; 与人工声明全精度一致否则拒绝。"""
    roles = case['roles']
    trend = case['trend']
    declared = case['second_point']
    up = trend['direction'] == 'up'
    side = 'sell2' if up else 'buy2'
    if declared['side'] != side:
        raise ValueError('声明方向与趋势方向不一致')
    sign = 1 if up else -1
    leave = 'down' if up else 'up'
    trend_first = (roles['a']['unit'] if roles['a']
                   else centers['A']['zn'][0])
    c_unit = roles['c']['unit']
    domain = units[trend_first:c_unit + 1]
    anchor_val = (max(u['high_ticks'] for u in domain) if up
                  else min(u['low_ticks'] for u in domain))
    k = trend_first
    while ((units[k]['high_ticks'] if up else units[k]['low_ticks'])
           != anchor_val):
        k += 1
    anchor_unit = units[k]
    boundary = anchor_val in (anchor_unit['start_ticks'],
                              anchor_unit['end_ticks'])
    anchor_kind = 'boundary' if boundary else 'interior'
    if (anchor_unit['direction'] == leave
            and anchor_unit['start_ticks'] == anchor_val):
        leg1 = k
    else:
        leg1 = k + 1
    leg2 = leg1 + 1
    if leg2 >= len(units):
        raise ValueError('腿2越界: 窗口过短')
    l1, l2 = units[leg1], units[leg2]
    second_ext = l2['high_ticks'] if up else l2['low_ticks']
    broke = second_ext > anchor_val if up else second_ext < anchor_val
    zd, zg = centers['B']['zd'], centers['B']['zg']
    if broke:
        tier = 'weakest'
    elif up:
        tier = ('strongest' if second_ext <= zd and l1['low_ticks'] < zd
                else 'ordinary')
    else:
        tier = ('strongest' if second_ext >= zg and l1['high_ticks'] > zg
                else 'ordinary')
    position = ('below' if second_ext < zd
                else 'within' if second_ext <= zg else 'above')

    def area(unit):
        a0 = raw_index(rows, unit['start_dt'], granularity)
        a1 = raw_index(rows, unit['end_dt'], granularity, last=True)
        return (math.fsum(max(sign * v, 0.0) for v in hist[a0 + 1:a1 + 1]),
                (a0, a1))

    anchor_area, anchor_span_raw = area(anchor_unit)
    leg2_area, leg2_span_raw = area(l2)
    consolidation_divergence = leg2_area < anchor_area
    later_break = None
    for j in range(leg2 + 1, len(units)):
        hit = ((units[j]['high_ticks'] > second_ext) if up
               else (units[j]['low_ticks'] < second_ext))
        if hit:
            later_break = dict(
                unit=j,
                extreme_ticks=(units[j]['high_ticks'] if up
                               else units[j]['low_ticks']))
            break
    interior_gap = (None if boundary
                    else (anchor_val - l1['start_ticks'] if up
                          else l1['start_ticks'] - anchor_val))
    if first_point['verdict'] == 'established':
        category = 'standard'
    else:
        category = 'minor_to_major'
    checks = (('anchor_unit', k), ('anchor_kind', anchor_kind),
              ('anchor_ticks', anchor_val),
              ('interior_gap_ticks', interior_gap),
              ('leg1', leg1), ('leg2', leg2),
              ('second_extreme_ticks', second_ext),
              ('broke_anchor', broke), ('tier', tier),
              ('position', position), ('anchor_area', anchor_area),
              ('leg2_area', leg2_area),
              ('consolidation_divergence', consolidation_divergence),
              ('later_break', later_break))
    for name, value in checks:
        if declared.get(name) != value:
            raise ValueError('声明' + name + '与复算不一致: ' +
                             str(declared.get(name)) + ' != ' + str(value))
    count = unit_seen[leg2]
    return dict(side=side,
                premise=dict(first_verdict=first_point['verdict'],
                             first_reason=first_point['reason'],
                             category=category),
                anchor_unit=k, anchor_kind=anchor_kind,
                anchor_ticks=anchor_val,
                anchor_span=[anchor_unit['start_dt'],
                             anchor_unit['end_dt']],
                interior_gap_ticks=interior_gap,
                leg1=leg1, leg2=leg2,
                leg1_span=[l1['start_dt'], l1['end_dt']],
                leg2_span=[l2['start_dt'], l2['end_dt']],
                second_extreme_ticks=second_ext, broke_anchor=broke,
                tier=tier, position=position,
                anchor_area=anchor_area, leg2_area=leg2_area,
                consolidation_divergence=consolidation_divergence,
                anchor_span_raw=list(anchor_span_raw),
                leg2_span_raw=list(leg2_span_raw),
                later_break=later_break,
                leg2_confirmed_raw_count=count,
                leg2_confirmed_dt=arrival_dt(rows[count - 1]['dt'],
                                             granularity),
                leg2_visible_in_window=count <= len(rows))


def compile_case(case, packet, packet_path):
    """全窗口结构、严格趋势、一类与二类裁定算术一并复算冻结。"""
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
    second_point = derive_second_point(case, units, centers, rows,
                                       granularity, hist, unit_seen,
                                       first_point)
    foundation_out = dict(bis=records(bis), bis_confirmed_raw_count=bi_seen)
    if events:
        foundation_out['xd_events'] = events
    out = dict(id=case['id'], window_key=case['window_key'],
               standard=case['standard'], level=case['level'],
               trend=case['trend'], raw_rows=rows,
               source=dict(packet=packet_path.name, sha256=digest(packet_path),
                           dataset_manifest_sha256=packet['manifest_sha256']),
               foundation=foundation_out, units=units,
               roles=case['roles'], ledger=ledger,
               first_point=first_point, second_point=second_point)
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
    result = dict(schema_version='chan-real-second-point-v1',
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
