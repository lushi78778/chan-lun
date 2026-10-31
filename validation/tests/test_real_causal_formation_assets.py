# -*- coding: utf-8 -*-
"""因果底顶冻结标注与轮次发现工具的独立算术、确认和来源契约。"""
import ast
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'validation/tools/gen_real_causal_formation.py'
MANUAL = ROOT / 'validation/chan-real-causal-formation-manual-0.9.11.json'
FIXTURE = ROOT / 'tests/fixtures/real_causal_formation.json'


def compiler(tool=TOOL):
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            tool.stem + '_assets', tool)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def manual_cases():
    return json.loads(MANUAL.read_text())['cases']


def packet_of(case):
    path = ROOT / 'validation' / case['packet']
    return path, json.loads(path.read_text())


class TestRealCausalFormationAssets(unittest.TestCase):
    def test_legacy_anchor_f1_completion_witnesses_recompute_from_original_rows(self):
        """六个旧锚点的完整F1反证表；AST读取，不导入包测试或识别器。"""
        source = ROOT / 'tests/test_real_causal_formation.py'
        table = next(ast.literal_eval(n.value) for n in ast.parse(source.read_text()).body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                     t.id == 'LEGACY_CAUSAL_F1_AUDIT' for t in n.targets))
        tool = compiler()
        cases = []
        for name in ('real_causal_formation.json', 'real_causal_formation_81.json'):
            cases.extend(json.loads((ROOT / 'tests/fixtures' / name).read_text())['cases'])
        self.assertEqual(set(table), {c['window_key'] for c in cases})
        for case in cases:
            audit = table[case['window_key']]
            a, z, kind, direction, triples, cores, proof = audit['f1']
            rows = case['raw_rows']
            anchor = case['first_point']['c_unit']
            self.assertTrue(a <= anchor <= z)
            self.assertGreater(audit['confirmed_raw_count'], case['first_point']['first_raw_count'])
            visibility = []
            for count in (case['first_point']['first_raw_count'],
                          audit['confirmed_raw_count']-1, audit['confirmed_raw_count']):
                _, _, bis = tool.foundation(rows[:count], case['standard'])
                fixed = tool.components(rows[:count], bis[:-1], dt_slice=None)
                visibility.append(len(fixed) > proof)
            self.assertEqual(visibility, [False, False, True])
            self.assertEqual((fixed[z]['end_dt'], fixed[z]['end_ticks']),
                             (audit['end_dt'], audit['end_ticks']))
            self.assertEqual((min(u['low_ticks'] for u in fixed[a:z+1]),
                              max(u['high_ticks'] for u in fixed[a:z+1])), audit['range_ticks'])
            actual = tuple((max(u['low_ticks'] for u in fixed[j:j+3]),
                            min(u['high_ticks'] for u in fixed[j:j+3])) for j in triples)
            self.assertEqual(actual, cores)
            width = 10 if case.get('granularity', 'day') == 'day' else None
            self.assertNotEqual((audit['end_dt'][:width], audit['end_ticks']),
                                (case['units'][anchor]['end_dt'], case['units'][anchor]['end_ticks']))

    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['annotation'],
                         'manual_causal_formation_real_first_point_established')
        self.assertEqual(labels['schema_version'],
                         'chan-real-causal-formation-v1')
        self.assertEqual(labels['minimum_rule'], manual['minimum_rule'])
        self.assertEqual(labels['availability'], manual['availability'])
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'F1', 'G1', 'H1', 'E1'})
        granularities = {'F1': 'day', 'G1': '30m',
                         'H1': 'day', 'E1': '60m'}
        outcomes = {'F1': ('bottom', 'failed'), 'G1': ('top', 'completed'),
                    'H1': ('top', 'failed'), 'E1': ('bottom', 'completed')}
        manual_by_key = {case['window_key']: case for case in manual['cases']}
        for case in labels['cases']:
            key = case['window_key']
            self.assertEqual(case.get('granularity', 'day'),
                             granularities[key])
            self.assertEqual(case['id'], manual_by_key[key]['id'])
            self.assertEqual(case['first_point']['verdict'], 'established')
            self.assertEqual((case['formation']['kind'],
                              case['formation']['outcome']), outcomes[key])
            self.assertEqual(case['formation']['attempts'][-1]['outcome'],
                             'established')
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
            self.assertEqual(tool.digest(packet),
                             manual_by_key[key]['packet_sha256'])
            data = json.loads(packet.read_text())
            self.assertEqual(data['rows'], case['raw_rows'])
            self.assertEqual(
                data['manifest_sha256'],
                case['source']['dataset_manifest_sha256'])
        for path in (TOOL, ROOT / 'validation/tools/gen_real_first_point.py',
                     ROOT / 'validation/tools/gen_real_strict_trend.py',
                     ROOT / 'validation/tools/gen_real_third_point.py',
                     ROOT / 'validation/tools/gen_real_f1_originals.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                self.assertTrue(
                    all(name.split('.')[0] != 'chan' for name in names))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'labels.json'
            command = [sys.executable, str(TOOL), '--manual', str(MANUAL),
                       '--packets', str(ROOT / 'validation'),
                       '--output', str(output)]
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())

    def test_reject_corrupt_f1_strict_trend_first_point_and_formation_tables(self):
        """F1结构、趋势角色、台账、一类与因果底顶表被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'F1'][0]
        path, data = packet_of(case)
        changes = [
            ('level', lambda c: c.__setitem__('level', 'xd')),
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1091)),
            ('trend_status',
             lambda c: c['trend'].__setitem__('status', 'ongoing')),
            ('trend_direction',
             lambda c: c['trend'].__setitem__('direction', 'up')),
            ('a_zn_step',
             lambda c: c['roles']['A']['zn'].__setitem__(1, 3)),
            ('A_zd', lambda c: c['roles']['A'].__setitem__('zd', 1100)),
            ('b_unit',
             lambda c: c['roles']['b'].__setitem__('unit', 2)),
            ('B_zd', lambda c: c['roles']['B'].__setitem__('zd', 1060)),
            ('c_unit', lambda c: c['roles']['c'].__setitem__('unit', 6)),
            ('c_outcome',
             lambda c: c['roles']['c'].__setitem__('outcome', 'fail')),
            ('proof_unit',
             lambda c: c['roles']['proof'].__setitem__('unit', 9)),
            ('gap_ticks',
             lambda c: c['roles'].__setitem__('gap_ticks', 12)),
            ('ledger_dropped', lambda c: c['ledger'].pop()),
            ('ledger_event',
             lambda c: c['ledger'][0].__setitem__(0, 'B_open')),
            ('fp_side',
             lambda c: c['first_point'].__setitem__('side', 'sell1')),
            ('fp_verdict',
             lambda c: c['first_point'].__setitem__('verdict',
                                                    'not_established')),
            ('fp_reason',
             lambda c: c['first_point'].__setitem__('reason',
                                                    'no_divergence')),
            ('fp_area_b',
             lambda c: c['first_point'].__setitem__('area_b', 0.028)),
            ('fp_prior_extreme',
             lambda c: c['first_point'].__setitem__(
                 'prior_extreme_ticks',
                 c['first_point']['prior_extreme_ticks'] + 1)),
            ('fp_c_extreme',
             lambda c: c['first_point'].__setitem__(
                 'c_extreme_ticks',
                 c['first_point']['c_extreme_ticks'] + 1)),
            ('fp_new_extreme',
             lambda c: c['first_point'].__setitem__('new_extreme', False)),
            ('fp_zero_axis',
             lambda c: c['first_point'].__setitem__(
                 'zero_axis', c['first_point']['zero_axis'] + 0.001)),
            ('formation_kind',
             lambda c: c['formation'].__setitem__('kind', 'top')),
            ('center_zn',
             lambda c: c['formation']['center']['zn'].__setitem__(1, 12)),
            ('center_zd',
             lambda c: c['formation']['center'].__setitem__(
                 'zd', c['formation']['center']['zd'] + 1)),
            ('center_zg',
             lambda c: c['formation']['center'].__setitem__(
                 'zg', c['formation']['center']['zg'] + 1)),
            ('center_dd',
             lambda c: c['formation']['center'].__setitem__(
                 'dd', c['formation']['center']['dd'] + 1)),
            ('center_gg',
             lambda c: c['formation']['center'].__setitem__(
                 'gg', c['formation']['center']['gg'] + 1)),
            ('center_closed_by',
             lambda c: c['formation']['center'].__setitem__(
                 'closed_by', None)),
            ('attempts_dropped',
             lambda c: c['formation']['attempts'].pop()),
            ('attempt_side',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'side', 'buy3')),
            ('attempt_leave',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'leave', c['formation']['attempts'][0]['leave'] + 1)),
            ('attempt_pull',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'pull', c['formation']['attempts'][0]['pull'] + 1)),
            ('attempt_outcome',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'outcome', 'established')),
            ('attempt_point',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'point_ticks',
                 c['formation']['attempts'][0]['point_ticks'] + 1)),
            ('attempt_margin',
             lambda c: c['formation']['attempts'][0].__setitem__(
                 'margin_ticks',
                 c['formation']['attempts'][0]['margin_ticks'] + 1)),
            ('resolution_side',
             lambda c: c['formation']['resolution'].__setitem__(
                 'side', 'buy3')),
            ('resolution_unit',
             lambda c: c['formation']['resolution'].__setitem__(
                 'unit', c['formation']['resolution']['unit'] + 1)),
            ('resolution_leave',
             lambda c: c['formation']['resolution'].__setitem__(
                 'leave', c['formation']['resolution']['leave'] + 1)),
            ('resolution_point',
             lambda c: c['formation']['resolution'].__setitem__(
                 'point_ticks',
                 c['formation']['resolution']['point_ticks'] + 1)),
            ('outcome_mapping',
             lambda c: c['formation'].__setitem__('outcome', 'completed')),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)

    def test_reject_corrupt_frozen_window_formation_tables(self):
        """G1/H1/E1因果底顶表被篡改时直接拒绝。"""
        tool = compiler()
        for case in manual_cases():
            if case['window_key'] == 'F1':
                continue
            path, data = packet_of(case)
            formation = case['formation']
            changes = [
                ('formation_kind',
                 lambda c: c['formation'].__setitem__(
                     'kind', 'top' if c['formation']['kind'] == 'bottom'
                     else 'bottom')),
                ('outcome_mapping',
                 lambda c: c['formation'].__setitem__(
                     'outcome',
                     'completed' if c['formation']['outcome'] == 'failed'
                     else 'failed')),
                ('center_zn',
                 lambda c: c['formation']['center']['zn'].__setitem__(
                     1, c['formation']['center']['zn'][1] + 2)),
                ('center_zd',
                 lambda c: c['formation']['center'].__setitem__(
                     'zd', c['formation']['center']['zd'] + 1)),
                ('center_zg',
                 lambda c: c['formation']['center'].__setitem__(
                     'zg', c['formation']['center']['zg'] + 1)),
                ('center_dd',
                 lambda c: c['formation']['center'].__setitem__(
                     'dd', c['formation']['center']['dd'] + 1)),
                ('center_gg',
                 lambda c: c['formation']['center'].__setitem__(
                     'gg', c['formation']['center']['gg'] + 1)),
                ('center_closed_by',
                 lambda c: c['formation']['center'].__setitem__(
                     'closed_by', None)),
                ('attempts_dropped',
                 lambda c: c['formation']['attempts'].pop()),
                ('attempt_side',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'side', 'buy3' if c['formation']['attempts'][0]['side']
                     == 'sell3' else 'sell3')),
                ('attempt_leave',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'leave', c['formation']['attempts'][0]['leave'] + 1)),
                ('attempt_pull',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'pull', c['formation']['attempts'][0]['pull'] + 1)),
                ('attempt_outcome',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'outcome',
                     'established'
                     if c['formation']['attempts'][0]['outcome'] == 'fail'
                     else 'fail')),
                ('attempt_point',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'point_ticks',
                     c['formation']['attempts'][0]['point_ticks'] + 1)),
                ('attempt_margin',
                 lambda c: c['formation']['attempts'][0].__setitem__(
                     'margin_ticks',
                     c['formation']['attempts'][0]['margin_ticks'] + 1)),
                ('last_attempt_outcome',
                 lambda c: c['formation']['attempts'][-1].__setitem__(
                     'outcome', 'fail')),
                ('last_attempt_point',
                 lambda c: c['formation']['attempts'][-1].__setitem__(
                     'point_ticks',
                     c['formation']['attempts'][-1]['point_ticks'] + 1)),
                ('resolution_side',
                 lambda c: c['formation']['resolution'].__setitem__(
                     'side', 'buy3' if c['formation']['resolution']['side']
                     == 'sell3' else 'sell3')),
                ('resolution_unit',
                 lambda c: c['formation']['resolution'].__setitem__(
                     'unit', c['formation']['resolution']['unit'] + 1)),
                ('resolution_leave',
                 lambda c: c['formation']['resolution'].__setitem__(
                     'leave', c['formation']['resolution']['leave'] + 1)),
                ('resolution_point',
                 lambda c: c['formation']['resolution'].__setitem__(
                     'point_ticks',
                     c['formation']['resolution']['point_ticks'] + 1)),
                ('resolution_margin',
                 lambda c: c['formation']['resolution'].__setitem__(
                     'margin_ticks',
                     c['formation']['resolution']['margin_ticks'] + 1)),
            ]
            for name, mutate in changes:
                with self.subTest(window=case['window_key'], name=name):
                    broken = copy.deepcopy(case)
                    mutate(broken)
                    with self.assertRaises(ValueError):
                        tool.compile_case(broken, data, path)


class TestRealCausalFormation81Assets(unittest.TestCase):
    """两份新前缀与独立审计表保真；旧四窗和编译器输出不回写。"""

    def test_sources_confirmation_audit_and_frozen_rebuild(self):
        tool = compiler()
        manual_path = ROOT / 'validation/chan-real-causal-formation-manual-1.0.2.json'
        fixture = ROOT / 'tests/fixtures/real_causal_formation_81.json'
        manual = json.loads(manual_path.read_text())
        labels = json.loads(fixture.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(manual_path))
        self.assertEqual(labels['annotation'],
                         'manual_causal_formation_81_conditional_auxiliary_math')
        self.assertEqual(labels['minimum_rule'], manual['minimum_rule'])
        self.assertEqual(labels['limits'], manual['limits'])
        self.assertEqual(len(labels['cases']), 2)
        for case, frozen in zip(manual['cases'], labels['cases']):
            path, packet = packet_of(case)
            self.assertEqual(tool.digest(path), case['packet_sha256'])
            self.assertEqual(frozen['source']['sha256'], case['packet_sha256'])
            self.assertEqual(packet['rows'], frozen['raw_rows'])
            self.assertEqual(packet['manifest_sha256'],
                             frozen['source']['dataset_manifest_sha256'])
            audit = case['audit']
            self.assertEqual(frozen['foundation']['bis_confirmed_raw_count'],
                             audit['expected_confirmed_raw_counts'])
            self.assertEqual(frozen['first_point']['first_raw_count'],
                             audit['first_raw_count'])
            self.assertEqual(frozen['formation']['center_open_first_raw_count'],
                             audit['center_open_raw_count'])
            self.assertEqual(frozen['formation']['resolution']['first_raw_count'],
                             audit['resolution_raw_count'])
            self.assertEqual(len(packet['rows']), audit['resolution_raw_count'])
            self.assertFalse(audit['current_default_zero_axis_pass'])
            self.assertGreater(frozen['first_point']['zero_axis'],
                               audit['current_default_zero_axis_limit'])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'labels.json'
            command = [sys.executable, str(TOOL), '--manual', str(manual_path),
                       '--packets', str(ROOT / 'validation'), '--output', str(output)]
            run = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(output.read_bytes(), fixture.read_bytes())
            run = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(output.read_bytes(), fixture.read_bytes())

    def test_reject_wrong_standard_early_proof_and_mislabelled_first_attempt(self):
        tool = compiler()
        manual = json.loads((ROOT / 'validation/chan-real-causal-formation-manual-1.0.2.json').read_text())
        for case in manual['cases']:
            path, packet = packet_of(case)
            changes = [
                ('standard', lambda c: c.__setitem__('standard', '106')),
                ('early_proof', lambda c: c['roles']['proof'].__setitem__(
                    'unit', c['roles']['c']['unit'])),
                ('point', lambda c: c['formation']['attempts'][-1].__setitem__(
                    'point_ticks', c['formation']['attempts'][-1]['point_ticks'] + 1)),
                ('outcome', lambda c: c['formation'].__setitem__('outcome', 'completed')),
                ('missing_first_attempt', lambda c: c['formation']['attempts'].pop(0)),
            ]
            for name, mutate in changes:
                with self.subTest(window=case['window_key'], change=name):
                    broken = copy.deepcopy(case)
                    mutate(broken)
                    with self.assertRaises(ValueError):
                        tool.compile_case(broken, packet, path)


class TestE1Formation81Assets(unittest.TestCase):
    """新81整数审计表只读取既有报价/坐标；旧两份fixture及标签保持。"""

    @staticmethod
    def inputs():
        tree = ast.parse((ROOT / 'tests/test_real_causal_formation.py').read_text())
        audit = next(ast.literal_eval(n.value) for n in tree.body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                     and t.id == 'E1_81_CAUSAL_AUDIT' for t in n.targets))
        case = next(c for c in json.loads(FIXTURE.read_text())['cases']
                    if c['window_key'] == audit['case'])
        expected = []
        for a, z in audit['spans']:
            u, v = case['units'][a], case['units'][z]
            expected.append(dict(direction=u['direction'], start_index=u['start_index'],
                                 end_index=v['end_index'], start_ticks=u['start_ticks'],
                                 end_ticks=v['end_ticks'], start_dt=u['start_dt'], end_dt=v['end_dt']))
        for direction, a, z, start, end, first, last in audit['tail']:
            expected.append(dict(direction=direction, start_index=a, end_index=z,
                                 start_ticks=start, end_ticks=end, start_dt=first, end_dt=last))
        for unit in expected:
            unit.update(low_ticks=min(unit['start_ticks'], unit['end_ticks']),
                        high_ticks=max(unit['start_ticks'], unit['end_ticks']))
        return audit, case, expected

    def test_e1_81_raw_coordinates_gaps_and_all_630_confirmation_prefixes(self):
        audit, case, expected = self.inputs()
        tool = compiler()
        self.assertEqual(tool.digest(FIXTURE), audit['source_sha256'])
        self.assertEqual(len(case['raw_rows']), audit['raw_rows'])
        groups, _, _ = tool.foundation(case['raw_rows'], '81')
        for unit in expected:
            self.assertGreaterEqual(unit['end_index']-unit['start_index'], 4)
            for endpoint, which in [('start', 'lo' if unit['direction'] == 'up' else 'hi'),
                                    ('end', 'hi' if unit['direction'] == 'up' else 'lo')]:
                group = groups[unit[endpoint+'_index']]
                self.assertEqual(group[which], unit[endpoint+'_ticks'])
                self.assertEqual(case['raw_rows'][group['elements'][-1]]['dt'], unit[endpoint+'_dt'])
        for a, z in audit['spans']:
            if a != z:
                self.assertTrue(any(u['end_index']-u['start_index'] < 4
                                    for u in case['units'][a:z+1]))
        first = {}
        for count in range(1, len(case['raw_rows'])+1):
            rows = case['raw_rows'][:count]
            fixed = tool.foundation(rows, '81')[2][:-1]
            units = tool.components(rows, fixed, dt_slice=None)
            self.assertEqual(units, expected[:len(units)])
            self.assertEqual(len(units), sum(n <= count for n in audit['counts']))
            for i in range(len(units)):
                first.setdefault(i, count)
        self.assertEqual(tuple(first[i] for i in range(38)), audit['counts'])

    def test_e1_81_integer_roles_and_rational_macd_do_not_prove_complete_first(self):
        audit, case, units = self.inputs()
        rows = case['raw_rows']
        for name in ('A', 'B'):
            zn, core, envelope = audit[name]
            self.assertEqual((max(units[i]['low_ticks'] for i in zn[:2]),
                              min(units[i]['high_ticks'] for i in zn[:2])), core)
            self.assertEqual((min(u['low_ticks'] for u in units[zn[0]:zn[-1]+1]),
                              max(u['high_ticks'] for u in units[zn[0]:zn[-1]+1])), envelope)
        self.assertEqual(audit['A'][2][0]-audit['B'][2][1], 1)
        self.assertEqual(min(u['low_ticks'] for u in units[:15])-units[15]['low_ticks'], 13)
        # 从原始十进制报价用有理EMA独立复算，不调用扫描器的MACD helper。
        prices = [Fraction(str(r['close'])) for r in rows]
        short = long = prices[0]
        signal = Fraction(0)
        dif, dea, hist = [], [], []
        for price in prices:
            short = (2*price+11*short)/13
            long = (2*price+25*long)/27
            delta = short-long
            signal = (2*delta+8*signal)/10
            dif.append(delta)
            dea.append(signal)
            hist.append(2*(delta-signal))
        areas = []
        for a, z in audit['macd_spans'][:2]:
            areas.append(float(sum((max(-v, Fraction(0)) for v in hist[a+1:z+1]), Fraction(0))))
        for actual, expected in zip(areas, audit['areas']):
            self.assertAlmostEqual(actual, expected, delta=abs(expected)*1e-12)
        a, z = audit['macd_spans'][2]
        zero = float(min(max(abs(dif[i]), abs(dea[i]))/prices[i] for i in range(a, z+1)))
        self.assertAlmostEqual(zero, audit['zero_axis'], delta=1e-14)
        self.assertTrue(0 < areas[1] < areas[0])
        self.assertLess(zero, 0.005)
        a, z, core, proof, count, end = audit['f1']
        self.assertEqual((max(u['low_ticks'] for u in units[a:z+1]),
                          min(u['high_ticks'] for u in units[a:z+1])), core)
        self.assertEqual((units[z]['end_ticks'], audit['counts'][proof]), (end, count))
        self.assertFalse(audit['automatic_first_point_proven'])
        self.assertFalse(audit['complete_lower_level_proven'])

    def test_e1_81_discovery_whole_membership_and_formed_snapshot_stay_distinct(self):
        audit, case, units = self.inputs()
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        result = tool.scan({'rows': case['raw_rows']}, granularity='60m', standard='81')
        item, = result['rounds']
        self.assertEqual((item['first_raw_count'], item['formation']['resolution']['first_raw_count']), (311, 614))
        self.assertEqual(tuple(item['formation']['center']['zn']), audit['whole'][0])
        for name in ('formed', 'whole'):
            zn, core, envelope, _ = audit[name]
            center = dict(zn=list(zn), zd=core[0], zg=core[1])
            actual = tool.enumerate_attempts(units, center)
            self.assertEqual(tuple((x['leave'], x['pull'], x['margin_ticks']) for x in actual),
                             audit[name+'_attempts'])
            self.assertEqual(min(u['low_ticks'] for u in units[zn[0]:zn[-1]+1]), envelope[0])
            self.assertEqual(max(u['high_ticks'] for u in units[zn[0]:zn[-1]+1]), envelope[1])
        rows = [r for r in case['raw_rows'] if r['dt'][:10] >= '2019-03-15']
        sub = tool.scan({'rows': rows}, granularity='60m', standard='81')['rounds'][0]
        self.assertEqual((sub['first_raw_count'], sub['formation']['resolution']['first_raw_count']), (261, 564))
        self.assertEqual(sub['first_dt'], item['first_dt'])
        self.assertEqual(sub['formation']['resolution']['first_dt'], item['formation']['resolution']['first_dt'])
        self.assertEqual(len(case['raw_rows'])-len(rows), 50)


class TestE1CompleteTypes81Assets(unittest.TestCase):
    """从整数切分和原始前缀独立核证完整F1/F2，不继承辅助点位标签。"""

    @staticmethod
    def inputs():
        tree = ast.parse((ROOT / 'tests/test_real_causal_formation.py').read_text())
        audit = next(ast.literal_eval(n.value) for n in tree.body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                     and t.id == 'E1_81_F1_GATE_AUDIT' for t in n.targets))
        source, case, units = TestE1Formation81Assets.inputs()
        tool = compiler(ROOT / 'validation/tools/gen_real_f1_originals.py')
        records = [tool.move_record(units, spec) for spec in audit['f1_specs']]
        return audit, source, case, units, records, tool

    def test_f1_integer_cuts_first_intersections_and_successors_cover_the_source(self):
        audit, source, _, units, records, _ = self.inputs()
        covered = []
        for spec, record, count in zip(audit['f1_specs'], records, audit['f1_counts']):
            a, z, _, _, triples, cores, proof = spec
            covered.extend(range(a, z+1))
            self.assertGreaterEqual(z-a+1, 3)
            self.assertEqual(proof, z+1)
            self.assertEqual(source['counts'][proof], count)
            for j in range(a, triples[0]):
                self.assertGreater(max(u['low_ticks'] for u in units[j:j+3]),
                                   min(u['high_ticks'] for u in units[j:j+3]))
            for j, core in zip(triples, cores):
                self.assertEqual((max(u['low_ticks'] for u in units[j:j+3]),
                                  min(u['high_ticks'] for u in units[j:j+3])), core)
            if len(cores) > 1:
                self.assertEqual(record['kind'], 'down')
                self.assertLess(cores[1][1], cores[0][0])
                self.assertTrue(all(u['high_ticks'] < cores[0][0]
                                    for u in units[triples[1]:z+1]))
            self.assertLessEqual(units[proof]['low_ticks'], cores[-1][1])
            self.assertGreaterEqual(units[proof]['high_ticks'], cores[-1][0])
        self.assertEqual(covered, list(range(37)))
        self.assertEqual(len(units), 38)
        self.assertEqual(audit['f1_tail'][:2], (37, 37))
        # 最后一项先有三段空交集8格，不能机械地按每三笔分一项。
        self.assertEqual(max(u['low_ticks'] for u in units[33:36])-
                         min(u['high_ticks'] for u in units[33:36]), 8)
        for left, right in zip(records, records[1:]):
            self.assertEqual((left['end_dt'], left['end_ticks']),
                             (right['start_dt'], right['start_ticks']))

    def test_all_630_raw_prefixes_confirm_f1_and_f2_only_at_successor_proof(self):
        audit, _, case, _, records, tool = self.inputs()
        first, first_f2 = {}, None
        for count in range(1, len(case['raw_rows'])+1):
            rows = case['raw_rows'][:count]
            bis = tool.foundation(rows, '81')[2][:-1]
            units = tool.components(rows, bis, dt_slice=None)
            visible = []
            for i, spec in enumerate(audit['f1_specs']):
                if len(units) > spec[-1]:
                    record = tool.move_record(units, spec)
                    self.assertEqual(record, records[i])
                    visible.append(record)
                    first.setdefault(i, count)
            self.assertEqual(len(visible), sum(n <= count for n in audit['f1_counts']))
            if len(visible) > audit['f2'][-1]:
                higher = tool.move_record(visible, audit['f2'])
                first_f2 = count if first_f2 is None else first_f2
                self.assertEqual((higher['seg_start'], higher['seg_end'], higher['kind']), (0, 7, 'down'))
                self.assertEqual((higher['low_ticks'], higher['high_ticks']), audit['f2_composition_range'])
                self.assertEqual((higher['start_ticks'], higher['end_ticks']), audit['f2_body_endpoints'])
        self.assertEqual(tuple(first[i] for i in range(11)), audit['f1_counts'])
        self.assertEqual(first_f2, audit['f2_known'])
        self.assertEqual(max(audit['f1_counts'][:8]), 464)
        self.assertEqual(audit['f1_counts'][8], 510)
        body, proof = records[7], records[8]
        core = audit['f2'][5][-1]
        self.assertEqual(body['low_ticks']-core[1], 2)
        self.assertEqual(core[1]-proof['low_ticks'], 3)
        tail = tool.move_record(records, audit['f2_tail'])
        self.assertFalse(tail['complete'])
        self.assertEqual(tail['centers_ticks'], [[1460, 1505]])
        delayed_index, known, evidence_count = audit['delayed_proof']
        clocks = list(audit['f1_counts'])
        clocks[delayed_index] = known
        self.assertEqual(sum(t < known for t in clocks), 8)
        self.assertEqual(sum(t <= known for t in clocks), evidence_count)

    def test_missing_B_reverse_tail_is_a_skip_not_a_force_or_macd_verdict(self):
        audit, source, _, units, records, _ = self.inputs()
        self.assertEqual(audit['f2_spans'], ((0, 2, 3), (4, 6, 6)))
        # A在成形后的2/3中有净向上回试2；B只到成形6，净向下而非反向尾段。
        self.assertLess(records[2]['start_ticks'], records[2]['end_ticks'])
        self.assertGreater(records[6]['start_ticks'], records[6]['end_ticks'])
        self.assertEqual(audit['f2_spans'][1][1:], (6, 6))
        self.assertEqual(audit['skip'], 'no_comparable_center_tail')
        for span, expected in zip(audit['f2_spans'], audit['f2_composition_waves']):
            a, _, z = span
            self.assertEqual((min(r['low_ticks'] for r in records[a:z+1]),
                              max(r['high_ticks'] for r in records[a:z+1])), expected)
        self.assertEqual(audit['f2_composition_waves'][1][1]-
                         audit['f2_composition_waves'][0][0], 127)
        self.assertEqual(source['b_c_proof'], (11, 15, 16))
        containing = [next((r['seg_start'], r['seg_end']) for r in records
                           if r['seg_start'] <= i <= r['seg_end'])
                      for i in source['b_c_proof'][:2]]
        self.assertEqual(containing, [(9, 14), (15, 17)])
        self.assertEqual(units[15]['end_ticks'], 1378)
        self.assertNotEqual(audit['f2_body_endpoints'][-1], units[15]['end_ticks'])
        self.assertFalse(audit['theoretical_level_proven'])


class TestPointPacketAdmissionAssets(unittest.TestCase):
    """运行时单包验收与冻结独立表对账，不将运行结果称为独立标注。"""

    @staticmethod
    def checker():
        prior = list(sys.path)
        try:
            spec = importlib.util.spec_from_file_location(
                'point_packet_runtime_assets', ROOT / 'validation/tools/verify_points_history.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.path[:] = prior

    @staticmethod
    def packet():
        path = ROOT / 'validation/chan-real-159915-60m-20190301-20190901-input.json'
        return path, json.loads(path.read_text())

    def test_packet_replays_the_independent_E1_complete_type_admission_table(self):
        checker = self.checker()
        _, packet = self.packet()
        before = copy.deepcopy(packet)
        audit = TestE1CompleteTypes81Assets.inputs()[0]
        result = checker.check_packet(packet, standard='81')
        self.assertEqual(packet, before)
        self.assertEqual(result['raw_prefixes'], 630)
        self.assertEqual(result['consumer_batches'], 12)
        self.assertEqual(result['annotation'], 'runtime_discovery_not_independent_labels')
        self.assertFalse(result['theoretical_acceptance'])
        self.assertEqual(tuple(r['raw_count'] for r in result['f1']), audit['f1_counts'])
        self.assertEqual([r['part_span'] for r in result['f1']],
                         [list(s[:2]) for s in audit['f1_specs']])
        for item, spec in zip(result['f1'], audit['f1_specs']):
            self.assertEqual(len(item['snapshot']['unit_ids']), spec[1]-spec[0]+1)
            self.assertEqual(len(item['snapshot']['evidence_ids']), spec[-1]+1)
        first = next(b for b in result['batches'] if b['f2'])
        self.assertEqual(first['raw_count'], audit['f2_known'])
        move, = first['f2']
        self.assertEqual((move['kind'], len(move['unit_ids']), len(move['evidence_ids'])), ('down', 8, 9))
        self.assertEqual(move['confirmed_dt'], '2019-07-29 15:01:00')
        final = result['batches'][-1]
        self.assertEqual(final['strict']['results'], [])
        self.assertEqual(final['strict']['skipped'][0][1], audit['skip'])
        self.assertEqual(final['auxiliary']['exclusions'][0][1], audit['skip'])
        self.assertEqual(final['chain']['formations'], [])
        self.assertEqual(result['checks']['future_poison_checks'], 12)
        self.assertEqual(result['checks']['before_arrival_checks'], 12)

    def test_packet_rejects_mixed_scope_bad_prices_factors_and_time_without_mutation(self):
        checker = self.checker()
        _, original = self.packet()
        changes = [
            lambda p: p.__setitem__('rows', []),
            lambda p: p['rows'].__setitem__(1, copy.deepcopy(p['rows'][0])),
            lambda p: p['rows'].__setitem__(0, dict(p['rows'][0], dt='2019-03-02 09:30:00')),
            lambda p: p['rows'][0].__setitem__('ts_code', 'other'),
            lambda p: p['rows'][0].__setitem__('adj_factor', None),
            lambda p: p['rows'][1].__setitem__('adj_factor', 2),
            lambda p: p['rows'][0].__setitem__('open', float('nan')),
            lambda p: p['rows'][0].__setitem__('low', p['rows'][0]['high']+1),
            lambda p: p['rows'][0].__setitem__('vol', -1),
            lambda p: p.__setitem__('timezone', 'UTC'),
            lambda p: p.__setitem__('adjustment', 'pre'),
            lambda p: p['sampling_rule'].__setitem__('codes', ['a', 'b']),
            lambda p: p['sampling_rule'].__setitem__('periods', ['1d']),
            lambda p: p['sampling_rule'].__setitem__('window', ['2019-03-01', '2019-03-01']),
        ]
        for i, mutate in enumerate(changes):
            with self.subTest(change=i):
                broken = copy.deepcopy(original)
                mutate(broken)
                before = json.dumps(broken, sort_keys=True)
                with self.assertRaises(ValueError):
                    checker.check_packet(broken)
                self.assertEqual(json.dumps(broken, sort_keys=True), before)

    def test_positive_constant_factor_zero_volume_daily_clock_and_xd_scope_are_explicit(self):
        checker = self.checker()
        _, packet = self.packet()
        packet['rows'] = packet['rows'][:3]
        for row in packet['rows']:
            row['adj_factor'] = 1.455
        packet['rows'][0]['vol'] = 0
        original = copy.deepcopy(packet)
        bars, metadata = checker._packet_bars(packet)
        self.assertEqual(metadata['factor'], 1.455)
        self.assertEqual(bars[0]['volume'], 0)
        self.assertEqual(bars[0]['close'], packet['rows'][0]['close'])
        self.assertEqual(str(bars[0]['available_dt']), '2019-03-01 09:31:00')
        result = checker.check_packet(packet, parts='xd', standard='81')
        self.assertEqual(result['xd_origin'], 'legacy_default')
        self.assertEqual(result['raw_prefixes'], 3)
        self.assertEqual(result['consumer_batches'], 1)
        self.assertFalse(result['theoretical_acceptance'])
        self.assertEqual(packet, original)
        daily = json.loads((ROOT / 'validation/chan-real-512880-day-20170901-20180401-input.json').read_text())
        daily['rows'] = daily['rows'][:3]
        bars, _ = checker._packet_bars(daily)
        self.assertEqual(str(bars[0]['available_dt']), '2017-09-01 15:05:00')

    def test_packet_cli_works_from_other_cwd_and_refuses_both_receipt_overwrite_paths(self):
        checker = self.checker()
        original, packet = self.packet()
        untouched = original.read_bytes()
        script = ROOT / 'validation/tools/verify_points_history.py'
        with tempfile.TemporaryDirectory() as temp:
            packet['dataset'] = str(Path(temp) / 'not-a-readable-dataset')
            source = Path(temp) / 'original packet.json'
            source.write_text(json.dumps(packet))
            frozen = source.read_bytes()
            output = Path(temp) / 'new receipt.json'
            cmd = [sys.executable, str(script), '--packet', str(source), '--standard', '81', '--output', str(output)]
            run = subprocess.run(cmd, cwd=temp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            raw = output.read_bytes()
            report = json.loads(raw)
            self.assertEqual(report['packet'], str(source.resolve()))
            self.assertEqual(report['packet_sha256'], checker.digest(source))
            self.assertEqual(len(report['source_sha256']), 41)
            self.assertTrue(Path(report['chan_path']).is_absolute())
            for command in (cmd, [sys.executable, str(script), str(Path(temp)/'missing-dataset'), '--output', str(output)]):
                run = subprocess.run(command, cwd=temp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('拒绝覆盖', run.stderr)
                self.assertEqual(output.read_bytes(), raw)
            base = [sys.executable, str(script), str(Path(temp)/'missing-dataset')]
            for flags in (['--packet', str(source)], ['--standard', '81']):
                run = subprocess.run(base+flags+['--output', str(Path(temp)/'bad.json')], cwd=temp,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((Path(temp)/'bad.json').exists())
            self.assertEqual(source.read_bytes(), frozen)
        self.assertEqual(original.read_bytes(), untouched)


class TestRealRoundsDiscovery(unittest.TestCase):
    """发现工具复用冻结结构；改变笔标准须同时改变实际前缀确认。"""

    @staticmethod
    def factor_packet():
        return dict(adjustment='none', timezone='Asia/Shanghai',
                    sampling_rule={'periods': ['1d'], 'window': ['2022-09-26', '2022-09-28']},
                    rows=[dict(dt=dt, open=10.25, high=11.1, low=9.3, close=10.75,
                               vol=volume, adj_factor=factor)
                          for dt, volume, factor in [('2022-09-26', 0, 1.003886),
                              ('2022-09-27', 200, 1.003886), ('2022-09-28', 300, 1.005408)]])

    def test_factor_product_is_exact_at_every_observation_not_quote_rounded(self):
        """逐观察价用Fraction直接复算; 数量和因子不改, 不把坐标当实际报价。"""
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        packet = self.factor_packet()
        original = copy.deepcopy(packet)
        view, metadata = tool.price_coordinate(packet, 'factor-product')
        self.assertEqual(metadata['price_multiplier'], 1000000)
        self.assertEqual(metadata['source_factor_values'], ['1.003886', '1.005408'])
        for count in range(1, 4):
            prefix, _ = tool.price_coordinate(dict(packet, rows=packet['rows'][:count]),
                                              'factor-product')
            self.assertEqual(prefix, view[:count])
            anchor = Fraction(str(packet['rows'][count-1]['adj_factor']))
            for raw, adjusted in zip(packet['rows'][:count], prefix):
                self.assertEqual(adjusted['vol'], raw['vol'])
                self.assertEqual(adjusted['adj_factor'], raw['adj_factor'])
                for key in ('open', 'high', 'low', 'close'):
                    expected = Fraction(str(raw[key])) * Fraction(str(raw['adj_factor'])) / anchor
                    self.assertEqual(Fraction(str(adjusted[key])) / 1000000 / anchor, expected)
        self.assertEqual(packet, original)
        with self.assertRaises(ValueError):
            tool.scan(packet)  # 默认仍拒绝变因子, 不隐式开启新视图。

    def test_factor_product_has_no_future_precision_or_factor_dependency(self):
        """已截前缀不读未来因子, 倍率不靠未来行精度决定。"""
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        packet = self.factor_packet()
        expected, _ = tool.price_coordinate(dict(packet, rows=packet['rows'][:2]),
                                           'factor-product')
        for value in (float('nan'), 1.000000000001):
            packet['rows'][2]['adj_factor'] = value
            self.assertEqual(tool.price_coordinate(dict(packet, rows=packet['rows'][:2]),
                'factor-product')[0], expected)
            with self.assertRaises(ValueError):
                tool.price_coordinate(packet, 'factor-product')

    def test_factor_product_rejects_unknown_contract_bad_values_and_time(self):
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        for field, value in [('adj_factor', None), ('adj_factor', True),
                ('adj_factor', -1), ('adj_factor', float('inf')), ('open', '10'),
                ('close', float('nan')), ('vol', -1), ('low', 12),
                ('dt', '2022-09-26'), ('dt', '2022-09-27 12:00:00')]:
            with self.subTest(field=field, value=value):
                packet = self.factor_packet()
                packet['rows'][1][field] = value
                with self.assertRaises(ValueError):
                    tool.price_coordinate(packet, 'factor-product')
        for field, value in [('adjustment', 'pre'), ('timezone', 'UTC'),
                              ('sampling_rule', {'periods': ['30m']})]:
            packet = self.factor_packet(); packet[field] = value
            with self.assertRaises(ValueError):
                tool.price_coordinate(packet, 'factor-product')
        with self.assertRaises(ValueError):
            tool.scan(self.factor_packet(), granularity='30m', coordinate='factor-product')
        with self.assertRaises(ValueError):
            tool.price_coordinate(self.factor_packet(), 'unknown')

    def test_factor_product_precision_bounds_reject_instead_of_rounding(self):
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        for price in (1e8, 1e-10):
            packet = self.factor_packet()
            for row in packet['rows']:
                row.update(open=price, high=price, low=price, close=price, adj_factor=1)
            with self.assertRaises(ValueError):
                tool.price_coordinate(packet, 'factor-product')
        packet = self.factor_packet()
        for row in packet['rows']:
            row.update(open=9000001, high=9000001, low=9000001, close=9000001,
                       adj_factor=1.000000001)
        with self.assertRaisesRegex(ValueError, '保真'):
            tool.price_coordinate(packet, 'factor-product')
        packet = self.factor_packet()
        for row in packet['rows']:
            row.update(open=2e-8, high=3e-8, low=1e-8, close=2e-8, adj_factor=0.1)
        view, _ = tool.price_coordinate(packet, 'factor-product')
        self.assertEqual([view[0]['low'], view[0]['high']], [0.001, 0.003])

    def test_factor_product_cli_requires_opt_in_and_records_inverse_coordinate(self):
        tool = ROOT / 'validation/tools/scan_real_rounds.py'
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'packet.json'
            source.write_text(json.dumps(self.factor_packet()))
            untouched = source.read_bytes(); output = Path(temp) / 'scan.json'
            command = [sys.executable, str(tool), '--packet', str(source), '--output', str(output)]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            result = subprocess.run(command + ['--coordinate', 'factor-product'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['factor_coordinate']['kind'], 'factor-product')
            self.assertEqual(report['factor_coordinate']['ticks_per_price_factor'], 1000000000)
            self.assertIn('observation_n_price', report['factor_coordinate']['rule'])
            self.assertEqual(source.read_bytes(), untouched)

    def test_both_standards_match_frozen_structure_and_confirmation(self):
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        labels = json.loads(
            (ROOT / 'tests/fixtures/real_f1_originals.json').read_text())
        different = False
        for case in labels['cases']:
            different = different or (case['foundation_81']['bis'] !=
                                      case['foundation_106']['bis'])
            for standard in ('81', '106'):
                with self.subTest(window=case['window_key'], standard=standard):
                    result = tool.scan({'rows': case['raw_rows']},
                                       standard=standard)
                    self.assertEqual(result['bis'],
                                     case['foundation_' + standard]['bis'])
                    observations = sorted(
                        (int(count), observation[standard]['fixed_bis'])
                        for count, observation in case['observations'].items())
                    for i, unit in enumerate(result['units']):
                        count, fixed = next((count, fixed)
                                            for count, fixed in observations
                                            if len(fixed) > i)
                        self.assertEqual(unit['confirmed_raw_count'], count)
                        self.assertEqual(unit['confirmed_dt'],
                                         case['raw_rows'][count - 1]['dt'][:10]
                                         + ' 15:05:00')
                        self.assertEqual(
                            {k: v for k, v in unit.items()
                             if not k.startswith('confirmed_')}, fixed[i])
        self.assertTrue(different, '样本须实际覆盖81/106不同笔链')

    def test_default_standard_preserves_frozen_106_round(self):
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        case = manual_cases()[0]
        _, packet = packet_of(case)
        result = tool.scan(packet)
        self.assertEqual(result, tool.scan(packet, standard='106'))
        self.assertEqual(len(result['rounds']), 1)
        item = result['rounds'][0]
        self.assertEqual(item['side'], 'buy1')
        self.assertEqual(item['first_dt'], '2018-01-02 15:05:00')
        self.assertEqual(item['formation']['outcome'], 'failed')
        self.assertIsNone(item['handover'])
        with self.assertRaisesRegex(ValueError, '笔标准'):
            tool.scan(packet, standard='unknown')

    def test_positive_constant_factor_is_identity_without_mutating_source(self):
        """当行/观察末因子恒相等, 任意正恒因子不改变原价或冻结结构。"""
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        _, original = packet_of(manual_cases()[0])
        for standard in ('81', '106'):
            expected = tool.scan(original, standard=standard)
            for factor in (1.455, 6.66401, 0.25):
                with self.subTest(standard=standard, factor=factor):
                    packet = copy.deepcopy(original)
                    for row in packet['rows']:
                        row['adj_factor'] = factor
                    untouched = copy.deepcopy(packet)
                    self.assertEqual(tool.constant_factor(packet['rows']), factor)
                    self.assertEqual(tool.scan(packet, standard=standard), expected)
                    self.assertEqual(packet, untouched)
                    self.assertEqual(packet['rows'][-1]['adj_factor'], factor)

    def test_factor_changes_and_invalid_factors_are_not_normalized_or_filled(self):
        """只放行恒因子恒等坐标, 不放行跳变、微小差值或缺因子。"""
        tool = compiler(ROOT / 'validation/tools/scan_real_rounds.py')
        _, original = packet_of(manual_cases()[0])
        for value in (None, 0, -1, float('nan'), float('inf'), True, '1',
                      1 + 1e-12):
            with self.subTest(value=value):
                packet = copy.deepcopy(original)
                packet['rows'][len(packet['rows']) // 2]['adj_factor'] = value
                with self.assertRaises(ValueError):
                    tool.scan(packet)
        packet = copy.deepcopy(original)
        del packet['rows'][0]['adj_factor']
        with self.assertRaises(ValueError):
            tool.scan(packet)
        with self.assertRaises(ValueError):
            tool.scan({'rows': []})

    def test_cli_records_selected_standard_and_preserves_existing_output(self):
        labels = json.loads(
            (ROOT / 'tests/fixtures/real_f1_originals.json').read_text())
        case = labels['cases'][0]
        tool = ROOT / 'validation/tools/scan_real_rounds.py'
        with tempfile.TemporaryDirectory() as temp:
            packet = json.loads(
                (ROOT / 'validation' / case['source']['packet']).read_text())
            for row in packet['rows']:
                row['adj_factor'] = 1.455
            source = Path(temp) / 'packet.json'
            source.write_text(json.dumps(packet))
            original = source.read_bytes()
            output = Path(temp) / 'scan.json'
            command = [sys.executable, str(tool), '--packet',
                       str(source),
                       '--output', str(output), '--standard', '81']
            run = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            frozen = output.read_bytes()
            report = json.loads(frozen.decode('utf-8'))
            self.assertEqual(report['standard'], '81')
            self.assertEqual(report['factor_coordinate']['source_factor'], 1.455)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(report['bis'], case['foundation_81']['bis'])
            self.assertEqual(report['annotation'],
                             'rounds_discovery_scan_not_labels')
            run = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(output.read_bytes(), frozen)


if __name__ == '__main__':
    unittest.main()
