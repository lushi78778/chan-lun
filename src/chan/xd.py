# -*- coding: utf-8 -*-
"""
chan.xd —— 线段的识别(特征序列两种标准)

理论依据: 课67定义、课71分界包含、课78延续与极值、课81图例更正。

  线段由至少三笔构成, 前三笔必须有重叠。
  以向上线段为例(向下对称):
    - 特征序列: 向下笔序列 X1X2X3...(每笔区间 [low, high]);
    - 标准特征序列: 特征序列按包含关系处理后;
    - 只考察顶分型(向下线段只考察底分型);
    - 第一种情况: 顶分型第一、二元素间无缺口 -> 线段在该顶分型
      的高点处结束;
    - 第二种情况: 第一、二元素间有缺口 -> 必须等"从该分型最高点
      开始的向下一笔开始的序列的特征序列(向上笔序列)出现底分型",
      线段才在该顶分型高点处结束(第二序列的分型不分一、二种情况)。

XD.mode 标记线段结束方式: 1 = 第一种情况(无缺口), 2 = 第二种情况
(缺口 + 第二特征序列确认); complete区分完成与尾部, mode不作完成标志。

课71/81边界: 假设分界前后的两元素不进行包含合并, 后侧同类元素
仍须顺序包含; 第二种情况的第二特征序列按课78完整包含, 不能用
未经包含的三个折点代替分型。笔破坏不等于线段破坏; 第一反向笔
之后的三笔若仍被包含, 须等先破其结束位置或开始位置再判破坏或
延续。第二序列确认不要求回补原段最后特征缺口, 小转大未回补的
情形仍按两种定义判断。课71最后作者示意须采用课81的5/7更正。

1.2.0可显式声明起点前提，按前驱局部证明与累计发布分别推进；
未传起点前提时保留既有工程口径。显式条件不证明自然全历史起点。

输入为固定、交替且衔接的笔, 输出组成范围与证据末笔分开; 未知
图外前段不推断。比较使用精确闭区间, 没有价差容差或量化阈值。
PDF编者“顶/底组合”的标题只描述形状, 不代替完成条件。

课78古怪线段的唯一成因: 第一种情况笔破坏未沿该笔形成线段破坏。
分析B的延续/破坏前, 必须先确认B已破坏前段。内部极值可超越净
端点; 上层把XD视为无内部结构的部件时使用low/high实际包络,
不修改start/end的分界和时间, 也不由包络虚构内部极值时间。
PDF612页编者为实用而提前选择方向的替代法不作为本模块规则。

兼容: Python 3.6。
"""

from __future__ import print_function

from typing import Any, Dict, List, Optional, Tuple
import math
from numbers import Real

from chan.bi import BI


class XD(object):
    """线段对象

    属性:
        direction: 'up' / 'down'。
        start_dt / start_value / start_index: 起点(时间/价格/无包含K线索引)。
        end_dt / end_value / end_index: 终点(时间/价格/无包含K线索引)。
        mode: 1 = 第一种情况(特征序列分型直接确认),
              2 = 第二种情况(缺口, 由第二特征序列分型确认)。
              序列末尾未完成线段的 mode 恒为 1。
        complete: 当前工程规则在给定笔前缀上的完成状态; 特殊回退仍需上下文证明。
        evidence_dt/evidence_end_index: 最后一笔证据端点(不等于行情确认时间)。
        gg / dd: 线段内部高低极值(所有构成笔的范围),
            中枢重叠计算用 high/low 属性即返回它们。
    """

    __slots__ = ["direction", "start_dt", "end_dt", "start_value",
                 "end_value", "start_index", "end_index", "mode",
                 "gg", "dd", "complete", "evidence_end_index", "evidence_dt"]

    def __init__(self, direction: str,
                 start: Tuple[Any, float, int], end: Tuple[Any, float, int],
                 mode: int, gg: Optional[float] = None,
                 dd: Optional[float] = None, complete: bool = False,
                 evidence_end_index: Optional[int] = None, evidence_dt: Any = None):
        self.direction = direction    # 'up' / 'down'
        self.start_dt, self.start_value, self.start_index = start
        self.end_dt, self.end_value, self.end_index = end
        self.mode = mode              # 1 第一种情况 / 2 第二种情况(缺口确认)
        self.complete = complete
        self.evidence_end_index = evidence_end_index
        self.evidence_dt = evidence_dt
        # 只计算线段组成笔的范围, 确认用的后续笔另记证据。
        if gg is None:
            gg = max(self.start_value, self.end_value)
        if dd is None:
            dd = min(self.start_value, self.end_value)
        self.gg = gg
        self.dd = dd

    @property
    def high(self) -> float:
        """线段内部最高点"""
        return self.gg

    @property
    def low(self) -> float:
        """线段内部最低点"""
        return self.dd

    def to_dict(self) -> Dict[str, Any]:
        """转 dict(测试/存档用), dt 统一转字符串"""
        return {"direction": self.direction,
                "start": [str(self.start_dt), self.start_value],
                "end": [str(self.end_dt), self.end_value],
                "gg": self.gg, "dd": self.dd,
                "mode": self.mode, "complete": self.complete,
                "evidence_end_index": self.evidence_end_index,
                "evidence_dt": None if self.evidence_dt is None else str(self.evidence_dt)}


