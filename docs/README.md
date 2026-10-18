# 文档与目录索引

`chan-lun-core` 是独立维护的结构识别与理论辅助计算库，发行名为
`chan-lun-core`，导入名为 `chan`。仓库采用 src 布局；外层研究项目
可通过 Git 子模块引用本仓库，开发和 CI 不依赖外层目录。

## 目录职责

```text
.
├── pyproject.toml          # 包元数据、运行依赖、构建与包发现配置
├── requirements-dev.txt   # Python 3.10+ 开发和构建环境
├── src/chan/              # 可安装算法包；公开导出与运行时版本在 __init__.py
├── tests/                 # 自包含包测试
│   └── fixtures/          # 包测试所需的冻结最小输入与独立预期
├── tools/                 # 五个自包含工程入口
├── docs/                  # 理论计划、能力参考、内部治理说明
│   └── archive/           # 历史登记快照
├── validation/            # 仓库级开发验收资产，排除 wheel/sdist
│   ├── tests/             # 原始包、独立重建和工具适配验收
│   ├── tools/             # 行情验收、独立标注、扫描、图册、样本准备
│   └── requirements.txt   # 可选 Parquet 工具依赖
└── .github/               # CI 与随版声明
```

`src/chan/` 按理论概念划分模块，数据对象留在所属模块，公开导入路径由
[API.md](../API.md) 约束。共用数学运算放 `_intervals.py`、`_series.py`；
策略调度、行情下载和下单由调用方维护。

`tests/fixtures/` 保存可独立运行包测试所需的最小冻结材料；原始行情包、
审计表、收据和图册放 `validation/`。包测试只能读取随 sdist 分发的文件；
资产测试可读取两侧材料，缺失时明确失败。

## 文档职责

| 入口 | 唯一维护的内容 |
|---|---|
| [README](../README.md) | 当前定位、安装、用法和使用边界 |
| [API](../API.md) | 公开导出、字段、身份、时间、空值和版本兼容契约 |
| [ARCHITECTURE](../ARCHITECTURE.md) | 模块分层、输入契约与组合方式 |
| [CONTRIBUTING](../CONTRIBUTING.md) / [AGENTS](../AGENTS.md) | 开发、验收与交付流程 / 协作执行规则 |
| [理论实现计划](缠论理论逐一实现计划.md) | §6 唯一当前理论进度；其他章节登记规格与阶段证据 |
| [能力与证据矩阵](辅助模块能力与证据矩阵.md) | 辅助模块的阈值和证据参考，标明复核基准版本 |
| [CHANGELOG](../CHANGELOG.md) / [MIGRATION](../MIGRATION.md) | 版本事实与工程维护 / 调用方迁移影响 |
| [工程工具](../tools/README.md) | 包测试、安装诊断、产物检查与基准入口 |
| [资产索引](../validation/README.md) / [资产工具](../validation/tools/README.md) | 按版本归档的证据 / 当前仓库验收命令 |

当前说明随代码维护。带版本、日期的验收记录说明当时证据，不能用其
旧测试数量或发布状态覆盖当前状态；源码版本与发布状态分别核验。
治理评估与整改快照见 [评估](项目治理评估-2026-10-18.md)、
[整改](项目治理整改收口-2026-10-18.md)，不另维护理论进度。

## 工具路径迁移

2026-10-18 起，原 `tools/` 中的 `verify_*` 行情工具、`gen_real_*`、
`scan_real_*`、`build_*_annotations.py`、`index_core_samples.py` 统一迁到
`validation/tools/`，文件名保持。`verify_installed.py` 保留在工程层。
旧命令更换脚本路径；原图图册的 `--pdf` 明确为必填，不再猜测维护者
私有材料的位置。其他参数保持，当前完整命令见资产工具索引。

历史收据、HTML 和原始输入保留旧路径、参数与摘要；需要重放当时完整
环境时检出对应 Git 提交。新验收使用新文件名，不能回写历史记录。
