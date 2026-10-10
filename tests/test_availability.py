# -*- coding: utf-8 -*-
"""日线日期标签、收盘、到达时间与结构确认前缀的工程契约。"""
import json
import math
import os
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan.availability import analyze_available, replay_available
from chan import analyze_bars


def bars(n=220):
    out=[]
    for i in range(n):
        dt=datetime(2025,1,1)+timedelta(days=i)
        p=20+3*math.sin(i/6.0)+i/80.0
        out.append(dict(dt=dt, closed_dt=dt+timedelta(hours=15),
                        available_dt=dt+timedelta(hours=15,minutes=5),
                        open=p, close=p, high=p+.3, low=p-.3, volume=1000))
    return out


class TestAvailability(unittest.TestCase):
    def test_daily_label_not_visible_at_midnight_or_before_arrival(self):
        """同日日线在00:00和15:00尚不可见, 15:05才可参与计算。"""
        data=bars(2)
        for cutoff in [data[1]['dt'],data[1]['closed_dt']]:
            self.assertEqual(analyze_available(data,cutoff).as_of,data[0]['dt'])
        self.assertEqual(analyze_available(data,data[1]['available_dt']).as_of,data[1]['dt'])

    def test_future_price_poison_is_not_read(self):
        """未来或尚未到达的OHLCV不能影响结果。"""
        data=bars(80);cut=data[50]['available_dt']
        expected=analyze_bars(data[:51]).to_dict()
        for row in data[51:]:
            row.pop('open');row['high']=float('inf');row['low']=float('nan')
        self.assertEqual(analyze_available(data,cut).to_dict(),expected)

    def test_no_metadata_fallback(self):
        """缺失时间不退回日期标签, 阻止盘中误用全日OHLC。"""
        for key in ['closed_dt','available_dt']:
            data=bars(1);data[0].pop(key)
            with self.assertRaisesRegex(ValueError,'时间元数据'):
                analyze_available(data,datetime(2025,1,2))
        with self.assertRaises(ValueError):
            list(replay_available([{'dt':datetime(2025,1,1)}]))

    def test_invalid_metadata_chronology_and_mixed_kind(self):
        """收盘不能早于标签, 到达不能早于收盘, 不混时区表示。"""
        for field,value in [('closed_dt',datetime(2024,12,31)),
                            ('available_dt',datetime(2025,1,1)),
                            ('available_dt','2025-01-01')]:
            data=bars(1);data[0][field]=value
            with self.assertRaises(ValueError):
                analyze_available(data,datetime(2025,1,2))

    def test_each_snapshot_equals_independent_visible_prefix(self):
        """逐观察实际前缀等价; 并不以全样本结构过滤代替。"""
        data=bars(90)
        for i,snap in enumerate(replay_available(data)):
            self.assertEqual(snap.result.to_dict(),analyze_bars(data[:i+1]).to_dict())
            self.assertEqual(snap.observed_dt,data[i]['available_dt'])

    def test_only_preceded_bis_and_completed_xds_enter_structure_records(self):
        """末筆排除; 线段确认记录只能由固定笔构造, 不能倒填到端点。"""
        data=bars(170)
        points=[20,25,22,32,25,29,21,26,22,30,23,27,20,25,21,29,24,28,22,26,20,25,22]
        for i,row in enumerate(data):
            j,r=divmod(i,8)
            price=points[j]+(points[j+1]-points[j])*r/8.0
            row.update(open=price,close=price,high=price+.1,low=price-.1)
        observations=[row['available_dt'] for row in data]
        kinds=set()
        for snap in replay_available(data,observations):
            counted=sum(x.kind=='bi' for x in snap.structures)
            self.assertEqual(counted,max(0,len(snap.result.bis)-1))
            for item in snap.structures:
                kinds.add(item.kind)
                self.assertLessEqual(item.first_seen,item.observed_dt)
                if item.kind=='xd':
                    self.assertTrue(item.record['complete'])
                    self.assertLess(item.record['evidence_dt'],str(item.first_seen))
        self.assertIn('bi',kinds)
        self.assertIn('xd',kinds)

    def test_snapshot_mutations_do_not_pollute_ledger(self):
        """确认结构及变更都是独立快照, 消费者写入不污染历史。"""
        data=bars(240)
        gen=replay_available(data,[row['available_dt'] for row in data[120:125]])
        first=next(gen);original=deepcopy(first.to_dict())
        self.assertTrue(first.structures)
        first.structures[0].record['direction']='tampered'
        for snap in gen:
            self.assertFalse(any('tampered' in str(x.to_dict()) for x in snap.changes))
        json.dumps(original,allow_nan=False)

    def test_closed_empty_and_duplicate_observations(self):
        """空可见前缀合法; 观察网格不能逆序或重复。"""
        self.assertEqual(list(replay_available([])),[])
        self.assertIsNone(analyze_available(bars(1),datetime(2024,12,31)).as_of)
        dt=bars(1)[0]['available_dt']
        with self.assertRaises(ValueError):
            list(replay_available(bars(1),[dt,dt]))

    def test_same_arrival_batches_default_observations(self):
        """多根行情同批到达只计算一个观察时点, 不伪造逐根更早可见。"""
        data=bars(3)
        for row in data:row['available_dt']=data[-1]['available_dt']
        snapshots=list(replay_available(data))
        self.assertEqual(len(snapshots),1)
        self.assertEqual(len(snapshots[0].result.hist),3)