def _has_fx(feats: List[Tuple[float, float, BI]], kind: str) -> Optional[int]:
    """检查末尾三元素是否构成分型; 返回起始索引或 None

    参数:
        feats: 已合并的标准特征序列。
        kind: 'top' 顶分型 / 'bottom' 底分型。

    返回:
        构成分型的第一个元素在 feats 中的下标; 不构成返回 None。
        (分型判定只看区间: 顶分型 = 中间元素 high/low 均三者最高;
         底分型 = 中间元素 low/high 均三者最低。)
    """
    if len(feats) < 3:
        return None
    a, b, c = feats[-3], feats[-2], feats[-1]
    if kind == "top":
        if b[1] > a[1] and b[1] > c[1] and b[0] > a[0] and b[0] > c[0]:
            return len(feats) - 3
    else:
        if b[0] < a[0] and b[0] < c[0] and b[1] < a[1] and b[1] < c[1]:
            return len(feats) - 3
    return None


def _feature_append(out, elem, direction_up):
    """同一特征序列顺序包含; 初始方向由假设转折后的走势给定。"""
    if not out:
        return [elem]
    last = out[-1]
    contained = (last[0] <= elem[0] and last[1] >= elem[1] or
                 elem[0] <= last[0] and elem[1] >= last[1])
    if not contained:
        return out + [elem]
    if len(out) > 1:
        direction_up = last[1] > out[-2][1]
    low = max(last[0], elem[0]) if direction_up else min(last[0], elem[0])
    high = max(last[1], elem[1]) if direction_up else min(last[1], elem[1])
    ref = (elem[2] if (elem[1] > last[1] if direction_up else elem[0] < last[0])
           else last[2])
    return out[:-1] + [(low, high, ref)]


def _context(owner, predecessor=None, ancestor=None, qualification="unknown", origin=None, premise=None):
    """Immutable finite lineage; None proof is never a confirmed predecessor.

    Certificate version=(start,stop,local_proof,published_proof), stop exclusive.
    Provisional predecessors bind their boundary even when proofs are unknown.
    Unknown history differs from a supplied, waiting lineage hypothesis.
    """
    if qualification not in ("unknown", "waiting", "visible"):
        raise ValueError("unknown/waiting/visible qualification required")
    if ancestor is not None:
        if premise is None:
            premise = ancestor[5]
        elif premise != ancestor[5]:
            raise ValueError("ancestor belongs to a different origin premise")
        if origin is None:
            origin = ancestor[4]
        elif origin != ancestor[4]:
            raise ValueError("ancestor belongs to a different origin")
    if predecessor is not None:
        a, stop, local, published = predecessor
        if a < 0 or stop <= a or stop != owner:
            raise ValueError("predecessor identity does not meet owner")
        if published is not None and (local is None or published < local):
            raise ValueError("publication cannot precede local proof")
        if local is not None and local < stop:
            raise ValueError("local proof must follow the composed predecessor")
        if qualification == "visible" and (local is None or published is None):
            raise ValueError("provisional predecessor cannot be declared confirmed")
    elif qualification != "unknown":
        raise ValueError("known qualification requires a predecessor identity")
    return owner, predecessor, ancestor, qualification, origin, premise


