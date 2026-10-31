# -*- coding: utf-8 -*-
"""自动MACD辅助一类/因果中枢/点位链的真实行情与时间接线验收。

使用锁定已知价格锚、固定笔或其完成线段经同级切分声明F1。F1真理论
仍须人工原图验收, K线周期不等于走势级别。暖机历史只在首观察声明
已知。行情关闭/到达是测试约定, 不证明真实供应版本及聚宽时效。

--packet消费既有chan-real-sample-v1原始包，不读取其dataset路径。
全原始前缀冻结F1，消费者只在实际F1到达批及末观察验收；报告仍为
运行时发现，不生成独立理论标签。两种模式均拒绝覆盖已有收据。
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
import hashlib
import math
from numbers import Real
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_core_history import CODES,bars_from,digest,load_frames
from verify_core_available import prepare_prices
from verify_ma_history import timed
from verify_completion_history import shape
from scan_real_rounds import constant_factor
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


def _packet_bars(packet):
    """接收既有单标的原始样本合同；不读取包内dataset路径或继承标签。"""
    if not isinstance(packet, dict) or packet.get('schema_version') != 'chan-real-sample-v1':
        raise ValueError('单包模式要求chan-real-sample-v1原始样本')
    if packet.get('timezone', 'Asia/Shanghai') != 'Asia/Shanghai' or packet.get('adjustment', 'none') != 'none':
        raise ValueError('单包须为北京时间未复权报价，不接受冲突声明')
    rule = packet.get('sampling_rule', {})
    if not isinstance(rule, dict):
        raise ValueError('单包sampling_rule须显式声明周期、代码和观察范围')
    periods, codes, window = (rule.get(k) for k in ('periods', 'codes', 'window'))
    if not isinstance(periods, list) or len(periods) != 1 or periods[0] not in ('1d', '5m', '15m', '30m', '60m'):
        raise ValueError('单包须声明一个受支持周期')
    if not isinstance(codes, list) or len(codes) != 1 or not isinstance(codes[0], str) or not codes[0].strip():
        raise ValueError('单包须声明单一标的')
    if not isinstance(window, list) or len(window) != 2:
        raise ValueError('单包须声明起止日期')
    for value in window:
        if not isinstance(value, str) or datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') != value:
            raise ValueError('单包起止日期须为YYYY-MM-DD')
    if window[0] > window[1]:
        raise ValueError('单包起止日期倒置')
    rows = packet.get('rows')
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise ValueError('单包原始行不能为空且须为对象序列')
    factor = constant_factor(rows)
    bars, previous, width = [], None, None
    for row in rows:
        stamp = row.get('dt')
        if not isinstance(stamp, str) or len(stamp) not in (10, 19) or (width is not None and len(stamp) != width):
            raise ValueError('原始时间须为一致的北京时间日期/时间标签')
        width = len(stamp)
        fmt = '%Y-%m-%d' if len(stamp) == 10 else '%Y-%m-%d %H:%M:%S'
        dt = datetime.strptime(stamp, fmt)
        if dt.strftime(fmt) != stamp or (previous is not None and dt <= previous):
            raise ValueError('原始时间须规范且严格递增，不排序或去重')
        if not window[0] <= stamp[:10] <= window[1] or row.get('ts_code') != codes[0]:
            raise ValueError('原始行超出声明日期或混入其他标的')
        daily = periods[0] == '1d'
        if (daily and dt.time() != datetime.min.time()) or (not daily and (len(stamp) != 19 or dt.time() == datetime.min.time())):
            raise ValueError('周期声明与原始时间粒度不一致')
        prices = [row.get(k) for k in ('open', 'high', 'low', 'close')]
        volume = row.get('vol')
        if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v <= 0 for v in prices):
            raise ValueError('单包OHLC须为有限正实数')
        if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
            raise ValueError('单包OHLC包络无效，不修价')
        if isinstance(volume, bool) or not isinstance(volume, Real) or not math.isfinite(volume) or volume < 0:
            raise ValueError('单包量须有限非负；零量保留')
        closed = dt+timedelta(hours=15 if daily else 0)
        bars.append(dict(dt=dt, open=row['open'], high=row['high'], low=row['low'],
                         close=row['close'], volume=volume, closed_dt=closed,
                         available_dt=closed+timedelta(minutes=5 if daily else 1)))
        previous = dt
    return bars, dict(period=periods[0], code=codes[0], window=list(window), rows=len(bars),
                      factor=factor, factor_rule='positive constant factor; raw prices preserved',
                      timezone='Asia/Shanghai (input schema declaration)',
                      availability='daily 15:05 / minute label +1m; test convention only')


def check_packet(packet, parts='bi', standard='106'):
    """全原始前缀确认F1，按实际F1到达批验收消费者；输出仍是运行时发现。"""
    if parts not in ('bi', 'xd') or standard not in ('81', '106'):
        raise ValueError('不支持的配件或笔标准')
    rows, metadata = _packet_bars(packet)
    bases, bodies, first_seen, batches, centers = {}, {}, [], [], {}
    previous_points, previous_types = [set(), set(), set()], set()
    for stop in range(1, len(rows)+1):
        fixed = chan.chan_fx_bi(rows[:stop], standard=standard)[2][:-1]
        units = fixed if parts == 'bi' else [x for x in chan.find_xds(fixed) if x.complete]
        current, added = {}, False
        now = rows[stop-1]['available_dt']
        for move in chan.same_level_decompose(units):
            if not move.complete:
                continue
            a, z = move.seg_start, move.seg_end
            identity = 'F1:'+str(move.start_dt)
            names = tuple(parts+':'+str(u.start_dt) for u in units[a:z+1])
            body = (shape(move), units[a].start_value, units[z].end_value, names)
            current[identity] = body
            if identity not in bases:
                bases[identity] = chan.ConfirmedMoveType(
                    identity, 'F1', move.kind, move.direction, move.start_dt, move.end_dt,
                    units[a].start_value, units[z].end_value, move.low, move.high, now,
                    names, tuple(parts+':'+str(u.start_dt) for u in units), tuple(move.centers))
                bodies[identity] = body
                first_seen.append(dict(raw_count=stop, part_span=[a, z], snapshot=bases[identity].to_dict()))
                added = True
            elif bodies[identity] != body:
                raise ValueError('单包基础完成类型修订')
        if not set(bases).issubset(current):
            raise ValueError('单包基础完成类型撤销')
        if not added and stop != len(rows):
            continue  # 价格连续且端点已到；消费者在F1实际到达批及末观察核对。
        typed = sorted(bases.values(), key=lambda u: u.start_dt)
        higher = chan.confirm_level_up(typed, now, 'F2')
        strict = chan.scan_strict_divergence(typed, now, 'F2')
        auxiliary = chan.scan_first_points(typed, rows, now, 'F2')
        chain = chan.analyze_point_chain(typed, rows, now, 'F2')
        poisoned = [dict(r) for r in rows]
        for row in poisoned[stop:]:
            row.pop('open')
            row.update(high=float('nan'), low=-999, close=99999)
        future = chan.ConfirmedMove(None, None, None, None, None, None, None, None, None, now+timedelta(days=1))
        if chain != chan.analyze_point_chain(typed, rows[:stop], now, 'F2') or chain != chan.analyze_point_chain(typed+[future], poisoned, now, 'F2'):
            raise ValueError('单包未来行情/结构改变点位链')
        if strict != chan.scan_strict_divergence(typed+[future], now, 'F2'):
            raise ValueError('单包未来结构改变严格扫描')
        if not previous_types.issubset(set(higher)):
            raise ValueError('单包完成F2修订或撤销')
        previous_types = set(higher)
        for i, stream in enumerate((chain.first_points, chain.second_points, chain.third_points)):
            if not previous_points[i].issubset(set(stream)):
                raise ValueError('单包已输出点位修订或撤销')
            previous_points[i] = set(stream)
        for context in chain.contexts:
            center = context.causal_center
            if center is not None:
                if center.center_id in centers and centers[center.center_id] != center:
                    raise ValueError('单包因果中枢回写')
                centers[center.center_id] = center
        before = now-timedelta(microseconds=1)
        visible = [u for u in typed if u.confirmed_dt <= before]
        if chan.confirm_level_up(typed, before, 'F2') != chan.confirm_level_up(visible, before, 'F2'):
            raise ValueError('单包确认前读取到达批')
        batches.append(dict(raw_count=stop, f1_count=len(typed), f2=[x.to_dict() for x in higher],
                            strict=strict.to_dict(), auxiliary=auxiliary.to_dict(), chain=chain.to_dict()))
    return dict(schema_version='chan-complete-f1-packet-check-v1', annotation='runtime_discovery_not_independent_labels',
                version=chan.__version__, input=metadata, base_parts=parts, standard=standard,
                xd_origin='legacy_default' if parts == 'xd' else None, theoretical_acceptance=False,
                raw_prefixes=len(rows), consumer_batches=len(batches), f1=first_seen, batches=batches,
                checks=dict(base_revisions=0, point_revisions=0, center_revisions=0,
                            future_poison_checks=len(batches), before_arrival_checks=len(batches)), ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path,nargs='?')
    parser.add_argument('--packet',type=Path,help='单一chan-real-sample-v1冻结原始包；不读取其中dataset路径')
    parser.add_argument('--standard',choices=['81','106'],help='仅单包模式；默认106，全窗和前缀相同标准')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--parts',choices=['bi','xd'],default='bi')
    args=parser.parse_args()
    if (args.dataset is None) == (args.packet is None):
        parser.error('数据集与--packet须恰选一种')
    if args.standard is not None and args.packet is None:
        parser.error('--standard仅用于单包模式，历史数据集默认合同保持')
    if args.output.exists() or args.output.is_symlink():
        parser.error('拒绝覆盖已有验收收据，使用新输出路径')
    output=args.output.resolve()
    if args.packet is not None:
        source=args.packet.resolve()
        raw=source.read_bytes()
        packet_sha=hashlib.sha256(raw).hexdigest()
        package=Path(chan.__file__).resolve().parent
        source_hashes={p.name:digest(p) for p in sorted(package.glob('*.py'))}
        try:
            report=check_packet(json.loads(raw.decode('utf-8')),args.parts,args.standard or '106')
        except ValueError as error:
            parser.error(str(error))
        report.update(packet=str(source),packet_sha256=packet_sha,
                      chan_path=str(Path(chan.__file__).resolve()),source_sha256=source_hashes)
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
        return
    root=args.dataset.resolve();files=[]
    daily=load_frames(root,'1d',CODES,files);minutes=load_frames(root,'30m',CODES,files)
    report=dict(version=chan.__version__,dataset=str(root),manifest_sha256=digest(root/'manifest.json'),
                files=files,base_parts=args.parts,scope=__doc__,assets=[],errors=[],
                source_sha256={p.name:digest(p) for p in sorted((Path(__file__).resolve().parents[2]/'src/chan').glob('*.py'))})
    for code in CODES:
        try:
            item=dict(code=code,day=check(daily[code],'1d',args.parts),minute=check(minutes[code],'30m',args.parts))
            report['assets'].append(item);print(code,'OK',flush=True)
        except Exception as e:
            report['errors'].append(dict(code=code,error=repr(e)));print(code,repr(e),flush=True)
    report['ok']=len(report['assets'])==len(CODES) and not report['errors']
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    sys.exit(0 if report['ok'] else 1)

if __name__=='__main__':main()
