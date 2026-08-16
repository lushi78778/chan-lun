# chan-lun-core

缠论(缠中说禅理论)量化核心库 —— 从 K 线归一化到三类买卖点的完整
技术分析流水线,外加日线信号 → 30 分钟级别的跨级别共振确认(区间套)。

纯 Python 实现,**不依赖任何行情接口与第三方指标库**:输入标准化的
bar 序列,输出结构化的分型/笔/线段/中枢/背驰/买卖点对象与信号事件。
MACD 指标为内置实现,唯一第三方依赖是 numpy(计算)与 pandas(数据归一化辅助)。

- 发行名:**chan-lun-core**(PyPI 上 `chan` 已被占用, `chan-lun` 与现有 `chanlun` 冲突, 故加 `-core` 后缀)
- import 名:`chan`
- 许可证:MIT
- 仓库:https://github.com/lushi78778/chan-lun

## 特性

- **完整理论链条**:包含处理 → 分型 → 笔 → 线段 → 中枢 → 背驰 → 三类买卖点,每层独立成模块、可单独调用;
- **跨级别确认(区间套)**:日线三买/三卖 → 30 分钟内部背驰 + 中枢边界守位,输出 confirmed/weak/broke 等明确状态;
- **零行情耦合**:输入只是 `list of dict` 的标准 bar,任何数据源(聚宽/米筐/本地 CSV)归一化后即可用;
- **无未来函数**:所有信号只用信号日及之前的数据计算(见下文"防未来函数"一节);
- **老环境友好**:Python 3.6+、numpy 1.14+、pandas 0.23+ 均可运行(实测于聚宽研究环境 3.6.7 / numpy 1.14.6 / pandas 0.23.4)。

## 安装

从 PyPI 安装:

```bash
pip install chan-lun-core
```

从 GitHub Release 安装(由 CI 自动构建):

```bash
pip install https://github.com/lushi78778/chan-lun/releases/download/v0.1.7/chan_lun_core-0.1.7-py3-none-any.whl
```

或源码安装:

```bash
pip install git+https://github.com/lushi78778/chan-lun.git
```

## 快速开始

全部公开 API 已在包顶层重新导出,既可按模块导入,也可直接从 `chan`
导入(两者等价):

```python
from chan import (normalize_bars, chan_fx_bi, chan_bis_xds, find_zs,
                  macd_series, find_buy_points, find_sell_points,
                  confirm_buy3_30m)
# 等价于 from chan.bars import ... / from chan.bi import ... 等
```

完整管线:

```python
from chan.bars import normalize_bars
from chan.bi import chan_fx_bi
from chan.xd import chan_bis_xds
from chan.zs import find_zs, classify_trend
from chan.bc import macd_series, find_trend_bc
from chan.bs import find_buy_points, find_sell_points

# 1. 行情 DataFrame -> 标准 bar 列表(列名可配置)
bars = normalize_bars(df)

# 2. 分型 + 笔(chan_fx_bi 返回 无包含序列/分型/笔 三元组)
new_bars, fxs, bis = chan_fx_bi(bars)

# 3. 线段(特征序列标准, 支持缺口确认)
xds = chan_bis_xds(bars)

# 4. 中枢(find_zs 鸭子类型: 传笔列表得笔级中枢, 传线段列表得线段级中枢)
zss = find_zs(xds)
trends = classify_trend(zss)          # 盘整/趋势粗分类

# 5. MACD 与背驰
dif, dea, hist = macd_series(bars)    # 标准参数 12/26/9
trend_bc = find_trend_bc(bis, zss, bars)   # 趋势背驰候选
pan_bc = find_pan_bc(bis, zss, bars)       # 盘整背驰候选

# 6. 三类买卖点
buys = find_buy_points(bis, zss, trend_bc)
sells = find_sell_points(bis, zss, trend_bc)
```

跨级别确认(日线三买 → 30 分钟底背驰 + 不破中枢上沿 ZG):

