# -*- coding: utf-8 -*-
"""课17/20/29/33/106：R2 严格趋势 Zn 与 a+A+b+B+c 完整角色标注编译。

本地开发工具，不导入chan。基础包含、分型及笔复用独立整数参考；
XD组成、模式与证明笔来自已冻结人工表，本工具不重推gate算术
（该正确性由核心测试逐前缀回放find_xds恰好复现冻结事件保证）。
Zn取中枢形成方向同向单元；默认ZD/ZG由首对同向段固定；存在性=三连续
单元重叠；延伸=闭区间与[ZD,ZG]触沿；DD/GG为zn[0]..zn[-1]全单元
包络；c离开最后中枢核心才算departed，B+c扩展按a~+A~未完成延续
登记。0.9.3：完成正例要求最后中枢B在c离开处冻结Zn延伸
（frozen_by_departure与closed_by互斥），证明段紧随c立即自外侧
回触核心（延迟回核心被第三中枢阻断，结构性不可达），台账增
proof_fixed事件。台账事件序列由角色推导比对，first_raw_count按
逐原始日前缀首次可见冻结。非法索引、空交集、越界证明与角色
算术冲突直接拒绝。0.9.4：granularity='60m'时单元时刻保留完整
bar结束时刻、到达时刻按+1分钟约定，日线路径保持15:05不变。
0.9.6：granularity='5m'沿用分钟约定（bar结束时刻+1分钟）。

新角色可显式声明core_basis='three_units'，按课20三段全程区间交集
固定ZD/ZG；其余Zn成员、包络及封口规则保持。默认same_direction_pair
保留历史表的首对简化式及中间全覆盖检查，不重算或改写冻结标签。
XD内部极值使中间段不能覆盖首对交集时，两种口径不得互换。
"""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, records


def arrival_dt(row_dt, granularity):
    """到达时刻测试约定: 日线收盘日15:05; 分钟粒度按bar结束时刻+1分钟。"""
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


def validate_zhongshu(name, spec, units):
    """Zn同向步2、声明口径的核心、存在性、延伸触沿、包络与封口算术。

    0.9.3：frozen_by_departure=true时closed_by须为null，zn[-1]+1
    中间反向单元须离开核心（趋势方向判据），zn[-1]+2同向后继须
    存在且触沿（冻结承重：否则普通封口规则已适用）；二者互斥。
    冻结承重使0.9.2字面延伸吸收证明段（如zn=[4,6,8]）不可复现，
    课29行20-26离开后最后中枢定界。
    """
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
    basis = spec.get('core_basis', 'same_direction_pair')
    if basis not in ('same_direction_pair', 'three_units'):
        raise ValueError(name + ' core_basis无效')
    formation = ([first, units[zn[0] + 1], second]
                 if basis == 'three_units' else [first, second])
    zd = max(unit['low_ticks'] for unit in formation)
    zg = min(unit['high_ticks'] for unit in formation)
    if zd > zg:
        raise ValueError(name + (' 三段核心为空' if basis == 'three_units'
                                 else ' 首对核心为空'))
    if [zd, zg] != [spec['zd'], spec['zg']]:
        raise ValueError(name + (' 三段核心与声明不一致' if basis == 'three_units'
                                 else ' 首对核心与声明不一致'))
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
    result = dict(zn=zn, zd=zd, zg=zg, dd=dd, gg=gg, closed_by=closed_by,
                  frozen_by_departure=frozen)
    if 'core_basis' in spec:
        result['core_basis'] = basis
    return result


def validate_xd_events(case, fixed):
    """冻结XD组成结构校验；gate/包含/撤销算术不在此重推。"""
    events = case['xd_events']
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


def validate_xd_audit(case):
    """18条确认理由只做序号与mode一致性校验，算术为叙述性冻结。"""
    audit = case['xd_audit']
    events = case['xd_events']
    if len(audit) != len(events):
        raise ValueError('xd_audit须与xd_events等长')
    kinds = {'first_selected', 'first_crossed_start', 'first_pending_cascade',
             'second_fx'}
    for i, (event, entry) in enumerate(zip(events, audit)):
        if entry['xd'] != i or entry['confirm_kind'] not in kinds:
            raise ValueError('xd_audit序号或确认类别无效')
        if (entry['confirm_kind'] == 'second_fx') != (event[2] == 2):
            raise ValueError('xd_audit确认类别与mode不一致')


