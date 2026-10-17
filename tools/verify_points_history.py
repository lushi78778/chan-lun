# -*- coding: utf-8 -*-
"""自动MACD辅助一类/因果中枢/点位链的真实行情与时间接线验收。

使用锁定已知价格锚、固定笔或其完成线段经同级切分声明F1。F1真理论
仍须人工原图验收, K线周期不等于走势级别。暖机历史只在首观察声明
已知。行情关闭/到达是测试约定, 不证明真实供应版本及聚宽时效。
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_core_history import CODES,bars_from,digest,load_frames
from verify_core_available import prepare_prices
from verify_ma_history import timed
from verify_completion_history import shape
import chan


def check(frame,period,parts):
    key='trade_date' if period=='1d' else 'trade_time'
    first=next(i for i,t in enumerate(frame[key]) if t.year==2026)
    anchor=float(frame['adj_factor'].iloc[first])
    precision=None
    if period!='1d':frame,precision=prepare_prices(frame)
    rows=timed(bars_from(frame,period,anchor=anchor),period)
    if period=='1d':stops=list(range(first+1,len(frame)+1))
    else:
        days=sorted(set(r['dt'].date() for r in rows))[-20:]
        stops=[i+1 for i,r in enumerate(rows) if r['dt'].date() in days]
    bases,bodies={},{}
    previous=[set(),set(),set()];unique=[{}, {}, {}];centers={};examples={}
    snapshots=Counter();warm=0;unresolved=set()
    for obs,stop in enumerate(stops):
        now=rows[stop-1]['available_dt']
        result=chan.analyze_available(rows,now)
        parts_list=(result.bis[:-1] if parts=='bi' else
                    [x for x in chan.find_xds(result.bis[:-1]) if x.complete])
        current={}
        for move in chan.same_level_decompose(parts_list):
            if not move.complete:continue
            a,b=parts_list[move.seg_start],parts_list[move.seg_end]
            name='F1:'+str(move.start_dt)
            names=tuple(parts+':'+str(u.start_dt) for u in parts_list[move.seg_start:move.seg_end+1])
            body=(shape(move),a.start_value,b.end_value,names);current[name]=body
            if name not in bases:
                bases[name]=chan.ConfirmedMoveType(name,'F1',move.kind,move.direction,
                    move.start_dt,move.end_dt,a.start_value,b.end_value,move.low,move.high,now,
                    names,tuple(parts+':'+str(u.start_dt) for u in parts_list),tuple(move.centers))
                bodies[name]=body
            else:assert bodies[name]==body,'基础完成类型修订'
        assert set(bases).issubset(current),'基础完成类型撤销'
        if obs==0:warm=len(bases)
        units=sorted(bases.values(),key=lambda u:u.start_dt)
        chain=chan.analyze_point_chain(units,rows,now,'F2')
        independent=chan.analyze_point_chain(units,rows[:stop],now,'F2')
        assert chain==independent,'未来行情改变点位链'
        poison=chan.ConfirmedMove(None,None,None,None,None,None,None,None,None,now+timedelta(days=1))
        assert chain==chan.analyze_point_chain(units+[poison],rows,now,'F2'),'未来结构字段读取'
        unresolved.update(chain.unresolved_move_ids)
        streams=[chain.first_points,chain.second_points,chain.third_points]
        for i,points in enumerate(streams):
            assert previous[i].issubset(set(points)),'已成立点位修订/撤销'
            previous[i]=set(points)
            for p in points:
                identity=p.point_id if i==0 else (p.context_id,p.kind,p.dt)
                unique[i][identity]=p.kind
                assert p.confirmed_dt<=now and p.dt<=p.confirmed_dt
                examples.setdefault(p.kind,p.to_dict())
        for context in chain.contexts:
            center=context.causal_center
            if center:
                assert center.confirmed_dt<=now
                if center.center_id in centers:assert centers[center.center_id]==center,'引发中枢回写'
                centers[center.center_id]=center
        for f in chain.formations:snapshots[f.kind+':'+f.phase]+=1
    scan=chan.scan_first_points(units,rows,now,'F2')
    return dict(completed_f2_types=scan.completed_types,
                first_exclusions=dict(Counter(reason for identity,reason in scan.exclusions)),
                unresolved_flat_types=len(unresolved),period=period,observations=len(stops),rows=len(rows),anchor_factor=anchor,
                warm_f1=warm,total_f1=len(bases),points=[dict(Counter(x.values())) for x in unique],
                causal_centers=len(centers),point_revisions=0,base_revisions=0,center_revisions=0,
                prefix_checks=len(stops),future_poison_checks=len(stops),formation_snapshots=dict(snapshots),
                examples=examples,price_precision=precision)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--parts',choices=['bi','xd'],default='bi')
    args=parser.parse_args();root=args.dataset.resolve();files=[]
    daily=load_frames(root,'1d',CODES,files);minutes=load_frames(root,'30m',CODES,files)
    report=dict(version=chan.__version__,dataset=str(root),manifest_sha256=digest(root/'manifest.json'),
                files=files,base_parts=args.parts,scope=__doc__,assets=[],errors=[],
                source_sha256={p.name:digest(p) for p in sorted((Path(__file__).resolve().parents[1]/'src/chan').glob('*.py'))})
    for code in CODES:
        try:
            item=dict(code=code,day=check(daily[code],'1d',args.parts),minute=check(minutes[code],'30m',args.parts))
            report['assets'].append(item);print(code,'OK',flush=True)
        except Exception as e:
            report['errors'].append(dict(code=code,error=repr(e)));print(code,repr(e),flush=True)
    report['ok']=len(report['assets'])==len(CODES) and not report['errors']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    sys.exit(0 if report['ok'] else 1)

if __name__=='__main__':main()
