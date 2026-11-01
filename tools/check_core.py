# -*- coding: utf-8 -*-
"""核心库独立测试入口；默认包测试，资产验收单独选择。

不读取维护者外层项目。子进程使用相同源码，空测试集明确失败。
兼容 Python 3.6；旧依赖实跑与平台验收仍须分别记录。
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 完整回放保留在默认full；fast只延后这些已知重型模块，新模块默认进入fast。
DEFERRED = frozenset((
    'test_real_causal_formation', 'test_real_f1_originals', 'test_real_first_point',
    'test_real_foundation', 'test_real_second_point', 'test_real_strict_chain',
    'test_real_strict_completion', 'test_real_strict_divergence', 'test_real_strict_trend',
    'test_real_strict_trend_5m', 'test_real_strict_trend_completed', 'test_real_strict_trend_minute',
    'test_real_third_point', 'test_real_third_point_margin0', 'test_real_third_point_xd_margin0',
    'test_real_xd_f1', 'test_real_xd_originals',
    'test_real_causal_formation_assets', 'test_real_f1_assets', 'test_real_first_point_assets',
    'test_real_second_point_assets', 'test_real_strict_trend_5m_assets',
    'test_real_strict_trend_assets', 'test_real_strict_trend_completed_assets',
    'test_real_strict_trend_minute_assets', 'test_real_third_point_assets',
    'test_real_third_point_margin0_assets', 'test_real_third_point_xd_margin0_assets',
    'test_real_xd_f1_assets',
))
LEGACY_REQUIREMENTS = ('pip==21.3.1', 'numpy==1.14.6', 'pandas==0.23.4',
                       'python-dateutil==2.8.2', 'six==1.16.0', 'pytz==2025.2')


def change_plan(paths, full=False):
    """只分配执行范围，不将缺少diff等同文档修改；未知路径保守跑全部快速层。"""
    runtime = assets = artifacts = bool(full or paths is None)
    for path in paths or ():
        if path.endswith('.md') and path != 'README.md':
            continue
        if path == 'README.md':
            artifacts = True
        elif path.startswith('validation/'):
            assets = True
        else:
            runtime = assets = artifacts = True
    return dict(full=bool(full), runtime=runtime, assets=assets, artifacts=artifacts)


def previous_success():
    """取消旧运行后，仍须覆盖上一次成功main CI以来的全部变化。"""
    repository, token = os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_TOKEN')
    if not token or not re.match(r'^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$', repository):
        return None
    url = ('https://api.github.com/repos/'+repository+
           '/actions/workflows/test-and-release.yml/runs?'+
           urlencode(dict(branch='main', event='push', status='success', per_page=1)))
    request = Request(url, headers={'Authorization': 'Bearer '+token,
                                   'Accept': 'application/vnd.github+json', 'User-Agent': 'chan-core-ci'})
    try:
        with urlopen(request, timeout=15) as response:
            runs = json.load(response)['workflow_runs']
        return runs[0]['head_sha'] if runs else None
    except (OSError, ValueError, KeyError, TypeError):
        return None  # API不可用不缩小检查范围，不回退到可能漏掉已取消提交的before。


def github_plan():
    """标准库读取事件及完整push/PR差异；不把SHA或文件名作为shell代码执行。"""
    with open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8') as stream:
        event = json.load(stream)
    full = (os.environ.get('GITHUB_REF', '').startswith('refs/tags/v') or
            (os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and
             str(event.get('inputs', {}).get('full', True)).lower() == 'true'))
    base = event.get('pull_request', {}).get('base', {}).get('sha')
    if not full and os.environ.get('GITHUB_EVENT_NAME') == 'push':
        base = previous_success()
    head = os.environ.get('GITHUB_SHA', '')
    paths = None
    if (not full and isinstance(base, str) and base.strip('0') and
            re.match(r'^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$', base) and
            re.match(r'^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$', head)):
        command = ['git', 'diff', '--no-renames', '--name-only', '-z', base, head, '--']
        try:
            try:
                raw = subprocess.check_output(command, cwd=ROOT, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                subprocess.check_call(['git', 'fetch', '--no-tags', '--depth=1', 'origin', base], cwd=ROOT)
                raw = subprocess.check_output(command, cwd=ROOT)
            paths = [p for p in raw.decode('utf-8').split('\0') if p]
        except (OSError, subprocess.CalledProcessError, UnicodeError):
            paths = None
    plan = change_plan(paths, full)
    print(json.dumps(dict(plan, base=base, changed=paths), ensure_ascii=False), flush=True)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        for key, value in sorted(plan.items()):
            stream.write('{}={}\n'.format(key, str(value).lower()))
    return 0


def verify_checks(checks, release=False):
    """稳定CI门禁：需要执行的检查必须成功，不能用skipped绕过发版完整验收。"""
    if checks['build']['result'] != 'success':
        raise ValueError('build/source checks did not succeed')
    outputs = checks['build']['outputs']
    full, runtime = outputs['full'] == 'true', outputs['runtime'] == 'true'
    if release and not full:
        raise ValueError('release requires full acceptance')
    for name, required in (('test', full or runtime), ('legacy', full or runtime), ('validation', full)):
        allowed = ('success',) if required else ('success', 'skipped')
        if checks[name]['result'] not in allowed:
            raise ValueError('{} did not succeed: {}'.format(name, checks[name]['result']))


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            for test in cases(item):
                yield test
        else:
            yield item


def select_suite(suite, profile):
    selected, deferred = unittest.TestSuite(), []
    for test in cases(suite):
        if profile == 'fast' and test.__class__.__module__.split('.')[-1] in DEFERRED:
            deferred.append(test.id())
        else:
            selected.addTest(test)
    return selected, deferred


class TimedResult(unittest.TextTestResult):
    """逐用例计时用于分层复核；不改变失败、跳过或默认full语义。"""
    def startTest(self, test):
        self.started = time.perf_counter()
        if not hasattr(self, 'timings'):
            self.timings = []
        super(TimedResult, self).startTest(test)

    def stopTest(self, test):
        self.timings.append(dict(id=test.id(), seconds=round(time.perf_counter()-self.started, 6)))
        super(TimedResult, self).stopTest(test)


def docker_matrix(version, scope):
    """资产专验只选现代环境；all矩阵中的旧环境仅承担包层。"""
    versions = ('3.10', '3.13', '3.6') if version == 'all' else (version,)
    matrix = tuple((v, 'package' if v == '3.6' else scope) for v in versions
                   if v != '3.6' or scope != 'validation')
    if not matrix:
        raise ValueError('3.6仅验包测试，资产专验选择现代环境')
    return matrix


def docker_check(args):
    """本地隔离源码验收；Dockerfile临时生成，宿主源码只读，报告独立留存。"""
    output = os.path.abspath(args.docker_output)
    os.makedirs(output)  # 拒绝覆盖、续写或复用旧收据。
    for version, scope in docker_matrix(args.docker, args.scope):
        folder = os.path.join(output, version)
        os.mkdir(folder)
        with open(os.path.join(ROOT, 'requirements-dev.txt'), encoding='utf-8') as stream:
            requirements = ''.join(line for line in stream if not line.strip().startswith('-e '))
        legacy = version == '3.6'
        if legacy:
            requirements = '\n'.join(LEGACY_REQUIREMENTS)+'\n'
        image = 'chan-core-check:py{}-{}'.format(
            version.replace('.', ''), hashlib.sha256(requirements.encode('utf-8')).hexdigest()[:12])
        platform = ['--platform', 'linux/amd64'] if legacy else []
        found = subprocess.call(['docker', 'image', 'inspect', image],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        if not found:
            base = 'python:3.6.15-buster' if legacy else 'python:{}-slim'.format(version)
            dockerfile = ('FROM '+base+'\nCOPY requirements.txt /tmp/requirements.txt\n'
                          'RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt\n')
            with tempfile.TemporaryDirectory(prefix='chan-docker-') as context:
                with open(os.path.join(context, 'requirements.txt'), 'w', encoding='utf-8') as stream:
                    stream.write(requirements)
                subprocess.run(['docker', 'build']+platform+['-t', image, '-f', '-', context],
                               input=dockerfile, universal_newlines=True, check=True)
        image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                                           universal_newlines=True).strip()
        print('Docker {} / {} / {}; image {}'.format(version, scope, args.profile, image_id), flush=True)
        # 只传已解析的参数列表，不拼接宿主路径、模式或测试名为shell代码。
        script = '''import hashlib, json, os, platform, shutil, subprocess, sys
import numpy, pandas
shutil.copytree('/checkout', '/tmp/chan-core', ignore=shutil.ignore_patterns(
    '.git', '.venv', '.uvcache', 'build', 'dist', '__pycache__', '*.egg-info', '.coverage*', '.ruff_cache'))
os.chdir('/tmp/chan-core')
scope, profile, pattern, version = sys.argv[1:]
environment = dict(python=sys.version, numpy=numpy.__version__, pandas=pandas.__version__, machine=platform.machine())
environment['source_sha256'] = {}
for base in ('src', 'tools', 'tests', 'validation'):
    for directory, _, files in os.walk(base):
        for name in sorted(files):
            if name.endswith(('.py', '.json')):
                path = os.path.join(directory, name)
                with open(path, 'rb') as stream: environment['source_sha256'][path] = hashlib.sha256(stream.read()).hexdigest()
environment['dependencies'] = json.loads(subprocess.check_output([sys.executable, '-m', 'pip', 'list', '--format=json'], universal_newlines=True))
with open('/results/environment.json', 'x') as stream: json.dump(environment, stream, indent=2)
for layer in (['package', 'validation'] if scope == 'all' else [scope]):
    command = [sys.executable, 'tools/check_core.py', '--scope', layer, '--profile', profile,
               '--pattern', pattern, '--timings', '/results/'+layer+'-timings.json', '-v']
    coverage = version == '3.10' and layer == 'package' and profile == 'full' and pattern == 'test_*.py'
    if coverage: command[1:1] = ['-m', 'coverage', 'run', '--data-file=/results/coverage.data']
    with open('/results/'+layer+'.log', 'x') as stream:
        result = subprocess.call(command, stdout=stream, stderr=subprocess.STDOUT)
    print(layer+' exit '+str(result), flush=True)
    if result: sys.exit(result)
    if coverage:
        subprocess.check_call([sys.executable, '-m', 'coverage', 'report', '--data-file=/results/coverage.data'])
        subprocess.check_call([sys.executable, '-m', 'coverage', 'json', '--data-file=/results/coverage.data', '-o', '/results/coverage.json'])
'''
        user = ['--user', '{}:{}'.format(os.getuid(), os.getgid())] if hasattr(os, 'getuid') else []
        command = (['docker', 'run', '--rm']+platform+user+
                   ['--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,size=1g',
                    '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'TZ=Asia/Shanghai',
                    '-v', ROOT+':/checkout:ro', '-v', folder+':/results:rw',
                    image, 'python', '-u', '-c', script, scope, args.profile, args.pattern, version])
        with open(os.path.join(folder, 'invocation.json'), 'x', encoding='utf-8') as stream:
            json.dump(dict(image=image, image_id=image_id, scope=scope, profile=args.profile,
                           pattern=args.pattern, legacy_package_only=legacy), stream, indent=2)
        result = subprocess.call(command)
        if result:
            return result
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("package", "validation", "all"), default="package")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument('--profile', choices=('full', 'fast'), default='full')
    parser.add_argument('--timings', help='新JSON收据路径，记录逐用例耗时及显式延后项')
    parser.add_argument('--ci-plan', action='store_true', help='从GitHub事件生成CI执行范围（不运行测试）')
    parser.add_argument('--ci-gate', action='store_true', help='核对GitHub所需检查均已成功')
    parser.add_argument('--docker', choices=('3.6', '3.10', '3.13', 'all'), help='本地Docker源码验收')
    parser.add_argument('--docker-output', help='全新Docker结果目录（不覆盖已有结果）')
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if sum(bool(v) for v in (args.ci_plan, args.ci_gate, args.docker)) > 1:
        parser.error('CI分流、门禁和Docker模式不得混用')
    if args.ci_plan:
        return github_plan()
    if args.ci_gate:
        verify_checks(json.loads(os.environ['CHECKS']), os.environ.get('GITHUB_REF', '').startswith('refs/tags/v'))
        print('Applicable CI checks succeeded', flush=True)
        return 0
    if args.docker:
        if not args.docker_output or args.timings:
            parser.error('Docker须指定全新--docker-output；不混用--timings；3.6仅验包测试')
        try:
            matrix = docker_matrix(args.docker, args.scope)
        except ValueError as error:
            parser.error(str(error))
        if any(scope in ('all', 'validation') for _, scope in matrix) and not os.path.isdir(os.path.join(ROOT, 'validation/tests')):
            parser.error('Docker资产验收须有完整仓库validation/tests，不在缺失资产后先跑长包测试')
        return docker_check(args)
    if args.docker_output:
        parser.error('--docker-output须与--docker一起使用')
    if args.timings and os.path.lexists(os.path.abspath(args.timings)):
        parser.error('拒绝覆盖已有计时收据')
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
    suite, deferred = select_suite(suite, args.profile)
    if not suite.countTestCases():
        parser.error('快速配置未选中测试；完整回放使用--profile full')
    print("core {} / {}; selected {}; deferred {}; source: {} ({})".format(
        args.scope, args.profile, suite.countTestCases(), len(deferred), chan.__file__, chan.__version__), flush=True)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1, resultclass=TimedResult).run(suite)
    if args.timings:
        path = os.path.abspath(args.timings)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'x', encoding='utf-8') as stream:
            json.dump(dict(profile=args.profile, scope=args.scope, pattern=args.pattern,
                           tests_run=result.testsRun, deferred=deferred, ok=result.wasSuccessful(),
                           failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                           tests=result.timings), stream, ensure_ascii=False, indent=2)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
