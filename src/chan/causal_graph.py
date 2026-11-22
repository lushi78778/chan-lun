# -*- coding: utf-8 -*-
"""chan.causal_graph —— 谱系与轮次的可视因果图(计划 §11.7 R4)。

输入为已冻结数据对象(CenterLineage/RoundChain), 输出确定性 Graphviz
DOT 源文本, 库不引入渲染依赖: 同输入同输出, 逐节点逐边按事件流与
轮次顺序输出。图是数据对象的确定性投影, 不读取源行情, 不新增
理论判定; 渲染由外部 Graphviz 等工具完成, 渲染失败不影响数据对象。

节点与边:
  - 中枢节点=中枢身份(版本链聚合), 标签为级别与形成区间 zd~zg
    (取 version 0 冻结快照); extended 计入自环标签(课 20 延伸);
  - formed 边按课 20 定理二新生关系: 前中枢 -> 新中枢, relation
    为边标签; 首中枢无前驱不连边, 不虚构来源;
  - expanded_up/reorganized 边由来源中枢指向上层中枢(课 20 波动
    重叠/课 69+70 重组), basis 标记入边;
  - 轮次节点=锚点 point_id, 标签为 side 与课 108 构造 phase;
    移交边仅在该轮 handed_over_dt 已登记且存在同侧后继轮次时连接
    (课 101 旧轮中阴被新锚点接管), 未移交不虚构因果边。

兼容: Python 3.6。
"""

from __future__ import print_function

import json

from chan.lineage import (CenterLineage, _EXPANDED_UP, _EXTENDED, _FORMED,
                          _REORGANIZED)
from chan.rounds import RoundChain


def _esc(value):
    text = str(value)
    return text.replace('\\', '\\\\').replace('"', '\\"')


def _graph_id(identity, domain):
    """发生跨域碰撞时对全部图身份做可逆编码，数据对象身份保持原值。"""
    if domain is not None:
        identity = json.dumps([domain, identity], ensure_ascii=False, separators=(',', ':'))
    return _esc(identity)


def _center_node(event, lineage, domain=None):
    snap = lineage.snapshot(event.center_id, 0)
    return '  "%s" [label="%s %s~%s"];' % (
        _graph_id(event.center_id, domain), _esc(snap.level), _esc(snap.zd), _esc(snap.zg))


def _lineage_lines(lineage, domain=None):
    """谱系投影: 中枢节点、定理二新生边、延伸自环与升级/重组来源边。"""
    extended_counts = {}
    for event in lineage.events:
        if event.kind == _EXTENDED:
            extended_counts[event.center_id] = \
                extended_counts.get(event.center_id, 0) + 1
    nodes = []
    seen = set()
    edges = []
    for event in lineage.events:
        if event.kind == _FORMED:
            line = _center_node(event, lineage, domain)
            if event.center_id not in seen:
                seen.add(event.center_id)
                nodes.append(line)
            if event.prev_center_id is not None:
                edges.append('  "%s" -> "%s" [label="%s"];' % (
                    _graph_id(event.prev_center_id, domain), _graph_id(event.center_id, domain),
                    _esc(event.relation)))
        elif event.kind == _EXPANDED_UP:
            line = _center_node(event, lineage, domain)
            if event.center_id not in seen:
                seen.add(event.center_id)
                nodes.append(line)
            for source in event.source_center_ids:
                edges.append('  "%s" -> "%s" [label="%s"];' % (
                    _graph_id(source, domain), _graph_id(event.center_id, domain), _esc(event.kind)))
        elif event.kind == _REORGANIZED:
            line = _center_node(event, lineage, domain)
            if event.center_id not in seen:
                seen.add(event.center_id)
                nodes.append(line)
            for source in event.source_center_ids:
                edges.append('  "%s" -> "%s" [label="%s: %s"];' % (
                    _graph_id(source, domain), _graph_id(event.center_id, domain),
                    _esc(event.kind), _esc(event.basis)))
    lines = list(nodes)
    ordered = []
    for event in lineage.events:
        cid = event.center_id
        if cid not in extended_counts:
            continue
        key = (cid, extended_counts[cid])
        if key not in ordered:
            ordered.append(key)
    for cid, count in ordered:
        lines.append('  "%s" -> "%s" [label="extended x%d"];' % (
            _graph_id(cid, domain), _graph_id(cid, domain), count))
    lines.extend(edges)
    return lines


def _round_lines(round_chain, domain=None):
    """轮次投影: 锚点节点(课108构造状态)与移交边(课101同侧接管)。"""
    rounds = round_chain.rounds
    lines = ['  "%s" [label="%s %s"];' % (
        _graph_id(item.round_id, domain), _esc(item.side), _esc(item.formation.phase))
        for item in rounds]
    for i, item in enumerate(rounds):
        if item.handed_over_dt is None:
            continue
        for later in rounds[i + 1:]:
            if later.side == item.side:
                lines.append('  "%s" -> "%s" [label="handover %s"];' % (
                    _graph_id(item.round_id, domain), _graph_id(later.round_id, domain),
                    _esc(item.handed_over_dt)))
                break
    return lines


def causal_graph_dot(lineage=None, round_chain=None,
                     title='chan causal graph'):
    """CenterLineage/RoundChain -> 确定性 Graphviz DOT 源文本。

    lineage/round_chain 可只给其一, 两者皆缺或类型不符报错, 不猜测。
    返回 UTF-8 DOT 文本(含末尾换行), 同输入同输出; 节点与边含义见
    模块 docstring。图只做投影: 数据对象中的身份、关系与时刻原样
    进入图, 不在图里推导新结论。两域身份相交时，全部图节点及边
    分别采用JSON["lineage", 原身份]/["round", 原身份]编码；无交集
    及单域输出保持原文本，数据对象本身不变。
    """
    if lineage is None and round_chain is None:
        raise ValueError('lineage与round_chain至少提供其一')
    if lineage is not None and not isinstance(lineage, CenterLineage):
        raise ValueError('lineage须为CenterLineage')
    if round_chain is not None and not isinstance(round_chain, RoundChain):
        raise ValueError('round_chain须为RoundChain')
    separate = False
    if lineage is not None and round_chain is not None:
        identities = set(event.center_id for event in lineage.events)
        for event in lineage.events:
            if event.kind == _FORMED and event.prev_center_id is not None:
                identities.add(event.prev_center_id)
            elif event.kind in (_EXPANDED_UP, _REORGANIZED):
                identities.update(event.source_center_ids)
        separate = bool(identities.intersection(item.round_id for item in round_chain.rounds))
    out = ['digraph "%s" {' % _esc(title),
           '  rankdir=LR;',
           '  node [shape=box];']
    if lineage is not None:
        out.extend(_lineage_lines(lineage, 'lineage' if separate else None))
    if round_chain is not None:
        out.extend(_round_lines(round_chain, 'round' if separate else None))
    out.append('}')
    return '\n'.join(out) + '\n'
