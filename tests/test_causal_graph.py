# -*- coding: utf-8 -*-
"""§11.7 R4: 可视因果图 DOT 投影的确定性输出(0.11.5)。

图是 CenterLineage/RoundChain 的确定性投影: 同输入同输出, 身份中
双引号转义, 节点先于边, 不在图中推导新结论。
"""
import unittest
from datetime import datetime, timedelta

from chan import (ConfirmedMove, causal_graph_dot, track_center_lineage,
                  track_rounds)
from chan.causal_graph import _esc

T = datetime(2025, 1, 1)
PRICES = [120, 110, 115, 108, 114, 90, 95, 88, 94, 70, 74, 68, 72, 67, 69,
          65, 76, 70, 78, 75, 82, 76, 86]
NINE = [120, 110, 115, 108, 114, 112, 109, 116, 111, 113, 110, 117, 111, 114]
DOUBLE = PRICES + [80, 83, 78.8, 82.4, 68, 71, 66.8, 70.4, 56, 58.4, 54.8,
                   57.2, 54.2, 55.4, 53,
                   59.6, 56, 60.8, 59, 63.2, 59.6, 65.6]


def moves(prices, n=20):
    units = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        s = T + timedelta(hours=i * n)
        e = T + timedelta(hours=(i + 1) * n)
        units.append(ConfirmedMove('u%d' % i, 'base', 'up' if b > a else 'down',
                                   s, e, a, b, min(a, b), max(a, b),
                                   e + timedelta(minutes=2)))
    return units


def bars_of(prices, n=20):
    rows = []
    for i, (a, b) in enumerate(zip(prices, prices[1:])):
        for j in range(n):
            dt = T + timedelta(hours=i * n + j)
            p = a + (b - a) * j / n
            rows.append(dict(dt=dt, open=p, high=p, low=p, close=p,
                             volume=100., closed_dt=dt,
                             available_dt=dt + timedelta(minutes=1)))
    dt = T + timedelta(hours=(len(prices) - 1) * n)
    p = prices[-1]
    rows.append(dict(dt=dt, open=p, high=p, low=p, close=p, volume=100.,
                     closed_dt=dt, available_dt=dt + timedelta(minutes=1)))
    return rows


def now_of(prices, n=20):
    return T + timedelta(hours=(len(prices) - 1) * n) + timedelta(days=1)


class TestLineageGraph(unittest.TestCase):
    def test_nodes_edges_and_determinism(self):
        """谱系图: 节点/定理二边/来源边/延伸自环, 同输入同输出。"""
        lineage = track_center_lineage(moves(PRICES), now_of(PRICES),
                                       'main', 'trend')
        dot = causal_graph_dot(lineage=lineage)
        self.assertEqual(dot, causal_graph_dot(lineage=lineage))
        self.assertTrue(dot.startswith('digraph "chan causal graph" {'))
        self.assertTrue(dot.endswith('}\n'))
        # 4 同级中枢 + 1 上层节点; 身份中的双引号须转义
        self.assertIn('  "[\\"main\\",\\"u0\\"]" [label="main 110~115"];', dot)
        self.assertIn('  "[\\"main\\",\\"u15\\"]" [label="main 70~76"];', dot)
        self.assertIn('  "[\\"trend\\",\\"u0\\",\\"u5\\"]" '
                      '[label="trend 90~95"];', dot)
        # 课20定理二新生边与 expanded_up 来源边
        self.assertIn('  "[\\"main\\",\\"u0\\"]" -> "[\\"main\\",\\"u5\\"]" '
                      '[label="higher_level"];', dot)
        self.assertIn('  "[\\"main\\",\\"u5\\"]" -> "[\\"main\\",\\"u9\\"]" '
                      '[label="down_continue"];', dot)
        self.assertIn('  "[\\"main\\",\\"u0\\"]" -> '
                      '"[\\"trend\\",\\"u0\\",\\"u5\\"]" '
                      '[label="expanded_up"];', dot)
        # 延伸自环计数(版本链聚合)
        self.assertIn('  "[\\"main\\",\\"u0\\"]" -> "[\\"main\\",\\"u0\\"]" '
                      '[label="extended x2"];', dot)
        self.assertIn('  "[\\"main\\",\\"u15\\"]" -> "[\\"main\\",\\"u15\\"]" '
                      '[label="extended x4"];', dot)
        # 节点先于边输出
        self.assertLess(dot.index('[label="main 110~115"]'),
                        dot.index('[label="higher_level"]'))

    def test_reorganized_edge_carries_basis(self):
        """重组边携带 basis 标记, 上层节点区间为三×三交集。"""
        lineage = track_center_lineage(moves(NINE), now_of(NINE),
                                       'main', 'trend')
        dot = causal_graph_dot(lineage=lineage)
        self.assertIn('  "[\\"main\\",\\"u0\\"]" -> '
                      '"[\\"trend\\",\\"nine_segment\\",\\"u0\\"]" '
                      '[label="reorganized: nine_segment"];', dot)
        self.assertIn('  "[\\"trend\\",\\"nine_segment\\",\\"u0\\"]" '
                      '[label="trend 109~114"];', dot)

    def test_empty_lineage_minimal_graph(self):
        """空谱系输出最小图, 不虚构节点。"""
        lineage = track_center_lineage(moves([100, 90, 80, 70, 60, 50]),
                                       now_of([100, 90, 80, 70, 60, 50]),
                                       'main', 'trend')
        self.assertEqual(causal_graph_dot(lineage=lineage),
                         'digraph "chan causal graph" {\n'
                         '  rankdir=LR;\n'
                         '  node [shape=box];\n'
                         '}\n')


