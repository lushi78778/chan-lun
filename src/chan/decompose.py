# -*- coding: utf-8 -*-
"""
chan.decompose —— 同级别分解(课 38/39/40)

理论依据: 《教你炒股票 38: 走势类型连接的同级别分解》原文:
  "所谓同级别分解, 就是把所有走势按一固定级别的走势类型进行分解。
   根据'缠中说禅走势分解定理', 同级别分解具有唯一性, 不存在任何
   含糊乱分解的可能。"
  "在这种同级别的分解中, 是不需要中枢延伸或扩展的概念的, 对30分钟
   来说, 只要5分钟级别的三段上下上或下上下类型有价格区间的重合就
   构成中枢。如果这5分钟次级别延伸出6段, 那么就当成两个30分钟盘整
   类型的连接, 在这种分解中, 是允许盘整+盘整情况的。"
  "在某级别中, 不定义中枢延伸, 允许该级别上的盘整+盘整连接。"

《教你炒股票 39: 同级别分解再研究》a+A 模型:
  向上情形 "A1 不能跌破 a 的低点; 如果 A2 升破 a 的高点而 A3 不跌回
  a 的高点, 可以把 a+A1+A2+A3 当成一个 a'(还是本级别走势类型);
  一般性地考虑 A3 跌破 a 的高点情况, A1、A2、A3 必然构成(高一级别)
  中枢"——对应本模块: 中枢 = 最早的次级别三段重叠组, 其前的段全部
  归入进入段 a(可为多段或空), a 与中枢合并即一个本级别走势类型的
  雏形; 中枢后段一旦跌回中枢区间, 本级别走势类型完成。

  走势类型延续(趋势): 离开段不回中枢后, 若形成第二个本级别中枢且
  其区间整体在前中枢之上/之下(严格不等式, 与 zs.zs_relation 口径
  一致), 走势类型延续为上涨/下跌; 新中枢与原中枢区间重叠 = 高级别
  中枢形成, 本级别走势类型就此完成。

《教你炒股票 40: 同级别分解的多重赋格》: 换档/多重赋格属应用层,
本模块只交付"一种分解"(基础版)。

分解规则(逐段状态机, 唯一, 无未来函数):
  1. 本级别中枢 = 次级别交替三段有价格重叠(区间交集 [max(低点),
     min(高点)] 非空); 不定义延伸——中枢固定为首个三段重叠组
     (课 38); 中枢前的段全部归入进入段 a(课 39 a+A 模型, a 可为
     空/多段, 与 XD 序列起点衔接)。
  2. 中枢后的段逐段检查: 与中枢区间重叠(端点触及也算)则当前走势
     类型完成于前一段, 重叠段开启下一单元——次级别延伸 6 段即
     两个盘整的连接, 允许盘整+盘整(课 38)。
  3. 段与中枢区间完全不重叠即离开段(与 track_zs 中枢完成判定
     同口径); 离开段参与下一中枢的构造(track_zs 口径), 后续段
     一旦回抽进中枢区间 = 课 39"A3 跌回 a 高点, A1A2A3 构成高
     一级别中枢"情形, 走势类型完成于该回抽段前一段(含离开段),
     回抽段开启下一单元。
  4. 离开段起的三段重叠组构成第二中枢, 按其区间相对前中枢的整体
     位置判定(严格不等式, 与 zs.zs_relation 一致): 上移=上涨延续 /
     下移=下跌延续, 同向(与进入段方向一致, a 为空时由中枢移动
     方向补定)则吸收进当前走势类型继续生长; 下移/上移与进入段
     方向相反则当前走势类型完成于离开段前, 离开段归下一单元。
  5. 第二中枢与前中枢区间重叠的情形在逐段扫描下不可达(可证:
     区间重叠则其构成段中必有一段与前中枢重叠, 逐段检查先触发
     规则 3), 代码保留防御分支。
  6. 剩余段不足以构成中枢(不足三段或无重叠)时标记 incomplete——
     同级别分解视角下, 无本级别中枢不成走势类型。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple


class MoveType(object):
    """同级别走势类型(课 38)

    属性:
        kind: 'up' 上涨 / 'down' 下跌 / 'consolidation' 盘整 /
              'incomplete' 残段(无本级别中枢, 不成走势类型)。
        complete: 走势类型是否已确认结束。含中枢但尚无法确认结束时
              为 False(当下视角: 离开段之后是回抽还是新中枢, 需要
              后续段确认); kind='incomplete' 时恒为 False。
        direction: 进入段方向 'up'/'down'; 进入段为空(序列起点)或
              残段时为 None。
        start_dt / end_dt: 走势类型起止时间(覆盖段首末)。
        high / low: 覆盖段的价格极值。
        seg_start / seg_end: 覆盖次级别段的索引区间(闭区间)。
        centers: 本级别中枢区间列表 [(zd, zg), ...];
              盘整恰一个, 趋势两个及以上(区间依次同向移动)。
    """

    __slots__ = ["kind", "complete", "direction", "start_dt", "end_dt",
                 "high", "low", "seg_start", "seg_end", "centers"]

    def __init__(self, kind: str, complete: bool,
                 direction: Optional[str], start_dt: Any, end_dt: Any,
                 high: float, low: float, seg_start: int, seg_end: int,
                 centers: List[Tuple[float, float]]):
        self.kind = kind
        self.complete = complete
        self.direction = direction
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.high = high
        self.low = low
        self.seg_start = seg_start
        self.seg_end = seg_end
        self.centers = centers

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"kind": self.kind,
                "complete": self.complete,
                "direction": self.direction,
                "start_dt": str(self.start_dt),
                "end_dt": str(self.end_dt),
                "high": self.high,
                "low": self.low,
                "seg_start": self.seg_start,
                "seg_end": self.seg_end,
                "centers": [[zd, zg] for zd, zg in self.centers]}


def _overlap3(segs: List[Any], j: int) -> bool:
    """次级别三段 segs[j..j+2] 是否有共同价格重叠(课 38 三段重合)"""
    a, b, c = segs[j], segs[j + 1], segs[j + 2]
    # 区间交集 [max(低点), min(高点)] 非空; 端点触及也算重叠
    return max(a.low, b.low, c.low) <= min(a.high, b.high, c.high)


def _range3(segs: List[Any], j: int) -> Tuple[float, float]:
    """三段重叠区间 (zd, zg) = [max(低点), min(高点)](调用方保证重叠)"""
    a, b, c = segs[j], segs[j + 1], segs[j + 2]
    return (max(a.low, b.low, c.low), min(a.high, b.high, c.high))


def _overlap_center(seg: Any, center: Tuple[float, float]) -> bool:
    """段区间与中枢区间是否重叠(端点触及也算, 同 zs._overlap_zs)"""
    return not (seg.high < center[0] or seg.low > center[1])


def _find_center(segs: List[Any], start: int) -> Optional[int]:
    """从 start 起找最早的三段重叠组首段索引; 无则 None"""
    j = start
    n = len(segs)
    while j + 2 < n:
        if _overlap3(segs, j):
            return j
        j += 1
    return None


def _build(segs: List[Any], p: int, q: int,
           centers: List[Tuple[float, float]],
           direction: Optional[str], kind: str,
           complete: bool) -> MoveType:
    """把覆盖段区间 [p, q] 与中枢列表装配为 MoveType"""
    if kind in ("up", "down") and len(centers) < 2:
        # 趋势要求同向两个及以上中枢(课 17 走势类型定义)
        kind = "consolidation"
    if kind == "incomplete":
        complete = False
    high = max(segs[i].high for i in range(p, q + 1))
    low = min(segs[i].low for i in range(p, q + 1))
    return MoveType(kind, complete, direction,
                    segs[p].start_dt, segs[q].end_dt,
                    high, low, p, q, list(centers))


def same_level_decompose(segs: List[Any]) -> List[MoveType]:
    """同级别分解: 次级别段序列 -> 本级别走势类型序列(课 38/39)

    参数:
        segs: 次级别段序列(如 XD 列表), 相邻段方向交替。每段只需具备
              direction / start_dt / end_dt / high / low 属性。

    返回:
        List[MoveType], 相邻项的段区间无缝衔接(前项 seg_end + 1 =
        后项 seg_start), 覆盖全部输入段; 末项(或唯一项)常为
        complete=False(当下视角走势尚未确认结束)。

    唯一性: 分解每一步只用当前段与已形成中枢, 无未来函数; 任意前缀
        的分解结果中已确认项(complete=True)在更长前缀下保持不变。
    """
    n = len(segs)
    out: List[MoveType] = []
    if n == 0:
        return out
    pos = 0
    while pos < n:
        # --- 阶段 A: 定位本级别中枢(最早三段重叠组), 其前段为进入段 a ---
        j = _find_center(segs, pos)
        if j is None:
            # 剩余段不成中枢: 残段, 不构成走势类型
            out.append(_build(segs, pos, n - 1, [], None,
                              "incomplete", False))
            break
        # 进入段 a = segs[pos..j-1](课 39 a+A 模型, a 可为空/多段)
        entry_dir = segs[pos].direction if j > pos else None
        centers = [_range3(segs, j)]
        kind = "consolidation"
        k = j + 3      # 中枢后逐段扫描位置
        leave_start: Optional[int] = None   # 离开段索引(待确认)
        while True:
            if k >= n:
                # 段耗尽: 含中枢但离开后走势未确认结束
                out.append(_build(segs, pos, n - 1, centers,
                                  entry_dir, kind, False))
                pos = n
                break
            seg = segs[k]
            center = centers[-1]
            if _overlap_center(seg, center):
                # 与最后中枢区间重叠: 或为延伸(课 38 不定义延伸,
                # 延伸段归下一单元), 或为离开后回抽回中枢(课 39
                # A3 跌回 a 高点, 构成高一级别中枢情形)——两者切点
                # 相同: 当前走势类型完成于前一段, 重叠段开启下一单元
                out.append(_build(segs, pos, k - 1, centers,
                                  entry_dir, kind, True))
                pos = k
                break
            # seg 与最后中枢区间完全不重叠: 离开段(track_zs 同口径)
            if leave_start is None:
                leave_start = k
            elif k - 2 >= leave_start and _overlap3(segs, k - 2):
                # 离开段起的三段重叠组恰于本段完成(离开段参与新中枢
                # 构造, 与 track_zs "离开段参与下一中枢"同口径)
                z2 = _range3(segs, k - 2)
                if z2[0] > center[1]:
                    new_dir = "up"    # 新中枢整体在前中枢之上: 上涨延续
                elif z2[1] < center[0]:
                    new_dir = "down"  # 新中枢整体在前中枢之下: 下跌延续
                else:
                    # 第二中枢与前中枢区间重叠(理论不可达, 规则 5
                    # 防御分支): 按反向处理, 完成于离开段前
                    new_dir = None
                if new_dir is None or \
                        (entry_dir is not None and entry_dir != new_dir):
                    # 方向相反: 当前走势类型完成于离开段前,
                    # 离开段归下一单元(作为其进入段 a 的一部分)
                    out.append(_build(segs, pos, leave_start - 1, centers,
                                      entry_dir, kind, True))
                    pos = leave_start
                    break
                # 同向延续要求进入方向一致; a 为空时由中枢移动方向补定
                if entry_dir is None:
                    entry_dir = new_dir
                # 趋势延续: 吸收第二中枢, 继续生长(后续段按与
                # 新中枢的重叠逐段检查)
                kind = new_dir
                centers.append(z2)
                leave_start = None
            k += 1
    return out
