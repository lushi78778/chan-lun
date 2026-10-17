# -*- coding: utf-8 -*-
"""R2独立F1/F2对照册: 只绘制冻结整数标签, 不调用chan识别器。

原始K线、固定部件、中枢、F1组成与后继确认同时展示。内部极值只
作为区间画出, 不虚构极值发生日; 证明时刻画在实际前缀的观察日。
输入、人工表和HTML摘要一起存档, 拒绝覆盖既有对照册。
"""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows):
    head = ''.join('<th>' + html.escape(str(h)) + '</th>' for h in headers)
    body = ''.join('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>'
                                    for v in row) + '</tr>' for row in rows)
    return '<div class="table"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def chart(case, name):
    """可滚动原始价格图: 端点/包络/中枢/证明分别画, 不借用库输出。"""
    rows, path = case['raw_rows'], case['paths'][name]
    width, height = max(1100, len(rows) * 8 + 110), 460
    low = min(r['low'] for r in rows) * 1000
    high = max(r['high'] for r in rows) * 1000
    span = high - low or 1
    dates = dict((r['dt'][:10], i) for i, r in enumerate(rows))
    x = lambda i: 65 + i * (width - 100) / max(1, len(rows) - 1)
    y = lambda price: 60 + (high - price) * 300 / span
    elements = []
    for i in range(5):
        price = low + i * span / 4
        elements.append('<line x1="60" x2="%s" y1="%.1f" y2="%.1f" stroke="#e2e8f0"/><text x="5" y="%.1f">%.3f</text>'
                        % (width - 25, y(price), y(price), y(price) + 4, price / 1000))
    for i, r in enumerate(rows):
        color = '#dc2626' if r['close'] >= r['open'] else '#15803d'
        op, cl = y(r['open'] * 1000), y(r['close'] * 1000)
        elements.append('<g><title>%s OHLC %s/%s/%s/%s</title><line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s"/><rect x="%.1f" y="%.1f" width="4" height="%.1f" fill="%s"/></g>'
                        % (r['dt'][:10], r['open'], r['high'], r['low'], r['close'],
                           x(i), x(i), y(r['high'] * 1000), y(r['low'] * 1000),
                           color, x(i) - 2, min(op, cl), max(1, abs(op - cl)), color))
        if i % 30 == 0 or i == len(rows) - 1:
            elements.append('<text x="%.1f" y="405" transform="rotate(-25 %.1f 405)">%s</text>'
                            % (x(i), x(i), r['dt'][:10]))
    for n, unit in enumerate(path['units']):
        a, b = x(dates[unit['start_dt']]), x(dates[unit['end_dt']])
        elements.append('<path d="M%.1f %.1f L%.1f %.1f" stroke="#2563eb" stroke-width="2" fill="none"><title>固定部件%s; 包络[%s,%s]</title></path>'
                        % (a, y(unit['start_ticks']), b, y(unit['end_ticks']), n,
                           unit['low_ticks'], unit['high_ticks']))
    for n, move in enumerate(path['moves']):
        a, b = x(dates[move['start_dt']]), x(dates[move['end_dt']])
        for zd, zg in move['centers_ticks']:
            elements.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#f59e0b" fill-opacity=".13" stroke="#b45309" stroke-dasharray="4 3"><title>F1[%s]中枢[%s,%s]</title></rect>'
                            % (a, y(zg), max(2, b - a), max(2, y(zd) - y(zg)), n, zd, zg))
        text = 'F1[%s] %s %s' % (n, move['kind'], '完成' if move['complete'] else '等待')
        elements.append('<text x="%.1f" y="%s" fill="#334155">%s</text>'
                        % (a, 18 + n % 3 * 14, text))
        if move['complete']:
            proof = x(move['confirmed_raw_count'] - 1)
            elements.append('<line x1="%.1f" x2="%.1f" y1="58" y2="365" stroke="#7c3aed" stroke-dasharray="4 4"><title>F1[%s]首次确认 %s; 不是端点日</title></line><text x="%.1f" y="%s" fill="#7c3aed">证%s</text>'
                            % (proof, proof, n, move['confirmed_dt'], proof, 375 + n % 2 * 14, n))
    return '<div class="plot"><svg width="%s" height="%s" viewBox="0 0 %s %s" role="img" aria-label="%s"><g font-size="11" font-family="system-ui">%s</g></svg></div>' % (
        width, height, width, height, html.escape(case['id'] + ' ' + name), ''.join(elements))


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
        parser.error('人工表摘要与fixture不一致')
    hashes = dict((str(p.resolve().relative_to(ROOT)), digest(p))
                  for p in (args.labels, args.manual))
    counts = Counter((name.split('-')[0], m['kind']) for c in labels['cases']
                     for name, path in c['paths'].items() for m in path['completed'])
    content = ['<h1>真实F1及相邻F2独立标注 · 0.9.0</h1>',
               '<p>六窗口928行（窗口有重叠），两个笔标准分别计数。固定笔F1：盘整35、上涨2、下跌1；完成XD F1：盘整3。完成F2：盘整1。未覆盖完成XD路径的上涨/下跌F1，R2尚未全过。</p>',
               '<p>蓝线为固定部件净端点，橙框为F1中枢，紫虚线为后继证据首次可见日。两条路径分别声明最低操作构造层；日线周期不自动等于理论级别。15:05可见仅工程测试约定。</p>',
               '<nav>' + ' · '.join('<a href="#%s">%s %s</a>' % (c['window_key'], c['window_key'], c['id']) for c in labels['cases']) + '</nav>',
               '<details><summary>输入与标注摘要</summary><pre>' + html.escape(json.dumps(hashes, indent=2)) + '</pre></details>']
    for case in labels['cases']:
        key = case['window_key']
        packet = args.packets / case['source']['packet']
        if digest(packet) != case['source']['sha256'] or json.loads(packet.read_text())['rows'] != case['raw_rows']:
            parser.error('原始输入包摘要/行不一致')
        hashes[str(packet.resolve().relative_to(ROOT))] = digest(packet)
        content.append('<article id="%s"><h2>%s · %s</h2><p>%s原始行 · 价格单位0.001 · 因子恒为1。</p>'
                       % (key, key, case['id'], len(case['raw_rows'])))
        for reason in manual['reasons'].get(key, []):
            content.append('<p>' + html.escape(reason) + '</p>')
        for name, path in case['paths'].items():
            content.append('<h3>' + name + '</h3>' + chart(case, name))
            content.append(table(['F1', '状态', '部件闭区间', '中枢整数区间', '组成末日', '后继证明部件', '首次确认行数', '首次确认时刻'],
                                 [[m['kind'], '完成' if m['complete'] else '等待',
                                   [m['seg_start'], m['seg_end']], m['centers_ticks'],
                                   m['end_dt'], m['proof_unit'], m.get('confirmed_raw_count'),
                                   m.get('confirmed_dt')] for m in path['moves']]))
            content.append('<h4>相邻F2（允许中枢延伸，仅使用已完成F1）</h4>' + table(
                ['F2', '状态', 'F1组成', '中枢整数区间', '组成末日', '确认时刻'],
                [[m['kind'], m['complete'], [m['seg_start'], m['seg_end']],
                  m['centers_ticks'], m['end_dt'], m.get('confirmed_dt')] for m in path['f2']]))
        content.append('<details><summary>独立整数合并/分型/笔与完整部件表</summary><pre>' + html.escape(json.dumps(
            dict((k, v) for k, v in case.items() if k.startswith('foundation_')), ensure_ascii=False, indent=2)) + '</pre></details></article>')
    content.append('<h2>证据边界</h2>' + ''.join('<p>' + html.escape(v) + '</p>' for v in labels['limits']))
    document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>真实F1独立标注 0.9.0</title><style>body{max-width:1200px;margin:28px auto;padding:0 18px;background:#f5f7fb;color:#172036;font:16px/1.65 system-ui}article{padding:24px;background:#fff;border:1px solid #d7deeb;border-radius:10px;margin:26px 0}.plot,.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d7deeb;padding:8px;text-align:left;vertical-align:top}th{background:#edf2fa}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}h1{font-size:28px}h2{font-size:22px}svg{display:block}nav{line-height:2.2}</style></head><body>' + ''.join(content) + '</body></html>'
    output.write_text(document)
    receipt = dict(version='0.9.0', algorithm_used_to_generate_labels=False,
                   cases=len(labels['cases']), window_rows=sum(len(c['raw_rows']) for c in labels['cases']),
                   raw_standard_observations=1856, f1_path_observations=3712,
                   completed_f1=dict((p + ':' + k, n) for (p, k), n in counts.items()),
                   completed_f2=1, source_hashes=hashes, html_sha256=digest(output),
                   browser_visual_checked=False, R2_gate_passed=False, R3_ready=False)
    output.with_suffix('.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
