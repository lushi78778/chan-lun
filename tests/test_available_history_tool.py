# -*- coding: utf-8 -*-
"""真实验收适配层的浮点归一化不能掩盖物质性坏数据。"""
import importlib.util
import os
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec=importlib.util.spec_from_file_location('_available_history_tool',os.path.join(ROOT,'tools','verify_core_available.py'))
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class TestAvailableHistoryTool(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([dict(ts_code='sample',trade_time=pd.Timestamp('2026-07-31 15:00:00'),
                                  open=3.5,high=3.5-4e-14,low=3.3,close=3.4,vol=1.0,adj_factor=1.0)])

    def test_small_noise_is_logged_and_input_preserved(self):
        source=self.frame();copy=source.copy(deep=True)
        normalized,receipt=tool.prepare_prices(source)
        assert_frame_equal(source,copy)
        self.assertEqual(receipt['original_envelope_violations'],1)
        self.assertLess(receipt['max_absolute_change'],1e-12)
        self.assertEqual(normalized.iloc[0]['high'],normalized.iloc[0]['open'])
        self.assertEqual(len(tool.bars_from(normalized,'30m')),1)

    def test_material_violation_is_still_rejected(self):
        source=self.frame();source.loc[0,'high']=3.49
        normalized,receipt=tool.prepare_prices(source)
        self.assertEqual(receipt['original_envelope_violations'],1)
        with self.assertRaises(ValueError):
            tool.bars_from(normalized,'30m')

    def test_ohlc_precision_policy_does_not_round_volume_or_factor(self):
        source=self.frame();source.loc[0,'adj_factor']=1.234567891234567
        source.loc[0,'vol']=123.4567891234567
        normalized,_=tool.prepare_prices(source)
        self.assertEqual(normalized.iloc[0]['vol'],source.iloc[0]['vol'])
        self.assertEqual(normalized.iloc[0]['adj_factor'],source.iloc[0]['adj_factor'])
