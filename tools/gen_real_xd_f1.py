# -*- coding: utf-8 -*-
"""课20/38/63/67/71/78/84/106：人工完成XD→F1标注编译。

本地开发工具，不导入chan。基础包含、分型及笔使用独立整数参考；
XD边界、模式、最末证明笔和F1三段组均来自已冻结的人工审计。
本工具只验算这些声明，不搜索分界。非法索引、空交集及提前证明
直接拒绝，禁止Python负索引或切片截短把错误表变成可用真值。
各原始日前缀重算基础链，末笔先排除；证据首次固定的日线15:05
为测试可用时间，不代表真实供应到达。核心移位与全部波动关系分列。
"""
import argparse
import json
from pathlib import Path

from gen_real_f1_originals import components, digest, foundation, move_record, records


def index(value):
    """人工坐标仅为非负整数；布尔值不是索引。"""
    if type(value) is not int or value < 0:
        raise ValueError('人工索引须为非负整数')
    return value


def validate_manual(case, fixed):
    """先检查完整人工表，证明比组成晚且实际存在；不跳过错表。"""
    next_start = None
    for event in case['xd_events']:
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
        if max(u['low_ticks'] for u in first) > min(u['high_ticks'] for u in first):
            raise ValueError('XD前三筆闭区间交集为空')
    count = len(case['xd_events'])
    for spec in (case['f1_spec'], case['tail_spec']):
        a, z, kind, direction, triples, centers, proof = spec
        if not (index(a) <= index(z) < count):
            raise ValueError('F1人工组成越界')
        if len(triples) != len(centers):
            raise ValueError('三段组与核心交集数量不一致')
        for j, center in zip(triples, centers):
            if not (a <= index(j) and j + 2 <= z):
                raise ValueError('F1三段组须完整位于组成内')
            if len(center) != 2 or any(type(v) is not int for v in center) or center[0] > center[1]:
                raise ValueError('F1人工核心交集无效或为空')
        if proof is not None and not (z < index(proof) < count):
            raise ValueError('F1后继证明须晚于组成且存在')
        if proof is not None and (not centers or kind == 'incomplete'):
            raise ValueError('无中枢残段不得声明完成F1')
        if kind not in ('up', 'down', 'consolidation', 'incomplete') or direction not in ('up', 'down', None):
            raise ValueError('人工F1类型或方向无效')


def xd_records(fixed, events):
    """只在人工证明笔已固定时装配完成段，包络只含组成笔。"""
    out = []
    for a, z, mode, proof in events:
        if len(fixed) <= proof:
            continue
        covered = fixed[a:z + 1]
        record = dict(covered[0])
        record.update(end_index=covered[-1]['end_index'],
                      end_ticks=covered[-1]['end_ticks'], end_dt=covered[-1]['end_dt'],
                      low_ticks=min(u['low_ticks'] for u in covered),
                      high_ticks=max(u['high_ticks'] for u in covered),
                      mode=mode, proof_bi=proof,
                      evidence_end_index=fixed[proof]['end_index'],
                      evidence_dt=fixed[proof]['end_dt'])
        out.append(record)
    return out


def wave_relation(parts, spec, expected):
    """课20严格关系用三段组的全部波动，核心不相交不能替代它。"""
    triples = spec[4]
    waves = [[min(u['low_ticks'] for u in parts[j:j + 3]),
              max(u['high_ticks'] for u in parts[j:j + 3])] for j in triples]
    if len(waves) != 2:
        raise ValueError('本轮独立关系标注固定为两个三段中枢组')
    relation = ('up' if waves[1][0] > waves[0][1] else
                'down' if waves[1][1] < waves[0][0] else 'expand')
    # 工程三段组不自动等于课20 Z_n的全部角色归属；此处不输出严格正例。
    actual = dict(centers_ticks=spec[5], waves_ticks=waves,
                  core_direction=spec[2], relation=relation,
                  strict_trend_proven=False, scope='engineering_three_unit_groups')
    if actual != expected:
        raise ValueError('人工全部波动关系算术冲突')
    return actual


def compile_case(case, packet, packet_path):
    rows = packet['rows']
    if any(r['adj_factor'] != 1 for r in rows):
        raise ValueError('本轮整数标注仅接受因子恒为1，不修价或补因子')
    groups, fxs, bis = foundation(rows, case['standard'])
    fixed = components(rows, bis[:-1])
    validate_manual(case, fixed)
    units = xd_records(fixed, case['xd_events'])
    final = move_record(units, case['f1_spec'])
    tail = move_record(units, case['tail_spec'])
    relation = wave_relation(units, case['f1_spec'], case['wave_relation'])
    observations, previous, first_xd = {}, None, {}
    for count in range(1, len(rows) + 1):
        _, _, prefix_bis = foundation(rows[:count], case['standard'])
        visible = components(rows[:count], prefix_bis[:-1])
        xds = xd_records(visible, case['xd_events'])
        for i, item in enumerate(xds):
            first_xd.setdefault(i, count)
            # 已完成项组成必须保持稳定；证据笔延伸另由当前前缀记录。
            for field in ('start_index', 'end_index', 'start_ticks', 'end_ticks',
                          'start_dt', 'end_dt', 'low_ticks', 'high_ticks', 'direction', 'mode'):
                if item[field] != units[i][field]:
                    raise ValueError('人工完成XD组成回写: ' + field)
        completed = []
        if len(xds) > case['f1_spec'][-1]:
            current = move_record(xds, case['f1_spec'])
            if current != dict((k, v) for k, v in final.items()
                               if not k.startswith('confirmed_')):
                raise ValueError('人工完成F1回写')
            completed = [current]
            final.setdefault('confirmed_raw_count', count)
        snapshot = dict(fixed_bis=visible, completed_xds=xds, completed_f1=completed)
        if snapshot != previous:
            observations[str(count)] = snapshot
            previous = snapshot
    if 'confirmed_raw_count' not in final:
        raise ValueError('人工完成F1证明未出现')
    final['confirmed_dt'] = rows[final['confirmed_raw_count'] - 1]['dt'][:10] + ' 15:05:00'
    for i, unit in enumerate(units):
        unit['confirmed_raw_count'] = first_xd[i]
        unit['confirmed_dt'] = rows[first_xd[i] - 1]['dt'][:10] + ' 15:05:00'
    return dict(id=case['id'], window_key=case['window_key'], standard=case['standard'],
                raw_rows=rows, source=dict(packet=packet_path.name, sha256=digest(packet_path),
                    dataset_manifest_sha256=packet['manifest_sha256']),
                foundation=dict(new_bars=[dict(elements=g['elements'], low_ticks=g['lo'],
                    high_ticks=g['hi']) for g in groups],
                    fxs=[[f['kind'], f['index'], f['price']] for f in fxs], bis=records(bis)),
                paths={'xd-' + case['standard']:dict(units=units, moves=[final, tail], completed=[final])},
                observations=observations, wave_relation=relation)


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
    result = dict(schema_version='chan-real-xd-f1-v1', version=manual['version'],
                  manual_sha256=digest(args.manual), annotation=manual['annotation'],
                  availability=manual['availability'], limits=manual['limits'], cases=cases)
    args.output.resolve().write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
