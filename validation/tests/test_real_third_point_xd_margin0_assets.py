# -*- coding: utf-8 -*-
"""0.9.8 xd级触沿允许(margin=0)三类买卖点标注的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'validation/tools/gen_real_third_point.py'
MANUAL = ROOT / 'validation/chan-real-third-point-manual-0.9.8.json'
FIXTURE = ROOT / 'tests/fixtures/real_third_point_xd_margin0.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_third_point_xd_margin0_compiler', TOOL)
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


class TestRealThirdPointXdMarginZeroAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['annotation'],
                         'third_point_real_xd_margin0_established')
        self.assertEqual(labels['schema_version'],
                         'chan-real-third-point-v1')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'M1', 'M2'})
        granularities = {'M1': '30m', 'M2': '5m'}
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
        for path in (TOOL, ROOT / 'validation/tools/gen_real_f1_originals.py'):
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

    def test_reject_corrupt_m1_center_and_attempt_tables(self):
        """M1中枢算术、xd级触沿成立台账被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'M1'][0]
        path, data = packet_of(case)
        changes = [
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1091)),
            ('xd_events_parity',
             lambda c: c['xd_events'][0].__setitem__(1, 4)),
            ('xd_events_mode',
             lambda c: c['xd_events'][0].__setitem__(2, 3)),
            ('xd_events_proof',
             lambda c: c['xd_events'][0].__setitem__(3, 3)),
            ('zn_step', lambda c: c['centers']['A']['zn'].__setitem__(1, 50)),
            ('zd', lambda c: c['centers']['A'].__setitem__('zd', 1040)),
            ('dd', lambda c: c['centers']['A'].__setitem__('dd', 1010)),
            ('A_closed_by',
             lambda c: c['centers']['A'].__setitem__('closed_by', 8)),
            ('A_frozen',
             lambda c: c['centers']['A'].__setitem__('frozen_by_departure',
                                                     True)),
            ('B_closed_by',
             lambda c: c['centers']['B'].__setitem__('closed_by', 38)),
            ('A_attempt_dropped',
             lambda c: c['attempts']['A'].pop()),
            ('A_outcome',
             lambda c: c['attempts']['A'][-1].__setitem__('outcome', 'fail')),
            ('A_point',
             lambda c: c['attempts']['A'][-1].__setitem__('point_ticks',
                                                          1040)),
            ('A_margin_zero_to_one',
             lambda c: c['attempts']['A'][-1].__setitem__('margin_ticks', 1)),
            ('B_side',
             lambda c: c['attempts']['B'][0].__setitem__('side', 'sell3')),
            ('B_leave',
             lambda c: c['attempts']['B'][0].__setitem__('leave', 34)),
            ('B_pull',
             lambda c: c['attempts']['B'][0].__setitem__('pull', 37)),
            ('granularity_removed', lambda c: c.pop('granularity')),
            ('granularity_day',
             lambda c: c.__setitem__('granularity', 'day')),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)

    def test_reject_corrupt_m2_margin0_and_new_center_tables(self):
        """M2触沿台账、B新生中枢与xd事件表被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'M2'][0]
        path, data = packet_of(case)
        changes = [
            ('xd_events_adjacency',
             lambda c: c['xd_events'][5].__setitem__(
                 0, c['xd_events'][5][0] + 1)),
            ('xd_events_mode',
             lambda c: c['xd_events'][0].__setitem__(2, 3)),
            ('zn_step', lambda c: c['centers']['A']['zn'].__setitem__(1, 5)),
            ('A_zd', lambda c: c['centers']['A'].__setitem__('zd', 690)),
            ('A_closed_by',
             lambda c: c['centers']['A'].__setitem__('closed_by', 9)),
            ('A_frozen',
             lambda c: c['centers']['A'].__setitem__('frozen_by_departure',
                                                     True)),
            ('B_zn_truncated',
             lambda c: c['centers']['B']['zn'].__delitem__(-1)),
            ('B_closed_by',
             lambda c: c['centers']['B'].__setitem__('closed_by', 26)),
            ('A_outcome',
             lambda c: c['attempts']['A'][-1].__setitem__('outcome', 'fail')),
            ('A_side',
             lambda c: c['attempts']['A'][-1].__setitem__('side', 'sell3')),
            ('A_point',
             lambda c: c['attempts']['A'][-1].__setitem__('point_ticks',
                                                          1099)),
            ('A_margin_zero_to_one',
             lambda c: c['attempts']['A'][-1].__setitem__('margin_ticks', 1)),
            ('A_first_margin',
             lambda c: c['attempts']['A'][0].__setitem__('margin_ticks', -88)),
            ('A_first_leave',
             lambda c: c['attempts']['A'][0].__setitem__('leave', 28)),
            ('B_attempt_dropped',
             lambda c: c['attempts']['B'].pop()),
            ('B_leave',
             lambda c: c['attempts']['B'][0].__setitem__('leave', 33)),
            ('B_pull',
             lambda c: c['attempts']['B'][0].__setitem__('pull', 37)),
            ('B_established_margin',
             lambda c: c['attempts']['B'][-1].__setitem__('margin_ticks',
                                                          3)),
            ('granularity_removed', lambda c: c.pop('granularity')),
            ('granularity_day',
             lambda c: c.__setitem__('granularity', 'day')),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)


if __name__ == '__main__':
    unittest.main()
