# -*- coding: utf-8 -*-
"""独立验收入口：没有外层仓库仍能运行，子进程同源，失败不降级。"""

import os
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def entry():
    spec = importlib.util.spec_from_file_location('core_entry_contract', str(ROOT / 'tools/check_core.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCoreEntry(unittest.TestCase):
    def test_ci_change_ranges_are_scoped_but_unknown_paths_are_conservative(self):
        tool = entry()
        for paths, flags in ((['docs/usage.md'], (False, False, False)),
                             (['validation/README.md'], (False, False, False)),
                             (['README.md'], (False, False, True)),
                             (['validation/tools/index_core_samples.py'], (False, True, False)),
                             (['tests/fixtures/real_xd_f1.json'], (True, True, True)),
                             (['src/chan/xd.py', 'docs/api.md'], (True, True, True)),
                             (['.github/workflows/test-and-release.yml'], (True, True, True)),
                             (['unknown.file'], (True, True, True)), (None, (True, True, True))):
            result = tool.change_plan(paths)
            self.assertFalse(result['full'])
            self.assertEqual(tuple(result[k] for k in ('runtime', 'assets', 'artifacts')), flags, paths)
        self.assertTrue(all(tool.change_plan(['docs/usage.md'], full=True).values()))

    def test_github_plan_covers_push_pr_fallback_and_tag_without_shell_evaluation(self):
        tool = entry()
        with tempfile.TemporaryDirectory() as folder:
            event, output = Path(folder)/'event.json', Path(folder)/'output.txt'
            env = dict(GITHUB_EVENT_PATH=str(event), GITHUB_OUTPUT=str(output),
                       GITHUB_SHA='b'*40, GITHUB_REF='refs/heads/main', GITHUB_EVENT_NAME='push')
            for document in ({'before': 'a'*40}, {'pull_request': {'base': {'sha': 'a'*40}}}):
                event.write_text(json.dumps(document))
                selected_env = dict(env, GITHUB_EVENT_NAME='pull_request' if 'pull_request' in document else 'push')
                with mock.patch.dict(os.environ, selected_env), mock.patch.object(tool, 'previous_success', return_value='a'*40), mock.patch.object(tool.subprocess, 'check_output', return_value=b'src/chan/xd.py\0') as command:
                    self.assertEqual(tool.github_plan(), 0)
                    args = command.call_args[0][0]
                    self.assertEqual(args, ['git', 'diff', '--no-renames', '--name-only', '-z', 'a'*40, 'b'*40, '--'])
            event.write_text(json.dumps({'before': 'a'*40}))
            with mock.patch.dict(os.environ, env), mock.patch.object(tool, 'previous_success', return_value='a'*40), mock.patch.object(tool.subprocess, 'check_output', side_effect=[subprocess.CalledProcessError(128, 'git'), b'docs/usage.md\0']), mock.patch.object(tool.subprocess, 'check_call') as fetch:
                tool.github_plan()
                self.assertEqual(fetch.call_args[0][0], ['git', 'fetch', '--no-tags', '--depth=1', 'origin', 'a'*40])
            for before in ('0'*40, '--exec=$(unexpected)', None):
                event.write_text(json.dumps({'before': before}))
                with mock.patch.dict(os.environ, env), mock.patch.object(tool, 'previous_success', return_value=before), mock.patch.object(tool.subprocess, 'check_output') as command:
                    tool.github_plan()
                    command.assert_not_called()
                self.assertIn('runtime=true', output.read_text())
            event.write_text(json.dumps({'before': 'a'*40}))
            for update, expected in (({'GITHUB_REF': 'refs/tags/v1.2.0'}, True),
                                     ({'GITHUB_EVENT_NAME': 'workflow_dispatch'}, True)):
                output.write_text('')
                with mock.patch.dict(os.environ, dict(env, **update)), mock.patch.object(tool.subprocess, 'check_output') as command:
                    tool.github_plan()
                    command.assert_not_called()
                self.assertEqual('full=true' in output.read_text(), expected)
            # 本次push即使只改文档，也必须从更早的成功基准覆盖被取消的代码提交。
            with mock.patch.dict(os.environ, env), mock.patch.object(tool, 'previous_success', return_value='c'*40), mock.patch.object(tool.subprocess, 'check_output', return_value=b'src/chan/xd.py\0') as command:
                tool.github_plan()
                self.assertEqual(command.call_args[0][0][-3:-1], ['c'*40, 'b'*40])
            output.write_text('')
            with mock.patch.dict(os.environ, env), mock.patch.object(tool, 'previous_success', return_value=None), mock.patch.object(tool.subprocess, 'check_output') as command:
                tool.github_plan()
                command.assert_not_called()  # 不能回退到本次push的有效before。
            self.assertIn('runtime=true', output.read_text())

    def test_previous_success_is_readonly_and_api_failure_cannot_skip_code_checks(self):
        tool = entry()
        with mock.patch.dict(os.environ, dict(GITHUB_TOKEN='test-token', GITHUB_REPOSITORY='owner/repo')):
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = b'{"workflow_runs":[{"head_sha":"abc"}]}'
            with mock.patch.object(tool, 'urlopen', return_value=response) as request:
                self.assertEqual(tool.previous_success(), 'abc')
                url = request.call_args[0][0].full_url
                self.assertIn('event=push', url)
                self.assertIn('status=success', url)
                self.assertIn('branch=main', url)
            with mock.patch.object(tool, 'urlopen', side_effect=OSError('offline')):
                self.assertIsNone(tool.previous_success())
                self.assertTrue(tool.change_plan(None)['runtime'])

    def test_ci_gate_rejects_failed_cancelled_or_skipped_required_checks(self):
        tool = entry()
        needs = dict(build=dict(result='success', outputs=dict(full='true', runtime='true')),
                     test=dict(result='success'), validation=dict(result='success'), legacy=dict(result='success'))
        tool.verify_checks(needs, release=True)
        for name in needs:
            for state in ('failure', 'cancelled', 'skipped'):
                changed = copy.deepcopy(needs)
                changed[name]['result'] = state
                with self.assertRaises(ValueError):
                    tool.verify_checks(changed, release=True)
        needs['build']['outputs'] = dict(full='false', runtime='false')
        for name in ('test', 'validation', 'legacy'):
            needs[name]['result'] = 'skipped'
        tool.verify_checks(needs)
        with self.assertRaisesRegex(ValueError, 'full acceptance'):
            tool.verify_checks(needs, release=True)
        needs['build']['outputs']['runtime'] = 'true'
        with self.assertRaises(ValueError):
            tool.verify_checks(needs)

    def test_profiles_preserve_default_full_failure_and_expose_deferred_timings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'tools').mkdir()
            (root/'src/chan').mkdir(parents=True)
            (root/'tests').mkdir()
            shutil.copyfile(str(ROOT/'tools/check_core.py'), str(root/'tools/check_core.py'))
            (root/'src/chan/__init__.py').write_text("__version__ = '0.0.0'\n")
            (root/'pyproject.toml').write_text('[project]\nversion = "0.0.0"\n')
            common = 'import unittest\nclass TestCase(unittest.TestCase):\n    def test_case(self):\n'
            (root/'tests/test_source.py').write_text(common+'        self.assertTrue(True)\n')
            (root/'tests/test_real_new_module.py').write_text(common+'        self.assertTrue(True)\n')
            (root/'tests/test_real_xd_f1.py').write_text(common+"        self.fail('full replay sentinel')\n")
            base = [sys.executable, str(root/'tools/check_core.py')]
            fast_path, full_path = root/'fast.json', root/'full.json'
            fast = subprocess.run(base+['--profile', 'fast', '--timings', str(fast_path)], cwd=folder,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(fast.returncode, 0, fast.stdout+fast.stderr)
            data = json.loads(fast_path.read_text())
            self.assertEqual((data['tests_run'], len(data['deferred']), data['ok']), (2, 1, True))
            self.assertEqual({r['id'] for r in data['tests']},
                             {'test_source.TestCase.test_case', 'test_real_new_module.TestCase.test_case'})
            frozen = fast_path.read_bytes()
            repeated = subprocess.run(base+['--timings', str(fast_path)], cwd=folder,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(fast_path.read_bytes(), frozen)
            full = subprocess.run(base+['--timings', str(full_path)], cwd=folder,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(full.returncode, 0)
            data = json.loads(full_path.read_text())
            self.assertEqual((data['profile'], data['tests_run'], data['failures'], data['deferred']), ('full', 3, 1, []))
            empty = subprocess.run(base+['--profile', 'fast', '--pattern', 'test_real_xd_f1.py'], cwd=folder,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(empty.returncode, 0)
            self.assertIn('未选中', empty.stderr)

    def test_docker_rejects_ambiguous_scope_or_existing_receipts_before_starting(self):
        tool = entry()
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(tool.subprocess, 'call') as docker:
            args = type('Args', (), dict(docker_output=folder, docker='3.6', scope='package', profile='full', pattern='test_*.py'))()
            with self.assertRaises(OSError):
                tool.docker_check(args)
            docker.assert_not_called()
        for flags in (['--docker', '3.6', '--scope', 'validation'], ['--docker-output', 'unused'],
                      ['--ci-plan', '--docker', '3.10']):
            with self.assertRaises(SystemExit):
                tool.main(flags)

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
