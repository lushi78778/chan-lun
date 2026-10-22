# -*- coding: utf-8 -*-
"""R2样本提取的日期和缺测契约; 独立于核心识别器。"""
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

import pandas as pd

_PATH = Path(__file__).resolve().parents[2]/'validation/tools/index_core_samples.py'
_SPEC = importlib.util.spec_from_file_location('real_sample_index',str(_PATH))
_TOOL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TOOL)


def frame():
    return pd.DataFrame([
        dict(ts_code='512880.SH',trade_date='2024-07-01',open=2,high=3,low=1,
             close=2.5,vol=100,adj_factor=1),
        dict(ts_code='512880.SH',trade_date='2024-07-02',open=2.5,high=3.5,low=2,
             close=3,vol=200,adj_factor=1),
        dict(ts_code='512880.SH',trade_date='2024-07-03',open=3,high=4,low=2,
             close=3.5,vol=300,adj_factor=2)])


class TestRealSamplePacket(unittest.TestCase):
    def test_future_price_and_factor_poison_is_outside_packet(self):
        """先截原始观察日; 未来坏价/复权因子不影响已冻结输入。"""
        prices = frame()
        expected = _TOOL.packet_records(prices,'1d','2024-07-01','2024-07-02')
        prices.loc[2,['open','high','low','close','adj_factor']] = float('nan')
        self.assertEqual(_TOOL.packet_records(prices,'1d','2024-07-01','2024-07-02'),expected)
        self.assertEqual(len(expected),2)
        self.assertEqual(expected[-1]['adj_factor'],1)

    def test_missing_visible_factor_is_not_filled_from_future(self):
        """观察内缺因子拒绝, 不能采用未来已知因子2或默认1补空。"""
        prices = frame()
        prices.loc[1,'adj_factor'] = float('nan')
        with self.assertRaises(ValueError):
            _TOOL.packet_records(prices,'1d','2024-07-01','2024-07-02')

    def test_observation_is_a_closed_signal_day_not_an_intraday_time(self):
        """盘中时刻不按次日同一时刻截断; 开始日也不得晚于观察日。"""
        with self.assertRaises(ValueError):
            _TOOL.packet_records(frame(),'1d','2024-07-01','2024-07-02 09:30:00')
        with self.assertRaises(ValueError):
            _TOOL.packet_records(frame(),'1d','2024-07-03','2024-07-02')

    def test_empty_and_duplicate_visible_input_are_not_accepted(self):
        """空样本不等于通过; 重复代码时间不由提取器自动去重。"""
        with self.assertRaises(ValueError):
            _TOOL.packet_records(frame(),'1d','2024-08-01','2024-08-02')
        duplicate = pd.concat([frame(),frame().iloc[:1]],ignore_index=True)
        with self.assertRaises(ValueError):
            _TOOL.packet_records(duplicate,'1d','2024-07-01','2024-07-02')

    def test_visible_positive_prices_still_require_an_ohlc_envelope(self):
        """全部为正仍可错: 收盘超出最高价时拒绝, 不向上补high。"""
        prices = frame()
        prices.loc[1, 'close'] = 4
        with self.assertRaises(ValueError):
            _TOOL.packet_records(prices, '1d', '2024-07-01', '2024-07-02')

    def test_future_envelope_violation_is_removed_before_validation(self):
        """观察日之后的包络错误与坏因子一样, 不污染当前输入。"""
        prices = frame()
        expected = _TOOL.packet_records(prices, '1d', '2024-07-01', '2024-07-02')
        prices.loc[2, 'high'] = 1
        self.assertEqual(
            _TOOL.packet_records(prices, '1d', '2024-07-01', '2024-07-02'),
            expected)


