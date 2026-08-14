# chan-lun

缠论(缠中说禅理论)量化核心库 —— 分型 / 笔 / 线段 / 中枢 / 背驰 / 三类买卖点,
外加日线信号 → 30 分钟级别的跨级别共振确认(区间套)。

纯 Python 实现,**不依赖任何行情接口**:输入标准化 bar 序列,输出结构对象与信号。
只依赖 numpy(背驰计算)与 pandas(bars 归一化辅助)。

- 发行名:**chan-lun**(PyPI 上 `chan` 已被一个 Python 2 时代的库占用)
- import 名:`chan`
- 许可证:MIT

## 安装

从 GitHub Release 安装(推荐;每次打 `v*` tag,CI 自动构建并发布 wheel):

```bash
pip install https://github.com/lushi78778/chan-lun/releases/download/v0.1.0/chan_lun-0.1.0-py3-none-any.whl
```

或源码安装:

```bash
pip install git+https://github.com/lushi78778/chan-lun.git
```

要求 Python >= 3.6、numpy >= 1.14、pandas >= 0.23
(与聚宽研究环境 3.6.7 / numpy 1.14.6 / pandas 0.23.4 对齐,新版同样兼容)。

## 数据约定

所有模块的输入/输出都是**纯 Python 结构**(list of dict / 简单对象),
与数据来源无关:

```python
# 标准 bar: 按时间升序的 dict 列表
bars = [
    {"dt": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...},
    ...
]
```

`chan.bars.normalize_bars` 负责把聚宽 `get_price`/`get_bars` 等返回的
DataFrame 转成标准 bar 序列(列名可配置)。

## 模块与流水线

| 模块 | 功能 | 主要入口 |
|---|---|---|
| `chan.bars` | 行情归一化 | `normalize_bars`, `bars_to_df` |
| `chan.fx` | 包含处理 + 分型 | `remove_includes`, `find_fxs` |
| `chan.bi` | 笔识别 | `find_bis`, `chan_fx_bi` |
| `chan.xd` | 线段(特征序列两种标准) | `find_xds`, `chan_bis_xds` |
| `chan.zs` | 中枢与走势类型 | `find_zs`, `classify_trend` |
| `chan.bc` | 背驰(MACD 辅助) | `macd_series`, `find_trend_bc`, `find_pan_bc` |
| `chan.bs` | 三类买卖点 | `find_buy_points`, `find_sell_points` |
| `chan.cross30` | 30m 跨级别共振确认 | `confirm_buy3_30m`, `confirm_sell3_30m` |

最小示例(完整管线):

```python
from chan.bars import normalize_bars
from chan.bi import chan_fx_bi
from chan.xd import chan_bis_xds
from chan.zs import find_zs
from chan.bc import macd_series, find_trend_bc
from chan.bs import find_buy_points

bars = normalize_bars(df)          # df -> 标准 bar 列表
bis = chan_fx_bi(bars)             # 分型 -> 笔
xds = chan_bis_xds(bars)           # 笔 -> 线段
zss = find_zs(xds)                 # 线段 -> 中枢
dif, dea, hist = macd_series(bars) # MACD
bc = find_trend_bc(bis, zss, bars) # 趋势背驰
buys = find_buy_points(bis, zss)   # 三类买点
```

跨级别确认(日线三买 → 30 分钟底背驰 + 守中枢上沿):

```python
from chan.cross30 import confirm_buy3_30m

r = confirm_buy3_30m(bars30, zd=zg_of_day_zs, zg=zg_of_day_zs, signal_dt=...)
# r["status"] in {"confirmed", "weak", "no_exhaustion", "broke", "stale", "no_data"}
```

## 与聚宽(JoinQuant)研究脚本的关系

本包是作者聚宽(JoinQuant)研究项目的算法内核:该项目(私有)的单文件
Notebook 脚本由内部 `tools/build_*.py` 从本包拼接生成,直接复制进聚宽
研究 Notebook 即可运行(聚宽 3.6 环境无需 pip 安装本包)。本包独立发布,
与聚宽环境互不依赖。

## 兼容性

- Python 3.6+ 语法(无 walrus / dataclasses / f-string 自描述等 3.7+ 特性)
- pandas 0.23+ API(无 to_numpy / to_markdown 等新 API)

## 免责声明

本库仅用于研究与学习,输出不构成任何投资建议。

## 许可证

MIT,见 [LICENSE](LICENSE)。