```python
from chan.cross30 import confirm_buy3_30m

# bars30: 30 分钟 bar, 必须拉到"信号日为止", 不能包含信号日之后的数据
r = confirm_buy3_30m(bars30, zd=zd, zg=zg, signal_dt="2026-08-14")
print(r["status"])   # confirmed / weak / no_exhaustion / broke / stale / no_data
print(r["note"])     # 人类可读结论
```

## 数据约定

所有模块的输入/输出都是**纯 Python 结构**,与数据来源无关:

```python
# 标准 bar: 按时间升序的 dict 列表
bars = [
    {"dt": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...},
    ...
]
```

- `dt` 为原类型(datetime/Timestamp/str 均可,内部统一按 `str(dt)` 比较);
- 数量单位、复权方式由调用方决定——只要同一序列内部一致即可;
- `chan.bars.normalize_bars` 负责把 DataFrame 转成标准 bar(默认列名即聚宽 `get_price`/`get_bars` 列名,可配置映射)。

## 防未来函数(重要)

本库**只做计算,不拉行情**——因此"未来函数"的风险完全在调用方的取数上:

1. 计算信号日 `D` 的信号时,行情序列必须以 `D` 的最后一根 bar 结束,**严禁**包含 `D` 之后的 bar;
2. 前复权数据请把复权基准日锚定在信号日;
3. 分型需要后一根 K 线确认,因此分型/笔的 `dt` 天然比"确认时刻"早一个周期——这是正常现象,不是未来函数。

## 模块详解

### chan.bars —— 行情归一化

```python
from chan.bars import normalize_bars, bars_to_df, BAR_KEYS

bars = normalize_bars(df, dt_col="date", open_col="open", high_col="high",
                      low_col="low", close_col="close", volume_col="volume",
                      drop_paused=True)
```

- 按时间升序排序、数值化 OHLCV;`drop_paused=True` 时丢弃停牌 bar(成交量=0 且高低价持平);
- `bars_to_df(bars)`:标准 bar 列表转回 DataFrame(测试与展示用)。

### chan.fx —— 包含处理 + 分型

```python
from chan.fx import remove_includes, find_fxs

new_bars = remove_includes(bars)   # 包含关系处理(顺序原则)
fxs = find_fxs(new_bars)           # 分型识别
```

- `NewBar`:合并后的 K 线,含 `dt/open/high/low/close/volume/elements`(elements 记录合并进来的原始 bar 索引);
- `FX`:分型对象,`kind`(`top` 顶 / `bottom` 底)、`dt`、`high`、`low`、`bar_index`、`value`(分型极值);
- 顶分型:中间 K 线高点与低点都是三者最高;底分型镜像。

### chan.bi —— 笔

```python
from chan.bi import find_bis, chan_fx_bi, BI, MIN_K_GAP

new_bars, fxs, bis = chan_fx_bi(bars)   # 一站式: 包含处理 + 分型 + 笔
bis = find_bis(new_bars, fxs)           # 或分步调用
```

- 成笔条件(课 77/81):一顶一底交替、顶必须高于底、两个分型中间 K 线之间至少 `MIN_K_GAP=3` 根独立 K 线(无包含序列索引差 >= 4);
- `find_bis(new_bars, fxs, min_k_gap=3)`:`min_k_gap` 可参数化——调小(如 2)笔更灵敏、数量更多,调大更稳健,用于不同级别/流动性适配;默认即课 81 标准;
- 同向连续分型取极端(顶取更高、底取更低),并同步延伸上一笔终点;
- `BI` 对象:`direction`(`up`/`down`)、`start_dt/end_dt`、`start_value/end_value`、`high/low` 属性、`start_index/end_index`、`to_dict()`。

### chan.xd —— 线段

```python
from chan.xd import find_xds, chan_bis_xds, XD

xds = chan_bis_xds(bars)   # bars -> 分型 -> 笔 -> 线段(完整入口)
xds = find_xds(bis)        # 或从笔列表出发
```

- 基于特征序列,支持两种标准:`mode` 1 = 第一种情况(特征序列顶分/底分),2 = 第二种情况(缺口确认);
- `XD` 对象:`direction`、`start_dt/end_dt`、`start_value/end_value`、`gg/dd`(内部高低极值,中枢重叠计算用)、`mode`、`to_dict()`。

