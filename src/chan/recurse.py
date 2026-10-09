# -*- coding: utf-8 -*-
"""
chan.recurse —— 级别递归 f2(课 35/63/84/102)

理论依据: 《教你炒股票 35: 给基础差的同学补补课》递归定义:
  "三个连续的最低级别走势类型之间, 如果发生重叠关系, 也就是三个
   最低级别走势类型所分别经过的价格区间有交集, 那么就形成了高一级
   别的缠中说禅中枢。有了该中枢定义, 依照在最低级别上的分类方法,
   同样在高级别上可以把走势进行完全的分类, 而这个过程可以逐级
   上推"——中枢与走势类型的循环定义由级别解开(课 35 开篇)。
  "依次保持着第 N 个中枢比 N-1 个高的状态, 那么就是上涨走势类型
   的延续; ......第 N 个中枢不再高于、即等于或低于第 N-1 个的状态,
   才可说这最低级别的上涨结束。"

《教你炒股票 84》递归函数两段式:
  "一般的递归定义, 由两部分组成, 一、f1(a0)=a1; 二、f2(an)=an+1;
   ......可以用分型、线段这样的函数关系去构造最低级别的中枢、走势
   类型, 也就是一中的 a1, 而在二中, 也就是最低级别以上, 可以用
   另一套规则去定义"——f1 = 分型/笔/线段(chan.fx/chan.bi/chan.xd),
   f2 = 本模块 level_up。

《教你炒股票 102》记数法:
  "任何走势, 都可以唯一地表示为 a1A1+a5A5+a30A30 的形式"——
  level_up 可逐级复合: level_up(level_up(xds)) 依次升大级别,
  自同构性结构(课 84)保证各级别同构。

与 chan.decompose.same_level_decompose 的关系(重要):
  两者是同一自同构状态机的两种切分语义, 输入单元都只需具备
  direction/start_dt/end_dt/high/low(XD 段或 MoveType 均可):
  - same_level_decompose(课 38/39): 该级别不定义中枢延伸——单元与
    中枢区间重叠即切分完成(延伸 6 段 = 两个盘整的连接);
  - level_up(课 17/20/35 标准递归): 允许中枢延伸——单元与中枢区间
    重叠归并进当前走势类型继续生长, 仅"离开后回抽进中枢区间"
    (课 39 A3 跌回, 构成高一级别中枢情形)或第二中枢与进入方向
    相反时才完成切分。

递归规则(逐单元状态机, 唯一, 无未来函数):
  1. 高一级别中枢 = 三个连续次级别走势类型价格区间有交集
     (课 35): 区间交集 [max(低点), min(高点)] 非空; 中枢前的单元
     全部归入进入段 a(课 39 a+A 模型同款, a 可为空/多单元)。
  2. 中枢后的单元逐个检查: 与最后中枢区间 [ZD, ZG] 重叠(端点触及
     也算) = 中枢延伸(课 17/20), 归并进当前走势类型继续; 完全
     不重叠 = 离开单元(与 track_zs 中枢完成判定同口径)。
  3. 离开后回抽进中枢区间 = 课 39"A3 跌回 a 高点, A1A2A3 构成高
     一级别中枢"情形: 当前走势类型完成于回抽单元前一个单元
     (含离开单元), 回抽单元开启下一走势类型。
  4. 离开单元起的三单元重叠组构成第二中枢(离开单元参与下一中枢
     构造, 与 track_zs 口径一致), 按其区间相对前中枢的整体位置
     判定(严格不等式, 与 zs.zs_relation 一致): 上移 = 上涨延续 /
     下移 = 下跌延续, 与进入方向同向则吸收进当前走势类型(课 35
     N 个中枢依次保持高低状态的延续), 方向相反则当前走势类型
     完成于离开单元前, 离开单元归下一走势类型。
  5. 第二中枢与前中枢区间部分重叠的情形在逐单元扫描下不可达
     (可证: 区间重叠则其构成单元中必有一个与前中枢重叠, 逐单元
     检查先触发规则 2 延伸分支), 代码保留防御分支。
  6. 单元耗尽仍无法确认结束时 complete=False(当下视角); 剩余
     单元不足以构成中枢时标记 incomplete。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, List, Optional

from chan.decompose import (MoveType, _build, _find_center, _overlap3,
                            _overlap_center, _range3)


def _unit_dir(unit: Any) -> Optional[str]:
    """进入单元的方向: XD 取 direction('up'/'down');

    MoveType 取进入方向 direction, 为 None 时退回 kind(up/down);
    盘整/残段且无进入方向时为 None。
    """
    d = getattr(unit, "direction", None)
    if d in ("up", "down"):
        return d
    k = getattr(unit, "kind", None)
    if k in ("up", "down"):
        return k
    return None


def level_up(units: List[Any]) -> List[MoveType]:
    """级别递归 f2: 次级别单元序列 -> 高一级别走势类型序列

    参数:
        units: 次级别单元序列(XD 段或 MoveType 走势类型), 每个单元
               只需具备 direction / start_dt / end_dt / high / low
               属性(方向交替非必需——盘整+盘整连接时相邻走势类型
               方向可同)。可逐级复合:
               level_up(level_up(find_xds(bis))) 依次升大级别。

    返回:
        List[MoveType], 相邻项的单元区间无缝衔接(前项 seg_end + 1 =
        后项 seg_start), 覆盖全部输入单元; 末项(或唯一项)常为
        complete=False(当下视角走势尚未确认结束)。

    唯一性: 分解每一步只用当前单元与已形成中枢, 无未来函数; 任意
        前缀的分解结果中已确认项(complete=True)在更长前缀下保持
        不变。
    """
    n = len(units)
    out: List[MoveType] = []
    if n == 0:
        return out
    pos = 0
    while pos < n:
        # --- 阶段 A: 定位高一级别中枢(最早三单元重叠组), 前为进入段 a ---
        j = _find_center(units, pos)
        if j is None:
            # 剩余单元不成中枢: 残段, 不构成走势类型
            out.append(_build(units, pos, n - 1, [], None,
                              "incomplete", False))
            break
        # 进入段 a = units[pos..j-1](课 39 a+A 模型, a 可为空/多单元)
        entry_dir = _unit_dir(units[pos]) if j > pos else None
        centers = [_range3(units, j)]
        kind = "consolidation"
        k = j + 3      # 中枢后逐单元扫描位置
        leave_start: Optional[int] = None   # 离开单元索引(待确认)
        while True:
            if k >= n:
                # 单元耗尽: 含中枢但离开后走势未确认结束
                out.append(_build(units, pos, n - 1, centers,
                                  entry_dir, kind, False))
                pos = n
                break
            unit = units[k]
            center = centers[-1]
            if _overlap_center(unit, center):
                if leave_start is None:
                    # 与最后中枢区间重叠且未离开过: 中枢延伸
                    # (课 17/20, 与同级别分解课 38"重叠即切分"的
                    # 最大差异)——归并进当前走势类型继续生长
                    k += 1
                    continue
                # 离开后回抽进中枢区间: 课 39 A3 跌回 a 高点,
                # A1A2A3 构成高一级别中枢情形——当前走势类型完成于
                # 前一单元(含离开单元), 回抽单元开启下一走势类型
                out.append(_build(units, pos, k - 1, centers,
                                  entry_dir, kind, True))
                pos = k
                break
            # unit 与最后中枢区间完全不重叠: 离开单元(track_zs 同口径)
            if leave_start is None:
                leave_start = k
            elif k - 2 >= leave_start and _overlap3(units, k - 2):
                # 离开单元起的三单元重叠组恰于本单元完成(离开单元
                # 参与新中枢构造, 与 track_zs "离开段参与下一中枢"
                # 同口径)
                z2 = _range3(units, k - 2)
                if z2[0] > center[1]:
                    new_dir = "up"    # 新中枢整体在前中枢之上: 上涨延续
                elif z2[1] < center[0]:
                    new_dir = "down"  # 新中枢整体在前中枢之下: 下跌延续
                else:
                    # 第二中枢与前中枢区间部分重叠(理论不可达, 规则 5
                    # 防御分支): 按反向处理, 完成于离开单元前
                    new_dir = None
                if new_dir is None or \
                        (entry_dir is not None and entry_dir != new_dir):
                    # 方向相反: 当前走势类型完成于离开单元前,
                    # 离开单元归下一走势类型(作为其进入段 a 的一部分)
                    out.append(_build(units, pos, leave_start - 1, centers,
                                      entry_dir, kind, True))
                    pos = leave_start
                    break
                # 同向延续要求进入方向一致; a 为空时由中枢移动方向补定
                if entry_dir is None:
                    entry_dir = new_dir
                # 趋势延续: 吸收第二中枢, 继续生长(课 35: 依次保持
                # 第 N 个中枢比第 N-1 个高的状态 = 上涨延续)
                kind = new_dir
                centers.append(z2)
                leave_start = None
            k += 1
    return out
