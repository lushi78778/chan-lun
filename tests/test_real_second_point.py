# -*- coding: utf-8 -*-
"""课17/21/53/101: R2 0.9.10 二类买卖点真实正反例标注。

预期由原始行情、独立整数人工表经独立编译器冻结, 测试只读取标签,
不重新生成预期; 输入不继承窗口以前的结构。六案例因子恒为1, 价格
单位0.001。二类裁定: 锚定极值=趋势域(a或A首Zn成员..c单元)顺趋势
极值, 首次触及单元为锚定单元(端点boundary/内部interior, 差距
interior_gap_ticks登记); 离开方向与趋势相反, 锚定单元方向与离开
一致且锚值为其起点时腿1=锚定单元否则其后首个单元, 腿2=腿1后首个
反向单元; 二类点=腿2锚向极值(课17:74-78/课101:9-12); 三档(课101:
13-24): 最弱=腿2破锚, 最强=二三合一(买腿1高>B.zg且腿2低>=B.zg/
卖腿1低<B.zd且腿2高<=B.zd, 触沿允许沿用0.9.7/0.9.8, 课21:57-59),
一般=之间; 位置below/within/above仅登记(课21:51-53); 盘整背驰
leg2_area<anchor_area仅登记不作门槛(MACD口径同0.9.9, 课101:20
"一般都"为倾向性表述); 前提standard(一类成立)或minor_to_major
(小转大, 课53:42-49); 可见=腿2单元首确认, first_raw_count按逐原始
bar前缀首次可见冻结; later_break登记腿2后首个严格超越二类点极值
的单元(课101:25-35), 不改窗内裁定; 禁止确认时间回填。60m/30m/5m
bar以结束时刻为标签, 到达按结束+1分钟计; 日线到达15:05(测试
约定)。覆盖: buy2 x3(B1最弱/D1小转大/Y1小转大)、sell2 x3(C1
一般/X1小转大内部锚定/Z1最强二三合一)、事后跌破x2、位置below x4/
above x2。
"""
from datetime import datetime, timedelta
import json
import os
import unittest

import chan


def load_labels():
    """加载独立冻结标签; 不调用识别器、编译器或补齐预期字段。"""
    path = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'real_second_point.json')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


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


def xd_events(xds, fixed):
    """完成XD事件表[a,z,mode,proof]; proof为固定笔序列零基下标。"""
    out = []
    for xd in xds:
        starts = [i for i, bi in enumerate(fixed)
                  if bi.start_index == xd.start_index]
        ends = [i for i, bi in enumerate(fixed)
                if bi.end_index == xd.end_index]
        proofs = [i for i, bi in enumerate(fixed)
                  if bi.end_index == xd.evidence_end_index]
        if not (len(starts) == len(ends) == len(proofs) == 1):
            raise AssertionError('完成XD组成/证明须在固定笔内唯一回溯')
        out.append([starts[0], ends[0], xd.mode, proofs[0]])
    return out


def xd_unit_record(xd, fixed, count, rows, granularity):
    """完成XD序列化: 组成范围、模式、唯一证据笔与首确认。"""
    matches = [i for i, bi in enumerate(fixed)
               if bi.end_index == xd.evidence_end_index and
               bi.end_dt == xd.evidence_dt]
    if len(matches) != 1:
        raise AssertionError('完成XD须有唯一可回溯证据笔')
    return dict(start_index=xd.start_index, end_index=xd.end_index,
                start_ticks=round(xd.start_value * 1000),
                end_ticks=round(xd.end_value * 1000),
                start_dt=str(xd.start_dt), end_dt=str(xd.end_dt),
                low_ticks=round(xd.low * 1000),
                high_ticks=round(xd.high * 1000),
                direction=xd.direction, mode=xd.mode,
                proof_bi=matches[0],
                evidence_end_index=xd.evidence_end_index,
                evidence_dt=str(xd.evidence_dt),
                confirmed_raw_count=count,
                confirmed_dt=arrival(count, rows, granularity))


def library_units(case):
    """全窗口库链单元: bi级为固定笔, xd级为完成XD(不含尾部)。"""
    bars = raw_bars(case)
    _, _, bis = chan.chan_fx_bi(bars, standard=case['standard'])
    fixed = bis[:-1]
    if case['level'] == 'bi':
        return fixed
    return [xd for xd in chan.find_xds(fixed) if xd.complete]