def validate_roles(case, units):
    """a/A/b/B/c/C、gap、定理二合并与状态的全部角色算术。"""
    trend = case['trend']
    if trend['direction'] not in ('up', 'down'):
        raise ValueError('趋势方向无效')
    if trend['status'] not in ('ongoing', 'no_departure', 'completed'):
        raise ValueError('趋势状态无效')
    up = trend['direction'] == 'up'
    roles = case['roles']
    centers = {}
    for name in ('A', 'B', 'C'):
        spec = roles[name]
        centers[name] = (None if spec is None
                         else validate_zhongshu(name, spec, units))
    if centers['A'] is None or centers['B'] is None:
        raise ValueError('严格趋势须有A与B两个中枢')
    a = roles['a']
    if a is None:
        if centers['A']['zn'][0] != 0:
            raise ValueError('a缺席时A首Zn成员须为单元0')
    else:
        if index(a['unit']) != centers['A']['zn'][0] - 1:
            raise ValueError('a须紧邻A首Zn成员之前')
        if units[a['unit']]['direction'] != trend['direction']:
            raise ValueError('a方向须与趋势同向')
    b = index(roles['b']['unit'])
    if b != centers['A']['zn'][-1] + 1:
        raise ValueError('b须为A.zn[-1]+1')
    unit = units[b]
    if unit['direction'] != trend['direction']:
        raise ValueError('b方向须与趋势同向')
    if (unit['high_ticks'] <= centers['A']['zg'] if up
            else unit['low_ticks'] >= centers['A']['zd']):
        raise ValueError('b未离开A核心')
    if centers['B']['zn'][0] not in (b, b + 1):
        raise ValueError('B首Zn成员须紧随b')
    c = roles['c']
    if c is None:
        raise ValueError('严格趋势标注须声明c角色')
    if index(c['unit']) != centers['B']['zn'][-1] + 1:
        raise ValueError('c须为B.zn[-1]+1')
    unit = units[c['unit']]
    if unit['direction'] != trend['direction']:
        raise ValueError('c方向须与趋势同向')
    if c['outcome'] not in ('departed', 'fail'):
        raise ValueError('c结局无效')
    if up:
        departed = unit['high_ticks'] > centers['B']['zg']
        failed = unit['high_ticks'] < centers['B']['zd']
    else:
        departed = unit['low_ticks'] < centers['B']['zd']
        failed = unit['low_ticks'] > centers['B']['zg']
    if (departed, failed) != (c['outcome'] == 'departed',
                              c['outcome'] == 'fail'):
        raise ValueError('c结局与核心算术不一致')
    if centers['C'] is not None and \
            centers['C']['zn'][0] not in (c['unit'], c['unit'] + 1):
        raise ValueError('C首Zn成员须紧随c')
    gap = (centers['B']['dd'] - centers['A']['gg'] if up
           else centers['A']['dd'] - centers['B']['gg'])
    if index(roles['gap_ticks']) != gap:
        raise ValueError('gap算术不一致')
    if gap <= 0:
        raise ValueError('A与B包络重叠，不构成严格趋势')
    merge = roles['merge']
    branch_below = branch_above = None
    if centers['C'] is not None:
        branch_below = (centers['C']['zg'] < centers['B']['zd'] and
                        centers['C']['gg'] >= centers['B']['dd'])
        branch_above = (centers['C']['zd'] > centers['B']['zg'] and
                        centers['C']['dd'] <= centers['B']['gg'])
        if centers['C']['gg'] < centers['B']['dd'] or \
                centers['C']['dd'] > centers['B']['gg']:
            raise ValueError('定理二延续分支成立，不是合并')
    if merge is None:
        if branch_below or branch_above:
            raise ValueError('定理二合并分支成立，merge不得为null')
    else:
        if centers['C'] is None:
            raise ValueError('合并须有C中枢')
        if merge['pair'] != ['B', 'C'] or \
                merge['branch'] not in ('below', 'above'):
            raise ValueError('合并对或分支无效')
        if merge['determined'] is not (centers['C']['closed_by'] is not None):
            raise ValueError('合并determined与C封闭状态不一致')
        if merge['branch'] == 'below' and not branch_below:
            raise ValueError('下方合并算术不成立')
        if merge['branch'] == 'above' and not branch_above:
            raise ValueError('上方合并算术不成立')
    if c['outcome'] == 'fail':
        if trend['status'] != 'no_departure':
            raise ValueError('c_fail状态须为no_departure')
    else:
        proof = None
        for i in range(c['unit'] + 1, len(units)):
            item = units[i]
            if item['low_ticks'] <= centers['B']['zg'] and \
                    item['high_ticks'] >= centers['B']['zd']:
                proof = i
                break
        declared = roles.get('proof')
        if trend['status'] == 'completed':
            if declared is None:
                raise ValueError('完成须声明证明段')
            if index(declared['unit']) != c['unit'] + 1:
                raise ValueError('完成证明段须紧随c立即回核心（延迟回核心被第三中枢阻断）')
            if proof != declared['unit']:
                raise ValueError('证明段须为c后首个触核心单元')
            unit = units[declared['unit']]
            if up:
                if unit['direction'] != 'down' or \
                        unit['high_ticks'] <= centers['B']['zg'] or \
                        unit['low_ticks'] > centers['B']['zg']:
                    raise ValueError('证明段须自外侧回到B核心')
            elif unit['direction'] != 'up' or \
                    unit['low_ticks'] >= centers['B']['zd'] or \
                    unit['high_ticks'] < centers['B']['zd']:
                raise ValueError('证明段须自外侧回到B核心')
            if not centers['B']['frozen_by_departure']:
                raise ValueError('完成须B按0.9.3离开冻结（课29最后中枢定界）')
        elif declared is not None:
            raise ValueError('非完成状态不得声明证明段')
        elif trend['status'] != 'ongoing' or proof is not None:
            raise ValueError('departed状态与证明段算术不一致')
    return centers


