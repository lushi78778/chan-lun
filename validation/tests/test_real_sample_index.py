# -*- coding: utf-8 -*-
"""样本提取与发现输入的日期、质量和来源契约；独立于核心识别器。"""
import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_PATH = ROOT/'validation/tools/index_core_samples.py'
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


class TestDiscoveryInputGuards(unittest.TestCase):
    """发现输入不得删坏行拼接；不重跑网格或生成独立市场标签。"""

    @staticmethod
    def scanners():
        previous = list(sys.path)
        try:
            sys.path.insert(0, str(ROOT / 'validation/tools'))
            modules = []
            for name in ('scan_real_strict_trend', 'scan_real_first_point'):
                spec = importlib.util.spec_from_file_location(
                    name+'_guard_assets', ROOT / 'validation/tools' / (name+'.py'))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                modules.append(module)
            return modules
        finally:
            sys.path[:] = previous

    @staticmethod
    def frame():
        import pandas as pd
        return pd.DataFrame([
            dict(ts_code='510300.SH', trade_date='2026-01-0'+str(i+1),
                 open=10., high=11., low=9., close=10., vol=0., adj_factor=1.)
            for i in range(3)])

    def test_complete_input_keeps_all_rows_zero_volume_and_factor_boundaries(self):
        import pandas as pd
        source = self.frame()
        source.loc[2, 'adj_factor'] = 2.
        source.index = [3, 5, 7]
        before = source.copy(deep=True)
        for tool in self.scanners():
            result = tool.clean_rows(source)
            pd.testing.assert_frame_equal(result, before.reset_index(drop=True))
            result.loc[0, 'close'] = 99.
            pd.testing.assert_frame_equal(source, before)

    def test_bad_middle_row_is_rejected_instead_of_joining_its_neighbors(self):
        import pandas as pd
        changes = [('close', float('nan')), ('high', float('inf')), ('open', -1.),
                   ('adj_factor', 0.), ('adj_factor', float('nan')), ('vol', -1.),
                   ('vol', float('nan')), ('low', 12.), ('close', 20.)]
        for tool in self.scanners():
            for field, value in changes:
                with self.subTest(tool=tool.__name__, field=field, value=str(value)):
                    source = self.frame()
                    source.loc[1, field] = value
                    before = source.copy(deep=True)
                    with self.assertRaises(ValueError):
                        tool.clean_rows(source)
                    pd.testing.assert_frame_equal(source, before)
            for value in (True, '10'):
                source = self.frame().astype(object)
                source.loc[1, 'close'] = value
                with self.assertRaises(ValueError):
                    tool.clean_rows(source)

    def test_duplicate_unsorted_missing_or_mixed_grain_cannot_be_silently_repaired(self):
        source = self.frame()
        duplicate = source.copy(); duplicate.loc[1, 'trade_date'] = duplicate.loc[0, 'trade_date']
        mixed = source.copy(); mixed.loc[1, 'ts_code'] = '510500.SH'
        invalid = source.copy(); invalid.loc[1, 'trade_date'] = 'not-a-date'
        numeric = source.copy(); numeric['trade_date'] = [1, 2, 3]
        variants = (source.iloc[::-1], duplicate, mixed, invalid, numeric,
                    source.iloc[:0], source.drop(columns=['close']), source.drop(columns=['trade_date']))
        for tool in self.scanners():
            for frame in variants:
                with self.assertRaises(ValueError):
                    tool.clean_rows(frame)

    def test_declared_minute_cutoff_excludes_future_prices_but_not_bad_time_metadata(self):
        tool = self.scanners()[1]
        source = self.frame().rename(columns={'trade_date': 'trade_time'})
        source['trade_time'] = ['2026-07-24 15:00:00', '2026-07-27 09:30:00', '2026-07-28 09:30:00']
        source.loc[1:, 'close'] = float('nan')
        self.assertEqual(tool.scan_code_period('510300.SH', {'510300.SH': source}, '30m',
                                              None, '2026-07-27', 18), [])
        bad_visible = source.copy(); bad_visible.loc[0, 'close'] = float('nan')
        with self.assertRaises(ValueError):
            tool.scan_code_period('510300.SH', {'510300.SH': bad_visible}, '30m', None, '2026-07-27', 18)
        bad_clock = source.copy(); bad_clock.loc[2, 'trade_time'] = 'invalid'
        with self.assertRaises(ValueError):
            tool.scan_code_period('510300.SH', {'510300.SH': bad_clock}, '30m', None, '2026-07-27', 18)

    def test_receipt_writer_rejects_existing_and_symlink_paths_without_truncation(self):
        for tool in self.scanners():
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp)/'receipt.json'
                tool.write_discovery_result(output, {'ok': True})
                before = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    tool.write_discovery_result(output, {'ok': False})
                self.assertEqual(output.read_bytes(), before)
                target = Path(temp)/'absent.json'
                link = Path(temp)/'link.json'; link.symlink_to(target)
                with self.assertRaises(FileExistsError):
                    tool.write_discovery_result(link, {'ok': True})
                self.assertFalse(target.exists())
                self.assertTrue(link.is_symlink())
                malformed = Path(temp)/'nan.json'
                with self.assertRaises(ValueError):
                    tool.write_discovery_result(malformed, {'bad': float('nan')})
                self.assertFalse(malformed.exists())

    def test_cli_existing_or_dangling_receipt_is_rejected_before_loading_dataset(self):
        for tool in self.scanners():
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp)/'receipt.json'; output.write_bytes(b'frozen evidence')
                link = Path(temp)/'dangling.json'; target = Path(temp)/'target.json'; link.symlink_to(target)
                for path in (output, link):
                    run = subprocess.run([sys.executable, tool.__file__, '--dataset', str(Path(temp)/'missing'),
                                          '--output', str(path)], cwd=temp, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, universal_newlines=True)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn('拒绝覆盖', run.stderr)
                self.assertEqual(output.read_bytes(), b'frozen evidence')
                self.assertFalse(target.exists())

    def test_missing_requested_period_does_not_become_zero_candidate_result(self):
        tool = self.scanners()[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'manifest.json').write_text(json.dumps({'datasets': {}}))
            output = root/'result.json'
            run = subprocess.run([sys.executable, tool.__file__, '--dataset', str(root),
                                  '--output', str(output), '--periods', '1d'], cwd=temp,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('不能写成零候选', run.stderr)
            self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError, '不能写成零候选'):
            self.scanners()[1].scan_code_period('510300.SH', {}, '1d', None, '2026-07-27', 18)


