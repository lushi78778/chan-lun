# -*- coding: utf-8 -*-
"""内部通用运算边界: 端点接触、三单元交集与缺失序列。

状态机各自的分解/递归/中阴测试仍是理论语义的验收依据。
本文件只锁定它们共用的数学边界, 不合并理论完成规则。
"""

import os
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from chan._intervals import _find_center, _overlap3, _overlap_center  # noqa: E402
from chan._series import _diff_series  # noqa: E402

Unit = namedtuple("Unit", "low high")


class TestInternalBoundaries(unittest.TestCase):
    """闭区间与公共序列运算必须共享同一边界。"""

    def test_touching_intervals(self):
        """课 20/35/38 单点接触属于重叠, 完全离开才不重叠。"""
        self.assertTrue(_overlap3([Unit(0, 1), Unit(1, 2), Unit(1, 3)], 0))
        self.assertTrue(_overlap_center(Unit(1, 2), (0, 1)))
        self.assertTrue(_overlap_center(Unit(-1, 0), (0, 1)))
        self.assertFalse(_overlap_center(Unit(2, 3), (0, 1)))

    def test_three_units_require_common_intersection(self):
        """相邻两两重叠不等于三单元共同交集, 不应误建中枢。"""
        units = [Unit(0, 2), Unit(1, 4), Unit(3, 5), Unit(3, 6)]
        self.assertFalse(_overlap3(units, 0))
        self.assertEqual(_find_center(units, 0), 1)
        self.assertIsNone(_find_center(units, 2))
        self.assertIsNone(_find_center([], 0))

    def test_missing_values_keep_positions(self):
        """均线暖机/NaN 不填充也不压缩, 差值索引与输入对齐。"""
        self.assertEqual(
            _diff_series([None, 3, float("nan"), object(), 7], [1, 2, 3, 4, 5]),
            [None, 1.0, None, None, 2.0])

    def test_different_lengths_use_common_prefix(self):
        """长度不等只消费公共前缀; 空输入不制造额外值。"""
        self.assertEqual(_diff_series([3, 8], [1]), [2.0])
        self.assertEqual(_diff_series([], [1]), [])


if __name__ == "__main__":
    unittest.main()
