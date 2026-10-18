# -*- coding: utf-8 -*-
"""0.9.10 二类买卖点标注的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'validation/tools/gen_real_second_point.py'
MANUAL = ROOT / 'validation/chan-real-second-point-manual-0.9.10.json'
FIXTURE = ROOT / 'tests/fixtures/real_second_point.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location(
            'real_second_point_compiler', TOOL)
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


class TestRealSecondPointAssets(unittest.TestCase):
    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        self.assertEqual(labels['version'], manual['version'])
        self.assertEqual(labels['annotation'], manual['annotation'])
        self.assertEqual(labels['annotation'],
                         'manual_second_point_real_strict_completed_divergence')
        self.assertEqual(labels['schema_version'],
                         'chan-real-second-point-v1')
        self.assertEqual({case['window_key'] for case in labels['cases']},
                         {'B1', 'C1', 'D1', 'X1', 'Y1', 'Z1'})
        granularities = {'B1': 'day', 'C1': 'day', 'D1': '60m',
                         'X1': '60m', 'Y1': '5m', 'Z1': '30m'}
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
        for path in (TOOL, ROOT / 'validation/tools/gen_real_first_point.py',
                     ROOT / 'validation/tools/gen_real_strict_trend.py',
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

    def test_reject_corrupt_b1_strict_trend_and_second_point_tables(self):
        """B1严格趋势角色、台账、一类与二类裁定表被篡改时直接拒绝。"""
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
            ('b_unit',
             lambda c: c['roles']['b'].__setitem__('unit', 2)),
            ('B_zd', lambda c: c['roles']['B'].__setitem__('zd', 1060)),
            ('c_unit', lambda c: c['roles']['c'].__setitem__('unit', 6)),
            ('c_outcome',
             lambda c: c['roles']['c'].__setitem__('outcome', 'fail')),
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
            ('fp_area_b',
             lambda c: c['first_point'].__setitem__('area_b', 0.028)),
            ('sp_side',
             lambda c: c['second_point'].__setitem__('side', 'sell2')),
            ('sp_anchor_unit',
             lambda c: c['second_point'].__setitem__('anchor_unit',
                                                     c['second_point']['anchor_unit'] + 1)),
            ('sp_anchor_kind',
             lambda c: c['second_point'].__setitem__(
                 'anchor_kind',
                 'interior' if c['second_point']['anchor_kind'] == 'boundary'
                 else 'boundary')),
            ('sp_anchor_ticks',
             lambda c: c['second_point'].__setitem__(
                 'anchor_ticks', c['second_point']['anchor_ticks'] + 1)),
            ('sp_interior_gap',
             lambda c: c['second_point'].__setitem__(
                 'interior_gap_ticks',
                 1 if c['second_point']['interior_gap_ticks'] is None
                 else c['second_point']['interior_gap_ticks'] + 1)),
            ('sp_leg1',
             lambda c: c['second_point'].__setitem__(
                 'leg1', c['second_point']['leg1'] + 1)),
            ('sp_leg2',
             lambda c: c['second_point'].__setitem__(
                 'leg2', c['second_point']['leg2'] + 1)),
            ('sp_second_extreme',
             lambda c: c['second_point'].__setitem__(
                 'second_extreme_ticks',
                 c['second_point']['second_extreme_ticks'] + 1)),
            ('sp_broke_anchor',
             lambda c: c['second_point'].__setitem__(
                 'broke_anchor', not c['second_point']['broke_anchor'])),
            ('sp_tier',
             lambda c: c['second_point'].__setitem__(
                 'tier', {'weakest': 'ordinary', 'ordinary': 'strongest',
                          'strongest': 'weakest'}[c['second_point']['tier']])),
            ('sp_position',
             lambda c: c['second_point'].__setitem__(
                 'position', {'below': 'within', 'within': 'above',
                              'above': 'below'}[c['second_point']['position']])),
            ('sp_anchor_area',
             lambda c: c['second_point'].__setitem__(
                 'anchor_area', c['second_point']['anchor_area'] + 0.001)),
            ('sp_leg2_area',
             lambda c: c['second_point'].__setitem__(
                 'leg2_area', c['second_point']['leg2_area'] + 0.001)),
            ('sp_cd',
             lambda c: c['second_point'].__setitem__(
                 'consolidation_divergence',
                 not c['second_point']['consolidation_divergence'])),
            ('sp_later_break',
             lambda c: c['second_point'].__setitem__(
                 'later_break',
                 None if c['second_point']['later_break'] is not None
                 else dict(unit=99, extreme_ticks=1))),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                broken = copy.deepcopy(case)
                mutate(broken)
                with self.assertRaises(ValueError):
                    tool.compile_case(broken, data, path)

    def test_reject_corrupt_frozen_window_second_point_tables(self):
        """C1/D1/X1/Y1/Z1二类裁定表被篡改时直接拒绝。"""
        tool = compiler()
        for case in manual_cases():
            if case['window_key'] == 'B1':
                continue
            path, data = packet_of(case)
            changes = [
                ('sp_side',
                 lambda c: c['second_point'].__setitem__(
                     'side', 'buy2' if c['second_point']['side'] == 'sell2'
                     else 'sell2')),
                ('sp_anchor_unit',
                 lambda c: c['second_point'].__setitem__(
                     'anchor_unit', c['second_point']['anchor_unit'] + 1)),
                ('sp_anchor_kind',
                 lambda c: c['second_point'].__setitem__(
                     'anchor_kind',
                     'interior' if c['second_point']['anchor_kind'] == 'boundary'
                     else 'boundary')),
                ('sp_anchor_ticks',
                 lambda c: c['second_point'].__setitem__(
                     'anchor_ticks', c['second_point']['anchor_ticks'] + 1)),
                ('sp_interior_gap',
                 lambda c: c['second_point'].__setitem__(
                     'interior_gap_ticks',
                     1 if c['second_point']['interior_gap_ticks'] is None
                     else c['second_point']['interior_gap_ticks'] + 1)),
                ('sp_leg1',
                 lambda c: c['second_point'].__setitem__(
                     'leg1', c['second_point']['leg1'] + 1)),
                ('sp_leg2',
                 lambda c: c['second_point'].__setitem__(
                     'leg2', c['second_point']['leg2'] + 1)),
                ('sp_second_extreme',
                 lambda c: c['second_point'].__setitem__(
                     'second_extreme_ticks',
                     c['second_point']['second_extreme_ticks'] + 1)),
                ('sp_broke_anchor',
                 lambda c: c['second_point'].__setitem__(
                     'broke_anchor',
                     not c['second_point']['broke_anchor'])),
                ('sp_tier',
                 lambda c: c['second_point'].__setitem__(
                     'tier', {'weakest': 'ordinary', 'ordinary': 'strongest',
                              'strongest': 'weakest'}[c['second_point']['tier']])),
                ('sp_position',
                 lambda c: c['second_point'].__setitem__(
                     'position', {'below': 'within', 'within': 'above',
                                  'above': 'below'}[c['second_point']['position']])),
                ('sp_anchor_area',
                 lambda c: c['second_point'].__setitem__(
                     'anchor_area', c['second_point']['anchor_area'] + 0.001)),
                ('sp_leg2_area',
                 lambda c: c['second_point'].__setitem__(
                     'leg2_area', c['second_point']['leg2_area'] + 0.001)),
                ('sp_cd',
                 lambda c: c['second_point'].__setitem__(
                     'consolidation_divergence',
                     not c['second_point']['consolidation_divergence'])),
                ('sp_later_break',
                 lambda c: c['second_point'].__setitem__(
                     'later_break',
                     None if c['second_point']['later_break'] is not None
                     else dict(unit=99, extreme_ticks=1))),
            ]
            for name, mutate in changes:
                with self.subTest(window=case['window_key'], name=name):
                    broken = copy.deepcopy(case)
                    mutate(broken)
                    with self.assertRaises(ValueError):
                        tool.compile_case(broken, data, path)


if __name__ == '__main__':
    unittest.main()
