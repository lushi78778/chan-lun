# chan-lun-core 协作规范

本文件适用于独立核心库仓库，不依赖维护者外层项目的目录或测试入口。
开发与验收流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，目录与文档职责见
[docs/README.md](docs/README.md)。

## 真源与范围

- `src/chan/` 为算法唯一真源，`tests/` 为包测试唯一真源。
- [理论实现计划](docs/缠论理论逐一实现计划.md) §6 为唯一实现进度表;
  其他文档只链接，不另维护状态。`validation/` 是仓库级资产，排除 wheel/sdist。
  `tests/` 维护自包含包测试，`validation/tests/` 维护资产验收；资产工具在
  `validation/tools/`，工程入口在 `tools/`。
- 理论最终依据为《缠中说禅教你炒股票 108 课》原文。PDF、逐课文本、
  导航知识库和笔记是维护者私有工作区材料，不随本仓库分发。
  文本存疑时复核 PDF 原页; 缺原文不能登记理论核验完成。
- 库不取行情、不调度策略、不下单。新行为接入研究脚本与平台需独立验证。
- 日期和验收记录使用北京时间 UTC+8，本机用 `TZ=Asia/Shanghai`。

## 实现与兼容

- 每概念完成原文核验、规格、实现、边界测试、公开导出和 §6 登记。
  docstring 记录课号、输入输出、边界、量化阈值与理论差异;
  判定分支及测试说明对应的数学含义或原文依据。
- 兼容 Python 3.6、numpy 1.14、pandas 0.23。禁用 walrus、dataclasses、
  match、自描述 f-string、to_numpy、to_markdown。
- 通用闭区间交集放 `_intervals.py`，均线差值放 `_series.py`;
  不同理论的完成和延伸规则保留各自语义。
- 版本号在 `pyproject.toml` 与 `src/chan/__init__.py` 保持一致。
  1.0 后遵循 [API.md](API.md) 的稳定性契约; 行为变化须说明并验证。
- 观察日截断行情与复权锚点; 端点时间不同于证据确认时间。
  回放采用实际可见前缀，验证已完成项前缀一致性和未完成尾部修订。
- 所有输出使用绝对路径; 冻结输入、历史收据与已交付版本保留，不覆盖。

## 独立验收与交付

```bash
python -m pip install -r requirements-dev.txt  # Python 3.10+ 开发环境
python tools/check_core.py
python tools/check_core.py --pattern test_模块.py
python tools/check_core.py --scope validation
python tools/check_core.py --scope all
```

- 默认只运行包测试；资产测试在完整仓库显式执行，不静默跳过缺失资产。
- 标准 `python -m unittest discover -s tests -p 'test_*.py'` 仍可使用。
  源码入口、Python 3.6 语法、旧环境实跑、原文、真实行情、安装包和平台
  验收分别记录。空测试集或导入失败不能视为成功。
- 外层集成测试、教程、策略和报告由外层项目维护，本仓库 CI 不调用外层工具。
- 修改前检查工作树与 diff，只纳入本次范围。提交、tag、push、CI、
  Release/PyPI 分别核验; 工程治理不自动升级版本或发布。
- 核心库提交在本仓库完成。外层子模块指针只引用远端已存在的提交;
  不将本地未提交改动登记为外层已交付指针。
- 文档和注释只记结论与验证证据，不写决策归因。
