# -*- coding: utf-8 -*-
"""
chan.lineage —— 中枢演化谱系(课 20/35, 计划 §11.7)

理论依据: 《教你炒股票 20》中枢延伸与 Z 走势段:
  "中枢的延伸等价于任意区间[dn,gn]与[ZD,ZG]有重叠"(定理一);
  "把这些与中枢方向一致的次级别走势类型称为Z走势段......定义四个
  指标 GG=max(gn)，G=min(gn)，D=max(dn)，DD=min(dn)"(ZG/ZD 取
  前两个 Z 段: ZG=min(g1,g2), ZD=max(d1,d2));
  中心定理二: "后GG<前DD等价于下跌及其延续; 后DD>前GG等价于上涨
  及其延续; 后ZG<前ZD且后GG>=前DD, 或后ZD>前ZG且后DD<=前GG,
  则等价于形成高级别的走势中枢"。

《教你炒股票 35》递归: 三个连续次级别走势类型区间有交集即构成
高一级别中枢, 本模块在 confirm_level_up 同款可见前缀与到达批
口径上重放该状态机(recurse._level_up_traced), 不复制或改变
公开切分规则。

事件模型(0.11.2 范围):
  - formed: 中枢首现, 冻结首三段交集 [ZD,ZG](端点连续下与课 20
    ZG=min(g1,g2)/ZD=max(d1,d2) 等价)、Z 段极值 GG/DD、组成与
    证据到达时刻;
  - extended: 延伸(课 20 定理一), 保留形成身份, 产生新快照版本,
    [ZD,ZG] 不变, GG/DD 随 Z 段增长;
  - expanded_up: 升级(课 20 开篇"一个走势中枢完成前，其波动触及
    上一个走势中枢或延伸时的某个瞬间波动区间，由此产生更大级别
    的走势中枢", 与中心定理二 higher_level 分支同一触发): 新中枢
    取 upper_level 新身份, source_center_ids=参与波动重叠的前后
    连续同级别中枢; 上层中枢 zd/zg=两来源波动的交集
    [max(前DD,后DD), min(前GG,后GG)](higher_level 下非空可证:
    形成三单元首单元必为 Z 段且触及本中枢, 故后DD<=后ZG<前ZD
    <=前GG 与后GG>=前DD 保证交集非空), gg/dd=来源波动并集口径,
    组成为前中枢全程至后中枢首三段; 定理二为等级价条件, 递归
    复合(三个同级别走势类型重叠)的严格验证不在此版本。
  - 新生关系: 非首个中枢的 formed 事件按课 20 中心定理二记录与前
    中枢(形成当时最新快照)的关系 down_continue/up_continue/
    higher_level/overlap; 前中枢此后延伸不回改已冻结关系。
  - reorganized: 重组(课 69 "九段可延伸成5分钟中枢, 可不等于5分钟
    中枢就一定是九段" + 课 70 多样性分解原则/结合律): 同级别中枢
    延伸跨过 9 个组成单元时, 连续三组三单元(各组看成一次级别走势,
    区间为组内极值并集)的交集构成高一级别中枢(课 35 三重叠); 新
    中枢取 upper_level 新身份并携带 basis='nine_segment' 标记与
    source_center_ids(原同级别中枢), 旧身份不删除且此后继续延伸
    (课 20 级别延续定理一)。首九单元冻结为上层形成快照, zd/zg 为
    三组区间交集, gg/dd 为首三次级别走势极值(即首九单元极值);
    中枢级别由递归层级分辨(课 69), 不是段数。上层中枢此后的延伸
    与课 70 "等走势走出最自然的选择再继续更合理的划分"的再划分
    无机械判据, 不在本版本, 保留输入前提。

定序: 事件按到达批时刻排序; 同一批内 formed 先于 extended 先于
expanded_up 先于 reorganized, 再按中枢身份字典序。同一时刻多单元
整批进入, 不虚构批内不同到达时间。事件不回写: 更晚 as_of 下已产
生事件的种类、身份、版本与顺序不变, 更早证据不因后到单元改变
归属。

边界: 无三单元重叠不成中枢不产生事件; 零宽中枢(交集退化为一点)
照常登记; 不足三单元或全部未确认返回空谱系; 可见单元须为连续
前缀, 乱序到达拒绝(与 confirm_level_up 同口径)。组成方向不可
分辨时(盘整无向)GG/DD 退化为全组成单元极值口径, 显式登记为
工程退化, 不冒充课 20 Z 段口径。

兼容: Python 3.6。
"""

