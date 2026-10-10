# chan-lun-core

缠论结构识别与理论辅助计算库。输入单标的、单周期的行情或结构序列，
输出分型、笔、线段、中枢、背驰、买卖点，以及多级分解和辅助状态。
算法用 Python 实现，第三方依赖只有 numpy 与 pandas；MACD 内置计算。

- 发行名：`chan-lun-core`；Python 导入名：`chan`。
- 当前源码版本：`0.5.0`。安装环境的实际版本以 `chan.__version__` 为准。
- 仓库：[lushi78778/chan-lun](https://github.com/lushi78778/chan-lun)。
- 许可证：[MIT](LICENSE)。

本库负责结构与指标计算。行情下载、交易日历、复权、跨周期取数、组合管理、
调度和下单由调用方负责。批量入口每次重新计算所提供的完整前缀。

## 阅读入口

| 需要做什么 | 阅读位置 |
|---|---|
| 安装、确认实际版本、排查导入错误 | [安装与环境检查](#安装与环境检查) |
| 第一次计算完整结构 | [快速开始](#快速开始) |
| 接入自己的行情 | [行情输入契约](#行情输入契约) |
| 读取结果、存档、回放 | [结果与时间语义](#结果与时间语义) |
| 选择算法和辅助能力 | [模块与公开入口](#模块与公开入口) |
| 了解为何采用对象与函数组合 | [组织方式](#组织方式) |
| 开发和验证 | [测试与开发](#测试与开发)、[CONTRIBUTING.md](CONTRIBUTING.md) |

## 组织方式

采用**数据对象＋纯函数＋组合入口**，按职责组织：

| 层 | 代表入口 | 职责 |
|---|---|---|
| 行情适配与校验 | `normalize_bars`、`validate_bars` | 转换数据格式、检查原始行情契约 |
| 结构与结果对象 | `NewBar`、`FX`、`BI`、`XD`、`ZS`、`AnalysisResult` | 表达结构、持有结果、提供具名字段 |
| 计算函数 | `find_bis`、`find_zs`、`level_up` 等 | 接收明确输入并计算结果，不持有跨调用分析状态 |
| 组合入口 | `analyze_bars` | 连接基础识别链，区分笔级和线段级结果 |

结构对象已有必要的面向对象表达。一个算法对应一个带 `calculate()` 的类，
不会自动改善其职责和可测试性，因此现阶段保持函数组合。
`track_zs`、`formation_state` 等函数可以计算历史状态，但不会在多次调用间
自动保存上一轮状态。

当前没有 `update/reset` 实时分析器、共享缓存、行情源基类或策略框架。
以后如需实时增量处理，须另行定义未收盘 bar 更新、同时间替换、历史修订、
确认事件和缓存失效，再逐前缀与批量实现比较。详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 安装与环境检查

### 普通 Python 环境

使用将要运行程序的解释器安装，固定版本便于复现：

```bash
python -m pip install 'chan-lun-core==0.5.0'
python -c "import chan; print(chan.__version__); print(chan.__file__)"
```

`pip` 发行名与 `import` 名不同，不要安装名为 `chan` 的其他发行包来替代。
依赖下限为 Python 3.6、numpy 1.14、pandas 0.23。现代本地开发环境与
聚宽旧环境分开准备，兼容性验证范围见后文。

### 聚宽研究 Notebook

一个安装单元格，保留换行：

```python
import sys
!{sys.executable} -m pip install --user chan-lun-core==0.5.0 --no-cache-dir
```

如果当前镜像尚未提供 `0.5.0`，可继续使用已经安装并可导入的 `0.4.0`。
镜像同步时间不由本库控制；版本不可获取时不要把安装失败当成算法错误。
如能访问 GitHub Release，也可安装指定 wheel：

```python
import sys
!{sys.executable} -m pip install --user https://github.com/lushi78778/chan-lun/releases/download/v0.5.0/chan_lun_core-0.5.0-py3-none-any.whl
```

离线时，先下载该 wheel 并上传到 Notebook 能读取的目录，再用当前解释器
对实际文件绝对路径执行 `-m pip install --user /绝对路径/文件.whl`。
保持已有 numpy/pandas，不为安装本库升级聚宽内置环境。

安装后若此前已导入过 `chan`，重启内核，再在新的单元格确认：

```python
import sys
import chan

print("python:", sys.version.split()[0])
print("chan version:", chan.__version__)
print("chan file:", chan.__file__)
print("has find_bis:", hasattr(chan, "find_bis"))
```

`0.4.0` 可以使用其已有基础链与理论模块；`analyze_bars`、行情校验和
分型力度从 `0.4.2` 起可用，106课笔标准从 `0.4.3` 起可用，MACD 防狼从
`0.4.4` 起可用，底/顶构造从 `0.4.5` 起可用，板块强弱从 `0.5.0` 起可用。
下面的完整示例按 `0.5.0` 编写。冻结研究脚本的原有版本要求另行保留。

### `chan.__version__` 不存在时

先确认实际导入对象，不要给错误模块手工补版本号：

```python
import sys
import chan

print("python:", sys.version.split()[0])
print("file:", getattr(chan, "__file__", None))
print("path:", list(getattr(chan, "__path__", [])))
print("spec:", getattr(chan, "__spec__", None))
print("version:", getattr(chan, "__version__", None))
print("has find_bis:", hasattr(chan, "find_bis"))
```

| 现象 | 含义与处理 |
|---|---|
| `file=None`、`origin='namespace'`，路径为工作目录 `/home/jquser/chan` | 导入了同名目录形成的命名空间包。用当前内核解释器安装 `chan-lun-core`，重启内核后再查 |
| 文件来自工作区的 `chan.py` 或其他 `chan/__init__.py` | 有同名模块遮蔽。检查导入路径和该文件用途，消除遮蔽后重新启动 |
| 文件来自 `site-packages/chan/__init__.py`，但版本或入口不符合预期 | 检查当前解释器的安装元数据、安装版本及内核缓存 |
| `ModuleNotFoundError` | 当前解释器找不到包；用同一解释器安装，而不是其他终端中的 pip |

聚宽 Python 3.6 可额外检查安装元数据：

```python
import pkg_resources

try:
    dist = pkg_resources.get_distribution("chan-lun-core")
    print("installed:", dist.version, dist.location)
except pkg_resources.DistributionNotFound:
    print("chan-lun-core: 未安装")
```

元数据说明发行包已安装，不单独证明 `import chan` 加载了它。
完整 Chan 工作区提供 `tools/diagnose_chan.py`，可同时核对运行时路径、
版本、安装元数据和关键公开入口。

### 从源码开发

本仓库采用 src-layout。包文件在仓库根的 `src/chan/`，不是仓库根本身。

```bash
# 在独立 chan-lun 仓库根运行，使用现代开发解释器
python -m pip install -e .
python -m unittest discover -s tests -p 'test_*.py'
```

完整 Chan 工作区中，本仓库在 `src/chan/`，安装命令为
`python -m pip install -e ./src/chan`。如果显式设置源码导入路径，应该是
工作区的 `src/chan/src`，不是外层 `src` 或 `src/chan`。
构建后端要求现代 setuptools；旧 Python 环境优先安装已构建的 wheel。

## 快速开始

下面使用合成行情，完整复制后即可运行，无需行情账号：

```python
import math
import json
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
print("as_of:", result.as_of)
print("分型/笔/线段:", len(result.fxs), len(result.bis), len(result.xds))
print("笔级中枢:", len(result.bi_zss))
print("买点:", result.buy_points)
print("卖点:", result.sell_points)
snapshot = result.to_dict()
json_text = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
```

合成数据只演示调用方法，不保证每类结构或信号都会出现。
`analyze_bars` 提供基础链默认参数；需要自定义 MACD、背驰参数、三买力度
门槛或辅助模块时，使用各模块函数组合。

## 行情输入契约

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

## 结果与时间语义

### `AnalysisResult`

| 字段 | 内容 |
|---|---|
| `as_of` | 最后一根输入 bar 的时间；空输入为 None |
| `new_bars`、`fxs`、`bis`、`xds` | 无包含 K 线、分型、笔、线段的对象列表 |
| `bi_zss`、`xd_zss` | 分别由笔和线段得到的中枢，明确分开 |
| `bi_trends` | 笔级中枢的走势分类 |
| `trend_bc`、`pan_bc` | 使用笔级中枢和笔序列的背驰候选 |
| `buy_points`、`sell_points` | 同一笔级口径的买卖点事件列表 |
| `dif`、`dea`、`hist` | 与原始 bars 等长的 numpy 数组，默认参数 12/26/9 |

结果字段不可重新绑定，但内部列表、数组和结构对象可以修改。
每次批量计算独立分配结果；`.to_dict()` 生成深拷贝，将时间转为字符串、
数组转为列表，适合 JSON 存档。不要把任意底层对象都当成统一 JSON schema。

### 端点、输入截止与确认时间

`as_of` 只表示输入截止，不证明最后一根 bar 已经收盘。
分型的中心 K 线时间、笔端点时间、买卖点 `dt` 表示结构所在位置，
不自动等于当时可识别或可成交的时刻。分型需要右邻确认，包含合并还可能
延长确认等待；未完成的笔、线段和上推结构尾部也会随新数据修订。

历史回放应逐前缀重算，或读取当时存下的可见快照：

```python
from chan import analyze_bars

observed = []
for stop in range(1, len(bars) + 1):
    current = analyze_bars(bars[:stop])
    observed.append((current.as_of, current.to_dict()))
```

上例说明正确的可见性边界，长样本需要自行控制存储和计算量。
对完整样本最终结果仅按结构端点 `dt` 过滤，不能还原历史可见状态。
已完成项的前缀一致性也以输入单元稳定、实际可见为前提。

取数截止与前复权基准均锚定观察日；聚宽可能填充未来日期行情，调用方需
钳制 `end_date` 并再次过滤返回时间。跨周期数据也按对应观察时刻截断。

## 模块与公开入口

公开函数和结果类可直接 `from chan import ...`，也可从所属模块导入。
完整导出清单是 `chan.__all__`；以下按用途列出主要入口，阈值和边界细节
见函数 docstring 与模块测试。

### 基础识别链：分型、笔、线段、中枢

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
| `fx` | `remove_includes`、`find_fxs`、`NewBar`、`FX` | 先按顺序处理包含，再识别三K分型 |
| `bi` | `find_bis`、`chan_fx_bi`、`BI` | 分步或一次返回 `(new_bars, fxs, bis)` |
| `xd` | `find_xds`、`chan_bis_xds`、`XD` | 特征序列识别线段，支持第一种情况及缺口确认 |
| `zs` | `find_zs`、`track_zs`、`ZS`、`ZsEvent` | 返回中枢，或 `(zss, events)` 事件流 |
| `zs` | `zs_relation`、`build_expanded_zs`、`classify_trend` | 中枢关系、扩展构造与走势粗分类 |

`NewBar.elements` 记录原始 bar 下标；`FX.bar_index` 是无包含序列下标。
`BI.direction` 为 `up/down`，有起止时间、起止值和高低点；
`XD.mode` 为情况 1/2，`gg/dd` 表达内部极值。

默认成笔标准是81课：`MIN_K_GAP=3`，两个分型中心在无包含序列的
下标差至少为4。显式选择106课标准：

```python
from chan import analyze_bars, chan_fx_bi

new_bars_106, fxs_106, bis_106 = chan_fx_bi(bars, standard="106")
result_106 = analyze_bars(bars, bi_standard="106")
```

106课要求两个完整三K分型至少六个无包含 K 线单位，中心端点区间触及
方向相应的原始 MA5；默认间隔为2。直接调用 `find_bis(..., standard="106",
ma5=...)` 时，MA5 必须按每个包含组最后原始下标对齐。
`min_k_gap` 可另设间隔，但不能取消106课六K单位等条件。

`ZS.zd/zg` 为中枢边界，`gg/dd` 为构成波动的最高/最低点；另有
`start_dt/end_dt/direction/xd_count/extended_9`。
`classify_trend` 分组保留 `zs_list`，顶层 `zd/zg` 是组内首个中枢。
`track_zs` 事件反映形成、延伸、九段升级、完成与新生，其事件 `dt`
仍取源单元端点，不自动提供实际确认时间。

边界约定因概念而异：`zs` 的初始三段要求 `ZD < ZG`；同级分解和
递归使用闭区间交集，`ZD == ZG` 可计为交集。不要跨模块抹平这些差异。

### 背驰与买卖点

| 模块 | 入口 | 内容 |
|---|---|---|
| `bc` | `ema`、`macd_series`、`segment_area` | EMA、MACD 与段内柱面积 |
| `bc` | `find_trend_bc`、`find_pan_bc` | 趋势/盘整背驰候选，可复用 `hist` |
| `bs` | `find_buy_points`、`find_sell_points` | 第一、二、三类事件 |

MACD 返回 `(dif, dea, hist)`，`hist = 2 * (dif - dea)`。
趋势背驰使用相应趋势与创新极值条件下的柱面积比较；盘整背驰另有位置
过滤参数 `max_dev=0.15`。这些是当前量化识别口径。

| 点类型 | 当前识别条件 |
|---|---|
| 一买/一卖 | 下跌/上涨趋势背驰；当前取首个方向匹配的趋势背驰锚点 |
| 二买/二卖 | 一类点后首次回调/反弹，不破对应一类点极值 |
| 三买/三卖 | 离开中枢后首次回抽/反抽守边界，并比较离开与回拉力度 |

不传 `trend_bc` 时只识别第三类。信号公共字段为 `type/dt/price/basis/zs_idx`。
三类点另有 `power_ratio/zs_zd/zs_zg/pull_start_dt/pull_end_dt/pull_start/pull_end`；
二买有 `b1_price`，二卖有 `s1_price`。事件按判定顺序返回，需要时间排序时
由调用方显式排序；`zs_idx` 是本次列表的局部索引，不能用作长期中枢身份。

三类点回抽恰好触边界可接受。默认力度比较使用保留两位小数的比值 `> 1`；
传入 `min_power_ratio=n` 改为 `>= n`。阈值属于工程参数，需要独立验证。

理论覆盖边界：当前 `bs` 是笔级简化识别，不等同于第101课的完整精确定义。
第101课允许二买低于一买的弱情形，现有“不破一类点”门槛尚未覆盖；
中阴上下文、已完成次级走势以及第53课小转大中无本级一类点的情形仍需
补强。后续需要完整定义输入证据，不能只删除价格门槛扩大输出。

### 同级分解、级别递归与状态

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
| `levels` | `LevelDecomposition`、`decompose_levels`、`level_reading`、`change_starts_low` | 多级分解、指定端点时间读数、上下级方向改变自洽性 |
| `zhongyin` | `ZhongYinResult`、`track_zhongyin` | 中阴阶段：进入、中枢形成及结束状态 |
| `zhongyin` | `boll_bands`、`boll_state`、`boll_events`、`boll_bs1_hints` | BOLL 辅助事件与一类点提示 |
| `osc` | `OscReport`、`oscillation_monitor`、`osc_strength`、`zn_next_estimate` | 中枢震荡统计、力度及数值估计 |
| `biaoli` | `bi_state`、`bi_transition_valid`、`disease_stage`、`followup_quality`、`zhongyin_health` | 笔四状态、合法迁移、双级状态与震荡强弱 |

同级分解与递归是不同规则，不能互相替换。`MoveType.complete=False`
表示尾部尚未完成，`kind='incomplete'` 表示没有形成完整走势类别，
两种标记不能混为一谈。

`decompose_levels` 第1级保留输入单元，以后逐级上推；序号不自动对应
1分钟/5分钟/日线等时间周期。`level_reading` 按起止端点的闭区间读数，
历史可见性仍要先做前缀计算。

震荡监视器的 `center` 是 `(zd, zg)`，单元需有价格区间与方向属性。
BOLL 阈值和震荡估计都是辅助口径，BOLL 提示不等同于 `bs` 的确认事件。
双级“病情”和“健康”标签相对原走势方向解释，不自动映射为开平仓动作。

### 力度、转折和均线吻

| 模块 | 主要入口 | 输入/输出职责 |
|---|---|---|
| `strength` | `sma_series`、`ma_areas`、`MaArea`、`find_ma_bc`、`avg_strength_state`、`MaStrengthState` | 两条均线差值面积、同向力度比较、形成中的平均力度 |
| `turn` | `classify_bc_turn`、`guaranteed_rebound_gap` | 背驰后转折三分类与回拉幅度条件 |
| `minor_turn` | `classify_minor_turn` | 小级别背驰引发大级别转折的阶段分类 |
| `kiss` | `alignment_series`、`classify_kiss`、`find_kisses`、`KissEvent` | 两均线体位与飞吻/唇吻/湿吻，保留吻次序和量能原料 |
| `gap` | `Gap`、`find_gaps`、`classify_gap` | 原始 K 线缺口与基于可见后续行情的力度分类 |

`strength` 的短长均线等长，`sma_series` 暖机段为 None；输入价格需完整。
`find_ma_bc` 比较已闭合的同向均线面积，`use_avg=True` 使用平均力度。
`avg_strength_state` 可描述形成中的面积，不应作为已完成背驰替代品。

`find_kisses(short, long, volumes=None, proximity=0.5, min_depth=0.2,
flip_confirm=0.5)` 返回吻事件。`alignment_series` 的 `up/down` 分别表示
短线在长线上方/下方；触零也算湿吻。三个默认比例是对定性描述的量化，
吻本身不自动生成买卖点，需要配合价格结构和背驰。

`classify_bc_turn` 接收原中枢、后续回拉、原趋势方向；`classify_minor_turn`
还可接收次级中枢和三类点信息。分类保留必要条件与充分证据的区别。
缺口最终如何回补依赖后续输入；回放时只能使用当时已知行情。

### 固定两级与任意多级区间套

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

固定30m确认使用段首末 DIF 摆动，端点各顺延两根 K 线吸收 EMA 惯性；
MACD 柱面积只作参考。常见返回状态为 `confirmed/weak/no_exhaustion/broke/
stale/no_data`；找不到相应运行段时也可能出现 `none`。
`note` 给出解释，其他字段按判定路径提供，不能假定每次都有完整力度数据。

库默认 `stale_days=1`（自然日）；历史研究脚本可能明确采用3。
`min_prev_swing_ratio` 默认为 None；设值后要求对照力度达到最低规模。
三买 `zg_tol`、三卖 `zd_tol` 是保留参数，目前不影响判定；实际弱确认
容忍由 `weak_tol` 控制。二买采用 `pierce_tol`，不套用三买的离开段逻辑。

调用方必须提前截断传入分钟行情，确认函数不会替调用方统一裁剪所有输入。
取到信号之后的行情可能改变分型确认与末端结构。

任意多级 `nested_bc(inputs, strength_fn=None)` 从大级别到小级别接收
候选段链；默认力度为 MACD 柱面积，也可注入 `strength_fn(bars, move)`。
区间不嵌套、未创新极值或力度未衰减等都会使链断开；结果 `complete`
表示给定证据链成立。`BcNestInput.center` 仅用于记录，中枢因果关系和
趋势前提需要调用方核对。

### 分型力度、均线突破与 MACD 防狼

| 模块 | 入口/对象 | 结果 |
|---|---|---|
| `fxpower` | `classify_fx_power`、`classify_fx`、`FxPowerResult` | 三K形态 `weak/neutral/strong/severe` 及包含标签 |
| `fxpower` | `ma_break_state`、`MaBreakState` | 收盘相对均线的 `none/testing/effective` 历史确认 |
| `macd_guard` | `macd_below_zero`、`macd_guard_series` | DIF 与 DEA 都严格小于零为 True，有效其他值为 False，缺测为 None |

`classify_fx_power(b1, b2, b3, direction='top', long_body=0.35,
small_body=0.15, shadow=0.25)` 假定三K分型已由调用方确定；底分型镜像。
三个比例是形态量化阈值，不是原文给出的通用数值。
`classify_fx(fx, new_bars)` 是已有分型对象的便捷入口；NewBar 实体是
包含组首开末收的近似，精细原始形态分析优先使用原始 K 线。

`ma_break_state(closes, mas, direction, confirm=2)` 的观察序列从分型
右邻之后开始；均线先在完整历史上计算再对齐截取。有效突破需连续指定
根数的收盘严格越线，缺测中断连续计数。一旦有效，后续回归不会取消历史
有效记录；有效前的恢复可表现为假突破。

```python
from chan import macd_below_zero, macd_guard_series

assert macd_below_zero(-0.2, -0.1) is True
assert macd_below_zero(0.0, -0.1) is False
assert macd_guard_series([-0.2, None], [-0.1, -0.1]) == [True, None]
```

触零或跨轴只说明负区判据不成立，不等于重新站稳，也不自动产生买入许可。

### 底部与顶部构造

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
这个精确走势构造状态。结果类为 `FormationState`。

### 均线九类与板块强弱

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
缺测不当作“从未攻克”；无法判定类别时 `class_no=None`。

`sector_strength` 接收唯一成员标识到 `MaClassResult` 的映射，返回
`SectorStrength`。成员必须使用相同周期与确认标准；调用方还须保证
观察日期、复权、时间周期和反弹起点定义一致。
均值只统计已知类别，需要同时查看 `coverage/valid_count/total_count`；
空板块或无有效成员时均值为 None，不填成第1类或0。

## 测试与开发

### 源码测试

在独立包仓库根运行：

```bash
python -m pip install -e .
python -m unittest discover -s tests -p 'test_*.py'
# 定向检查公开契约和 README 示例
python -m unittest discover -s tests -p 'test_contracts.py'
```

测试覆盖理论定义分支、退化输入、时间状态、组合入口等价性、输入与
快照隔离、公开导出、版本一致和 Python 3.6 语法。README 的基础链、
批量入口、构造状态和板块强弱示例随契约测试执行。

### 安装产物验证

源码测试主动使用本仓库源码，不能证明 wheel 包含了全部文件。
构建并安装 wheel 后另行运行隔离检查：

```bash
python -m pip install build
python -m build
python -m pip install --force-reinstall --no-deps dist/chan_lun_core-0.5.0-py3-none-any.whl
python -I tools/verify_installed.py
```

检查导入路径来自安装位置、运行时与元数据版本一致、公开入口完整及
代表性计算可运行。`-I` 避免源码路径使漏打包问题被掩盖。
不要在源码安装环境中把常规 `import chan` 的成功当成产物验收。

### 验证范围与交付

CI 在 Python 3.10/3.13 运行源码与安装产物检查；tag 发布另有 Release
和 PyPI 步骤。Python 3.6 语法检查、现代依赖本地运行、旧解释器旧依赖
实跑、聚宽取数、真实行情、报告显示和研究有效性是不同层次的验证。

聚宽已确认 `0.4.0` 可安装并导入，但这不代替全部新增算法在该环境的实跑。
新的辅助结果不会自动接入冻结研究脚本或改变策略参数。

开发分层、原文核验、概念版本和交付流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
完整 Chan 工作区的理论进度唯一维护在 `doc/缠论理论逐一实现计划.md` §6；
本 README 维护用法，版本历史维护公开变化，不另设理论完成状态表。

## 版本历史

- **0.5.0**: 阶段4辅助系统完成; 新增106课均线九类与板块强弱
  `classify_ma_strength/ma_strength_class/sector_strength`, 显式本轮
  起点、因果SMA、缺测状态及均值覆盖率。安装产物进入CI独立导入验收。
- **0.4.5**: 底部/顶部构造状态(课108), `formation_state` 按同级同因果
  中枢的首次三类点结束构造。`FormationEvent.confirmed_dt` 为实际确认
  时间, 不能用全样本结构端点代替; 分型箱体辅助定义另行处理。
- **0.4.4**: MACD零轴防狼术(课103), `macd_below_zero(dif, dea)` 与
  `macd_guard_series` 返回双线严格负区的布尔判据, 缺测为None。
  触零/跨轴不等于重新站稳, 不直接生成买入许可。
- **0.4.3**: 可选106课笔标准 `chan_fx_bi(bars, standard="106")`:
  两个完整无包含三K分型至少六K单位、端点区间至少触及原始MA5。
  默认仍为81课标准; 包含组均线按最后原始下标对齐。
  `analyze_bars(..., bi_standard="106")` 与 `chan_bis_xds(..., standard="106")`
  支持显式选择, 未完成尾笔仍可能延伸。
- **0.4.2**: 分型力度(课79/82), 三K线形态四档与底分型镜像、包含标签,
  以及收盘对均线的历史确认状态。定性形态采用可配置工程阈值;
  有效破均线不保证成笔。公开入口 `classify_fx_power/classify_fx/ma_break_state`。
- **0.4.1**: 均线吻系统(课11/12)，体位与飞吻/唇吻/湿吻分类。
- **0.4.0**: 动力学补强，包含均线趋势力度、背驰转折分类、小转大与多级区间套。
- **0.3.0**: 走势状态与监视，包含中阴、震荡监视、表里关系和多级记数法分解。
- **0.2.0**: 形态学主干补强，包含缺口、中枢状态、同级分解与级别递归。
- **0.1.10**(冻结基线): LICENSE 版权人更新为 lushi78778; 版本历史与文档措辞清理(去决策归因表述);
- **0.1.9**:发布元数据维护; license 改 PEP 639 SPDX 表达式 MIT(pip show 显示 License: MIT 而非内联全文), LICENSE 文件仍随包分发; Home-page 为 PEP 621 旧字段, 现代规范用 Project-URL Homepage(已指向 GitHub 仓库, PyPI 页面可见);
- **0.1.8**:正确性/健壮性——`classify_trend` 补方向一致性判定(反向中枢不再误并趋势); `bc.ema`/`macd_series`/`find_trend_bc` 空输入防护; `confirm_buy3/3_30m` 的 zg_tol/zd_tol 标注为保留参数(文档如实化); stale_days 文档与默认值表述澄清;
- **0.1.7**:通用完善——`chan` 顶层导出全部公开 API
  (`__all__`, `from chan import find_zs` 可用);全模块补 3.6 兼容
  typing 注解与详细 docstring(参数/返回结构/规则边界逐条说明);
  `find_bis` 新增 `min_k_gap` 参数(默认行为不变);`classify_trend`
  新增 `zs_list`(组内全部中枢明细,旧字段保留);
- **0.1.6**:新增二买 30m 轻量确认 `confirm_buy2_30m`、
  三买/三卖事件桥接 `confirm_buy3_event_30m` / `confirm_sell3_event_30m`、
  二买/二卖事件补 `b1_price`/`s1_price` 字段、三买/三卖力度过滤
  参数化 `min_power_ratio`(默认行为不变,向后兼容);
- **0.1.5**:详细版 README(全模块 API/数据约定/防未来函数/状态表);
- **0.1.4**:发行名 `chan-lun-core`(PyPI 拒绝 `chan-lun`:
  与现有 `chanlun` 名称过于相似),GitHub Release + PyPI 双发布打通;
- 0.1.3:首次 PyPI 发布尝试,因发行名冲突被 PyPI 拒绝(GitHub Release 保留);
- 0.1.2:仓库改为标准 src-layout(PyPA 官方布局);
- 0.1.0 / 0.1.1:早期布局(GitHub Release 保留)。

## 免责声明

本库仅用于研究与学习。缠论信号是对价格结构的客观描述,**不构成任何投资建议**;
交易有风险,使用本库产生的一切后果由使用者自行承担。

## 许可证

MIT,见 [LICENSE](LICENSE)。
