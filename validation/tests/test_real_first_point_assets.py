# -*- coding: utf-8 -*-
"""0.9.9 一类买卖点标注的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'validation/tools/gen_real_first_point.py'
MANUAL = ROOT / 'validation/chan-real-first-point-manual-0.9.9.json'
FIXTURE = ROOT / 'tests/fixtures/real_first_point.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_first_point_compiler', TOOL)
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


class TestRealFirstPointAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['annotation'],
                         'manual_first_point_real_strict_completed_divergence')
        self.assertEqual(labels['schema_version'],
                         'chan-real-first-point-v1')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'B1', 'C1', 'D1', 'X1', 'Y1'})
        granularities = {'B1': 'day', 'C1': 'day', 'D1': '60m',
                         'X1': '60m', 'Y1': '5m'}
        for case in labels['cases']:
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
            self.assertEqual(case.get('granularity', 'day'),
                             granularities[case['window_key']])
            data = json.loads(packet.read_text())
            self.assertEqual(data['rows'], case['raw_rows'])
            self.assertEqual(
                data['manifest_sha256'],
                case['source']['dataset_manifest_sha256'])
        for path in (TOOL, ROOT / 'validation/tools/gen_real_strict_trend.py',
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

    def test_reject_corrupt_b1_strict_trend_and_first_point_tables(self):
        """B1严格趋势角色、台账与一类裁定表被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'B1'][0]
        path, data = packet_of(case)
        changes = [
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1091)),
            ('trend_status',
             lambda c: c['trend'].__setitem__('status', 'ongoing')),
            ('trend_direction',
             lambda c: c['trend'].__setitem__('direction', 'up')),
            ('a_zn_step',
             lambda c: c['roles']['A']['zn'].__setitem__(1, 3)),
            ('A_zd', lambda c: c['roles']['A'].__setitem__('zd', 1100)),
            ('A_dd', lambda c: c['roles']['A'].__setitem__('dd', 1090)),
            ('A_closed_by',
             lambda c: c['roles']['A'].__setitem__('closed_by', 6)),
            ('b_unit',
             lambda c: c['roles']['b'].__setitem__('unit', 2)),
            ('B_zd', lambda c: c['roles']['B'].__setitem__('zd', 1060)),
            ('B_frozen_to_closed',
             lambda c: c['roles']['B'].__setitem__('closed_by', 10)),
            ('B_frozen_removed',
             lambda c: c['roles']['B'].__setitem__(
                 'frozen_by_departure', False)),
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
            ('fp_area_c',
             lambda c: c['first_point'].__setitem__('area_c', 0.0)),
            ('fp_zero_axis',
             lambda c: c['first_point'].__setitem__('zero_axis', 0.013)),
            ('fp_prior_extreme',
             lambda c: c['first_point'].__setitem__('prior_extreme_ticks',
                                                    1020)),
            ('fp_c_extreme',
             lambda c: c['first_point'].__setitem__('c_extreme_ticks',
                                                    1013)),
            ('fp_new_extreme',
             lambda c: c['first_point'].__setitem__('new_extreme', False)),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)

    def test_reject_corrupt_frozen_window_first_point_tables(self):
        """C1/D1/X1/Y1一类裁定表被篡改时直接拒绝。"""
        tool = compiler()
        for case in manual_cases():
            if case['window_key'] == 'B1':
                continue
            path, data = packet_of(case)
            changes = [
                ('fp_side',
                 lambda c: c['first_point'].__setitem__(
                     'side', 'buy1' if c['first_point']['side'] == 'sell1'
                     else 'sell1')),
                ('fp_verdict',
                 lambda c: c['first_point'].__setitem__(
                     'verdict',
                     'not_established'
                     if c['first_point']['verdict'] == 'established'
                     else 'established')),
                ('fp_reason',
                 lambda c: c['first_point'].__setitem__(
                     'reason',
                     None if c['first_point']['reason'] is not None
                     else 'no_divergence')),
                ('fp_area_b',
                 lambda c: c['first_point'].__setitem__(
                     'area_b', c['first_point']['area_b'] + 0.001)),
                ('fp_area_c',
                 lambda c: c['first_point'].__setitem__(
                     'area_c', c['first_point']['area_c'] + 0.001)),
                ('fp_zero_axis',
                 lambda c: c['first_point'].__setitem__(
                     'zero_axis', c['first_point']['zero_axis'] + 0.001)),
                ('fp_new_extreme',
                 lambda c: c['first_point'].__setitem__(
                     'new_extreme', not c['first_point']['new_extreme'])),
            ]
            for name, mutate in changes:
                with self.subTest(window=case['window_key'], name=name):
                    broken = copy.deepcopy(case)
                    mutate(broken)
                    with self.assertRaises(ValueError):
                        tool.compile_case(broken, data, path)


if __name__ == '__main__':
    unittest.main()