def _origin_premise(spec):
    """Explicit input assumption in BI-position time; not inferred from a window."""
    if spec is None:
        return None
    if not isinstance(spec, dict) or set(spec) != set(("basis", "anchor", "available_bi")):
        raise ValueError("origin premise requires basis/anchor/available_bi")
    basis, anchor, count = spec["basis"], spec["anchor"], spec["available_bi"]
    if basis not in ("unknown", "no_prior_history", "given_recent"):
        raise ValueError("unknown/no_prior_history/given_recent basis required")
    if not isinstance(anchor, (list, tuple)) or len(anchor) != 3:
        raise ValueError("origin anchor must bind BI position, direction and price")
    owner, direction, price = anchor
    if isinstance(owner, bool) or not isinstance(owner, int) or owner < 0:
        raise ValueError("nonnegative origin BI position required")
    if direction not in ("up", "down") or not isinstance(price, Real) or isinstance(price, bool) or not math.isfinite(price):
        raise ValueError("origin direction and finite price required")
    if basis == "unknown":
        if count is not None:
            raise ValueError("unknown origin has no known arrival")
    elif isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("nonnegative premise arrival BI required")
    if basis == "no_prior_history" and owner != 0:
        raise ValueError("no prior history applies only at the input beginning")
    return basis, tuple(anchor), count


def _root_no_history(context):
    return (context is not None and context[1] is None and
            context[5] is not None and context[5][0] == "no_prior_history")


def _qualification(context, observed):
    if context is None:
        return "unknown", None
    if _root_no_history(context):
        at = context[5][2]
        return ("visible" if at <= observed else "waiting"), at
    if context[3] == "unknown":
        return "unknown", None
    predecessor = context[1]
    publication = predecessor[3]
    if predecessor[2] is None or publication is None or publication > observed:
        return "waiting", publication
    return "visible", publication


def _local_identity(start, ending, context):
    stop, local, _ = ending
    prior = None if context is None else context[1]
    premise = None if context is None else context[5]
    if prior is not None:
        publication = max(local, prior[3]) if prior[2] is not None and prior[3] is not None else None
    elif premise is None:
        publication = local
    elif premise[0] == "unknown":
        publication = None
    else:
        publication = max(local, premise[2])
    return start, stop, local, publication


def _following_context(start, stop, context):
    """待证前驱始终保留身份和waiting，不退化为未知前史。"""
    return _context(stop, (start, stop, None, None), context, "waiting", context[4])


