# -*- coding: utf-8 -*-
"""R2样本提取的日期和缺测契约; 独立于核心识别器。"""
import importlib.util
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


if __name__=='__main__':
    unittest.main()
