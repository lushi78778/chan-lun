# 核心库验收与标注工具

本目录维护核心库的真实行情验收、独立标注编译、候选发现扫描与图册构建工具。
验收收据与冻结输入包统一归档在 `../validation/`, 收据链说明见
[validation/README.md](../validation/README.md)。

## 真实行情验收（verify_*）

| 工具 | 用途 | 示例 |
|---|---|---|
| `verify_core_history.py` | 只读Parquet真实行情验收、输入摘要及逐日前缀防未来检查；本地需pyarrow | `python tools/verify_core_history.py /数据集绝对路径 --replay --output /结果绝对路径.json` |
| `verify_core_available.py` | 收盘/到达门控、保守结构日线和30m前缀验收；精度适配有界且留痕 | `python tools/verify_core_available.py /数据集绝对路径 --output /结果绝对路径.json` |
| `verify_ma_history.py` | 均线候选日线/30m前缀、独立面积/价格算术、未来隔离与记录稳定性 | `python tools/verify_ma_history.py /数据集绝对路径 --output /结果绝对路径.json` |
| `verify_completion_history.py` | 声明最低层f1构造后验证完成类型递归、证据时间、未来隔离与冻结稳定性 | `python tools/verify_completion_history.py /数据集绝对路径 --parts bi --output /结果绝对路径.json` |
| `verify_fractal_history.py` | 分型区间实际前缀冻结、独立边界核对、未来隔离及终态稳定性 | `python tools/verify_fractal_history.py /数据集绝对路径 --output /结果绝对路径.json` |
| `verify_points_history.py` | 自动MACD辅助一类/因果中枢/点位链的真实行情与时间接线验收 | `python tools/verify_points_history.py /数据集绝对路径 --output /结果绝对路径.json` |
| `verify_rounds_lineage.py` | 轮次移交与中枢演化谱系的十ETF三粒度逐前缀真实回放收据；谱系/台账零回写断言与排除原因分布 | `python tools/verify_rounds_lineage.py /数据集绝对路径 --output /结果绝对路径.json` |

`verify_core_history.py` 是其余验收工具的共享算术入口（`load_frames/bars_from/digest` 等），
兄弟模块经脚本目录导入，须与本目录内其他 `verify_*.py` 一起使用。

历史数据验收默认取十只覆盖宽基、行业、跨境、黄金和债券的ETF；核验
manifest及所读文件SHA-256。`--replay` 加入逐交易日验证：每前缀复权锚、
MACD前缀比例一致性、未来价格扰动与候选修订账本。报告明确区分计算、
时点契约与理论真实性，不测试收益或策略表现。
`pyarrow`仅用于这些库外工具，不加入核心库依赖或聚宽环境。

## 独立标注编译（gen_real_*，不导入chan）

| 工具 | 用途 |
|---|---|
| `gen_real_strict_trend.py` | 课17/20/29/33/106：R2 严格趋势 Zn 与 a+A+b+B+c 完整角色标注编译 |
| `gen_real_first_point.py` | 课17/20/24/27/29/106：R2 一类买卖点真实正反例标注编译 |
| `gen_real_second_point.py` | 课17/21/53/101：R2 二类买卖点真实正反例标注编译 |
| `gen_real_third_point.py` | 编译三类买卖点真实正反例标注为核心测试fixture |
| `gen_real_xd_f1.py` | 课20/38/63/67/71/78/84/106：人工完成XD→F1标注编译 |
| `gen_real_f1_originals.py` | R2 F1 独立标注编译器（课35/38/63/67/81/84/106），输出portable包fixture |
| `gen_real_causal_formation.py` | 课108：R2 因果底顶真实正反例标注编译 |

编译器只验算人工冻结的审计表，不搜索分界、不自动发现真值；非法索引、
空交集及提前证明直接拒绝。固定链、完成XD与台账算术按 0.9.x 各冻结
版本链式复用，不重推已冻结结构。

## 候选发现扫描（scan_real_*，导入核心库）

| 工具 | 用途 |
|---|---|
| `scan_real_first_point.py` | 0.9.9 一类买卖点成立候选发现扫描（课24/17/20/27/29/33） |
| `scan_real_strict_trend.py` | 0.9.3 严格两中枢趋势修正口径发现扫描（课20/29/33） |
| `scan_real_rounds.py` | 笔级月首日起点连续真实窗口同侧多轮发现扫描（0.9.9/0.9.11冻结算术，不导入chan） |

发现工具按冻结口径分类候选，不产出独立真值；独立标注由对应
`gen_real_*.py` 的人工表另行冻结，扫描结果仅作候选发现，入选窗一律
以窗内重跑冻结验证。

## 标注图册构建（build_*_annotations，不调用算法）

| 工具 | 用途 |
|---|---|
| `build_original_annotations.py` | 课62/65/67/71/77/78/81/106原页与人工预期对照册；108课PDF经`--pdf`传入 |
| `build_real_annotations.py` | 真实基础标注对照册（读取冻结标签，不调用识别器） |
| `build_real_f1_annotations.py` | 六窗口双路径F1及相邻F2对照册 |
| `build_real_xd_annotations.py` | 四窗口独立线段对照册 |
| `build_real_xd_f1_annotations.py` | 完成XD构造F1两窗口对照册 |

108课PDF为维护者私有版权材料，不随本仓库分发；构建原图对照册时经
`--pdf` 指定本地副本。图册构建器只读取冻结标签并核对输入包摘要，
产物拒绝覆盖，重跑需使用不存在的新文件名。

## 样本、诊断与既有工具

| 工具 | 用途 | 示例 |
|---|---|---|
| `index_core_samples.py` | R2真实ETF样本准备：文件完整性、指定十标的原始数据概况与快照提取；本地Python3.10+及pyarrow环境使用 | `python tools/index_core_samples.py profile /数据集绝对路径 --periods 1d 30m --output /结果绝对路径.json` |
| `diagnose_chan.py` | 检查当前解释器实际导入的 chan，不注入源码、不安装或改写模块；可将本文件复制到聚宽运行 | `python tools/diagnose_chan.py --expect 0.4.0` |
| `benchmark.py` | 包内固定样本性能基准（历史工具，见 `tests/test_performance_baseline.py`） | `python tools/benchmark.py --help` |
| `verify_installed.py` | 核心库 wheel 的隔离导入验收 | 包仓库根运行 `python -I tools/verify_installed.py` |

诊断工具必须使用目标环境的 Python，不能由本地结果推断 Notebook 环境。