### chan.zs —— 中枢与走势类型

```python
from chan.zs import find_zs, classify_trend, ZS

zss = find_zs(xds)            # 传 XD 列表; 也可传 BI 列表做笔级中枢
trends = classify_trend(zss)  # [{'type': '盘整'|'趋势', 'zs_count', 'start_dt', 'end_dt', 'zd', 'zg', 'zs_list'}, ...]
```

- `classify_trend` 每个分组除 `type/zs_count/start_dt/end_dt` 外,新增
  **`zs_list`**:组内全部中枢的明细(各自的 zd/zg/gg/dd/start_dt/end_dt/
  xd_count/extended_9),需要"第 k 个中枢边界"时不再只能拿到第一个;
  顶层 `zd/zg` 字段保留(组内首个中枢,向后兼容)。

- 中枢 = 至少三个连续次级别走势(线段)重叠区间:`ZD = max(三个低点)`,`ZG = min(三个高点)`;另记录 `GG/DD`(构成线段的最高/最低点);
- 后续线段与 `[ZD, ZG]` 重叠 → 中枢延伸(更新 GG/DD、结束时间);不重叠 → 中枢完成、新生;
- 延伸超过 9 个线段标记 `extended_9 = True`(更大级别中枢,第一版仅标记);
- `ZS` 对象:`zd/zg/gg/dd`、`start_dt/end_dt`、`direction`、`xd_count`、`extended_9`、`to_dict()`。

### chan.bc —— 背驰(MACD 辅助)

```python
from chan.bc import ema, macd_series, segment_area, find_trend_bc, find_pan_bc

dif, dea, hist = macd_series(bars)          # 内置 EMA 实现, 参数 12/26/9
trend_bc = find_trend_bc(bis, zss, bars)    # 趋势背驰候选
pan_bc = find_pan_bc(bis, zss, bars, max_dev=0.15)   # 盘整背驰候选(含位置过滤)
```

- `macd_series` 返回 `(dif, dea, hist)` 三个 numpy 数组,`hist = (dif - dea) * 2`;
- `find_trend_bc`:相邻两中枢不重叠构成趋势,最后中枢离开段创新高/新低但 MACD 柱面积小于前一连接段 → 背驰候选;
  返回 `{direction, dt, price, zs_idx, area_prev, area_last, note}` 列表;
- `find_pan_bc`:中枢震荡中相邻两段同向波动力度比较;`max_dev` 位置过滤(创新高/新低后偏离中枢超过该比例的信号多为趋势延伸,剔除)。

### chan.bs —— 三类买卖点

```python
from chan.bs import find_buy_points, find_sell_points

buys = find_buy_points(bis, zss, trend_bc)
sells = find_sell_points(bis, zss, trend_bc)
```

| 类型 | 定义 |
|---|---|
| 第一类 | 趋势背驰点(下跌趋势背驰为买点,上涨趋势背驰为卖点) |
| 第二类 | 一买后第一次次级别回调不破一买低点(卖点镜像) |
| 第三类 | 离开中枢后回抽不破 ZG(买)/不升破 ZD(卖),并做力度过滤(回拉力度 < 离开力度) |

每个信号事件为 dict:`{type: 1/2/3, dt, price, basis, zs_idx, power_ratio}`;
第三类信号额外附带 `zs_zd/zs_zg/pull_start_dt/pull_end_dt/pull_start/pull_end`,
供 30 分钟跨级别确认使用。

- `find_buy_points(bis, zss, trend_bc=None, min_power_ratio=None)`:
  `min_power_ratio` 为三买力度过滤下限——`None` 保持默认行为(离开力度
  必须大于回拉力度),传入数值 `n` 则要求比值 `>= n`(回测敏感性测试用,
  如 1.5/2.0);卖点镜像同参数;
- 第二类买点事件附带 **`b1_price`**(对应一买低点),第二类卖点事件附带
  **`s1_price`**(对应一卖高点),供 30m 轻量确认(`chan.cross30.confirm_buy2_30m`)。

### chan.cross30 —— 30m 跨级别共振确认(区间套)