class TestDiscoveryPartitionIntegrity(unittest.TestCase):
    """分区摘要绑定读取字节；解析替身只验加载合同，不冒充真实Parquet。"""

    @staticmethod
    def call_loader(tool, root, receipt, period='1d'):
        args = [root, period, ['510300.SH']]
        if 'scan_real_first_point' in tool.__name__:
            args.append(None if period == '1d' else ('2026',))
        return tool.load_frames(*args, receipt=receipt)

    @staticmethod
    def parser(frame, during_read=None):
        from types import ModuleType, SimpleNamespace
        from unittest.mock import Mock
        parent, parquet = ModuleType('pyarrow'), ModuleType('pyarrow.parquet')
        parent.__path__ = []
        parent.parquet = parquet
        table = SimpleNamespace(num_rows=len(frame), to_pandas=lambda: frame.copy(deep=True))
        def read(*args, **kwargs):
            if during_read is not None:
                during_read()
            return table
        parquet.read_table = Mock(side_effect=read)
        return {'pyarrow': parent, 'pyarrow.parquet': parquet}, parquet.read_table

    @staticmethod
    def manifest(root, item, period='1d'):
        (root/'manifest.json').write_text(json.dumps({'datasets': {period: {'files': [item]}}}))

    def test_verified_partition_preserves_loader_result_and_records_actual_read_scope(self):
        import pandas as pd
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame()
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'bars.parquet'; path.write_bytes(b'frozen partition')
                item = dict(path=path.name, partition='all', sha256=tool.digest(path))
                self.manifest(root, item)
                fake, read = self.parser(frame)
                receipt = []
                with patch.dict(sys.modules, fake):
                    frames, key = self.call_loader(tool, root, receipt)
                pd.testing.assert_frame_equal(frames['510300.SH'], frame)
                self.assertEqual(key, 'trade_date')
                self.assertEqual(receipt, [dict(item, columns=list(frame.columns),
                                               codes=['510300.SH'], rows_read=3)])
                self.assertEqual(read.call_count, 1)
                self.assertEqual(read.call_args[1]['filters'], [('ts_code', 'in', ['510300.SH'])])

    def test_absent_invalid_or_changed_hash_rejects_before_parquet_parser(self):
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame()
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'bars.parquet'; path.write_bytes(b'actual partition')
                for expected in (None, 'bad', '0'*64):
                    item = dict(path=path.name, partition='all')
                    if expected is not None:
                        item['sha256'] = expected
                    self.manifest(root, item)
                    fake, read = self.parser(frame); receipt = []
                    with patch.dict(sys.modules, fake), self.assertRaisesRegex(ValueError, 'SHA-256'):
                        self.call_loader(tool, root, receipt)
                    self.assertEqual(read.call_count, 0)
                    self.assertEqual(receipt, [])

    def test_partition_changed_during_parser_is_not_registered_as_verified(self):
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame()
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'bars.parquet'; path.write_bytes(b'before')
                self.manifest(root, dict(path=path.name, partition='all', sha256=tool.digest(path)))
                fake, read = self.parser(frame, lambda: path.write_bytes(b'after'))
                receipt = []
                with patch.dict(sys.modules, fake), self.assertRaisesRegex(ValueError, '读取期间改变'):
                    self.call_loader(tool, root, receipt)
                self.assertEqual(read.call_count, 1)
                self.assertEqual(receipt, [])

    def test_partition_selection_never_reads_unselected_file_and_empty_selection_fails(self):
        import pandas as pd
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame().rename(columns={'trade_date': 'trade_time'})
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'selected.parquet'; path.write_bytes(b'selected')
                selected = dict(path=path.name, partition='2026', sha256=tool.digest(path))
                unselected = dict(path='absent.parquet', partition='2025', sha256='0'*64)
                (root/'manifest.json').write_text(json.dumps({'datasets': {'30m': {'files': [unselected, selected]}}}))
                fake, read = self.parser(frame); receipt = []
                with patch.dict(sys.modules, fake):
                    frames, key = self.call_loader(tool, root, receipt, '30m')
                pd.testing.assert_frame_equal(frames['510300.SH'], frame)
                self.assertEqual((key, read.call_count, len(receipt)), ('trade_time', 1, 1))
                self.manifest(root, unselected, '30m')
                fake, read = self.parser(frame)
                with patch.dict(sys.modules, fake), self.assertRaisesRegex(ValueError, '无所选分区'):
                    self.call_loader(tool, root, [], '30m')
                self.assertEqual(read.call_count, 0)

    def test_main_binds_receipt_to_the_exact_manifest_snapshot_used_for_loading(self):
        """清单摘要取解析的原字节，分区加载使用同一快照而非结束时重读。"""
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame()
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'bars.parquet'; path.write_bytes(b'partition')
                self.manifest(root, dict(path=path.name, partition='all', sha256=tool.digest(path)))
                # 同一JSON值可有不同字节；收据须绑定实际解析的版本。
                manifest = root/'manifest.json'
                manifest.write_text(' \n'+manifest.read_text()+'\n')
                raw = manifest.read_bytes()
                snapshot, expected = tool.read_discovery_manifest(root)
                self.assertEqual(snapshot, json.loads(raw.decode('utf-8')))
                self.assertEqual(expected, tool.digest(manifest))
                output = root/'result.json'
                argv = [tool.__file__, '--dataset', str(root), '--output', str(output),
                        '--codes', '510300.SH', '--periods', '1d']
                fake, _ = self.parser(frame)
                with patch.dict(sys.modules, fake), patch.object(sys, 'argv', argv), \
                        patch.object(tool, 'import_chan', return_value=SimpleNamespace(__version__='test')), \
                        patch.object(tool, 'load_frames', wraps=tool.load_frames) as load, \
                        contextlib.redirect_stdout(io.StringIO()):
                    tool.main()
                self.assertEqual(load.call_args[1]['manifest'], snapshot)
                result = json.loads(output.read_text())
                self.assertEqual(result['manifest_sha256'], expected)
                self.assertEqual(len(result['input_files']), 1)
                self.assertEqual(manifest.read_bytes(), raw)

    def test_main_rejects_manifest_replacement_after_partition_read_without_success_receipt(self):
        """加载后移除清单分区，不得给旧读取结果登记新清单摘要。"""
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        frame = TestDiscoveryInputGuards.frame()
        for tool in TestDiscoveryInputGuards.scanners():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = root/'bars.parquet'; path.write_bytes(b'partition')
                self.manifest(root, dict(path=path.name, partition='all', sha256=tool.digest(path)))
                original = tool.load_frames
                def replace_manifest(*args, **kwargs):
                    result = original(*args, **kwargs)
                    (root/'manifest.json').write_text(json.dumps({'datasets': {'1d': {'files': []}}}))
                    return result
                output = root/'result.json'
                argv = [tool.__file__, '--dataset', str(root), '--output', str(output),
                        '--codes', '510300.SH', '--periods', '1d']
                fake, _ = self.parser(frame)
                with patch.dict(sys.modules, fake), patch.object(sys, 'argv', argv), \
                        patch.object(tool, 'import_chan', return_value=SimpleNamespace(__version__='test')), \
                        patch.object(tool, 'load_frames', side_effect=replace_manifest), \
                        contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'manifest'):
                    tool.main()
                self.assertFalse(output.exists())


if __name__=='__main__':
    unittest.main()
