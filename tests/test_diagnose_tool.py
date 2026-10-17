# -*- coding: utf-8 -*-
"""导入诊断工具的失败分支：禁止错误模块/零测试被报为通过。"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "_chan_diagnose_tool", os.path.join(ROOT, "tools", "diagnose_chan.py"))
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class TestImportDiagnosis(unittest.TestCase):
    def module(self, version="0.4.0"):
        module = types.ModuleType("chan")
        module.__file__ = "/example/site-packages/chan/__init__.py"
        module.__version__ = version
        for name in doctor.REQUIRED_APIS:
            setattr(module, name, lambda: None)
        return module

    def test_namespace_and_missing_distribution_are_explained(self):
        module = types.ModuleType("chan")
        module.__path__ = ["/home/jquser/chan"]
        report = doctor.inspect_module(module, None)
        self.assertFalse(report["ok"])
        self.assertIsNone(report["file"])
        self.assertIn("命名空间", report["issues"][0])
        self.assertEqual(report["missing_apis"], list(doctor.REQUIRED_APIS))

    def test_matching_installed_import_passes(self):
        report = doctor.inspect_module(self.module(), {"version": "0.4.0"}, "0.4.0")
        self.assertTrue(report["ok"])

    def test_stale_runtime_fails_even_when_distribution_exists(self):
        report = doctor.inspect_module(self.module(), {"version": "0.5.0"})
        self.assertFalse(report["ok"])
        self.assertIn("不一致", report["issues"][0])

    def test_expected_version_is_exact(self):
        report = doctor.inspect_module(self.module(), {"version": "0.4.0"}, "0.5.0")
        self.assertFalse(report["ok"])

    def test_non_callable_api_is_rejected(self):
        module = self.module()
        module.find_bis = "wrong binding"
        report = doctor.inspect_module(module, {"version": "0.4.0"})
        self.assertFalse(report["ok"])
        self.assertIn("find_bis", report["missing_apis"])

    def test_cli_namespace_import_matches_notebook_failure(self):
        """新进程复现同名目录，无已安装 site-packages 掩盖命名空间错误。"""
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "chan"))
            env = os.environ.copy()
            env["PYTHONPATH"] = root
            proc = subprocess.run(
                [sys.executable, "-S", os.path.join(ROOT, "tools", "diagnose_chan.py"), "--json"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8"))
            import json
            report = json.loads(proc.stdout.decode("utf-8"))
            self.assertIsNone(report["file"])
            self.assertEqual(report["path"], [os.path.join(root, "chan")])
            self.assertIsNone(report["installed"])

    def test_cli_version_requirement_returns_failure(self):
        """诊断的退出码可用于 CI，不能打印失败后仍返回成功。"""
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "diagnose_chan.py"),
             "--expect", "0.0.0", "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