def _natural_reaction_state(bis, first_index, context, memo=None):
    """Earliest boundary/S-completion race, then qualification publication gate.

    固定笔下标是本判定的观察坐标，原始行情实际到达须另外映射。
    较晚破坏不撤回较早已证明的自然反应；同一观察下先破首起点。
    """
    if memo is None:
        memo = {"segment": {}, "natural": {}}
    key = (len(bis), first_index, context)
    if key in memo['natural']:
        return memo['natural'][key]
    first = bis[first_index]
    up = first.direction == "up"
    ready = first_index + 3
    valid_owner = first_index >= context[0]+3
    triple = bis[first_index:first_index+3]
    overlap = (len(triple) == 3 and max(b.low for b in triple) <= min(b.high for b in triple))
    events = []
    for i in range(first_index+1, len(bis)):
        bi = bis[i]
        if valid_owner and bi.direction != first.direction and (
                bi.end_value < first.start_value if up else bi.end_value > first.start_value):
            events.append((i, 0, "first_start_broken", None))
        elif valid_owner and bi.direction == first.direction and i >= first_index+2 and overlap and (
                bi.end_value > first.end_value if up else bi.end_value < first.end_value):
            events.append((i, 1, "first_end_selected", None))
    reaction = bis[first_index+1:ready+1]
    reaction_origin = (valid_owner and len(reaction) == 3 and
        max(b.low for b in reaction) <= min(b.high for b in reaction) and
        (reaction[-1].end_value < reaction[0].start_value if up else
         reaction[-1].end_value > reaction[0].start_value))
    if reaction_origin:
        # R is a provisional lineage hypothesis, not a completed one-BI XD.
        r_context = _following_context(context[0], first_index, context)
        s_context = _context(first_index+1, (first_index, first_index+1, None, None),
                             r_context, "waiting", context[4])
        # Examine prefixes in order so later boundary events cannot erase S.
        for n in range(ready+1, len(bis)+1):
            ending = _segment_end(bis[:n], first_index+1, context=s_context, memo=memo)
            if ending is not None:
                identity = _local_identity(first_index+1, ending, s_context)
                events.append((ending[1], 2, "confirmed_without_start_break", identity))
                break
    if events:
        evidence, _, state, reaction_identity = min(events, key=lambda e: (e[0], e[1]))
    else:
        evidence, state, reaction_identity = None, "pending", None
    qualification, prior = _qualification(context, len(bis)-1)
    publication = (max(evidence, prior) if qualification == "visible" and evidence is not None else None)
    if qualification == "unknown":
        kind = "context_unproved"
    elif qualification == "waiting":
        kind = "qualification_waiting"
    elif state == "confirmed_without_start_break":
        kind = "reaction_confirmed_without_start_break"
    elif state == "pending":
        kind = "reaction_pending" if reaction_origin else "reaction_origin_unproved"
    else:
        kind = state
    result = dict(kind=kind, state=state, qualification=qualification, evidence=evidence,
                  local_proof=evidence, published_proof=publication,
                  predecessor=None if context is None else context[1],
                  reaction_identity=reaction_identity, origin=context[4])
    memo['natural'][key] = result
    return result


def _gap_waiting_at(bis, candidate, left, evidence):
    """课67/78/81: 截止证据笔, 原有缺口转折是否仍待第二序列。

    只处理转折处原本有正缺口且第一特征分型已经成立的候选。
    后续回补不追溯改变其分类; 第二序列证明与新极值同笔到达时,
    先认可已成立的第二分型。无缺口的课78特殊延续不受此门控。
    """
    first = bis[candidate]
    up = first.direction == "down"
    if not (left[1] < first.low if up else left[0] > first.high):
        return False
    right, second = [(first.low, first.high, first)], []
    first_fractal = False
    for i in range(candidate+1, evidence+1):
        bi = bis[i]
        if bi.direction == first.direction:
            right = _feature_append(right, (bi.low, bi.high, bi), up)
        else:
            second = _feature_append(second, (bi.low, bi.high, bi), not up)
        if len(right) >= 2:
            first_fractal = (first_fractal or
                             _has_fx([left]+right[:2], "top" if up else "bottom") is not None)
        if first_fractal and _has_fx(second, "bottom" if up else "top") is not None:
            return False
        if bi.direction != first.direction and (
                bi.end_value > first.start_value if up else bi.end_value < first.start_value):
            return False
    return first_fractal


