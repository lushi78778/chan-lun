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
    def test_xd_f1_lineage_third_table_uses_first_known_core_and_whole_return(self):
        """七个核心全部保留; 首回试破沿与重新离开分开, 不靠库输出反推预期。"""
        tree = ast.parse((ROOT / 'tests/test_real_xd_f1.py').read_text())

        def embedded(name):
            return next(ast.literal_eval(n.value) for n in tree.body
                        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and
                            t.id==name for t in n.targets))

        types,table = embedded('M3_XD_RECURSION_AUDIT'),embedded('M3_XD_THIRD_AUDIT')
        spec = importlib.util.spec_from_file_location('independent_xd_third',
                    ROOT / 'validation/tools/gen_real_f1_originals.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        self.assertEqual(set(table),set(types))
        totals = [0,0,0,0,0]
        for key,audit in sorted(types.items()):
            path = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(path),audit['source_sha256'])
            case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['parent_id'])
            f1 = []
            for row in audit['f1']:
                record = tool.move_record(case['units'],row)
                proof = case['units'][row[-1]]
                record.update(confirmed_raw_count=proof['confirmed_raw_count'],confirmed_dt=proof['confirmed_dt'])
                f1.append(record)
            self.assertEqual([(r[0],r[1],r[2]) for r in table[key]],
                             [(a,b,core) for move,spans in zip(audit['f2'],audit['f2_spans'])
                              for (a,b,_),core in zip(spans,move[5])])
            for start,formed,core,known,extended,expected,pending,failed in table[key]:
                zd,zg = core
                self.assertEqual(formed,start+2)
                self.assertEqual((max(r['low_ticks'] for r in f1[start:formed+1]),
                                  min(r['high_ticks'] for r in f1[start:formed+1])),core)
                self.assertEqual(max(r['confirmed_raw_count'] for r in f1[start:formed+1]),known)
                known_dt = max(r['confirmed_dt'] for r in f1[start:formed+1])
                self.assertEqual([i for i,_ in extended],list(range(formed+1,formed+1+len(extended))))
                for i,count in extended:
                    self.assertEqual(f1[i]['confirmed_raw_count'],count)
                    self.assertTrue(f1[i]['low_ticks']<=zg and f1[i]['high_ticks']>=zd)
                matches,breaches = [],[]
                for i in range(formed+1,len(f1)-1):
                    leave,pull = f1[i:i+2]
                    self.assertEqual((leave['end_dt'],leave['end_ticks']),
                                     (pull['start_dt'],pull['start_ticks']))
                    up = leave['end_ticks']>leave['start_ticks']
                    reverse_up = pull['end_ticks']>pull['start_ticks']
                    if leave['start_dt']<known_dt or leave['low_ticks']>zg or leave['high_ticks']<zd:
                        continue
                    if up==reverse_up or not (leave['end_ticks']>zg if up else leave['end_ticks']<zd):
                        continue
                    margin = pull['low_ticks']-zg if up else zd-pull['high_ticks']
                    count = max(known,leave['confirmed_raw_count'],pull['confirmed_raw_count'])
                    if margin<0:
                        breaches.append((i,i+1,count,margin))
                    else:
                        matches.append(('buy3' if up else 'sell3',i,i+1,pull['end_dt'],pull['end_ticks'],count,margin))
                self.assertEqual(matches[0] if matches else None,expected)
                self.assertEqual(tuple(breaches),failed)
                last = f1[-1]
                outside = last['end_ticks']>zg if last['end_ticks']>last['start_ticks'] else last['end_ticks']<zd
                waiting = (len(f1)-1 if not matches and last['start_dt']>=known_dt and
                           last['low_ticks']<=zg and last['high_ticks']>=zd and outside else None)
                self.assertEqual(waiting,pending)
                totals[0] += 1
                totals[1] += len(extended)
                totals[2] += expected is not None
                totals[3] += len(failed)
                totals[4] += pending is not None
        self.assertEqual(totals,[7,9,2,1,1])

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
