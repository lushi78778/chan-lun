# -*- coding: utf-8 -*-
"""R2真实ETF样本准备: 文件完整性、指定十标的原始数据概况与快照提取。

本工具不导入chan, 不运行识别器, 不生成理论真值。profile核对全部频率
文件摘要, 仅对显式频率和标的读取原始字段; extract固定观察日并保留
原始OHLC/复权因子, 不填空、不修价、不选择暖机或自动认定分钟到达时刻。
本地Python3.10+及pyarrow环境使用, 不加入核心包依赖。
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

CODES = ['510300.SH','510500.SH','512880.SH','512480.SH','159915.SZ',
         '513100.SH','518880.SH','511010.SH','588000.SH','516160.SH']


def digest(path):
    """分块计算只读源文件SHA-256, 不依赖文件可驻内存。"""
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def source_path(dataset, relative):
    """manifest路径只能指向数据集内部, 不写入源数据。"""
    path = (dataset/relative).resolve()
    path.relative_to(dataset)
    return path


def load_manifest(dataset):
    manifest = json.loads((dataset/'manifest.json').read_text())
    if manifest['timezone']!='Asia/Shanghai' or manifest['adjustment']!='none':
        raise ValueError('当前提取规格要求北京时间的未复权原始数据')
    return manifest


def read_file(dataset, item, period, codes):
    import pyarrow.parquet as pq
    path = source_path(dataset,item['path'])
    actual = digest(path)
    if actual!=item['sha256']:
        raise ValueError('源文件摘要不一致: '+str(path))
    time_key = 'trade_date' if period=='1d' else 'trade_time'
    keys = ['ts_code',time_key,'open','high','low','close','vol','adj_factor']
    frame = pq.read_table(path,columns=keys,filters=[('ts_code','in',codes)]).to_pandas()
    return frame,time_key


def profile(dataset, manifest, periods, codes):
    """全频率摘要独立核对; 指定频率逐文件分组审计, 避免全库驻内存。

    唯一键为代码+时间; 分区之间须严格递增。精确包络违规与大于
    1e-12的违规分别计数, 仅分类误差, 原始价格不改。0成交量是否
    停牌没有供应规格, 只统计不删除。全库空因子和标的空因子分开。
    """
    import numpy as np
    import pyarrow.parquet as pq
    receipt = {'file_checks':[],'periods':{},'profiles':{},'issues':[]}
    checksums = {}
    for line in (dataset/'checksums.sha256').read_text().splitlines():
        checksum,name = line.split(None,1)
        checksums[name.strip()] = checksum
    for period, spec in manifest['datasets'].items():
        stats = {'manifest_rows':spec['row_count'],'files':len(spec['files']),
                 'min_time':min(f['min_time'] for f in spec['files']),
                 'max_time':max(f['max_time'] for f in spec['files']),
                 'manifest_null_adj_factor':sum(f['null_counts'].get('adj_factor',0) for f in spec['files'])}
        receipt['periods'][period] = stats
        schema_path = source_path(dataset,spec['schema_file'])
        if checksums.get(spec['schema_file'])!=digest(schema_path):
            raise ValueError('schema摘要不一致: '+str(schema_path))
        if sum(f['row_count'] for f in spec['files'])!=spec['row_count']:
            raise ValueError('manifest文件行数与频率总数不一致: '+period)
        if period in periods:
            receipt['profiles'][period] = {code:{'rows':0,'nulls':{},'duplicate_keys':0,
                'out_of_order_files':0,'invalid_prices':0,'exact_envelope_violations':0,
                'material_envelope_violations':0,'invalid_factors':0,'zero_volume':0,
                'negative_volume':0,'examples':{},'first_time':None,'last_time':None} for code in codes}
        for item in spec['files']:
            path = source_path(dataset,item['path'])
            actual = digest(path)
            if actual!=item['sha256'] or checksums.get(item['path'])!=actual or path.stat().st_size!=item['size_bytes']:
                raise ValueError('文件manifest/checksums/长度不一致: '+str(path))
            if pq.read_metadata(path).num_rows!=item['row_count']:
                raise ValueError('Parquet物理行数不一致: '+str(path))
            receipt['file_checks'].append({'path':item['path'],'sha256':actual,'size_bytes':path.stat().st_size})
            if period not in periods:
                continue
            frame,key = read_file(dataset,item,period,codes)
            for code,group in frame.groupby('ts_code'):
                out = receipt['profiles'][period][code]
                if not group[key].is_monotonic_increasing:
                    out['out_of_order_files'] += 1
                first,last = str(group[key].min()),str(group[key].max())
                if out['last_time'] is not None and first<=out['last_time']:
                    raise ValueError('跨文件代码时间重叠,须先裁决源数据: '+code+' '+period)
                out['first_time'] = out['first_time'] or first
                out['last_time'] = last
                out['rows'] += len(group)
                out['duplicate_keys'] += int(group.duplicated([key]).sum())
                for column,count in group.isna().sum().items():
                    out['nulls'][column] = out['nulls'].get(column,0)+int(count)
                prices = group[['open','high','low','close']].values
                invalid_prices = ~np.isfinite(prices).all(axis=1)|(prices<=0).any(axis=1)
                out['invalid_prices'] += int(invalid_prices.sum())
                violation = np.maximum.reduce([group['low'].values-group['high'].values,
                    group[['open','close']].max(axis=1).values-group['high'].values,
                    group['low'].values-group[['open','close']].min(axis=1).values])
                out['exact_envelope_violations'] += int((violation>0).sum())
                out['material_envelope_violations'] += int((violation>1e-12).sum())
                factors = group['adj_factor'].values
                out['invalid_factors'] += int((~np.isfinite(factors)|(factors<=0)).sum())
                out['zero_volume'] += int((group['vol']==0).sum())
                out['negative_volume'] += int((group['vol']<0).sum())
                masks = {'invalid_prices':invalid_prices,'invalid_factors':~np.isfinite(factors)|(factors<=0),
                         'material_envelope_violations':violation>1e-12}
                for check,mask in masks.items():
                    examples = out['examples'].setdefault(check,[])
                    for _,row in group.loc[mask].head(max(0,5-len(examples))).iterrows():
                        record = {'path':item['path'],'dt':str(row[key])}
                        for column in ['open','high','low','close','vol','adj_factor']:
                            value = float(row[column])
                            record[column] = value if math.isfinite(value) else None
                        examples.append(record)
    for period, assets in receipt['profiles'].items():
        for code,stats in assets.items():
            if not stats['rows']:
                receipt['issues'].append({'period':period,'code':code,'check':'missing_instrument','count':1})
            for key in ['duplicate_keys','out_of_order_files','invalid_prices','material_envelope_violations','invalid_factors','negative_volume']:
                if stats[key]:
                    receipt['issues'].append({'period':period,'code':code,'check':key,'count':stats[key]})
    receipt['integrity_ok'] = True
    receipt['selected_rows_usable'] = not receipt['issues']
    receipt['scope'] = '全频率文件摘要;仅显式periods和codes的数据行检查,非全2693标的语义验收'
    receipt['limits'] = ['时间戳是否为区间开始/结束未实测,不生成closed_dt/available_dt',
                         '0量是否为停牌未知;不删除0量行','历史发布版本缺失,不证明供应数据当时未修订']
    return receipt


def packet_records(frame, period, start, observation):
    """先截观察日, 再验证和导出原始行; 日线观察日包括当日收盘数据。

    observation为已收盘的信号日, 分钟时间只作为原始字段保留; 平台
    区间结束及供应到达时间未核验。本函数不计算结构和EMA, 不宣称
    分钟盘中可见性。缺复权因子直接拒绝, 不以未来最后因子补空。
    """
    import pandas as pd
    first_day = datetime.strptime(str(start),'%Y-%m-%d')
    observation_day = datetime.strptime(str(observation),'%Y-%m-%d')
    if first_day>observation_day:
        raise ValueError('开始日不得晚于观察日')
    key = 'trade_date' if period=='1d' else 'trade_time'
    dates = pd.to_datetime(frame[key])
    # 信号日边界通过下一日严格小于比较, 避免漏掉日内秒/微秒。
    end = pd.Timestamp(observation_day)+pd.Timedelta(days=1)
    visible = frame.loc[(dates>=pd.Timestamp(first_day)) & (dates<end)].copy()
    visible = visible.sort_values(key)
    if visible.empty or visible.duplicated(['ts_code',key]).any():
        raise ValueError('样本为空或存在重复代码时间')
    rows = []
    for _,row in visible.iterrows():
        record = {'ts_code':str(row['ts_code']),'dt':str(row[key])}
        for column in ['open','high','low','close','vol','adj_factor']:
            value = float(row[column])
            if not math.isfinite(value) or (column!='vol' and value<=0) or (column=='vol' and value<0):
                raise ValueError('观察前缀字段无效: '+column)
            record[column] = value
        # 提取包保留原始报价; 连浮点末位包络差也不在此处修正。
        # profile把精确差与大于1e-12的差分列, 供后续裁决源数据。
        if (record['low'] > min(record['open'], record['close']) or
                record['high'] < max(record['open'], record['close']) or
                record['low'] > record['high']):
            raise ValueError('观察前缀OHLC包络无效;不自动修正价格')
        rows.append(record)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['profile','extract'])
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--periods',nargs='+',default=['1d','30m'])
    parser.add_argument('--codes',nargs='+',default=CODES)
    parser.add_argument('--start')
    parser.add_argument('--observation')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('拒绝覆盖已归档样本/收据;请使用新文件名')
    dataset = args.dataset.resolve()
    manifest = load_manifest(dataset)
    if not set(args.periods)<=set(manifest['datasets']):
        parser.error('不支持的行情频率')
    report = {'schema_version':'chan-real-sample-v1','dataset':str(dataset),
        'manifest_sha256':digest(dataset/'manifest.json'),'dataset_version':manifest['dataset_version'],
        'generated_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'sampling_rule':{'periods':args.periods,'codes':args.codes,'window':'all history' if args.mode=='profile' else [args.start,args.observation]},
        'algorithm_labels_generated':False,'theoretical_acceptance':False}
    if args.mode=='profile':
        report.update(profile(dataset,manifest,args.periods,args.codes))
    else:
        if len(args.periods)!=1 or len(args.codes)!=1 or not args.start or not args.observation:
            parser.error('extract需一个period、一个code、start及已收盘observation日')
        import pandas as pd
        frames = [read_file(dataset,item,args.periods[0],args.codes)[0]
                  for item in manifest['datasets'][args.periods[0]]['files']]
        report['rows'] = packet_records(pd.concat(frames,ignore_index=True),args.periods[0],args.start,args.observation)
        report['factor_recipe'] = '每次观察独立截原始行情;价格*当行factor/当次观察最后可见factor;不在本包中提前复权'
        report['availability_scope'] = '仅收盘后研究输入;分钟区间/实际到达仍待供应方核验'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(args.output.resolve())
    return 0


if __name__=='__main__':
    raise SystemExit(main())