def _candidate_end(bis, start, candidate, left, context=None, memo=None):
    """课71/77/78假设局部转折, 返回(分界笔,证据末笔,结束方式)。

    bis为当前可见固定笔前缀; start是旧段起笔, candidate为第一
    反向笔, left为旧段最后标准特征(low,high,原笔)。左右不跨界
    包含, 后側须顺序包含。无缺口时未经包含的首反向笔约束方向
    选择; 其内摆动只能等待, 后继段破坏可以同时确认两段。递归
    起点严格后移且逐次限制于当前笔, 不引入观察前缀之外的价格。
    未满足定义返回None, 不把待定标准元素的转向当完成标志。
    """
    up = bis[start].direction == "up"
    first = bis[candidate]
    # 假设转折须相对其左特征元素同向突出, 不是任意回落点。
    if (first.high <= left[1] if up else first.low >= left[0]):
        return None
    right, second = [(first.low, first.high, first)], []
    pending_first_kind = False
    extreme = first.start_value
    gap = left[1] < first.low if up else left[0] > first.high
    for i in range(candidate+1, len(bis)):
        bi = bis[i]
        if bi.direction == first.direction:
            # 首次包含方向由左元素到假设转折给定, 不能凭下一段猜方向。
            right = _feature_append(right, (bi.low, bi.high, bi), up)
        else:
            second = _feature_append(second, (bi.low, bi.high, bi), not up)
            if gap and len(right) >= 2 and _has_fx(second, "bottom" if up else "top") is not None:
                return candidate, i, 2
            if pending_first_kind:
                # 课77/78逆时间传递: 反向首笔内的摆动本身不完成旧段,
                # 但后继线段已破坏这条反向段时, 两段破坏可同时确认。
                # 递归起点严格后移, 只使用当前i的可见前缀; 不把该
                # 后继证据回填到早先的包含时刻。先检验再撤销假设,
                # 才能保留端点并非实际极值的古怪线段。
                if context is None:
                    following = _segment_end(bis[:i+1], candidate)
                    if following is not None:
                        return candidate, i, 1
                else:
                    state = _natural_reaction_state(bis[:i+1], candidate, context, memo)
                    if state['kind'] == "first_start_broken" or (_root_no_history(context) and state['state'] == "first_start_broken"):
                        return None
                    if state['kind'] == "reaction_confirmed_without_start_break" or (_root_no_history(context) and state['state'] == "confirmed_without_start_break"):
                        return candidate, state['evidence'], 1
                    if _root_no_history(context):
                        following_context = _following_context(start, candidate, context)
                        following = _segment_end(bis[:i+1], candidate,
                                                 context=following_context, memo=memo)
                        if following is not None:
                            return candidate, i, 1
            if bi.end_value > extreme if up else bi.end_value < extreme:
                return None  # 第二序列未确认前先创新极值, 假设撤销。
        if context is not None and not gap and bi.direction == first.direction and i >= candidate+2:
            reverse_three = bis[candidate:candidate+3]
            overlap = (len(reverse_three) == 3 and
                       max(u.low for u in reverse_three) <= min(u.high for u in reverse_three))
            first_pen_break = (first.end_value <= left[1] if up else
                               first.end_value >= left[0])
            selected = (bi.end_value < first.end_value if up else
                        bi.end_value > first.end_value)
            if first_pen_break and overlap and selected:
                return candidate, i, 1
        if len(right) < 2:
            continue
        a, b = right[0], right[1]
        turned = (b[1] < a[1] and b[0] < a[0] if up else
                  b[1] > a[1] and b[0] > a[0])
        if turned and not gap and bi.direction == first.direction:
            # 课71/77: 后侧包含可削低/抬高标准元素, 但不能把它的
            # 新边界当成原始第一反向笔的结束价。第三及后续反向笔
            # 仍在首笔内时方向未选择, 单笔反弹不完成旧段。
            selected = (bi.end_value < first.end_value if up else
                        bi.end_value > first.end_value)
            # 课78回复03/38/811对应特定前史条件。这里保留穿越起价的
            # 工程回退; 三笔重叠或越起价本身不证明前段破坏状态,
            # 不能把该布尔门槛称为普遍理论充分条件。
            crossed_start = (bi.end_value < bis[start].start_value if up else
                             bi.end_value > bis[start].start_value)
            if selected or context is None and crossed_start:
                return candidate, i, 1
            if context is not None:
                state = _natural_reaction_state(bis[:i+1], candidate, context, memo)
                if state['kind'] == "reaction_confirmed_without_start_break" or (_root_no_history(context) and state['state'] == "confirmed_without_start_break"):
                    return candidate, state['evidence'], 1
                if crossed_start and _root_no_history(context):
                    return candidate, i, 1
            pending_first_kind = True
        if turned and gap and _has_fx(second, "bottom" if up else "top") is not None:
            return candidate, i, 2
    return None


