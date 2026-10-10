# -*- coding: utf-8 -*-
"""已确认次级走势的三类点条件接口(课20, 与课101二三合一配合)。

课20: 次级走势向上离开中枢后的首次回试低点不破ZG是三买; 向下
离开后的首次回抽高点不升破ZD是三卖。必须是第一次, 不设力度比。
走势完成需要更低级别证据(课20末段实例), 不以一笔替代次级走势。
本模块消费外部已确认走势, 不从K线自动推断完成、级别或因果关系。
"""
from collections import namedtuple

from chan.bars import _bar_time
from chan.second import ConfirmedCenter, _move_groups, _price, _text, _time


class ThirdPointContext(namedtuple('ThirdPointContextBase',
                                  'context_id level sub_level center')):
    """一个因果中枢的完整后续次级走势上下文; center须为ConfirmedCenter。

    level与center.level相同, sub_level是调用方明确指定的相邻下级。
    moves必须包含自中枢形成起的完整可见后续走势, 不截取第二次回试
    冒充首次。保守口径要求中枢确认时间不晚于离开走势起点; 若调用方
    只能提供更晚确认信息, 本接口不追认该次离开。一个中枢至多一事件。
    """
    __slots__ = ()


class ThirdPoint(namedtuple('ThirdPointBase',
                           'kind context_id center_id level dt price confirmed_dt leave_move_id pull_move_id')):
    """dt为回试端点, confirmed_dt为全部条件证据的最晚可用时间。"""
    __slots__ = ()

    def to_dict(self):
        out=dict(self._asdict())
        for key in ['dt','confirmed_dt']:
            out[key]=str(out[key])
        return out


def find_third_points(moves, contexts, as_of):
    """按观察时点判定首离开/首回试, 上下镜像且触沿允许(课20)。

    moves是ConfirmedMove序列, 校验规则与find_second_points一致。
    未来确认的价格/中枢边界不读取。离开走势整体经过中枢区间且
    结束于ZG上/ ZD下; 紧邻首个相反方向走势的整个区间守沿才成立。
    首回试破沿后本次离开失败, 不跳过首回试挑选第二次; 重新进中枢
    后发生新的离开可以重新检查。已成立后不重复发同一中枢事件。
    不使用未来扩展后的中枢边界; 缺级别邻接/完成证据不能自动补齐。
    """
    cutoff, kind=_bar_time(as_of)
    groups=_move_groups(moves,cutoff,kind)
    out,ids,centers=[],set(),set()
    for context in contexts:
        if not isinstance(context,ThirdPointContext) or not isinstance(context.center,ConfirmedCenter):
            raise ValueError('须ThirdPointContext及ConfirmedCenter')
        center=context.center
        known=_time(center.confirmed_dt,kind)
        if known>cutoff:
            continue
        for value in [context.context_id,context.level,context.sub_level,center.center_id]:
            _text(value)
        if context.context_id in ids or center.center_id in centers:
            raise ValueError('可见上下文和中枢身份须唯一')
        ids.add(context.context_id);centers.add(center.center_id)
        if context.level!=center.level or context.level==context.sub_level:
            raise ValueError('目标级别须与中枢相同且不同于次级别')
        if not _price(center.zd)<_price(center.zg):
            raise ValueError('中枢须ZD<ZG')
        group=groups.get(context.sub_level,[])
        for leave,pull in zip(group,group[1:]):
            if _time(leave.start_dt,kind)<known:
                continue
            if leave.low>center.zg or leave.high<center.zd:
                continue  # 完全在中枢外的继续走势不是从此中枢的新离开。
            up=leave.direction=='up'
            if not (leave.end_price>center.zg if up else leave.end_price<center.zd):
                continue
            if leave.end_dt!=pull.start_dt or leave.end_price!=pull.start_price:
                raise ValueError('离开与首次回试时间和价格须连续')
            if leave.direction==pull.direction:
                continue  # 尚无首个反向回试, 不跳到后续单元凑相邻配对。
            holds=pull.low>=center.zg if up else pull.high<=center.zd
            if not holds:
                continue  # 首回试失败; 不能跳过它使用第二次回抽。
            confirmed=max([center.confirmed_dt,leave.confirmed_dt,pull.confirmed_dt],
                          key=lambda dt:_time(dt,kind))
            out.append(ThirdPoint('buy3' if up else 'sell3',context.context_id,center.center_id,
                                  context.level,pull.end_dt,pull.end_price,confirmed,
                                  leave.move_id,pull.move_id))
            break  # 中枢第一个成立的三类点, 不按延续回抽重复输出。
    return sorted(out,key=lambda point:_time(point.confirmed_dt,kind))
