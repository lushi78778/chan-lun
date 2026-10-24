# -*- coding: utf-8 -*-
"""完成XD构造F1的来源、独立编译与人工表防错契约。"""
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
TOOL = ROOT / 'validation/tools/gen_real_xd_f1.py'
MANUAL = ROOT / 'validation/chan-real-xd-f1-manual-0.9.1.json'
FIXTURE = ROOT / 'tests/fixtures/real_xd_f1.json'


def embedded_table(filename, name):
    """只读已有常量，不执行另一测试模块或用算法回填预期。"""
    tree = ast.parse((ROOT / 'tests' / filename).read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


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
    def test_completed_xd_views_do_not_skip_unavailable_predecessors(self):
        """前段proof9晚于后段proof8；两段应同时发布，不倒填后段已可见。"""
        tool = compiler()
        values = [10,20,15,25,12,22,11,21,13,23,14,24,16,26]
        fixed = [dict(start_index=i, end_index=i+1, start_ticks=a,
                      end_ticks=z, low_ticks=min(a,z), high_ticks=max(a,z),
                      start_dt=str(i), end_dt=str(i+1), direction='up' if z>a else 'down')
                 for i, (a,z) in enumerate(zip(values, values[1:]))]
        # 交替、衔接且前三笔重叠的给定部件；只核事件表的发布时序。
        events = [[0, 2, 2, 9], [3, 5, 1, 8], [6, 8, 1, 12]]
        integer_path = ROOT / 'validation/tools/gen_real_f1_originals.py'
        spec = importlib.util.spec_from_file_location('ordered_xd_integer', integer_path)
        integer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integer)
        for build in (tool.xd_records, integer.completed_xds):
            self.assertEqual(build(fixed[:9], events), [])
            both = build(fixed[:10], events)
            self.assertEqual([u['start_index'] for u in both], [0, 3])
            self.assertEqual([u['proof_bi'] for u in both], [9, 8])
            self.assertEqual([u['start_index'] for u in build(fixed, events)], [0, 3, 6])

    def test_ipo_context_jan10_fixed_bi_is_not_ordinary_xd_confirmation(self):
        """上市史固定笔可映射，不以BI端点或前三笔重叠补课78特殊前提。"""
        parts = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        # 同源IPO上下文：full81为11-16→12-03的上笔，12-22已固定。
        # 以01-10为假设下段端点的4个基本几何候选，其末标准旧侧均为该笔。
        # 完整42假设与原始1110日前缀另存源审计；本测试只核有限条件算术。
        left = (609358802000, 694689112000)
        first, right = [tuple(sorted(parts[i][4:6])) for i in (0, 2)]
        self.assertLessEqual(max(left[0], first[0]), min(left[1], first[1]))
        self.assertLess(first[0], left[0])
        self.assertLess(first[1], left[1])
        self.assertLess(right[0], first[0])
        self.assertLess(right[1], first[1])  # 右侧更低，不能确认以first为底的普通分型。
        self.assertLess(parts[1][5], parts[0][4])
        # full84在raw897(02-18)固定低于01-10；第三笔full85须raw900(02-23)。
        self.assertEqual((parts[1][6] + 868, parts[2][6] + 868), (897, 900))
        self.assertLess(parts[1][6], parts[2][6])

    def test_ipo_context_given_dec3_start_has_later_ordinary_local_boundaries(self):
        """给定12-03起段的普通局部正例；不裁定其全局归属或替换原两窗。"""
        parts = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        band = lambda i: tuple(sorted(parts[i][4:6]))
        overlap = lambda rows: (max(r[0] for r in rows), min(r[1] for r in rows))
        # full82..84从12-03到02-14。01-10是内部折点，不将它改写为新起点。
        prior = (526277196640, 694689112000)
        self.assertEqual(prior[0], parts[0][4])
        self.assertEqual(overlap([prior, band(0), band(1)]), (526277196640, 612350382280))
        left, middle, right = [band(i) for i in (0, 2, 4)]
        self.assertTrue(all(middle[k] < min(left[k], right[k]) for k in (0, 1)))
        self.assertLessEqual(max(left[0], middle[0]), min(left[1], middle[1]))
        self.assertEqual(overlap([band(i) for i in (2, 3, 4)]), (494283349820, 545612041000))
        self.assertGreater(parts[4][5], parts[2][5])
        self.assertEqual(parts[4][6] + 868, 910)  # 03-09可见，不能倒填为02-14。

        # 给定上述后段，03-01端点依课71首反向破坏+第三笔延伸，非严格标准顶。
        left, first, third = [band(i) for i in (3, 5, 7)]
        self.assertGreater(first[1], left[1])
        self.assertLess(first[0], left[0])
        self.assertFalse(all(first[k] > max(left[k], third[k]) for k in (0, 1)))
        self.assertLessEqual(max(left[0], first[0]), min(left[1], first[1]))
        self.assertEqual(overlap([band(i) for i in (5, 6, 7)]), (444731536860, 537079010000))
        self.assertLess(parts[7][5], parts[5][5])
        self.assertEqual(parts[7][6] + 868, 956)  # 05-19固定证据到齐。

    def test_first_seed_candidate_lifecycle_keeps_revocation_order(self):
        """保持start0的14个假设；局部条件、撤销与未知前提分开，不给替代分界。"""
        parts = embedded_table('test_real_f1_originals.py','M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        # 候选反向笔、端点首次可见行、更高峰首次可见行、反向三笔齐备行。
        frozen = [(1,26,None,37),(3,32,42,49),(5,42,120,88),(7,52,120,101),
                  (9,94,106,115),(11,106,120,124),(13,120,166,153),(15,133,166,170),
                  (17,166,None,180),(19,173,None,191),(21,184,195,205),
                  (23,195,None,217),(25,212,231,None),(27,231,None,None)]
        self.assertEqual([r[0] for r in frozen],list(range(1,len(parts)+1,2)))
        valid_net = []
        for candidate,endpoint_count,higher_count,three_count in frozen:
            endpoint = candidate-1
            self.assertEqual(parts[endpoint][6],endpoint_count)
            peak = parts[endpoint][5]
            higher = [p for p in parts[endpoint+2::2] if p[5] > peak]
            self.assertEqual(higher[0][6] if higher else None,higher_count)
            self.assertEqual(parts[candidate+2][6] if candidate+2 < len(parts) else None,three_count)
            self.assertEqual(max(p[5] for p in parts[:candidate:2]),612350382280)
            if peak > parts[0][4]:
                valid_net.append(candidate)
        self.assertEqual(valid_net,[1,3,5,7,13,15,17])
        self.assertLess(frozen[0][0],3)  # 最高峰自身不足最低三笔，不能直接用它闭合。
        self.assertEqual((max(min(p[4:6]) for p in parts[:3]),min(max(p[4:6]) for p in parts[:3])),
                         (526277196640,545612041000))

        # 13有正缺口但第二序列第三项须raw173；更高峰raw166已先到。
        self.assertEqual(min(parts[13][4:6])-max(parts[11][4:6]),41149287140)
        self.assertEqual(max(parts[13][4:6]),max(parts[15][4:6]))
        self.assertEqual([parts[i][6] for i in (14,16,18)],[133,166,173])
        self.assertLess(parts[16][6],parts[18][6])
        # 15的反向三笔还要等raw170，不能在更高峰到达前认定完成。
        self.assertLess(parts[16][6],max(parts[i][6] for i in (15,16,17)))
        # 5/17各有局部三笔，仍不得据此推定课78上下文已成立。
        for candidate,count in ((5,88),(17,180)):
            reverse = parts[candidate:candidate+3]
            self.assertEqual(reverse[-1][6],count)
            self.assertLessEqual(max(min(p[4:6]) for p in reverse),min(max(p[4:6]) for p in reverse))
            self.assertLess(reverse[-1][5],reverse[0][5])
            self.assertLess(parts[candidate-1][5],612350382280)

    def test_raw_crossed_start_threshold_is_not_standard_feature_proof(self):
        """8笔整数见证仅证明门槛不等价，不用识别器输出或赋予全局分界标签。"""
        original = [50,100,40,70,45,80,30,60,20]  # 抽象价位以0.1为单位。
        for points,up in ((original,True),([150-p for p in original],False)):
            bis = [(min(a,b),max(a,b)) for a,b in zip(points,points[1:])]
            self.assertEqual(len(bis),8)
            self.assertLessEqual(max(b[0] for b in bis[:3]),min(b[1] for b in bis[:3]))
            self.assertTrue(bis[1][0] <= bis[3][0] and bis[1][1] >= bis[3][1])
            pick = max if up else min
            standard = (pick(bis[1][0],bis[3][0]),pick(bis[1][1],bis[3][1]))
            raw,first = bis[3],bis[5]
            raw_turn = first[1] > raw[1] if up else first[0] < raw[0]
            standard_turn = first[1] > standard[1] if up else first[0] < standard[0]
            self.assertTrue(raw_turn)
            self.assertFalse(standard_turn)
            self.assertLessEqual(max(b[0] for b in bis[5:8]),min(b[1] for b in bis[5:8]))
            self.assertTrue(points[8] < points[6] if up else points[8] > points[6])
            self.assertTrue(points[8] < points[0] if up else points[8] > points[0])

    def test_factor_xd_standard_left_and_second_sequence_stages(self):
        """课67/71/78/81：保留标准旧侧，区分原邻笔条件与未知种子上下文。"""
        inputs = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')
        legacy = embedded_table('test_real_xd_f1.py', 'M3_FACTOR_XD_AUDIT')
        for value,wanted in ((inputs,'8100b6d1128eb2fcf38813678729051831b17798c33315bccef61f9629efd004'),
                             (legacy,'a5e29d244716a2147c97f5f6e83255ab8e9b8cdeac0fed3085926d674953901c')):
            blob = json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            self.assertEqual(hashlib.sha256(blob).hexdigest(),wanted)
        self.assertFalse(legacy['independent_theory_labels'])
        self.assertFalse(legacy['global_segmentation_independently_proven'])

        def groups(parts,indices,up):
            """整数区间顺序包含；旧侧初始方向显式给定，第二序列由相邻项建立。"""
            result = []
            for i in indices:
                low,high = min(parts[i][4:6]),max(parts[i][4:6])
                if result and (low <= result[-1][1] and high >= result[-1][2] or
                               low >= result[-1][1] and high <= result[-1][2]):
                    self.assertIsNotNone(up)
                    pick = max if up else min
                    ids,old_low,old_high = result[-1]
                    result[-1] = (ids+(i,),pick(low,old_low),pick(high,old_high))
                else:
                    if result:
                        up = high > result[-1][2]
                    result.append(((i,),low,high))
            return [(ids,(low,high)) for ids,low,high in result]

        # 调库前补充表：6条标准侧局部条件、1条raw-only、1条第二序列。
        # 起点是给定假设；此表不裁定完整候选生命周期或全局分界。
        sides = [
            ('2022-01-01-106',0,4,1,7,(1,3),(494283349820,612350382280),False),
            ('2022-01-01-106',5,7,2,19,(6,),(444731536860,537079010000),None),
            ('2022-01-01-106',8,16,1,19,(13,15),(511981860000,567165473420),True),
            ('2022-01-01-106',17,23,1,26,(20,22),(393345771840,437021692380),True),
            ('2022-01-01-81',0,12,1,15,(11,),(490900254000,546103945140),True),
            ('2022-01-01-81',13,17,1,20,(16,),(393345771840,444390336000),True),
            ('2022-04-15-106',0,16,1,19,(13,15),(393345771840,437021692380),True),
            ('2022-04-15-81',0,12,1,15,(11,),(393345771840,444390336000),True)]
        self.assertEqual(len(sides),sum(len(c['events']) for c in legacy['cases'].values()))
        supported = []
        for key,a,z,mode,proof,ids,left,wanted in sides:
            parts = inputs['cases'][key]['parts']
            up = parts[a][5] > parts[a][4]
            self.assertEqual(groups(parts,range(a+1,z,2),up)[-1],(ids,left))
            self.assertIn((a,z,mode,proof),[tuple(e[:4]) for e in legacy['cases'][key]['events']])
            if mode == 1:
                first = (min(parts[z+1][4:6]),max(parts[z+1][4:6]))
                protrudes = first[1] > left[1] if up else first[0] < left[0]
                self.assertEqual(protrudes,wanted)
                supported.append(protrudes)
                if wanted:
                    self.assertLessEqual(max(left[0],first[0]),min(left[1],first[1]))
                    reverse = parts[z+1:proof+1]
                    self.assertEqual(len(reverse),3)
                    self.assertLessEqual(max(min(p[4:6]) for p in reverse),min(max(p[4:6]) for p in reverse))
                    self.assertTrue(parts[proof][5] < parts[z+1][5] if up else parts[proof][5] > parts[z+1][5])
                    right = (min(parts[proof][4:6]),max(parts[proof][4:6]))
                    first_break = first[0] < left[0] if up else first[1] > left[1]
                    standard_fx = (all(first[k] > max(left[k],right[k]) for k in (0,1)) if up else
                                   all(first[k] < min(left[k],right[k]) for k in (0,1)))
                    self.assertTrue(first_break or standard_fx)
                else:
                    # BI1包含BI3后高点仍在；不能以较低原BI3直接证明标准顶。
                    self.assertEqual((key,a,z),('2022-01-01-106',0,4))
                    self.assertLess(max(parts[z-1][4:6]),first[1])
                    self.assertGreater(left[1],first[1])
        self.assertEqual((supported.count(True),supported.count(False)),(6,1))

        parts = inputs['cases']['2022-01-01-106']['parts']
        stages = [
            (11,115,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860))),False),
            (13,124,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,),(511981860000,567165473420))),False),
            (15,153,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15),(511981860000,567165473420))),False),
            (17,170,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15,17),(511981860000,577234450000))),False),
            (19,180,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15,17),(511981860000,577234450000)),((19,),(407577716000,461988337200))),True)]
        self.assertEqual(parts[10][6],106)  # 第一序列底先到，不代替第二序列顶。
        for last,count,wanted,complete in stages:
            self.assertEqual(parts[last][6],count)
            current = groups(parts,range(9,last+1,2),None)
            self.assertEqual(current,list(wanted))
            tops = [i for i in range(1,len(current)-1)
                    if all(current[i][1][k] > max(current[i-1][1][k],current[i+1][1][k]) for k in (0,1))]
            self.assertEqual(bool(tops),complete)
            if complete:
                self.assertEqual([current[i][0] for i in range(tops[0]-1,tops[0]+2)],[(11,),(13,15,17),(19,)])

    def test_factor_xd_local_proofs_and_shared_second_feature(self):
        """核给定分界的原邻笔几何；标准旧侧与种子前提另核，不称完整证明。"""
        inputs = embedded_table('test_real_f1_originals.py','M3_FACTOR_F1_AUDIT')['cases']
        audit = embedded_table('test_real_xd_f1.py','M3_FACTOR_XD_AUDIT')
        self.assertFalse(audit['independent_theory_labels'])
        self.assertFalse(audit['global_segmentation_independently_proven'])
        totals = [0,0]
        for key,case in audit['cases'].items():
            self.assertEqual(len(case['events']),len(case['local_proofs']))
            rows = inputs[key]['parts']
            bounds = lambda i:(min(rows[i][4:6]),max(rows[i][4:6]))
            for event,proof in zip(case['events'],case['local_proofs']):
                a,z,mode,last,count,known = event
                self.assertEqual(proof['event'],[a,z,mode,last])
                self.assertEqual(rows[last][6],count)
                self.assertGreater(known[:10],rows[last][3])
                self.assertGreater(last,z)
                self.assertEqual(proof['initial_core'],[max(bounds(i)[0] for i in range(a,a+3)),
                                                        min(bounds(i)[1] for i in range(a,a+3))])
                if mode == 1:
                    reverse = [bounds(i) for i in range(z+1,last+1)]
                    self.assertEqual(last-z,3)
                    self.assertLessEqual(max(r[0] for r in reverse),min(r[1] for r in reverse))
                    self.assertEqual(proof['reverse_core'],[max(r[0] for r in reverse),min(r[1] for r in reverse)])
                    up = rows[a][5] > rows[a][4]
                    self.assertTrue(bounds(z+1)[1] > bounds(z-1)[1] if up else bounds(z+1)[0] < bounds(z-1)[0])
                    self.assertTrue(bounds(z+1)[0] <= bounds(z-1)[1] if up else bounds(z+1)[1] >= bounds(z-1)[0])
                    if up:
                        self.assertLess(rows[last][5],rows[z+1][5])
                    else:
                        self.assertGreater(rows[last][5],rows[z+1][5])
                else:
                    self.assertEqual(key,'2022-01-01-106')
                    self.assertEqual(bounds(6)[0]-bounds(8)[1],11052784860)
                    self.assertEqual(proof['gap_ticks'],11052784860)
                    self.assertFalse(proof['gap_unfilled_at_proof'])
                    self.assertGreaterEqual(max(bounds(i)[1] for i in range(9,last+1)),bounds(6)[0])
                    self.assertTrue(bounds(8)[0]<min(bounds(6)[0],bounds(10)[0]))
                    self.assertTrue(bounds(8)[1]<min(bounds(6)[1],bounds(10)[1]))
                    first,container,later = bounds(13),bounds(15),bounds(17)
                    self.assertTrue(first[0]>=container[0] and first[1]<=container[1])
                    merged = (max(first[0],container[0]),max(first[1],container[1]))
                    self.assertTrue(later[0]<=merged[0] and later[1]>=merged[1])
                    merged = (max(merged[0],later[0]),max(merged[1],later[1]))
                    self.assertEqual(proof['second_top'],[*bounds(11),*merged,*bounds(19)])
                    self.assertGreater(merged[0],max(bounds(11)[0],bounds(19)[0]))
                    self.assertGreater(merged[1],max(bounds(11)[1],bounds(19)[1]))
                totals[mode-1] += 1
        self.assertEqual(totals,[7,1])

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
