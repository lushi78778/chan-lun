# -*- coding: utf-8 -*-
"""检查当前解释器实际导入的 chan，不注入源码、不安装或改写模块。

python tools/diagnose_chan.py [--expect 0.4.0] [--json]
可将本文件复制到聚宽运行；Python 3.6 用 pkg_resources 查询发行元数据。
"""

import argparse
import importlib
import json
import sys


REQUIRED_APIS = ("find_bis", "find_zs", "find_buy_points", "find_sell_points")


def distribution_info():
    """元数据与运行时导入分别检查；现代 Python 不依赖 pkg_resources。"""
    if sys.version_info >= (3, 8):
        from importlib import metadata
        try:
            dist = metadata.distribution("chan-lun-core")
        except metadata.PackageNotFoundError:
            return None
        return {"version": dist.version, "location": str(dist.locate_file(""))}
    try:
        import pkg_resources
    except ImportError:
        # python -S 或无 setuptools 环境没有 pkg_resources, 视为无发行元数据。
        return None
    try:
        dist = pkg_resources.get_distribution("chan-lun-core")
    except pkg_resources.DistributionNotFound:
        return None
    return {"version": dist.version, "location": dist.location}


def inspect_module(module, installed, expected=None):
    """判定导入对象与发行元数据，返回可写 JSON 的诊断。"""
    spec = getattr(module, "__spec__", None)
    report = {
        "python": sys.version.split()[0], "executable": sys.executable,
        "file": getattr(module, "__file__", None),
        "path": list(getattr(module, "__path__", [])),
        "origin": getattr(spec, "origin", None),
        "version": getattr(module, "__version__", None),
        "installed": installed, "expected": expected,
        "missing_apis": [name for name in REQUIRED_APIS
                         if not callable(getattr(module, name, None))],
        "issues": [],
    }
    issues = report["issues"]
    if report["file"] is None:
        issues.append("加载了命名空间或非文件模块；检查同名工作目录、当前解释器安装与内核缓存")
    if report["version"] is None or report["missing_apis"]:
        issues.append("实际加载的 chan 缺少核心库版本或公开算法入口")
    if installed is None:
        issues.append("当前解释器没有 chan-lun-core 安装元数据；源码模式请明确开发路径")
    elif report["version"] != installed["version"]:
        issues.append("运行时版本与发行元数据不一致；检查源码遮蔽或旧内核缓存")
    if expected is not None and report["version"] != expected:
        issues.append("运行时版本不等于指定版本 {}".format(expected))
    report["ok"] = not issues
    return report


def diagnose(expected=None):
    installed = distribution_info()
    try:
        module = importlib.import_module("chan")
    except ImportError as exc:
        return {"ok": False, "python": sys.version.split()[0],
                "executable": sys.executable, "installed": installed,
                "issues": ["导入失败: {}".format(exc)]}
    return inspect_module(module, installed, expected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", help="期望精确版本（不是最低版本）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = diagnose(args.expect)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key in ("python", "executable", "file", "path", "version", "installed", "missing_apis"):
            print("{}: {}".format(key, report.get(key)))
        print("status: {}".format("OK" if report["ok"] else "需要处理"))
        for issue in report["issues"]:
            print("- " + issue)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
