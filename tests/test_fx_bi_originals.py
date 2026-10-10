# -*- coding: utf-8 -*-
"""课62原图1至7全组标注, 相对价格保留几何而非市场报价。"""
import json
import os
import unittest
from datetime import datetime,timedelta
from chan import remove_includes,find_fxs,find_bis

class TestOriginalFxBi(unittest.TestCase):
    def test_all_definition_diagrams_and_mirrors(self):
        with open(os.path.join(os.path.dirname(__file__),'fixtures','fx_bi_originals.json')) as f:
            cases=json.load(f)
        for c in cases:
            for mirror in [False,True]:
                with self.subTest(case=c['id'],mirror=mirror):
                    ranges=([[20-high,20-low] for low,high in c['ranges']]
                            if mirror else c['ranges'])
                    rows=[dict(dt=datetime(2025,1,1)+timedelta(days=i),low=low,high=high,
                               open=(low+high)/2.,close=(low+high)/2.,volume=1.)
                          for i,(low,high) in enumerate(ranges)]
                    nb=remove_includes(rows)
                    if c['kind']=='include':
                        expected=([[20-high,20-low] for low,high in c['expected']]
                                  if mirror else c['expected'])
                        self.assertEqual([[b.low,b.high] for b in nb],expected)
                    elif c['kind']=='fx':
                        expected=[('bottom' if k=='top' else 'top') if mirror else k for k in c['expected']]
                        self.assertEqual([x.kind for x in find_fxs(nb)],expected)
                        self.assertEqual(find_fxs(nb[:2]),[])
                    else:
                        expected=[[a,b,('up' if d=='down' else 'down') if mirror else d]
                                  for a,b,d in c['expected']]
                        self.assertEqual([[b.start_index,b.end_index,b.direction] for b in find_bis(nb)],expected)
