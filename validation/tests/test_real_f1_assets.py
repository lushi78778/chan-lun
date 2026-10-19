# -*- coding: utf-8 -*-
"""F1归档来源与独立编译契约; 理论算法测试仍只维护在包tests。"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/real_f1_originals.json'
MANUAL = ROOT / 'validation/chan-real-f1-manual-0.9.0.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestRealF1Assets(unittest.TestCase):
    def test_embedded_m3_f1_tables_recompute_without_importing_package_tests(self):
        """复用整数编译器核验34个F1/三个F2表；AST读取避免执行包测试或调用chan。"""
        source = ROOT / 'tests/test_real_f1_originals.py'
        table = next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                     if isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'M3_STRICT_F2_AUDIT'
                         for target in node.targets))
        tool = ROOT / 'validation/tools/gen_real_f1_originals.py'
        spec = importlib.util.spec_from_file_location('independent_f1_audit', str(tool))
        compiler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compiler)
        for key, audit in sorted(table.items()):
            fixture = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(digest(fixture), audit['source_sha256'], key)
            parent = next(c for c in json.loads(fixture.read_text())['cases']
                          if c['id'] == audit['parent_id'])
            rows = [r for r in parent['raw_rows'] if r['dt'][:10] >= audit['anchor']]
            rows = rows[:audit['cutoff']]
            self.assertTrue(all(r['adj_factor'] == 1 for r in rows))
            _, _, bis = compiler.foundation(rows, audit['standard'])
            units = compiler.components(rows, bis[:-1], dt_slice=None)
            targets, first = [], {}
            for item in audit['f1']:
                target = compiler.move_record(units, item[:7])
                self.assertEqual((target['start_dt'], target['end_dt']),
                                 (rows[item[8]]['dt'], rows[item[9]]['dt']))
                self.assertEqual((target['start_ticks'], target['end_ticks'],
                                  target['low_ticks'], target['high_ticks']), item[10:14])
                proof = units[item[6]]
                lo, hi = item[5][-1]
                self.assertTrue(proof['low_ticks'] <= hi and proof['high_ticks'] >= lo)
                targets.append(target)
            for count in range(1, len(rows)+1):
                _, _, prefix = compiler.foundation(rows[:count], audit['standard'])
                visible = compiler.components(rows[:count], prefix[:-1], dt_slice=None)
                for i, item in enumerate(audit['f1']):
                    if len(visible) > item[6]:
                        self.assertEqual(compiler.move_record(visible, item[:7]), targets[i])
                        first.setdefault(i, count)
            self.assertEqual([first[i] for i in range(len(targets))],
                             [item[7] for item in audit['f1']], key)
            f2 = compiler.move_record(targets, audit['f2'])
            self.assertTrue(f2['complete'])
            self.assertEqual(audit['cutoff'], first[audit['f2'][-1]]+1)
            for (a, formed, extended), core in zip(audit['spans'], audit['f2'][5]):
                self.assertEqual(formed, a+2)
                for unit in targets[formed+1:extended+1]:
                    self.assertTrue(unit['low_ticks'] <= core[1] and unit['high_ticks'] >= core[0])
            pa, ba = audit['spans'][-2][0], audit['spans'][-1][0]
            pt, bt = audit['tails']
            previous, last = targets[pa:pt+1], targets[ba:bt+1]
            gap = (min(u['low_ticks'] for u in last)-max(u['high_ticks'] for u in previous)
                   if f2['kind'] == 'up' else
                   min(u['low_ticks'] for u in previous)-max(u['high_ticks'] for u in last))
            self.assertEqual(gap, audit['wave_gap'], key)

    def test_frozen_source_packets_and_manual_receipt(self):
        """源包摘要/行/时间/价格/因子须保真, 不允许静默修价或补因子。"""
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(fixture['manual_sha256'], digest(MANUAL))
        for case in fixture['cases']:
            source = case['source']
            packet = ROOT / 'validation' / source['packet']
            self.assertEqual(source['sha256'], digest(packet))
            data = json.loads(packet.read_text())
            self.assertEqual(data['rows'], case['raw_rows'])
            self.assertEqual(source['dataset_manifest_sha256'], data['manifest_sha256'])
            rows = data['rows']
            self.assertEqual(len(rows), len(set(r['dt'] for r in rows)))
            self.assertEqual([r['dt'] for r in rows], sorted(r['dt'] for r in rows))
            for row in rows:
                self.assertEqual(row['adj_factor'], 1)
                self.assertGreater(row['low'], 0)
                self.assertLessEqual(row['low'], min(row['open'], row['close']))
                self.assertGreaterEqual(row['high'], max(row['open'], row['close']))
                self.assertGreaterEqual(row['vol'], 0)

    def test_generator_has_no_library_dependency_and_rebuilds_frozen_bytes(self):
        """独立编译只复算人工表, 每次输出摘要一致且拒绝覆盖既有证据。"""
        tool = ROOT / 'validation/tools/gen_real_f1_originals.py'
        for node in ast.walk(ast.parse(tool.read_text())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            self.assertTrue(all(name.split('.')[0] != 'chan' for name in names))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'labels.json'
            command = [sys.executable, str(tool), '--manual', str(MANUAL),
                       '--base-labels', str(ROOT / 'tests/fixtures/real_xd_originals.json'),
                       '--packets', str(ROOT / 'validation'), '--output', str(output)]
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(digest(output), digest(FIXTURE))
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(digest(output), digest(FIXTURE))


if __name__ == '__main__':
    unittest.main()