def derive_ledger(roles, centers):
    """台账事件由角色推导；同单元内固定顺序，时间不回填。"""
    events = []

    def add_center(prefix, center):
        events.append((prefix + '_open', center['zn'][0] + 2))
        for i in center['zn'][2:]:
            events.append((prefix + '_zn_extend', i))
        if center['closed_by'] is not None:
            events.append((prefix + '_closed', center['closed_by']))

    add_center('A', centers['A'])
    events.append(('b_fixed', roles['b']['unit']))
    add_center('B', centers['B'])
    events.append(('c_fixed', roles['c']['unit']))
    events.append(('c_departed' if roles['c']['outcome'] == 'departed'
                   else 'c_fail', roles['c']['unit']))
    if roles.get('proof') is not None:
        events.append(('proof_fixed', roles['proof']['unit']))
    if centers['C'] is not None:
        add_center('C', centers['C'])
        if roles['merge'] is not None and roles['merge']['determined']:
            events.append(('merge_determined', centers['C']['closed_by']))
    rank = {'extend': 0, 'closed': 1, 'open': 2, 'fixed': 3,
            'departed': 4, 'fail': 4, 'determined': 5}
    events.sort(key=lambda item: (item[1], rank[item[0].rsplit('_', 1)[1]]))
    return [[name, unit] for name, unit in events]


def check_adjacency(units):
    """共享端点与方向交替是全部角色算术的前提。"""
    for i in range(1, len(units)):
        if units[i]['start_index'] != units[i - 1]['end_index'] or \
                units[i]['start_ticks'] != units[i - 1]['end_ticks'] or \
                units[i]['direction'] == units[i - 1]['direction']:
            raise ValueError('单元邻接或交替被破坏: ' + str(i))


def xd_units(fixed, events):
    """按冻结事件装配完成XD单元；证明笔未固定时不装配。"""
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
    """逐原始前缀核固定链及顺序发布；后段同时等待全部前段可见。

    事件的局部proof_bi保持原值；首次发布是自身证明与前段发布的最晚者。
    证据在前段以前齐备的后段，只能在前段实际可见时同批发布，不倒填。
    """
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
            if xd_seen[k] is None and n_fixed > proof and (k == 0 or xd_seen[k-1] is not None):
                xd_seen[k] = count
    if any(value is None for value in bi_seen) or \
            any(value is None for value in xd_seen):
        raise ValueError('存在未在前缀内确认的单元')
    return bi_seen, xd_seen


def compile_case(case, packet, packet_path):
    """全窗口角色算术、台账推导与逐前缀首确认一并冻结。"""
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
                           first_dt=arrival_dt(rows[count - 1]['dt'], granularity)))
    foundation_out = dict(bis=records(bis), bis_confirmed_raw_count=bi_seen)
    if events:
        foundation_out['xd_events'] = events
    out = dict(id=case['id'], window_key=case['window_key'],
               standard=case['standard'], level=case['level'],
               trend=case['trend'], raw_rows=rows,
               source=dict(packet=packet_path.name, sha256=digest(packet_path),
                           dataset_manifest_sha256=packet['manifest_sha256']),
               foundation=foundation_out, units=units,
               roles=case['roles'], ledger=ledger)
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
    result = dict(schema_version='chan-real-strict-trend-v1',
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
