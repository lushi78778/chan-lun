# -*- coding: utf-8 -*-
"""课108：R2 因果底顶真实正反例标注编译。

本地开发工具，不导入chan。固定链、严格趋势角色、台账与一类裁定
复用0.9.9冻结编译算术（gen_real_first_point），本工具不重推已冻结
的结构。新增因果底顶算术（课108行2-6）：底部=第一类买点出现后至
该买点所引发的中枢第一次走出第三类买卖点前的构造过程，顶部反过
来定义；引发中枢=证明段起贪心运行的首个有效Zn（定理一全延伸，
一类点后无新趋势上下文），封闭不改变其身份；三类尝试沿用0.9.5
几何（gen_real_third_point.enumerate_attempts）：核心确立后非Zn
单元与核心闭区间重叠且端点越沿离开+紧邻反向回试，fail不跳过、
成立即止、触沿允许；结局映射：底×buy3=completed、底×sell3=
failed、顶×sell3=completed、顶×buy3=failed；可见=回试单元首
确认，first_raw_count按逐原始bar前缀首次可见冻结；构造区间=
[一类点可见, 三类回试首确认]；前提为一类买卖点成立。非法索引、
前缀漂移、声明与复算不一致直接拒绝。
"""
import argparse
import json
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, records
from gen_real_strict_trend import (arrival_dt, check_adjacency, derive_ledger,
                                   replay_confirmations, validate_roles)
from gen_real_first_point import derive_first_point, macd_tables
from gen_real_third_point import enumerate_attempts


def run_causal_zn(units, s):
    """引发中枢整数贪心运行: 定理一全延伸(allow_freeze=False口径)。"""
    n = len(units)
    if s + 2 >= n:
        return None
    zdir = units[s]['direction']
    if units[s + 2]['direction'] != zdir:
        return None
    zd = max(units[s]['low_ticks'], units[s + 2]['low_ticks'])
    zg = min(units[s]['high_ticks'], units[s + 2]['high_ticks'])
    if zd > zg:
        return None
    mid = units[s + 1]
    if mid['low_ticks'] > zd or mid['high_ticks'] < zg:
        return None
    zn = [s, s + 2]
    last = s + 2
    closed_by = None
    while True:
        succ_i = last + 2
        if succ_i >= n:
            break
        succ = units[succ_i]
        if not (succ['low_ticks'] <= zg and succ['high_ticks'] >= zd):
            closed_by = succ_i
            break
        zn.append(succ_i)
        last = succ_i
    span = units[s:zn[-1] + 1]
    return dict(zn=zn, zd=zd, zg=zg,
                dd=min(u['low_ticks'] for u in span),
                gg=max(u['high_ticks'] for u in span),
                closed_by=closed_by)


def index(value):
    """单元索引非负整数; 索引即坐标，不另设偏移。"""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError('单元索引无效: ' + str(value))
    return value