def _segment_end(bis, start, context=None, memo=None):
    """按课71逐一检验转折, 保留课81较高/低缺口候选的待定约束。

    课67附图第八种/课78: 段内部可有比终点更极端的价格, 不能只
    检查全局新高/新低。假设左右元素不包含合并; 右側首次包含以
    左元素到转折的方向处理。第二特征必须真实形成三元素分型。
    较早更极端的缺口候选若在某次证据到达时仍待第二序列, 后来的
    较低顶/较高底不能抢先完成; 不把所有无证据候选一律当作阻塞。
    """
    if context is not None and context[0] != start:
        raise ValueError("context owner differs from segment start")
    if memo is None:
        memo = {"segment": {}, "natural": {}}
    segment_key = (len(bis), start, context)
    if segment_key in memo['segment']:
        return memo['segment'][segment_key]
    up = bis[start].direction == "up"
    counter = "down" if up else "up"
    features, endings, gaps, first_kind = [], [], [], []
    for i in range(start, len(bis)):
        bi = bis[i]
        if bi.direction != counter:
            continue
        if i >= start+3 and features and (bi.start_value > bis[start].start_value if up else
                                         bi.start_value < bis[start].start_value):
            if context is not None:
                if features[-1][1] < bi.low if up else features[-1][0] > bi.high:
                    gaps.append((i, features[-1]))
                else:
                    left = features[-1]
                    protrudes = bi.high > left[1] if up else bi.low < left[0]
                    breaks = bi.end_value <= left[1] if up else bi.end_value >= left[0]
                    reverse_three = bis[i:i+3]
                    overlaps = (len(reverse_three) == 3 and
                        max(b.low for b in reverse_three) <= min(b.high for b in reverse_three))
                    if protrudes and breaks and overlaps:
                        first_kind.append(i)
            end = _candidate_end(bis, start, i, features[-1], context, memo)
            if end is not None:
                endings.append(end)
            # 原相邻笔穿越起价的条件性工程回退。课67标准序列仍须
            # 保留更高旧顶; 课78特殊状态前提须另证, 不由本分支补足。
            raw = bis[i-2]
            local = _candidate_end(bis, start, i, (raw.low, raw.high, raw), context, memo)
            if local is not None:
                evidence = bis[local[1]]
                reverse = bis[i:local[1]+1]
                first_three = reverse[:3]
                crossed = (evidence.end_value < bis[start].start_value if up else
                           evidence.end_value > bis[start].start_value)
                overlap = (len(first_three) == 3 and
                           max(u.low for u in first_three) <= min(u.high for u in first_three))
                if crossed and overlap:
                    endings.append(local)
        features = _feature_append(features, (bi.low, bi.high, bi), up)
    if context is None:
        result = min(endings, key=lambda r: (r[1], r[0])) if endings else None
        memo['segment'][segment_key] = result
        return result
    waiting = {}
    allowed = []
    for ending in endings:
        candidate, evidence, _ = ending
        blocked = False
        ancestor = context[2]
        # A locally certified no-history root binds its immediate successor.
        # A provisional parent with no local proof grants no such boundary.
        # Late premise/publication still gates _local_identity and find_xds;
        # it must not retime an already valid conditional local proof.
        parent = context[1]
        root_parent_local = (_root_no_history(ancestor) and parent is not None and
                             parent[2] is not None and parent[2] <= evidence)
        if (ancestor is not None and not root_parent_local and candidate > start+3
                and (bis[candidate].start_value < bis[start].end_value if up else
                     bis[candidate].start_value > bis[start].end_value)):
            state = _natural_reaction_state(bis[:evidence+1], start, ancestor, memo)
            # A pending immediate reaction is an active constraint. Its missing
            # completion cannot authorize a lower local peak or higher trough.
            if state['kind'] in ("reaction_pending", "reaction_origin_unproved",
                                 "first_start_broken", "qualification_waiting"):
                blocked = True
            elif state['kind'] == "reaction_confirmed_without_start_break":
                reaction = state['reaction_identity']
                # S confirms that R can extend. An internal S candidate is not
                # a natural R boundary; an actual successor after S may be.
                d = [] if reaction is None else bis[reaction[1]:candidate]
                first_d = d[:3]
                shape = (len(d) >= 3 and d[0].direction == bis[start].direction and
                    max(b.low for b in first_d) <= min(b.high for b in first_d) and
                    (d[-1].end_value > d[0].start_value if up else
                     d[-1].end_value < d[0].start_value))
                # Necessary shape only; D completion and natural ownership
                # remain separate certificates, not implied by this gate.
                if not shape:
                    blocked = True
        for earlier in first_kind:
            if earlier >= candidate:
                break
            stronger = (bis[earlier].start_value >= bis[candidate].start_value if up else
                        bis[earlier].start_value <= bis[candidate].start_value)
            if not stronger:
                continue
            state = _natural_reaction_state(bis[:evidence+1], earlier, context, memo)
            if state['kind'] in ("reaction_pending", "qualification_waiting"):
                # A known pending original first reversal cannot be replaced
                # by a later lower raw-neighbour peak (or higher trough).
                blocked = True
                break
        for earlier, left in gaps:
            if earlier >= candidate:
                break
            if not (bis[earlier].start_value > bis[candidate].start_value if up else
                    bis[earlier].start_value < bis[candidate].start_value):
                continue
            waiting_key = (earlier, evidence)
            if waiting_key not in waiting:
                waiting[waiting_key] = _gap_waiting_at(bis, earlier, left, evidence)
            if waiting[waiting_key]:
                blocked = True
                break
        if not blocked:
            allowed.append(ending)
    result = min(allowed, key=lambda r: (r[1], r[0])) if allowed else None
    memo['segment'][segment_key] = result
    return result


