# -*- coding: utf-8 -*-
"""课103 MACD零轴防狼术的基础布尔判据。

原文:「回避所有MACD黄白线在0轴下面的市场或股票」;
「根据自己的能力,决定一个最低的时间周期」,「直到重新站住0轴再说」。

口径: 黄白两线即DIF/DEA, 两者严格小于0才命中字面回避条件。
接触0或分处两侧为False, 缺测为None; False只表示没有同时处于负区,
不是重新站稳确认或买入许可。重新站稳的时间确认、背驰介入例外和
具体时间周期由调用方选择, 本模块不生成交易指令。指标复用bc.macd_series,
本模块不重复计算。兼容Python3.6, 仅标准库+typing。
"""
from typing import Any, List, Optional

from chan._series import _finite_number


def macd_below_zero(dif: Optional[float], dea: Optional[float]) -> Optional[bool]:
    """课103: 当前DIF和DEA是否都严格低于0。

    参数单位为与价格同尺度的MACD线值, 不是柱(hist)。两者为有限数值
    时返回bool; None/NaN/inf返回None, 不将缺测默认为通过。错误数值
    类型抛ValueError。调用方保证两值属于同一时刻、标的和周期。
    """
    d, e = _finite_number(dif), _finite_number(dea)
    if d is None or e is None:
        return None
    # 课103'黄白线在0轴下面': 两线负值的交集, 不是看柱颜色或金死叉。
    return d < 0 and e < 0


def macd_guard_series(dif: Any, dea: Any) -> List[Optional[bool]]:
    """课103判据逐棒序列; 与输入等长, 空输入返回[]。

    dif/dea为等长一维序列(list或numpy数组等), 每项语义同
    macd_below_zero; 长度不等抛ValueError。结果每棒只依赖同棒两条
    MACD线, 不从未来填充暖机或观测缺口。
    """
    if len(dif) != len(dea):
        raise ValueError("DIF与DEA长度必须一致")
    return [macd_below_zero(d, e) for d, e in zip(dif, dea)]
