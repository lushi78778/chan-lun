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


def embedded_table(name):
    """读取同一静态表, 不导入包测试或执行识别器。"""
    source = ROOT / 'tests/test_real_f1_originals.py'
    return next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == name for target in node.targets))


class TestRealF1Assets(unittest.TestCase):
    def test_joined_f2_role_table_recomputes_declared_intersections_and_proofs(self):
        """课20/35/38：显式F1输入的10个核心、完整波动与证明角色，独立整数复算。"""
        table = embedded_table('M3_JOINED_F2_AUDIT')
        self.assertEqual(table['source_expectations_sha256'],
                         '8b00e438b838b894e5616f3e1755654f5cabad5d1d6b873f9362e1875d2ac431')
        self.assertEqual({k: len(v) for k, v in table['inputs'].items()}, {'81': 19, '106': 41})
        self.assertEqual(set(table['cases']), {'81-up', '106-up', '106-down'})
        core_count = 0
        for key, audit in sorted(table['cases'].items()):
            rows = table['inputs'][audit['standard']]
            for previous, current in zip(rows, rows[1:]):
                self.assertEqual((previous[5], previous[7]), (current[4], current[6]))
                self.assertLess(previous[10], current[10])
                self.assertLess(previous[11], current[11])
            a, z, kind, _, triples, cores, proof = audit['f2']
            for j, (start, formed, extended), core in zip(triples, audit['spans'], cores):
                self.assertEqual((j, j+2), (start, formed))
                self.assertEqual((max(u[8] for u in rows[j:j+3]),
                                  min(u[9] for u in rows[j:j+3])), tuple(core))
                for u in rows[formed+1:extended+1]:
                    self.assertTrue(u[8] <= core[1] and u[9] >= core[0])
                core_count += 1
            for left, right in zip(cores, cores[1:]):
                self.assertGreater(right[0] if kind == 'up' else left[0],
                                   left[1] if kind == 'up' else right[1])
            waves, tails = [], []
            for start, formed, extended in audit['spans'][-2:]:
                waves.append((min(u[8] for u in rows[start:extended+1]),
                              max(u[9] for u in rows[start:extended+1])))
                reverse = [i for i in range(formed, extended+1)
                           if rows[i][7] != rows[i][6] and
                           (rows[i][7] > rows[i][6]) == (kind == 'down')]
                tails.append(reverse[-1] if reverse else None)
            self.assertEqual(waves, [tuple(w) for w in audit['waves']])
            self.assertEqual((max(w[0] for w in waves), min(w[1] for w in waves)), audit['wave_overlap'])
            self.assertLessEqual(*audit['wave_overlap'])
            self.assertEqual(tuple(tails), audit['tails'])
            if None not in tails:
                reference = (tails[0]+1, audit['spans'][-1][0]-1)
                leave = (tails[1]+1, z)
                self.assertEqual(reference if reference[0] <= reference[1] else None, audit['reference'])
                self.assertEqual(leave if leave[0] <= leave[1] else None, audit['leave'])
            else:
                self.assertEqual((audit['reference'], audit['leave']), (None, None))
            completion, first_leave, new_triple, new_core = audit['completion']
            last_core = cores[-1]
            self.assertGreater(proof, z)
            self.assertEqual(rows[proof][10], audit['confirmed_raw_count'])
            self.assertGreater(rows[proof][11], max(u[11] for u in rows[a:z+1]))
            for u in rows[first_leave:proof]:
                self.assertTrue(u[9] < last_core[0] or u[8] > last_core[1])
            if completion == 'first_return':
                self.assertTrue(rows[proof][8] <= last_core[1] and rows[proof][9] >= last_core[0])
            else:
                self.assertEqual(completion, 'reverse_center')
                self.assertEqual((z, proof), (first_leave-1, new_triple[-1]))
                self.assertEqual((max(rows[i][8] for i in new_triple),
                                  min(rows[i][9] for i in new_triple)), new_core)
                self.assertLess(new_core[1], last_core[0])
                self.assertGreater(max(u[8] for u in rows[first_leave:first_leave+3]),
                                   min(u[9] for u in rows[first_leave:first_leave+3]))
        self.assertEqual(core_count, 10)

    def test_embedded_m3_f1_tables_recompute_without_importing_package_tests(self):
        """复用整数编译器核验34个F1/三个F2表；AST读取避免执行包测试或调用chan。"""
        table = embedded_table('M3_STRICT_F2_AUDIT')
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

    def test_complete_f1_third_point_table_uses_causal_centers_and_whole_returns(self):
        """六个真实F1上下文全保留; 两侧条件与待回试分别用独立整数算术核对。"""
        types = embedded_table('M3_STRICT_F2_AUDIT')
        table = embedded_table('M3_F1_THIRD_AUDIT')
        self.assertEqual(set(types), set(table))
        positive, pending = [], []
        for key, audit in sorted(types.items()):
            f1 = audit['f1']
            self.assertEqual(len(table[key]), len(audit['spans']))
            for number, ((start, formed, _), core, record) in enumerate(zip(
                    audit['spans'], audit['f2'][5], table[key])):
                known, expected, waiting = record
                zd, zg = core
                self.assertEqual((max(f[12] for f in f1[start:formed+1]),
                                  min(f[13] for f in f1[start:formed+1])), core)
                self.assertEqual(max(f[7] for f in f1[start:formed+1]), known)
                self.assertLess(f1[formed+1][8], known)
                matches = []
                for i in range(formed+1, len(f1)-1):
                    leave, pull = f1[i:i+2]
                    self.assertEqual((leave[9], leave[11]), (pull[8], pull[10]))
                    up, reverse_up = leave[11] > leave[10], pull[11] > pull[10]
                    if leave[8] < known or leave[12] > zg or leave[13] < zd:
                        continue
                    outside = leave[11] > zg if up else leave[11] < zd
                    if not outside or up == reverse_up:
                        continue
                    margin = pull[12]-zg if up else zd-pull[13]
                    if margin >= 0:
                        matches.append(('buy3' if up else 'sell3', i, i+1, pull[9], pull[11],
                                        max(known, leave[7], pull[7]), margin))
                self.assertEqual(matches[0] if matches else None, expected, (key, number))
                if expected is not None:
                    positive.append(expected[0])
                last = f1[-1]
                outside = last[11] > zg if last[11] > last[10] else last[11] < zd
                actual_wait = len(f1)-1 if (not matches and last[8] >= known and
                              last[12] <= zg and last[13] >= zd and outside) else None
                self.assertEqual(actual_wait, waiting, (key, number))
                if waiting is not None:
                    pending.append((key, number))
        self.assertEqual(sorted(positive), ['buy3', 'sell3'])
        self.assertEqual(pending, [('M3I106', 1), ('M3W106', 1)])

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
