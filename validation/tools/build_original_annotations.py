# -*- coding: utf-8 -*-
"""课62/65/67/71/77/78/81/106原页与人工预期对照册, 不调用算法。

读取已冻结的包fixture和图面登记, 绘制相对价格并嵌入PDF原页。
108课PDF为维护者私有版权材料, 不随本仓库分发, 构建时经--pdf传入。
输出HTML及摘要收据, 文件名含显式版本; 旧产物拒绝覆盖, 保留发布证据。
历史OHLC缺失、作者/编者差异及标注修订逐条显示, 不从印刷图恢复行情。
"""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'tests/fixtures'


def svg(case):
    """只绘制人工输入与预期; 组成分界蓝色完成/橙色待确认。"""
    parts = []
    if 'values' in case:
        values = case['values']
        low, high = min(values), max(values)
        xy = [(35+i*730./(len(values)-1),190-(v-low)*135./(high-low))
              for i,v in enumerate(values)]
        parts.append('<polyline points="'+ ' '.join('%.1f,%.1f'%p for p in xy)+
                     '" fill="none" stroke="#777" stroke-width="2"/>')
        for a,b,mode,complete in case['expected']:
            parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="4" %s/>' %
                         (*xy[a],*xy[b],'#2563eb' if complete else '#a66a00',
                          '' if complete else 'stroke-dasharray="7 4"'))
        for i,((x,y),v) in enumerate(zip(xy,values)):
            parts.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#172036"/><text x="%.1f" y="%.1f">%d / %s</text>' %
                         (x,y,x,y-(10 if i%2 else 22),i,v))
    else:
        ranges = case['ranges']
        low, high = min(a for a,b in ranges), max(b for a,b in ranges)
        for i,(a,b) in enumerate(ranges):
            x = 60+i*650./max(len(ranges)-1,1)
            y0,y1 = 185-(a-low)*135./(high-low),185-(b-low)*135./(high-low)
            parts.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="#172036" stroke-width="8"/><text x="%.1f" y="%.1f">%d [%s,%s]</text>' %
                         (x,x,y0,y1,x,y1-12,i,a,b))
    return '<svg viewBox="0 0 800 230" role="img" aria-label="人工相对价格标注"><g font-size="11" text-anchor="middle">'+''.join(parts)+'</g></svg>'


def details(record):
    """来源角色、假设、冲突和修订作为可复核证据直接显示。"""
    keys = ['source_role','annotation','assumptions','scope','notes',
            'observations','annotation_revisions']
    return ''.join('<p>'+html.escape(key)+': '+html.escape(
        json.dumps(record[key],ensure_ascii=False) if isinstance(record[key],(list,dict))
        else str(record[key]))+'</p>' for key in keys if key in record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True,help='收据及文件名的概念版本')
    parser.add_argument('--review',type=Path,help='该版本的图面登记JSON')
    parser.add_argument('--pdf',type=Path,required=True,help='108课PDF路径, 版权材料不随本仓库分发, 由维护者本地提供')
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    pdf = args.pdf.resolve()
    if not pdf.is_file():
        parser.error('找不到108课PDF: %s; 该文件不随本仓库分发, 请经--pdf指定维护者本地副本' % pdf)
    output = (args.output or ROOT/('validation/chan-original-annotations-'+args.version+'.html')).resolve()
    if output.exists() or output.with_suffix('.json').exists():
        parser.error('拒绝覆盖历史对照册;请选择新版本文件名')
    review = json.loads(args.review.read_text()) if args.review else {'figures':[],'conflicts':[],'remaining':[]}
    if args.review and review['version'] != args.version:
        parser.error('图面登记版本与对照册版本不一致')
    fixture_paths = [FIX/'fx_bi_originals.json',FIX/'xd_originals.json']
    fx,xd = [json.loads(p.read_text()) for p in fixture_paths]
    cases = fx+xd
    identities = {c['id'] for c in cases}
    assert len(identities)==len(cases), '重复标注身份'
    for c in review['figures']:
        assert set(c['fixture_refs']) <= identities, '图面引用缺少对应fixture'
    pages = sorted({c['pdf_page'] for c in cases+review['figures']} |
                   {c['pdf_page'] for c in review['conflicts'] if 'pdf_page' in c})
    title = '缠论原图标注与图面核对 · '+args.version
    content = ['<h1>'+title+'</h1><p>点位数值为保留不等式的相对价位;历史实盘结构复刻是合成固定笔,不是原始报价。蓝色为已完成分界,橙色为待确认尾段。观察前缀与端点时间分开,后继破坏证据不得倒填。</p><p>作者定义及课81更正优先;编者图示与实用提前选方向法分别登记。图面/正文核对不证明原始行情、MA或MACD数值复现。</p>']
    for c in cases:
        label = c['id']+' · '+c.get('figure',c.get('source',''))
        content.append('<article id="'+c['id']+'"><h2>'+html.escape(label)+'</h2><a href="#page-%d">原PDF第%d页</a>' % (c['pdf_page'],c['pdf_page'])+svg(c)+'<p>'+html.escape(c.get('reason',c['figure']))+'</p><pre>人工预期: '+html.escape(json.dumps(c['expected'],ensure_ascii=False))+'</pre>'+details(c)+'</article>')
    for c in review['figures']:
        refs = ' · '.join('<a href="#'+ref+'">'+ref+'</a>' for ref in c['fixture_refs'])
        content.append('<article id="review-'+c['id']+'"><h2>'+html.escape(c['caption'])+'</h2><a href="#page-%d">原PDF第%d页</a><p>%s</p><p>%s</p>%s</article>' % (c['pdf_page'],c['pdf_page'],html.escape(c['status']),refs,details(c)))
    content.append('<section><h2>来源冲突与范围</h2><pre>'+html.escape(json.dumps(review['conflicts'],ensure_ascii=False,indent=2))+'</pre></section>')
    executable = shutil.which('pdftoppm')
    if not executable:
        parser.error('需要pdftoppm渲染原页')
    with tempfile.TemporaryDirectory(prefix='chan-originals-') as folder:
        for page in pages:
            dest = Path(folder)/str(page)
            subprocess.run([executable,'-f',str(page),'-l',str(page),'-scale-to','1400','-png','-singlefile',str(pdf),str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            data = base64.b64encode(dest.with_suffix('.png').read_bytes()).decode('ascii')
            content.append('<section id="page-%d"><h2>原PDF第%d页</h2><img alt="原PDF第%d页" src="data:image/png;base64,%s"/></section>' % (page,page,page,data))
    content.append('<section><h2>尚缺证据</h2><pre>'+html.escape(json.dumps(review['remaining'],ensure_ascii=False,indent=2))+'</pre></section>')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{max-width:1000px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui;color:#172036;background:#f5f7fb}article,section{background:white;border:1px solid #d7deeb;border-radius:10px;padding:20px;margin:20px 0}h1{font-size:28px}h2{font-size:20px}svg,img{width:100%;height:auto}pre{white-space:pre-wrap;word-break:break-word;font-size:14px}a{color:#1b55bb}p{overflow-wrap:anywhere}</style>'+''.join(content)+'</html>'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(document)
    sources = fixture_paths+([args.review.resolve()] if args.review else [])
    receipt = dict(version=args.version,pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
                   source_pages=pages,independent_cases=len(cases),fx_bi_cases=len(fx),xd_cases=len(xd),
                   figure_reviews=len(review['figures']),source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                   pending=review['remaining'],algorithm_used_to_generate_labels=False)
    output.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(output,len(cases),'independent cases,',len(review['figures']),'figure reviews')


if __name__=='__main__':
    main()
