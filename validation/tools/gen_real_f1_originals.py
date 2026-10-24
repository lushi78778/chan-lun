# -*- coding: utf-8 -*-
"""R2 F1 独立标注编译器（课35/38/63/67/81/84/106）。

输入为不可覆盖的原始包、0.8.0已裁定基础标注、人工三段交集/切点/后继
证明表; 输出portable包fixture。全部价格用0.001整数, MA5比较交叉乘5。
不导入chan, 不自动发现XD或F1边界; 这些边界只来自人工裁定表。
确认时间按逐原始日前缀中固定笔/完成XD证明首次可见计算, 不取端点日。
日线15:00闭合/15:05到达仅测试约定, 不证明供应方真实历史发布时间。
本地开发工具; 未裁定的走势类型不得自动生成真值。
"""
import json
from decimal import Decimal
from pathlib import Path

def ticks(v):
    """原始日线0.001价格坐标; 禁止隐藏的四舍五入。"""
    value=Decimal(str(v))*1000
    if value!=value.to_integral_value():raise ValueError('价格不在0.001格点: '+str(v))
    return int(value)

def foundation(rows, standard):
    """独立整数包含/严格分型/交替端点裁定, 只读取当前原始前缀。"""
    groups=[]
    for i,row in enumerate(rows):
        lo,hi=ticks(row['low']),ticks(row['high'])
        if groups and ((lo<=groups[-1]['lo'] and hi>=groups[-1]['hi']) or (lo>=groups[-1]['lo'] and hi<=groups[-1]['hi'])):
            p=groups[-1]
            up=p['hi']>=groups[-2]['hi'] if len(groups)>1 else hi>=p['hi']
            choose=max if up else min
            groups[-1]={'lo':choose(lo,p['lo']),'hi':choose(hi,p['hi']),'elements':p['elements']+[i]}
        else: groups.append({'lo':lo,'hi':hi,'elements':[i]})
    fxs=[]
    for j in range(1,len(groups)-1):
        a,b,c=groups[j-1:j+2]
        if b['hi']>max(a['hi'],c['hi']) and b['lo']>max(a['lo'],c['lo']):kind='top'
        elif b['lo']<min(a['lo'],c['lo']) and b['hi']<min(a['hi'],c['hi']):kind='bottom'
        else:continue
        fxs.append({'kind':kind,'index':j,'price':b['hi'] if kind=='top' else b['lo'], 'raw':b['elements'][-1]})
    bis=[]
    last=None
    for f in fxs:
        if last is None:last=f;continue
        if f['kind']==last['kind']:
            better=f['price']>last['price'] if f['kind']=='top' else f['price']<last['price']
            if better:
                # 同向延伸仅能替换当前终点对象, 不能改写曾用于起点的分型。
                if bis and bis[-1]['b'] is last:bis[-1]['b']=f
                last=f
            continue
        gap=f['index']-last['index']
        direction='down' if last['kind']=='top' else 'up'
        positive=last['price']>f['price'] if direction=='down' else f['price']>last['price']
        touch=standard=='81'
        if standard=='106':
            for j in range(last['index'],f['index']+1):
                r=groups[j]['elements'][-1]
                if r<4:continue
                total=sum(ticks(rows[k]['close']) for k in range(r-4,r+1))
                if (groups[j]['hi']*5>=total if direction=='up' else groups[j]['lo']*5<=total):touch=True
        if positive and gap>=(4 if standard=='81' else 3) and touch:
            bis.append({'direction':direction,'a':last,'b':f});last=f
    return groups,fxs,bis

def records(bis):
    return [[b['direction'],b['a']['index'],b['b']['index'],b['a']['price'],b['b']['price']] for b in bis]


