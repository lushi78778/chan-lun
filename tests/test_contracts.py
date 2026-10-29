# -*- coding: utf-8 -*-
"""包工程契约: 版本一致、公开入口可用、最低 Python 语法可解析。

与算法测试一同进入本地/CI discover。语法检查不能代替 Python 3.6
及聚宽旧依赖上的实际运行验证; 不把本地通过称为平台验证。
"""

import ast
import json
import os
import re
import sys
import unittest
from urllib.parse import unquote, urlsplit

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
sys.path.insert(0, _SRC)

import chan  # noqa: E402


def _python_examples(relative_path):
    """文档示例按其维护位置读取；路径也须在解包 sdist 中存在。"""
    with open(os.path.join(_ROOT, relative_path), encoding="utf-8") as f:
        return re.findall(r"```python\n(.*?)```", f.read(), re.S)


class TestPackageContracts(unittest.TestCase):
    """未来概念迭代也必须保持的工程契约。"""

    def test_version_matches_metadata(self):
        """元数据、运行时与发行README版本一致，拦截长描述的旧版安装指引。"""
        with open(os.path.join(_ROOT, "pyproject.toml"), encoding="utf-8") as f:
            metadata = f.read().split("[project]\n", 1)[1].split("\n[", 1)[0]
        match = re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(chan.__version__, match.group(1))
        with open(os.path.join(_ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        source_version = re.search(r'^\| 当前源码版本 \| `([^`]+)`', readme, re.M)
        self.assertIsNotNone(source_version)
        self.assertEqual(source_version.group(1), chan.__version__)
        install_versions = re.findall(r"python -m pip install 'chan-lun-core==([^']+)'", readme)
        self.assertEqual(install_versions, [chan.__version__])

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

    def test_engineering_constants_exported(self):
        """0.13.1: 工程阈值/原因码常量包级直出, 调用方不深入子模块。"""
        for name in ("REASON_BC", "REASON_STRONGER", "REASON_NO_EXTREME",
                     "REASON_WEAK_SIGN", "REASON_NOT_NESTED", "REASON_EMPTY",
                     "OSC_UPGRADE_N", "WEDGE_MIN_RUN", "UPGRADE_UNITS",
                     "MAX_LEVELS_DEFAULT", "MIN_UNITS_FOR_NEXT"):
            with self.subTest(name=name):
                self.assertIn(name, chan.__all__)
                self.assertTrue(hasattr(chan, name))

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
        """入门实际输出与展示一致，指南分步链仍与批量入口等价。"""
        with open(os.path.join(_ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        namespace = {}
        for code in _python_examples("README.md"):
            exec(code, namespace)
        displayed = json.loads(re.search(r"```json\n(.*?)```", readme, re.S).group(1))
        self.assertEqual(namespace["summary"], displayed)
        self.assertEqual(json.loads(namespace["json_text"]), namespace["snapshot"])
        self.assertEqual(namespace["current"].to_dict(), namespace["snapshot"])
        self.assertEqual(namespace["observed"].result.to_dict(), namespace["snapshot"])

        examples = _python_examples(os.path.join("docs", "usage.md"))
        pipeline = next(code for code in examples if "# 1. 行情 DataFrame" in code)
        exec(pipeline, namespace)
        self.assertTrue(namespace["bis"])
        self.assertIsInstance(namespace["buys"], list)
        self.assertIsInstance(namespace["sells"], list)
        self.assertEqual([bi.to_dict() for bi in namespace["result"].bis],
                         [bi.to_dict() for bi in namespace["bis"]])
        self.assertEqual(namespace["snapshot"]["as_of"], str(namespace["df"].index[-1]))

    def test_readme_auxiliary_examples_run(self):
        """新辅助API的文档示例必须可独立执行, 防确认时间与成员口径误用。"""
        examples = _python_examples(os.path.join("docs", "usage.md"))
        for marker in ["first = FormationEvent", "report = sector_strength",
                       "context = SecondPointContext", "available_bars =", "third_moves =", "fractal_box =", "ma_point_bars =", "completion_prices ="]:
            code = next(code for code in examples if marker in code)
            namespace = {}
            exec(code, namespace)
            if marker == "ma_point_bars =":
                warning = next(code for code in examples if "ma_warning = ma_point_state" in code)
                exec(warning, namespace)

    def test_readme_links_work_outside_repository(self):
        """README 同时进入 PyPI 长描述，链接不能依赖仓库目录作为基址。"""
        with open(os.path.join(_ROOT, "README.md"), encoding="utf-8") as f:
            targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", f.read())
        self.assertTrue(targets)
        prefix = "/lushi78778/chan-lun/blob/main/"
        for target in targets:
            with self.subTest(target=target):
                url = urlsplit(target)
                self.assertEqual(url.scheme, "https")
                self.assertTrue(url.netloc)
                if url.netloc == "github.com" and url.path.startswith(prefix):
                    relative = unquote(url.path[len(prefix):])
                    # 仓库资产索引只在线访问；包测试不读取 validation。
                    if relative == "validation/README.md":
                        continue
                    path = os.path.realpath(os.path.join(_ROOT, relative))
                    self.assertTrue(path.startswith(_ROOT + os.sep))
                    self.assertTrue(os.path.isfile(path), path)

    def test_migration_examples_run(self):
        """迁移指南中的指纹示例可独立执行并落盘，防文档示例漂移。"""
        import tempfile
        with open(os.path.join(_ROOT, "docs", "migration.md"), encoding="utf-8") as f:
            examples = re.findall(r"```python\n(.*?)```", f.read(), re.S)
        self.assertTrue(examples)
        cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                for code in examples:
                    exec(code, {})
                self.assertTrue(os.path.exists(
                    "fingerprint-{}.json".format(chan.__version__)))
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
