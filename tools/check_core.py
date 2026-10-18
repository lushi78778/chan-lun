# -*- coding: utf-8 -*-
"""核心库独立测试入口；默认包测试，资产验收单独选择。

不读取维护者外层项目。子进程使用相同源码，空测试集明确失败。
兼容 Python 3.6；旧依赖实跑与平台验收仍须分别记录。
"""

import argparse
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("package", "validation", "all"), default="package")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    source = os.path.join(ROOT, "src")
    init = os.path.join(source, "chan", "__init__.py")
    if not os.path.isfile(init):
        parser.error("核心库源码缺失: {}".format(init))
    sys.path.insert(0, source)
    prior = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = source + (os.pathsep + prior if prior else "")
    import chan
    if os.path.realpath(chan.__file__) != os.path.realpath(init):
        parser.error("实际导入不是本仓库源码: {}".format(chan.__file__))
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        metadata = f.read()
    match = re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M)
    if not match or chan.__version__ != match.group(1):
        parser.error("核心库源码与发布元数据版本不一致")
    directories = []
    if args.scope in ("package", "all"):
        directories.append(os.path.join(ROOT, "tests"))
    if args.scope in ("validation", "all"):
        directories.append(os.path.join(ROOT, "validation", "tests"))
    suite = unittest.TestSuite()
    for test_dir in directories:
        if not os.path.isdir(test_dir):
            parser.error("验收目录缺失（validation 不随发行包分发）: {}".format(test_dir))
        part = unittest.TestLoader().discover(test_dir, pattern=args.pattern)
        if not part.countTestCases():
            parser.error("未发现测试: {} / {}".format(test_dir, args.pattern))
        suite.addTests(part)
    print("core {}; source: {} ({})".format(args.scope, chan.__file__, chan.__version__), flush=True)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
