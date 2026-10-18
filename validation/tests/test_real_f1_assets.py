# -*- coding: utf-8 -*-
"""F1归档来源与独立编译契约; 理论算法测试仍只维护在包tests。"""
import ast
import hashlib
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
        tool = ROOT / 'tools/gen_real_f1_originals.py'
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
