# -*- coding: utf-8 -*-
"""包工程契约: 版本一致、公开入口可用、最低 Python 语法可解析。

与算法测试一同进入本地/CI discover。语法检查不能代替 Python 3.6
及聚宽旧依赖上的实际运行验证; 不把本地通过称为平台验证。
"""

import ast
import math
import os
import re
import sys
import unittest
from datetime import datetime, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
sys.path.insert(0, _SRC)

import chan  # noqa: E402


class TestPackageContracts(unittest.TestCase):
    """未来概念迭代也必须保持的工程契约。"""

    def test_version_matches_metadata(self):
        """发布元数据与运行时版本一致, 避免双处版本号漂移。"""
        with open(os.path.join(_ROOT, "pyproject.toml"), encoding="utf-8") as f:
            metadata = f.read().split("[project]\n", 1)[1].split("\n[", 1)[0]
        match = re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(chan.__version__, match.group(1))

    def test_public_exports_resolve_once(self):
        """全部公开导出唯一且可取到; 检查清单随新增入口自动增长。"""
        self.assertTrue(chan.__all__)
        self.assertEqual(len(chan.__all__), len(set(chan.__all__)))
        for name in chan.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(chan, name))
        for name, value in vars(chan).items():
            # 顶层绑定的本包函数/类应可通过 import * 获取, 防漏登记。
            origin = getattr(value, "__module__", "")
            if not name.startswith("_") and origin.startswith("chan."):
                self.assertIn(name, chan.__all__)

    def test_python36_source_grammar(self):
        """包内所有源码按 3.6 语法解析, 拦截 walrus 等较新语法。"""
        package_dir = os.path.join(_SRC, "chan")
        for name in sorted(os.listdir(package_dir)):
            if not name.endswith(".py"):
                continue
            with self.subTest(module=name):
                with open(os.path.join(package_dir, name), encoding="utf-8") as f:
                    source = f.read()
                if sys.version_info >= (3, 8):
                    ast.parse(source, filename=name, feature_version=(3, 6))
                else:
                    # 3.6/3.7 的 ast 尚无 feature_version 参数。
                    ast.parse(source, filename=name)

    def test_readme_pipeline_runs(self):
        """公开快速示例以合成行情运行, 拦截返回值误用与级别接线错误。"""
        import pandas as pd

        with open(os.path.join(_ROOT, "README.md"), encoding="utf-8") as f:
            examples = re.findall(r"```python\n(.*?)```", f.read(), re.S)
        pipeline = next(code for code in examples if "# 1. 行情 DataFrame" in code)
        closes = [20.0 + 3.0 * math.sin(i / 6.0) + i / 80.0 for i in range(160)]
        frame = pd.DataFrame({
            "open": closes, "close": closes,
            "high": [price + 0.3 for price in closes],
            "low": [price - 0.3 for price in closes],
            "volume": [1000.0] * len(closes),
        }, index=[datetime(2025, 1, 1) + timedelta(days=i) for i in range(160)])
        namespace = {"df": frame}
        exec(pipeline, namespace)
        self.assertTrue(namespace["bis"])
        self.assertIsInstance(namespace["buys"], list)
        self.assertIsInstance(namespace["sells"], list)
        batch_example = next(code for code in examples if "snapshot = result.to_dict()" in code)
        exec(batch_example, namespace)
        self.assertEqual([bi.to_dict() for bi in namespace["result"].bis],
                         [bi.to_dict() for bi in namespace["bis"]])
        self.assertEqual(namespace["snapshot"]["as_of"], str(frame.index[-1]))

    def test_readme_auxiliary_examples_run(self):
        """新辅助API的文档示例必须可独立执行, 防确认时间与成员口径误用。"""
        with open(os.path.join(_ROOT, "README.md"), encoding="utf-8") as f:
            examples = re.findall(r"```python\n(.*?)```", f.read(), re.S)
        for marker in ["first = FormationEvent", "report = sector_strength",
                       "context = SecondPointContext", "available_bars ="]:
            code = next(code for code in examples if marker in code)
            exec(code, {})


if __name__ == "__main__":
    unittest.main()
