# -*- coding: utf-8 -*-
"""课62/65/67/71/78/81/106真实日线四窗口的独立线段标注。

512880上市首段(两标准分叉与未完成反例)、2025自然边界窗口(第一种
完成线段)、2022窗口(第一/第二种完成线段)与159915古怪线段窗口的
合并组/分型/两标准笔/线段先于算法对比冻结。全部原始日前缀逐项回放,
验证已完成段身份稳定、确认证据笔延伸与首次确认计数。使用嵌入的
只读源行, 不要求开发机安装外部数据目录; 摘要与输入包由外层核验。
"""
from datetime import datetime, timedelta
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))
from chan import analyze_at, chan_fx_bi, find_xds


def load_windows():
    with open(os.path.join(os.path.dirname(__file__), 'fixtures',
                           'real_xd_originals.json')) as stream:
        return json.load(stream)


def source_bars(rows):
    """四窗口因子全部为1, 保留原始OHLC并显式标明日线时间。"""
    bars = []
    for row in rows:
        assert row['adj_factor'] == 1, '新因子样本须单独冻结观察锚与算术'
        bars.append(dict(dt=datetime.strptime(row['dt'][:10], '%Y-%m-%d'),
                         open=row['open'], high=row['high'], low=row['low'],
                         close=row['close'], volume=row['vol']))
    return bars


def fx_records(fxs):
    return [[f.kind, f.bar_index, round(f.value * 1000)] for f in fxs]


def bi_records(bis):
    return [[b.direction, b.start_index, b.end_index,
             round(b.start_value * 1000), round(b.end_value * 1000)] for b in bis]


def xd_sig(xds):
    return [[x.start_index, x.end_index, x.mode, bool(x.complete),
             x.evidence_end_index] for x in xds]


def xd_records(xds):
    """富线段记录: 方向/索引/价位/日期/模式/完成/证据/内部极值。"""
    records = []
    for x in xds:
        records.append(dict(
            direction=x.direction,
            start_index=x.start_index, end_index=x.end_index,
            start_ticks=round(x.start_value * 1000),
            end_ticks=round(x.end_value * 1000),
            start_dt=str(x.start_dt)[:10], end_dt=str(x.end_dt)[:10],
            mode=x.mode, complete=bool(x.complete),
            evidence_end_index=x.evidence_end_index,
            evidence_dt=(str(x.evidence_dt)[:10]
                         if x.evidence_dt is not None else None),
            gg_ticks=(round(x.gg * 1000) if x.gg is not None else None),
            dd_ticks=(round(x.dd * 1000) if x.dd is not None else None)))
    return records


