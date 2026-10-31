# -*- coding: utf-8 -*-
"""课108: R2 因果底顶及81笔级条件算术的独立真实标注。

预期由原始行情、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。案例因子恒为1, 价格
单位0.001。因果底顶裁定(课108:2-6): 底部=第一类买点出现后至该买
点所引发的中枢第一次走出第三类买卖点前的构造过程, 顶部反过来
定义; 引发中枢=证明段起贪心运行的首个有效Zn(定理一全延伸, 一类
点后无新趋势上下文, 封闭不改变身份); 三类尝试沿用0.9.5几何(核心
确立后非Zn单元与核心闭区间重叠且端点越沿离开+紧邻反向回试, fail
不跳过、成立即止、触沿允许); 结局映射: 底×sell3先出现=失败、底×
buy3先出现=完成、顶×sell3先出现=完成、顶×buy3先出现=失败; 可见
=回试单元首确认, first_raw_count按逐原始bar前缀首次可见冻结;
构造区间=[一类点可见, 三类回试首确认]; 前提为历史笔级R2声明的
一类条件(0.9.9口径)，不证明当前完整F1/F2自动链的一类成立。
60m/30m bar以结束时刻为标签, 到达按结束+1分钟计;
日线到达15:05(测试约定)。覆盖: 底部失败F1(512880日线)、顶部完成
G1(588000 30m)、顶部失败H1(518880日线)、底部完成E1(159915 60m),
历史笔级条件下底/顶×完成/失败四格闭合，旧锚点均在未完成F1内部。

原81两窗只验证R2辅助前提下的结构、确认和失败映射；其MACD零轴比值
均>0.005。E1另补81笔级条件完成分支，零轴<0.005，但c仍是完整F1内部
锚点；输入不提供严格一类或完整次级证明，不把笔包装为ConfirmedMove。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    cases = []
    for name in ('real_causal_formation.json', 'real_causal_formation_81.json'):
        path = os.path.join(os.path.dirname(__file__), 'fixtures', name)
        with open(path, encoding='utf-8') as stream:
            cases.extend(json.load(stream)['cases'])
    return dict(cases=cases)


def raw_bars(case):
    """保留全部源行与完整bar时刻; 恒1因子样本不隐含暖机或复权。"""
    bars = []
    for row in case['raw_rows']:
        if row['adj_factor'] != 1:
            raise ValueError('新因子样本须另行冻结每个观察锚的算术')
        dt = datetime.strptime(row['dt'], '%Y-%m-%d %H:%M:%S')
        bars.append(dict(dt=dt, open=row['open'], high=row['high'],
                         low=row['low'], close=row['close'],
                         volume=row['vol']))
    return bars


def bi_records(bis):
    """笔五元组; 比较以人工整数价位表为准。"""
    return [[bi.direction, bi.start_index, bi.end_index,
             round(bi.start_value * 1000), round(bi.end_value * 1000)]
            for bi in bis]


def arrival(count, rows, granularity):
    """到达时刻测试约定: 日线收盘日15:05; 分钟按bar结束+1分钟。"""
    if granularity == 'day':
        return rows[count - 1]['dt'][:10] + ' 15:05:00'
    stamp = datetime.strptime(rows[count - 1]['dt'], '%Y-%m-%d %H:%M:%S')
    return (stamp + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')


def bi_unit_record(bi, count, rows, granularity):
    """固定笔序列化; 内部极值不改写端点bar时刻; day单元时刻取日期。"""
    width = 10 if granularity == 'day' else None
    return dict(start_index=bi.start_index, end_index=bi.end_index,
                start_ticks=round(bi.start_value * 1000),
                end_ticks=round(bi.end_value * 1000),
                start_dt=str(bi.start_dt)[:width],
                end_dt=str(bi.end_dt)[:width],
                low_ticks=round(bi.low * 1000), high_ticks=round(bi.high * 1000),
                direction=bi.direction, confirmed_raw_count=count,
                confirmed_dt=arrival(count, rows, granularity))


def unit_ticks(units):
    """因果底顶算术只消费整数区间与方向, 不读端点时间。"""
    return [dict(low_ticks=round(unit.low * 1000),
                 high_ticks=round(unit.high * 1000),
                 start_ticks=round(unit.start_value * 1000),
                 end_ticks=round(unit.end_value * 1000),
                 start_dt=(str(unit.start_dt)[:10] if
                           str(unit.start_dt)[11:] == '00:00:00'
                           else str(unit.start_dt)),
                 end_dt=(str(unit.end_dt)[:10] if
                         str(unit.end_dt)[11:] == '00:00:00'
                         else str(unit.end_dt)),
                 direction=unit.direction) for unit in units]


def library_units(case):
    """全窗口库链单元: bi级为固定笔。"""
    bars = raw_bars(case)
    _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
    return bis[:-1]


def ema(values, n):
    """固定EMA: 首值种子values[0], k=2/(n+1); 与冻结口径一致。"""
    out = [0.0] * len(values)
    k = 2.0 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def raw_index(rows, unit_dt, granularity, last=False):
    """单元端点映射原始行下标: 日线按日期, 分钟按完整bar标签。"""
    key = unit_dt if granularity != 'day' else unit_dt[:10]
    hits = [i for i, row in enumerate(rows)
            if (row['dt'] if granularity != 'day'
                else row['dt'][:10]) == key]
    if not hits:
        raise AssertionError('单元端点不在原始行: ' + str(unit_dt))
    return hits[-1] if last else hits[0]


def run_causal_zn(ticks, s):
    """引发中枢整数贪心运行(定理一全延伸, allow_freeze=False口径)。"""
    n = len(ticks)
    if s + 2 >= n:
        return None
    zdir = ticks[s]['direction']
    if ticks[s + 2]['direction'] != zdir:
        return None
    zd = max(ticks[s]['low_ticks'], ticks[s + 2]['low_ticks'])
    zg = min(ticks[s]['high_ticks'], ticks[s + 2]['high_ticks'])
    if zd > zg:
        return None
    mid = ticks[s + 1]
    if mid['low_ticks'] > zd or mid['high_ticks'] < zg:
        return None
    zn = [s, s + 2]
    last = s + 2
    closed_by = None
    while True:
        succ_i = last + 2
        if succ_i >= n:
            break
        succ = ticks[succ_i]
        if not (succ['low_ticks'] <= zg and succ['high_ticks'] >= zd):
            closed_by = succ_i
            break
        zn.append(succ_i)
        last = succ_i
    span = ticks[s:zn[-1] + 1]
    return dict(zn=zn, zd=zd, zg=zg,
                dd=min(u['low_ticks'] for u in span),
                gg=max(u['high_ticks'] for u in span),
                closed_by=closed_by)


def enumerate_attempts(ticks, center):
    """三类尝试台账几何重枚举(0.9.5冻结几何): fail不跳过, 成立即止。"""
    zn = set(center['zn'])
    zd, zg = center['zd'], center['zg']
    out = []
    for i in range(center['zn'][1] + 1, len(ticks) - 1):
        if i in zn:
            continue
        leave, pull = ticks[i], ticks[i + 1]
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


# 六个旧笔级条件锚点与最低完整F1的角色，静态整数表；不是新底顶标签。
LEGACY_CAUSAL_F1_AUDIT = {
    'F1': {
        'index': 2,
        'completed_then': 2,
        'f1': (6, 8, 'consolidation', None, (6,), ((1021, 1059),), 9),
        'confirmed_raw_count': 88,
        'end_dt': '2017-12-01 00:00:00',
        'end_ticks': 1059,
        'range_ticks': (1012, 1077),
    },
    'G1': {
        'index': 2,
        'completed_then': 2,
        'f1': (6, 15, 'down', 'down', (6, 10, 13), ((1203, 1224), (1149, 1169), (1076, 1090)), 16),
        'confirmed_raw_count': 229,
        'end_dt': '2022-09-01 10:30:00',
        'end_ticks': 1090,
        'range_ticks': (1072, 1230),
    },
    'H1': {
        'index': 2,
        'completed_then': 2,
        'f1': (6, 8, 'consolidation', None, (6,), ((4320, 4383),), 9),
        'confirmed_raw_count': 105,
        'end_dt': '2023-05-19 00:00:00',
        'end_ticks': 4320,
        'range_ticks': (4276, 4426),
    },
    'E1': {
        'index': 4,
        'completed_then': 4,
        'f1': (15, 17, 'consolidation', None, (15,), ((1406, 1441),), 18),
        'confirmed_raw_count': 319,
        'end_dt': '2019-05-30 14:00:00',
        'end_ticks': 1406,
        'range_ticks': (1378, 1445),
    },
    'M3T81': {
        'index': 2,
        'completed_then': 2,
        'f1': (9, 11, 'consolidation', None, (9,), ((1663, 1763),), 12),
        'confirmed_raw_count': 165,
        'end_dt': '2016-11-28 00:00:00',
        'end_ticks': 1849,
        'range_ticks': (1630, 1849),
    },
    'M3B81': {
        'index': 2,
        'completed_then': 2,
        'f1': (6, 8, 'consolidation', None, (6,), ((1626, 1702),), 9),
        'confirmed_raw_count': 87,
        'end_dt': '2018-01-26 00:00:00',
        'end_ticks': 1751,
        'range_ticks': (1601, 1751),
    },
}


class TestRealCausalFormation(unittest.TestCase):
    def test_legacy_first_points_are_internal_to_later_complete_f1(self):
        """课35/38/108：六个旧笔级锚点不等于完整F1端点，不能沿用为新链正例。"""
        cases = load_labels()['cases']
        self.assertEqual(set(LEGACY_CAUSAL_F1_AUDIT), {c['window_key'] for c in cases})
        for case in cases:
            key = case['window_key']
            audit = LEGACY_CAUSAL_F1_AUDIT[key]
            a, z, kind, direction, _, centers, _ = audit['f1']
            anchor = case['units'][case['first_point']['c_unit']]
            legacy_count = case['first_point']['first_raw_count']
            width = 10 if case.get('granularity', 'day') == 'day' else None
            bars = raw_bars(case)
            seen = None
            for count in range(1, audit['confirmed_raw_count']+1):
                fixed = chan.chan_fx_bi(bars[:count], standard=case['standard'])[2][:-1]
                moves = chan.same_level_decompose(fixed)
                complete = [m for m in moves if m.complete]
                target = [m for m in complete if m.seg_start == a]
                if count == legacy_count:
                    self.assertEqual(len(complete), audit['completed_then'], key)
                    containing, = [m for m in moves if m.seg_start <=
                                   case['first_point']['c_unit'] <= m.seg_end]
                    self.assertFalse(containing.complete, key)
                    self.assertEqual(containing.seg_start, a)
                    self.assertFalse(any(str(m.end_dt)[:width] == anchor['end_dt'] and
                                         round(fixed[m.seg_end].end_value*1000) == anchor['end_ticks']
                                         for m in complete), key)
                if target:
                    seen = count if seen is None else seen
                    move, = target
                    self.assertEqual((move.seg_start, move.seg_end, move.kind, move.direction),
                                     (a, z, kind, direction), key)
                    self.assertEqual(str(move.end_dt), audit['end_dt'])
                    self.assertEqual(round(fixed[z].end_value*1000), audit['end_ticks'])
                    self.assertEqual((round(move.low*1000), round(move.high*1000)), audit['range_ticks'])
                    self.assertEqual(tuple((round(lo*1000), round(hi*1000)) for lo, hi in move.centers), centers)
            self.assertEqual(seen, audit['confirmed_raw_count'], key)
            self.assertGreater(seen, legacy_count)

    def assert_area_close(self, actual, expected, label):
        """MACD面积按相对误差1e-12比较: 内建sum自Python 3.12对浮点
        改用Neumaier补偿求和, 3.6/3.10为顺序累加, 两种算法存在末位
        舍入差异; 相对误差1e-12只吸收该差异, 任何真实的区间/EMA/符号
        算术错误都会显著超出。"""
        self.assertLessEqual(
            abs(actual - expected),
            1e-12 * max(abs(actual), abs(expected)),
            '%s: %r != %r' % (label, actual, expected))

    def rederive_center(self, ticks, spec, context):
        """课17/20/29: 库单元上重推中枢算术; zn成员为人工声明结构。"""
        zn = spec['zn']
        self.assertGreaterEqual(len(zn), 2, context)
        for i in range(1, len(zn)):
            self.assertEqual(zn[i], zn[i - 1] + 2, (context, 'Zn同向步2'))
        direction = ticks[zn[0]]['direction']
        for i in zn:
            self.assertEqual(ticks[i]['direction'], direction,
                             (context, 'Zn成员方向'))
        first, second = ticks[zn[0]], ticks[zn[1]]
        zd = max(first['low_ticks'], second['low_ticks'])
        zg = min(first['high_ticks'], second['high_ticks'])
        self.assertLessEqual(zd, zg, (context, '首对核心为空'))
        self.assertEqual([zd, zg], [spec['zd'], spec['zg']],
                         (context, '首对核心与声明不一致'))
        middle = ticks[zn[0] + 1]
        self.assertLessEqual(middle['low_ticks'], zd,
                             (context, '中间单元未覆盖核心下沿'))
        self.assertGreaterEqual(middle['high_ticks'], zg,
                                (context, '中间单元未覆盖核心上沿'))
        for i in zn[2:]:
            unit = ticks[i]
            self.assertTrue(unit['low_ticks'] <= zg and
                            unit['high_ticks'] >= zd,
                            (context, '延伸单元未触沿', i))
        span = ticks[zn[0]:zn[-1] + 1]
        dd = min(unit['low_ticks'] for unit in span)
        gg = max(unit['high_ticks'] for unit in span)
        self.assertEqual([dd, gg], [spec['dd'], spec['gg']],
                         (context, 'DD/GG包络与声明不一致'))
        closed_by = spec['closed_by']
        frozen = spec.get('frozen_by_departure', False)
        self.assertIsInstance(frozen, bool, (context, 'frozen须为布尔'))
        if closed_by is None:
            if frozen:
                self.assertLess(zn[-1] + 2, len(ticks),
                                (context, '离开冻结须后继存在'))
                mid = ticks[zn[-1] + 1]
                self.assertNotEqual(mid['direction'], direction,
                                    (context, '冻结判定单元须为反向'))
                if direction == 'down':
                    self.assertGreater(mid['high_ticks'], zg,
                                       (context, '冻结须反向单元离开核心'))
                else:
                    self.assertLess(mid['low_ticks'], zd,
                                    (context, '冻结须反向单元离开核心'))
                successor = ticks[zn[-1] + 2]
                self.assertEqual(successor['direction'], direction,
                                 (context, '冻结须同向后继存在（承重）'))
                self.assertTrue(successor['low_ticks'] <= zg and
                                successor['high_ticks'] >= zd,
                                (context, '冻结承重：同向后继须触沿'))
            else:
                self.assertGreaterEqual(zn[-1] + 2, len(ticks),
                                        (context, '开放中枢不得有同向后继'))
        else:
            self.assertFalse(frozen, (context, 'closed_by与frozen互斥'))
            self.assertEqual(closed_by, zn[-1] + 2,
                             (context, '封口单元须为zn[-1]+2'))
            unit = ticks[closed_by]
            self.assertFalse(unit['low_ticks'] <= zg and
                             unit['high_ticks'] >= zd,
                             (context, '封口单元不得触沿'))
        return dict(zn=list(zn), zd=zd, zg=zg, dd=dd, gg=gg,
                    closed_by=closed_by, frozen_by_departure=frozen)

    def derive_ledger_events(self, roles, centers):
        """台账事件由角色推导; 同单元内固定顺序, 时间不回填。"""
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
        rank = {'extend': 0, 'closed': 1, 'open': 2, 'fixed': 3,
                'departed': 4, 'fail': 4, 'determined': 5}
        events.sort(key=lambda item: (item[1], rank[item[0].rsplit('_', 1)[1]]))
        return events

    def test_library_structure_matches_frozen_labels(self):
        """课65/67: 库全窗口链与冻结结构逐字段一致; 不读标签外预期。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            granularity = case.get('granularity', 'day')
            _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
            fixed = bis[:-1]
            self.assertEqual(bi_records(bis), case['foundation']['bis'],
                             case['id'])
            counts = case['foundation']['bis_confirmed_raw_count']
            rows = case['raw_rows']
            self.assertEqual(len(fixed), len(counts), case['id'])
            self.assertEqual(
                [bi_unit_record(bi, counts[i], rows, granularity)
                 for i, bi in enumerate(fixed)],
                case['units'], case['id'])

    def test_every_raw_prefix_replays_frozen_chain_and_first_confirmation(self):
        """课65/67/78: 逐原始bar前缀重放; 链前缀稳定、无撤销、首确认
        恰合; 一类裁定可见恰为证明段首确认、三类点可见恰为回试单元
        首确认、引发中枢核心可见恰为zn[1]首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            foundation = case['foundation']
            frozen = foundation['bis']
            granularity = case.get('granularity', 'day')
            rows = case['raw_rows']
            bi_seen = {}
            previous = 0
            for count in range(1, len(bars) + 1):
                _, _, bis = chan.chan_fx_bi(bars[:count],
                                            standard=case['standard'])
                fixed = bis[:-1]
                records = bi_records(bis)
                self.assertEqual(records[:len(fixed)], frozen[:len(fixed)],
                                 (case['id'], count, '固定链漂移'))
                self.assertGreaterEqual(len(fixed), previous,
                                        (case['id'], count, '固定笔撤销'))
                previous = len(fixed)
                for i in range(len(fixed)):
                    bi_seen.setdefault(i, count)
            counts = foundation['bis_confirmed_raw_count']
            self.assertEqual(
                [bi_seen[i] for i in range(len(counts))], counts, case['id'])
            for entry in case['ledger']:
                context = (case['id'], entry['event'])
                self.assertEqual(entry['first_raw_count'],
                                 bi_seen[entry['unit']], context)
                self.assertEqual(
                    entry['first_dt'],
                    arrival(entry['first_raw_count'], rows, granularity),
                    context)
            first = case['first_point']
            proof = first['proof_unit']
            self.assertEqual(first['first_raw_count'],
                             bi_seen[proof], case['id'])
            self.assertEqual(first['first_dt'],
                             arrival(first['first_raw_count'], rows,
                                     granularity), case['id'])
            formation = case['formation']
            center = formation['center']
            self.assertEqual(formation['center_open_first_raw_count'],
                             bi_seen[center['zn'][1]],
                             (case['id'], '引发中枢核心可见'))
            self.assertEqual(formation['center_open_first_dt'],
                             arrival(formation['center_open_first_raw_count'],
                                     rows, granularity), case['id'])
            zn = set(center['zn'])
            for attempt in formation['attempts']:
                context = (case['id'], 'attempt', attempt['leave'])
                if attempt['outcome'] == 'established':
                    self.assertNotIn(attempt['pull'], zn, context)
                self.assertEqual(attempt['first_raw_count'],
                                 bi_seen[attempt['pull']], context)
                self.assertEqual(
                    attempt['first_dt'],
                    arrival(attempt['first_raw_count'], rows, granularity),
                    context)
            resolution = formation['resolution']
            self.assertEqual(resolution['first_raw_count'],
                             bi_seen[resolution['unit']],
                             (case['id'], '三类点可见'))
            self.assertEqual(resolution['first_dt'],
                             arrival(resolution['first_raw_count'], rows,
                                     granularity), case['id'])
            self.assertEqual(formation['construction_interval'],
                             [first['first_dt'], resolution['first_dt']],
                             (case['id'], '构造区间'))

    def test_strict_trend_roles_rederived_from_library_units(self):
        """课17/20/29: 库单元重推A/B中枢、b/c/证明段角色、gap与台账。"""
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            self.assertEqual(trend['status'], 'completed', case['id'])
            centers = {}
            for name in ('A', 'B'):
                centers[name] = self.rederive_center(
                    ticks, roles[name], (case['id'], name))
            if roles['a'] is None:
                self.assertEqual(centers['A']['zn'][0], 0,
                                 (case['id'], 'a缺席时A首Zn成员须为单元0'))
            b = roles['b']['unit']
            self.assertEqual(b, centers['A']['zn'][-1] + 1,
                             (case['id'], 'b须为A.zn[-1]+1'))
            self.assertEqual(ticks[b]['direction'], trend['direction'],
                             (case['id'], 'b方向须与趋势同向'))
            if up:
                self.assertGreater(ticks[b]['high_ticks'],
                                   centers['A']['zg'],
                                   (case['id'], 'b未离开A核心'))
            else:
                self.assertLess(ticks[b]['low_ticks'], centers['A']['zd'],
                                (case['id'], 'b未离开A核心'))
            self.assertIn(centers['B']['zn'][0], (b, b + 1),
                          (case['id'], 'B首Zn成员须紧随b'))
            c = roles['c']['unit']
            self.assertEqual(c, centers['B']['zn'][-1] + 1,
                             (case['id'], 'c须为B.zn[-1]+1'))
            self.assertEqual(ticks[c]['direction'], trend['direction'],
                             (case['id'], 'c方向须与趋势同向'))
            self.assertEqual(roles['c']['outcome'], 'departed', case['id'])
            if up:
                self.assertGreater(ticks[c]['high_ticks'],
                                   centers['B']['zg'],
                                   (case['id'], 'c未离开B核心'))
            else:
                self.assertLess(ticks[c]['low_ticks'], centers['B']['zd'],
                                (case['id'], 'c未离开B核心'))
            proof = roles['proof']['unit']
            self.assertEqual(proof, c + 1,
                             (case['id'], '证明段须紧随c立即回核心'))
            self.assertTrue(centers['B']['frozen_by_departure'],
                            (case['id'], '完成须B按0.9.3离开冻结'))
            gap = (centers['B']['dd'] - centers['A']['gg'] if up
                   else centers['A']['dd'] - centers['B']['gg'])
            self.assertEqual(roles['gap_ticks'], gap, (case['id'], 'gap算术'))
            self.assertGreater(gap, 0, (case['id'], 'A与B包络重叠'))
            self.assertEqual(
                self.derive_ledger_events(roles, centers),
                [(entry['event'], entry['unit']) for entry in case['ledger']],
                (case['id'], '台账事件序列'))

    def test_first_point_arithmetic_rederived_from_raw_rows(self):
        """课24/27/29: 重推冻结辅助算术，不等同严格一类点证明。"""
        coverage = dict(buy1_established=0, sell1_established=0)
        for case in load_labels()['cases']:
            rows = case['raw_rows']
            granularity = case.get('granularity', 'day')
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            sign = 1 if up else -1
            first = case['first_point']
            self.assertEqual(first['side'],
                             'sell1' if up else 'buy1', case['id'])
            self.assertEqual(first['verdict'], 'established',
                             (case['id'], '因果底顶前提为一类成立'))
            self.assertIsNone(first['reason'], case['id'])
            b, c = roles['b']['unit'], roles['c']['unit']
            self.assertEqual(first['b_unit'], b, case['id'])
            self.assertEqual(first['c_unit'], c, case['id'])
            self.assertEqual(first['proof_unit'], roles['proof']['unit'],
                             case['id'])
            closes = [row['close'] for row in rows]
            fast, slow = ema(closes, 12), ema(closes, 26)
            dif = [x - y for x, y in zip(fast, slow)]
            dea = ema(dif, 9)
            hist = [(x - y) * 2.0 for x, y in zip(dif, dea)]
            b0 = raw_index(rows, ticks[b]['start_dt'], granularity)
            b1 = raw_index(rows, ticks[b]['end_dt'], granularity, True)
            c0 = raw_index(rows, ticks[c]['start_dt'], granularity)
            c1 = raw_index(rows, ticks[c]['end_dt'], granularity, True)
            area_b = sum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
            area_c = sum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
            self.assert_area_close(area_b, first['area_b'],
                                   (case['id'], 'area_b'))
            self.assert_area_close(area_c, first['area_c'],
                                   (case['id'], 'area_c'))
            self.assertGreater(area_b, area_c, (case['id'], '一类背驰'))
            trend_first = (roles['a']['unit'] if roles['a']
                           else roles['A']['zn'][0])
            self.assertEqual(first['trend_first_unit'], trend_first, case['id'])
            prior = ticks[trend_first:roles['B']['zn'][-1] + 1]
            prior_ext = (max(unit['high_ticks'] for unit in prior) if up
                         else min(unit['low_ticks'] for unit in prior))
            c_ext = ticks[c]['high_ticks'] if up else ticks[c]['low_ticks']
            self.assertEqual(prior_ext, first['prior_extreme_ticks'],
                             (case['id'], '全趋势先验极值'))
            self.assertEqual(c_ext, first['c_extreme_ticks'],
                             (case['id'], 'c极值'))
            new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
            self.assertTrue(new_extreme, (case['id'], 'c须新极值'))
            self.assertEqual(first['new_extreme'], new_extreme, case['id'])
            z_start = raw_index(rows,
                                ticks[roles['B']['zn'][0]]['start_dt'],
                                granularity)
            z_end = raw_index(rows, ticks[roles['B']['zn'][-1]]['end_dt'],
                              granularity, True)
            zero = min(max(abs(dif[i]), abs(dea[i])) / closes[i]
                       for i in range(z_start, z_end + 1))
            self.assertEqual(zero, first['zero_axis'],
                             (case['id'], '零轴回拉'))
            coverage['sell1_established' if up
                     else 'buy1_established'] += 1
        self.assertEqual(coverage, dict(buy1_established=3,
                                        sell1_established=3))

    def test_causal_formation_rederived_from_library_units(self):
        """课108: 库单元重推引发中枢贪心运行、三类尝试枚举与四结局
        映射; 封闭不改变引发中枢身份, fail尝试不跳过。"""
        coverage = dict(bottom_completed=0, bottom_failed=0,
                        top_completed=0, top_failed=0, attempts_fail=0)
        for case in load_labels()['cases']:
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            kind = 'top' if up else 'bottom'
            formation = case['formation']
            self.assertEqual(formation['kind'], kind, case['id'])
            self.assertEqual(case['first_point']['verdict'], 'established',
                             case['id'])
            proof = roles['proof']['unit']
            center = None
            for s in range(proof, len(ticks) - 2):
                center = run_causal_zn(ticks, s)
                if center is not None:
                    break
            self.assertIsNotNone(center, case['id'])
            declared_center = formation['center']
            self.assertEqual(declared_center['zn'], center['zn'],
                             (case['id'], '引发中枢Zn与重推不一致'))
            for name in ('zd', 'zg', 'dd', 'gg', 'closed_by'):
                self.assertEqual(declared_center[name], center[name],
                                 (case['id'], '引发中枢' + name))
            self.assertGreaterEqual(center['zn'][0], proof,
                                    (case['id'], '引发中枢须自证明段起'))
            enumerated = enumerate_attempts(ticks, center)
            attempts = formation['attempts']
            self.assertEqual(len(enumerated), len(attempts),
                             (case['id'], '尝试台账条目数'))
            zn = set(center['zn'])
            previous_leave = -1
            for enum, attempt in zip(enumerated, attempts):
                context = (case['id'], 'attempt', attempt['leave'])
                self.assertEqual(enum['side'], attempt['side'], context)
                self.assertEqual(enum['leave'], attempt['leave'], context)
                self.assertEqual(enum['pull'], attempt['pull'], context)
                self.assertGreater(attempt['leave'], previous_leave, context)
                previous_leave = attempt['leave']
                self.assertEqual(attempt['pull'], attempt['leave'] + 1,
                                 (context, '回试须紧随离开单元'))
                self.assertEqual(
                    attempt['outcome'],
                    'established' if enum['holds'] else 'fail', context)
                self.assertEqual(enum['point_ticks'],
                                 attempt['point_ticks'], context)
                self.assertEqual(enum['margin_ticks'],
                                 attempt['margin_ticks'], context)
                if attempt['outcome'] == 'established':
                    self.assertNotIn(attempt['pull'], zn, context)
                if attempt['outcome'] == 'fail':
                    coverage['attempts_fail'] += 1
            resolution = attempts[-1]
            self.assertEqual(resolution['outcome'], 'established',
                             (case['id'], '末条尝试须成立'))
            declared_res = formation['resolution']
            self.assertEqual(declared_res['side'], resolution['side'],
                             case['id'])
            self.assertEqual(declared_res['unit'], resolution['pull'],
                             case['id'])
            self.assertEqual(declared_res['leave'], resolution['leave'],
                             case['id'])
            self.assertEqual(declared_res['point_ticks'],
                             resolution['point_ticks'], case['id'])
            self.assertEqual(declared_res['margin_ticks'],
                             resolution['margin_ticks'], case['id'])
            if kind == 'bottom':
                outcome = ('completed' if resolution['side'] == 'buy3'
                           else 'failed')
            else:
                outcome = ('completed' if resolution['side'] == 'sell3'
                           else 'failed')
            self.assertEqual(formation['outcome'], outcome,
                             (case['id'], '结局映射（课108行4-6）'))
            coverage[kind + '_' + outcome] += 1
        self.assertEqual(coverage, dict(bottom_completed=1, bottom_failed=2,
                                        top_completed=1, top_failed=2,
                                        attempts_fail=11))

    def test_81_auxiliary_labels_preserve_their_evidence_boundary(self):
        """81条件标签不能冒充默认零轴筛选通过或严格理论底顶证明。"""
        path = os.path.join(os.path.dirname(__file__), 'fixtures',
                            'real_causal_formation_81.json')
        with open(path, encoding='utf-8') as stream:
            labels = json.load(stream)
        self.assertEqual(labels['annotation'],
                         'manual_causal_formation_81_conditional_auxiliary_math')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'M3T81', 'M3B81'})
        for case in labels['cases']:
            self.assertEqual(case['standard'], '81')
            self.assertGreater(case['first_point']['zero_axis'], 0.005)
            self.assertEqual(case['formation']['outcome'], 'failed')
            endpoint = case['units'][case['first_point']['c_unit']]['end_dt']
            self.assertGreater(case['first_point']['first_dt'][:10], endpoint)

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察时刻; NaN、缺价格字段及未来结构均
        不可读; 裁定可见边界恰为证明段/三类回试单元首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            first = case['first_point']
            formation = case['formation']
            resolution = formation['resolution']
            stop_points = (first['first_raw_count'] - 1,
                           first['first_raw_count'],
                           resolution['first_raw_count'])
            for stop in stop_points:
                now = bars[stop - 1]['dt']
                baseline = chan.analyze_at(bars[:stop], now,
                                           bi_standard=case['standard'])
                poisoned = [dict(bar) for bar in bars]
                for bar in poisoned[stop:]:
                    bar.pop('open')
                    bar.update(high=float('nan'), low=-999, close=99999)
                future = dict(dt=bars[-1]['dt'] + timedelta(days=1),
                              high=float('inf'), low=-999,
                              close=float('nan'), volume=1)
                self.assertEqual(
                    chan.analyze_at(poisoned + [future], now,
                                    bi_standard=case['standard']).to_dict(),
                    baseline.to_dict(), (case['id'], stop))
                expected = len([unit for unit in case['units']
                                if unit['confirmed_raw_count'] <= stop])
                self.assertEqual(len(baseline.bis) - 1, expected,
                                 (case['id'], stop))
            self.assertLessEqual(first['first_raw_count'],
                                 len(case['raw_rows']), case['id'])
            self.assertLessEqual(resolution['first_raw_count'],
                                 len(case['raw_rows']), case['id'])


# 81间隔重切既有E1报价；spans只复用旧独立表的端点坐标，不继承其角色。
# 17/21/26等旧笔只有三格间隔，不能将106确认时刻挪作81确认。
E1_81_CAUSAL_AUDIT = {
    'case': 'E1', 'raw_rows': 630,
    'source_sha256': '6e72f6931e6cbe957ee40d184c51ab0bf9a666aefd6f9c521333343b7e3dbf5b',
    'spans': ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5),
              (6, 6), (7, 7), (8, 8), (9, 9), (10, 10), (11, 11),
              (12, 12), (13, 13), (14, 14), (15, 15), (16, 16),
              (17, 19), (20, 20), (21, 23), (24, 24), (25, 25),
              (26, 28), (29, 29), (30, 30), (31, 31), (32, 32),
              (33, 33), (34, 34), (35, 37), (38, 38), (39, 39),
              (40, 40), (41, 43), (44, 48)),
    'tail': (('down', 332, 343, 1572, 1529, '2019-08-20 09:30:00', '2019-08-26 10:30:00'),
             ('up', 343, 347, 1529, 1586, '2019-08-26 10:30:00', '2019-08-27 11:30:00'),
             ('down', 347, 351, 1586, 1555, '2019-08-27 11:30:00', '2019-08-28 11:30:00')),
    'counts': (32, 40, 51, 59, 70, 81, 93, 110, 138, 166, 184, 245,
               263, 270, 283, 295, 311, 342, 363, 377, 390, 414,
               427, 432, 440, 449, 458, 464, 481, 495, 510, 521,
               528, 553, 596, 614, 619, 628),
    'A': ((0, 2, 4, 6, 8, 10), (1580, 1648), (1473, 1714)),
    'B': ((12, 14), (1402, 1441), (1391, 1472)),
    'b_c_proof': (11, 15, 16),
    'macd_spans': ((164, 233), (268, 285), (233, 268)),
    'areas': (0.3529640717199559, 0.040199284525317076),
    'zero_axis': 0.00045331264887526167,
    'formed': ((16, 18), (1378, 1432), (1356, 1445), 363),
    'whole': ((16, 18, 20, 22), (1378, 1432), (1356, 1518), 427),
    'formed_attempts': ((20, 21, -6), (22, 23, 37)),
    'whole_attempts': ((34, 35, 97),),
    'f1': (15, 17, (1378, 1441), 18, 363, 1356),
    'automatic_first_point_proven': False,
    'complete_lower_level_proven': False,
}


def e1_81_units(case):
    """81审计端点由旧坐标重切及三条原始尾端声明组成，不调用识别器。"""
    out = []
    for a, z in E1_81_CAUSAL_AUDIT['spans']:
        first, last = case['units'][a], case['units'][z]
        out.append(dict(direction=first['direction'],
                        start_index=first['start_index'], end_index=last['end_index'],
                        start_ticks=first['start_ticks'], end_ticks=last['end_ticks'],
                        start_dt=first['start_dt'], end_dt=last['end_dt']))
    for direction, a, z, start, end, start_dt, end_dt in E1_81_CAUSAL_AUDIT['tail']:
        out.append(dict(direction=direction, start_index=a, end_index=z,
                        start_ticks=start, end_ticks=end, start_dt=start_dt, end_dt=end_dt))
    for unit, count in zip(out, E1_81_CAUSAL_AUDIT['counts']):
        unit.update(low_ticks=min(unit['start_ticks'], unit['end_ticks']),
                    high_ticks=max(unit['start_ticks'], unit['end_ticks']),
                    confirmed_raw_count=count,
                    confirmed_dt=arrival(count, case['raw_rows'], '60m'))
    return out


class TestE1Formation81(unittest.TestCase):
    """81笔级R2辅助条件回归；不把笔包装为已完成次级走势或自动一类。"""

    def setUp(self):
        self.case = next(c for c in load_labels()['cases'] if c['window_key'] == 'E1')
        self.rows = self.case['raw_rows']
        self.bars = raw_bars(self.case)
        self.expected = e1_81_units(self.case)

    def actual(self, count):
        fixed = chan.chan_fx_bi(self.bars[:count], standard='81')[2][:-1]
        records = [bi_unit_record(bi, E1_81_CAUSAL_AUDIT['counts'][i],
                                  self.rows, '60m') for i, bi in enumerate(fixed)]
        self.assertEqual(records, self.expected[:len(records)])
        return fixed

    def test_all_630_raw_prefixes_recut_81_units_and_first_confirmation(self):
        """三格短笔重切、38项固定笔首确认及已完成前缀均独立声明。"""
        seen = {}
        for count in range(1, len(self.rows) + 1):
            fixed = self.actual(count)
            self.assertEqual(len(fixed), sum(n <= count for n in E1_81_CAUSAL_AUDIT['counts']))
            for i in range(len(fixed)):
                seen.setdefault(i, count)
        self.assertEqual(tuple(seen[i] for i in range(38)), E1_81_CAUSAL_AUDIT['counts'])
        self.assertEqual(self.case['first_point']['first_raw_count'], 305)
        self.assertEqual(E1_81_CAUSAL_AUDIT['counts'][16], 311)

    def test_formed_snapshot_and_whole_declaration_have_distinct_first_attempts(self):
        """同核心不同成员声明；不把全窗Zn筛选回填成形成快照的首次回试。"""
        ticks = unit_ticks(self.actual(630))
        for name in ('formed', 'whole'):
            zn, core, envelope, known = E1_81_CAUSAL_AUDIT[name]
            n = sum(v <= known for v in E1_81_CAUSAL_AUDIT['counts'])
            center = run_causal_zn(ticks[:n], 16)
            self.assertEqual((tuple(center['zn']), (center['zd'], center['zg']),
                              (center['dd'], center['gg'])), (zn, core, envelope))
            attempts = enumerate_attempts(ticks, center)
            self.assertEqual(tuple((a['leave'], a['pull'], a['margin_ticks']) for a in attempts),
                             E1_81_CAUSAL_AUDIT[name + '_attempts'])
        zss = chan.find_zs(self.actual(363)[16:19])
        self.assertEqual([(round(z.zd*1000), round(z.zg*1000)) for z in zss], [(1378, 1432)])
        self.assertEqual(self.expected[23]['end_ticks'], 1469)
        self.assertEqual(self.expected[35]['end_ticks'], 1529)
        # 几何失败20/21的离开还早于形成确认；不能称为已准入的条件点。
        self.assertLess(self.expected[20]['start_dt'], arrival(363, self.rows, '60m'))
        self.assertGreater(self.expected[22]['start_dt'], arrival(363, self.rows, '60m'))
        self.assertLess(self.expected[22]['start_dt'], arrival(427, self.rows, '60m'))

    def test_declared_auxiliary_events_keep_confirmation_and_future_boundaries(self):
        """只验证外部事件条件；空一类仍waiting，未借裸笔自动声明精确走势。"""
        clock = lambda n: datetime.strptime(arrival(n, self.rows, '60m'), '%Y-%m-%d %H:%M:%S')
        first = chan.FormationEvent('buy1', clock(311), 'declared-R2')
        for center_id, count in [('formed-E1-81', 432), ('whole-E1-81', 614)]:
            event = chan.FormationEvent('buy3', clock(count), 'declared-R2', center_id)
            for now, phase in [(clock(311)-timedelta(microseconds=1), 'waiting'),
                               (clock(count)-timedelta(microseconds=1), 'constructing'),
                               (clock(count), 'completed'), (clock(630), 'completed')]:
                state = chan.formation_state(first, center_id, [event], now)
                self.assertEqual(state.phase, phase)
                self.assertEqual(state.end_dt, event.confirmed_dt if phase == 'completed' else None)
            self.assertEqual(chan.formation_state(None, center_id, [event], clock(630)).phase, 'waiting')
        for count in (310, 311, 362, 363, 431, 432, 613, 614):
            at = self.bars[count-1]['dt']
            baseline = chan.analyze_at(self.bars, at, bi_standard='81').to_dict()
            poisoned = [dict(b) for b in self.bars]
            for bar in poisoned[count:]:
                bar.pop('open')
                bar.update(high=float('nan'), low=-999, close=99999)
            self.assertEqual(chan.analyze_at(poisoned, at, bi_standard='81').to_dict(), baseline)

    def test_auxiliary_buy_anchor_is_inside_later_complete_f1(self):
        """c15不是完整F1端点；新81完成端1356与旧106的1406分开。"""
        a, z, core, proof, known, end = E1_81_CAUSAL_AUDIT['f1']
        for count in (311, known-1, known, 630):
            fixed = self.actual(count)
            moves = chan.same_level_decompose(fixed)
            target, = [m for m in moves if m.seg_start <= 15 <= m.seg_end]
            self.assertEqual(target.seg_start, a)
            self.assertEqual(target.complete, count >= known)
            if count >= known:
                self.assertEqual((target.seg_end, target.kind, target.direction), (z, 'consolidation', None))
                self.assertEqual(tuple((round(lo*1000), round(hi*1000)) for lo, hi in target.centers), (core,))
                self.assertEqual(round(fixed[z].end_value*1000), end)
                self.assertEqual(E1_81_CAUSAL_AUDIT['counts'][proof], known)
        self.assertNotEqual(end, self.expected[15]['end_ticks'])
        self.assertFalse(E1_81_CAUSAL_AUDIT['automatic_first_point_proven'])
        self.assertFalse(E1_81_CAUSAL_AUDIT['complete_lower_level_proven'])


if __name__ == '__main__':
    unittest.main()
