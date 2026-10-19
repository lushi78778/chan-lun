# -*- coding: utf-8 -*-
"""真实样本准备: Parquet数据集审计/提取, 或显式声明来源的单标的CSV接收。

本工具不导入chan, 不运行识别器, 不生成理论真值。profile核对全部频率
文件摘要, 仅对显式频率和标的读取原始字段; extract固定观察日并保留
原始OHLC/复权因子, 不填空、不修价、不选择暖机或自动认定分钟到达时刻。
CSV接收不推断复权、周期或历史到达, 不把来源声明视为平台验证。
本地Python3.10+及pandas环境使用, 仅Parquet模式需要pyarrow, 不加入核心包依赖。
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
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
        if 'paused' in visible.columns:
            paused = float(row['paused'])
            if paused not in (0.0, 1.0):
                raise ValueError('观察前缀paused须为0或1;不以0量推定停牌')
            record['paused'] = int(paused)
        rows.append(record)
    return rows


def csv_packet(path, code, period, start, observation, source, source_version,
               timezone_name, adjustment, time_label, layout='joinquant',
               expected_sha256=None, volume_unit='unknown'):
    """接收单标的未复权CSV并冻结观察日前缀; 不调用识别器或生成理论标签。

    joinquant布局使用date/volume/factor, canonical布局使用
    ts_code/dt/vol/adj_factor; OHLC同名。单文件原始字节摘要在解析前固定,
    只有提供expected_sha256时才证明与该外部摘要一致。时间均为显式声明的
    北京时间无偏移格式; 不推导closed_dt/available_dt, 不转换价格/成交量,
    不补因子、不删停牌、不自动排序坏输入。未来数值先截后验, 原始字节保留。
    """
    import pandas as pd
    if not code or code.strip() != code or not source.strip() or not source_version.strip():
        raise ValueError('需单一代码、来源和来源版本/导出批次声明')
    if timezone_name != 'Asia/Shanghai' or adjustment != 'none':
        raise ValueError('CSV接收仅支持显式北京时间、未复权原始行情')
    if period not in ('1d', '1m', '5m', '15m', '30m', '60m'):
        raise ValueError('不支持的CSV频率')
    if time_label not in (('date',) if period == '1d' else ('start', 'end', 'unknown')):
        raise ValueError('日线须声明date, 分钟须声明start/end/unknown')
    if volume_unit not in ('shares', 'lots', 'units', 'unknown'):
        raise ValueError('未支持的成交量单位;不得自动换算')
    if layout not in ('joinquant', 'canonical'):
        raise ValueError('需显式选择CSV列布局')
    path = Path(path).resolve()
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and expected_sha256.lower() != actual:
        raise ValueError('CSV源文件摘要不一致')
    reader = csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True)
    header = next(reader, [])
    if not header or len(set(header)) != len(header):
        raise ValueError('CSV表头为空或重复')
    values = list(reader)
    if not values or any(len(row) != len(header) for row in values):
        raise ValueError('CSV为空或数据列数与表头不一致')
    frame = pd.DataFrame(values, columns=header)
    names = ({'date': 'dt', 'volume': 'vol', 'factor': 'adj_factor'}
             if layout == 'joinquant' else {})
    # 显式布局不容许同义列同时出现, 防止重命名后读到不同坐标。
    if any(old in header and new in header for old, new in names.items()):
        raise ValueError('CSV包含冲突的同义列')
    required = ({'date', 'open', 'high', 'low', 'close', 'volume', 'factor'}
                if layout == 'joinquant' else
                {'ts_code', 'dt', 'open', 'high', 'low', 'close', 'vol', 'adj_factor'})
    if not required <= set(header):
        raise ValueError('CSV缺少布局要求的行情/因子字段')
    frame = frame.rename(columns=names)
    if 'ts_code' in frame.columns:
        if set(frame['ts_code']) != {code}:
            raise ValueError('CSV代码与声明不一致或含多个标的;不静默筛选')
    else:
        frame['ts_code'] = code
    time_format = '%Y-%m-%d' if period == '1d' else '%Y-%m-%d %H:%M:%S'
    # 只接受一种明确时间格式, 不靠pandas猜测月日顺序、时区或bar标签。
    for value in frame['dt']:
        if datetime.strptime(value, time_format).strftime(time_format) != value:
            raise ValueError('CSV时间格式与频率不一致')
    first_day = datetime.strptime(start, '%Y-%m-%d')
    last_day = datetime.strptime(observation, '%Y-%m-%d')
    dates = pd.to_datetime(frame['dt'])
    visible = frame.loc[(dates >= first_day) & (dates < last_day + timedelta(days=1))]
    if not visible['dt'].is_monotonic_increasing:
        raise ValueError('观察前缀时间乱序;不自动排序或删除')
    key = 'trade_date' if period == '1d' else 'trade_time'
    rows = packet_records(frame.rename(columns={'dt': key}), period, start, observation)
    return {
        'schema_version': 'chan-real-sample-v1', 'dataset': str(path),
        'dataset_version': source_version, 'source': source,
        'source_sha256': actual,
        'source_digest_check': 'matched_expected' if expected_sha256 is not None else 'calculated_only',
        'source_rows': len(frame), 'source_layout': layout,
        'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'sampling_rule': {'periods': [period], 'codes': [code], 'window': [start, observation]},
        'timezone': timezone_name, 'adjustment': adjustment,
        'time_label': time_label, 'volume_unit': volume_unit, 'rows': rows,
        'algorithm_labels_generated': False, 'theoretical_acceptance': False,
        'factor_recipe': '保留原始价格及当行因子;每次观察截断后再独立选择复权锚',
        'availability_scope': '仅已收盘观察日研究输入;不生成closed_dt/available_dt',
        'limits': ['来源/版本/时间标签为输入声明,不是平台或历史供应时效验证',
                   '不证明历史数据未修订;不推断停牌、交易日完整性或真实走势级别']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['profile','extract','import-csv'])
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--periods',nargs='+',default=['1d','30m'])
    parser.add_argument('--codes',nargs='+',default=CODES)
    parser.add_argument('--start')
    parser.add_argument('--observation')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--csv-layout', choices=['joinquant', 'canonical'])
    parser.add_argument('--source')
    parser.add_argument('--source-version')
    parser.add_argument('--timezone')
    parser.add_argument('--adjustment', choices=['none'])
    parser.add_argument('--time-label', choices=['date', 'start', 'end', 'unknown'])
    parser.add_argument('--volume-unit', choices=['shares', 'lots', 'units', 'unknown'], default='unknown')
    parser.add_argument('--sha256', help='可选外部源文件摘要;未提供时只计算摘要')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('拒绝覆盖已归档样本/收据;请使用新文件名')
    dataset = args.dataset.resolve()
    if args.mode == 'import-csv':
        if (len(args.periods) != 1 or len(args.codes) != 1 or not args.start or
                not args.observation or not all([args.csv_layout, args.source,
                    args.source_version, args.timezone, args.adjustment, args.time_label])):
            parser.error('import-csv需一个period/code、start/observation、布局、来源/版本、时区、复权及时间标签声明')
        report = csv_packet(dataset, args.codes[0], args.periods[0], args.start,
                            args.observation, args.source, args.source_version,
                            args.timezone, args.adjustment, args.time_label,
                            args.csv_layout, args.sha256, args.volume_unit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(args.output.resolve())
        return 0
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
