# -*- coding: utf-8 -*-
"""独立验收入口：没有外层仓库仍能运行，子进程同源，失败不降级。"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestCoreEntry(unittest.TestCase):
    def test_no_matches_fails_from_another_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "check_core.py"),
                 "--pattern", "__missing_tests__.py"], cwd=folder,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("未发现测试", proc.stderr)

    def test_missing_validation_suite_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tools").mkdir()
            (root / "src/chan").mkdir(parents=True)
            shutil.copyfile(str(ROOT / "tools/check_core.py"), str(root / "tools/check_core.py"))
            (root / "src/chan/__init__.py").write_text("__version__ = '0.0.0'\n")
            (root / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
            proc = subprocess.run([sys.executable, str(root / "tools/check_core.py"),
                                   "--scope", "validation"], cwd=folder,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("验收目录缺失", proc.stderr)

    def test_independent_checkout_and_subprocess_use_selected_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "core"
            (root / "tools").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "validation/tests").mkdir(parents=True)
            (root / "validation/tests/test_poison.py").write_text("raise AssertionError('包测试不应加载资产测试')\n", encoding="utf-8")
            (root / "src" / "chan").mkdir(parents=True)
            shutil.copyfile(str(ROOT / "tools" / "check_core.py"),
                            str(root / "tools" / "check_core.py"))
            (root / "src" / "chan" / "__init__.py").write_text(
                "__version__ = '0.0.0'\nMARKER = 'independent'\n")
            (root / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n')
            (root / "tests" / "test_source.py").write_text(
                "import subprocess, sys, unittest, chan\n"
                "class TestSource(unittest.TestCase):\n"
                "    def test_source(self):\n"
                "        self.assertEqual(chan.MARKER, 'independent')\n"
                "        output = subprocess.check_output([sys.executable, '-c', "
                "'import chan; print(chan.MARKER)'], universal_newlines=True)\n"
                "        self.assertEqual(output.strip(), 'independent')\n")
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            proc = subprocess.run(
                [sys.executable, str(root / "tools" / "check_core.py")], cwd=folder,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Ran 1 test", proc.stderr)


if __name__ == "__main__":
    unittest.main()
