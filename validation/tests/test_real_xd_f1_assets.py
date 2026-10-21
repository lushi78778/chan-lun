# -*- coding: utf-8 -*-
"""完成XD构造F1的来源、独立编译与人工表防错契约。"""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'validation/tools/gen_real_xd_f1.py'
MANUAL = ROOT / 'validation/chan-real-xd-f1-manual-0.9.1.json'
FIXTURE = ROOT / 'tests/fixtures/real_xd_f1.json'


def compiler():
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location('real_xd_f1_compiler', TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class TestRealXdF1Assets(unittest.TestCase):
    def test_complete_xd_f1_f2_table_has_independent_intersections_and_proofs(self):
        """AST读取同一冻结表; 独立核返回/反向中枢证明、F2延伸及开放尾部。"""
        source = ROOT / 'tests/test_real_xd_f1.py'
        table = next(ast.literal_eval(n.value) for n in ast.parse(source.read_text()).body
                     if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and
                         t.id=='M3_XD_RECURSION_AUDIT' for t in n.targets))
        tool = compiler()
        spec = importlib.util.spec_from_file_location('independent_xd_recursion',
                    ROOT / 'validation/tools/gen_real_f1_originals.py')
        arithmetic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(arithmetic)

        def touches(unit,core):
            return unit['low_ticks']<=core[1] and unit['high_ticks']>=core[0]

        def core_at(units,start):
            return (max(u['low_ticks'] for u in units[start:start+3]),
                    min(u['high_ticks'] for u in units[start:start+3]))

        total, opposite, completed = 0, [], []
        self.assertEqual(set(table),{'X1','Y1','S3','M1','M2'})
        for key,audit in sorted(table.items()):
            fixture = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(fixture),audit['source_sha256'])
            case = next(c for c in json.loads(fixture.read_text())['cases'] if c['id']==audit['parent_id'])
            self.assertEqual((case['standard'],case['level']),('106','xd'))
            self.assertTrue(all(r['adj_factor']==1 for r in case['raw_rows']))
            units, records = case['units'], []
            rows = audit['f1']+(audit['tail'],)
            self.assertEqual(rows[0][0],0)
            self.assertEqual(rows[-1][1],len(units)-1)
            for left,right in zip(rows,rows[1:]):
                self.assertEqual(left[1]+1,right[0])
            for row in rows:
                a,z,kind,entry,triples,cores,proof = row
                record = arithmetic.move_record(units,row)
                if not triples:
                    self.assertEqual((kind,proof),('incomplete',None))
                    self.assertLess(z-a,2)
                    continue
                for j in range(a,triples[0]):
                    lo,hi = core_at(units,j)
                    self.assertGreater(lo,hi)
                for n,(j,core) in enumerate(zip(triples,cores)):
                    stop = triples[n+1]+3 if n+1<len(triples) else z+1
                    self.assertTrue(all(not touches(u,core) for u in units[j+3:stop]))
                if proof is None:
                    continue
                if proof==z+1:
                    self.assertTrue(touches(units[proof],cores[-1]))
                else:
                    self.assertEqual(proof,z+3)
                    new = core_at(units,z+1)
                    self.assertLessEqual(*new)
                    self.assertTrue(new[0]>cores[-1][1] or new[1]<cores[-1][0])
                    direction = 'up' if new[0]>cores[-1][1] else 'down'
                    self.assertNotEqual(direction,entry)
                    self.assertTrue(all(not touches(u,cores[-1]) for u in units[z+1:proof+1]))
                    self.assertEqual({u['confirmed_raw_count'] for u in units[z+1:proof+1]},{4727})
                    opposite.append(key)
                record.update(confirmed_raw_count=units[proof]['confirmed_raw_count'])
                records.append(record)
            total += len(records)
            self.assertEqual(len(audit['f2']),len(audit['f2_spans']))
            for row,spans in zip(audit['f2'],audit['f2_spans']):
                record = arithmetic.move_record(records,row)
                a,z,_,_,_,cores,proof = row
                for j in range(a,spans[0][0]):
                    lo,hi = core_at(records,j)
                    self.assertGreater(lo,hi)
                for i,((start,formed,extended),core) in enumerate(zip(spans,cores)):
                    self.assertEqual(formed,start+2)
                    self.assertTrue(all(touches(u,core) for u in records[formed+1:extended+1]))
                    if i+1<len(spans):
                        new_start,new_formed,_ = spans[i+1]
                        self.assertEqual(new_start,extended+1)
                        self.assertTrue(all(not touches(u,core) for u in records[new_start:new_formed+1]))
                leave = spans[-1][2]+1
                self.assertTrue(all(not touches(u,cores[-1]) for u in records[leave:z+1]))
                if proof is None:
                    self.assertLess(z-leave+1,3)
                else:
                    self.assertEqual(proof,z+1)
                    self.assertTrue(touches(records[proof],cores[-1]))
                    self.assertEqual(records[proof]['confirmed_raw_count'],3323)
                    self.assertEqual((record['low_ticks'],record['high_ticks']),(666,1113))
                    self.assertEqual(records[proof]['high_ticks'],1202)
                    completed.append(key)
        self.assertEqual((total,opposite,completed),(38,['M2'],['M1']))

    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        for case in labels['cases']:
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
            data = json.loads(packet.read_text())
            self.assertEqual(data['rows'], case['raw_rows'])
            self.assertEqual(data['manifest_sha256'], case['source']['dataset_manifest_sha256'])
        for path in (TOOL, ROOT / 'validation/tools/gen_real_f1_originals.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                self.assertTrue(all(name.split('.')[0] != 'chan' for name in names))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'labels.json'
            command = [sys.executable, str(TOOL), '--manual', str(MANUAL),
                       '--packets', str(ROOT / 'validation'), '--output', str(output)]
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())

    def test_reject_corrupt_manual_ranges_and_premature_proof(self):
        """负索引/截短三段/空交集/提前证明不得编译成理论真值。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        fixed = labels['cases'][0]['observations'][str(len(labels['cases'][0]['raw_rows']))]['fixed_bis']
        changes = [
            ('negative', lambda c: c['xd_events'][0].__setitem__(0, -1)),
            ('boolean', lambda c: c['xd_events'][0].__setitem__(0, True)),
            ('early_xd', lambda c: c['xd_events'][0].__setitem__(3, 2)),
            ('missing_xd', lambda c: c['xd_events'][0].__setitem__(3, len(fixed))),
            ('short_triple', lambda c: c['f1_spec'][4].__setitem__(1, 5)),
            ('outside_triple', lambda c: c['f1_spec'][4].__setitem__(0, -1)),
            ('empty_core', lambda c: c['f1_spec'][5].__setitem__(0, [843, 842])),
            ('early_f1', lambda c: c['f1_spec'].__setitem__(6, 5)),
            ('missing_f1', lambda c: c['f1_spec'].__setitem__(6, 7)),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                case = json.loads(json.dumps(manual['cases'][0]))
                mutate(case)
                with self.assertRaises(ValueError):
                    tool.validate_manual(case, fixed)


if __name__ == '__main__':
    unittest.main()
