# -*- coding: utf-8 -*-
"""内部数值序列适配, 不包含力度或吻的理论判定。

均线力度与均线吻使用同一差值口径: 短线减长线, 取公共长度,
None/NaN 及不能参与数值运算的对象置 None。保持原有处理语义。
"""

from typing import Any, List, Optional


def _diff_series(short: Any, long: Any) -> List[Optional[float]]:
    """两均线差值序列; 任一侧无效(NaN/None)处置 None。

    空输入返回 []; 长度不等取公共前缀; 不做补齐或前向填充。
    """
    out: List[Optional[float]] = []
    for i in range(min(len(short), len(long))):
        s, l = short[i], long[i]
        if s is None or l is None:
            out.append(None)
            continue
        try:
            if s != s or l != l:  # NaN 无法作为均线有效数值。
                out.append(None)
            else:
                out.append(float(s) - float(l))
        except TypeError:
            out.append(None)
    return out