class TestCsvStockIntake(unittest.TestCase):
    """外部原始个股的来源绑定、日期截断与错误拒绝; 不依赖行情服务。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'stock.csv'
        self.text = ('date,open,high,low,close,volume,factor,paused\n'
                     '2024-07-01,10,11,9,10.25,0,1.25,1\n'
                     '2024-07-02,10.25,12,10,11,200,1.5,0\n'
                     '2024-07-03,11,12,10,11.5,300,1.5,0\n')
        self.path.write_text(self.text, encoding='utf-8-sig')

    def packet(self, **changes):
        args = dict(path=self.path, code='600721.XSHG', period='1d',
                    start='2024-07-01', observation='2024-07-02',
                    source='fixture source', source_version='export-20240703',
                    timezone_name='Asia/Shanghai', adjustment='none',
                    time_label='date', volume_unit='shares')
        args.update(changes)
        return _TOOL.csv_packet(**args)

    def test_raw_factor_pause_and_external_digest_are_preserved(self):
        """跨分红的两行不提前复权; 停牌零量行保留, 原始字节绑定摘要。"""
        original = self.path.read_bytes()
        sha = hashlib.sha256(original).hexdigest()
        packet = self.packet(expected_sha256=sha)
        self.assertEqual(packet['source_digest_check'], 'matched_expected')
        self.assertEqual(packet['source_sha256'], sha)
        self.assertEqual(packet['dataset'], str(self.path.resolve()))
        self.assertEqual(packet['source_rows'], 3)
        self.assertEqual([(r['close'], r['vol'], r['adj_factor'], r['paused'])
                          for r in packet['rows']],
                         [(10.25, 0.0, 1.25, 1), (11.0, 200.0, 1.5, 0)])
        self.assertFalse(packet['theoretical_acceptance'])
        self.assertFalse(packet['algorithm_labels_generated'])
        self.assertNotIn('available_dt', packet['rows'][0])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.packet()['source_digest_check'], 'calculated_only')
        with self.assertRaisesRegex(ValueError, '摘要'):
            self.packet(expected_sha256='0' * 64)

    def test_future_numeric_poison_is_removed_before_validation(self):
        """未来价、量、因子和停牌错误只改变源摘要, 不改变可见行情。"""
        before = self.packet()
        self.path.write_text(self.text.replace('11,12,10,11.5,300,1.5,0',
                                              'nan,0,-1,bad,-1,,9'))
        after = self.packet()
        self.assertEqual(after['rows'], before['rows'])
        self.assertNotEqual(after['source_sha256'], before['source_sha256'])

    def test_canonical_minutes_require_one_code_and_keep_time_label(self):
        """分钟开始标签是来源声明; 不虚构结束或实际到达。"""
        self.path.write_text('ts_code,dt,open,high,low,close,vol,adj_factor\n'
                             '600721.XSHG,2024-07-02 09:30:00,10,11,9,10,100,1\n')
        packet = self.packet(period='30m', time_label='start', layout='canonical')
        self.assertEqual(packet['time_label'], 'start')
        self.assertEqual(packet['rows'][0]['dt'], '2024-07-02 09:30:00')
        self.assertNotIn('closed_dt', packet['rows'][0])
        self.assertNotIn('paused', packet['rows'][0])
        with self.assertRaisesRegex(ValueError, '布局'):
            self.packet(period='30m', time_label='start', layout='joinquant')
        for code in ['600865.XSHG', '600721.SH']:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, '代码'):
                self.packet(code=code, period='30m', time_label='end', layout='canonical')
        self.path.write_text(self.path.read_text() +
                             '600865.XSHG,2024-07-02 10:00:00,10,11,9,10,100,1\n')
        with self.assertRaisesRegex(ValueError, '多个标的'):
            self.packet(period='30m', time_label='unknown', layout='canonical')

    def test_source_and_coordinate_declarations_cannot_be_guessed(self):
        """不从价格猜复权、时区、周期或时间标签, 未声明来源不得接收。"""
        for changes in [dict(source=' '), dict(source_version=''), dict(code=''),
                        dict(timezone_name='UTC'), dict(adjustment='pre'),
                        dict(time_label='end'), dict(period='weekly'),
                        dict(volume_unit='auto'), dict(layout='auto')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.packet(**changes)

    def test_unknown_minute_grid_and_volume_are_preserved_without_repairs(self):
        """09:30可为非平价桶; 零量不推停牌, 大量值不自动除100。"""
        self.path.write_text(
            'ts_code,dt,open,high,low,close,vol,adj_factor\n'
            '600721.XSHG,2024-07-02 09:30:00,1734,1736,1733.4599609375,1736,19397500,1.25\n'
            '600721.XSHG,2024-07-02 09:35:00,1736,1736,1736,1736,0,1.25\n'
            '600721.XSHG,2024-07-02 10:00:00,1735,1738,1734,1737,100,1.25\n')
        original = self.path.read_bytes()
        # 合成输入只验证接收边界, 不证明某个供应商的真实周期或数量单位。
        for period in ('5m', '30m'):
            with self.subTest(period=period):
                packet = self.packet(period=period, time_label='unknown',
                                     volume_unit='unknown', layout='canonical')
                self.assertEqual(packet['time_label'], 'unknown')
                self.assertEqual(packet['volume_unit'], 'unknown')
                self.assertEqual(len(packet['rows']), 3)
                self.assertEqual([r['vol'] for r in packet['rows']],
                                 [19397500.0, 0.0, 100.0])
                self.assertEqual(packet['rows'][0]['dt'], '2024-07-02 09:30:00')
                self.assertEqual(packet['rows'][0]['low'], 1733.4599609375)
                self.assertFalse(packet['theoretical_acceptance'])
                for row in packet['rows']:
                    for name in ('paused', 'closed_dt', 'available_dt'):
                        self.assertNotIn(name, row)
        self.assertEqual(self.path.read_bytes(), original)

    def test_visible_bad_rows_are_not_repaired_or_dropped(self):
        """缺因子、坏包络/量/停牌、重复及乱序均拒绝, 不能静默生成可用包。"""
        variants = [
            self.text.replace('200,1.5,0', '200,,0'),
            self.text.replace('10.25,12,10,11,200', '10.25,10.5,10,11,200'),
            self.text.replace('200,1.5,0', '-1,1.5,0'),
            self.text.replace('200,1.5,0', '200,1.5,2'),
            self.text.replace('2024-07-02', '2024-07-01'),
            self.text.replace('2024-07-01', '2024-07-02', 1).replace(
                '2024-07-02,10.25', '2024-07-01,10.25'),
            self.text.replace('2024-07-02', '2024/07/02'),
            self.text.replace('2024-07-02', '2024-07-02 00:00:00'),
        ]
        for text in variants:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.path.write_text(text)
                self.packet()
        self.path.write_text(self.text)
        with self.assertRaises(ValueError):
            self.packet(start='2024-08-01', observation='2024-08-02')
        with self.assertRaises(ValueError):
            self.packet(start='2024-07-03', observation='2024-07-02')

    def test_zero_minute_volume_does_not_override_explicit_pause(self):
        """合成零量分钟分别保留给定paused=0/1, 不从零量推断停牌。"""
        self.path.write_text(
            'date,open,high,low,close,volume,factor,paused\n'
            '2024-07-01 09:31:00,10,10,10,10,0,1.25,0\n'
            '2024-07-02 09:31:00,10,10,10,10,0,1.25,1\n')
        original = self.path.read_bytes()
        packet = self.packet(period='1m', time_label='end')
        self.assertEqual([r['vol'] for r in packet['rows']], [0.0, 0.0])
        self.assertEqual([r['paused'] for r in packet['rows']], [0, 1])
        self.assertFalse(packet['theoretical_acceptance'])
        for row in packet['rows']:
            self.assertNotIn('closed_dt', row)
            self.assertNotIn('available_dt', row)
        self.assertEqual(self.path.read_bytes(), original)

    def test_malformed_headers_and_missing_factor_do_not_get_defaults(self):
        """重复/冲突列与截断CSV不得被pandas自动改名或补空后接受。"""
        for text in [self.text.replace('volume', 'open'),
                     self.text.replace('factor', 'unused'),
                     self.text.replace(',factor,paused', ',factor,adj_factor'),
                     self.text.replace('200,1.5,0', '200,1.5'),
                     self.text.splitlines()[0] + '\n', '']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.path.write_text(text)
                self.packet()

    def test_cli_is_standalone_and_refuses_overwrite(self):
        """真实CLI从任意cwd运行, 不需要chan/pyarrow; 既有收据不覆盖。"""
        output = Path(self.temp.name) / 'receipt.json'
        command = [sys.executable, '-I', str(_PATH), 'import-csv', str(self.path),
                   '--periods', '1d', '--codes', '600721.XSHG',
                   '--start', '2024-07-01', '--observation', '2024-07-02',
                   '--csv-layout', 'joinquant', '--source', 'fixture source',
                   '--source-version', 'export-20240703', '--timezone', 'Asia/Shanghai',
                   '--adjustment', 'none', '--time-label', 'date', '--output', str(output)]
        result = subprocess.run(command, cwd=self.temp.name, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(output.resolve()))
        self.assertEqual(len(json.loads(output.read_text())['rows']), 2)
        before = output.read_bytes()
        result = subprocess.run(command, cwd=self.temp.name, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('拒绝覆盖', result.stderr)
        self.assertEqual(output.read_bytes(), before)
        self.assertNotIn('import chan', _PATH.read_text())


if __name__=='__main__':
    unittest.main()
