# -*- coding: utf-8 -*-
"""完成XD→F1独立对照册：绘制冻结标签，不运行结构识别算法。"""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

from build_real_f1_annotations import chart, digest, table

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--manual', type=Path, required=True)
    parser.add_argument('--packets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.json').exists():
        parser.error('拒绝覆盖已归档对照册')
    labels = json.loads(args.labels.read_text())
    manual = json.loads(args.manual.read_text())
    if labels['manual_sha256'] != digest(args.manual):
        parser.error('人工表摘要漂移')
    if [c['id'] for c in labels['cases']] != [c['id'] for c in manual['cases']]:
        parser.error('人工表与标签窗口顺序或数量不一致')
    hashes = {str(p.resolve().relative_to(ROOT)): digest(p) for p in (args.labels, args.manual)}
    content = ['<h1>完成线段构造F1 · 0.9.1</h1>',
               '<p>两个自然起点窗口，106标准，700根原始日线、14条完成XD。按明示同级切分合同完成up/down各1；严格趋势仍未由此证明。</p>',
               '<p>先截原始行情，再排除活动末笔、计算完成XD。蓝线为净端点，橙框为核心区间，紫线为后继证据首次可见日；日线15:05仅测试约定。</p>']
    for case, adjudication in zip(labels['cases'], manual['cases']):
        packet = args.packets / case['source']['packet']
        if digest(packet) != case['source']['sha256'] or json.loads(packet.read_text())['rows'] != case['raw_rows']:
            parser.error('原始包摘要或行漂移')
        hashes[str(packet.resolve().relative_to(ROOT))] = digest(packet)
        name = 'xd-' + case['standard']
        path = case['paths'][name]
        content += ['<article><h2>' + html.escape(case['id']) + '</h2>',
                    '<p>' + html.escape(adjudication['sampling_rule']) + '</p>', chart(case, name)]
        content.append(table(['工程F1', '完成', 'XD组成', '核心区间（0.001）', '组成末日', '后继XD', '首次行数', '首次确认'],
            [[m['kind'], m['complete'], [m['seg_start'], m['seg_end']], m['centers_ticks'],
              m['end_dt'], m['proof_unit'], m.get('confirmed_raw_count'), m.get('confirmed_dt')] for m in path['moves']]))
        content.append(table(['XD', '净端点', '实际包络（0.001）', 'mode', '证明BI', '证据笔端点', '首次可见'],
            [[i, [u['start_dt'], u['end_dt']], [u['low_ticks'], u['high_ticks']], u['mode'],
              u['proof_bi'], u['evidence_dt'], u['confirmed_dt']] for i, u in enumerate(path['units'])]))
        r = case['wave_relation']
        content.append('<h3>核心移位与严格趋势证据分开</h3>' + table(
            ['核心方向', '三段构造组核心', '三段构造组全部波动', '波动关系', '严格趋势已证明'],
            [[r['core_direction'], r['centers_ticks'], r['waves_ticks'], r['relation'], r['strict_trend_proven']]]))
        content.append('<p>工程三段组不自动等于课20的Z_n；严格趋势仍需独立裁定完整角色和波动。本表不作为严格一类点正例。</p>')
        content.extend('<p>' + html.escape(v) + '</p>' for v in adjudication['f1_audit'])
        content.append('<details><summary>逐段人工裁定及基础表</summary><pre>' + html.escape(json.dumps(
            dict(xd_audit=adjudication['audit'], foundation=case['foundation']), ensure_ascii=False, indent=2)) + '</pre></details></article>')
    content.append('<h2>证据边界</h2>' + ''.join('<p>' + html.escape(v) + '</p>' for v in labels['limits']))
    content.append('<details><summary>输入与标注摘要</summary><pre>' + html.escape(json.dumps(hashes, indent=2)) + '</pre></details>')
    document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完成XD与F1独立标注0.9.1</title><style>body{max-width:1200px;margin:28px auto;padding:0 18px;background:#f5f7fb;color:#172036;font:16px/1.65 system-ui}article{padding:24px;background:white;border:1px solid #d7deeb;border-radius:10px;margin:26px 0}.plot,.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d7deeb;padding:8px;text-align:left;vertical-align:top}th{background:#edf2fa}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}svg{display:block}</style></head><body>' + ''.join(content) + '</body></html>'
    output.write_text(document)
    paths = [path for case in labels['cases'] for path in case['paths'].values()]
    counts = Counter(move['kind'] for path in paths for move in path['completed'])
    receipt = dict(version=labels['version'], source_hashes=hashes, html_sha256=digest(output),
                   cases=len(labels['cases']), window_rows=sum(len(c['raw_rows']) for c in labels['cases']),
                   completed_xds=sum(len(path['units']) for path in paths), completed_f1=dict(counts),
                   strict_trend_proven=False, R2_gate_passed=False, R3_ready=False,
                   algorithm_used_to_generate_labels=False, browser_visual_checked=False)
    output.with_suffix('.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
