# 核心库开发与验收

本仓库独立维护 `chan-lun-core`。定位为缠论结构识别与理论辅助计算库，
输入输出与能力边界见 [README](README.md) 和 [API](API.md)。
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

- [ARCHITECTURE.md](ARCHITECTURE.md) 定义数据对象、计算函数和组合入口。
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

工程维护与概念实现分开登记；纯文档、测试布局和工具整理不自动升级包版本。
当前 1.x 的兼容与算法修正规则以 [API.md](API.md#1x-版本规则) 为准。

## 两层验收

```bash
python tools/check_core.py                              # 自包含包测试
python tools/check_core.py --pattern test_contracts.py   # 定向包测试
python tools/check_core.py --scope validation            # 完整仓库资产验收
python tools/check_core.py --scope all                   # 两层验收
```

入口自动定位本仓库源码并传递给子进程，可从任意 cwd 通过绝对路径启动。
默认仅发现 `tests/test_*.py`；资产层单独发现 `validation/tests/test_*.py`。
缺目录、空测试集和导入失败明确失败。标准 unittest 包测试入口也可使用：

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

工程契约检查双处版本、公开导出、Python 3.6 语法以及 README/MIGRATION
示例。语法检查、现代运行时、旧依赖实跑、原文核验、真实行情、平台和
发布产物分别记录，任一项通过不代替其他项。

CI 集中构建一次 wheel/sdist 并冻结提交、版本和摘要。现代与 Python 3.6
job 从解包 sdist 执行包测试，wheel 另行隔离导入；资产 job 在完整仓库
执行验收。Release/PyPI 仅消费同一候选，上传前复核标签、元数据和摘要。
具体工具见 [tools/README.md](tools/README.md)。

## 仓库交付

修改前检查工作树和 diff，只提交本次范围。包代码、测试、版本和发布操作
在本仓库完成；外层研究项目独立维护其集成测试、依赖和报告。

外层升级依赖时，先验证集成行为，再提交子模块引用；引用的核心提交必须
已从远端可获得。未提交的源码修改不能作为已交付的指针。
原始输入、历史收据、已发布版本和冻结研究产物保留，不覆盖。

推送标签须精确指定对应版本，如 `git push origin refs/tags/v1.0.0`；
不使用 `git push --tags` 顺带发送历史标签。已发布标签不移动，后续治理
在新的提交中维护，不重发已有版本。
