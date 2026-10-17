# -*- coding: utf-8 -*-
"""完成走势递归的真实行情接线与前缀验收, 不替代独立理论标注。

最低层明确选已固定笔或这些笔上的已完成线段, 再由same_level_decompose构造
F1走势类型; 不将单笔/单线段当ConfirmedMove。F1的真实理论正确性
未有人工作图标注。暖机历史仅在2026首观察时统一声明已知, 不反推
历史确认日。之后F1首次观察时间为保守到达证明, 完成后不得修改。
价格锚锁在2026首观察日因子; 日线15:00闭合/15:05到达和30m结束
后1分钟为测试约定, 不证明供应版本、聚宽时效、收益或交易有效性。
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_core_history import CODES, bars_from, digest, load_frames
from verify_core_available import prepare_prices
from verify_ma_history import timed
import chan


def shape(move):
    """f2结构的独立结果字段, 不以本入口时间字段自证确认。"""
    return (move.kind,move.direction,move.start_dt,move.end_dt,move.low,move.high,tuple(move.centers))


def reference(units, now, level, seen):
    """当前到达批的普通f2结果加独立首次出现账本, 核对时间接线。"""
    completed=[m for m in chan.level_up(units) if m.complete]
    for move in completed:
        key=shape(move)
        seen.setdefault(key,now)
    return completed


def check(frame,period,parts):
    key='trade_date' if period=='1d' else 'trade_time'
    first=next(i for i,time in enumerate(frame[key]) if time.year==2026)
    anchor=float(frame['adj_factor'].iloc[first])
    precision=None
    if period!='1d':frame,precision=prepare_prices(frame)
    rows=timed(bars_from(frame,period,anchor=anchor),period)
    if period=='1d':stops=list(range(first+1,len(frame)+1))
    else:
        days=sorted(set(row['dt'].date() for row in rows))[-20:]
        stops=[i+1 for i,row in enumerate(rows) if row['dt'].date() in days]
    bases,base_records={},{}
    expected_seen=[{},{}]
    old=[set(),set()]
    snapshots=[Counter(),Counter()]
    unique=[{},{}]
    examples=[{},{}]
    warm_count=0
    conversions=Counter()
    for observation,stop in enumerate(stops):
        now=rows[stop-1]['available_dt']
        result=chan.analyze_available(rows,now)
        components=(result.bis[:-1] if parts=='bi' else
                    [x for x in chan.find_xds(result.bis[:-1]) if x.complete])
        f1=[m for m in chan.same_level_decompose(components) if m.complete]
        current={}
        for move in f1:
            a,b=components[move.seg_start],components[move.seg_end]
            name='f1:'+str(move.start_dt)
            unit_ids=tuple(parts+':'+str(u.start_dt) for u in components[move.seg_start:move.seg_end+1])
            body=(shape(move),a.start_value,b.end_value,unit_ids)
            current[name]=body
            if name not in bases:
                bases[name]=chan.ConfirmedMoveType(name,'F1',move.kind,move.direction,
                    move.start_dt,move.end_dt,a.start_value,b.end_value,move.low,move.high,now,
                    unit_ids,tuple(parts+':'+str(u.start_dt) for u in components),tuple(move.centers))
                base_records[name]=body
            else:assert base_records[name]==body,'基础完成类型修订'
        assert set(bases).issubset(current),'基础完成类型撤销'
        if observation==0:warm_count=len(bases)
        inputs=sorted(bases.values(),key=lambda u:u.start_dt)
        for k,level in enumerate(['F2','F3']):
            actual=chan.confirm_level_up(inputs,now,level)
            plain=reference(inputs,now,level,expected_seen[k])
            assert [shape(m) for m in actual]==[shape(m) for m in plain],'普通f2算术/分解不一致'
            assert all(m.confirmed_dt==expected_seen[k][shape(m)] for m in actual),'证据到达确认不一致'
            assert old[k].issubset(set(actual)),'递归完成类型修订/撤销'
            old[k]=set(actual)
            future=chan.ConfirmedMove(None,None,None,None,None,float('nan'),None,None,None,now+timedelta(days=1))
            assert actual==chan.confirm_level_up(inputs+[future],now,level),'未来毒字段读取'
            visible=[u for u in inputs if u.confirmed_dt<=now]
            assert actual==chan.confirm_level_up(visible,now,level),'独立输入前缀不一致'
            before=now-timedelta(microseconds=1)
            previous_inputs=[u for u in inputs if u.confirmed_dt<=before]
            assert chan.confirm_level_up(inputs,before,level)==chan.confirm_level_up(previous_inputs,before,level)
            by_id={u.move_id:u for u in inputs}
            for move in actual:
                constituents=[by_id[name] for name in move.unit_ids]
                proof=[by_id[name] for name in move.evidence_ids]
                assert move.confirmed_dt==max(u.confirmed_dt for u in proof)
                assert move.low==min(u.low for u in constituents) and move.high==max(u.high for u in constituents)
                snapshots[k][move.kind]+=1
                unique[k][move.move_id]=move.kind
                examples[k].setdefault(move.kind,move.to_dict())
                if move.start_price==move.end_price:
                    conversions['flat_not_convertible']+=1
                else:
                    point=move.to_confirmed_move()
                    assert point.confirmed_dt==move.confirmed_dt
                    assert (point.low,point.high)==(move.low,move.high)
                    conversions['convertible_snapshot']+=1
            inputs=actual
    return dict(period=period,rows=len(frame),observations=len(stops),anchor_factor=anchor,
        anchor_dt=str(rows[first]['dt']),warm_base_count=warm_count,total_base_count=len(bases),
        new_base_count=len(bases)-warm_count,base_record_revisions=0,recursive_record_revisions=0,
        levels=[dict(level=level,unique_types=dict(Counter(unique[k].values())),
                     snapshot_counts=dict(snapshots[k]),examples=examples[k])
                for k,level in enumerate(['F2','F3'])],conversion_snapshots=dict(conversions),
        future_poison_checks=2*len(stops),independent_prefix_checks=2*len(stops),
        before_arrival_checks=2*len(stops),price_precision=precision)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--parts',choices=['bi','xd'],default='xd',help='声明最低层f1构造配件, 不对应K线分钟级别')
    args=parser.parse_args()
    root,receipt=args.dataset.resolve(),[]
    daily=load_frames(root,'1d',CODES,receipt)
    minutes=load_frames(root,'30m',CODES,receipt)
    report=dict(version=chan.__version__,dataset=str(root),manifest_sha256=digest(root/'manifest.json'),
                files=receipt,scope=__doc__,base_parts=args.parts,assets=[],errors=[])
    for code in CODES:
        try:
            asset=dict(code=code,day=check(daily[code],'1d',args.parts),minute=check(minutes[code],'30m',args.parts))
            report['assets'].append(asset)
            print(code,'day',asset['day']['total_base_count'],'minute',asset['minute']['total_base_count'],'OK',flush=True)
        except Exception as error:
            report['errors'].append(dict(code=code,error=repr(error)))
            print(code,repr(error),flush=True)
    report['ok']=len(report['assets'])==len(CODES) and not report['errors']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    sys.exit(0 if report['ok'] else 1)


if __name__=='__main__':main()
