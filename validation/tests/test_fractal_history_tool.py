# -*- coding: utf-8 -*-
"""锁定构造价格坐标的验证回归, 防重复转换改写边沿。"""
import importlib.util
import os
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    '_fractal_history_tool', os.path.join(ROOT, 'tools', 'verify_fractal_history.py'))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class TestFractalHistoryTool(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([
            dict(trade_date=pd.Timestamp('2026-07-01'), open=10.3135,
                 high=10.8, low=10., close=10.5, vol=1., adj_factor=1.217),
            dict(trade_date=pd.Timestamp('2026-07-02'), open=10.6,
                 high=11., low=10., close=10.8, vol=1., adj_factor=0.823)])

    def test_same_history_bytes_do_not_depend_on_later_observation_anchor(self):
        """先前行按同一因子路径求值, 未来因子不能微调已锁定价格。"""
        frame = self.frame()
        anchor = 1.184
        early = tool.locked_bars(frame.iloc[:1], anchor)
        later = tool.locked_bars(frame, anchor)
        self.assertEqual(early, later[:1])
        self.assertEqual(early[0]['open'], 10.3135 * (1.217 / anchor))

    def test_price_basis_adaptation_preserves_input_and_nonprice_fields(self):
        """源文件值、量额与日期不变, 不靠精度阈值掩盖坏价格。"""
        frame = self.frame(); original = frame.copy(deep=True)
        result = tool.locked_bars(frame, 1.184)
        assert_frame_equal(frame, original)
        self.assertEqual(result[0]['volume'], frame.iloc[0]['vol'])
        self.assertEqual(result[0]['dt'], frame.iloc[0]['trade_date'])
        frame.loc[0, 'high'] = 9.
        with self.assertRaises(ValueError):
            tool.locked_bars(frame, 1.184)

    def test_shared_explicit_anchor_rejects_zero_and_nonfinite(self):
        """日线/分钟线复用价格数学, 非法基准不能产生可用行情。"""
        for anchor in (0,-1,float('nan'),float('inf')):
            with self.subTest(anchor=anchor),self.assertRaises(ValueError):
                tool.bars_from(self.frame(),'1d',anchor=anchor)

    def test_default_anchor_keeps_previous_prefix_contract(self):
        """旧默认仍锚前缀末因子, 显式同锚与旧调用逐字节一致。"""
        frame=self.frame()
        self.assertEqual(tool.bars_from(frame,'1d'),
                         tool.bars_from(frame,'1d',anchor=float(frame['adj_factor'].iloc[-1])))
