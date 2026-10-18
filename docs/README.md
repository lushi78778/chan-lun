# 文档中心

本目录集中维护核心库的参考正文。项目定位和最小用法从[根 README](../README.md)
开始；后续按本页选择文档，不需要在多个目录寻找同一主题的另一份说明。

## 文档布局

```text
docs/
├── README.md                       # 统一文档入口与维护职责
├── installation.md                 # 安装、Notebook、离线与导入排错
├── usage.md                        # 输入、回放、模块组合与排错
├── api.md                          # 公开 API 与行为契约
├── architecture.md                 # 分层、数据流与组合原则
├── migration.md                    # 升级影响与迁移指纹
├── 缠论理论逐一实现计划.md           # §6 唯一理论进度；规格与阶段证据
├── 辅助模块能力与证据矩阵.md         # 标明复核基准的能力与证据参考
└── archive/                        # 历史治理快照与原登记
```

| 要查的内容 | 唯一维护位置 |
|---|---|
| 安装到目标解释器、聚宽 Notebook 或离线环境 | [安装排错](installation.md) |
| 行情输入、观察时点、候选判定与模块示例 | [使用指南](usage.md) |
| 导出、字段、身份、时间、空值、原因码及 1.x 稳定性 | [API 契约](api.md) |
| 对象与函数的职责、层次和组合方式 | [架构](architecture.md) |
| 跨版本影响、旧结果保留与指纹比较 | [迁移指南](migration.md) |
| 当前理论能力、剩余缺口和阶段证据 | [正式计划](缠论理论逐一实现计划.md) §6 |
| 长期维护与剩余工作的顺序、依赖和验收条件 | [正式计划](缠论理论逐一实现计划.md) §12；不另维护进度 |
| 工程阈值与辅助模块的证据范围 | [能力与证据矩阵](辅助模块能力与证据矩阵.md) |

## 根目录与目录内索引

根目录保留四份常规入口文档，其余参考正文放在本目录：

| 根目录文件 | 职责 |
|---|---|
| [README](../README.md) | 项目介绍、最小工作流、接口选择和目录导航 |
| [CONTRIBUTING](../CONTRIBUTING.md) | 开发、验收与交付流程 |
| [AGENTS](../AGENTS.md) | 协作执行规则 |
| [CHANGELOG](../CHANGELOG.md) | 版本事实与未发版工程维护 |

[tests/README](../tests/README.md)、[tools/README](../tools/README.md)、
[validation/README](../validation/README.md) 和
[validation/tools/README](../validation/tools/README.md) 仅作为本目录的测试、
命令或证据索引。具体开发规则由 CONTRIBUTING 维护，API 规则由本目录的
`api.md` 维护，不在各索引另写一套。

仓库代码、测试和发行包边界见[项目结构](../README.md#项目结构与维护)。
`src/chan/` 与 `tests/` 分别维护算法和自包含包测试；`tools/` 维护工程入口，
`validation/` 维护仓库验收资产及工具，排除 wheel/sdist。

## 维护与历史

README、使用指南和迁移指南的可运行示例由 `tests/test_contracts.py` 执行；
带待提供输入的接线模板须明确标注。文档移动须同步相对链接、示例定位和
源码包检查。`docs/` 随 sdist 分发，不能靠原仓库中尚存的旧路径使测试通过。

理论进度只登记在正式计划 §6。带版本和日期的收据、能力矩阵及历史快照
说明当时的证据，不作为当前测试总数、远端状态或另一套理论进度。

历史治理记录归档在 `archive/`：

- [项目治理评估快照](archive/项目治理评估-2026-10-18.md)
- [项目治理整改收口](archive/项目治理整改收口-2026-10-18.md)
- [整理前实现登记](archive/implementation-register-2026-10-18.md)

工具路径迁移后的当前命令见[工程工具](../tools/README.md)和
[资产工具](../validation/tools/README.md)。原始输入、收据、图册和历史产物保留
当时路径、参数与摘要；需要复现历史环境时检出对应 Git 提交，不回写旧证据。
