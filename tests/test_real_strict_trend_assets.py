# -*- coding: utf-8 -*-
"""严格趋势Zn与完整角色标注的来源、独立编译与人工表防错契约。"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/gen_real_strict_trend.py'
MANUAL = ROOT / 'validation/chan-real-strict-trend-manual-0.9.2.json'
FIXTURE = ROOT / 'tests/fixtures/real_strict_trend.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_strict_trend_compiler', TOOL)
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


class TestRealStrictTrendAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['schema_version'],
                         'chan-real-strict-trend-v1')
        self.assertEqual(labels['cases'][0]['window_key'], 'S1')
        self.assertEqual(labels['cases'][1]['window_key'], 'S2')
        self.assertEqual(labels['cases'][2]['window_key'], 'S3')
        for case in labels['cases']:
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
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

    def test_reject_corrupt_manual_role_and_ledger_tables(self):
        """角色算术、台账与笔全链被篡改时不得编译成理论真值。"""
        tool = compiler()
        case = manual_cases()[0]
        path, data = packet_of(case)
        rows = data['rows']
        changes = [
            ('expected_bis', lambda c: c['expected_bis'][0].__setitem__(3, 1)),
            ('zn_step', lambda c: c['roles']['A']['zn'].__setitem__(2, 5)),
            ('zd', lambda c: c['roles']['A'].__setitem__('zd', 3188)),
            ('dd', lambda c: c['roles']['A'].__setitem__('dd', 3099)),
            ('closed_by', lambda c: c['roles']['A'].__setitem__('closed_by', 5)),
            ('closed_by_null', lambda c: c['roles']['A'].__setitem__('closed_by', None)),
            ('b_unit', lambda c: c['roles']['b'].__setitem__('unit', 4)),
            ('c_outcome', lambda c: c['roles']['c'].__setitem__('outcome', 'fail')),
            ('gap', lambda c: c['roles'].__setitem__('gap_ticks', 354)),
            ('ledger', lambda c: c['ledger'][0].__setitem__(1, 3)),
            ('completed_status',
             lambda c: c['trend'].__setitem__('status', 'completed')),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)

    def test_reject_corrupt_merge_and_xd_event_tables(self):
        """定理二合并、XD组成与确认理由被篡改时直接拒绝。"""
        tool = compiler()
        cases = manual_cases()
        _, data2 = packet_of(cases[1])
        _, _, bis2 = tool.foundation(data2['rows'], '106')
        units2 = tool.components(data2['rows'], bis2[:-1])
        merges = [
            ('merge_removed', lambda c: c['roles'].__setitem__('merge', None)),
            ('merge_determined',
             lambda c: c['roles']['merge'].__setitem__('determined', False)),
            ('merge_branch',
             lambda c: c['roles']['merge'].__setitem__('branch', 'above')),
            ('C_closed_by',
             lambda c: c['roles']['C'].__setitem__('closed_by', 37)),
        ]
        for name, mutate in merges:
            with self.subTest(name=name):
                broken = copy.deepcopy(cases[1])
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.validate_roles(broken, units2)
        case3 = cases[2]
        _, data3 = packet_of(case3)
        _, _, bis3 = tool.foundation(data3['rows'], '106')
        fixed3 = tool.components(data3['rows'], bis3[:-1])
        events = [
            ('xd_negative', lambda c: c['xd_events'][0].__setitem__(0, -1)),
            ('xd_boolean', lambda c: c['xd_events'][0].__setitem__(0, True)),
            ('xd_early_proof', lambda c: c['xd_events'][0].__setitem__(3, 2)),
            ('xd_missing_proof',
             lambda c: c['xd_events'][0].__setitem__(3, len(fixed3))),
            ('xd_mode', lambda c: c['xd_events'][0].__setitem__(2, 3)),
            ('xd_adjacency', lambda c: c['xd_events'][1].__setitem__(0, 4)),
        ]
        for name, mutate in events:
            with self.subTest(name=name):
                broken = copy.deepcopy(case3)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.validate_xd_events(broken, fixed3)
        audits = [
            ('audit_xd_index', lambda c: c['xd_audit'][0].__setitem__('xd', 1)),
            ('audit_kind',
             lambda c: c['xd_audit'][0].__setitem__('confirm_kind', 'third_fx')),
            ('audit_mode_mismatch',
             lambda c: c['xd_audit'][0].__setitem__('confirm_kind',
                                                    'first_selected')),
            ('audit_short', lambda c: c['xd_audit'].pop()),
        ]
        for name, mutate in audits:
            with self.subTest(name=name):
                broken = copy.deepcopy(case3)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.validate_xd_audit(broken)


if __name__ == '__main__':
    unittest.main()
