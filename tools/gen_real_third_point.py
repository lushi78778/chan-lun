# -*- coding: utf-8 -*-
"""编译三类买卖点真实正反例标注为核心测试fixture。

人工表声明四案例（T1-T4）的中枢zn/核心/包络与三类尝试台账（成立/
否决/pending）；编译器独立整数复算：重导基础链与人工expected_bis对比、
zn同向步2/首对核心/中间覆盖/延伸触沿/包络重推、closed_by与
frozen_by_departure状态算术、尝试台账几何重枚举逐项对比、pending
条件、逐原始bar前缀重放首确认与到达时刻。非法索引、算术冲突、
台账不一致直接拒绝；输出路径已存在即拒绝覆盖。

0.9.5：三类买卖点（课20定理三行77-80，行89-93第一次回试，课101
行7中枢破坏点）。zn规则：趋势末中枢沿用0.9.2-0.9.4离开冻结（课29
行20-26），无趋势上下文独立中枢按定理一全延伸；不导入chan，粒度
守卫与因子恒1同0.9.4。
0.9.8：xd级触沿（margin=0）成立样本；到达时刻口径扩至30m/5m（bar
结束+1分钟，同60m）。
"""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, records


def arrival_dt(row_dt, granularity):
    """到达时刻测试约定: 日线收盘日15:05; 分钟bar按结束时刻+1分钟。"""
    if granularity == 'day':
        return row_dt[:10] + ' 15:05:00'
    if granularity in ('60m', '30m', '5m'):
        stamp = datetime.strptime(row_dt, '%Y-%m-%d %H:%M:%S')
        return (stamp + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
    raise ValueError('不支持的粒度: ' + str(granularity))


def index(value):
    """人工坐标仅为非负整数；布尔值不是索引。"""
    if type(value) is not int or value < 0:
        raise ValueError('人工索引须为非负整数')
    return value


def validate_center(name, spec, units):
    """三类中枢算术: Zn同向步2、首对核心、中间覆盖、延伸触沿、
    包络与封口/冻结/开放状态全部重算并与声明比对（同0.9.4口径）。"""
    zn = [index(value) for value in spec['zn']]
    if len(zn) < 2:
        raise ValueError(name + ' Zn至少首对两成员')
    for i in range(1, len(zn)):
        if zn[i] != zn[i - 1] + 2:
            raise ValueError(name + ' Zn同向步2被破坏')
    if zn[-1] >= len(units):
        raise ValueError(name + ' Zn越界')
    direction = units[zn[0]]['direction']
    for i in zn:
        if units[i]['direction'] != direction:
            raise ValueError(name + ' Zn成员方向不一致')
    first, second = units[zn[0]], units[zn[1]]
    zd = max(first['low_ticks'], second['low_ticks'])
    zg = min(first['high_ticks'], second['high_ticks'])
    if zd > zg:
        raise ValueError(name + ' 首对核心为空')
    if [zd, zg] != [spec['zd'], spec['zg']]:
        raise ValueError(name + ' 首对核心与声明不一致')
    middle = units[zn[0] + 1]
    if middle['low_ticks'] > zd or middle['high_ticks'] < zg:
        raise ValueError(name + ' 中间单元未覆盖核心')
    for i in zn[2:]:
        unit = units[i]
        if unit['low_ticks'] > zg or unit['high_ticks'] < zd:
            raise ValueError(name + ' 延伸单元未触沿: ' + str(i))
    span = units[zn[0]:zn[-1] + 1]
    dd = min(unit['low_ticks'] for unit in span)
    gg = max(unit['high_ticks'] for unit in span)
    if [dd, gg] != [spec['dd'], spec['gg']]:
        raise ValueError(name + ' DD/GG包络与声明不一致')
    closed_by = spec['closed_by']
    frozen = spec.get('frozen_by_departure', False)
    if type(frozen) is not bool:
        raise ValueError(name + ' frozen_by_departure须为布尔')
    if closed_by is None:
        if frozen:
            if zn[-1] + 2 >= len(units):
                raise ValueError(name + ' 离开冻结须中间反向单元与同向后继存在')
            mid = units[zn[-1] + 1]
            if mid['direction'] == direction:
                raise ValueError(name + ' 冻结判定单元须为反向')
            if direction == 'down':
                if mid['high_ticks'] <= zg:
                    raise ValueError(name + ' 冻结须中间反向单元离开核心')
            elif mid['low_ticks'] >= zd:
                raise ValueError(name + ' 冻结须中间反向单元离开核心')
            successor = units[zn[-1] + 2]
            if successor['direction'] != direction:
                raise ValueError(name + ' 冻结须同向后继存在（承重）')
            if successor['low_ticks'] > zg or successor['high_ticks'] < zd:
                raise ValueError(name + ' 冻结承重：同向后继须触沿（否则普通封口）')
        elif zn[-1] + 2 < len(units):
            raise ValueError(name + ' 同向后继存在，closed_by不得为null')
    else:
        if frozen:
            raise ValueError(name + ' frozen_by_departure与closed_by互斥')
        closed_by = index(closed_by)
        if closed_by != zn[-1] + 2 or closed_by >= len(units):
            raise ValueError(name + ' 封口单元须为zn[-1]+2且存在')
        unit = units[closed_by]
        if unit['low_ticks'] <= zg and unit['high_ticks'] >= zd:
            raise ValueError(name + ' 封口单元不得触沿')
    return dict(zn=zn, zd=zd, zg=zg, dd=dd, gg=gg, closed_by=closed_by,
                frozen_by_departure=frozen)


def enumerate_attempts(units, center):
    """三类尝试台账几何重枚举: 核心确立后非zn单元离开+紧邻反向回试;
    fail不跳过; 成立即闭环。返回值与人工声明逐项对比。"""
    zn = set(center['zn'])
    zd, zg = center['zd'], center['zg']
    out = []
    for i in range(center['zn'][1] + 1, len(units) - 1):
        if i in zn:
            continue
        leave, pull = units[i], units[i + 1]
        if leave['direction'] == pull['direction']:
            continue
        if not (leave['low_ticks'] <= zg and leave['high_ticks'] >= zd):
            continue
        if leave['direction'] == 'up':
            if leave['end_ticks'] <= zg:
                continue
            side = 'buy3'
            holds = pull['low_ticks'] >= zg
            margin = pull['low_ticks'] - zg
        else:
            if leave['end_ticks'] >= zd:
                continue
            side = 'sell3'
            holds = pull['high_ticks'] <= zd
            margin = zd - pull['high_ticks']
        out.append(dict(side=side, leave=i, pull=i + 1, holds=holds,
                        point_ticks=pull['end_ticks'],
                        margin_ticks=margin))
        if holds:
            break
    return out


def validate_attempts(name, center, units, declared):
    """人工尝试台账与几何重枚举逐项对比; pending条件独立校验。"""
    if not isinstance(declared, list) or not declared:
        raise ValueError(name + ' 尝试台账不得为空')
    pending = None
    completed = declared
    if declared[-1]['outcome'] == 'pending':
        pending = declared[-1]
        completed = declared[:-1]
    enumerated = enumerate_attempts(units, center)
    if len(enumerated) != len(completed):
        raise ValueError(name + ' 尝试条目数与重枚举不一致')
    previous_leave = -1
    for enum, spec in zip(enumerated, completed):
        if spec['outcome'] not in ('fail', 'established'):
            raise ValueError(name + ' 尝试结局无效')
        if (enum['side'], enum['leave'], enum['pull']) != \
                (spec['side'], index(spec['leave']), index(spec['pull'])):
            raise ValueError(name + ' 尝试单元与重枚举不一致')
        if spec['leave'] <= previous_leave:
            raise ValueError(name + ' 尝试leave须严格递增')
        previous_leave = spec['leave']
        if enum['pull'] != spec['leave'] + 1:
            raise ValueError(name + ' 回试须紧随离开单元')
        if (enum['holds'] != (spec['outcome'] == 'established')):
            raise ValueError(name + ' 结局与回试触沿算术不一致')
        if enum['point_ticks'] != spec['point_ticks'] or \
                enum['margin_ticks'] != spec['margin_ticks']:
            raise ValueError(name + ' 点位或margin与重枚举不一致')
        if enum['holds'] and enum['pull'] in set(center['zn']):
            raise ValueError(name + ' 成立回试不得为zn成员')
    if pending is not None:
        if enumerated and enumerated[-1]['holds']:
            raise ValueError(name + ' 已成立中枢不得再声明pending')
        leave = index(pending['leave'])
        if pending['pull'] is not None:
            raise ValueError(name + ' pending不得声明回试单元')
        if leave != len(units) - 1:
            raise ValueError(name + ' pending离开须为窗口末单元')
        unit = units[leave]
        if leave in set(center['zn']):
            raise ValueError(name + ' pending离开不得为zn成员')
        if not (unit['low_ticks'] <= center['zg'] and
                unit['high_ticks'] >= center['zd']):
            raise ValueError(name + ' pending离开未与核心重叠')
        if unit['direction'] == 'up':
            if pending['side'] != 'buy3' or \
                    unit['end_ticks'] <= center['zg']:
                raise ValueError(name + ' pending方向或越沿算术不一致')
        elif unit['direction'] == 'down':
            if pending['side'] != 'sell3' or \
                    unit['end_ticks'] >= center['zd']:
                raise ValueError(name + ' pending方向或越沿算术不一致')
        else:
            raise ValueError(name + ' pending方向无效')
        if 'point_ticks' in pending or 'margin_ticks' in pending:
            raise ValueError(name + ' pending不得声明点位或margin')
    return completed, pending


def validate_context_centers(case, units):
    """T3式上下文中枢: 声明单元连续、闭区间交集与声明一致且非空。"""
    context = case.get('context_centers') or []
    for spec in context:
        members = [index(value) for value in spec['units']]
        if len(members) < 3:
            raise ValueError('上下文中枢至少三单元')
        for i in range(1, len(members)):
            if members[i] != members[i - 1] + 1:
                raise ValueError('上下文中枢单元须连续')
        if members[-1] >= len(units):
            raise ValueError('上下文中枢越界')
        low = max(units[i]['low_ticks'] for i in members)
        high = min(units[i]['high_ticks'] for i in members)
        if [low, high] != [spec['low_ticks'], spec['high_ticks']]:
            raise ValueError('上下文中枢交集与声明不一致')
        if low > high:
            raise ValueError('上下文中枢交集为空')
    return context


def validate_xd_events(events, fixed):
    """冻结XD组成结构校验; 沿用0.9.4口径, gate算术不在此重推。"""
    next_start = None
    for event in events:
        a, z, mode, proof = event
        for value in (a, z, proof):
            index(value)
        if not (a + 2 <= z < proof < len(fixed)) or (z - a) % 2:
            raise ValueError('XD至少三交替笔，证明须晚于组成且存在')
        if mode not in (1, 2) or type(mode) is not int:
            raise ValueError('XD人工模式须为1或2')
        if next_start is not None and a != next_start:
            raise ValueError('XD人工组成须相邻衔接')
        next_start = z + 1
        first = fixed[a:a + 3]
        if max(unit['low_ticks'] for unit in first) > \
                min(unit['high_ticks'] for unit in first):
            raise ValueError('XD前三笔闭区间交集为空')
    return events


def check_adjacency(units):
    """共享端点与方向交替是全部角色算术的前提。"""
    for i in range(1, len(units)):
        if units[i]['start_index'] != units[i - 1]['end_index'] or \
                units[i]['start_ticks'] != units[i - 1]['end_ticks'] or \
                units[i]['direction'] == units[i - 1]['direction']:
            raise ValueError('单元邻接或交替被破坏: ' + str(i))


def xd_units(fixed, events):
    """按冻结事件装配完成XD单元。"""
    out = []
    for a, z, mode, proof in events:
        covered = fixed[a:z + 1]
        out.append(dict(start_index=covered[0]['start_index'],
                        end_index=covered[-1]['end_index'],
                        start_ticks=covered[0]['start_ticks'],
                        end_ticks=covered[-1]['end_ticks'],
                        low_ticks=min(unit['low_ticks'] for unit in covered),
                        high_ticks=max(unit['high_ticks'] for unit in covered),
                        start_dt=covered[0]['start_dt'],
                        end_dt=covered[-1]['end_dt'],
                        direction=covered[0]['direction'], mode=mode,
                        proof_bi=proof,
                        evidence_end_index=fixed[proof]['end_index'],
                        evidence_dt=fixed[proof]['end_dt']))
    return out


def replay_confirmations(rows, case, events):
    """逐原始bar前缀重放：固定链前缀稳定与单元/证明首确认。"""
    expected = case['expected_bis']
    proofs = [event[3] for event in events] if events else []
    fixed_total = len(expected) - 1
    bi_seen = [None] * fixed_total
    xd_seen = [None] * len(proofs)
    for count in range(1, len(rows) + 1):
        _, _, prefix_bis = foundation(rows[:count], case['standard'])
        prefix_records = records(prefix_bis)
        n_fixed = max(0, len(prefix_bis) - 1)
        if prefix_records[:n_fixed] != expected[:n_fixed]:
            raise ValueError('前缀固定链漂移: count=%d' % count)
        for i in range(n_fixed):
            if bi_seen[i] is None:
                bi_seen[i] = count
        for k, proof in enumerate(proofs):
            if xd_seen[k] is None and n_fixed > proof:
                xd_seen[k] = count
    if any(value is None for value in bi_seen) or \
            any(value is None for value in xd_seen):
        raise ValueError('存在未在前缀内确认的单元')
    return bi_seen, xd_seen


def compile_case(case, packet, packet_path):
    """全窗口中枢/尝试算术、逐前缀首确认与到达时刻一并冻结。"""
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
        events = validate_xd_events(case['xd_events'], fixed)
        units = xd_units(fixed, events)
    elif case['level'] == 'bi':
        units = fixed
    else:
        raise ValueError('标注层级无效')
    check_adjacency(units)
    centers = {}
    for name in ('A', 'B'):
        if name not in case['centers']:
            raise ValueError('三类标注须声明A与B两个中枢')
        centers[name] = validate_center(name, case['centers'][name], units)
    context = validate_context_centers(case, units)
    attempts = {}
    for name in ('A', 'B'):
        completed, pending = validate_attempts(
            name, centers[name], units, case['attempts'][name])
        attempts[name] = dict(completed=completed, pending=pending)
    bi_seen, xd_seen = replay_confirmations(rows, case, events)
    unit_seen = xd_seen if case['level'] == 'xd' else bi_seen
    for unit, count in zip(units, unit_seen):
        unit['confirmed_raw_count'] = count
        unit['confirmed_dt'] = arrival_dt(rows[count - 1]['dt'], granularity)
    attempts_out = {}
    for name in ('A', 'B'):
        entries = []
        for spec in attempts[name]['completed']:
            count = unit_seen[spec['pull']]
            entries.append(dict(side=spec['side'], leave=spec['leave'],
                                pull=spec['pull'], outcome=spec['outcome'],
                                point_ticks=spec['point_ticks'],
                                margin_ticks=spec['margin_ticks'],
                                first_raw_count=count,
                                first_dt=arrival_dt(
                                    rows[count - 1]['dt'], granularity)))
        pending = attempts[name]['pending']
        if pending is not None:
            count = unit_seen[pending['leave']]
            entries.append(dict(side=pending['side'], leave=pending['leave'],
                                pull=None, outcome='pending',
                                point_ticks=None, margin_ticks=None,
                                first_raw_count=count,
                                first_dt=arrival_dt(
                                    rows[count - 1]['dt'], granularity)))
        attempts_out[name] = entries
    foundation_out = dict(bis=records(bis), bis_confirmed_raw_count=bi_seen)
    if events:
        foundation_out['xd_events'] = events
    out = dict(id=case['id'], window_key=case['window_key'],
               standard=case['standard'], level=case['level'],
               sampling_rule=case['sampling_rule'], audit=case['audit'],
               raw_rows=rows,
               source=dict(packet=packet_path.name, sha256=digest(packet_path),
                           dataset_manifest_sha256=packet['manifest_sha256']),
               foundation=foundation_out, units=units,
               centers={name: centers[name] for name in ('A', 'B')},
               attempts=attempts_out)
    if context:
        out['context_centers'] = context
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
    result = dict(schema_version='chan-real-third-point-v1',
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
