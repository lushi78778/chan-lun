# 工程工具

本目录维护开发、安装诊断、产物核验和性能基准入口。这五个脚本随 sdist
分发，不依赖仓库的 `validation/`。包运行时不加载这些工具。

从核心库仓库根运行：

| 工具 | 用途 | 命令 |
|---|---|---|
| `check_core.py` | 检查源码归属与版本，运行包测试或显式选择资产层 | `python tools/check_core.py`；`--scope validation`；`--scope all`；`--pattern test_模块.py` |
| `release_artifacts.py` | 核验标签、双处版本、产物元数据和摘要；封存同一候选 | `python tools/release_artifacts.py check-source`；`seal --commit <SHA>`；`verify --commit <SHA>` |
| `diagnose_chan.py` | 诊断目标解释器实际导入的包及安装元数据 | `python tools/diagnose_chan.py --expect 1.0.0 --json` |
| `verify_installed.py` | 在隔离模式核验已安装 wheel 的导入路径、版本与公开入口 | `python -I tools/verify_installed.py` |
| `benchmark.py` | 对显式输入测量批量与回放耗时、内存、结构规模 | `python tools/benchmark.py --help` |

`check_core.py` 支持从其他 cwd 通过绝对路径启动，并将本仓库源码路径
传给测试子进程。选择资产层时，完整仓库必须存在 `validation/tests/`；
缺目录或空测试集明确失败。安装诊断不注入源码、不自动安装。

`release_artifacts.py` 只核验和封存，不构建、不发布。标签参数仅在对应
版本发布时填写；日常治理不使用已有发布标签创建新产物。

真实行情验收、独立标注、候选扫描、图册与样本准备共 23 个工具位于
[validation/tools/](../validation/tools/README.md)，不进入 wheel/sdist。
`benchmark.py` 读取 Parquet 时同样需要可选 `pyarrow`，CSV 输入不需要。
诊断目标为聚宽时，必须使用目标环境的解释器，不能用本地结果替代。