from __future__ import print_function

from collections import namedtuple
from typing import Any, List, Optional

from chan._intervals import _range3
from chan.completion import _visible_units
from chan.recurse import _level_up_traced, _unit_dir
from chan.second import _text
from chan.strict import _identity

_FORMED = 'formed'
_EXTENDED = 'extended'
_EXPANDED_UP = 'expanded_up'
_REORGANIZED = 'reorganized'
_NINE_SEGMENT = 'nine_segment'
_KIND_RANK = {_FORMED: 0, _EXTENDED: 1, _EXPANDED_UP: 2, _REORGANIZED: 3}


class CenterVersion(namedtuple('CenterVersionBase',
                               'center_id level version zd zg gg dd '
                               'start_dt end_dt unit_ids confirmed_dt')):
    """中枢单次事件的不可变冻结快照, 数值单位沿用输入价格坐标。

    zd/zg 为形成时首三段区间交集, 形成后不再变动; gg/dd 为本版本
    Z 走势段极值(课 20 GG/DD), 组成方向不可分辨时为全组成单元
    极值口径; unit_ids 为本版本组成单元(形成版本仅首三段);
    confirmed_dt 为本快照证据到达时刻, 不早于组成单元确认时间。
    center_id 只在同一标的、输入版本及级别链内稳定, 不是全局身份。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        for key in ('start_dt', 'end_dt', 'confirmed_dt'):
            out[key] = str(out[key])
        out['unit_ids'] = list(out['unit_ids'])
        return out


class CenterEvent(namedtuple('CenterEventBase',
                             'event_id kind center_id level version '
                             'prev_center_id relation confirmed_dt '
                             'source_center_ids basis')):
    """中枢演化事件。

    kind: formed=首现(冻结首三段) / extended=延伸(新快照版本) /
      expanded_up=升级(课 20 波动重叠, 上层中枢新身份) /
      reorganized=重组(课 69 九段延伸 + 课 70 多样性分解, 上层中枢
      新身份);
    version 指向同身份快照; prev_center_id/relation 仅 formed 事件
      携带(课 20 定理二, 以前中枢形成当时最新快照为证据基准),
      extended 与 expanded_up 事件为 None; source_center_ids 仅
      expanded_up(参与波动重叠的前后连续同级别中枢身份)与
      reorganized(原同级别中枢身份)事件携带, 其余为空元组;
    basis 仅 reorganized 事件携带(多样性分解依据标记, 如
      'nine_segment'), 其余为 None。事件不回写: 更晚 as_of 下已产
      生事件的内容与顺序不变。
    """
    __slots__ = ()

    def to_dict(self):
        out = dict(self._asdict())
        out['confirmed_dt'] = str(out['confirmed_dt'])
        out['source_center_ids'] = list(out['source_center_ids'])
        return out


class CenterLineage(namedtuple('CenterLineageBase', 'centers events')):
    """中枢演化谱系。

    centers 为全部快照版本链, 按(形成顺序, 版本号)排序; events 为
    事件流, 按到达批时刻、批内 formed 先于 extended、身份字典序。
    """
    __slots__ = ()

    def to_dict(self):
        return {'centers': [item.to_dict() for item in self.centers],
                'events': [item.to_dict() for item in self.events]}

    def snapshot(self, center_id, version):
        """按身份与版本号取冻结快照, 不存在时报错, 不猜测归属。"""
        for item in self.centers:
            if item.center_id == center_id and item.version == version:
                return item
        raise KeyError('快照不存在: %s v%s' % (center_id, version))


def _snapshot(visible: List[Any], next_level: str, cid: str,
              start: int, ext: int, version: int,
              batch_dt: Any) -> CenterVersion:
    """冻结中枢快照: zd/zg 取首三段交集, gg/dd 取 Z 走势段极值。"""
    zd, zg = _range3(visible, start)
    direction = _unit_dir(visible[start])
    span = visible[start:ext + 1]
    if direction is None:
        z_units = span  # 组成方向不可分辨: 退化为全组成单元口径
    else:
        z_units = [unit for unit in span if _unit_dir(unit) == direction]
    return CenterVersion(
        cid, next_level, version, zd, zg,
        max(unit.high for unit in z_units),
        min(unit.low for unit in z_units),
        visible[start].start_dt, visible[ext].end_dt,
        tuple(unit.move_id for unit in span), batch_dt)


def _relation(prev: Optional[CenterVersion],
              cur: CenterVersion) -> Optional[str]:
    """课 20 中心定理二: 前后同级中枢波动关系; 无前中枢返回 None。"""
    if prev is None:
        return None
    if cur.gg < prev.dd:
        return 'down_continue'
    if cur.dd > prev.gg:
        return 'up_continue'
    if (cur.zg < prev.zd and cur.gg >= prev.dd) or \
            (cur.zd > prev.zg and cur.dd <= prev.gg):
        return 'higher_level'
    return 'overlap'


def _nine_range(visible: List[Any], start: int):
    """课 69/70 三×三重组: 连续三组三单元各成次级别走势
    (区间为组内极值并集), 返回三组区间交集 (zd, zg)(课 35 三重叠)。
    """
    lows = []
    highs = []
    for offset in (0, 3, 6):
        seg = visible[start + offset:start + offset + 3]
        lows.append(min(unit.low for unit in seg))
        highs.append(max(unit.high for unit in seg))
    return max(lows), min(highs)


def track_center_lineage(units, as_of, next_level, upper_level=None):
    """已确认次级单元前缀 -> 中枢事件流与快照版本链(课 20/35)。

    units/as_of/next_level 同 confirm_level_up 契约: 同级、时间及
    端点价格连续的已确认单元(ConfirmedMove 或 ConfirmedMoveType)
    连续前缀, 乱序拒绝, 未来价格不读取; next_level 为非空且不同
    于输入的递归相邻级别名, 即新中枢所属级别, 不猜 K 线周期。
    upper_level: 可选, next_level 之上的递归相邻级别名; 提供时新生
    关系为课 20 定理二 higher_level 的前后中枢额外产生 expanded_up
    升级事件(上层中枢新身份、source_center_ids 来源谱系、波动交集
    区间与确认时刻), 且同级别中枢延伸跨过 9 个组成单元时产生
    reorganized 重组事件(课 69 九段延伸 + 课 70 多样性分解, 上层
    中枢新身份、basis='nine_segment'、首九单元三×三交集快照,
    旧身份不删除); 缺省两者均不产生, 其余行为不变。级别邻接由
    调用方明示配置, 不猜 K 线周期。
    返回 CenterLineage(centers, events)。内部逐到达批重放
    recurse._level_up_traced, 复杂度 O(n^2) 最坏时间, 输入应是
    走势类型序列, 不是逐笔原始行情。无跨调用缓存。
    """
    visible, _time_kind = _visible_units(units, as_of, next_level)
    if upper_level is not None:
        _text(upper_level)
        if upper_level == next_level:
            raise ValueError('upper_level须为next_level之上的递归相邻级别名')
        if visible and upper_level == visible[0].level:
            raise ValueError('upper_level须为输入级别之上的递归相邻级别名')
    centers = []  # type: List[CenterVersion]
    events = []  # type: List[CenterEvent]
    state = {}  # center_id -> [最新版本号, 最新延伸索引, 跨度起点索引]
    latest = {}  # center_id -> 最新快照(供新生关系基准)
    prev_center_id = None  # type: Optional[str]
    reorganized = set()  # 已产生 reorganized 事件的同级别中枢身份
    for stop in range(1, len(visible) + 1):
        if stop < len(visible) and \
                visible[stop - 1].confirmed_dt == visible[stop].confirmed_dt:
            continue  # 同一到达时刻整批处理, 不虚构批内不同到达时间。
        batch_dt = visible[stop - 1].confirmed_dt
        _, traces = _level_up_traced(visible[:stop])
        batch = []  # type: List[CenterEvent]
        for spans in traces:
            for start, formed_idx, ext in spans:
                if formed_idx != start + 2:
                    raise ValueError('中枢形成索引违反首三段不变式')
                cid = _identity([next_level, visible[start].move_id])
                st = state.get(cid)
                if st is None:
                    # formed: 冻结首三段, 新生关系以当时前中枢最新快照为基准
                    first = _snapshot(visible, next_level, cid,
                                      start, formed_idx, 0, batch_dt)
                    prev = latest.get(prev_center_id) \
                        if prev_center_id is not None else None
                    relation = _relation(prev, first)
                    centers.append(first)
                    latest[cid] = first
                    batch.append(CenterEvent(
                        _identity([next_level, cid, _FORMED, 0]), _FORMED,
                        cid, next_level, 0, prev_center_id,
                        relation, batch_dt, (), None))
                    if relation == 'higher_level' and upper_level is not None:
                        # expanded_up: 课 20 开篇波动重叠产生更大级别中枢。
                        # 形成三单元首单元必为 Z 段且触及本中枢区间, 故
                        # 后DD<=后ZG<前ZD<=前GG 与后GG>=前DD 使两来源波动
                        # 交集 [max(前DD,后DD), min(前GG,后GG)] 非空。
                        upper_cid = _identity([upper_level, prev.unit_ids[0],
                                               first.unit_ids[0]])
                        span = visible[state[prev_center_id][2]:formed_idx + 1]
                        snap = CenterVersion(
                            upper_cid, upper_level, 0,
                            max(prev.dd, first.dd), min(prev.gg, first.gg),
                            max(prev.gg, first.gg), min(prev.dd, first.dd),
                            span[0].start_dt, span[-1].end_dt,
                            tuple(unit.move_id for unit in span), batch_dt)
                        centers.append(snap)
                        batch.append(CenterEvent(
                            _identity([upper_level, upper_cid, _EXPANDED_UP, 0]),
                            _EXPANDED_UP, upper_cid, upper_level, 0,
                            None, None, batch_dt,
                            (prev.center_id, first.center_id), None))
                    prev_center_id = cid
                    st = [0, formed_idx, start]
                    state[cid] = st
                if ext > st[1]:
                    # extended: 保留形成身份, 新快照版本(课 20 定理一)
                    version = st[0] + 1
                    snap = _snapshot(visible, next_level, cid,
                                     start, ext, version, batch_dt)
                    centers.append(snap)
                    latest[cid] = snap
                    batch.append(CenterEvent(
                        _identity([next_level, cid, _EXTENDED, version]),
                        _EXTENDED, cid, next_level, version,
                        None, None, batch_dt, (), None))
                    st[0], st[1] = version, ext
                elif ext < st[1]:
                    raise ValueError('中枢跨度不能收缩, 可见前缀违反连续性')
                if upper_level is not None and ext - start + 1 >= 9 \
                        and cid not in reorganized:
                    # reorganized: 课 69 九段延伸可看成高一级别中枢
                    # (课 70 多样性分解, 结合律下连续三组三单元划分),
                    # 旧身份不删除, 此后继续延伸(级别延续定理一)。
                    reorganized.add(cid)
                    zd, zg = _nine_range(visible, start)
                    # 三组交集为空不构成高一级别中枢(课 35 须有交集);
                    # 延伸前提下各组触及本级中枢区间且经共享端点连通,
                    # 可证交集非空(至多退化为一点), 空交集为防御分支。
                    if zd <= zg:
                        span9 = visible[start:start + 9]
                        upper_cid = _identity(
                            [upper_level, _NINE_SEGMENT, span9[0].move_id])
                        centers.append(CenterVersion(
                            upper_cid, upper_level, 0, zd, zg,
                            max(unit.high for unit in span9),
                            min(unit.low for unit in span9),
                            span9[0].start_dt, span9[-1].end_dt,
                            tuple(unit.move_id for unit in span9), batch_dt))
                        batch.append(CenterEvent(
                            _identity([upper_level, upper_cid,
                                       _REORGANIZED, 0]),
                            _REORGANIZED, upper_cid, upper_level, 0,
                            None, None, batch_dt, (cid,), _NINE_SEGMENT))
        batch.sort(key=lambda item: (_KIND_RANK[item.kind], item.center_id))
        events.extend(batch)
    return CenterLineage(tuple(centers), tuple(events))
