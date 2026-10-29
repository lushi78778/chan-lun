# chan-lun-core

缠论结构识别与理论辅助计算库。输入单标的、单周期的行情或结构序列，
输出分型、笔、线段、中枢、背驰、买卖点，以及多级分解和辅助状态。
算法用 Python 实现，第三方运行依赖只有 numpy 与 pandas；MACD 内置计算。

| 项目 | 约定 |
|---|---|
| 发行名 / 导入名 | `chan-lun-core` / `chan` |
| 当前源码版本 | `1.2.0`；发行可用性以 PyPI / GitHub Release 为准，安装环境核对 `chan.__version__` 与实际导入路径 |
| 运行兼容目标 | Python 3.6、numpy 1.14、pandas 0.23 及以上；验证范围见下文 |
| 开发与构建 | Python 3.10+，使用本仓库 `requirements-dev.txt` |
| 仓库 / 许可证 | [lushi78778/chan-lun](https://github.com/lushi78778/chan-lun) / [MIT](https://github.com/lushi78778/chan-lun/blob/main/LICENSE) |

本库维护算法、公开契约、包测试及仓库验收资产。调用方负责行情获取、交易日历、
复权、标的和周期管理、策略调度、组合风控与下单。跨级别和板块接口需要调用方
提供多组已对齐的输入；理论级别由结构关系和输入声明确定，不按分钟周期自动映射。

线段识别可显式声明起点前提，未传入时保持既有工程口径；参数和时间边界见
[使用指南](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md)的“显式线段起点前提”。

## 阅读入口

下列链接指向仓库当前主干文档，安装版本及升级差异按版本记录核对。

| 要完成的事 | 入口 |
|---|---|
| 安装并完成第一次计算 | [安装](https://github.com/lushi78778/chan-lun/blob/main/README.md#%E5%AE%89%E8%A3%85)、[快速开始](https://github.com/lushi78778/chan-lun/blob/main/README.md#%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B) |
| 根据现有数据选择接口 | [按输入选择入口](https://github.com/lushi78778/chan-lun/blob/main/README.md#%E6%8C%89%E8%BE%93%E5%85%A5%E9%80%89%E6%8B%A9%E5%85%A5%E5%8F%A3) |
| 接入自己的行情、分步计算或使用辅助模块 | [使用指南](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md) |
| 排查 Notebook 安装、版本或同名目录遮蔽 | [安装与环境排错](https://github.com/lushi78778/chan-lun/blob/main/docs/installation.md) |
| 查字段、身份、原因码、空值与兼容规则 | [API 契约](https://github.com/lushi78778/chan-lun/blob/main/docs/api.md) |
| 了解架构、维护代码或执行验收 | [架构](https://github.com/lushi78778/chan-lun/blob/main/docs/architecture.md)、[开发流程](https://github.com/lushi78778/chan-lun/blob/main/CONTRIBUTING.md)、[目录索引](https://github.com/lushi78778/chan-lun/blob/main/docs/README.md) |
| 查理论实现进度与真实证据 | [正式计划 §6](https://github.com/lushi78778/chan-lun/blob/main/docs/%E7%BC%A0%E8%AE%BA%E7%90%86%E8%AE%BA%E9%80%90%E4%B8%80%E5%AE%9E%E7%8E%B0%E8%AE%A1%E5%88%92.md#6-%E5%AE%9E%E7%8E%B0%E6%B8%85%E5%8D%95%E8%BF%9B%E5%BA%A6%E8%A1%A8%E5%94%AF%E4%B8%80%E8%BF%9B%E5%BA%A6%E7%BB%B4%E6%8A%A4%E5%A4%84)、[验收记录](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md) |
| 长期维护与剩余工作的次序 | [正式计划 §12](https://github.com/lushi78778/chan-lun/blob/main/docs/%E7%BC%A0%E8%AE%BA%E7%90%86%E8%AE%BA%E9%80%90%E4%B8%80%E5%AE%9E%E7%8E%B0%E8%AE%A1%E5%88%92.md#12-1x-%E9%95%BF%E6%9C%9F%E7%BB%B4%E6%8A%A4%E4%B8%8E%E5%89%A9%E4%BD%99%E5%B7%A5%E4%BD%9C2026-10-18-%E8%B5%B7) |
| 评估版本升级 | [迁移指南](https://github.com/lushi78778/chan-lun/blob/main/docs/migration.md)、[变更记录](https://github.com/lushi78778/chan-lun/blob/main/CHANGELOG.md) |

## 安装

安装示例固定发行版本 `1.2.0`；发行产物可用后执行，升级差异见版本记录。
使用将要运行程序的解释器安装，固定版本便于复现：

```bash
python -m pip install 'chan-lun-core==1.2.0'
python -c "import chan; print(chan.__version__); print(chan.__file__)"
```

发行名与导入名不同。安装后的包应来自预期环境，工作区中的 `chan.py` 或同名
目录可能遮蔽它。Notebook 安装后若此前已导入过包，应重启内核再核对。
聚宽、离线 wheel 安装和导入诊断见[安装指南](https://github.com/lushi78778/chan-lun/blob/main/docs/installation.md)。

运行依赖下限与现代开发依赖分别管理。旧 Python 环境优先安装已构建的 wheel；
`requirements-dev.txt` 用于维护和构建，不用于升级平台内置环境。源码版本相同
不代表提交或发行产物相同，工程维护和发布记录分别核验。

## 快速开始

下面生成单标的、单周期的合成行情，无需行情账号，复制后即可运行：

```python
import json
import math
from datetime import datetime, timedelta

import pandas as pd
from chan import normalize_bars, analyze_bars

closes = [20.0 + 3.0 * math.sin(i / 6.0) + i / 80.0 for i in range(160)]
df = pd.DataFrame({
    "open": closes,
    "close": closes,
    "high": [price + 0.3 for price in closes],
    "low": [price - 0.3 for price in closes],
    "volume": [1000.0] * len(closes),
}, index=[datetime(2025, 1, 1) + timedelta(days=i) for i in range(160)])

bars = normalize_bars(df)
result = analyze_bars(bars)
summary = {
    "as_of": str(result.as_of),
    "fxs": len(result.fxs),
    "bis": len(result.bis),
    "xds": len(result.xds),
    "bi_zss": len(result.bi_zss),
    "xd_zss": len(result.xd_zss),
    "buy_points": len(result.buy_points),
    "sell_points": len(result.sell_points),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
snapshot = result.to_dict()
json_text = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
```

按当前默认参数，摘要为：

```json
{
  "as_of": "2025-06-09 00:00:00",
  "fxs": 8,
  "bis": 7,
  "xds": 1,
  "bi_zss": 1,
  "xd_zss": 0,
  "buy_points": 0,
  "sell_points": 0
}
```

这个输入识别出分型、笔和线段，笔级中枢与线段级中枢分别统计；买卖候选为空
是正常结果，不表示程序失败，也不证明价格安全或全部理论分支已经检查。
示例只用于说明调用与结果，不是行情案例或策略验证。

`analyze_bars` 组合基础识别链，默认采用 81 课笔标准。需要 106 课标准时用
`analyze_bars(bars, bi_standard="106")`。自定义 MACD、背驰、买卖点参数或使用
严格条件、递归、谱系及其他辅助模块时，按[模块示例](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#6-%E6%A8%A1%E5%9D%97%E4%B8%8E%E5%85%AC%E5%BC%80%E5%85%A5%E5%8F%A3)
另行组合；这些能力不会全部由 `analyze_bars` 自动执行。

## 输入与结果

标准输入是时间严格递增、唯一的 dict 列表或元组，每条包含
`dt/open/high/low/close/volume`。OHLC 必须有限且严格为正，成交量有限且非负，
并满足 `low <= open/close <= high`。一个序列对应一个标的、一个周期及同一价格基准。

DataFrame 可先经 `normalize_bars` 映射列名、转数值并排序；它默认剔除
`volume == 0` 且 `high == low` 的行。该适配不代替行情校验。
`analyze_bars` 会校验输入；底层函数各有前提，直接组合时可先调用
`validate_bars`。重复时间、缺失值、复权、时区与停牌处理方式须由调用方明确。
完整规则见[行情输入契约](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#1-%E8%A1%8C%E6%83%85%E8%BE%93%E5%85%A5%E5%A5%91%E7%BA%A6)。

`AnalysisResult` 按级别保留结果：

| 字段 | 含义 |
|---|---|
| `as_of` | 最后一根输入 bar 的时间；空输入为 `None` |
| `new_bars`、`fxs`、`bis`、`xds` | 包含处理后的 K 线、分型、笔和线段 |
| `bi_zss` / `xd_zss` | 分别由笔 / 线段构造的中枢 |
| `bi_trends` | 笔级中枢的走势分类 |
| `trend_bc` / `pan_bc` | 笔级趋势 / 盘整背驰候选 |
| `buy_points` / `sell_points` | 基础链的笔级简化买卖候选 |
| `dif`、`dea`、`hist` | 与原始输入 bars 等长的 MACD 数组，默认 12/26/9 |

结果字段不能重新绑定，内部列表、数组与结构对象仍可修改。每次批量计算独立
分配结果，`AnalysisResult.to_dict()` 生成独立的 JSON 可写快照。底层对象按各自
契约序列化，例如 `NewBar.to_dict()` 保留原时间类型，不能据此假定任意对象均可
直接 `json.dumps`。

空行情也是合法输入：

```python
from chan import analyze_bars

empty = analyze_bars([])
assert empty.as_of is None
assert empty.bis == []
assert empty.buy_points == []
```

字段 `None`、空结果、条件否决与证据不足有不同含义。扫描入口还可返回
`exclusions`、`skipped`、`conditions` 和 `completed_types`，用于解释未产生点位的
原因；它们的范围见 [API](https://github.com/lushi78778/chan-lun/blob/main/docs/api.md#9-%E7%A9%BA%E5%80%BC%E4%B8%8E%E5%BE%85%E5%88%A4%E8%AF%AD%E4%B9%89) 与[排错指南](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#7-%E8%AF%81%E6%8D%AE%E8%BA%AB%E4%BB%BD%E4%B8%8E%E5%B8%B8%E8%A7%81%E9%94%99%E8%AF%AF)。

## 按输入选择入口

| 你已经具备的输入 / 目的 | 入口 | 结果与前提 |
|---|---|---|
| 单标的单周期原始行情 | `analyze_bars` | 基础结构、笔级候选和指标；只计算提供的前缀 |
| 已保证收盘的行情与历史观察时点 | `analyze_at`、`replay_bars` | 先按时间截断，再计算；回放追踪出现、修订与撤销 |
| 含收盘与实际到达时间的行情 | `analyze_available`、`replay_available` | 按 `closed_dt/available_dt` 门控；回放另给保守结构观察 |
| 需要自定义基础链参数 | `chan_fx_bi`、`find_xds`、`find_zs`、`find_*_bc` 等 | 显式分步组合；保持笔级与线段级输入一致 |
| 已确认次级走势与反转 / 中枢上下文 | `find_second_points`、`find_third_points` | 已确认输入上的条件判定，保留必要证据时间 |
| 已确认次级走势与对应行情 | `find_first_points`、`scan_first_points`、`analyze_point_chain` | MACD 辅助一类候选及组合链；候选性质沿链保留 |
| 已确认走势、相邻级别与力度方法 | `scan_strict_divergence`、`strict_nested_chain`、`strict_completion_cascade` | 严格结构与显式证据判定；力度方法和级别声明仍是输入前提 |
| 已确认类型的递归完成、中枢演化与轮次 | `confirm_level_up`、`track_center_lineage`、`track_rounds` | 完成证据、稳定身份、版本链和轮次移交 |
| 均线、分型区间或成员状态等专项输入 | 各辅助模块；均线组合用 `find_ma_points` / `ma_point_state` | 封闭候选与可撤销即时预警分别返回；阈值性质见模块说明 |

公开入口经 `import chan` 或 `from chan import ...` 使用；完整导出以
`chan.__all__` 为准，字段与稳定性以 [API](https://github.com/lushi78778/chan-lun/blob/main/docs/api.md) 为准。

笔级简化买卖候选、已确认输入上的条件判定、严格结构判定和工程辅助状态分别
解释。将任意笔或线段包装为 `ConfirmedMove`，不能证明它是真实完成的次级走势。
`confirmed` 也须结合所属接口的条件、力度方法与证据理解，不能统一视为理论证明
或交易指令。输入、示例与模块边界见[使用指南](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#5-%E5%80%99%E9%80%89%E4%B8%8E%E6%9D%A1%E4%BB%B6%E5%88%A4%E5%AE%9A)。

## 时间、回放与证据边界

**结构位置、证据确认时间、行情可用时间分别记录。** 分型中心、笔端点和点位
`dt` 表达结构位置；`as_of` 表达输入截止，并不证明末根 bar 已收盘。
`XD.evidence_dt` 是最后证据笔的端点，也不能当作实际行情确认时间。

历史计算先确定观察时点可见的输入，再计算结构。已经保证收盘的离线行情可以用：

```python
from chan import analyze_at, replay_bars

# 复用快速开始的 bars；真实接入时由调用方保证相应时点的收盘与价格基准。
cutoff = bars[-1]["dt"]
current = analyze_at(bars, cutoff)
for observed in replay_bars(bars, observations=[cutoff]):
    print(observed.observed_dt, len(observed.changes))
```

盘中或存在数据延迟时，应提供收盘与实际到达时间，使用
[`analyze_available`](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#4-%E6%8C%89%E6%94%B6%E7%9B%98%E4%B8%8E%E5%88%B0%E8%BE%BE%E6%97%B6%E9%97%B4%E8%A7%82%E5%AF%9F)。调用方还须按相应观察
时刻截断跨周期输入，并使用当时可得的复权基准；库不下载行情或复权。

固定输入历史版本、固定观察时点时，视野之外的未来价格不应影响当前结果。
观察时点推进后，未完成尾部和候选允许修订或撤销；`first_seen` 只代表在给定
观察网格中首次出现。用全样本最终结果按端点时间过滤，无法还原历史可见状态。
回放规则与账本身份见[时间指南](https://github.com/lushi78778/chan-lun/blob/main/docs/usage.md#2-%E6%8C%89%E8%A7%82%E5%AF%9F%E6%97%B6%E7%82%B9%E8%AE%A1%E7%AE%97%E4%B8%8E%E8%BF%BD%E8%B8%AA%E4%BF%AE%E8%AE%A2)。

当前使用边界包括：同侧多轮独立真实样本缺口、课 77 历史 OHLC 缺失和课 106
图文歧义、辅助模块的工程阈值，以及调用方对最低类型、级别和供应历史版本的
证明责任。接口实现、真实样本覆盖、平台可运行和策略有效性是不同结论。
当前理论能力与剩余缺口只在[正式计划 §6](https://github.com/lushi78778/chan-lun/blob/main/docs/%E7%BC%A0%E8%AE%BA%E7%90%86%E8%AE%BA%E9%80%90%E4%B8%80%E5%AE%9E%E7%8E%B0%E8%AE%A1%E5%88%92.md#6-%E5%AE%9E%E7%8E%B0%E6%B8%85%E5%8D%95%E8%BF%9B%E5%BA%A6%E8%A1%A8%E5%94%AF%E4%B8%80%E8%BF%9B%E5%BA%A6%E7%BB%B4%E6%8A%A4%E5%A4%84)
维护；分支证据和随版声明见[验收记录](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)。

## 项目结构与维护

本仓库独立开发和验收，采用 src 布局；也可由研究项目作为 Git 子模块引用。
仓库根的 `src/chan/` 是可安装包，仓库本身不是运行时包目录。

```text
.
├── pyproject.toml       # 包元数据、运行依赖与包发现配置
├── requirements-dev.txt # 现代开发与构建依赖
├── src/chan/           # 算法、数据对象、公开导出与运行时版本
├── tests/              # 自包含包测试；fixtures 为最小冻结输入与预期
├── tools/              # 包测试、诊断、产物检查与基准工具
├── docs/               # 用法、架构导航、正式计划与治理文档
├── validation/         # 仓库验收资产、资产测试与数据工具
└── .github/            # CI 与随版声明
```

| 交付形态 | 范围 |
|---|---|
| wheel | 可安装算法包、发行元数据与许可证；不含仓库验收资产 |
| sdist | 包源码、包测试与最小 fixtures、工程工具及维护文档；不含 `validation/` |
| 完整仓库 | 另含 `validation/` 的原始输入、独立标注、收据和资产工具 |
| 维护者私有材料 | 108 课 PDF、逐课原文及笔记；理论核验须显式提供，不随仓库分发 |

算法与包测试分别以 `src/chan/`、`tests/` 为真源；工程入口在 `tools/`，资产工具
在 `validation/tools/`。独立包开发不读取外层研究项目。研究集成与平台接线由
调用方另行验收，冻结脚本和历史产物保留各自版本。

在核心库仓库根准备现代开发环境后执行：

```bash
python -m pip install -r requirements-dev.txt
python tools/check_core.py                              # 自包含包测试
python tools/check_core.py --pattern test_contracts.py   # 文档示例与工程契约
python tools/check_core.py --scope validation            # 完整仓库资产验收
python tools/check_core.py --scope all                   # 两层合跑
```

包测试可从解包 sdist 执行；资产验收需要完整仓库，缺失输入或空测试集明确失败。
README 和使用指南的基础链、回放及独立辅助示例随契约测试执行。文档移动或示例
修改时，须同步示例定位和源码包内容，保持相同的执行验证。

| 验证层 | 能证明的范围 |
|---|---|
| Python 3.6 语法检查 | 包源码符合目标语法；不能代替旧解释器和旧依赖实跑 |
| 现代环境包测试 | 理论分支、输入边界、API、回放与组合契约在该环境下通过 |
| 旧解释器 / 旧依赖实跑 | 对应环境的运行结果；不能代替平台取数与数据时效验证 |
| wheel / 解包 sdist | 安装导入与源码分发完整性；单独检查产物而非仅从源码导入 |
| 原文与独立真实标注 | 所核验定义、样本和价格版本的证据；不扩大到未覆盖分支 |
| 平台与策略验证 | 调用方环境、取数、调度和研究结论的专项证据 |

CI 定义现代 Python 3.10 / 3.13、Python 3.6 旧依赖及仓库资产验收，并分别检查
wheel 与解包 sdist；某次提交是否通过，以该提交的运行记录为准。仓库历史结果见
[验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)，不把旧测试数量写成当前全量通过结论。

目录和文档职责见 [docs/README.md](https://github.com/lushi78778/chan-lun/blob/main/docs/README.md)。架构、原文核验、开发流程与
工程命令分别维护在 [ARCHITECTURE](https://github.com/lushi78778/chan-lun/blob/main/docs/architecture.md)、[CONTRIBUTING](https://github.com/lushi78778/chan-lun/blob/main/CONTRIBUTING.md)、
[AGENTS](https://github.com/lushi78778/chan-lun/blob/main/AGENTS.md) 与[工具索引](https://github.com/lushi78778/chan-lun/blob/main/tools/README.md)，README 不另维护开发规则或理论进度表。

## 版本与升级

1.x 的公开入口、字段、时间、身份及异常契约见 [API](https://github.com/lushi78778/chan-lun/blob/main/docs/api.md#1x-%E7%89%88%E6%9C%AC%E8%A7%84%E5%88%99)。算法
修正需要固定输入与逐前缀差异证据；输入历史被修订或候选随新证据变化，按对应
输入版本和时间契约解释。升级前保留旧结果，按[迁移指南](https://github.com/lushi78778/chan-lun/blob/main/docs/migration.md)逐项核对。

版本号在 `pyproject.toml` 与 `src/chan/__init__.py` 保持一致。工程治理按变更影响
纳入修订、次或主版本；只有内部维护的提交可暂不发布，已发布产物不覆盖。本地提交、标签、远端推送、CI、GitHub
Release 和 PyPI 分别核验；已有标签保持原指向，新增阶段标签须有明确的交付或
复现价值，推送单独评估。版本事实见 [CHANGELOG](https://github.com/lushi78778/chan-lun/blob/main/CHANGELOG.md)，历史收据保留当时记录。

## 许可证与使用责任

本项目采用 [MIT](https://github.com/lushi78778/chan-lun/blob/main/LICENSE) 许可证。计算结果用于结构研究与辅助分析，不构成投资
建议；交易决策、风控与执行由调用方负责。