def digest(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unit_dt(row_dt, dt_slice):
    """日线默认截10字符日期; 分钟粒度dt_slice=None保留完整bar时刻。"""
    return row_dt if dt_slice is None else row_dt[:dt_slice]


def components(rows, bis, dt_slice=10):
    """把当下已经固定的笔转为算术坐标; 不命名为完成走势。"""
    return [dict(start_index=b['a']['index'],end_index=b['b']['index'],
                    start_ticks=b['a']['price'],end_ticks=b['b']['price'],
                    low_ticks=min(b['a']['price'],b['b']['price']),
                    high_ticks=max(b['a']['price'],b['b']['price']),
                    start_dt=unit_dt(rows[b['a']['raw']]['dt'],dt_slice),
                    end_dt=unit_dt(rows[b['b']['raw']]['dt'],dt_slice),direction=b['direction']) for b in bis]


def completed_xds(units, events):
    """仅编译人工确认的XD组成/模式/后继笔; 证据笔须已经固定。

    event=(起笔,末笔,mode,最末证明笔)。具体gate/包含/撤销已经独立裁定,
    本函数不按算法寻找候选, 不使用活动末笔的将来极值。
    """
    out=[]
    for a,z,mode,proof in events:
        # 相邻分段必须从前段开始可见；后段局部证明较早时也不能跳过前段。
        if len(units)<=proof:break
        covered=units[a:z+1]
        out.append(dict(start_index=units[a]['start_index'],end_index=units[z]['end_index'],
                    start_ticks=units[a]['start_ticks'],end_ticks=units[z]['end_ticks'],
                    start_dt=units[a]['start_dt'],end_dt=units[z]['end_dt'],
                    low_ticks=min(u['low_ticks'] for u in covered),
                    high_ticks=max(u['high_ticks'] for u in covered),
                    direction=units[a]['direction'],mode=mode,proof_bi=proof))
    return out


def move_record(units, spec):
    """人工指定三段交集和范围的复算; 不由输入搜索F1/F2切分。

    交集[最大低点,最小高点]须与人工整数值精确一致, 触沿算重叠。
    proof指定实际后继单元; pending保持None, 不制造ConfirmedMove。
    """
    a,z,kind,direction,triples,centers,proof=spec
    actual=[(max(u['low_ticks'] for u in units[j:j+3]),
                    min(u['high_ticks'] for u in units[j:j+3])) for j in triples]
    if actual!=[tuple(c) for c in centers]:
        raise ValueError('人工三段交集算术冲突: '+str((spec,actual)))
    return dict(kind=kind,complete=proof is not None,direction=direction,
                    seg_start=a,seg_end=z,start_dt=units[a]['start_dt'],end_dt=units[z]['end_dt'],
                    start_ticks=units[a]['start_ticks'],end_ticks=units[z]['end_ticks'],
                    low_ticks=min(u['low_ticks'] for u in units[a:z+1]),
                    high_ticks=max(u['high_ticks'] for u in units[a:z+1]),
                    centers_ticks=[list(c) for c in actual],proof_unit=proof)


def compile_case(key, source, manual):
    """六窗口按两个标准分别重算全部原始日前缀, 冻结确认链。"""
    rows=source['raw_rows']
    if any(r['adj_factor']!=1 for r in rows):
        raise ValueError('本轮人工整数标注仅接受因子恒为1的原始包')
    out=dict(id=source['id'],window_key=key,source=source['source'],raw_rows=rows,
                    paths={},observations={})
    for standard in ('81','106'):
        groups,fxs,bis=foundation(rows,standard)
        if 'expected_bis_'+standard in source and records(bis)!=source['expected_bis_'+standard]:
            raise ValueError('0.8.0冻结笔与独立复算不一致')
        out['foundation_'+standard]=dict(
            new_bars=[dict(elements=g['elements'],low_ticks=g['lo'],high_ticks=g['hi']) for g in groups],
            fxs=[[f['kind'],f['index'],f['price']] for f in fxs],bis=records(bis))
        if key in manual['FULL_XD']:
            full=components(rows,bis)
            rich=[]
            for a,z,mode,proof in manual['FULL_XD'][key][standard]:
                item=completed_xds(full,[(a,z,mode,proof if proof is not None else z)])[0]
                item['complete']=proof is not None
                item['proof_bi']=proof
                item['evidence_end_index']=full[proof]['end_index'] if proof is not None else None
                item['evidence_dt']=full[proof]['end_dt'] if proof is not None else None
                rich.append(item)
            out['foundation_'+standard]['xds']=rich
        units=components(rows,bis[:-1])
        xd_units=completed_xds(units,manual['XD_EVENTS'][key][standard])
        for path,parts,specs,tail in [
            ('bi',units,manual['SPECS'][key][standard],manual['TAILS'][key][standard]),
            ('xd',xd_units,manual['XD_F1'].get(key,{}).get(standard,[]),
                manual['XD_TAILS'].get(key,{}).get(standard))]:
            name=path+'-'+standard
            completed=[move_record(parts,s) for s in specs]
            table=completed+([move_record(parts,tail)] if tail else [])
            f2=[]
            if path=='bi' and completed:
                f2=[move_record(completed,manual['F2'][key][standard])]
                if f2[0]['complete']:
                    f2.append(move_record(completed,(4,4,'incomplete',None,[],[],None)))
            elif path=='xd' and completed:
                f2=[move_record(completed,(0,len(completed)-1,'incomplete',None,[],[],None))]
            out['paths'][name]=dict(units=parts,moves=table,completed=completed,f2=f2)
        for count in range(1,len(rows)+1):
            _,_,prefix_bis=foundation(rows[:count],standard)
            fixed=components(rows[:count],prefix_bis[:-1])
            xds=completed_xds(fixed,manual['XD_EVENTS'][key][standard])
            obs=out['observations'].setdefault(str(count),{})
            obs[standard]=dict(fixed_bis=fixed,completed_xds=xds)
            for path,parts,specs in [('bi',fixed,manual['SPECS'][key][standard]),
                    ('xd',xds,manual['XD_F1'].get(key,{}).get(standard,[]))]:
                name=path+'-'+standard
                visible=[move_record(parts,s) for s in specs if len(parts)>s[-1]]
                obs[name]=[[m['seg_start'],m['seg_end']] for m in visible]
                final=out['paths'][name]['completed']
                for m in visible:
                    target=next(t for t in final if t['seg_start']==m['seg_start'])
                    # 真值自身必须前缀稳定, 不能用最终极值回填历史。
                    for field in ('kind','direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','centers_ticks'):
                        if m[field]!=target[field]:raise ValueError('人工完成项回写: '+field)
                    target.setdefault('confirmed_raw_count',count)
            # F2唯一完成样本: F1[3]离开后F1[4]回抽, 证明来自实际已确认F1前缀。
            for path in ('bi','xd'):
                name=path+'-'+standard
                for f2 in out['paths'][name]['f2']:
                    if f2['complete'] and len(obs[name])>f2['proof_unit']:
                        f2.setdefault('confirmed_raw_count',count)
        for path in ('bi','xd'):
            for m in out['paths'][path+'-'+standard]['completed']:
                count=m['confirmed_raw_count']
                m['confirmed_dt']=rows[count-1]['dt'][:10]+' 15:05:00'
            for m in out['paths'][path+'-'+standard]['f2']:
                if m['complete']:m['confirmed_dt']=rows[m['confirmed_raw_count']-1]['dt'][:10]+' 15:05:00'
    # 保存结构变化事件, 测试仍回放全部原始日前缀; 不重复数百份相同表。
    snapshots={}
    previous=None
    for count in range(1,len(rows)+1):
        current=out['observations'][str(count)]
        if current!=previous:
            snapshots[str(count)]=current
            previous=current
    out['observations']=snapshots
    return out


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual',type=Path,required=True)
    parser.add_argument('--base-labels',type=Path,required=True)
    parser.add_argument('--packets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('拒绝覆盖冻结fixture, 使用新输出路径')
    manual=json.loads(args.manual.read_text())
    base=json.loads(args.base_labels.read_text());sources=[]
    for key,label in zip('ABCD',base):
        packet=args.packets/label['source_packet']
        if digest(packet)!=label['source_packet_sha256']:raise ValueError('原始包摘要漂移')
        if json.loads(packet.read_text())['rows']!=label['raw_rows']:raise ValueError('原始包与标签行不一致')
        sources.append((key,dict(label,source=dict(packet=packet.name,sha256=digest(packet),
            base_fixture_sha256=digest(args.base_labels),dataset_manifest_sha256=label['source_manifest_sha256'],
            parquet_sha256=label['source_parquet_sha256']))))
    for key,name in [('E','chan-real-512880-day-20180824-20191120-input.json'),
                    ('F','chan-real-512880-day-20161109-20170830-input.json')]:
        packet=args.packets/name;data=json.loads(packet.read_text())
        sources.append((key,dict(id='512880-day-'+data['rows'][0]['dt'][:10]+'-'+data['rows'][-1]['dt'][:10],
            raw_rows=data['rows'],source=dict(packet=name,sha256=digest(packet),
            dataset_manifest_sha256=data['manifest_sha256'],parquet_sha256=base[0]['source_parquet_sha256']))))
    result=dict(schema_version='chan-real-f1-originals-v1',annotation='independent_interval_adjudication',
                    minimum_rules=manual['minimum_rules'],manual_sha256=digest(args.manual),
                    availability='日线15:00闭合/15:05可见, 仅测试约定',
                    limits=manual['limits'],cases=[compile_case(k,s,manual) for k,s in sources])
    args.output.resolve().write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(args.output.resolve())

if __name__=='__main__':main()
