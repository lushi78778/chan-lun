#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""固定样本性能基线工具: 代表性日线/分钟管线与回放的耗时、规模与内存。

用法(源码树或安装环境均可):
    python tools/benchmark.py --data "dir/*.parquet" --ts-code 510050.SH \
        --label 510050-daily --adj --out baseline.json

- ``--data`` 支持通配(多分区 parquet); 按扩展名选 parquet/csv 读取。
- ``--time-col`` 提供时按 日期+时间 合成 datetime 文本(分钟数据)。
- ``--adj`` 以 adj_factor 前复权 OHLC(缺列时报错, 不静默跳过)。
- ``--replay-step 0`` 表示自动取 ceil(n/120); ``--replay-limit`` 在
  均匀网格上再截取至多 N 个观察点。
- 输出 JSON: 版本/环境、样本规模、结构计数、分析与回放耗时、
  峰值内存。基线是测量环境事实, 不构成性能保证; 性能优化只有在
  确实阻碍使用时进行, 优化前后必须逐前缀等价。
"""

import argparse
import glob
import json
import math
import os
import platform
import resource
import sys
import time


def _peak_rss_mb():
    """进程峰值 RSS(MB); darwin 的 ru_maxrss 单位是字节, linux 是 KB。"""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024.0 * 1024.0)
    return peak / 1024.0


def _load_frames(pattern, ts_code):
    import pandas as pd

    paths = sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit("no files match: {}".format(pattern))
    frames = []
    for path in paths:
        if path.endswith(".csv"):
            frame = pd.read_csv(path)
        else:
            frame = pd.read_parquet(path)
        if ts_code and "ts_code" in frame.columns:
            frame = frame[frame["ts_code"] == ts_code]
        if frame.shape[0]:
            frames.append(frame)
    if not frames:
        raise SystemExit("no rows after ts_code filter: {}".format(ts_code))
    return pd.concat(frames, ignore_index=True)


def _build_data(frame, dt_col, time_col, vol_col, adjusted):
    """行情宽表 -> normalize_bars 可直接消费的 dt/OHLCV 表。"""
    dt = frame[dt_col].astype(str)
    if time_col and time_col in frame.columns:
        dt = dt + " " + frame[time_col].astype(str)
    elif time_col:
        raise SystemExit("time column missing: {}".format(time_col))
    factor = None
    if adjusted:
        if "adj_factor" not in frame.columns:
            raise SystemExit("--adj given but adj_factor column missing")
        factor = frame["adj_factor"].astype(float)
    data = {"dt": dt, "volume": frame[vol_col].astype(float)}
    for col in ("open", "high", "low", "close"):
        values = frame[col].astype(float)
        data[col] = values * factor if factor is not None else values
    import pandas as pd

    return pd.DataFrame(data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="chan 固定样本性能基线(耗时/规模/内存)")
    parser.add_argument("--data", required=True,
                        help="数据文件 glob(多分区 parquet 或 csv)")
    parser.add_argument("--ts-code", default="", help="按 ts_code 过滤")
    parser.add_argument("--dt-col", default="trade_date")
    parser.add_argument("--time-col", default="", help="分钟数据的时刻列")
    parser.add_argument("--vol-col", default="vol")
    parser.add_argument("--adj", action="store_true",
                        help="以 adj_factor 前复权 OHLC")
    parser.add_argument("--drop-invalid", action="store_true",
                        help="剔除 OHLC 包络/非正价格违规行并计数"
                             "(源数据保留不修, 只排除出基准样本)")
    parser.add_argument("--replay-step", type=int, default=0,
                        help="0=自动 ceil(n/120)")
    parser.add_argument("--replay-limit", type=int, default=0,
                        help="均匀网格上至多保留 N 个观察点(0=不限)")
    parser.add_argument("--label", default="sample")
    parser.add_argument("--out", default="", help="JSON 输出路径(缺省打印)")
    args = parser.parse_args(argv)

    # 源码树运行时优先 src 布局源码, 不落到已安装的旧版本。
    package_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(package_root, "src"))
    import chan  # noqa: E402

    import pandas as pd  # noqa: E402

    frame = _load_frames(args.data, args.ts_code)
    data = _build_data(frame, args.dt_col, args.time_col,
                       args.vol_col, args.adj)
    dropped_invalid = 0
    if args.drop_invalid:
        valid = ((data["low"] > 0) & (data["high"] > 0)
                 & (data["low"] <= data["open"]) & (data["low"] <= data["close"])
                 & (data["open"] <= data["high"]) & (data["close"] <= data["high"]))
        dropped_invalid = int((~valid).sum())
        data = data[valid]

    t0 = time.perf_counter()
    bars = chan.normalize_bars(data, dt_col="dt")
    normalize_seconds = time.perf_counter() - t0
    if not bars:
        raise SystemExit("no bars after normalize(输入为空或全为停牌)")

    t1 = time.perf_counter()
    result = chan.analyze_bars(bars)
    analyze_seconds = time.perf_counter() - t1

    step = args.replay_step or max(1, int(math.ceil(len(bars) / 120.0)))
    observations = [bar["dt"] for bar in bars[step - 1::step]]
    if args.replay_limit and len(observations) > args.replay_limit:
        stride = len(observations) / float(args.replay_limit)
        picked = []
        index = 0.0
        while len(picked) < args.replay_limit:
            picked.append(observations[int(index)])
            index += stride
        observations = picked
    t2 = time.perf_counter()
    snapshots = 0
    for _ in chan.replay_bars(bars, observations=observations):
        snapshots += 1
    replay_seconds = time.perf_counter() - t2

    payload = {
        "label": args.label,
        "chan_version": chan.__version__,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "system": platform.system(),
        "machine": platform.machine(),
        "ts_code": args.ts_code,
        "adjusted": bool(args.adj),
        "n_rows_raw": int(frame.shape[0]),
        "n_bars": len(bars),
        "dropped_invalid_rows": dropped_invalid,
        "dt_first": bars[0]["dt"],
        "dt_last": bars[-1]["dt"],
        "structures": {
            "new_bars": len(result.new_bars),
            "fxs": len(result.fxs),
            "bis": len(result.bis),
            "xds": len(result.xds),
            "bi_zss": len(result.bi_zss),
            "xd_zss": len(result.xd_zss),
        },
        "normalize_seconds": round(normalize_seconds, 3),
        "analyze_seconds": round(analyze_seconds, 3),
        "replay_step": step,
        "replay_snapshots": snapshots,
        "replay_seconds": round(replay_seconds, 3),
        "replay_seconds_per_snapshot": (
            round(replay_seconds / snapshots, 4) if snapshots else None),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print("written: {}".format(args.out))
    else:
        print(text)


if __name__ == "__main__":
    main()