class TestRealXdOriginals(unittest.TestCase):
    def test_full_tables_match_frozen_labels(self):
        """四窗口合并组/分型/两标准笔/线段全表与冻结标注逐项一致。"""
        for label in load_windows():
            raw = source_bars(label['raw_rows'])
            for standard in ('81', '106'):
                bars, fxs, bis = chan_fx_bi(raw, standard=standard)
                self.assertEqual(
                    [dict(elements=b.elements, low_ticks=round(b.low * 1000),
                          high_ticks=round(b.high * 1000)) for b in bars],
                    label['expected_new_bars'], (label['id'], standard))
                self.assertEqual(fx_records(fxs), label['expected_fx'],
                                 (label['id'], standard))
                self.assertEqual(
                    [f.dt for f in fxs],
                    [datetime.strptime(
                        label['raw_rows'][bars[f.bar_index].elements[-1]]['dt'][:10],
                        '%Y-%m-%d') for f in fxs], (label['id'], standard))
                self.assertEqual(bi_records(bis),
                                 label['expected_bis_' + standard],
                                 (label['id'], standard))
                xds = find_xds(bis)
                self.assertEqual(xd_records(xds),
                                 label['expected_xds_' + standard],
                                 (label['id'], standard))
                self.assertEqual(xd_sig(xds),
                                 label['observations'][str(len(raw))][standard]['xds'],
                                 (label['id'], standard))

    def test_frozen_samples_cover_divergence_modes_and_weird_segment(self):
        """冻结样本覆盖两标准分叉、两种完成模式、古怪线段与未完成反例。"""
        labels = load_windows()
        by_id = dict((item['id'], item) for item in labels)
        first = by_id['512880-day-2016-08-08-2016-12-26']
        self.assertNotEqual(first['expected_bis_81'], first['expected_bis_106'])
        self.assertFalse(any(x['complete'] for x in first['expected_xds_81']))
        self.assertFalse(any(x['complete'] for x in first['expected_xds_106']))
        second = by_id['512880-day-2025-08-21-2025-10-31']
        self.assertTrue(all(x['mode'] == 1 and x['complete']
                            for x in second['expected_xds_81'][:1]))
        third = by_id['512880-day-2022-04-20-2022-12-09']
        self.assertEqual(third['expected_xds_81'][0]['mode'], 2)
        self.assertTrue(third['expected_xds_81'][0]['complete'])
        self.assertEqual(third['expected_xds_106'][0]['mode'], 1)
        weird = by_id['159915-day-2016-05-05-2016-11-16']
        for standard in ('81', '106'):
            weird_xd = weird['expected_xds_' + standard][0]
            self.assertTrue(weird_xd['complete'])
            self.assertGreater(weird_xd['gg_ticks'], weird_xd['end_ticks'])

    def test_raw_prefixes_confirm_once_and_never_rewrite_completed_xds(self):
        """逐原始日前缀: 观察与冻结一致; 已完成段身份不回写, 证据笔端点只延伸。"""
        for label in load_windows():
            raw = source_bars(label['raw_rows'])
            total = len(raw)
            seen = {'81': {}, '106': {}}
            extensions = []
            for count in range(1, total + 1):
                observation = label['observations'][str(count)]
                for standard in ('81', '106'):
                    _, fxs, bis = chan_fx_bi(raw[:count], standard=standard)
                    self.assertEqual(len(fxs), observation['fx_n'],
                                     (label['id'], standard, count))
                    self.assertEqual(len(bis),
                                     observation[standard]['bis_n'],
                                     (label['id'], standard, count))
                    sig = xd_sig(find_xds(bis))
                    self.assertEqual(sig, observation[standard]['xds'],
                                     (label['id'], standard, count))
                    for item in sig:
                        if not item[3]:
                            continue
                        identity = (item[0], item[1], item[2])
                        if identity in seen[standard]:
                            previous = seen[standard][identity]
                            self.assertTrue(previous[0][3] and
                                            item[4] >= previous[1],
                                            (label['id'], standard, count,
                                             identity, previous, item))
                            if item[4] > previous[1]:
                                extensions.append(
                                    [standard, item[0], item[1],
                                     previous[1], item[4]])
                            previous[0] = item
                            previous[1] = item[4]
                        else:
                            seen[standard][identity] = [item, item[4]]
                            self.assertIn(
                                [item[0], item[1], item[2], count],
                                label['xd_first_confirmed_raw_counts'][standard],
                                (label['id'], standard, count, identity))
                    for identity in seen[standard]:
                        self.assertTrue(
                            any(item[0] == identity[0] and
                                item[1] == identity[1] and
                                item[2] == identity[2] and item[3]
                                for item in sig),
                            (label['id'], standard, count, identity))
            self.assertEqual(extensions, label['evidence_end_extension'],
                             label['id'])
            for standard in ('81', '106'):
                confirmed = [[item[0], item[1], item[2], item[3]]
                             for item in label['xd_first_confirmed_raw_counts'][standard]]
                self.assertEqual(confirmed,
                                 sorted(confirmed, key=lambda record: record[3]),
                                 (label['id'], standard))

    def test_future_poison_does_not_change_the_observed_real_window(self):
        """先截原始行情; 未来NaN价/极端结构不影响已观察窗口。"""
        for label in load_windows():
            raw = source_bars(label['raw_rows'])
            observation = raw[-1]['dt']
            original = analyze_at(raw, observation).to_dict()
            future = dict(dt=observation + timedelta(days=1),
                          open=float('nan'), high=float('nan'),
                          low=-999, close=99999, volume=1)
            self.assertEqual(analyze_at(raw + [future], observation).to_dict(),
                             original, label['id'])


if __name__ == '__main__':
    unittest.main()
