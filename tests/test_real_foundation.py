# -*- coding: utf-8 -*-
"""课62/65/67/78/81/106真实原始行的独立算术标注。

固定证券ETF日线窗口, 人工合并组/分型/笔及待确认XD先于算法对比
冻结。使用嵌入的只读源行, 不要求开发机安装外部数据目录; 摘要与
原始输入包由外层核验。窗口外继承、完成F1和点位不在此样本范围。
"""
from datetime import datetime, timedelta
import json
import os
import sys
import unittest

sys.path.insert(0,os.path.join(os.path.dirname(os.path.dirname(__file__)),'src'))
from chan import analyze_at, chan_fx_bi, find_xds


def load_label():
    with open(os.path.join(os.path.dirname(__file__),'fixtures','real_foundation.json')) as stream:
        return json.load(stream)[0]


def source_bars(rows):
    """本窗口因子全部为1, 保留原始OHLC并显式标明日线时间。"""
    bars = []
    for row in rows:
        assert row['adj_factor']==1, '新因子样本须单独冻结观察锚与算术'
        bars.append(dict(dt=datetime.strptime(row['dt'][:10],'%Y-%m-%d'),
                         open=row['open'],high=row['high'],low=row['low'],
                         close=row['close'],volume=row['vol']))
    return bars


def fx_records(fxs):
    return [[f.kind,f.bar_index,round(f.value*1000)] for f in fxs]


def bi_records(bis):
    return [[b.direction,b.start_index,b.end_index,
             round(b.start_value*1000),round(b.end_value*1000)] for b in bis]


class TestRealFoundation(unittest.TestCase):
    def test_independent_inclusion_groups_and_fractals(self):
        """课62/65: 顺序含组及三邻严格双极值, 与25行人工表逐项一致。"""
        label = load_label()
        bars,fxs,_ = chan_fx_bi(source_bars(label['raw_rows']))
        self.assertEqual([dict(elements=b.elements,low_ticks=round(b.low*1000),
                               high_ticks=round(b.high*1000)) for b in bars],
                         label['expected_new_bars'])
        self.assertEqual(fx_records(fxs),label['expected_fx'])
        self.assertEqual([f.dt for f in fxs],
                         [datetime.strptime(label['raw_rows'][bars[f.bar_index].elements[-1]]['dt'][:10],'%Y-%m-%d') for f in fxs])

    def test_81_and_106_stroke_conditions_and_unfinished_xd(self):
        """课81/106: 间距不足否决、同向不够极端忽略及MA5必要条件。

        三笔交集[789,790]有一个待确认下段, 净端点不代替内部
        实际包络[743,813], 裸三笔不自动成为完成F1。
        """
        label = load_label()
        raw = source_bars(label['raw_rows'])
        for standard in ['81','106']:
            _,_,bis = chan_fx_bi(raw,standard=standard)
            self.assertEqual(bi_records(bis),label['expected_bis_'+standard])
            xds = find_xds(bis)
            self.assertEqual([[x.start_index,x.end_index,x.mode,x.complete] for x in xds],
                             label['expected_xds'])
            self.assertEqual([round(xds[0].low*1000),round(xds[0].high*1000)],
                             label['expected_xd_range_ticks'])
            self.assertIsNone(xds[0].evidence_dt)
        closes = [b['close'] for b in raw]
        self.assertAlmostEqual(sum(closes[:5])/5,0.7766)
        self.assertAlmostEqual(sum(closes[3:8])/5,0.762)
        self.assertAlmostEqual(sum(closes[17:22])/5,0.791)

    def test_raw_confirmation_prefixes_are_independent_of_endpoint_day(self):
        """课65/81: 右邻出现才形成分型, 不把端点日算作可见确认日。"""
        label = load_label()
        raw = source_bars(label['raw_rows'])
        for count,expected in label['observations'].items():
            _,fxs,bis = chan_fx_bi(raw[:int(count)])
            self.assertEqual(fx_records(fxs),expected['fx'],count)
            self.assertEqual(bi_records(bis),expected['bis'],count)

    def test_future_poison_does_not_change_the_observed_real_prefix(self):
        """先截原始行情; 未来NaN价/新增极端结构不影响已观察窗口。"""
        raw = source_bars(load_label()['raw_rows'])
        observation = raw[-1]['dt']
        original = analyze_at(raw,observation).to_dict()
        future = dict(dt=observation+timedelta(days=1),open=float('nan'),
                      high=float('nan'),low=-999,close=99999,volume=1)
        self.assertEqual(analyze_at(raw+[future],observation).to_dict(),original)


if __name__=='__main__':
    unittest.main()
