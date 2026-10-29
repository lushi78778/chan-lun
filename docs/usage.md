# 使用指南与模块示例

本页维护详细输入、回放、模块组合与排错。先运行 [README 快速开始](../README.md#快速开始)，
再按实际输入选择入口。基础链的分步示例复用快速开始的 `df`；带“调用模板”的
代码需要调用方先提供所列输入，其余独立示例使用合成数据。合成对象只演示接口，
不证明真实走势类型、级别邻接或数据供应历史。

| 任务 | 位置 |
|---|---|
| 接入自己的行情 | [行情输入契约](#1-行情输入契约) |
| 历史回放与候选修订 | [按观察时点计算](#2-按观察时点计算与追踪修订) |
| 读懂线段的完成与证据 | [线段边界](#3-线段边界与证据时间) |
| 盘中或延迟行情 | [收盘与到达时间](#4-按收盘与到达时间观察) |
| 选择点位口径 | [候选与条件判定](#5-候选与条件判定) |
| 分步组合与辅助模块 | [模块示例](#6-模块与公开入口) |
| 解释无结果或报错 | [证据、身份与排错](#7-证据身份与常见错误) |

字段、原因码、身份与版本稳定性以 [API](api.md) 为准；安装问题见
[安装排错](installation.md)，实现进度只见[正式计划](缠论理论逐一实现计划.md) §6。

## 1. 行情输入契约


### 标准原始 bar

输入为按时间严格递增的 dict 列表或元组，每条至少含六个字段：

```python
bars = [
    {"dt": "2026-01-05", "open": 10.0, "high": 10.8,
     "low": 9.8, "close": 10.5, "volume": 1000.0},
    {"dt": "2026-01-06", "open": 10.5, "high": 11.0,
     "low": 10.2, "close": 10.7, "volume": 1200.0},
]
```

| 字段/条件 | 契约 |
|---|---|
| `dt` | 严格递增、唯一，整段序列使用一致的时间类型与表示 |
| `open/high/low/close` | 有限、严格为正的数值；布尔值不作为价格 |
| 价格包络 | `low <= open/close <= high` |
| `volume` | 有限且非负；单位由调用方统一 |
| 额外字段 | 可存在；批量入口只复制标准 OHLCV 和时间 |
| 空序列 | 合法；批量入口返回空结构，`as_of=None` |

支持 `date/datetime/pandas.Timestamp`；datetime 的 UTC 偏移需保持一致。
字符串可用 `YYYY-MM-DD`，或带秒的 `YYYY-MM-DD HH:MM:SS[.微秒]` /
`YYYY-MM-DDTHH:MM:SS[.微秒]`。同一序列不要混用日期与时间、空格与 T、
不同小数精度或不同类型；字符串形式不支持时区后缀。

```python
from chan import validate_bars

validate_bars(bars)  # 合法时无返回值；坏数据抛出异常
```

`validate_bars` 不排序、不填充、不去重，不静默删除坏行。
错误容器使用 `TypeError`，不符合行情契约的行使用 `ValueError` 并指出位置。
底层算法未统一执行完整校验，直接调用时由调用方保证契约。
正价格限制与当前相对价格力度口径一致；零价、负价资产需要先定义适用口径。

### DataFrame 适配

```python
from chan import normalize_bars, bars_to_df

bars = normalize_bars(
    df, dt_col="date", open_col="open", high_col="high",
    low_col="low", close_col="close", volume_col="volume",
    drop_paused=True,
)
restored_df = bars_to_df(bars)
```

有 `dt_col` 列时取该列，否则取 index；OHLCV 转为 float，并按时间排序。
默认停牌判据是 `volume == 0` 且 `high == low`，满足时剔除。
`normalize_bars` 是格式适配，不代替完整校验；重复时间、NaN 和价格包络
仍须由 `validate_bars` 或 `analyze_bars` 检查。

标的、周期、时区、前复权基准、成交量单位及 bar 是否收盘均由调用方管理。
多标的表须先分组；日线和分钟线分别形成各自的序列。
包含处理后的 `NewBar` 是形态对象，其首开末收可能落在合并形态区间之外，
不要把原始 OHLC 包络校验直接用于它。

## 2. 按观察时点计算与追踪修订


`analyze_at`（0.5.1 起）先筛选原始 `dt<=cutoff` 行情，再计算包含、MACD
和结构。截止值与行情时间使用相同类型、字符串格式和 UTC 偏移。未来
OHLCV 不参与计算；完整时间索引仍须有效且严格递增。返回的 `as_of` 是
最后可见行情时间，可能早于请求截止。行情是否收盘由调用方保证。

```python
from chan import analyze_at, replay_bars

# bars 已按本观察时点可用的复权因子处理, 并且只包含已收盘bar。
cutoff = bars[-1]["dt"]
current = analyze_at(bars, cutoff, bi_standard="106")
for snapshot in replay_bars(bars, observations=[row["dt"] for row in bars[-20:]]):
    for change in snapshot.changes:
        print(change.kind, change.field, change.first_seen, change.observed_dt)
```

`replay_bars` 逐个观察时间独立计算并返回 `ReplaySnapshot`，记录分型、
笔和旧买卖候选的 `appeared/revised/withdrawn`。`first_seen` 仅是当前
观察网格首次出现时间，不能当作理论确认时间。未完成末笔可能被同向
新极值替换；候选撤销保留在账本中。输入历史版本改变时重新建账本。
账本身份适用于固定输入序列，不是跨重采样或数据修订的全局中枢身份。

本入口不复权。若复权因子随观察时点变化，应分别构造各时点的行情前缀
后调用 `analyze_at`，不能拿最终复权行情假定其当时可用。跨周期数据也
须按同一实际观察时间截断。完整样本计算后按结构端点筛选不满足此契约。

## 3. 线段边界与证据时间


`find_xds` 不足三笔返回空列表；首三笔须重叠，不能把一笔当未完成线段。
`XD.complete` 表示给定笔序列下破坏定义成立；`mode` 只区分两种破坏方式。
`evidence_dt/evidence_end_index` 为最后证据笔的端点，不等于实际行情确认时间。
完成段的 `gg/dd` 仅覆盖自身构成笔，后续确认笔另记证据；缺口的第二序列
从假设转折点完整收集，未成立时新极值使旧假设撤销。分界前后不跨界包含。

线段划分与完成时间的历史修正见[迁移指南](migration.md)和
[CHANGELOG](../CHANGELOG.md)。升级前保存旧结果，并在相同前缀上比较。

平端点的完成类型仍能参与递归和中枢形成。自动点位组合通过
`unresolved_move_ids` 显式报告它，当前轮次的有向二/三类判定在首个
平端点前停止，保留此前结果；不会猜方向或删段后拼接。

包测试 `tests/fixtures/xd_originals.json` 用相对价位保留课67/71/81原图不等式，
不声称恢复原图的真实行情。原图完整覆盖仍在正式计划登记。

### 显式线段起点前提（1.2.0）

不传`origin_premise`时，`find_xds(bis)`保持既有工程规则。需要区分
未知前史、明确无前史与给定近期起点时，显式传入起点前提：

```python
# 调用模板：fixed_bis由调用方按当时可见行情生成，并从选定起点截取。
# anchor中的0是本列表的位置；前提从观察到第一笔时已知。
import chan

if len(fixed_bis) >= 3:
    origin = {
        'basis': 'given_recent',
        'anchor': (0, fixed_bis[0].direction, fixed_bis[0].start_value),
        'available_bi': 0,
    }
    conditional_xds = chan.find_xds(fixed_bis, origin_premise=origin)
```

此段是需要调用方提供`fixed_bis`的模板。给定起点须符合首三笔重叠，
接口不会把另一个起点偷偷改作声明的起点；不匹配时明确报错。若前提
在更晚的BI观察点才可知，填入相应`available_bi`，完成项会等待该
观察点。`unknown`表示尚无起点前史证明，`available_bi`须为`None`。

`no_prior_history`要求有独立依据声明输入开始前没有走势，仅可绑定
起笔0；缺少图外数据或选择近期极值不能当作这个事实。条件模式中
前驱待证会保留其身份，不能降成未知前史后放行。局部证明可先发生，
最后证据须包含前提和前驱的累计依赖，不能把早期局部证明当作实际
确认时间。实际行情可用时间仍按逐原始前缀记录；BI端点不替代它。

起点条件不同会改变后续XD、F1、递归与点位上下文，须按同一观察
前缀重新验收。默认调用的旧整窗标签不直接用于条件模式；既有
组合、回放及冻结策略继续使用原有默认参数。

## 4. 按收盘与到达时间观察


`analyze_at` 的 dt 过滤适合调用方已保证全部 bar 收盘的离线前缀。用于
盘中或存在数据延迟时，使用 `analyze_available`，每根原始 bar 增加两个
字段：`closed_dt` 是本周期结束时间，`available_dt` 是本版本行情可用时间。
日期标签、收盘时间和到达时间须满足 `dt <= closed_dt <= available_dt`。
缺字段报错，不会退回日期标签；本库不推断交易日历或供应历史版本。

```python
from datetime import datetime
from chan import analyze_available, replay_available

# dt是交易日标签; 当日日线在15:05才成为这个输入版本的可用数据。
available_bars = [dict(dt=datetime(2026, 7, 31),
                       closed_dt=datetime(2026, 7, 31, 15),
                       available_dt=datetime(2026, 7, 31, 15, 5),
                       open=4.0, high=4.2, low=3.9, close=4.1, volume=1000)]
assert analyze_available(available_bars, datetime(2026, 7, 31, 14)).as_of is None
visible = analyze_available(available_bars, datetime(2026, 7, 31, 15, 5))
for observed in replay_available(available_bars):
    print(observed.observed_dt, observed.result.as_of)
    print([item.to_dict() for item in observed.structures])
```

`replay_available` 独立重算每个实际可用前缀，保留原分型/笔/旧 bs 候选变更，
并记录保守结构链：后继笔出现后固定前笔；只用这些笔确认线段；三个已确认
线段形成线段构造层中枢。末笔和未完成线段不进入保守确认结构。
`StructureObservation.first_seen` 是该观察网格首次确认可见时间，不是端点
或下单时刻；中枢延伸另有修订记录。`structures` 不包含自动一类点上下文，
也不能直接把其中一笔或一条线段转换为 `ConfirmedMove`。
候选 `buy_points/sell_points` 仍采用旧笔级算法，保留其独立近似范围。

调用方必须提前截断传入分钟行情，确认函数不会替调用方统一裁剪所有输入。
取到信号之后的行情可能改变分型确认与末端结构。

## 5. 候选与条件判定


点位接口需要按输入和证据性质分别使用：

### 第一层：笔级简化识别（`bs` 模块）

`find_buy_points`/`find_sell_points` 在笔级结构上运行，输出候选事件：

| 点类型 | 当前识别条件 |
|---|---|
| 一买/一卖 | 下跌/上涨趋势背驰；当前取首个方向匹配的趋势背驰锚点 |
| 二买/二卖 | 一类点后首次回调/反弹，不破对应一类点极值 |
| 三买/三卖 | 离开中枢后首次回抽/反抽守边界，并比较离开与回拉力度 |

三类点回抽恰好触边界可接受。默认力度比较使用保留两位小数的比值
`> 1`；传入 `min_power_ratio=n` 改为 `>= n`。阈值属于工程参数。
信号公共字段为 `type/dt/price/basis/zs_idx`；事件按判定顺序返回，
需要时间排序时由调用方显式排序。

**理论覆盖边界**：这一层是笔级简化，不等同于第 101 课的完整精确定义。
第 101 课允许二买低于一买的弱情形，现有"不破一类点"门槛尚未覆盖；
一类点、实际走势完成和因果级别的自动识别仍需补强，不能只删除旧
价格门槛扩大输出。

### 第二层：已确认输入上的条件判定

这些入口要求你先证明输入（已确认结束的次级走势、当时已知的中枢），
它们只做条件判定，不会把笔级候选自动升级为理论事件：

| 入口 | 判定内容 |
|---|---|
| `find_second_points` | 课53/101 二类点：弱二类点、小转大无本级一类点、因果中枢二三合一 |
| `find_third_points` | 三类点：整个首回试区间守 ZG/ZD（触沿允许），同一中枢只输出第一个成立点 |
| `find_first_points` | 课24 MACD 辅助一类候选（不是严格背驰证明） |
| `scan_first_points` | 无候选时的第一项否决诊断，可复核 |
| `confirm_level_up` | 已确认走势类型逐证据到达递归 |
| `analyze_point_chain` | 点位组合链：引发中枢三类点驱动第108课底/顶构造 |
| `formation_state` | 同级同因果中枢首次三类点结束的底/顶构造状态 |
| `fractal_range_state` | 第108课分型区间辅助构造状态（与 `formation_state` 分别命名，不能互换） |

调用示例见[§6](#6-模块与公开入口)。

## 6. 模块与公开入口


公开函数和结果类可直接 `from chan import ...`，也可从所属模块导入。
完整导出清单是 `chan.__all__`；以下按用途列出主要入口，阈值和边界细节
见函数 docstring 与模块测试。

### 6.1 基础识别链：分型、笔、线段、中枢

对快速开始的同一个 `df`，可分步运行：

```python
from chan import (
    normalize_bars, validate_bars, chan_fx_bi, find_xds, find_zs,
    classify_trend, macd_series, find_trend_bc, find_pan_bc,
    find_buy_points, find_sell_points,
)

# 1. 行情 DataFrame -> 标准 bar 列表
bars = normalize_bars(df)
validate_bars(bars)
new_bars, fxs, bis = chan_fx_bi(bars)
xds = find_xds(bis)
zss = find_zs(bis)
segment_zss = find_zs(xds)
trends = classify_trend(zss)
dif, dea, hist = macd_series(bars)
trend_bc = find_trend_bc(bis, zss, bars, hist=hist)
pan_bc = find_pan_bc(bis, zss, bars, hist=hist)
buys = find_buy_points(bis, zss, trend_bc)
sells = find_sell_points(bis, zss, trend_bc)
```

| 模块 | 入口/对象 | 用法与边界 |
|---|---|---|
| `bars` | `BAR_KEYS`、`normalize_bars`、`bars_to_df`、`validate_bars` | 原始行情适配与校验 |
| `analysis` | `analyze_bars`、`AnalysisResult` | 基础链批量组合 |
| `fx` | `remove_includes`、`find_fxs`、`NewBar`、`FX` | 先按顺序处理包含，再识别三 K 分型 |
| `bi` | `find_bis`、`chan_fx_bi`、`BI` | 分步或一次返回 `(new_bars, fxs, bis)` |
| `xd` | `find_xds`、`chan_bis_xds`、`XD` | 特征序列识别线段，支持第一种情况及缺口确认 |
| `zs` | `find_zs`、`track_zs`、`ZS`、`ZsEvent` | 返回中枢，或 `(zss, events)` 事件流 |
| `zs` | `zs_relation`、`build_expanded_zs`、`classify_trend` | 中枢关系、扩展构造与走势粗分类 |

默认成笔标准是 81 课：`MIN_K_GAP=3`，两个分型中心在无包含序列的
下标差至少为 4。标准名可用常量 `BI_STANDARD_81`/`BI_STANDARD_106`
（值 `'81'`/`'106'`，见 [API](api.md) §6）。显式选择 106 课
标准：

```python
from chan import analyze_bars, chan_fx_bi

new_bars_106, fxs_106, bis_106 = chan_fx_bi(bars, standard="106")
result_106 = analyze_bars(bars, bi_standard="106")
```

106 课要求两个完整三 K 分型至少六个无包含 K 线单位，中心端点区间触及
方向相应的原始 MA5；默认间隔为 2。直接调用 `find_bis(..., standard="106",
ma5=...)` 时，MA5 必须按每个包含组最后原始下标对齐。
`min_k_gap` 可另设间隔，但不能取消 106 课六 K 单位等条件。

`ZS.zd/zg` 为中枢边界，`gg/dd` 为构成波动的最高/最低点；另有
`start_dt/end_dt/direction/xd_count/extended_9`。
`classify_trend` 分组保留 `zs_list`，顶层 `zd/zg` 是组内首个中枢。
`track_zs` 事件反映形成、延伸、九段升级、完成与新生，其事件 `dt`
仍取源单元端点，不自动提供实际确认时间。

边界约定因概念而异：`zs` 的初始三段要求 `ZD < ZG`；同级分解和
递归使用闭区间交集，`ZD == ZG` 可计为交集。不要跨模块抹平这些差异。

### 6.2 背驰与买卖点

| 模块 | 入口 | 内容 |
|---|---|---|
| `bc` | `ema`、`macd_series`、`segment_area` | EMA、MACD 与段内柱面积 |
| `bc` | `find_trend_bc`、`find_pan_bc` | 趋势/盘整背驰候选，可复用 `hist` |
| `bs` | `find_buy_points`、`find_sell_points` | 第一、二、三类事件 |

MACD 返回 `(dif, dea, hist)`，`hist = 2 * (dif - dea)`。
趋势背驰使用相应趋势与创新极值条件下的柱面积比较；盘整背驰另有位置
过滤参数 `max_dev=0.15`。这些是当前量化识别口径。

不传 `trend_bc` 时只识别第三类。三类点另有
`power_ratio/zs_zd/zs_zg/pull_start_dt/pull_end_dt/pull_start/pull_end`；
二买有 `b1_price`，二卖有 `s1_price`。`zs_idx` 是本次列表的局部索引，
不能用作长期中枢身份。

理论覆盖边界与两层口径的区别见[§5](#5-候选与条件判定)；
`second` 提供已确认次级走势及上下文的独立条件入口（下节）。

### 6.3 已确认次级走势的二类点

`find_second_points` 是课53/101 的条件判定入口，独立于旧 `find_buy_points`
和 `find_sell_points`。它接收已经确认结束的次级走势，允许二买低于一买，
支持小转大没有本级一类点的上下文，并可识别给定因果中枢的二三合一。
每个反转独立使用稳定 `context_id`，只取第一次反弹和紧接的第一次回试。

```python
from chan import ConfirmedMove, SecondPointContext, find_second_points

# 条件输入示例：调用方已确认这两个次级走势，以及本级一买上下文。
# 这些对象不是由任意两笔自动转换而来。
moves = [
    ConfirmedMove("rise", "sub", "up", "2026-01-01", "2026-01-03",
                  10, 15, 10, 15, "2026-01-04"),
    ConfirmedMove("pull", "sub", "down", "2026-01-03", "2026-01-05",
                  15, 9, 9, 15, "2026-01-06"),
]
context = SecondPointContext("cycle-A", "buy", "main", "sub",
                             "2026-01-01", 10, "2026-01-02")
assert find_second_points(moves, [context], "2026-01-05") == []
point = find_second_points(moves, [context], "2026-01-06")[0]
assert point.strength == "weak"
assert point.dt == "2026-01-05"          # 回试端点
assert point.confirmed_dt == "2026-01-06"  # 可用时间
```

| 输入 | 契约 |
|---|---|
| `ConfirmedMove` | 次级走势的稳定身份、级别、方向、端点价、全程极值及实际确认时间；未完成尾部不输入 |
| `SecondPointContext` | 一类点或小转大反转锚点、目标/次级级别及上下文确认时间；`ended_dt` 是本次中阴结束的确认时间 |
| `centers` | 可选 `context_id -> ConfirmedCenter`，须为反转前已形成的同级因果中枢；缺省不判最强合一 |
| `ConfirmedDivergence` | 小转大回试创新极值分支所需的盘整背驰证据，按走势身份、级别、方向关联 |

输出 `SecondPoint` 保留端点及最晚必要证据的确认时间。原中枢向上首次
离开后回试全程低点不破 ZG 可标 `also_third=True`，卖点镜像；无额外
力度比门槛。后续中阴结束不会删除此前成立的二类点，但结束后才确认
的点被排除。小转大回试创新低/高时须有当时已确认的盘整背驰证据。

本条件入口不自动识别一类点、走势完成、级别邻接或因果中枢；自动 MACD
辅助接线见[§6.13](#613-macd-辅助一类候选与因果点位链)。它也不将旧
笔级候选直接升级为精确点。调用方需用当时前缀/存档确定这些输入；
严禁用全样本 `complete=True` 给历史端点倒填确认时间。

既有 R2 二类表的固定笔/完成 XD 角色及价量条件，不能直接代入本接口。
按原窗口和既定最低 F1 规则聚合后，旧锚点可能位于完整 F1 内部，旧
反弹/回试也可能只覆盖其中一部分；内部极值还可能不等于腿起点价。
不得为了沿用旧点位剪断 F1、移动锚点或猜内部极值的精确发生时刻。
本接口的真实接线仍需锚点起始的相邻完整走势及上游一类/小转大证据；
旧标签与当前合同的逐项差异见
[仓库验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)。

### 6.4 已确认次级走势的三类点

`find_third_points` 与 `find_second_points` 共用 `ConfirmedMove` 输入契约，
但独立返回三类点。只消费真实完成的次级走势与当时已知中枢；不会将
笔级候选直接升级为理论事件。整个首回试区间必须守 ZG/ZD，触沿允许，
不加旧笔级算法的力度比门槛。同一中枢只输出第一个成立的三类点。

```python
from chan import ConfirmedMove, ConfirmedCenter, ThirdPointContext, find_third_points
third_moves = [
    ConfirmedMove("leave", "sub", "up", "2026-01-02", "2026-01-04",
                  11, 14, 11, 14, "2026-01-05"),
    ConfirmedMove("return", "sub", "down", "2026-01-04", "2026-01-06",
                  14, 12, 12, 14, "2026-01-07"),
]
third_context = ThirdPointContext("cycle", "main", "sub",
    ConfirmedCenter("center", "main", 10, 12, "2026-01-01"))
assert find_third_points(third_moves, [third_context], "2026-01-06") == []
third_points = find_third_points(third_moves, [third_context], "2026-01-07")
assert third_points[0].kind == "buy3"
assert third_points[0].confirmed_dt == "2026-01-07"
```

输入须包含从该中枢形成起的完整后续走势，不能截掉首回试后把第二次
回试冒充首次。保守口径要求中枢在离开起点前已确认可见；更晚才确认的
中枢不会追认历史离开。次级走势的完成、级别邻接、因果中枢仍由调用方
证明；当前尚不是从 K 线自动识别全部三类点的引擎。

仓库真实回归已用三组固定原始窗口逐前缀构造完整 F1，再转三类点输入：
六个声明中枢中，分别有买侧、卖侧条件样本，也保留缺首回试和时序不符
的空结果。中枢可知时间取首三个完整 F1 的最晚确认，不能回填到第三段
端点；三类点确认取回试完成证据到达，不取价格端点。该回归采用明示的
最低 F1-bi 规则与 F2/F1 邻接，不把原始周期命名为理论级别，也不提供
上游严格一类或二三合一证明；范围和独立算术见
[仓库验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)。

完成 XD 路径另复用五个原窗，按 `track_center_lineage` 的 formed 事件取
形成快照，转换为 `ConfirmedCenter` 后接三类上下文。完整类型及进入方向
保留给谱系；三类输入通过 `to_confirmed_move` 使用净端点方向、全程范围
和实际确认时刻。后续 extended 版本沿用中枢身份和核心，接线仍使用形成
时刻。真实回归保留七个中枢，含两处三买、一处首次回试破沿后重新离开
再成立，以及仍缺首回试的情况。中枢形成及三类条件可早于 F2 类型完成；
上述条件没有增加上游一类或底顶完成证明。

### 6.5 完成走势类型的递归确认

`confirm_level_up` 只接受已确认的 `ConfirmedMove` 或完整的
`ConfirmedMoveType`，按实际确认时间逐批重算可见前缀。调用方按明确 f1
规则冻结的最低层完整类型也可用后者表示，保留类型、中枢和进入方向。
它沿用允许中枢延伸的 `level_up` 规则，输出已完成走势，未完成尾部和
无中枢残段不输出。输入须同级、同一冻结价格版本，时间及端点价格连续；
乱序确认或缺段报错。原始笔、线段、裸 `MoveType.complete` 不带这些
证明，不能直接输入。

真实完成 XD 路径的接线回归复用五条已独立标注的原始序列，先按无延伸
最低规则形成完整 F1，再按允许延伸的规则递归 F2。588000 的 30m 样本
在 2024-11-11 10:01 才确认端点位于 2024-08-09 的盘整 F2；后继 F1
只供完成证明，其更高价格不并入前一 F2 的全程范围。512880 的 5m
样本另核三条后继 XD 同批形成反向中枢的 F1 完成路径，不逐条虚构到达。
输入合同、确认约定及其余开放尾部见
[仓库验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)。
F1/F2 在这里是声明的相邻层级；30m/5m 是原始行情频率，严格趋势及底顶
构造的理论证明仍需各自证据。

下面只演示调用方已经确认的最低层类型序列；合成端点不构成最低层识别器。

```python
from datetime import datetime, timedelta
from chan import (ConfirmedCenter, ConfirmedMove, SecondPointContext,
                  ThirdPointContext, confirm_level_up, find_second_points,
                  find_third_points)
completion_prices = [10, 14, 11, 15, 13, 18, 16, 20, 14, 18, 12, 11, 13, 19]
t0 = datetime(2026, 1, 1)
completion_units = [
    ConfirmedMove("u%d" % i, "base", "up" if b > a else "down",
                  t0 + timedelta(days=i), t0 + timedelta(days=i+1),
                  a, b, min(a, b), max(a, b), t0 + timedelta(days=i+2))
    for i, (a, b) in enumerate(zip(completion_prices, completion_prices[1:]))
]
assert confirm_level_up(completion_units, t0 + timedelta(days=8), "L1") == []
completion_result = confirm_level_up(completion_units, t0 + timedelta(days=9), "L1")
assert completion_result[0].end_dt == t0 + timedelta(days=7)
assert completion_result[0].confirmed_dt == t0 + timedelta(days=9)
assert len(completion_result[0].unit_ids) == 7
assert len(completion_result[0].evidence_ids) == 8
next_result = confirm_level_up(completion_result, t0 + timedelta(days=9), "L2")
assert next_result == []  # 单个已完成类型不足以形成上一级中枢。
point_move = completion_result[0].to_confirmed_move()
assert point_move.direction == "up"

# 原一类锚点与原中枢由调用方显式声明，转换本身不生成这些证明。
point_types = confirm_level_up(completion_units, t0 + timedelta(days=14), "L1")
point_moves = [item.to_confirmed_move() for item in point_types]
original_center = ConfirmedCenter("original", "main", 10, 11, t0 - timedelta(days=1))
second_context = SecondPointContext("cycle", "buy", "main", "L1", t0, 10, t0)
third_context = ThirdPointContext("cycle", "main", "L1", original_center)
assert find_second_points(point_moves, [second_context], t0 + timedelta(days=13)) == []
assert find_third_points(point_moves, [third_context], t0 + timedelta(days=13)) == []
second_points = find_second_points(point_moves, [second_context], t0 + timedelta(days=14),
                                   centers={"cycle": original_center})
third_points = find_third_points(point_moves, [third_context], t0 + timedelta(days=14))
assert second_points[0].also_third and third_points[0].kind == "buy3"
assert second_points[0].dt == third_points[0].dt == t0 + timedelta(days=12)
assert second_points[0].confirmed_dt == third_points[0].confirmed_dt == t0 + timedelta(days=14)
```

`unit_ids` 是组成单元，`evidence_ids` 是首次完成时的全部可见次级前缀，
包含可能位于端点之后的完成证据。`confirmed_dt` 取该批证据到达时间，
不能改成端点日或只取组成单元的最晚确认；较晚才调用也保留较早证据时间。
输出无可变嵌套，既有完成结果不随输入增长改变。各次调用须使用同一身份、
坐标和输入版本；供应修订要另存版本，本入口不存历史行情。

`direction` 是原 f2 进入方向，可为 `None`；`to_confirmed_move()` 以端点
净涨跌表示二/三类点所需的整体回抽方向，保留确认时间和全程极值。
平端点盘整显式报错，不能跳过后拼接两侧走势；它仍可参与结构递归。
转换不生成一类点、背驰、反转上下文或因果中枢。级别名由递归相邻关系
声明；继续递归时保留完整 `ConfirmedMoveType`，不要转换后丢失类型及
进入方向。级别不对应固定分钟时长。

上述回试类型端点为 13、全程低点为 11，原中枢 ZG=11，属于给定上下文下
触沿的二三合一。若只将原中枢 ZG 改为 12，端点仍守沿，但全程低点破沿，
二类条件保留而不再合一，三类不成立；不能在转换时用端点价格代替全程极值。
回试类型需要组成之外的 u12 完成证明，故端点为 t0+12 天、确认为 t0+14 天；
证明迟到时二/三类均继续等待，同批证明整批进入。二类的 ended_dt 也与
实际确认时间比较，同刻允许，三类判定独立。示例及镜像只验证工程接线，
不构成独立真实标签或上游一类点证明。

### 6.6 同级分解、级别递归与状态

```python
from chan import same_level_decompose, level_up, decompose_levels, level_reading

moves = same_level_decompose(bis)
higher_moves = level_up(moves)
levels = decompose_levels(bis, max_levels=8)
reading = level_reading(levels, at_dt=bars[-1]["dt"]) if bars else []
```

| 模块 | 主要入口 | 内容与解释 |
|---|---|---|
| `decompose` | `MoveType`、`same_level_decompose` | 固定三段中枢的同级分解；不把中枢延伸混入切分 |
| `recurse` | `level_up` | 次级单元递归聚合，处理延伸与更高级别结构 |
| `completion` | `ConfirmedMoveType`、`confirm_level_up` | 已确认类型逐到达前缀递归，冻结组成、中枢、完成证据与确认时刻 |
| `levels` | `LevelDecomposition`、`decompose_levels`、`level_reading`、`change_starts_low` | 多级分解、指定端点时间读数、上下级方向改变自洽性 |
| `zhongyin` | `ZhongYinResult`、`track_zhongyin` | 中阴阶段：进入、中枢形成及结束状态 |
| `zhongyin` | `boll_bands`、`boll_state`、`boll_events`、`boll_bs1_hints` | BOLL 辅助事件与一类点提示 |
| `osc` | `OscReport`、`oscillation_monitor`、`osc_strength`、`zn_next_estimate` | 中枢震荡统计、力度及数值估计 |
| `biaoli` | `bi_state`、`bi_transition_valid`、`disease_stage`、`followup_quality`、`zhongyin_health` | 笔四状态、合法迁移、双级状态与震荡强弱 |

同级分解与递归是不同规则，不能互相替换。`MoveType.complete=False`
表示尾部尚未完成，`kind='incomplete'` 表示没有形成完整走势类别，
两种标记不能混为一谈。

**类型口径**：`same_level_decompose` 和 `level_up` 的 `kind='up'/'down'`
表示各自切分规则中的中枢核心 ZD/ZG 同向移位；`complete=True` 表示
当前输入的后继结束结构已具备。这两个字段不独立证明课 20 严格趋势
或背驰。`zs_relation` 另比较完整波动 DD/GG，两种口径不可混用。
上例是区间结构计算；严格链还须声明最低完整 F1 规则，逐原始前缀取得
后继证明的实际确认，再构造 `ConfirmedMoveType` 供相邻 F2 递归。
裸笔/线段或未完成 `MoveType` 不能仅改名后充当这一输入。

现有 81 两窗在固定笔无延伸 F1 规则下，各形成 3 / 5 个完成类型；
原 R2 的 c 笔均在当时未完成的 F1 内。该窗口的 F2 仍未完成，严格
接口只登记 `skipped/not_two_separated_centers`，不能由辅助点名反推
严格一类点。独立切点和确认表见
[仓库验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)，
逐前缀检查复用 `tests/test_real_f1_originals.py`，只覆盖该声明规则。

`decompose_levels` 第 1 级保留输入单元，以后逐级上推；序号不自动对应
1 分钟/5 分钟/日线等时间周期。`level_reading` 按起止端点的闭区间读数，
历史可见性仍要先做前缀计算。

震荡监视器的 `center` 是 `(zd, zg)`，单元需有价格区间与方向属性。
BOLL 阈值和震荡估计都是辅助口径，BOLL 提示不等同于 `bs` 的确认事件。
双级"病情"和"健康"标签相对原走势方向解释，不自动映射为开平仓动作。

### 6.7 力度、转折和均线吻

| 模块 | 主要入口 | 输入/输出职责 |
|---|---|---|
| `strength` | `sma_series`、`ma_areas`、`MaArea`、`find_ma_bc`、`avg_strength_state`、`MaStrengthState` | 两条均线差值面积、同向力度比较、形成中的平均力度 |
| `turn` | `classify_bc_turn`、`guaranteed_rebound_gap` | 背驰后转折三分类与回拉幅度条件 |
| `minor_turn` | `classify_minor_turn` | 小级别背驰引发大级别转折的阶段分类 |
| `kiss` | `alignment_series`、`classify_kiss`、`find_kisses`、`KissEvent` | 两均线体位与飞吻/唇吻/湿吻，保留吻次序和量能原料 |
| `gap` | `Gap`、`find_gaps`、`classify_gap` | 原始 K 线缺口与基于可见后续行情的力度分类 |

`strength` 的短长均线等长，`sma_series` 暖机段为 None；输入价格需完整。
1.1.0 的 SMA 按数值 `str(value)` 的十进制表示精确求和、除以周期，最后
一次转回 float；内部用 Fraction 前缀累计，不受调用方 Decimal 精度设置影响。
仅使用 `math.fsum` 仍可能让十进制相等均值出现尾差。修正可能改变根数、
平均力度和依赖 SMA 的确认边界，升级须按同一输入逐前缀核对；
不增加近零屏蔽阈值。缺值、非有限、溢出及不能按数值解析的对象沿用既有
求和路径，数值字符串仍不作为价格输入。

**报价单位与计算精度**：核对 2026 年修订交易规则（2026-07-06 施行），
[上交所 §3.3.11、§3.3.17](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml)
和[深交所 §3.3.11、§3.3.19](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf)
的一般申报单位分别为 A 股 0.01 元、基金 0.001 元；所引舍入条款适用于
涨跌幅限制价格和有效申报价格范围。具体品种、日期及特别规定须由应用层
核对，不据此重写历史行情。由这些报价计算的均线可有更细精度：十根基金
收盘九根 1.000、一根 1.001，SMA5/10 分别为 1.0002/1.0001；强行保留
三位会把有效差值抹掉。因此核心库不推断标的档位，不将均线或复权价格
量化到交易报价单位；委托与限制价计算由策略层负责。输出仍为 float，
不恢复输入已丢失的小数，也不保证低于 float 分辨率的差异可见。
`find_ma_bc` 比较已闭合的同向均线面积，`use_avg=True` 使用平均力度。
`avg_strength_state` 可描述形成中的面积，不应作为已完成背驰替代品。
从 1.0.2 起，暖机后的缺值使尾段保持未封闭，即时状态返回 None；
不跨缺口拼接面积与均线距离，缺口前实际确认的历史候选仍保留。

`find_kisses(short, long, volumes=None, proximity=0.5, min_depth=0.2,
flip_confirm=0.5)` 返回吻事件。`alignment_series` 的 `up/down` 分别表示
短线在长线上方/下方；触零也算湿吻。三个默认比例是对定性描述的量化，
吻本身不自动生成买卖点。均线第一类候选另需价格趋势与力度证据，
第二类采用体位转化后的首次中继条件，不额外要求另一轮背驰。

`alignment_series` 表示每根均线的即时上下关系；`KissEvent.direction`
表示该吻开始时的宿主体位。差值已穿零但反向行程尚未达到 `flip_confirm`
门槛时，逐棒体位可以改变，转化仍待确认，返回的开放吻仍属于原宿主；
回撤过浅时可能还不返回开放吻。不能用一次上穿直接重置吻次序。
力度的 `MaArea` 按触零/穿零分段，不跟随吻宿主分段。
即时平均力度使用最近的同向面积，不跳过短小段选更早、更有利的参照；
`stretch_shortening=True` 也不能替代 `forming_weak` 或其他组合条件。

体位转化门槛在每根回撤上检查，首根回撤也不例外。例如差值由 1 直接
变为 -0.5，默认门槛已经满足，该根即产生 `open=False/resumed=False`
的湿吻；后续反弹不能把这个闭合事件改记为中继。1.1.0 修复了原实现
跳过首根检查造成的延迟；新体位前腿从实际转化根起算，吻时间、前腿涨幅/
均量及依赖这些字段的候选可能修正，比例阈值和字段含义保持。

课12茅台原图的局部报价可复核，但不意味着默认量化已复现原文点位。
以复牌日 2006-05-25 至 11-30 的 131 根原价日线、窗内 SMA5/10 及默认
吻参数回放，面积/平均力度两模式均未输出候选；08-07、09-14 的即时
状态也均为 no_warning。该窗的起点、前腿和吻计数是显式输入边界，不按
原文箭头调参或回填确认日。课12发表于 12-01 中午，当时观察不能使用
当日收盘；原图数值、独立算术及差异见
[仓库验收索引](https://github.com/lushi78778/chan-lun/blob/main/validation/README.md)。

`classify_bc_turn` 接收原中枢、后续回拉、原趋势方向；`classify_minor_turn`
还可接收次级中枢和三类点信息。分类保留必要条件与充分证据的区别。
缺口最终如何回补依赖后续输入；回放时只能使用当时已知行情。

### 6.8 固定两级与任意多级区间套

```python
from chan import confirm_buy3_event_30m

# 以下变量由调用方提供：evt 为三买事件，bars30 为截止目标观察时刻的30m行情
# result30 = confirm_buy3_event_30m(evt, bars30, stale_days=3,
#                                 min_prev_swing_ratio=0.002)
```

| 入口 | 作用 |
|---|---|
| `find_run_exhaustion` | 指定方向运行段的内部力度衰减 |
| `confirm_buy3_30m`、`confirm_sell3_30m` | 三买/三卖回拉内部背驰与中枢边界确认 |
| `confirm_buy3_event_30m`、`confirm_sell3_event_30m` | 接收 `bs` 事件，自动取边界与 `pull_end_dt`，缺失时取 `dt` |
| `confirm_buy2_30m` | 30m 底分型及一买价格守位的轻量确认 |
| `nested_bc`、`BcNestInput`、`BcNestLevel`、`NestBcState` | 任意多级候选段嵌套与力度判定 |

固定 30m 确认使用段首末 DIF 摆动，端点各顺延两根 K 线吸收 EMA 惯性；
MACD 柱面积只作参考。常见返回状态为 `confirmed/weak/no_exhaustion/broke/
stale/no_data`；找不到相应运行段时也可能出现 `none`。
`note` 给出解释，其他字段按判定路径提供，不能假定每次都有完整力度数据。

库默认 `stale_days=1`（自然日）；历史研究脚本可能明确采用 3。
`min_prev_swing_ratio` 默认为 None；设值后要求对照力度达到最低规模。
三买 `zg_tol`、三卖 `zd_tol` 是保留参数，目前不影响判定；实际弱确认
容忍由 `weak_tol` 控制。二买采用 `pierce_tol`，不套用三买的离开段逻辑。

任意多级 `nested_bc(inputs, strength_fn=None)` 从大级别到小级别接收
候选段链；默认力度为 MACD 柱面积，也可注入 `strength_fn(bars, move)`。
区间不嵌套、未创新极值或力度未衰减等都会使链断开；结果 `complete`
表示给定证据链成立。`BcNestInput.center` 仅用于记录，中枢因果关系和
趋势前提需要调用方核对。

### 6.9 分型力度、均线突破与 MACD 防狼

| 模块 | 入口/对象 | 结果 |
|---|---|---|
| `fxpower` | `classify_fx_power`、`classify_fx`、`FxPowerResult` | 三K形态 `weak/neutral/strong/severe` 及包含标签 |
| `fxpower` | `ma_break_state`、`MaBreakState` | 收盘相对均线的 `none/testing/effective` 历史确认 |
| `macd_guard` | `macd_below_zero`、`macd_guard_series` | DIF 与 DEA 都严格小于零为 True，有效其他值为 False，缺测为 None |

`classify_fx_power(b1, b2, b3, direction='top', long_body=0.35,
small_body=0.15, shadow=0.25)` 假定三 K 分型已由调用方确定；底分型镜像。
三个比例是形态量化阈值，不是原文给出的通用数值。
`classify_fx(fx, new_bars)` 是已有分型对象的便捷入口；NewBar 实体是
包含组首开末收的近似，精细原始形态分析优先使用原始 K 线。

`ma_break_state(closes, mas, direction, confirm=2)` 的观察序列从分型
右邻之后开始；均线先在完整历史上计算再对齐截取。有效突破需连续指定
根数的收盘严格越线，缺测中断连续计数。一旦有效，后续回归不会取消
历史有效记录；有效前的恢复可表现为假突破。

```python
from chan import macd_below_zero, macd_guard_series

assert macd_below_zero(-0.2, -0.1) is True
assert macd_below_zero(0.0, -0.1) is False
assert macd_guard_series([-0.2, None], [-0.1, -0.1]) == [True, None]
```

触零或跨轴只说明负区判据不成立，不等于重新站稳，也不自动产生买入许可。

### 6.10 底部与顶部构造

```python
from chan import FormationEvent, formation_state

# confirmed_dt 来自逐前缀识别或当时存档，不是全样本结构端点
first = FormationEvent("buy1", "2026-01-05", "day")
events = [FormationEvent("buy3", "2026-01-12", "day", "center-A")]
state = formation_state(first, "center-A", events, as_of="2026-01-10")
assert state.in_formation
assert formation_state(first, "center-A", events, "2026-01-12").phase == "completed"
```

`FormationEvent(kind, confirmed_dt, level, center_id=None)` 支持
`buy1/sell1/buy3/sell3`，`level` 为非空级别名；三类点需要稳定的中枢身份。
一类点尚不可见时等待，可见后进入构造。同级、同因果中枢的首次三类点
结束该轮构造：底部由三买完成、三卖失败，顶部镜像。

函数只消费 `as_of` 之前实际确认的事件；未来事件不参与当前判定。
终态保持，同一确认时刻的相冲突三类事件需先去重或消歧，否则拒绝判定。
一类点与因果中枢的关联由调用方提供；分型箱体的粗略底部定义不混入
这个事件构造状态。结果类为 `FormationState`。

`completed` 只表示已给一类事件和因果中枢前提下的构造完成，不回头证明
上游一类点真实成立。历史R2底顶fixture的笔级四格是该输入条件下的事件
算术；六个旧锚点均处于尚未完成的最低F1内部，不能直接沿用为当前完整
F1/F2自动链正例。当前输入层次与补证边界见[正式计划§12.3](缠论理论逐一实现计划.md#123-七项部分能力的处理边界)。

### 6.11 分型区间的底部／顶部构造（第108课）

`fractal_range_state` 消费已确认并冻结的 `ConfirmedFractalRange`，返回
`waiting / constructing / testing / completed / failed`。底部盘中严格跌破
区间最低点即失败；连续 `confirm` 根收盘严格高于上沿则成功，顶部镜像。
默认 `confirm=2` 是"有效站住"的工程约定，原文没有规定次数。触沿不算破位，
也不计成功次数；未确认的收盘越沿被收回后重新计数。首次终态冻结，后续反向
价格不改写旧构造；新分型另建区间。这是辅助状态，不返回买卖信号或成笔证明。

```python
from datetime import datetime, timedelta
from chan import ConfirmedFractalRange, fractal_range_state
fractal_box = ConfirmedFractalRange("bottom", datetime(2026, 7, 1), 10, 12,
                                    datetime(2026, 7, 2, 15, 5), "day")
range_bars = []
for day, close in [(3, 13), (4, 14)]:
    dt = datetime(2026, 7, day)
    range_bars.append(dict(dt=dt, open=close, high=close+1, low=11,
                           close=close, volume=100,
                           closed_dt=dt+timedelta(hours=15),
                           available_dt=dt+timedelta(hours=15, minutes=5)))
assert fractal_range_state(fractal_box, range_bars,
                           datetime(2026, 7, 3, 15, 5)).phase == "testing"
range_state = fractal_range_state(fractal_box, range_bars,
                                  datetime(2026, 7, 4, 15, 5))
assert range_state.phase == "completed"
assert range_state.end_dt == datetime(2026, 7, 4, 15, 5)
```

区间可取当时 `FX.low / FX.high` 的三根包含处理后 K 线总范围，调用方应明确
选取方式并冻结价格版本，不能从完整历史挑选最终分型回填过去。分型中间
K 线的 `dt` 不是确认时间。确认时间由当时观察或存档提供；保守做法为右邻
合并组被后续无包含 K 线固定后再登记。该入口不自动判断月线分型已形成。

后续行情必须同标的、同周期、同价格基准，携带收盘/到达时间；在分型确认
之前已闭合的行不计入其后构造。状态入口要求可见行的到达时间非降序，
乱序交付或历史修订须由调用方先形成对应版本快照。价格依据所选观察日
可得因子，不使用最新复权箱体配旧行情。这里的分型区间与 `formation_state`
使用一类点及因果中枢的事件构造定义分别命名，不能互换。

### 6.12 均线版辅助候选（第11、12、15课）

`find_ma_points` 从实际已到达的原始行情计算 SMA、吻和封闭面积，返回
`ma_buy1_candidate / ma_sell1_candidate / ma_buy2_candidate / ma_sell2_candidate`。
这些名称与中枢版点位分开；结果不保证反转，也不直接用于下单。

- `post_kiss_divergence`：第二次及以后已完成吻（飞吻、唇吻、湿吻均可）后的同向面积衰减，
  同时本段价格高点和低点均顺趋势移动。封闭面积取下一根相交行情到达时确认，
  不能按面积末端提前使用。`last_kiss_proven=False`，不回看未来挑最后一次。
- `first_continuation`：已经观察到体位转化之后的首次已完成同体位中继；
  接受飞吻、唇吻和湿吻，不要求先出现本模块的一类候选。窗口直接始于某体位
  而没有转化证据时不声称"第一次"。默认前腿涨跌强度至少 2%，前腿均量不超过
  此前长均线周期均量的 2 倍；可配置，`max_volume_ratio=None` 明确关闭量能过滤。

原文未规定吻的数值边界、前腿强度和放量阈值；本接口沿用 `find_kisses`
的量化参数并保留调整入口。第一类为保守封闭面积法，不覆盖飞吻／唇吻后的
全部背驰或尚未结束的即时预警；底层力度见 `avg_strength_state`，组合见下文。
价格趋势采用
同向面积腿的高低区间近似，不宣称已经完成精确走势类型划分。

`use_avg=False` 比较完整面积，`True` 比较面积除以根数，选项显式区分量纲。
真实输入中两种结果可以相反：159915 的 60m 样本两段面积 0.1012→0.0794，
根数 8→6，总面积减弱，但平均值约 0.01265→0.01323，并未减弱；512880
的 5m 样本面积 0.0288→0.0319、根数 11→17，总面积增加而平均值减弱。
这些是已封闭区间的工程算术，不把一种模式的候选改称另一种也通过。
对应原始窗口和独立区间表复用 `tests/test_ma_points.py` 的真实行情检查。

`avg_strength_state` 的 `forming_weak` 与 `stretch_shortening` 是当下状态，
随未封闭面积增长可以撤销，不能按已确认历史候选永久累计。仅有距离缩短，
不能代替平均力度减弱；预警不提前输出 `find_ma_points` 的稳妥候选，也不
保证最低/最高价已形成。即时状态的面积与平均值带方向符号，强弱比较采用
绝对值；`find_ma_points` 的两个 strength 字段记录绝对强度。

```python
from datetime import datetime, timedelta
from chan import find_ma_points
# 1/2周期仅为易核对的演示，实际参数按所研究周期选择。
ma_point_bars = []
closes = [500.0]
for diff in [-10, -8, 1, -11, -10, 1, -12, -1, 0]:
    closes.append(closes[-1] + 2*diff)
for i, close in enumerate(closes):
    dt = datetime(2026, 1, 1) + timedelta(days=i)
    ma_point_bars.append(dict(dt=dt, open=close, close=close,
                              high=close+1, low=close-1, volume=1,
                              closed_dt=dt+timedelta(hours=15),
                              available_dt=dt+timedelta(hours=15, minutes=5)))
ma_candidates = find_ma_points(ma_point_bars, datetime(2026, 1, 10, 15, 5),
                                short_period=1, long_period=2)
assert ma_candidates[0].kind == "ma_buy1_candidate"
assert ma_candidates[0].dt == datetime(2026, 1, 9)
assert ma_candidates[0].confirmed_dt == datetime(2026, 1, 10, 15, 5)
assert ma_candidates[0].to_dict()["last_kiss_proven"] is False
```

`dt / price` 是证据区间内最早的最低／最高点，`confirmed_dt` 是所需证据的
实际到达时刻，两者不同。只截断当时已关闭并已到达的行情，再计算均线；
调用方负责同标的、同周期、同价格基准及供应历史版本，到达时间非降序。
`find_ma_points` 与 `ma_point_state` 均要求可见行是所给输入的连续前缀。
末尾行情尚未到达时照常使用此前前缀；首行或内部行未到、后面已有可见行
则抛 `ValueError`，不能跳行后把新坐标当作同一历史。1.1.0 修复了过滤迟到
行后绕过到达顺序检查的问题。调用方须显式重建对应输入版本；接口不自动
填行、修改 available_dt 或选择新的暖机起点，也不要求检查未来 OHLC。

1.1.0 新增 `ma_point_state`，把即时平均力度与前置吻及价格趋势组合。
它使用同样的可见行情和吻参数，只取当前未封闭面积：最近已了结同向
中继吻为第二次及以后、两段价格高低点顺趋势移动、平均力度严格减弱、
距离缩短，全部满足才 warning；缺前同向面积或吻为 insufficient_evidence，
已知条件不满足为 no_warning。触零已封闭后不再发该段即时预警。

```python
from chan import ma_point_state
# 复用上例，最后的相交行尚未到达；当前快照可预警，但无已确认点。
ma_warning = ma_point_state(ma_point_bars, datetime(2026, 1, 9, 15, 5),
                            short_period=1, long_period=2)
assert ma_warning.status == 'warning'
assert ma_warning.kind == 'ma_buy1_warning'
assert ma_warning.observed_dt == datetime(2026, 1, 9, 15, 5)
assert ma_warning.last_kiss_proven is False
```

快照包含吻、两个证据区间、绝对平均力度、带符号距离和 reasons，没有精确
价格或 confirmed_dt。observed_dt 是所用最后行情实际到达时刻；相同已见
前缀的状态保持一致，后续观测可撤销预警。不要将各时刻的 warning 永久
累计进已确认候选列表；原 `find_ma_points` 的返回结构和封闭规则不变。
当时已产生的候选是历史判定事实，后续行情不会把它改为"最终反转成功"。

### 6.13 MACD 辅助一类候选与因果点位链

`find_first_points(units, bars, as_of, level)` 消费与
`confirm_level_up` 同契约的已确认次级走势，自动寻找已经完成的上涨/
下跌，追溯最后两个中枢、连接段与离开段，输出 `FirstPoint`。
`bars` 必须提供 `closed_dt`、`available_dt`，所有走势端点须在行情中
精确对应。行情和结构均先按实际到达时间截断。确认晚于离开段端点时，
返回的 `confirmed_dt` 保留这段等待时间。

这是第 24 课的 **MACD 辅助一类候选**，`method='macd_area'`，不是严格
背驰证明。它要求中枢周围波动区间严格分离、最后段创新极值、同向柱
面积减弱、B 双线回拉零轴。面积采用 `(start,end]`，共用端点不重复计数；
"零轴附近"默认量化为双线幅值/收盘价不超过 0.5%，可通过
`zero_axis_ratio` 调整，原文没有该数值。单中枢盘整背驰、未完成走势、
内部极值发生时间未知、零宽中枢等不输出。基础类型真实性、供应版本和
复权价格坐标仍由输入负责；EMA 暖机从所给历史第一根开始。
本辅助入口的新极值相对末中枢波动比较，并要求极值位于离开段端点；
严格入口另检查全趋势的先验极值，不能互相替代。
入参 `zero_axis_ratio` 是筛选阈值；`FirstPoint.zero_axis_ratio` 则记录
B 窗口实测的 `min(max(abs(DIF), abs(DEA)) / close)`，两者不可混为同一个值。

```python
import chan

# 调用模板，须先准备以下输入。
# units: 连续的ConfirmedMove或ConfirmedMoveType，不是单笔/单线段
# bars: 同坐标行情，带closed_dt和available_dt
points = chan.find_first_points(units, bars, as_of, level='F2')
chain = chan.analyze_point_chain(units, bars, as_of, level='F2')
print(chain.first_points, chain.second_points, chain.third_points)
print(chain.formations)
```

`first_point_contexts` 自动生成每轮 `SecondPointContext`，并区分两个归属：

| 字段 | 用途与可见证据 |
|---|---|
| `previous_center` | 原趋势最后中枢；第 101 课二三合一只在它反转前已知时判定 |
| `causal_center` | 一类候选锚点之后连续次级走势的首次三段重叠中枢；确认取三段实际证据和点位最晚到达时间 |

形成时的中枢边界和身份冻结，尚未形成时为 `None`；零宽交集不能用
现有三类接口表达，不跳过去改选后面的中枢。`analyze_point_chain` 是薄组合
入口，用引发中枢的首次三类点驱动第 108 课底/顶构造，用原趋势中枢判
二三合一；一类候选性质继续沿整个链传递。
下游点位通过 `context_id` 对应一类候选的 `point_id`，从该候选的
`method` 追溯力度来源；构造结果与 `contexts` 同序对应，经该上下文的
`first_point.method` 核对来源。`kind='buy2'`、构造 `phase='completed'` 等结果
只说明给定锚点下的条件与构造状态，不把锚点升级为严格背驰证明。

`scan_first_points` 返回 `FirstPointScan(points, exclusions, completed_types)`，
`exclusions` 记录完成类型未输出候选的首个原因，不能一概称为理论否决：

| 原因示例 | 阅读口径 |
|---|---|
| `not_trend` | 已完成类型不是趋势，不属于该入口的趋势一类候选问题 |
| `waiting_price_evidence` | 所需末端行情尚未到达，等待价格证据 |
| `internal_extreme_time_unknown`、`zero_width_center` | 现有输入不能定位或表达，保留证据缺口 |
| `no_zero_axis_pull`、`area_not_positive_and_weaker` | 当前参数下 MACD 辅助条件未通过，不等于严格背驰已被否定 |

比较段不足、中枢波动重叠或未创新极值也会记录相应首个原因；这些原因
不自动转换为严格接口的四态状态。尚未完成类型不进入 `exclusions`，空列表
也不能证明全部理论分支已被判定。需要四态诊断时使用 §6.15 的严格接口，
并保留其显式力度方法及证据前提。

中枢演化谱系、重组与轮次移交见 §6.17，严格结构、区间套及次级完成级联
见 §6.15—§6.16。这些接口保留显式级别、完成证据和力度方法前提，不能把
接口存在解释为所有理论分支已被真实样本验证。当前能力与证据缺口只在
[正式计划](缠论理论逐一实现计划.md) §6 登记。

### 6.14 均线九类与板块强弱

```python
from chan import ma_strength_class, sector_strength

# 原始历史保留 SMA 暖机；start_index 标记当时确定的本轮反弹起点
a = ma_strength_class([10.0] * 233 + [12.0, 9.0], start_index=233)
b = ma_strength_class([10.0] * 235, start_index=233)
report = sector_strength({"asset-A": a, "asset-B": b})
assert (a.class_no, b.class_no, report.mean_class) == (9, 1, 5.0)
```

`ma_strength_class(closes, start_index, periods=MA_PERIODS, confirm=1)`
默认采用 `(5, 13, 21, 34, 55, 89, 144, 233)` 八条 SMA，得到九个类别。
默认攻克标准为一次收盘严格高于相应均线，可通过 `confirm` 调整。
保留本轮已攻克历史，后续回落不自动降类；下一轮由调用方明确起点。

已有均线可用 `classify_ma_strength(closes, ma_by_period, start_index,
confirm=1)`。`MaClassResult` 记录类别、各均线状态和攻克位置。
缺测不当作"从未攻克"；无法判定类别时 `class_no=None`。

`sector_strength` 接收唯一成员标识到 `MaClassResult` 的映射，返回
`SectorStrength`。成员必须使用相同周期与确认标准；调用方还须保证
观察日期、复权、时间周期和反弹起点定义一致。
均值只统计已知类别，需要同时查看 `coverage/valid_count/total_count`；
空板块或无有效成员时均值为 None，不填成第 1 类或 0。

### 6.15 严格趋势背驰结构条件

```python
from chan import scan_strict_divergence, travel_force

# 调用模板，须先准备 units 和 as_of。
# units 是与 confirm_level_up 同契约的已确认连续前缀
# 力度方法可选注入, 必须声明方法身份
scan = scan_strict_divergence(
    units, as_of, 'main',
    force_fn=lambda reference, leave: (travel_force(reference),
                                       travel_force(leave)),
    force_method='unit_travel')
for r in scan.results:
    print(r.kind, r.status, r.reason, r.conditions, r.force_method)
```

`scan_strict_divergence(units, as_of, level, force_fn=None,
force_method=None)` 判定结构条件，力度方法显式注入。
按输入状态输出四类语义之一：`candidate`（开放尾部趋势，课61"先假设进入背驰
段"，同一尾部起点同一身份，完成后落为最终语义；不评估力度）、
`confirmed`（结构闭合 + 注入力度减弱；力度方法保留自身身份与
局限，不冒充理论证明）、`insufficient_evidence`（结构闭合但必需
证据缺失：力度未注入/方法不可用/内部极值时间未知/零宽中枢）、
`rejected`（中枢波动重叠、无新极值、c 无末中枢三类点、注入力度
不减，保留首个否决条件）。结构否决先于力度评估。

结构条件四项：趋势存在（课27/37）、中枢周围波动严格分离（课20/61）、
c 极值超越全趋势先验极值且恰在 c 端点（课37/61）、c 内含末中枢
次级别三类点（课37）。每项结果保留趋势/中枢/比较段单元身份、力度
方法身份与力度值、最晚确认时刻。`force_fn(reference, leave)` 返回
`(reference_force, leave_force)` 两项有序有限实数，返回 None 表示不可用；
数值须在 float 可表示范围，合法值仍按原类型和符号比较，不自动取绝对值。
NaN/inf、布尔/字符、映射/集合或错误项数抛 `ValueError`，不转成成立、
否决或缺证据；方法不可用应显式返回 None，方法执行异常原样传播。
该校验由扫描和区间套链共用，只在结构条件通过且实际评估力度时执行。
注入时必须以 `force_method` 声明非空方法身份。`travel_force` 为
内置示例力度（单元行程和），是工程示例度量，不称走势真实力度。
与 MACD 辅助候选（`find_first_points`）分别：辅助候选不
因本模块存在而改名严格（课24明示 MACD"不绝对精确"）。

### 6.16 严格区间套链与次级完成级联

```python
from chan import (scan_strict_divergence, strict_nested_chain,
                  strict_completion_cascade, travel_force)

# 调用模板，须先准备 scan、units、sub_units 和 as_of。
# scan 同 §6.15; layers 逐重显式供给相邻下级单元表(级别邻接
# 由调用方明示, 不按 K 线周期名猜级别)
chain = strict_nested_chain(
    scan.results[0], units, [('sub', sub_units)], as_of,
    force_fn=lambda reference, leave: (travel_force(reference),
                                       travel_force(leave)),
    force_method='unit_travel')
print(chain.depth, chain.complete, chain.break_depth, chain.break_reason)

# 课37"c 必然是次级别的": 对背驰段端点单元逐层复核次级完成
cascade = strict_completion_cascade(scan.results[0], units,
                                    [('sub', sub_units)], as_of)
print(cascade.depth, cascade.complete)
```

`strict_nested_chain(divergence, units, layers, as_of, force_fn=None,
force_method=None)`（课61区间套定位/课27定理）返回 `StrictChain`：
重1为传入的严格背驰结果，重2起每重取上一重背驰段区间内最后一个
次级中枢、围绕它比较两段力度（课61/课53推广）。每重 status：
`bc`/`no_new_extreme`/`force_not_declining`（否决即停止下探）、
`force_missing`/`force_unavailable`（证据缺失继续下探）、
`no_sub_center`/`no_compare_legs`/`not_covered`（窗口不可建立）。
`complete` 为最内一重 bc（区间套定位完成）；`break_depth=0` 表示
父级已否决（`parent_rejected`）；第 k 重单元须与第 k-1 重背驰段
区间时间首尾相等（否则 `not_covered`），端点价格须对齐（否则报
价格坐标契约错误）。

`strict_completion_cascade(divergence, units, layers, as_of)`（课
35/37）对 `divergence` 背驰段末单元（含转折端点）逐层复核：每层
细级可见前缀自上层端点单元起点起至 `as_of` 证据视野重算完成类型，
恰覆盖上层端点单元；返回 `StrictCompletion`，`levels` 逐层结果
（层1起，首个未通过层即止，其余声明层保留原状态），`complete`
为端点单元被逐层证明次级完成。

### 6.17 中枢演化谱系、反转轮次与可视因果图

```python
from chan import (track_center_lineage, track_rounds, causal_graph_dot)

# 调用模板，须先准备 units、bars、as_of、center_id 和 version。
# units 同 confirm_level_up 契约; next_level 为新中枢所属级别名
lineage = track_center_lineage(units, as_of, 'center_level',
                               upper_level='upper')
frozen = lineage.snapshot(center_id, version)  # 冻结快照, 不存在报错

# analyze_point_chain 的轮次分组视图(输入契约与其一致)
chain = track_rounds(units, bars, as_of, 'main')
for r in chain.rounds:
    print(r.round_id, r.formation.phase, r.handed_over_dt)

dot = causal_graph_dot(lineage=lineage, round_chain=chain, title='demo')
```

| 入口 | 返回 | 内容 |
|---|---|---|
| `track_center_lineage` | `CenterLineage(centers, events)` | 中枢事件流与快照版本链（课20/35）：`formed`/`extended`/`expanded_up`/`reorganized` 事件按到达批时刻、批内 kind 序、身份字典序排序；旧版本冻结不回写，`snapshot` 按身份+版本号取冻结快照 |
| `track_rounds` | `RoundChain(rounds, unresolved_move_ids)` | 每个自动一类候选开启一轮（课101/108）：`Round` 含锚点（`round_id` 即 `point_id`）、双中枢、课108构造状态、按 `context_id` 归属的二/三类点与同侧移交时刻 `handed_over_dt`（None=尚未移交）；平端点原样上报不删段拼接 |
| `causal_graph_dot` | `str`（DOT 文本） | `CenterLineage`/`RoundChain` 的确定性 Graphviz 投影；只投影数据中的身份、关系与时刻，不在图里推导新结论；同输入同输出 |

## 7. 证据、身份与常见错误


公开契约（导出清单、`to_dict()` 键集、常量值域、原因码、身份与
异常口径）的完整参考见 [API](api.md)；本节只给使用要点与排错。

### 证据与否决原因

扫描与条件入口不把"没有结果"混作"没有数据"：

- `scan_first_points`（§6.13）返回 `FirstPointScan(points,
  exclusions, completed_types)`：`exclusions` 每项
  `(move_id, 原因码)` 保存每个完成走势被否决的首个条件；
  `completed_types` 为完成走势数，独立计数。
- `scan_strict_divergence`（§6.15）返回 `StrictScan(results,
  skipped, completed_types, open_tail)`：`skipped` 同为
  `(move_id, 原因码)`；`results` 每项的 `conditions` 逐条件记录
  `True/False/None`（未决），`status`/`reason` 为四类返回语义与
  原因码。
- `strict_nested_chain`（§6.16）每重 `status` 即原因码。

全部原因码值域见 [API](api.md) §7；原因码字符串值属于冻结
契约，新增须排版本登记。0.13.1 起上述容器均有 `to_dict()`，可
直接 JSON 存档。

### 因果身份

`move_id`（已确认走势）、`point_id`（一类候选）、`context_id`
（反转上下文，不是数组下标）、`center_id`（因果中枢）分属不同
身份体系；组合规则、唯一性要求与冻结语义见 [API](api.md) §4。
身份须为非空字符串，重复身份在条件接口中抛 `ValueError`；输入被
供应方修订时新建输入版本，不静默覆盖旧收据。

### 常见错误

| 报错/现象 | 原因与处理 |
|---|---|
| `bars[N]时间元数据无效: 'closed_dt'` | 可用时间门控入口（`analyze_available`、`replay_available`、`find_ma_points` 等）要求 bar 带 `closed_dt`/`available_dt` 元数据；补齐元数据或改用不带门控的入口（§4） |
| `可见点位身份不能重复` / `可见上下文和中枢身份须唯一` | 同一可见视野内 `point_id`/`context_id`/`center_id` 重复；检查身份生成或数据重复 |
| `不能跳过锚点后未接线走势或使用不一致价格` | 一类点锚点与可见走势起点时间/价格不一致；确认行情与点位同源同口径 |
| `比较段与中枢端点须有精确行情, 不近似匹配` | 参与计算的时间点在行情里没有精确 bar；本库不做近似替代，检查行情覆盖 |
| `离开与首次回试时间和价格须连续` | 三类点输入的走势序列不连续；`ConfirmedMove` 须前尾后首相接 |
| `注入force_fn时必须以force_method声明方法身份` | 力度注入缺 `force_method`；补非空方法名（§6.15） |
| `可见行情须为连续前缀, 不允许跳过迟到历史行` | 迟到历史可能重算 EMA；必须声明新输入版本，不能跳过缺口后继续 |
| `json.dumps` 失败（日期/对象不可序列化） | 基础链用 `AnalysisResult.to_dict()`；底层对象按各自契约转换，如 `NewBar.to_dict()` 保留原时间类型，见 API §5 |
| `import chan` 后无 `__version__` | 导入了同名目录或遮蔽模块；按[安装排错](installation.md)排查 |
| 升级后结果与旧版不一致 | 按 1.x 兼容规则登记行为修正（CHANGELOG 标注差异并附收据）；升级前保存旧结果并逐前缀比较（见 §2 与迁移指南） |