```python
from chan.cross30 import (confirm_buy3_30m, confirm_sell3_30m,
                          confirm_buy2_30m, confirm_buy3_event_30m,
                          confirm_sell3_event_30m, find_run_exhaustion)

r = confirm_buy3_30m(bars30, zd, zg, signal_dt,
                     zg_tol=0.01, weak_tol=0.02, stale_days=1,
                     min_prev_swing_ratio=None)
```

- 逻辑:日线三买(回抽不破 ZG)后,到 30 分钟里看回抽段内部是否**底背驰**(末段 DIF 摆动小于前一同向段且创新低)+ 30 分钟低点是否守住 ZG;三卖镜像;
- 力度度量用 **DIF 摆动**(段首末 DIF 差,两端各顺延 2 根 K 线吸收 EMA 惯性尾),MACD 柱面积仅作参考;
- `min_prev_swing_ratio`:前段 DIF 摆动不足价格中位数该比例时判"无法比较力度"(微型波动时力度比较无意义),默认 None 不设门槛;

返回 dict,核心字段:

| 字段 | 含义 |
|---|---|
| `status` | `confirmed` 强共振 / `weak` 弱确认(盘中轻微刺破 ZG/ZG 容忍内)/ `no_exhaustion` 未确认(无背驰或无法比较)/ `broke` 30m 破位,日线信号存疑 / `stale` 30m 未跟上(回抽段终点早于信号日过多)/ `no_data` |
| `note` | 人类可读结论 |
| `low30` / `high30` | 30m 回抽段极值 |
| `dist_zg` / `dist_zd` | 极值距中枢边界的百分比 |
| `swing_last/swing_prev/swing_ratio` | 末段/前段 DIF 摆动及比值 |
| `area_last/area_prev/area_ratio` | MACD 柱面积及比值(参考) |
| `zs_count` | 与回抽段区间重叠的 30m 中枢个数 |

**二买轻量确认** `confirm_buy2_30m(bars30, buy1_price, signal_dt,
stale_days=1, pierce_tol=0.0)`:二买没有"离开中枢"结构,不套用区间套
背驰判定,改为两条轻量确认——信号日窗口内 30m 出现**底分型**,且该
底分型低点(回调低点)**不破一买低点**(允许轻微刺破,`pierce_tol` 内
算 weak)。状态:confirmed / weak / broke(破一买低点,二买结构失效)/
stale / no_data,附带 `fx_dt/low30/dist_b1`。

**事件桥接**:`confirm_buy3_event_30m(evt, bars30, ...)` 与
`confirm_sell3_event_30m(evt, bars30, ...)` 直接接收 `chan.bs` 模块
输出的买卖点事件 dict(自动取 `zs_zd/zs_zg/dt` 字段),省去手工拆字段
的胶水代码。

## 兼容性

- Python 3.6+ 语法(无 walrus / dataclasses / f-string 自描述等 3.7+ 特性);
- pandas 0.23+ API(无 `to_numpy` / `to_markdown` 等新 API);
- 依赖:`numpy>=1.14`、`pandas>=0.23`;
- 全模块带 3.6 兼容的 typing 注解(`typing.List/Dict/Optional/...`),
  docstring 含参数逐条说明、返回结构与规则边界,`chan.__all__` 列出
  全部顶层导出。

## 测试

仓库自带测试(62 个):`chan.bars/fx/bi/xd/zs/bc/bs` 与 `chan.cross30` 的
单元测试,覆盖合成行情的分型边界、成笔间隔(含 min_k_gap 参数)、
中枢延伸/新生、背驰判定、三类买卖点字段与力度过滤参数、
三买三卖/二买 30m 确认的 confirmed/broke/stale 等路径,以及
顶层 API 导出完整性:

```bash
pip install . && python -m unittest discover -s tests -p 'test_*.py'
```

CI(GitHub Actions)在 Python 3.10 / 3.13 双版本运行同一套测试,打 `v*` tag
后自动构建并发布 GitHub Release 与 PyPI。

## 版本历史

- **0.1.7**(当前 PyPI 版):通用完善——`chan` 顶层导出全部公开 API
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
