# 从 0.7.x / 0.8.x 迁移到1.x（0.13.x）

适用：冻结研究脚本或聚宽 Notebook 仍钉在 0.7.x/0.8.x，需要评估升级
到 0.13.x 的调用方。版本事实唯一登记在 [CHANGELOG.md](CHANGELOG.md)；
本文件按影响面组织升级要点。

## 升级原则

1. **冻结脚本不自动升级**。已交付研究脚本钉住原版本
   （`chan-lun-core==0.7.5` 之类），升级 = 新版本脚本另行立项，
   不改写既有产物。
2. **升级前先留指纹**。在旧版本环境对同一份行情运行 §指纹示例，
   存档 JSON；新版本环境运行同一脚本对比，差异逐项对应下表与
   CHANGELOG"行为变化"条目。
3. **逐前缀比较，不只比最终结果**。结构尾部会随新数据修订，
   对比应在相同输入前缀上进行（README §5）。

## 行为变化时间线（按影响面）

| 影响面 | 版本 | 变化与确认方式 |
|---|---|---|
| 线段识别 | 0.6.1/0.7.0/0.7.5/0.7.7/0.7.8/0.7.9 | 多次线段修正改变线段划分与完成时间；线段级中枢/背驰随之变化。最后一次线段行为变化在 0.7.9，0.7.10 起至 0.13.x 线段口径一致 |
| 实际可用时间 | 0.7.0 起 | `analyze_available` 等门控入口要求 bar 带 `closed_dt`/`available_dt` 元数据；不带门控的入口不受影响 |
| `find_ma_points` | 0.12.1 | 第一类候选（post_kiss_divergence）前置吻由"湿吻"放开为"飞/唇/湿吻"：旧候选全部保留，新增前置吻候选；收据见 CHANGELOG 0.12.1 |
| `classify_bc_turn` | 0.12.2 | 转折判据修正——课29"是否重新回抽最后一个中枢里"以回抽端点进入 [ZD,ZG] 为界（触及边界即算）：反弹高点落在 [ZD,ZG)/回落低点落在 (ZD,ZG] 由 `expansion` 改判 `turn`（`candidates` 随之非空）；收据 `validation/turn-0122-behavior-diff-*.json` |
| `Gap.to_dict()` | 0.13.1 | `dt_a`/`dt_b` 由原类型透传改为统一 `str()`（`None` 保持）；直接消费该 dict 的下游注意类型变化；`Gap` 补 `__slots__` 禁止动态属性 |
| `StrictDivergence` | 0.10.2 | namedtuple 新增 `force_method`/`force` 字段；按位置解包的代码需要改按字段名访问 |

0.9.x—0.11.x 的真实标注与因果接口、0.13.2 的 API.md 契约均为新增，
不改变既有输入的输出（各版 CHANGELOG 未标"行为变化"）。

## 指纹示例（可运行，0.7.0+ 与 0.13.x 通用）

在**旧版本环境**与**新版本环境**各运行一次，对比输出摘要；换上
你自己的行情 `df` 即为真实迁移核对：

```python
# migration_fingerprint.py — 依赖: numpy/pandas + chan-lun-core
import hashlib
import json
import math
from datetime import datetime, timedelta

import pandas as pd
import chan

closes = [20.0 + 3.0 * math.sin(i / 6.0) + i / 80.0 for i in range(160)]
df = pd.DataFrame({
    "open": closes, "close": closes,
    "high": [price + 0.3 for price in closes],
    "low": [price - 0.3 for price in closes],
    "volume": [1000.0] * len(closes),
}, index=[datetime(2025, 1, 1) + timedelta(days=i) for i in range(160)])

bars = chan.normalize_bars(df)
result = chan.analyze_bars(bars)
snapshot = json.dumps(result.to_dict(), sort_keys=True,
                      ensure_ascii=False, allow_nan=False)
print("version:", chan.__version__)
print("sha256:", hashlib.sha256(snapshot.encode("utf-8")).hexdigest())
print("bis:", len(result.bis), "xds:", len(result.xds),
      "bi_zss:", len(result.bi_zss))
with open("fingerprint-{}.json".format(chan.__version__), "w") as f:
    f.write(snapshot)
```

两个环境的 `sha256` 一致即基础链输出一致；不一致时按上表定位
（先看线段数，再看笔级中枢），并回到 CHANGELOG 对应版本的
"行为变化"条目核对是否为已登记修正。写入文件名带版本号，新旧
指纹并存，不互相覆盖。

## 聚宽 Notebook 注意

- 聚宽镜像同步延迟与离线安装方式见 README §2；版本不可获取不是
  算法错误。
- Notebook 内核已导入过 `chan` 时，安装/升级后必须重启内核。
- 信号目录与输出路径约定（绝对路径、候选链）沿用项目工作区规范，
  与本包无关。

## 冻结脚本与旧版本获取

- Release/PyPI 已核验、可用版本号直接钉住的版本：0.5.0、0.6.0、
  0.7.0—0.7.5、0.8.0、0.9.0、0.9.1、0.10.0（各版 CHANGELOG
  "发布状态"为准）。
- 其余版本（0.7.6—0.7.10、0.9.2—0.9.11、0.10.1—0.10.6、
  0.11.x、0.12.x、0.13.x）仅本地提交或本地 tag/推送，无独立
  Release/PyPI 产物；冻结脚本应钉住已核验发布版本，或随外层
  工作区交付源码。
- 已提交的历史文件可从 Git 查回；升级不删除旧产物。
