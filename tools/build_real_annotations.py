# -*- coding: utf-8 -*-
"""R2真实基础算术对照册: 只读独立标签, 不导入chan或生成预期。

输入包须与标签记录的SHA-256及原始前缀逐字一致。绘图仅展示原始
OHLC与人工含组/笔; 表格保留所有观察前缀。端点、内部极值及首次
右邻确认分列, 不从最终结构反推历史可见性。输出拒绝覆盖历史册。
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    """当前只读输入的字节摘要, 供复核与重建使用。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows):
    """仅格式化标签已有字段, 不计算理论预期。"""
    head = ''.join('<th>' + html.escape(str(v)) + '</th>' for v in headers)
    body = ''.join('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>'
                                  for v in row) + '</tr>' for row in rows)
    return '<div class="table"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def chart(label, merged=False):
    """绘制原始蜡烛或人工区间, 笔使用人工端点; 不调用包含算法。"""
    raw = label['raw_rows']
    groups = label['expected_new_bars']
    unit = label['price_unit']
    if merged:
        ranges = [(g['low_ticks'] * unit, g['high_ticks'] * unit) for g in groups]
    else:
        ranges = [(r['low'], r['high']) for r in raw]
    low = min(r['low'] for r in raw) - unit * 5
    high = max(r['high'] for r in raw) + unit * 5
    y = lambda v: 285 - (v - low) * 240 / (high - low)
    x = lambda i: 55 + i * 840 / max(1, len(ranges) - 1)
    parts = []
    for i in range(5):
        value = low + i * (high - low) / 4
        parts.append('<line x1="45" x2="915" y1="%.2f" y2="%.2f" stroke="#dce3ec"/><text x="4" y="%.2f">%.3f</text>' % (y(value), y(value), y(value) + 4, value))
    for i, (a, b) in enumerate(ranges):
        parts.append('<line x1="%.2f" x2="%.2f" y1="%.2f" y2="%.2f" stroke="#53657b" stroke-width="%d"/>' % (x(i), x(i), y(a), y(b), 6 if merged else 2))
        if not merged:
            row = raw[i]
            top, bottom = min(y(row['open']), y(row['close'])), max(y(row['open']), y(row['close']))
            parts.append('<rect x="%.2f" y="%.2f" width="12" height="%.2f" fill="%s"/>' % (x(i) - 6, top, max(1, bottom - top), '#c33d4d' if row['close'] >= row['open'] else '#157854'))
        parts.append('<text x="%.2f" y="310" text-anchor="middle">%d</text>' % (x(i), i))
    for _, a, b, start, end in label['expected_bis_81']:
        # 在原始图上用含组末行对齐端点; 这是对象索引位置, 非真实极值日。
        ia = a if merged else groups[a]['elements'][-1]
        ib = b if merged else groups[b]['elements'][-1]
        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#2563eb" stroke-width="3"/>' % (x(ia), y(start * unit), x(ib), y(end * unit)))
    return '<svg viewBox="0 0 940 330" role="img" aria-label="%s"><g font-family="system-ui" font-size="12">%s</g></svg>' % ('人工合并K线及笔' if merged else '原始OHLC及人工笔', ''.join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.json').exists():
        parser.error('拒绝覆盖已归档对照册')
    labels = json.loads(args.labels.read_text())
    packet = json.loads(args.packet.read_text())
    title = '真实日线独立标注 · ' + args.version
    content = ['<h1>' + title + '</h1><p>原始OHLC → 人工顺序包含 → 分型 → 81/106笔 → 待确认线段。全部预期来自冻结标签;本册不调用识别器。</p>']
    for label in labels:
        if digest(args.packet) != label['source_packet_sha256'] or packet['rows'][:len(label['raw_rows'])] != label['raw_rows']:
            parser.error('标签与原始输入包摘要/前缀不一致')
        rows = label['raw_rows']
        content.append('<article><h2>' + html.escape(label['id']) + '</h2><p>价格单位0.001。蓝线是人工笔,不是完成走势;原始图笔端对齐含组末行,该位置不代替内部极值实际发生日。</p><h3>原始K线</h3>' + chart(label))
        content.append('<h3>人工合并K线</h3>' + chart(label, merged=True))
        content.append(table(['合并索引', '原始行组', '低价单位', '高价单位'], [[i, g['elements'], g['low_ticks'], g['high_ticks']] for i, g in enumerate(label['expected_new_bars'])]))
        content.append('<h3>分型中心与首次右邻确认</h3>' + table(['类型', '合并索引', '首次可见原始行数', '观察收盘日'], [[kind, index, count, rows[count - 1]['dt'][:10]] for kind, index, count in label['fx_first_confirmed_raw_counts']]))
        content.append('<h3>81/106笔及待确认线段</h3><pre>' + html.escape(json.dumps({k: label[k] for k in ['expected_bis_81', 'expected_bis_106', 'expected_xds', 'expected_xd_range_ticks']}, ensure_ascii=False, indent=2)) + '</pre>')
        content.append('<h3>25个原始交易日前缀</h3>' + table(['行数', '观察日', '分型', '笔'], [[count, rows[int(count) - 1]['dt'][:10], data['fx'], data['bis']] for count, data in label['observations'].items()]))
        content.append('<h3>判定依据与证据边界</h3>' + ''.join('<p>' + html.escape(s) + '</p>' for s in label['reasoning'] + label['limitations']))
        content.append('<details><summary>原始输入逐行复核</summary>' + table(['行', '日期', '开', '高', '低', '收', '成交量', '因子'], [[i, r['dt'][:10]] + [r[k] for k in ['open', 'high', 'low', 'close', 'vol', 'adj_factor']] for i, r in enumerate(rows)]) + '</details></article>')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title><style>body{max-width:1100px;margin:30px auto;padding:0 18px;font:16px/1.7 system-ui;color:#172036;background:#f5f7fb}article{background:white;border:1px solid #d7deeb;border-radius:10px;padding:22px}svg{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d7deeb;padding:7px;text-align:left;vertical-align:top}th{background:#edf2fa}h1{font-size:28px}h2{font-size:22px}</style>' + ''.join(content) + '</html>'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document)
    receipt = {'version': args.version, 'algorithm_used_to_generate_labels': False,
               'cases': len(labels), 'source_hashes': {str(p.resolve().relative_to(ROOT)): digest(p) for p in [args.labels, args.packet]},
               'html_sha256': digest(output),
               'scope': '独立基础算术及全部原始前缀;没有完成XD/F1或严格点位真值'}
    output.with_suffix('.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
