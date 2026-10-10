# -*- coding: utf-8 -*-
"""安装产物冒烟: python -I tools/verify_installed.py。

不注入源码目录; 可传wheel路径或临时安装目标目录在本地验收产物。
校验安装元数据、全部导出与主组合/辅助入口, 源码算法测试另行执行。
此脚本在CI3.10/3.13使用, 不是旧聚宽运行时验证。
"""
import os
import re
import sys
from importlib.metadata import version


if len(sys.argv) > 1:
    artifact = os.path.abspath(sys.argv[1])
    if not (os.path.isdir(artifact) or os.path.isfile(artifact) and artifact.endswith(".whl")):
        raise ValueError("参数须为wheel路径或安装目标目录")
    sys.path.insert(0, artifact)

import chan

package_path = os.path.abspath(chan.__file__)
source_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
assert not package_path.startswith(source_path + os.sep), package_path
if len(sys.argv) > 1:
    assert package_path.startswith(artifact + os.sep), package_path
assert chan.__version__ == version("chan-lun-core")
with open(os.path.join(os.path.dirname(source_path), "pyproject.toml"), encoding="utf-8") as f:
    metadata = f.read().split("[project]\n", 1)[1].split("\n[", 1)[0]
assert chan.__version__ == re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M).group(1)
assert len(chan.__all__) == len(set(chan.__all__))
for name in chan.__all__:
    assert hasattr(chan, name), name
assert chan.analyze_bars([]).to_dict()["as_of"] is None
assert chan.analyze_bars([], bi_standard="106").bis == []
assert chan.classify_fx_power({"open": 10, "high": 12, "low": 9, "close": 11},
                              {"open": 12, "high": 14, "low": 11, "close": 13},
                              {"open": 12, "high": 13, "low": 10, "close": 11},
                              direction="top").power in ("weak", "neutral", "strong", "severe")
assert chan.macd_below_zero(-1, -2) is True
first = chan.FormationEvent("buy1", 1, "day")
boundary = chan.FormationEvent("buy3", 3, "day", "center-A")
assert chan.formation_state(first, "center-A", [boundary], 3).phase == "completed"
a = chan.ma_strength_class([10.0] * 233 + [12.0, 9.0], 233)
b = chan.ma_strength_class([10.0] * 235, 233)
assert (a.class_no, b.class_no) == (9, 1)
assert chan.sector_strength({"a": a, "b": b}).mean_class == 5
print("installed wheel OK:", chan.__version__, package_path)
