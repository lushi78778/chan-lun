# -*- coding: utf-8 -*-
"""R2真实日线四窗口独立线段对照册: 只读冻结标签, 不导入chan或生成预期。

输入包须与标签记录的SHA-256及原始行逐字一致。表格展示两标准笔、
富线段记录、逐原始日前缀签名、首次确认与证据笔延伸; 全部预期来自
冻结标签, 本工具不调用识别器。输出拒绝覆盖历史册。
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    """当前只读输入的字节摘要, 供复核与重建使用。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows):
    """仅格式化标签已有字段, 不计算理论预期。"""
    head = ''.join('<th>' + html.escape(str(v)) + '</th>' for v in headers)
    body = ''.join('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>'
                                    for v in row) + '</tr>' for row in rows)
    return '<div class="table"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def chart(label, standard):
    """绘制原始蜡烛与冻结笔端点; 只读标签, 不调用包含算法。"""
    raw = label['raw_rows']
    bis = label['expected_bis_' + standard]
    unit = label['price_unit']
    low = min(r['low'] for r in raw) - unit * 5
    high = max(r['high'] for r in raw) + unit * 5
    y = lambda v: 285 - (v - low) * 240 / (high - low)
    x = lambda i: 55 + i * 840 / max(1, len(raw) - 1)
    parts = []
    for i in range(5):
        value = low + i * (high - low) / 4
        parts.append('<line x1="45" x2="915" y1="%.2f" y2="%.2f" stroke="#dce3ec"/><text x="4" y="%.2f">%.3f</text>'
                     % (y(value), y(value), y(value) + 4, value))
    for i, row in enumerate(raw):
        parts.append('<line x1="%.2f" x2="%.2f" y1="%.2f" y2="%.2f" stroke="#53657b" stroke-width="2"/>'
                     % (x(i), x(i), y(row['low']), y(row['high'])))
        top, bottom = min(y(row['open']), y(row['close'])), max(y(row['open']), y(row['close']))
        parts.append('<rect x="%.2f" y="%.2f" width="12" height="%.2f" fill="%s"/>'
                     % (x(i) - 6, top, max(1, bottom - top),
                        '#c33d4d' if row['close'] >= row['open'] else '#157854'))
    groups = label['expected_new_bars']
    for _, start, end, start_ticks, end_ticks in bis:
        ia, ib = groups[start]['elements'][-1], groups[end]['elements'][-1]
        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#2563eb" stroke-width="3"/>'
                     % (x(ia), y(start_ticks * unit), x(ib), y(end_ticks * unit)))
    for record in label['expected_xds_' + standard]:
        ia, ib = groups[record['start_index']]['elements'][-1], groups[record['end_index']]['elements'][-1]
        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="2" stroke-dasharray="7 5"/>'
                     % (x(ia), y(record['start_ticks'] * unit), x(ib), y(record['end_ticks'] * unit),
                        '#7c3aed' if record['complete'] else '#9aa7ba'))
    for i in range(0, len(raw), max(1, len(raw) // 12)):
        parts.append('<text x="%.2f" y="310" text-anchor="middle">%s</text>' % (x(i), raw[i]['dt'][5:10]))
    return '<svg viewBox="0 0 940 330" role="img" aria-label="原始OHLC与冻结笔线段"><g font-family="system-ui" font-size="12">%s</g></svg>' % ''.join(parts)


def xd_rows(label, standard):
    return [[r['direction'], r['start_index'], r['end_index'], r['start_dt'], r['end_dt'],
             r['start_ticks'], r['end_ticks'], r['mode'], r['complete'],
             r['evidence_end_index'], r['evidence_dt'], r['gg_ticks'], r['dd_ticks']]
            for r in label['expected_xds_' + standard]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--packets', type=Path, required=True,
                        help='输入包目录, 按标签source_packet逐个核对')
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.with_suffix('.json').exists():
        parser.error('拒绝覆盖已归档对照册')
    labels = json.loads(args.labels.read_text())
    hashes = {str(args.labels.resolve().relative_to(ROOT)): digest(args.labels)}
    title = '真实日线独立线段标注 · ' + args.version
    content = ['<h1>' + title + '</h1><p>四个固定窗口的原始OHLC → 冻结合并组/分型 → 81/106标准笔 → 线段, 含逐原始日前缀签名、首次确认与已完成段稳定性。全部预期来自冻结标签; 本册不调用识别器。蓝线为冻结笔, 紫色虚线为完成线段, 灰色虚线为未完成线段。</p>']
    for label in labels:
        packet_path = (args.packets / label['source_packet']).resolve()
        packet = json.loads(packet_path.read_text())
        if digest(packet_path) != label['source_packet_sha256'] or packet['rows'] != label['raw_rows']:
            parser.error('标签与原始输入包摘要/原始行不一致: ' + label['id'])
        hashes[str(packet_path.relative_to(ROOT))] = digest(packet_path)
        rows = label['raw_rows']
        observations = label['observations']
        content.append('<article><h2>' + html.escape(label['id']) + '</h2>')
        content.append('<p>价格单位0.001; 输入包 ' + html.escape(label['source_packet'])
                       + '。合并组 %d、分型 %d、81笔 %d、106笔 %d; 完成线段 81标准 %d 个、106标准 %d 个。</p>'
                       % (len(label['expected_new_bars']), len(label['expected_fx']),
                          len(label['expected_bis_81']), len(label['expected_bis_106']),
                          sum(1 for r in label['expected_xds_81'] if r['complete']),
                          sum(1 for r in label['expected_xds_106'] if r['complete'])))
        content.append('<h3>原始K线与81标准冻结笔线段</h3>' + chart(label, '81'))
        content.append('<h3>原始K线与106标准冻结笔线段</h3>' + chart(label, '106'))
        content.append('<h3>合并组</h3>' + table(
            ['合并索引', '原始行组', '低价单位', '高价单位'],
            [[i, g['elements'], g['low_ticks'], g['high_ticks']]
             for i, g in enumerate(label['expected_new_bars'])]))
        content.append('<h3>分型中心与首次右邻确认</h3>' + table(
            ['类型', '合并索引', '首次可见原始行数', '观察收盘日'],
            [[kind, index, count, rows[count - 1]['dt'][:10]]
             for kind, index, count in label['fx_first_confirmed_raw_counts']]))
        content.append('<h3>81标准笔</h3>' + table(
            ['方向', '起点合并索引', '终点合并索引', '起点价单位', '终点价单位'],
            [[d, s, e, sv, ev] for d, s, e, sv, ev in label['expected_bis_81']]))
        content.append('<h3>106标准笔</h3>' + table(
            ['方向', '起点合并索引', '终点合并索引', '起点价单位', '终点价单位'],
            [[d, s, e, sv, ev] for d, s, e, sv, ev in label['expected_bis_106']]))
        content.append('<h3>81标准线段</h3>' + table(
            ['方向', '起', '止', '起日', '止日', '起价', '止价', '模式', '完成', '证据笔', '证据日', 'gg', 'dd'],
            xd_rows(label, '81')))
        content.append('<h3>106标准线段</h3>' + table(
            ['方向', '起', '止', '起日', '止日', '起价', '止价', '模式', '完成', '证据笔', '证据日', 'gg', 'dd'],
            xd_rows(label, '106')))
        content.append('<h3>线段首次确认与证据笔延伸</h3>' + table(
            ['标准', '起点笔', '终点笔', '首次确认原始行数', '观察收盘日'],
            [[std] + item[:3] + [rows[item[3] - 1]['dt'][:10]]
             for std in ('81', '106') for item in label['xd_first_confirmed_raw_counts'][std]])
            + ('<p>证据笔延伸: ' + html.escape(json.dumps(label['evidence_end_extension'], ensure_ascii=False)) + '</p>'
               if label['evidence_end_extension'] else '<p>无证据笔延伸事件。</p>'))
        content.append('<h3>逐原始日前缀签名</h3>' + table(
            ['行数', '观察日', '分型数', '81笔数', '81线段签名', '106笔数', '106线段签名'],
            [[count, rows[int(count) - 1]['dt'][:10], data['fx_n'],
              data['81']['bis_n'], json.dumps(data['81']['xds']),
              data['106']['bis_n'], json.dumps(data['106']['xds'])]
             for count, data in observations.items()]))
        content.append('<h3>判定依据与证据边界</h3>' + ''.join(
            '<p>' + html.escape(s) + '</p>' for s in label['reasoning'] + label['limitations']))
        content.append('<details><summary>原始输入逐行复核</summary>' + table(
            ['行', '日期', '开', '高', '低', '收', '成交量', '因子'],
            [[i, r['dt'][:10]] + [r[k] for k in ['open', 'high', 'low', 'close', 'vol', 'adj_factor']]
             for i, r in enumerate(rows)]) + '</details></article>')
    document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
                + title + '</title><style>body{max-width:1100px;margin:30px auto;padding:0 18px;font:16px/1.7 system-ui;color:#172036;background:#f5f7fb}article{background:white;border:1px solid #d7deeb;border-radius:10px;padding:22px;margin-bottom:26px}svg{width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d7deeb;padding:7px;text-align:left;vertical-align:top}th{background:#edf2fa}h1{font-size:28px}h2{font-size:22px}</style>'
                + ''.join(content) + '</html>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document)
    receipt = {'version': args.version, 'algorithm_used_to_generate_labels': False,
               'cases': len(labels), 'source_hashes': hashes,
               'html_sha256': digest(output),
               'scope': '四窗口独立基础算术、两标准笔、第一/第二种完成线段、真实古怪线段及全部原始日前缀; 没有完成F1、中枢或严格点位真值'}
    output.with_suffix('.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