def find_xds(bis: List[BI], origin_premise=None) -> List[XD]:
    """课67/71/78/81线段: 至少三笔、前三笔闭区间重叠。

    输入是按顺序首尾衔接的交替笔; 仅消费给定前缀。不足三笔或
    首三笔无重叠不输出伪线段; 若窗口从趋势中间开始, 向后寻找最早
    三笔重叠起点, 不保证覆盖前面的残笔。首三笔已重叠但尚无严格
    同向末端时等待后续证据, 不跳过该种子后再从未来恢复。末段
    complete=False。
    complete=True是当前工程规则在给定前缀上的完成状态; 特殊回退
    不替代其所需上下文证明, 也不证明输入笔在端点日已最终确认。
    evidence_dt是最后证据笔的端点,
    不是原始行情的实际可用时间; 回放仍须逐原始行情前缀计算。

    首段以给定笔前缀中按三笔重叠规则选出的起点作为工程种子。
    课78允许近期高低点起算,
    但特殊逆时间传递仍有前段破坏已确认等上下文前提; 仅凭本接口
    的笔前缀和原相邻笔穿越起价分支, 不证明自然行情中该前提成立,
    也不构成独立全局分界标注。需要理论证明时须另行核验上下文。

    origin_premise为1.2.0新增可选字典，None保持既有调用语义。
    显式模式只接受basis/anchor/available_bi三个字段。basis为unknown、
    no_prior_history或given_recent；anchor=(输入内起笔下标,方向,起价)，
    须匹配本输入选出的首个三笔重叠起点。调用方可先截取给定起点后的
    笔，不能把截断窗口推断为无前史。no_prior_history仅用于输入起笔0。
    available_bi为该前提已可知的非负BI观察下标，unknown须为None；
    知识未到时不发布完成项，给定近期起点也不补前驱破坏证明。
    此模式保留局部证明与累计发布的区别，最后证据笔取前驱、起点前提
    和本段证明中最后需要的BI；仍不等同原始行情的实际到达时间。
    前驱待证时保留其身份，不降成未知前史。输入前提真实性、行情及
    笔的实际可见性由调用方保证，完整自然起点和全局唯一性另行核验。

    完成段的gg/dd只含起点至终点的笔, 不把确认用的后续笔纳入。
    分界后从终点重新处理全部已读取笔, 不丢弃新段前部。构造器
    XD(...,mode)默认complete=False, 手工对象需显式提供完成证据。
    """
    if not isinstance(bis, (list, tuple)):
        raise TypeError("bis须为list或tuple")
    for i, bi in enumerate(bis):
        if not all(isinstance(v, Real) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (bi.start_value, bi.end_value)):
            raise ValueError("笔端点价须为有限数值")
        if bi.direction not in ("up", "down") or not bi.start_index < bi.end_index:
            raise ValueError("笔须有有效方向和递增端点索引")
        if (bi.direction == "up") != (bi.end_value > bi.start_value) or bi.end_value == bi.start_value:
            raise ValueError("笔方向须与端点价一致")
        if i and (bis[i-1].direction == bi.direction or
                  bis[i-1].end_dt != bi.start_dt or
                  bis[i-1].end_value != bi.start_value or
                  bis[i-1].end_index != bi.start_index):
            raise ValueError("笔须交替且时间、价格、索引首尾衔接")
    premise = _origin_premise(origin_premise)
    out, start, context = [], 0, None
    memo = {"segment": {}, "natural": {}}
    while start + 2 < len(bis):
        first = bis[start:start+3]
        if max(b.low for b in first) > min(b.high for b in first):
            start += 1
            continue
        if premise is not None and (context is None or context[0] != start):
            if premise[1] != (start, bis[start].direction, bis[start].start_value):
                raise ValueError("origin premise does not match selected boundary")
            origin = (bis[start].start_index, bis[start].start_value, bis[start].direction)
            context = _context(start, origin=origin, premise=premise)
        ending = _segment_end(bis, start, context=context, memo=memo)
        identity = None if ending is None or context is None else _local_identity(start, ending, context)
        if identity is not None and (identity[3] is None or identity[3] >= len(bis)):
            ending = None
        if ending is None:
            # 未完成段保留已达到的同向极值, 不用回落后的同向笔反转方向。
            # 最少三笔且顶须高于底(课78); 触沿净位移为零时等待, 不改换种子。
            eligible = [j for j in range(start+2, len(bis), 2)
                        if (bis[j].end_value > bis[start].start_value
                            if bis[start].direction == "up" else
                            bis[j].end_value < bis[start].start_value)]
            if not eligible:
                break
            end = (max(eligible, key=lambda j: bis[j].end_value)
                   if bis[start].direction == "up" else
                   min(eligible, key=lambda j: bis[j].end_value))
            stop, evidence, mode, complete = end+1, None, 1, False
        else:
            stop, evidence, mode = ending
            # 条件模式的最后证据包含前驱与起点前提，局部证明保留在identity。
            if identity is not None:
                evidence = identity[3]
            complete = True
        units = bis[start:stop]
        a, b = units[0], units[-1]
        out.append(XD(a.direction, (a.start_dt, a.start_value, a.start_index),
                      (b.end_dt, b.end_value, b.end_index), mode,
                      max(u.high for u in units), min(u.low for u in units),
                      complete, None if evidence is None else bis[evidence].end_index,
                      None if evidence is None else bis[evidence].end_dt))
        if ending is None:
            break
        if context is not None:
            context = _context(stop, identity, context, "visible", context[4])
        start = stop  # 完整重放分界后已消耗的笔, 不直接跳到证据末尾。
    return out


def chan_bis_xds(bars: List[Dict[str, Any]], standard: str = "81") -> Tuple[List[Any], List[Any], List[BI], List[XD]]:
    """完整入口: 原始 bars -> (无包含序列, 分型, 笔, 线段)

    参数:
        bars: 标准 bar 列表(chan.bars.normalize_bars 产出)。
        standard: 笔标准 '81'(默认)或'106', 透传给chan_fx_bi。

    返回:
        四元组 (new_bars, fxs, bis, xds):
            new_bars: 无包含K线序列(NewBar 列表);
            fxs: 分型列表(FX 列表);
            bis: 笔列表(BI 列表);
            xds: 线段列表(XD 列表, 末个可能未完成)。
    """
    from chan.bi import chan_fx_bi
    new_bars, fxs, bis = chan_fx_bi(bars, standard=standard)
    xds = find_xds(bis)
    return new_bars, fxs, bis, xds