class TestRoundGraph(unittest.TestCase):
    def test_round_nodes_and_handover_edge(self):
        """轮次图: 锚点节点与同侧移交边, 未移交不连边。"""
        rounds = track_rounds(moves(DOUBLE), bars_of(DOUBLE),
                              now_of(DOUBLE), 'main')
        self.assertEqual(len(rounds.rounds), 2)
        r1, r2 = rounds.rounds
        self.assertEqual(r1.handed_over_dt, r2.anchor.confirmed_dt)
        dot = causal_graph_dot(round_chain=rounds)
        self.assertEqual(dot, causal_graph_dot(round_chain=rounds))
        # 两轮节点: side 与课108构造 phase 入标签
        self.assertIn('  "%s" [label="buy completed"];' % _esc(r1.round_id), dot)
        self.assertIn('  "%s" [label="buy completed"];' % _esc(r2.round_id), dot)
        # 移交边: 旧轮 -> 新轮, 登记移交时刻
        self.assertIn('  "%s" -> "%s" [label="handover %s"];'
                      % (_esc(r1.round_id), _esc(r2.round_id),
                         r1.handed_over_dt), dot)
        # 新轮无移交, 无出边
        self.assertNotIn('"%s" -> ' % _esc(r2.round_id), dot)

    def test_no_handover_no_edge(self):
        """单轮无移交不虚构因果边, 只有锚点节点。"""
        rounds = track_rounds(moves(PRICES), bars_of(PRICES),
                              now_of(PRICES), 'main')
        self.assertEqual(len(rounds.rounds), 1)
        dot = causal_graph_dot(round_chain=rounds)
        self.assertNotIn(' -> ', dot)
        self.assertIn('[label="buy ', dot)


class TestValidationAndCombination(unittest.TestCase):
    def test_requires_at_least_one_input(self):
        """两者皆缺或类型不符报错, 不猜测。"""
        with self.assertRaises(ValueError):
            causal_graph_dot()
        with self.assertRaises(ValueError):
            causal_graph_dot(lineage=123)
        with self.assertRaises(ValueError):
            causal_graph_dot(round_chain='chain')

    def test_combined_parts_and_escaped_title(self):
        """谱系与轮次合并输出; 标题与身份中的引号转义。"""
        lineage = track_center_lineage(moves(PRICES), now_of(PRICES),
                                       'main', 'trend')
        rounds = track_rounds(moves(DOUBLE), bars_of(DOUBLE),
                              now_of(DOUBLE), 'main')
        dot = causal_graph_dot(lineage=lineage, round_chain=rounds,
                               title='回放 "2026"')
        self.assertTrue(dot.startswith('digraph "回放 \\"2026\\"" {'))
        self.assertIn('[label="main 110~115"];', dot)
        self.assertIn('[label="handover ', dot)
        # 谱系节点先于轮次节点输出
        self.assertLess(dot.index('main 110~115'),
                        dot.index('handover'))


if __name__ == '__main__':
    unittest.main()
