# -*- coding: utf-8 -*-
"""0.9.5三类买卖点真实正反例标注的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'tools/gen_real_third_point.py'
MANUAL = ROOT / 'validation/chan-real-third-point-manual-0.9.5.json'
FIXTURE = ROOT / 'tests/fixtures/real_third_point.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_third_point_compiler', TOOL)
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


class TestRealThirdPointAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['schema_version'],
                         'chan-real-third-point-v1')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'T1', 'T2', 'T3', 'T4'})
        granularities = {'T1': '60m', 'T2': '60m', 'T3': '60m', 'T4': 'day'}
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
        for path in (TOOL, ROOT / 'tools/gen_real_f1_originals.py'):
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

    def test_reject_corrupt_center_and_attempt_tables(self):
        """T2中枢算术、冻结互斥、尝试台账被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'T2'][0]
        path, data = packet_of(case)
        changes = [
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1208)),
            ('zn_step', lambda c: c['centers']['A']['zn'].__setitem__(1, 3)),
            ('zd', lambda c: c['centers']['A'].__setitem__('zd', 1208)),
            ('dd', lambda c: c['centers']['A'].__setitem__('dd', 1191)),
            ('A_closed_by',
             lambda c: c['centers']['A'].__setitem__('closed_by', 7)),
            ('A_frozen',
             lambda c: c['centers']['A'].__setitem__('frozen_by_departure',
                                                     True)),
            ('B_frozen_removed',
             lambda c: c['centers']['B'].pop('frozen_by_departure')),
            ('B_frozen_non_bool',
             lambda c: c['centers']['B'].__setitem__('frozen_by_departure',
                                                     1)),
            ('B_closed_by',
             lambda c: c['centers']['B'].__setitem__('closed_by', 10)),
            ('A_attempt_dropped',
             lambda c: c['attempts']['A'].pop()),
            ('A_outcome',
             lambda c: c['attempts']['A'][0].__setitem__('outcome', 'fail')),
            ('A_point',
             lambda c: c['attempts']['A'][0].__setitem__('point_ticks',
                                                         1164)),
            ('A_margin',
             lambda c: c['attempts']['A'][0].__setitem__('margin_ticks', 45)),
            ('B_side',
             lambda c: c['attempts']['B'][0].__setitem__('side', 'buy3')),
            ('B_leave',
             lambda c: c['attempts']['B'][0].__setitem__('leave', 8)),
            ('B_pull',
             lambda c: c['attempts']['B'][0].__setitem__('pull', 11)),
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

    def test_reject_corrupt_pending_and_context_tables(self):
        """T4 pending结构与T3上下文中枢被篡改时直接拒绝。"""
        tool = compiler()
        t4 = [c for c in manual_cases() if c['window_key'] == 'T4'][0]
        path4, data4 = packet_of(t4)
        changes4 = [
            ('pending_pull',
             lambda c: c['attempts']['B'][0].__setitem__('pull', 10)),
            ('pending_point',
             lambda c: c['attempts']['B'][0].__setitem__('point_ticks',
                                                         4400)),
            ('pending_margin',
             lambda c: c['attempts']['B'][0].__setitem__('margin_ticks', 1)),
            ('pending_side',
             lambda c: c['attempts']['B'][0].__setitem__('side', 'sell3')),
            ('pending_leave',
             lambda c: c['attempts']['B'][0].__setitem__('leave', 8)),
            ('pending_outcome',
             lambda c: c['attempts']['B'][0].__setitem__('outcome', 'fail')),
            ('B_closed_by',
             lambda c: c['centers']['B'].__setitem__('closed_by', 10)),
            ('B_frozen',
             lambda c: c['centers']['B'].__setitem__('frozen_by_departure',
                                                     True)),
        ]
        for name, mutate in changes4:
            with self.subTest(name=name):
                broken = copy.deepcopy(t4)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data4, path4)
        t3 = [c for c in manual_cases() if c['window_key'] == 'T3'][0]
        path3, data3 = packet_of(t3)
        changes3 = [
            ('context_low',
             lambda c: c['context_centers'][0].__setitem__('low_ticks',
                                                           2812)),
            ('context_high',
             lambda c: c['context_centers'][0].__setitem__('high_ticks',
                                                           2892)),
            ('context_units',
             lambda c: c['context_centers'][0]['units'].__setitem__(2, 10)),
            ('B_zn_truncated',
             lambda c: c['centers']['B']['zn'].__delitem__(4)),
            ('B_closed_by',
             lambda c: c['centers']['B'].__setitem__('closed_by', 18)),
            ('granularity_day',
             lambda c: c.__setitem__('granularity', 'day')),
        ]
        for name, mutate in changes3:
            with self.subTest(name=name):
                broken = copy.deepcopy(t3)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data3, path3)

    def test_reject_corrupt_xd_event_table(self):
        """T1的XD组成被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'T1'][0]
        path, data = packet_of(case)
        changes = [
            ('xd_too_short',
             lambda c: c['xd_events'][0].__setitem__(1, 4)),
            ('xd_mode', lambda c: c['xd_events'][0].__setitem__(2, 3)),
            ('xd_mode_bool',
             lambda c: c['xd_events'][0].__setitem__(2, True)),
            ('xd_proof_oob',
             lambda c: c['xd_events'][-1].__setitem__(3, 112)),
            ('xd_non_contiguous',
             lambda c: c['xd_events'][1].__setitem__(0, 7)),
            ('B_attempt_on_xd_units',
             lambda c: c['attempts']['B'][0].__setitem__('pull', 14)),
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
