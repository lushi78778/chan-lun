# -*- coding: utf-8 -*-
"""0.9.4完成严格趋势分钟粒度标注的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'tools/gen_real_strict_trend.py'
MANUAL = ROOT / 'validation/chan-real-strict-trend-manual-0.9.4.json'
FIXTURE = ROOT / 'tests/fixtures/real_strict_trend_minute.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_strict_trend_minute_compiler', TOOL)
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


class TestRealStrictTrendMinuteAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['schema_version'],
                         'chan-real-strict-trend-v1')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'D1', 'X1'})
        for case in labels['cases']:
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
            self.assertEqual(case['granularity'], '60m')
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

    def test_reject_corrupt_completed_role_and_ledger_tables(self):
        """D1完成正例角色算术、冻结互斥、证明段与台账被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'D1'][0]
        path, data = packet_of(case)
        changes = [
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1208)),
            ('zn_step', lambda c: c['roles']['B']['zn'].__setitem__(1, 7)),
            ('zd', lambda c: c['roles']['B'].__setitem__('zd', 1140)),
            ('dd', lambda c: c['roles']['B'].__setitem__('dd', 1089)),
            ('B_closed_by',
             lambda c: c['roles']['B'].__setitem__('closed_by', 10)),
            ('B_frozen_removed',
             lambda c: c['roles']['B'].pop('frozen_by_departure')),
            ('A_frozen',
             lambda c: c['roles']['A'].__setitem__('frozen_by_departure',
                                                   True)),
            ('frozen_non_bool',
             lambda c: c['roles']['B'].__setitem__('frozen_by_departure', 1)),
            ('b_unit', lambda c: c['roles']['b'].__setitem__('unit', 6)),
            ('c_outcome',
             lambda c: c['roles']['c'].__setitem__('outcome', 'fail')),
            ('proof_removed', lambda c: c['roles'].pop('proof')),
            ('proof_unit', lambda c: c['roles']['proof'].__setitem__('unit', 11)),
            ('gap', lambda c: c['roles'].__setitem__('gap_ticks', 28)),
            ('ledger', lambda c: c['ledger'][0].__setitem__(1, 3)),
            ('status_ongoing',
             lambda c: c['trend'].__setitem__('status', 'ongoing')),
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

    def test_reject_corrupt_xd_event_and_audit_tables(self):
        """X1的XD组成、确认理由与粒度被篡改时直接拒绝。"""
        tool = compiler()
        case = [c for c in manual_cases() if c['window_key'] == 'X1'][0]
        path, data = packet_of(case)
        changes = [
            ('expected_bis',
             lambda c: c['expected_bis'][0].__setitem__(3, 1682)),
            ('xd_too_short',
             lambda c: c['xd_events'][0].__setitem__(1, 4)),
            ('xd_mode', lambda c: c['xd_events'][0].__setitem__(2, 3)),
            ('xd_mode_bool',
             lambda c: c['xd_events'][0].__setitem__(2, True)),
            ('xd_proof_oob',
             lambda c: c['xd_events'][-1].__setitem__(3, 112)),
            ('xd_non_contiguous',
             lambda c: c['xd_events'][1].__setitem__(0, 7)),
            ('audit_short', lambda c: c['xd_audit'].pop()),
            ('audit_kind', lambda c: c['xd_audit'][0].__setitem__(
                'confirm_kind', 'second_fx')),
            ('audit_xd_index', lambda c: c['xd_audit'][3].__setitem__(
                'xd', 2)),
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