def unit_counts(case):
    """单元首确认原始bar计数: bi级取固定笔表, xd级取冻结单元表。"""
    if case['level'] == 'bi':
        return case['foundation']['bis_confirmed_raw_count']
    return [unit['confirmed_raw_count'] for unit in case['units']]


def unit_ticks(units):
    """二类算术只消费整数区间与方向, 不读端点时间。"""
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


class TestRealSecondPoint(unittest.TestCase):
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
        """课17/20/29: 库单元上重推中枢算术; zn成员为人工声明结构。

        Zn同向步2、首对核心、中间覆盖、延伸触沿、DD/GG包络全部重算
        并与声明比对。状态算术: closed_by非null时封口单元=zn[-1]+2
        且不触沿; frozen_by_departure=true时中间反向单元离开核心且
        同向后继存在并触沿(课29行20-26离开后定界, 仅趋势末中枢);
        二者互斥; 均缺席时zn[-1]+2须越界(窗口末开放中枢)。
        """
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
            counts = unit_counts(case)
            rows = case['raw_rows']
            if case['level'] == 'bi':
                self.assertEqual(len(fixed), len(counts), case['id'])
                self.assertEqual(
                    [bi_unit_record(bi, counts[i], rows, granularity)
                     for i, bi in enumerate(fixed)],
                    case['units'], case['id'])
            else:
                xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                self.assertEqual(xd_events(xds, fixed),
                                 case['foundation']['xd_events'], case['id'])
                self.assertEqual(
                    [xd_unit_record(xd, fixed, counts[i], rows, granularity)
                     for i, xd in enumerate(xds)],
                    case['units'], case['id'])

    def test_every_raw_prefix_replays_frozen_chain_and_first_confirmation(self):
        """课65/67/78: 逐原始bar前缀重放; 链前缀稳定、无撤销、首确认
        恰合; 一类裁定可见恰为证明段首确认、二类可见恰为腿2首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            foundation = case['foundation']
            frozen = foundation['bis']
            events = foundation.get('xd_events') or []
            granularity = case.get('granularity', 'day')
            rows = case['raw_rows']
            bi_seen, xd_seen = {}, {}
            previous, computed = 0, -1
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
                if case['level'] == 'xd' and len(fixed) != computed:
                    xds = [xd for xd in chan.find_xds(fixed) if xd.complete]
                    visible = [event for event in events
                               if event[3] < len(fixed)]
                    self.assertEqual(xd_events(xds, fixed), visible,
                                     (case['id'], count, '完成XD恰合冻结事件'))
                    for k in range(len(visible)):
                        xd_seen.setdefault(k, count)
                    computed = len(fixed)
            self.assertEqual(
                [bi_seen[i] for i in range(len(foundation['bis_confirmed_raw_count']))],
                foundation['bis_confirmed_raw_count'], case['id'])
            unit_seen = (xd_seen if case['level'] == 'xd' else bi_seen)
            self.assertEqual(
                [unit_seen[i] for i in range(len(case['units']))],
                unit_counts(case), case['id'])
            counts = unit_counts(case)
            for entry in case['ledger']:
                context = (case['id'], entry['event'])
                self.assertEqual(entry['first_raw_count'],
                                 unit_seen[entry['unit']], context)
                self.assertEqual(
                    entry['first_dt'],
                    arrival(entry['first_raw_count'], rows, granularity),
                    context)
            first = case['first_point']
            proof = first['proof_unit']
            self.assertEqual(first['first_raw_count'],
                             unit_seen[proof], case['id'])
            self.assertEqual(first['first_dt'],
                             arrival(first['first_raw_count'], rows,
                                     granularity), case['id'])
            self.assertEqual(first['first_raw_count'],
                             counts[proof], case['id'])
            second = case['second_point']
            leg2 = second['leg2']
            self.assertEqual(second['leg2_confirmed_raw_count'],
                             unit_seen[leg2], case['id'])
            self.assertEqual(second['leg2_confirmed_dt'],
                             arrival(second['leg2_confirmed_raw_count'],
                                     rows, granularity), case['id'])
            self.assertEqual(second['leg2_confirmed_raw_count'],
                             counts[leg2], case['id'])
            self.assertTrue(second['leg2_visible_in_window'], case['id'])
            self.assertLessEqual(second['leg2_confirmed_raw_count'],
                                 len(case['raw_rows']), case['id'])

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
                self.assertGreater(ticks[b]['high_ticks'], centers['A']['zg'],
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
                self.assertGreater(ticks[c]['high_ticks'], centers['B']['zg'],
                                   (case['id'], 'c未离开B核心'))
            else:
                self.assertLess(ticks[c]['low_ticks'], centers['B']['zd'],
                                (case['id'], 'c未离开B核心'))
            proof = roles['proof']['unit']
            self.assertEqual(proof, c + 1,
                             (case['id'], '证明段须紧随c立即回核心'))
            if up:
                self.assertEqual(ticks[proof]['direction'], 'down',
                                 (case['id'], '证明段方向'))
                self.assertGreater(ticks[proof]['high_ticks'],
                                   centers['B']['zg'],
                                   (case['id'], '证明段须自外侧'))
                self.assertLessEqual(ticks[proof]['low_ticks'],
                                     centers['B']['zg'],
                                     (case['id'], '证明段须回B核心'))
            else:
                self.assertEqual(ticks[proof]['direction'], 'up',
                                 (case['id'], '证明段方向'))
                self.assertLess(ticks[proof]['low_ticks'],
                                centers['B']['zd'],
                                (case['id'], '证明段须自外侧'))
                self.assertGreaterEqual(ticks[proof]['high_ticks'],
                                        centers['B']['zd'],
                                        (case['id'], '证明段须回B核心'))
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
        """课24/27/29: 原始行重推MACD面积/新极值/零轴与裁定结局;
        覆盖买/卖成立与两类不成立原因。"""
        coverage = dict(buy1_established=0, sell1_established=0,
                        no_divergence=0, no_new_extreme=0)
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
            spans = {}
            for name, unit in (('b_span_raw', b), ('c_span_raw', c)):
                start = raw_index(rows, ticks[unit]['start_dt'],
                                  granularity)
                end = raw_index(rows, ticks[unit]['end_dt'], granularity,
                                True)
                spans[name] = [start, end]
            self.assertEqual([spans['b_span_raw'], spans['c_span_raw']],
                             [first['b_span_raw'], first['c_span_raw']],
                             (case['id'], '单元端点原始行映射'))
            b0, b1 = spans['b_span_raw']
            c0, c1 = spans['c_span_raw']
            area_b = sum(max(sign * v, 0.0) for v in hist[b0 + 1:b1 + 1])
            area_c = sum(max(sign * v, 0.0) for v in hist[c0 + 1:c1 + 1])
            self.assert_area_close(area_b, first['area_b'],
                                   (case['id'], 'area_b'))
            self.assert_area_close(area_c, first['area_c'],
                                   (case['id'], 'area_c'))
            divergence = 0 < area_c < area_b
            trend_first = (roles['a']['unit'] if roles['a']
                           else roles['A']['zn'][0])
            self.assertEqual(first['trend_first_unit'], trend_first, case['id'])
            prior = ticks[trend_first:roles['B']['zn'][-1] + 1]
            prior_ext = (max(unit['high_ticks'] for unit in prior) if up
                         else min(unit['low_ticks'] for unit in prior))
            c_ext = (ticks[c]['high_ticks'] if up
                     else ticks[c]['low_ticks'])
            self.assertEqual(prior_ext, first['prior_extreme_ticks'],
                             (case['id'], '全趋势先验极值'))
            self.assertEqual(c_ext, first['c_extreme_ticks'],
                             (case['id'], 'c极值'))
            new_extreme = c_ext > prior_ext if up else c_ext < prior_ext
            self.assertEqual(new_extreme, first['new_extreme'], case['id'])
            z_start = raw_index(rows, ticks[roles['B']['zn'][0]]['start_dt'],
                                granularity)
            z_end = raw_index(rows, ticks[roles['B']['zn'][-1]]['end_dt'],
                              granularity, True)
            self.assertEqual([z_start, z_end], first['zero_span_raw'],
                             (case['id'], '零轴区间原始行映射'))
            zero = min(max(abs(dif[i]), abs(dea[i])) / closes[i]
                       for i in range(z_start, z_end + 1))
            self.assertEqual(zero, first['zero_axis'], (case['id'], '零轴回拉'))
            if divergence and new_extreme:
                verdict, reason = 'established', None
            elif not divergence:
                verdict, reason = 'not_established', 'no_divergence'
            else:
                verdict, reason = 'not_established', 'no_new_extreme'
            self.assertEqual(first['verdict'], verdict, (case['id'], '裁定'))
            self.assertEqual(first['reason'], reason, (case['id'], '不成立原因'))
            if verdict == 'established':
                coverage['buy1_established' if not up
                         else 'sell1_established'] += 1
            else:
                coverage[reason] += 1
        self.assertEqual(coverage, dict(buy1_established=1,
                                        sell1_established=2,
                                        no_divergence=1,
                                        no_new_extreme=2))

    def test_second_point_arithmetic_rederived_from_raw_rows(self):
        """课17/21/53/101: 原始行重推锚定/腿/三档/位置/盘整背驰/事后
        跌破与前提; 覆盖两侧三档两前提。"""
        coverage = dict(buy2=0, sell2=0, weakest=0, ordinary=0, strongest=0,
                        below=0, within=0, above=0, standard=0,
                        minor_to_major=0, boundary=0, interior=0,
                        later_break=0, visible=0, cd_true=0)
        for case in load_labels()['cases']:
            rows = case['raw_rows']
            granularity = case.get('granularity', 'day')
            ticks = unit_ticks(library_units(case))
            roles = case['roles']
            trend = case['trend']
            up = trend['direction'] == 'up'
            sign = 1 if up else -1
            leave = 'down' if up else 'up'
            second = case['second_point']
            first = case['first_point']
            centers = {}
            for name in ('A', 'B'):
                centers[name] = self.rederive_center(
                    ticks, roles[name], (case['id'], name))
            zd, zg = centers['B']['zd'], centers['B']['zg']
            self.assertEqual(second['side'],
                             'sell2' if up else 'buy2', case['id'])
            trend_first = (roles['a']['unit'] if roles['a']
                           else centers['A']['zn'][0])
            domain = ticks[trend_first:roles['c']['unit'] + 1]
            anchor_val = (max(unit['high_ticks'] for unit in domain) if up
                          else min(unit['low_ticks'] for unit in domain))
            k = trend_first
            while ((ticks[k]['high_ticks'] if up
                    else ticks[k]['low_ticks']) != anchor_val):
                k += 1
            anchor_unit = ticks[k]
            boundary = anchor_val in (anchor_unit['start_ticks'],
                                      anchor_unit['end_ticks'])
            self.assertEqual(second['anchor_unit'], k, case['id'])
            self.assertEqual(second['anchor_kind'],
                             'boundary' if boundary else 'interior',
                             case['id'])
            self.assertEqual(second['anchor_ticks'], anchor_val, case['id'])
            self.assertEqual(second['anchor_span'],
                             [anchor_unit['start_dt'], anchor_unit['end_dt']],
                             case['id'])
            if (anchor_unit['direction'] == leave
                    and anchor_unit['start_ticks'] == anchor_val):
                leg1 = k
            else:
                leg1 = k + 1
            leg2 = leg1 + 1
            self.assertLess(leg2, len(ticks), case['id'])
            l1, l2 = ticks[leg1], ticks[leg2]
            self.assertEqual(second['leg1'], leg1, case['id'])
            self.assertEqual(second['leg2'], leg2, case['id'])
            self.assertEqual(second['leg1_span'],
                             [l1['start_dt'], l1['end_dt']], case['id'])
            self.assertEqual(second['leg2_span'],
                             [l2['start_dt'], l2['end_dt']], case['id'])
            interior_gap = (None if boundary
                            else (anchor_val - l1['start_ticks'] if up
                                  else l1['start_ticks'] - anchor_val))
            self.assertEqual(second['interior_gap_ticks'], interior_gap,
                             case['id'])
            second_ext = l2['high_ticks'] if up else l2['low_ticks']
            self.assertEqual(second['second_extreme_ticks'], second_ext,
                             case['id'])
            broke = second_ext > anchor_val if up else second_ext < anchor_val
            self.assertEqual(second['broke_anchor'], broke, case['id'])
            if broke:
                tier = 'weakest'
            elif up:
                tier = ('strongest' if second_ext <= zd and
                        l1['low_ticks'] < zd else 'ordinary')
            else:
                tier = ('strongest' if second_ext >= zg and
                        l1['high_ticks'] > zg else 'ordinary')
            self.assertEqual(second['tier'], tier, case['id'])
            position = ('below' if second_ext < zd
                        else 'within' if second_ext <= zg else 'above')
            self.assertEqual(second['position'], position, case['id'])
            closes = [row['close'] for row in rows]
            fast, slow = ema(closes, 12), ema(closes, 26)
            dif = [x - y for x, y in zip(fast, slow)]
            dea = ema(dif, 9)
            hist = [(x - y) * 2.0 for x, y in zip(dif, dea)]

            def area(unit):
                a0 = raw_index(rows, unit['start_dt'], granularity)
                a1 = raw_index(rows, unit['end_dt'], granularity, True)
                return (sum(max(sign * v, 0.0) for v in hist[a0 + 1:a1 + 1]),
                        [a0, a1])

            anchor_area, anchor_span_raw = area(anchor_unit)
            leg2_area, leg2_span_raw = area(l2)
            self.assert_area_close(second['anchor_area'], anchor_area,
                                   (case['id'], 'anchor_area'))
            self.assert_area_close(second['leg2_area'], leg2_area,
                                   (case['id'], 'leg2_area'))
            self.assertEqual(second['anchor_span_raw'], anchor_span_raw,
                             case['id'])
            self.assertEqual(second['leg2_span_raw'], leg2_span_raw,
                             case['id'])
            cd = leg2_area < anchor_area
            self.assertEqual(second['consolidation_divergence'], cd,
                             case['id'])
            later_break = None
            for j in range(leg2 + 1, len(ticks)):
                hit = ((ticks[j]['high_ticks'] > second_ext) if up
                       else (ticks[j]['low_ticks'] < second_ext))
                if hit:
                    later_break = dict(
                        unit=j,
                        extreme_ticks=(ticks[j]['high_ticks'] if up
                                       else ticks[j]['low_ticks']))
                    break
            self.assertEqual(second['later_break'], later_break, case['id'])
            premise = second['premise']
            if first['verdict'] == 'established':
                category = 'standard'
            else:
                category = 'minor_to_major'
            self.assertEqual(premise['category'], category, case['id'])
            self.assertEqual(premise['first_verdict'], first['verdict'],
                             case['id'])
            self.assertEqual(premise['first_reason'], first['reason'],
                             case['id'])
            coverage[second['side']] += 1
            coverage[tier] += 1
            coverage[position] += 1
            coverage[category] += 1
            coverage['boundary' if boundary else 'interior'] += 1
            if later_break is not None:
                coverage['later_break'] += 1
            if second['leg2_visible_in_window']:
                coverage['visible'] += 1
            if cd:
                coverage['cd_true'] += 1
        self.assertEqual(coverage, dict(
            buy2=3, sell2=3, weakest=1, ordinary=4, strongest=1,
            below=4, within=0, above=2, standard=3, minor_to_major=3,
            boundary=5, interior=1, later_break=2, visible=6, cd_true=4))

    def test_future_raw_poison_is_filtered_before_price_validation(self):
        """课65: 原始行情先截观察时刻; NaN、缺价格字段及未来结构均
        不可读; 裁定可见边界恰为证明段/腿2单元首确认。"""
        for case in load_labels()['cases']:
            bars = raw_bars(case)
            first = case['first_point']
            second = case['second_point']
            stop_points = (first['first_raw_count'] - 1,
                           first['first_raw_count'],
                           second['leg2_confirmed_raw_count'])
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
                if case['level'] == 'bi':
                    self.assertEqual(len(baseline.bis) - 1, expected,
                                     (case['id'], stop))
                else:
                    stable = baseline.bis[:-1]
                    self.assertEqual(
                        len([xd for xd in chan.find_xds(stable)
                             if xd.complete]), expected, (case['id'], stop))
            self.assertLessEqual(first['first_raw_count'],
                                 len(case['raw_rows']), case['id'])
            self.assertLessEqual(second['leg2_confirmed_raw_count'],
                                 len(case['raw_rows']), case['id'])


if __name__ == '__main__':
    unittest.main()
