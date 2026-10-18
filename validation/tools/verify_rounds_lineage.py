# -*- coding: utf-8 -*-
"""轮次移交与中枢演化谱系的真实行情逐前缀回放验收(0.11.5)。

实现回放收据, 不冒充R2独立人工标注: 谱系事件/快照前缀零回写、
轮次锚点与已确认点位前缀冻结、移交单向登记、构造终态冻结为
机器断言; 事件语义正确性由合成测试与原文核验承担。基础单元
沿用锁定已知价格锚的固定笔同级切分声明F1; F1真理论仍须人工
原图验收, K线周期不等于走势级别。行情关闭/到达是测试约定,
不证明真实供应版本及聚宽时效。真实窗口无一类点触发时轮次
台账为空但须保持稳定, 排除原因分布如实入收据。
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_core_history import CODES,bars_from,digest,load_frames
from verify_core_available import prepare_prices
from verify_ma_history import timed
from verify_completion_history import shape
import chan

TERMINAL = ('completed','failed')


def absorb_lineage(lineage,previous_events,previous_centers):
    """谱系事件/快照严格前缀断言, 返回新前缀(零回写)。"""
    assert lineage.events[:len(previous_events)]==previous_events,'谱系事件回写'
    assert lineage.centers[:len(previous_centers)]==previous_centers,'谱系快照回写'
    return lineage.events,lineage.centers


def absorb_rounds(rounds,ledger):
    """轮次台账吸收: 锚点/中枢/点位前缀冻结, 移交与构造单向推进。"""
    seen_ids=set()
    for item in rounds.rounds:
        seen_ids.add(item.round_id)
        state=ledger.get(item.round_id)
        if state is None:
            ledger[item.round_id]=dict(side=item.side,anchor=item.anchor,
                previous_center=item.previous_center,causal_center=item.causal_center,
                second_points=item.second_points,third_points=item.third_points,
                formation=item.formation,handed_over=item.handed_over_dt)
            continue
        assert state['side']==item.side,'轮次方向回写'
        assert state['anchor']==item.anchor,'锚点回写'
        assert item.second_points[:len(state['second_points'])]==state['second_points'],'二类点回写'
        assert item.third_points[:len(state['third_points'])]==state['third_points'],'三类点回写'
        for name in ('previous_center','causal_center'):
            if state[name] is not None:assert state[name]==getattr(item,name),'轮次中枢回写'
            state[name]=getattr(item,name)
        if state['formation'].phase in TERMINAL:
            assert state['formation']==item.formation,'构造终态回写'
        state['formation']=item.formation
        state['second_points']=item.second_points
        state['third_points']=item.third_points
        if state['handed_over'] is not None:
            assert state['handed_over']==item.handed_over_dt,'移交时刻回写'
        state['handed_over']=item.handed_over_dt
    assert set(ledger).issubset(seen_ids),'轮次撤销'
    return ledger


def build_bases(result,parts_list,bases,bodies,now,name_prefix):
    """同级切分完成单元的增量账本; 修订/撤销即断言失败。"""
    current={}
    for move in chan.same_level_decompose(parts_list):
        if not move.complete:continue
        a,b=parts_list[move.seg_start],parts_list[move.seg_end]
        name=name_prefix+':'+str(move.start_dt)
        names=tuple(name_prefix+':'+str(u.start_dt) for u in parts_list[move.seg_start:move.seg_end+1])
        body=(shape(move),a.start_value,b.end_value,names);current[name]=body
        if name not in bases:
            bases[name]=chan.ConfirmedMoveType(name,'F1',move.kind,move.direction,
                move.start_dt,move.end_dt,a.start_value,b.end_value,move.low,move.high,now,
                names,tuple(name_prefix+':'+str(u.start_dt) for u in parts_list),tuple(move.centers))
            bodies[name]=body
        else:assert bodies[name]==body,'基础完成类型修订'
    assert set(bases).issubset(current),'基础完成类型撤销'
    return current


def scan_stats(units,rows,now,level='F2'):
    """末观察一类候选扫描统计: 完成数/候选数与排除原因分布。"""
    scan=chan.scan_first_points(units,rows,now,level)
    return dict(completed_types=scan.completed_types,
                first_points=len(scan.points),
                exclusions=dict(Counter(reason for _,reason in scan.exclusions)))


def summarize(ledger,lineage,period,extra):
    """台账与谱系汇总; 各回写计数恒为断言通过后的零。"""
    events=Counter(e.kind for e in lineage.events)
    hands=sum(1 for state in ledger.values() if state['handed_over'] is not None)
    formations=Counter(state['formation'].kind+':'+state['formation'].phase
                       for state in ledger.values())
    examples={}
    for state in ledger.values():
        examples.setdefault(state['side'],dict(
            anchor=str(state['anchor'].confirmed_dt),
            anchor_dt=str(state['anchor'].dt),
            handed_over=str(state['handed_over']),
            seconds=len(state['second_points']),thirds=len(state['third_points']),
            phase=state['formation'].phase))
    out=dict(period=period,rounds=len(ledger),
             rounds_by_side=dict(Counter(s['side'] for s in ledger.values())),
             handovers=hands,formation_snapshots=dict(formations),
             lineage_centers=len(lineage.centers),
             lineage_events=dict(events),
             event_bases=dict(Counter(e.basis for e in lineage.events if e.basis)),
             round_examples=examples,
             event_revisions=0,snapshot_revisions=0,anchor_revisions=0,
             point_revisions=0,handover_rewrites=0,terminal_rewrites=0)
    out.update(extra)
    return out


def replay(rows,stops,period,future_every=None):
    """统一逐前缀回放: 谱系/轮次台账断言与采样未来检查。

    future_every为None时逐停点做rows[:stop]等价与未来结构投毒;
    给定时按其间隔采样以控制长窗口成本, 采样数如实入收据。
    """
    bases,bodies={},{}
    previous_events=();previous_centers=();ledger={}
    warm=0;future_checks=0;prefix_checks=0
    rounds=lineage=None
    for obs,stop in enumerate(stops):
        now=rows[stop-1]['available_dt']
        result=chan.analyze_available(rows,now)
        build_bases(result,result.bis[:-1],bases,bodies,now,'bi')
        if obs==0:warm=len(bases)
        units=sorted(bases.values(),key=lambda u:u.start_dt)
        lineage=chan.track_center_lineage(units,now,'F2','F3')
        previous_events,previous_centers=absorb_lineage(lineage,previous_events,previous_centers)
        prefix_checks+=1
        rounds=chan.track_rounds(units,rows,now,'F2')
        absorb_rounds(rounds,ledger)
        if future_every is None or (obs+1)%future_every==0:
            assert rounds==chan.track_rounds(units,rows[:stop],now,'F2'),'未来行情改变轮次视图'
            poison=chan.ConfirmedMove(None,None,None,None,None,None,None,None,None,now+timedelta(days=1))
            assert rounds==chan.track_rounds(units+[poison],rows,now,'F2'),'未来结构字段读取'
            future_checks+=1
    dot=chan.causal_graph_dot(lineage=lineage,round_chain=rounds,
                              title='replay '+period)
    assert dot==chan.causal_graph_dot(lineage=lineage,round_chain=rounds,
                                      title='replay '+period),'因果图非确定'
    units=sorted(bases.values(),key=lambda u:u.start_dt)
    return summarize(ledger,lineage,period,dict(
        observations=len(stops),rows=len(rows),warm_f1=warm,total_f1=len(bases),
        first_scan=scan_stats(units,rows,rows[stops[-1]-1]['available_dt']),
        future_checks=future_checks,prefix_checks=prefix_checks,dot_checks=1,
        dot_lines=dot.count('\n')))


def check(frame,period,max_stops=160):
    """日线全2026观察与30m全2026分区的逐前缀回放。"""
    key='trade_date' if period=='1d' else 'trade_time'
    first=next(i for i,t in enumerate(frame[key]) if t.year==2026)
    anchor=float(frame['adj_factor'].iloc[first])
    precision=None
    if period!='1d':frame,precision=prepare_prices(frame)
    rows=timed(bars_from(frame,period,anchor=anchor),period)
    if period=='1d':stops=list(range(first+1,len(frame)+1))
    else:
        step=max(1,int(math.ceil(len(rows)/float(max_stops))))
        stops=list(range(step,len(rows)+1,step))
        if stops[-1]!=len(rows):stops.append(len(rows))
    out=replay(rows,stops,period)
    out['anchor_factor']=anchor
    out['price_precision']=precision
    return out


def check_minute1(frame,max_stops=120,future_every=10):
    """1m全2026分区逐前缀回放; 未来检查按间隔采样控成本。"""
    frame,precision=prepare_prices(frame)
    anchor=float(frame['adj_factor'].iloc[0])
    rows=timed(bars_from(frame,'1m',anchor=anchor),'1m')
    step=max(1,int(math.ceil(len(rows)/float(max_stops))))
    stops=list(range(step,len(rows)+1,step))
    if stops[-1]!=len(rows):stops.append(len(rows))
    out=replay(rows,stops,'1m',future_every=future_every)
    out['anchor_factor']=anchor
    out['price_precision']=precision
    out['stop_step']=step
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.dataset.resolve();files=[]
    daily=load_frames(root,'1d',CODES,files)
    minutes=load_frames(root,'30m',CODES,files)
    minute1=load_frames(root,'1m',CODES,files)
    report=dict(version=chan.__version__,dataset=str(root),manifest_sha256=digest(root/'manifest.json'),
                files=files,scope=__doc__,assets=[],errors=[],
                source_sha256={p.name:digest(p) for p in sorted((Path(__file__).resolve().parents[2]/'src/chan').glob('*.py'))})
    for code in CODES:
        try:
            item=dict(code=code,day=check(daily[code],'1d'),
                      minute30=check(minutes[code],'30m'),
                      minute1=check_minute1(minute1[code]))
            report['assets'].append(item);print(code,'OK',flush=True)
        except Exception as e:
            report['errors'].append(dict(code=code,error=repr(e)));print(code,repr(e),flush=True)
    report['ok']=len(report['assets'])==len(CODES) and not report['errors']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    sys.exit(0 if report['ok'] else 1)


if __name__=='__main__':main()
