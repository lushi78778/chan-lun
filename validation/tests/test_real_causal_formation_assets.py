# -*- coding: utf-8 -*-
"""因果底顶冻结标注与轮次发现工具的独立算术、确认和来源契约。"""
import ast
import copy
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


class TestRealRoundsDiscovery(unittest.TestCase):
    """发现工具复用冻结结构；改变笔标准须同时改变实际前缀确认。"""

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

    def test_cli_records_selected_standard_and_preserves_existing_output(self):
        labels = json.loads(
            (ROOT / 'tests/fixtures/real_f1_originals.json').read_text())
        case = labels['cases'][0]
        tool = ROOT / 'validation/tools/scan_real_rounds.py'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'scan.json'
            command = [sys.executable, str(tool), '--packet',
                       str(ROOT / 'validation' / case['source']['packet']),
                       '--output', str(output), '--standard', '81']
            run = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            frozen = output.read_bytes()
            report = json.loads(frozen.decode('utf-8'))
            self.assertEqual(report['standard'], '81')
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
