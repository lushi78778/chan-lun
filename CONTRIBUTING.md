# 核心库开发与验收

本仓库独立维护 `chan-lun-core`。定位为缠论结构识别与理论辅助计算库，
输入输出与能力边界见 [README](README.md) 和 [API](docs/api.md)。
目录职责与文档分工见 [docs/README.md](docs/README.md)。

## 环境与入口

现代开发和构建使用 Python 3.10+，在本仓库根安装：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python tools/check_core.py
```

以下命令中的 `python` 指准备好的解释器。运行时兼容目标仍为 Python 3.6、
numpy 1.14、pandas 0.23；现代开发依赖不用于升级聚宽旧环境。
构建后端的 Python 要求与 wheel 的最低运行版本分别验证。

`requirements-dev.txt` 固定现代开发与 CI 的直接依赖，按官方 Python 要求选择
相应 numpy/pandas 基线；CI 日志保留解析后的完整环境。构建使用已准备环境中的
固定后端，`python -m build --no-isolation` 生成一次候选。传递依赖并非哈希锁定，
需要重放时同时保留当次环境清单；运行时依赖范围仍由 pyproject 单独维护。

可选的 Parquet 样本工具另行安装 `python -m pip install -r validation/requirements.txt`。
原页图册还需要 `pdftoppm` 及经 `--pdf` 显式传入的本地 PDF；这些材料和
系统工具不属于包运行依赖。

## 计划与理论依据

- [理论实现计划](docs/缠论理论逐一实现计划.md) §6 是唯一实现进度表。
  协作规则见 [AGENTS.md](AGENTS.md)。
- 108 课 PDF、逐课文本和私有笔记由维护者提供，不随仓库分发；缺原文
  不能完成理论核验。文本存疑时复核原页。
- 源码、包测试、工程工具均在本仓库维护；独立开发和 CI 不读取外层项目。
  仓库级收据、原始输入、资产测试及其工具在 `validation/` 维护，整体排除
  wheel/sdist。证据入口见 [validation/README.md](validation/README.md)。

## 分层与抽象边界

- [架构](docs/architecture.md) 定义数据对象、计算函数和组合入口。
  `bars.py` 负责适配与行情校验；各概念模块拥有自己的完成、延伸和确认语义。
- `analysis.py` 组合既有公开算法，明确区分笔级与线段级字段；原始行情校验
  在输入边界执行。`replay.py`、`availability.py` 管理观察前缀与可用时间。
- `__init__.py` 只组装公开入口与版本号；私有模块不加入 `__all__`。
  共用闭区间交集放 `_intervals.py`，数值序列适配放 `_series.py`。
- 输入复用现有鸭子类型属性，不为每个概念引入行情源或策略依赖。
  跨级别和跨成员接口由调用方显式提供对齐的输入。
- 新行为接入研究脚本与策略需要调用方单独验收，不自动修改冻结脚本。

## 每个概念的完成条件

1. 核对课程原文，明确输入输出、边界、阈值和理论差异，写入 docstring。
2. 在 `src/chan/` 实现，在 `tests/` 覆盖定义分支与退化输入。时间状态功能
   还须验证确认时间、已完成项前缀一致性和未完成尾部修订。
3. 公开入口加入顶层导出；README 示例保持输入级别和候选/条件判定口径。
4. 完成相应验收，按 API 的 1.x 规则登记版本与公开行为差异，同步双处版本，
   再更新计划 §6。无完整测试、导出和概念登记的草稿不能登记为已实现。
5. 阶段末核对待发布文件，排除未验收草稿；分别核验 tag、push、CI、
   GitHub Release 和 PyPI，不互相替代。

工程维护与概念实现分开登记；兼容的打包和文档修正可纳入修订版本。
按实际影响迭代 1.x，不为每笔内部维护提交机械升版，不覆盖已发布产物。
当前 1.x 的兼容与算法修正规则以 [API](docs/api.md#1x-版本规则) 为准。

发布前在 CHANGELOG 的本版条目写明变更、升级影响与仍成立的证据边界；
工作流直接提取该条目生成 Release 正文，缺条目时失败，不新增逐版本
说明文件。发布结果核验后再登记，不预写为成功。

## 两层验收

```bash
python tools/check_core.py                              # 自包含包测试
python tools/check_core.py --pattern test_contracts.py   # 定向包测试
python tools/check_core.py --scope validation            # 完整仓库资产验收
python tools/check_core.py --scope all                   # 两层验收
python tools/check_core.py --profile fast                # 日常快速包测试，明确列出延后数量
python tools/check_core.py --scope validation --profile fast
python tools/check_core.py --timings /绝对路径/新计时收据.json
```

入口自动定位本仓库源码并传递给子进程，可从任意 cwd 通过绝对路径启动。
默认仅发现 `tests/test_*.py`；资产层单独发现 `validation/tests/test_*.py`。
缺目录、空测试集和导入失败明确失败。标准 unittest 包测试入口也可使用：

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

默认`full`与标准unittest仍执行全部测试。显式`fast`只延后现有入口
`DEFERRED`清单中的重型真实行情回放/重编译模块，不删除或改写用例；
新模块默认进入快速层。计时收据记录所选用例、逐项耗时与延后项，
拒绝覆盖；快速通过不等同完整回放、全量覆盖率或理论验收。

本地完整环境验收可使用已有入口和Docker，不维护额外Dockerfile：

```bash
python tools/check_core.py --docker all --scope all --docker-output /绝对路径/全新结果目录
```

宿主需要Python与可用的Docker服务。入口按现有依赖构建缓存镜像，
依次运行3.10、3.13和3.6；现代环境验包/资产两层，旧环境只验包层。
3.6使用linux/amd64保留旧依赖wheel，在ARM宿主仿真运行，耗时单列。
3.10完整包测试另执行94%覆盖率门禁。也可用`--docker 3.10`、
`--docker 3.13`或`--docker 3.6 --scope package`单独验收。
`--docker all --scope validation`只验两个现代环境，不额外执行旧包层；
缺少资产目录时在准备镜像/长回放前直接失败。
源码只读挂载并复制到容器临时目录，测试阶段禁用网络；镜像准备需
下载依赖。结果目录保留实际镜像ID、依赖、源码摘要、日志和逐用例
计时，不覆盖旧结果。该入口验收源码；发行包隔离导入与同一候选
的发版门禁仍由下面的产物流程独立验证，不代替聚宽平台验收。

日常开发按改动执行快速层和定向`--pattern`；Docker三环境完整矩阵
用于阶段/发版前验收，不要求每次commit重跑整套。`--docker all`
顺序运行，各版本也可用独立新目录分别启动，按本机资源安排。

工程契约检查双处版本、公开导出、Python 3.6 语法，以及 README、使用指南与
迁移指南示例；可运行示例和需要调用方输入的模板分别标明。语法检查、
现代运行时、旧依赖实跑、原文核验、真实行情、平台和发布产物分别记录，任一项通过不代替其他项。

日常CI按上次成功main CI以来的差异或PR基底差异分流，不能只比较
本次push的before而漏掉已取消运行的代码修改。成功基准只读查询
GitHub，API不可用则保守跑所有快速层。说明文档只验基础契约，资产/数据工具
变化增加轻量资产契约；源码、测试、依赖或工程入口变化执行快速算法
回归、3.13及3.6兼容检查。未知路径/diff缺失保守执行所有快速层。
这些检查不采集全量覆盖率；过时日常运行由concurrency取消，tag及
手动完整运行不被后续日常推送取消。稳定`ci`门禁要求应执行的job
成功，失败、取消和必要job被跳过均不能过门禁。

`v*` tag及手动`full=true`执行完整验收，覆盖率仅在3.10统计，94门槛
保持。CI集中构建一次wheel/sdist并冻结提交、版本和摘要；现代与3.6
从同一解包sdist执行完整包测试，wheel另行隔离导入；资产job在完整
仓库双环境验收。Release/PyPI只在tag且完整门禁通过后消费同一候选，
上传前复核标签、元数据和摘要。手动完整验收不发布。
具体工具见 [tools/README.md](tools/README.md)。

现代环境额外执行名称错误检查和包算法覆盖率，配置统一在 pyproject：

```bash
python -m ruff check --no-cache src/chan tools tests validation/tools validation/tests
python -m coverage run --data-file /tmp/chan-core.coverage tools/check_core.py
python -m coverage report --data-file /tmp/chan-core.coverage
```

覆盖率启用分支测量，门禁指标为语句与分支合并的总体覆盖率，另报告各自计数；
不把该比例解释为理论或真实样本覆盖率。仅按已测基线设置门槛，不通过排除业务
代码提高比例。质量工具只在现代开发环境运行，Python 3.6 仍独立实跑包测试。
候选构建后执行 `python -m twine check --strict dist/*.whl dist/*.tar.gz`，再封存。
还须执行 `python tools/release_artifacts.py check-description`，实际渲染两种产物的
Markdown 并核对链接；缺少 `readme-renderer[md]` 时明确失败，不将元数据通过
写成页面已渲染。
README 导航使用仓库主干绝对链接，并由现有文档契约测试核对本地目标存在。

## 仓库交付

修改前检查工作树和 diff，只提交本次范围。包代码、测试、版本和发布操作
在本仓库完成；外层研究项目独立维护其集成测试、依赖和报告。

外层升级依赖时，先验证集成行为，再提交子模块引用；引用的核心提交必须
已从远端可获得。未提交的源码修改不能作为已交付的指针。
原始输入、历史收据、已发布版本和冻结研究产物保留，不覆盖。

推送标签须精确指定对应版本，如 `git push origin refs/tags/v1.0.0`；
不使用 `git push --tags` 顺带发送历史标签。已有标签保持原名称与指向；
缺少标签的历史提交仅在具有独立交付或复现价值时评估补充，不按提交数量
或远端缺口批量补齐。新增本地标签与推送分别评估，候选名称、提交、理由及
工作流影响明确后执行。后续治理在新的提交中维护，不重发已有版本。