def derive_formation(case, units, centers, rows, granularity, unit_seen,
                     first_point):
    """因果底顶算术复算; 与人工声明全精度一致否则拒绝。"""
    trend = case['trend']
    declared = case['formation']
    up = trend['direction'] == 'up'
    kind = 'top' if up else 'bottom'
    if declared['kind'] != kind:
        raise ValueError('声明底顶类别与趋势方向不一致')
    if first_point['verdict'] != 'established':
        raise ValueError('因果底顶前提为一类买卖点成立（课108行2）')
    proof_unit = index(case['roles']['proof']['unit'])
    center = None
    for s in range(proof_unit, len(units) - 2):
        center = run_causal_zn(units, s)
        if center is not None:
            break
    if center is None:
        raise ValueError('证明段起未形成引发中枢')
    spec = declared['center']
    for name in ('zn', 'zd', 'zg', 'dd', 'gg', 'closed_by'):
        if spec[name] != center[name]:
            raise ValueError('引发中枢' + name + '与复算不一致: ' +
                             str(spec[name]) + ' != ' + str(center[name]))
    enumerated = enumerate_attempts(units, center)
    specs = declared['attempts']
    if not isinstance(specs, list) or not specs:
        raise ValueError('尝试台账不得为空')
    if len(enumerated) != len(specs):
        raise ValueError('尝试台账条目数与重枚举不一致')
    zn_set = set(center['zn'])
    attempts = []
    previous_leave = -1
    for enum, item in zip(enumerated, specs):
        if item['side'] not in ('buy3', 'sell3'):
            raise ValueError('尝试方向无效')
        if item['outcome'] not in ('fail', 'established'):
            raise ValueError('尝试结局无效')
        leave = index(item['leave'])
        pull = index(item['pull'])
        if (enum['side'], enum['leave'], enum['pull']) != \
                (item['side'], leave, pull):
            raise ValueError('尝试单元与重枚举不一致')
        if leave <= previous_leave:
            raise ValueError('尝试leave须严格递增')
        previous_leave = leave
        if pull != leave + 1:
            raise ValueError('回试须紧随离开单元')
        if enum['holds'] != (item['outcome'] == 'established'):
            raise ValueError('尝试结局与回试触沿算术不一致')
        if enum['point_ticks'] != item['point_ticks'] or \
                enum['margin_ticks'] != item['margin_ticks']:
            raise ValueError('尝试点位或margin与重枚举不一致')
        if enum['holds'] and pull in zn_set:
            raise ValueError('成立回试不得为zn成员')
        count = unit_seen[pull]
        attempts.append(dict(side=item['side'], leave=leave, pull=pull,
                             outcome=item['outcome'],
                             point_ticks=enum['point_ticks'],
                             margin_ticks=enum['margin_ticks'],
                             first_raw_count=count,
                             first_dt=arrival_dt(rows[count - 1]['dt'],
                                                 granularity)))
    if attempts[-1]['outcome'] != 'established':
        raise ValueError('本轮只冻结已裁定底顶：引发中枢首个三类点须在窗内成立')
    resolution = attempts[-1]
    if kind == 'bottom':
        outcome = 'completed' if resolution['side'] == 'buy3' else 'failed'
    else:
        outcome = 'completed' if resolution['side'] == 'sell3' else 'failed'
    if declared['outcome'] != outcome:
        raise ValueError('声明结局与三类点映射不一致（课108行4-6）')
    declared_res = declared['resolution']
    expected_res = dict(side=resolution['side'], unit=resolution['pull'],
                        leave=resolution['leave'],
                        point_ticks=resolution['point_ticks'],
                        margin_ticks=resolution['margin_ticks'])
    for name, value in expected_res.items():
        if declared_res[name] != value:
            raise ValueError('声明三类点' + name + '与复算不一致: ' +
                             str(declared_res[name]) + ' != ' + str(value))
    open_unit = center['zn'][1]
    open_count = unit_seen[open_unit]
    return dict(kind=kind,
                center=dict(zn=center['zn'], zd=center['zd'],
                            zg=center['zg'], dd=center['dd'],
                            gg=center['gg'], closed_by=center['closed_by']),
                center_open_first_raw_count=open_count,
                center_open_first_dt=arrival_dt(rows[open_count - 1]['dt'],
                                                granularity),
                attempts=attempts,
                resolution=dict(expected_res,
                                first_raw_count=resolution['first_raw_count'],
                                first_dt=resolution['first_dt']),
                outcome=outcome,
                construction_interval=[first_point['first_dt'],
                                       resolution['first_dt']])


def compile_case(case, packet, packet_path):
    """全窗口结构、严格趋势、一类与因果底顶算术一并复算冻结。"""
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
    if case['level'] != 'bi':
        raise ValueError('本轮底顶标注仅验收bi级单元')
    units = fixed
    check_adjacency(units)
    centers = validate_roles(case, units)
    if derive_ledger(case['roles'], centers) != case['ledger']:
        raise ValueError('台账事件序列与角色推导不一致')
    bi_seen, _ = replay_confirmations(rows, case, [])
    unit_seen = bi_seen
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
    formation = derive_formation(case, units, centers, rows, granularity,
                                 unit_seen, first_point)
    out = dict(id=case['id'], window_key=case['window_key'],
               standard=case['standard'], level=case['level'],
               trend=case['trend'], raw_rows=rows,
               source=dict(packet=packet_path.name, sha256=digest(packet_path),
                           dataset_manifest_sha256=packet['manifest_sha256']),
               foundation=dict(bis=records(bis),
                               bis_confirmed_raw_count=bi_seen),
               units=units, roles=case['roles'], ledger=ledger,
               first_point=first_point, formation=formation)
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
    result = dict(schema_version='chan-real-causal-formation-v1',
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
