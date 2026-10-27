# -*- coding: utf-8 -*-
"""完成XD构造F1的来源、独立编译与人工表防错契约。"""
import ast
import copy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'validation/tools/gen_real_xd_f1.py'
MANUAL = ROOT / 'validation/chan-real-xd-f1-manual-0.9.1.json'
FIXTURE = ROOT / 'tests/fixtures/real_xd_f1.json'


# 课65/67/71/77/78/81独立有限后缀；只保存事件/首次raw与来源摘要，不复制行情。
# Y1前7段及M2前27段为给定基底；M2的175..200为既有相邻条件证书。
# 独立收据SHA仅作来源锚点；运行时只读核心仓库资产，不依赖外层临时目录。
M3_FINITE_SUFFIX_AUDIT = {
    'Y1': dict(
        fixture='real_second_point.json', id='518880-5m-20260501-20260724',
        fixture_sha256='745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
        packet_sha256='fe56c1ed02f0e63500f0eec385580b37f0206d107e61842549d86a12d3d23773',
        receipt_sha256='7df9217fb0692b17ab1f5aae11b90e267ff6fd1c4ce5fc6893b2fb0877e9dbee',
        raw_rows=2793, fixed_bis=264, inherited_prefix=7, given_adjacent=0,
        events=((1,7,1,14),(8,26,1,29),(27,29,1,32),(30,32,1,35),
                (33,35,1,38),(36,48,1,51),(49,51,2,65),(52,58,1,61),
                (59,63,2,79),(64,76,2,86),(77,83,1,86),(84,86,2,94),
                (87,91,1,94),(92,94,1,97),(95,97,1,100),(98,106,1,109),
                (107,109,1,112),(110,112,2,122),(113,123,2,129),(124,126,2,136),
                (127,131,2,147),(132,144,1,147),(145,147,1,150),(148,158,2,164),
                (159,161,1,164),(162,164,1,169),(165,171,1,176),(172,176,2,182),
                (177,179,1,182),(180,182,1,185),(183,191,1,194),(192,200,1,203),
                (201,205,1,208),(206,208,1,211),(209,211,1,214),(212,220,2,228),
                (221,225,1,228),(226,240,1,243),(241,251,2,263)),
        local_counts=(163,299,323,352,381,557,661,630,840,946,946,1017,1017,
                      1067,1115,1218,1296,1377,1456,1520,1624,1624,1675,1773,
                      1773,1830,1881,1963,1963,1993,2113,2189,2235,2279,
                      2323,2440,2440,2580,2793),
        published_counts=(163,299,323,352,381,557,661,661,840,946,946,1017,1017,
                          1067,1115,1218,1296,1377,1456,1520,1624,1624,1675,1773,
                          1773,1830,1881,1963,1963,1993,2113,2189,2235,2279,
                          2323,2440,2440,2580,2793),
        tail=(252,263,260,8360)),
    'M2': dict(
        fixture='real_third_point_xd_margin0.json', id='512880-5m-20260201-20260724',
        fixture_sha256='5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        packet_sha256='0ce13561dd32e43d6b2c9f71e4d27fcf52e652c29be22aa84280b6f10f455d8e',
        receipt_sha256='b0a3cda8cb9719ce714a55a710001e7cd87cfa922e64c2889107555256d26ad5',
        raw_rows=5586, fixed_bis=322, inherited_prefix=27, given_adjacent=4,
        events=((0,10,1,13),(11,15,1,18),(16,34,1,37),(35,37,1,48),
                (38,48,1,51),(49,55,1,58),(56,64,2,72),(65,67,1,72),
                (68,74,1,77),(75,77,1,80),(78,86,1,89),(87,89,1,92),
                (90,92,1,97),(93,97,1,102),(98,102,1,110),(103,107,1,110),
                (108,110,1,113),(111,113,1,118),(114,122,1,125),(123,125,2,131),
                (126,128,2,136),(129,133,1,136),(134,138,1,141),(139,143,1,146),
                (144,160,1,163),(161,163,1,168),(164,174,2,180),(175,177,2,197),
                (178,180,1,189),(181,189,1,194),(190,200,1,203),(201,227,2,241),
                (228,238,1,255),(239,257,1,260),(258,262,1,265),(263,267,1,270),
                (268,290,1,293),(291,293,2,305),(294,302,1,305)),
        local_counts=(277,546,940,1139,1183,1349,1648,1648,1745,1775,2003,
                      2063,2133,2208,2321,2321,2365,2476,2660,2759,2872,2872,
                      2994,3077,3362,3480,3681,3956,3811,3928,4016,4563,4727,
                      4774,4848,4894,5235,5364,5364),
        published_counts=(277,546,940,1139,1183,1349,1648,1648,1745,1775,2003,
                          2063,2133,2208,2321,2321,2365,2476,2660,2759,2872,2872,
                          2994,3077,3362,3480,3681,3956,3956,3956,4016,4563,4727,
                          4774,4848,4894,5235,5364,5364),
        tail=(303,321,309,1131)),
}


# 额外实际消费者的有限声明；摘要是来源锚点，测试不读取外层收据或复制行情。
# E固定BI0近期顶737；all_current使用各原始前缀的实际活动末笔，不回填最终端点。
# G1只核实际消费上限1623内给定BI35后的共同后缀，不裁定seed0/1全球归属。
M3_ADDITIONAL_CONSUMERS_AUDIT = {
    'E': {
        'fixture': 'real_f1_originals.json', 'id': '512880-day-2018-08-24-2019-11-20',
        'fixture_sha256': '7c8408bf8beaf9f9c492460cb00353856c15dec56951a310de8522b1db9b5d29',
        'packet_sha256': '749db65b58f409c48b9f7e8b90e6b904dac596ed5400c45bc1026f853c861a80',
        'receipt_sha256': 'd55126633a153c0c0b9948c2c33b5184d6393f848eb94c7516116e0476d5dc8d',
        'limit': 300, 'all_bis': 35, 'fixed_bis': 34,
        'seed': (0, '2018-08-28', 737, (687,735)),
        'events': ((0,2,1,5),(3,5,1,8),(6,8,1,11),(9,11,2,23),
                   (12,20,1,23),(21,23,2,29),(24,26,1,29),(27,29,1,32)),
        'local_counts': {
            'all_current': (57,84,113,200,200,255,255,279),
            'fixed_without_active': (63,90,134,204,204,264,264,292)},
        'published_counts': {
            'all_current': (57,84,113,200,200,255,255,279),
            'fixed_without_active': (63,90,134,204,204,264,264,292)},
        # (首次raw, 当时证明端点日, 当时证明价)，活动证据与后来固定值分列。
        'special_proof_first': {
            'all_current': {11: (113,'2019-02-14',845),29: (255,'2019-09-09',1024)},
            'fixed_without_active': {11: (134,'2019-03-07',1185),29: (264,'2019-09-16',1039)}},
        # (尾起点, 末输入BI, 最后同向BI, 末同向价, 原首反向33撤销BI或None)。
        'tail': {'all_current': (30,34,34,893,34),
                 'fixed_without_active': (30,33,32,913,None)},
        'raw_crosses': {964: (251,'2019-09-04',969),1017: (252,'2019-09-05',1024)},
        'first_available_bi29': 255, 'active_tail_revoke_raw': 299,
        'global_theory_labels': False,
    },
    'G1': {
        'fixture': 'real_causal_formation.json', 'id': '588000-30m-20220801-20230501',
        'fixture_sha256': '6e72f6931e6cbe957ee40d184c51ab0bf9a666aefd6f9c521333343b7e3dbf5b',
        'packet_sha256': '35e7a15319477a7628edf2ac1a8869969a60534ed632db8535b2d3fb1978a009',
        'receipt_sha256': '675b97d6eb3b08263428c4c5b91fa31f41f7f7893a62a37d8a92475dff9adbe7',
        'source_rows': 1638, 'limit': 1623, 'actual_prefixes': (125,126,1623),
        'all_bis': 133, 'fixed_bis': 132, 'given_common_start': (35,910,(968,983)),
        'events': ((35,49,2,63),(50,60,1,63),(61,63,1,66),(64,76,1,79),
                   (77,89,1,94),(90,100,2,126),(101,123,1,126),(124,126,1,129)),
        'local_counts': (748,748,777,924,1137,1535,1540,1580),
        'published_counts': (748,748,777,924,1137,1535,1540,1580),
        # 每个事件分别记录(birth raw/价、首次成立raw/价、固定raw/价)。
        # 同proof126的两事件首次成立不同时，不能改成proof索引字典合并。
        'proof_stages': ((748,1056,748,1056,757,1066),
                         (748,1056,748,1056,757,1066),
                         (777,1044,777,1044,787,1044),
                         (924,1011,924,1011,935,1011),
                         (1125,1058,1137,1048,1146,1048),
                         (1535,1155,1535,1155,1553,1139),
                         (1535,1155,1540,1141,1553,1139),
                         (1573,1196,1580,1206,1583,1206)),
        'tail': (127,129,1206,130,1106,132,1108),
        'global_theory_labels': False, 'seed0_seed1_resolved': False,
    },
}


# M2仅给定起点下的局部证书；不替换继承基底或宣称自然发布时间提前。
M3_M2_GIVEN_PROOFS_AUDIT = {'receipt_sha256': '4420c9adb0523577aeb56aec8cd5d2d7b3b81a3fd3ecff8595df3398a459398b',
 'events': ((65, 67, 1, 70), (111, 113, 1, 116)),
 'old_proofs': (72, 118),
 'local_counts': (1618, 2437),
 'parent_events': ((56, 64, 2, 72), (108, 110, 1, 113)),
 'parent_counts': (1648, 2365),
 'conditional_publication': (1648, 2437),
 'original_first': ((68, 1060, 1054, 69), (114, 1079, 1075, 115)),
 'recent_seed87_ticks': (1010,
                         1043,
                         1039,
                         1056,
                         1036,
                         1038,
                         1029,
                         1091,
                         1066,
                         1080,
                         1058,
                         1084,
                         1074,
                         1080,
                         1074,
                         1081,
                         1067,
                         1086),
 'state_counts': (2063, 2122),
 'natural_events': ((87, 89, 1, 92), (94, 96, 1, 103)),
 'natural_start111_proven': False}


# 近期87种子有限公开完成项的目标合同；当前包算法尚未采用该修正。
# 两份独立原文/整数推导在原型比较之前冻结，不读取外层收据作测试输入。
M3_NATURAL_STATE_AUDIT = dict(
    public_contract_sha256='151ee6dcf197ed4704e2d42dcb9f0c40caab3e36b55ae9312dbb4c47e1671644',
    state_contract_sha256='8ae5afd41ebff09c90b2e0fea493b7ee190927f6276f7ac7d2cf8d9ca5075fe3',
    publication_contract_sha256='be44209957f564ecc593e8c86481023ede7d01b3be1c726594f6e34df4d07183',
    owner=3, first=6, predecessor=(0,2,1,5), reaction=(7,9,1,16),
    completed_at17=((0,2,1,5),(3,5,1,16)),
    forbidden=((6,10,1,15),(7,9,1,16)))


# S确认后，R后继需另给D的组成和完成证书；不把旧前史基底升级为自然证明。
# M2同批自审更正仅替代旧38..52的唯一性结论，旧原始收据/表均保留。
M3_NATURAL_SUCCESSOR_AUDIT = {
    'Y1': dict(
        fixture='real_second_point.json',id='518880-5m-20260501-20260724',
        source_sha256='745d73a5dc9370161e0cf619101542f823eaa257206f5f0864bd0f7a6a6880f6',
        receipt_sha256='e406c9ba128aef579b5f7c145080de08f955485aae17e43e377236d4f80e1c02',
        d_receipt_sha256='7a7b771da6a5754edf231c4e6101eae8a3bf0cc03595c03fb2c241e9d8413899',
        seed=1,owner=8,first=19,parent=(1,7,1,14),reaction=(20,26,1,29),
        successor=(27,29,1,32),extended=(19,29,1,32),old_boundary=(8,18,1,29),
        counts=(163,299,323),original_first=(9714,9906),net_end=9834),
    'M2': dict(
        fixture='real_third_point_xd_margin0.json',id='512880-5m-20260201-20260724',
        source_sha256='5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        receipt_sha256='686712846dec30a4dedef89fd2e0d2b0590b47aab580028e9f98879065287456',
        seed=16,owner=35,first=38,parent=(16,34,1,37),reaction=(39,41,2,51),
        successor=(42,48,1,51),extended=(38,48,1,51),old_boundary=(35,37,1,51),
        counts=(940,1183,1183),original_first=(1135,1105),net_end=1112),
}


# 新增三源只固定近期种子后的首处分歧，不把原型整窗输出当作真值。
# current首价来自当时活动笔，fixed计数来自后继笔固定；二者不得混填。
M3_EXPANDED_FIRST_AUDIT = {
    'M1_30m': dict(
        fixture='real_third_point_xd_margin0.json',id='588000-30m-20230501-20250228',
        source_sha256='5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        seed=38,owner=41,first=54,parent=(38,40,1,43),target=(41,67,1,72),
        reaction=(55,67,1,72),local_competitor=(54,58,1,61),cancel=67,
        current_counts=(637,930),fixed_counts=(642,943),raw_limit=943,
        current_proof_prices=(963,930),fixed_proof_prices=(963,934)),
    'S3_day': dict(
        fixture='real_strict_trend.json',id='518880-day-20210101-20260731',
        source_sha256='ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        seed=10,owner=13,first=16,parent=(10,12,1,15),target=(13,23,1,26),
        reaction=(17,23,1,26),local_competitor=(16,20,1,23),cancel=23,
        current_counts=(141,232),fixed_counts=(149,239),raw_limit=239,
        current_proof_prices=(3730,3550),fixed_proof_prices=(3730,3550)),
    'T_day': dict(
        fixture='real_third_point_margin0.json',id='588000-day-20210101-20231231',
        source_sha256='64c4f4b80eca2f31f262b86c26523ddc9c13d59195ca33a5c5aa5904460c0217',
        seed=22,owner=31,first=40,parent=(22,30,2,38),target=(31,39,1,59),
        reaction=(41,53,2,59),local_competitor=(31,53,2,59),cancel=None,
        current_counts=(370,586),fixed_counts=(377,589),raw_limit=589,
        current_proof_prices=(1088,1113),fixed_proof_prices=(1088,1113)),
}


# 仅裁定两处给定近期种子后的证明时刻；不替换完整来源或原静态标签。
# parent与target可同批可见，extended另有D完成证书；current保留当时端价。
M3_EXPANDED_PROOF_AUDIT = {
    'M1_274': dict(
        fixture='real_third_point_xd_margin0.json',id='588000-30m-20230501-20250228',
        source_sha256='5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        seed=266,owner=274,first=279,qualification=(266,270,1,273),
        parent=(271,273,2,285),old_boundary=(274,278,1,285),
        reaction=(280,282,1,285),successor=(283,285,1,288),extended=(279,285,1,288),
        events=((266,270,1,273),(271,273,2,285),(274,278,1,285),(279,285,1,288)),
        current_counts=(3665,3815,3815,3831),fixed_counts=(3692,3822,3822,3849),
        current_proof_prices=(997,1012,1012,1069),fixed_proof_prices=(981,1008,1008,1093),
        raw_window=(3598,3849),original_first=(1048,1001),reaction_margin=14),
    'S3_27': dict(
        fixture='real_strict_trend.json',id='518880-day-20210101-20260731',
        source_sha256='ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        seed=24,owner=27,first=36,qualification=None,
        parent=(24,26,1,29),old_boundary=(27,35,1,42),
        reaction=(37,39,1,42),successor=(40,42,1,45),extended=(36,42,1,45),
        events=((24,26,1,29),(27,35,1,42),(36,42,1,45)),
        current_counts=(246,329,348),fixed_counts=(256,334,355),
        current_proof_prices=(3643,3845,3942),fixed_proof_prices=(3658,3834,3942),
        raw_window=(227,355),original_first=(4077,3792),reaction_margin=108),
}


# 两个后续分界的有限证书；撤销与最终完成分开，未补源起点至近期种子的桥接。
M3_EXPANDED_BOUNDARY_AUDIT = {
    'M1_201': dict(
        fixture='real_third_point_xd_margin0.json',id='588000-30m-20230501-20250228',
        source_sha256='5f5f549a8775cec25dcedf2de920e0ff585d5293d2bf660df99ec4a3ec23cb01',
        receipt_sha256='15d097535011c97eff6bac0a31ca401cd5bb98612edd431aaa685b0973536ea0',
        seed=192,owner=201,first=204,parent=(192,200,1,203),target=(201,223,1,226),
        reaction=(205,223,1,226),local_competitor=(204,208,1,213),old_target=(201,203,1,213),
        cancel=213,current_cancel=2865,fixed_cancel=2874,current_counts=(2721,3068),
        fixed_counts=(2739,3081),current_proof_prices=(733,698),fixed_proof_prices=(733,718),
        raw_window=(2586,3081),raw_limit=3081,original_first=(733,784)),
    'S3_43': dict(
        fixture='real_strict_trend.json',id='518880-day-20210101-20260731',
        source_sha256='ac9101f3cb99de1a9e8612a6366aa87be4e4627664ccf1b4884ffe60fc39ffde',
        receipt_sha256='59873d576c07efdc1c5cdaa4ff7a77308c35e41a8cf959456a51cbd8ecf38f30',
        seed=36,owner=43,first=46,parent=(36,42,1,45),target=(43,81,1,84),
        reaction=(47,81,1,84),local_competitor=(46,48,1,50),old_target=(43,45,1,50),
        cancel=55,current_cancel=450,fixed_cancel=456,current_counts=(348,701),
        fixed_counts=(355,705),current_proof_prices=(3942,4488),fixed_proof_prices=(3942,4488),
        raw_window=(295,705),raw_limit=705,original_first=(3942,3615)),
}


def manual_xd_certificate_ready(parts, event):
    """只验给定分界的整数证书，不搜索XD；课67包含与课71原首笔选向分列。"""
    a, z, mode, proof = event
    if len(parts) <= proof:
        return False
    up = parts[a]['direction'] == 'up'
    turn = z + 1

    def standard(indices, initial_up):
        nodes = []
        for i in indices:
            p = (parts[i]['low_ticks'],parts[i]['high_ticks'])
            if nodes and ((nodes[-1][0]<=p[0] and p[1]<=nodes[-1][1]) or
                          (p[0]<=nodes[-1][0] and nodes[-1][1]<=p[1])):
                direction = initial_up if len(nodes)==1 else nodes[-1][1]>nodes[-2][1]
                choose = max if direction else min
                nodes[-1] = tuple(choose(nodes[-1][j],p[j]) for j in (0,1))
            else:
                nodes.append(p)
        return nodes

    def fractal(nodes, top):
        return len(nodes)==3 and all(nodes[1][j]>max(nodes[0][j],nodes[2][j]) if top else
                                    nodes[1][j]<min(nodes[0][j],nodes[2][j]) for j in (0,1))

    for start in (a,turn):
        group = parts[start:start+3]
        if len(group)!=3 or max(p['low_ticks'] for p in group)>min(p['high_ticks'] for p in group):
            return False
    left = standard(range(a+1,turn,2),up)[-1]
    first = parts[turn]
    if first['high_ticks']<=left[1] if up else first['low_ticks']>=left[0]:
        return False
    gap = first['low_ticks']-left[1] if up else left[0]-first['high_ticks']
    canceled = next((i for i in range(turn+1,proof+1,2) if
                    (parts[i]['end_ticks']>first['start_ticks'] if up else
                     parts[i]['end_ticks']<first['start_ticks'])),None)
    if mode == 1:
        selected = next((i for i in range(turn+2,proof+1,2) if
                        (parts[i]['end_ticks']<first['end_ticks'] if up else
                         parts[i]['end_ticks']>first['end_ticks'])),None)
        return gap<=0 and selected==proof and canceled is None
    right = standard(range(turn,proof+1,2),up)
    if gap<=0 or len(right)<2 or not fractal([left]+right[:2],up):
        return False
    second = standard(range(turn+1,proof+1,2),not up)
    # 同一可用BI快照的第二分型可与新极值同批；不声称原始price先后已证。
    return fractal(second[-3:],not up) and (canceled is None or canceled>=proof)


def manual_natural_reaction_state(parts, seen, observed, owner, first, predecessor, reaction):
    """课71/78给定证书的独立时序参考；不搜索分界或调用包识别器。

    parts只含当前可用固定笔，seen逐笔记录实际可见计数；observed与
    predecessor['published_count']使用同一观察单位，不能用BI序号冒充raw。
    predecessor绑定owner前段的身份；reaction必须从原首反向笔紧接起算。
    调用方须另证原首反向笔已构成课65第一种笔破坏、原转折无正缺口；
    不适用于第二种缺口或任意内部子段。reaction=None表示没有给定完成
    证书，不能从中推断自然反应不存在。四态先按最早可见事件裁定，
    再施加资格发布门控；未知前史、资格
    尚未可见与已可见分别保留。这里只验证给定自然起点的条件证书。
    published_count仅为该状态条件齐备的计数，不自行生成公开XD链。
    同一不可变笔输入及来源/祖先路径的自然资格由调用方另证，不能
    仅凭相同数值或索引把其他路径的条件证书移来使用。
    """
    if len(parts)!=len(seen) or not parts or any(a>b for a,b in zip(seen,seen[1:])):
        raise ValueError('可见固定笔与到达计数须逐项对应且有序')
    if seen[-1]>observed or owner<0 or first<owner+3 or first>=len(parts):
        raise ValueError('只允许当前观察前缀内的首反向笔')
    if parts[owner]['direction']==parts[first]['direction']:
        raise ValueError('首反向笔须与原段反向')
    qualification, identity, prior_count = 'unknown', None, None
    if predecessor is not None:
        identity = tuple(predecessor['event'])
        a,z,mode,proof = identity
        prior_count = predecessor['published_count']
        if a<0 or z<a+2 or mode not in (1,2) or proof<=z or z+1!=owner:
            raise ValueError('前驱证书身份与原段起点不衔接')
        if prior_count is not None and proof<len(parts) and prior_count<seen[proof]:
            raise ValueError('累计发布不能早于前驱局部证明')
        qualification = 'visible' if prior_count is not None and prior_count<=observed else 'waiting'
        if qualification=='visible' and not manual_xd_certificate_ready(parts,identity):
            raise ValueError('资格可见时前驱局部证书也须成立')
    if reaction is not None:
        a,z,mode,proof = reaction
        if a!=first+1 or z<a+2 or mode not in (1,2) or proof<=z:
            raise ValueError('自然反应证书须绑定紧邻起点')
    r = parts[first]
    up = r['direction']=='up'
    events = []
    triple = parts[first:first+3]
    overlap = (len(triple)==3 and
               max(p['low_ticks'] for p in triple)<=min(p['high_ticks'] for p in triple))
    for i in range(first+1,len(parts)):
        p = parts[i]
        broken = (p['end_ticks']<r['start_ticks'] if up else p['end_ticks']>r['start_ticks'])
        selected = (p['end_ticks']>r['end_ticks'] if up else p['end_ticks']<r['end_ticks'])
        if p['direction']!=r['direction'] and broken:
            events.append((seen[i],0,i,'first_start_broken'))
        elif p['direction']==r['direction'] and i>=first+2 and overlap and selected:
            events.append((seen[i],1,i,'first_end_selected'))
    if reaction is not None and proof<len(parts):
        if not manual_xd_certificate_ready(parts[:proof+1],reaction):
            raise ValueError('自然反应局部证书未成立')
        events.append((seen[proof],2,proof,'confirmed_without_start_break'))
    if events:
        # 同批破首起价否决“未破”条件；选终价与自然确认同批均支持反转。
        local_count,_,local_proof,state = min(events)
    else:
        local_count,local_proof,state = None,None,'pending'
    published = (max(prior_count,local_count) if qualification=='visible' and
                 local_count is not None else None)
    return dict(qualification=qualification,state=state,local_proof=local_proof,
                local_count=local_count,published_count=published,predecessor=identity)


def manual_natural_successor_certificate(parts, seen, observed, audit, predecessor):
    """给定R/S/D证书的条件装配；D最低形态不代替完成或自然归属证明。

    S可先支持R形成；D紧接S且与R同向，R拟终点须在D末。局部完成
    分别由原笔检验，再合并可见时刻；不额外要求候选序号晚于S证明。
    本函数不搜索自然起点，不把S/D内部部件直接输出为全局XD。
    """
    r,s,d = audit['extended'],audit['reaction'],audit['successor']
    if r[0]!=audit['first'] or s[0]!=r[0]+1 or d[0]!=s[1]+1 or d[1]!=r[1]:
        raise ValueError('R/S/D组成身份不衔接')
    if audit['old_boundary']!=(audit['owner'],audit['first']-1,1,s[3]):
        raise ValueError('原段分界与给定自然反应证明不一致')
    if d[1]-d[0]+1<3:
        raise ValueError('给定自然后继D至少三笔')
    if max(r[3],s[3],d[3])>=len(parts):
        return None
    first_d=parts[d[0]:d[0]+3]
    if (parts[d[0]]['direction']!=parts[r[0]]['direction'] or
            max(p['low_ticks'] for p in first_d)>min(p['high_ticks'] for p in first_d)):
        raise ValueError('D方向及首三笔重叠须另证')
    up=parts[r[0]]['direction']=='up'
    if parts[s[0]]['direction']==parts[r[0]]['direction']:
        raise ValueError('S须与R反向')
    for event in (r,s,d):
        a,z=parts[event[0]]['start_ticks'],parts[event[1]]['end_ticks']
        event_up=not up if event==s else up
        if not (z>a if event_up else z<a):
            raise ValueError('R/S/D净端方向须成立')
    for event in (r,s,d):
        if not manual_xd_certificate_ready(parts,event):
            raise ValueError('R/S/D局部完成证书未成立')
    state=manual_natural_reaction_state(parts,seen,observed,audit['owner'],audit['first'],predecessor,s)
    if state['qualification']!='visible' or state['state']!='confirmed_without_start_break':
        return None
    return dict(local_proof=r[3],local_count=seen[r[3]],successor_proof=d[3],
                published_count=max(state['published_count'],seen[r[3]],seen[d[3]]),
                reaction=s,successor=d,extended=r)


def embedded_table(filename, name):
    """只读已有常量，不执行另一测试模块或用算法回填预期。"""
    tree = ast.parse((ROOT / 'tests' / filename).read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def compiler(path=TOOL):
    """只加载独立开发工具，不把包算法引入真值编译。"""
    sys.path.insert(0, str(ROOT / 'validation/tools'))
    try:
        spec = importlib.util.spec_from_file_location('real_xd_f1_compiler', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def pending_gap_revisions():
    """复用包测试同一显式修订表；只读AST，不执行包测试或其识别器。"""
    table = embedded_table('test_real_xd_f1.py', 'M3_GAP_REVISION_AUDIT')
    return dict((key, dict(fixture=a['fixture'], id=a['id'], base=a['base'],
                events=[list(e) for e in a['events'][a['base']:]],
                local_counts=[u[9] for u in a['units'][a['base']:]],
                published_counts=[u[10] for u in a['units'][a['base']:]]))
                for key,a in table.items())


class TestRealXdF1Assets(unittest.TestCase):
    @staticmethod
    def _natural_parts(values):
        return [dict(direction='up' if z>a else 'down',start_ticks=a,end_ticks=z,
                     low_ticks=min(a,z),high_ticks=max(a,z))
                for a,z in zip(values,values[1:])]

    def _conditional_f1_source(self,key):
        audit=embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')[key]
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['source_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        rows=case['raw_rows'][:audit['raw_window'][1]]
        tool=compiler()
        _,_,bis=tool.foundation(rows,'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
        parts=tool.components(rows,bis[:-1],None)
        units=tool.xd_records(parts,audit['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual(tuple(tuple(u[n] for n in fields) for u in units),audit['units'])
        for left,right in zip(units,units[1:]):
            self.assertEqual((left['end_dt'],left['end_ticks']),(right['start_dt'],right['start_ticks']))
            self.assertNotEqual(left['direction'],right['direction'])
        for a,b in zip(audit['events'],audit['events'][1:]):
            self.assertEqual(a[1]+1,b[0])
        return audit,case,units

    def _conditional_f1_given_snapshot_boundaries(self,audit,case,units):
        """按既有独立XD证书时刻装配，另核F1首次准入；不搜索XD或F1分界。"""
        from datetime import datetime,timedelta
        tool=compiler()
        for contract in ('current','fixed'):
            counts=audit[contract+'_counts']
            for at,stamp in zip(counts,audit[contract+'_available_dt']):
                raw_dt=case['raw_rows'][at-1]['dt']
                dt=datetime.strptime(raw_dt,'%Y-%m-%d' if len(raw_dt)==10 else '%Y-%m-%d %H:%M:%S')
                available=dt+timedelta(hours=15,minutes=5) if '-day-' in audit['id'] else dt+timedelta(minutes=1)
                self.assertEqual(str(available),stamp)
            for count in sorted({n for at in counts[2:4] for n in (at-1,at)}):
                rows=case['raw_rows'][:count]
                _,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
                parts=tool.components(rows,bis if contract=='current' else bis[:-1],None)
                size=sum(at<=count for at in counts)
                visible=tool.xd_records(parts,audit['events'][:size])
                self.assertEqual(visible,[dict(u,evidence_dt=visible[i]['evidence_dt'],
                                 evidence_end_index=visible[i]['evidence_end_index']) for i,u in enumerate(units[:size])])
                if size<3:
                    continue
                spec=list(audit['f1'])
                spec[-1]=3 if size>=4 else None
                record=tool.move_record(visible,spec)
                self.assertEqual(record['complete'],count>=counts[3])
                self.assertEqual((record['seg_start'],record['seg_end']),(0,2))
                self.assertEqual((record['end_dt'],record['end_ticks']),
                                 (units[2]['end_dt'],units[2]['end_ticks']))
                self.assertEqual(record['proof_unit'],3 if size>=4 else None)

    def test_m1_given_four_xd_f1_admission_keeps_external_proof_and_real_end_separate(self):
        """给seed266：三段core为1019..1048，第四XD到达后才完成F1的0..2。"""
        audit,case,units=self._conditional_f1_source('M1_recent266')
        previous=M3_EXPANDED_PROOF_AUDIT['M1_274']
        self.assertEqual(audit['events'],tuple(previous[n] for n in ('qualification','parent','old_boundary','extended')))
        for contract in ('current','fixed'):
            self.assertEqual(audit[contract+'_counts'],previous[contract+'_counts'])
        self.assertEqual([(u['low_ticks'],u['high_ticks']) for u in units],
                         [(1019,1099),(981,1099),(981,1048),(1001,1048)])
        tool=compiler()
        record=tool.move_record(units,audit['f1'])
        self.assertEqual((record['kind'],record['direction'],record['low_ticks'],record['high_ticks']),
                         ('consolidation',None,981,1099))
        self.assertEqual(record['centers_ticks'],[[1019,1048]])
        self.assertNotEqual((record['end_dt'],record['end_ticks']),(units[3]['end_dt'],units[3]['end_ticks']))
        self.assertFalse(tool.move_record(units,audit['tail'])['complete'])
        self.assertEqual(audit['complete_f2'],0)
        self._conditional_f1_given_snapshot_boundaries(audit,case,units)

    def test_s3_joined_recent_certificates_form_one_f1_and_keep_later_tail_pending(self):
        """给seed10：10/24/36三包同源衔接，重复36段只保留一次；尾部仍未完。"""
        audit,case,units=self._conditional_f1_source('S3_recent10')
        first=M3_EXPANDED_FIRST_AUDIT['S3_day']
        middle=M3_EXPANDED_PROOF_AUDIT['S3_27']
        last=M3_EXPANDED_BOUNDARY_AUDIT['S3_43']
        self.assertEqual(audit['events'][:2],(first['parent'],first['target']))
        self.assertEqual(audit['events'][2:5],middle['events'])
        self.assertEqual(audit['events'][4:],(last['parent'],last['target']))
        for contract in ('current','fixed'):
            counts=audit[contract+'_counts']
            self.assertEqual(counts[:2],first[contract+'_counts'])
            self.assertEqual(counts[2:5],middle[contract+'_counts'])
            self.assertEqual(counts[4:],last[contract+'_counts'])
        self.assertEqual(len(units),6)
        self.assertEqual(sum(e==(36,42,1,45) for e in audit['events']),1)
        tool=compiler()
        record=tool.move_record(units,audit['f1'])
        tail=tool.move_record(units,audit['tail'])
        self.assertEqual((record['seg_end'],record['end_ticks'],record['proof_unit']),(2,3550,3))
        self.assertEqual(record['centers_ticks'],[[3579,3745]])
        self.assertEqual((record['low_ticks'],record['high_ticks']),(3541,3865))
        self.assertEqual((tail['seg_start'],tail['seg_end'],tail['complete']),(3,5,False))
        self.assertEqual(tail['centers_ticks'],[[3792,4077]])
        self.assertEqual(audit['complete_f2'],0)
        self._conditional_f1_given_snapshot_boundaries(audit,case,units)

    def test_m2_six_given_xds_keep_child_local_proof_separate_from_parent_publication(self):
        """给seed16：first-end70可先有局部证书，父gap72未完成前不发布65段。"""
        audit,case,units=self._conditional_f1_source('M2_recent16')
        previous=M3_NATURAL_SUCCESSOR_AUDIT['M2']
        self.assertEqual(audit['events'][:3],tuple(previous[n] for n in ('parent','old_boundary','extended')))
        self.assertEqual(audit['fixed_counts'][:3],previous['counts'])
        tool=compiler()
        record=tool.move_record(units,audit['f1'])
        self.assertEqual(record['centers_ticks'],[[1113,1135]])
        self.assertEqual((record['low_ticks'],record['high_ticks'],record['end_ticks']),(1105,1200,1112))
        self.assertLess(units[3]['low_ticks'],record['low_ticks'])
        self.assertFalse(tool.move_record(units,audit['tail'])['complete'])
        self.assertGreater(max(u['low_ticks'] for u in units[3:]),min(u['high_ticks'] for u in units[3:]))
        self._conditional_f1_given_snapshot_boundaries(audit,case,units)
        for contract in ('current','fixed'):
            local=audit[contract+'_local_counts'][-1]
            published=audit[contract+'_counts'][-1]
            self.assertLess(local,published)
            self.assertEqual(published,audit[contract+'_counts'][-2])
            for count in (local,published-1,published):
                parts=self._boundary_current_prefix(case,count)
                if contract=='fixed':
                    parts=parts[:-1]
                self.assertTrue(manual_xd_certificate_ready(parts,audit['events'][-1]))
                parent=manual_xd_certificate_ready(parts,audit['events'][-2])
                self.assertEqual(parent,count>=published)
                size=6 if parent else 4
                self.assertEqual(len(tool.xd_records(parts,audit['events'][:size])),size)
                if count==local:
                    self.assertEqual(parts[70]['end_ticks'],audit[contract+'_local_proof_prices'][-1])
                    if contract=='current':
                        self.assertEqual(parts[70]['end_dt'],'2026-03-26 10:30:00')
                if count==published:
                    self.assertEqual((parts[70]['end_ticks'],parts[70]['end_dt']),
                                     (1033,'2026-03-26 14:25:00'))
            self.assertEqual(audit[contract+'_counts'][-1],audit[contract+'_counts'][-2])
        self.assertEqual((audit['current_local_proof_prices'][-1],audit['fixed_local_proof_prices'][-1]),(1048,1033))

    def test_y1_corrected_head_joins_next_segment_and_replaces_no_historical_core(self):
        """给seed1：30..32由35严格选向；修正核心9714..9906，不沿用旧9780..9834。"""
        audit,case,units=self._conditional_f1_source('Y1_recent1')
        previous=M3_NATURAL_SUCCESSOR_AUDIT['Y1']
        self.assertEqual(audit['events'][:3],tuple(previous[n] for n in ('parent','old_boundary','extended')))
        self.assertEqual(audit['fixed_counts'][:3],previous['counts'])
        alias=next(c for c in json.loads((ROOT/'tests/fixtures/real_first_point.json').read_text())['cases']
                   if c['id']==audit['id'])
        self.assertEqual(case['raw_rows'][:352],alias['raw_rows'][:352])
        self.assertEqual(case['foundation']['bis'][:36],alias['foundation']['bis'][:36])
        tool=compiler()
        rows=case['raw_rows'][:352]
        _,_,bis=tool.foundation(rows,'106')
        parts=tool.components(rows,bis[:-1],None)
        self.assertTrue(manual_xd_certificate_ready(parts,(30,32,1,35)))
        self.assertEqual((parts[33]['start_ticks'],parts[33]['end_ticks'],parts[35]['end_ticks']),
                         (9761,9793,9797))
        self.assertGreater(parts[34]['end_ticks'],parts[33]['start_ticks'])
        record=tool.move_record(units,audit['f1'])
        self.assertEqual(record['centers_ticks'],[[9714,9906]])
        self.assertEqual((record['start_ticks'],record['end_ticks'],record['low_ticks'],record['high_ticks']),
                         (9702,9834,9702,9933))
        old=embedded_table('test_real_xd_f1.py','M3_XD_RECURSION_AUDIT')['Y1']['f1'][0]
        self.assertEqual(old[5],((9780,9834),))
        self.assertNotEqual(audit['f1'][5],old[5])
        self.assertEqual(audit['f1'][-1],old[-1])
        self.assertFalse(tool.move_record(units,audit['tail'])['complete'])
        self._conditional_f1_given_snapshot_boundaries(audit,case,units)

    def _boundary_pair_source(self,key):
        audit=M3_EXPANDED_BOUNDARY_AUDIT[key]
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['source_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        rows=case['raw_rows'][:audit['raw_limit']]
        tool=compiler()
        _,_,bis=tool.foundation(rows,'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
        parts=tool.components(rows,bis[:-1],None)
        seen=case['foundation']['bis_confirmed_raw_count'][:len(parts)]
        self.assertEqual(tuple(seen[audit[n][3]] for n in ('parent','target')),audit['fixed_counts'])
        self.assertEqual(seen[audit['cancel']],audit['fixed_cancel'])
        self.assertEqual((parts[audit['first']]['start_ticks'],parts[audit['first']]['end_ticks']),
                         audit['original_first'])
        return audit,case,parts,seen

    def _boundary_current_prefix(self,case,count):
        rows=case['raw_rows'][:count]
        tool=compiler()
        _,_,bis=tool.foundation(rows,'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
        return tool.components(rows,bis,None)

    def test_m1_later_boundary_rejects_same_batch_local_completion_and_original_start_break(self):
        """给seed192：local proof213与撤销同批；201须等新首224到226选向。"""
        audit,case,original,seen=self._boundary_pair_source('M1_201')
        self._expanded_first_arrival_boundaries(audit,case)
        self.assertEqual(original[204]['end_ticks']-original[208]['end_ticks'],30)
        self.assertEqual(original[212]['low_ticks']-original[214]['high_ticks'],8)
        self.assertEqual(original[214]['low_ticks']-original[216]['high_ticks'],7)
        parent=dict(event=audit['parent'],published_count=2739)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=20000-p['start_ticks'],
                end_ticks=20000-p['end_ticks'],low_ticks=20000-p['high_ticks'],high_ticks=20000-p['low_ticks'])
                for p in original]
            for name in ('parent','target','reaction','local_competitor'):
                self.assertTrue(manual_xd_certificate_ready(parts,audit[name]))
            self.assertFalse(manual_xd_certificate_ready(parts,audit['old_target']))
            pending=manual_natural_reaction_state(parts[:213],seen[:213],2865,201,204,parent,audit['reaction'])
            self.assertEqual((pending['state'],pending['published_count']),('pending',None))
            broken=manual_natural_reaction_state(parts[:214],seen[:214],2874,201,204,parent,audit['reaction'])
            self.assertEqual((broken['state'],broken['local_proof'],broken['published_count']),
                             ('first_start_broken',213,2874))
            late=manual_natural_reaction_state(parts,seen,3081,201,204,parent,audit['reaction'])
            self.assertEqual((late['state'],late['published_count']),('first_start_broken',2874))
            for end in (213,215):
                self.assertFalse(manual_xd_certificate_ready(parts,(201,end,2,226)))
        before_local=self._boundary_current_prefix(case,2864)
        self.assertEqual(len(before_local),213)
        self.assertFalse(manual_xd_certificate_ready(before_local,audit['local_competitor']))
        current=self._boundary_current_prefix(case,2865)
        self.assertTrue(manual_xd_certificate_ready(current,audit['local_competitor']))
        self.assertLess(current[213]['end_ticks'],current[204]['start_ticks'])
        self.assertEqual((audit['current_cancel'],audit['fixed_cancel']),(2865,2874))
        appeared=self._boundary_current_prefix(case,3063)
        self.assertEqual(appeared[226]['end_ticks'],683)
        self.assertLess(appeared[226]['end_ticks'],appeared[224]['end_ticks'])
        self.assertFalse(manual_xd_certificate_ready(appeared,audit['target']))
        self.assertNotEqual(audit['current_proof_prices'][1],audit['fixed_proof_prices'][1])

    def test_s3_later_boundary_rejects_unprotruded_local_and_late_reaction_revival(self):
        """给seed36：local49包含于47；46先在55撤销，后续S不能复活旧45分界。"""
        audit,case,original,seen=self._boundary_pair_source('S3_43')
        self._expanded_first_arrival_boundaries(audit,case)
        self.assertLess(original[50]['end_ticks'],original[43]['start_ticks'])
        self.assertGreater(original[50]['end_ticks'],original[46]['end_ticks'])
        self.assertGreater(original[49]['low_ticks'],original[47]['low_ticks'])
        self.assertLess(original[49]['high_ticks'],original[47]['high_ticks'])
        # 候选76的77撤销先于78选向；不能只看后来的更低净端。
        self.assertGreater(original[77]['end_ticks'],original[76]['start_ticks'])
        self.assertLess(original[78]['end_ticks'],original[76]['end_ticks'])
        parent=dict(event=audit['parent'],published_count=355)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=20000-p['start_ticks'],
                end_ticks=20000-p['end_ticks'],low_ticks=20000-p['high_ticks'],high_ticks=20000-p['low_ticks'])
                for p in original]
            for name in ('parent','target','reaction'):
                self.assertTrue(manual_xd_certificate_ready(parts,audit[name]))
            for name in ('old_target','local_competitor'):
                self.assertFalse(manual_xd_certificate_ready(parts,audit[name]))
            pending=manual_natural_reaction_state(parts[:51],seen[:51],412,43,46,parent,audit['reaction'])
            self.assertEqual((pending['state'],pending['published_count']),('pending',None))
            broken=manual_natural_reaction_state(parts[:56],seen[:56],456,43,46,parent,audit['reaction'])
            self.assertEqual((broken['state'],broken['local_proof'],broken['published_count']),
                             ('first_start_broken',55,456))
            late=manual_natural_reaction_state(parts,seen,705,43,46,parent,audit['reaction'])
            self.assertEqual((late['state'],late['published_count']),('first_start_broken',456))
        appeared=self._boundary_current_prefix(case,346)
        self.assertEqual(appeared[45]['end_ticks'],3895)
        self.assertFalse(manual_xd_certificate_ready(appeared,audit['parent']))
        before_break=self._boundary_current_prefix(case,440)
        self.assertEqual(before_break[55]['end_ticks'],3829)
        self.assertLess(before_break[55]['end_ticks'],before_break[46]['start_ticks'])
        last_unbroken=self._boundary_current_prefix(case,449)
        self.assertEqual(last_unbroken[55]['end_ticks'],3831)
        self.assertLess(last_unbroken[55]['end_ticks'],last_unbroken[46]['start_ticks'])
        broken=self._boundary_current_prefix(case,450)
        self.assertGreater(broken[55]['end_ticks'],broken[46]['start_ticks'])
        self.assertEqual((audit['current_cancel'],audit['fixed_cancel']),(450,456))

    def _proof_pair_source(self,key):
        audit=M3_EXPANDED_PROOF_AUDIT[key]
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['source_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        rows=case['raw_rows'][:audit['raw_window'][1]]
        tool=compiler()
        _,_,bis=tool.foundation(rows,'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
        parts=tool.components(rows,bis[:-1],None)
        seen=case['foundation']['bis_confirmed_raw_count'][:len(parts)]
        self.assertEqual(tuple(seen[e[3]] for e in audit['events']),audit['fixed_counts'])
        self.assertEqual((parts[audit['first']]['start_ticks'],parts[audit['first']]['end_ticks']),
                         audit['original_first'])
        return audit,case,parts,seen

    def _proof_pair_arrival_boundaries(self,audit,case):
        """独立给定证书的raw临界点，不调用识别器或外层临时脚本。"""
        tool=compiler()
        for contract in ('current','fixed'):
            counts=audit[contract+'_counts']
            for count in sorted({n for at in counts for n in (at-1,at)}):
                rows=case['raw_rows'][:count]
                _,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
                parts=tool.components(rows,bis if contract=='current' else bis[:-1],None)
                qualified=(audit['qualification'] is None or
                           manual_xd_certificate_ready(parts,audit['qualification']))
                parent=qualified and manual_xd_certificate_ready(parts,audit['parent'])
                target=parent and manual_xd_certificate_ready(parts,audit['reaction'])
                if target:
                    first=parts[audit['first']]
                    self.assertTrue(all(parts[i]['end_ticks']<=first['start_ticks']
                                        for i in range(audit['first']+1,audit['old_boundary'][3]+1,2)))
                    self.assertTrue(all(parts[i]['end_ticks']>=first['end_ticks']
                                        for i in range(audit['first']+2,audit['old_boundary'][3]+1,2)))
                extended=(target and manual_xd_certificate_ready(parts,audit['extended']) and
                          manual_xd_certificate_ready(parts,audit['successor']))
                ready=[parent,target,extended]
                if audit['qualification'] is not None:
                    ready.insert(0,qualified)
                for i,(event,good) in enumerate(zip(audit['events'],ready)):
                    self.assertEqual(good,count>=counts[i],(audit['id'],contract,count,event))
                    if good and count==counts[i]:
                        self.assertEqual(parts[event[3]]['end_ticks'],audit[contract+'_proof_prices'][i])

    def test_m1_later_proof_uses_same_batch_gap_parent_and_natural_reaction(self):
        """给seed266：父gap47与S280同285确认，274不必等后继R的proof288。"""
        audit,case,original,seen=self._proof_pair_source('M1_274')
        self._proof_pair_arrival_boundaries(audit,case)
        self.assertEqual(original[272]['low_ticks']-original[274]['high_ticks'],47)
        self.assertEqual(original[279]['start_ticks']-max(p['high_ticks'] for p in original[280:283]),14)
        parent=dict(event=audit['parent'],published_count=3822)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=20000-p['start_ticks'],
                end_ticks=20000-p['end_ticks'],low_ticks=20000-p['high_ticks'],high_ticks=20000-p['low_ticks'])
                for p in original]
            for name in ('qualification','parent','reaction','successor','extended'):
                self.assertTrue(manual_xd_certificate_ready(parts,audit[name]))
            self.assertFalse(manual_xd_certificate_ready(parts,audit['old_boundary']))
            waiting=manual_natural_reaction_state(parts[:283],seen[:283],3788,274,279,parent,audit['reaction'])
            self.assertEqual((waiting['qualification'],waiting['state'],waiting['published_count']),
                             ('waiting','pending',None))
            confirmed=manual_natural_reaction_state(parts[:286],seen[:286],3822,274,279,parent,audit['reaction'])
            self.assertEqual((confirmed['qualification'],confirmed['state'],confirmed['published_count']),
                             ('visible','confirmed_without_start_break',3822))
            result=manual_natural_successor_certificate(parts,seen,3849,audit,parent)
            self.assertEqual((result['reaction'],result['successor'],result['extended']),
                             (audit['reaction'],audit['successor'],audit['extended']))
            self.assertEqual(result['published_count'],3849)
            # 288后来破原首起价，不回撤285已经成立的自然反应。
            later=manual_natural_reaction_state(parts,seen,3849,274,279,parent,audit['reaction'])
            self.assertEqual((later['state'],later['published_count']),('confirmed_without_start_break',3822))
        self.assertEqual(audit['old_boundary'][3],285)
        self.assertEqual(audit['extended'][3],288)

    def test_s3_later_proof_uses_completed_reaction_before_reverse_successor(self):
        """给seed24：S37..39在42完成且低于首起108格；45只证明后继R/D。"""
        audit,case,original,seen=self._proof_pair_source('S3_27')
        self._proof_pair_arrival_boundaries(audit,case)
        self.assertEqual(original[36]['start_ticks']-max(p['high_ticks'] for p in original[37:40]),108)
        parent=dict(event=audit['parent'],published_count=256)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=20000-p['start_ticks'],
                end_ticks=20000-p['end_ticks'],low_ticks=20000-p['high_ticks'],high_ticks=20000-p['low_ticks'])
                for p in original]
            for name in ('parent','reaction','successor','extended'):
                self.assertTrue(manual_xd_certificate_ready(parts,audit[name]))
            self.assertFalse(manual_xd_certificate_ready(parts,audit['old_boundary']))
            for first,cancel in ((30,31),(32,33)):
                canceled=manual_natural_reaction_state(parts[:cancel+1],seen[:cancel+1],seen[cancel],
                                                       27,first,parent,None)
                self.assertEqual((canceled['state'],canceled['local_proof']),('first_start_broken',cancel))
            # 较早gap34先在35失效，42的晚分型不能复活该假设分界。
            self.assertFalse(manual_xd_certificate_ready(parts,(27,33,2,42)))
            pending=manual_natural_reaction_state(parts[:42],seen[:42],329,27,36,parent,audit['reaction'])
            self.assertEqual((pending['state'],pending['published_count']),('pending',None))
            confirmed=manual_natural_reaction_state(parts[:43],seen[:43],334,27,36,parent,audit['reaction'])
            self.assertEqual((confirmed['state'],confirmed['published_count']),('confirmed_without_start_break',334))
            self.assertIsNone(manual_natural_successor_certificate(parts[:43],seen[:43],334,audit,parent))
            result=manual_natural_successor_certificate(parts,seen,355,audit,parent)
            self.assertEqual((result['local_proof'],result['successor_proof'],result['published_count']),(45,45,355))
        self.assertEqual(audit['old_boundary'][3],42)
        self.assertEqual(audit['extended'][3],45)

    def _expanded_first_source(self,key):
        audit=M3_EXPANDED_FIRST_AUDIT[key]
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['source_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        rows=case['raw_rows'][:audit['raw_limit']]
        tool=compiler()
        _,_,bis=tool.foundation(rows,'106')
        parts=tool.components(rows,bis[:-1],None)
        seen=case['foundation']['bis_confirmed_raw_count'][:len(parts)]
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(parts)])
        self.assertEqual(tuple(seen[audit[name][3]] for name in ('parent','target')),audit['fixed_counts'])
        return audit,case,parts,seen

    def _expanded_first_arrival_boundaries(self,audit,case):
        """仅给定证书的必要raw边界；未运行识别器或回填活动端点。"""
        tool=compiler()
        for contract in ('current','fixed'):
            counts=audit[contract+'_counts']
            for count in sorted({n for at in counts for n in (at-1,at)}):
                rows=case['raw_rows'][:count]
                _,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
                parts=tool.components(rows,bis if contract=='current' else bis[:-1],None)
                parent=manual_xd_certificate_ready(parts,audit['parent'])
                if audit['cancel'] is not None:
                    target=parent and manual_xd_certificate_ready(parts,audit['target'])
                    if target:
                        first=parts[audit['first']]
                        up=first['direction']=='up'
                        canceled=next((i for i in range(audit['first']+1,audit['target'][3]+1,2)
                            if (parts[i]['end_ticks']<first['start_ticks'] if up else
                                parts[i]['end_ticks']>first['start_ticks'])),None)
                        self.assertEqual(canceled,audit['cancel'])
                else:
                    target=parent and manual_xd_certificate_ready(parts,audit['reaction'])
                    if target:
                        first=parts[audit['first']]
                        group=parts[audit['reaction'][0]:audit['reaction'][1]+1]
                        self.assertLess(max(p['high_ticks'] for p in group),first['start_ticks'])
                        self.assertTrue(all(parts[i]['end_ticks']>=first['end_ticks']
                                           for i in range(audit['first']+2,audit['target'][3]+1,2)))
                        self.assertTrue(all(parts[i]['end_ticks']<=first['start_ticks']
                                           for i in range(audit['first']+1,audit['target'][3]+1,2)))
                for j,(name,ready) in enumerate((('parent',parent),('target',target))):
                    self.assertEqual(ready,count>=counts[j],(audit['id'],contract,count,name))
                    if ready and count==counts[j]:
                        self.assertEqual(parts[audit[name][3]]['end_ticks'],audit[contract+'_proof_prices'][j])

    def test_expanded_m1_first_reverse_waits_instead_of_using_one_tick_lower_local_peak(self):
        """给seed38：R54终994未被993选向，local proof61不越过自然S55待定。"""
        audit,case,original,seen=self._expanded_first_source('M1_30m')
        self._expanded_first_arrival_boundaries(audit,case)
        self.assertEqual((original[54]['start_ticks'],original[54]['end_ticks'],original[58]['end_ticks']),
                         (906,994,993))
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=5000-p['start_ticks'],
                end_ticks=5000-p['end_ticks'],low_ticks=5000-p['high_ticks'],high_ticks=5000-p['low_ticks'])
                for p in original]
            parent=dict(event=audit['parent'],published_count=642)
            for event in (audit['parent'],audit['target'],audit['reaction'],audit['local_competitor']):
                self.assertTrue(manual_xd_certificate_ready(parts,event))
            pending=manual_natural_reaction_state(parts[:62],seen[:62],815,41,54,parent,audit['reaction'])
            self.assertEqual((pending['state'],pending['published_count']),('pending',None))
            broken=manual_natural_reaction_state(parts,seen,943,41,54,parent,audit['reaction'])
            self.assertEqual((broken['state'],broken['local_proof'],broken['published_count']),
                             ('first_start_broken',67,902))
            self.assertLess(broken['published_count'],seen[audit['target'][3]])
        self.assertEqual(audit['current_proof_prices'][1],930)
        self.assertEqual(audit['fixed_proof_prices'][1],934)

    def test_expanded_s3_crossing_old_start_does_not_replace_original_first_end_selection(self):
        """给seed10：3542越旧起3579但未破首终3541；须等撤销后24的26证明。"""
        audit,case,original,seen=self._expanded_first_source('S3_day')
        self._expanded_first_arrival_boundaries(audit,case)
        self.assertLess(original[20]['end_ticks'],original[13]['start_ticks'])
        self.assertEqual(original[20]['end_ticks']-original[16]['end_ticks'],1)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=10000-p['start_ticks'],
                end_ticks=10000-p['end_ticks'],low_ticks=10000-p['high_ticks'],high_ticks=10000-p['low_ticks'])
                for p in original]
            parent=dict(event=audit['parent'],published_count=149)
            self.assertTrue(manual_xd_certificate_ready(parts,audit['local_competitor']))
            self.assertFalse(manual_xd_certificate_ready(parts,(13,15,1,20)))
            pending=manual_natural_reaction_state(parts[:21],seen[:21],189,13,16,parent,audit['reaction'])
            self.assertEqual(pending['state'],'pending')
            broken=manual_natural_reaction_state(parts,seen,239,13,16,parent,audit['reaction'])
            self.assertEqual((broken['state'],broken['local_proof'],broken['published_count']),
                             ('first_start_broken',23,218))
            self.assertTrue(manual_xd_certificate_ready(parts,audit['target']))

    def test_expanded_daily_same_proof_gap_certificate_keeps_earlier_original_turn_identity(self):
        """给seed22：父gap22与自然S gap46；同proof59不交换R40与较低gap54。"""
        audit,case,original,seen=self._expanded_first_source('T_day')
        self._expanded_first_arrival_boundaries(audit,case)
        parent=dict(event=audit['parent'],published_count=377)
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',start_ticks=5000-p['start_ticks'],
                end_ticks=5000-p['end_ticks'],low_ticks=5000-p['high_ticks'],high_ticks=5000-p['low_ticks'])
                for p in original]
            for event in (audit['parent'],audit['reaction'],audit['local_competitor']):
                self.assertTrue(manual_xd_certificate_ready(parts,event))
            waiting=manual_natural_reaction_state(parts[:38],seen[:38],370,31,34,parent,None)
            self.assertEqual(waiting['qualification'],'waiting')
            visible=manual_natural_reaction_state(parts[:39],seen[:39],377,31,34,parent,None)
            self.assertEqual((visible['qualification'],visible['state']),('visible','pending'))
            canceled=manual_natural_reaction_state(parts[:40],seen[:40],395,31,34,parent,None)
            self.assertEqual((canceled['state'],canceled['local_proof']),('first_start_broken',39))
            actual=manual_natural_reaction_state(parts,seen,589,31,40,parent,audit['reaction'])
            self.assertEqual((actual['state'],actual['local_proof'],actual['published_count']),
                             ('confirmed_without_start_break',59,589))
        self.assertEqual(original[40]['start_ticks']-max(p['high_ticks'] for p in original[41:54]),14)
        self.assertEqual(original[29]['low_ticks']-original[31]['high_ticks'],22)
        self.assertEqual(original[54]['low_ticks']-max(original[i]['high_ticks'] for i in (50,52)),46)
        self.assertEqual(audit['target'],(31,39,1,59))
        self.assertEqual(audit['local_competitor'],(31,53,2,59))

    def _natural_successor_source(self,key):
        audit=M3_NATURAL_SUCCESSOR_AUDIT[key]
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['source_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        limit=max(audit[name][3] for name in ('parent','reaction','successor','extended'))+1
        seen=case['foundation']['bis_confirmed_raw_count'][:limit]
        parts=[dict(direction=b[0],start_ticks=b[3],end_ticks=b[4],
                    low_ticks=min(b[3],b[4]),high_ticks=max(b[3],b[4]))
               for b in case['foundation']['bis'][:limit]]
        self.assertEqual(tuple(seen[audit[name][3]] for name in ('parent','reaction','extended')),
                         audit['counts'])
        return audit,parts,seen

    def test_y1_confirmed_reaction_allows_certified_successor_after_its_composition(self):
        """给seed1：自然S20确认后允许D27，原首高9906不永久封死净端9834。"""
        audit,original,seen=self._natural_successor_source('Y1')
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',
                start_ticks=20000-p['start_ticks'],end_ticks=20000-p['end_ticks'],
                low_ticks=20000-p['high_ticks'],high_ticks=20000-p['low_ticks']) for p in original]
            parent=dict(event=audit['parent'],published_count=seen[audit['parent'][3]])
            for event in (audit['parent'],audit['reaction'],audit['successor'],audit['extended']):
                self.assertTrue(manual_xd_certificate_ready(parts,event))
            for count in (29,30,32,33):
                result=manual_natural_successor_certificate(parts[:count],seen[:count],seen[count-1],audit,parent)
                if count<33:
                    self.assertIsNone(result)
                else:
                    self.assertEqual((result['local_proof'],result['successor_proof'],result['published_count']),
                                     (32,32,323))
            self.assertGreater(audit['successor'][0],audit['reaction'][1])
        self.assertEqual((original[19]['start_ticks'],original[19]['end_ticks']),audit['original_first'])
        self.assertEqual(original[29]['end_ticks'],audit['net_end'])
        self.assertLess(audit['net_end'],audit['original_first'][1])

    def test_m2_same_batch_successor_uses_composition_instead_of_proof_index_order(self):
        """给seed16：S39与D42局部证书同51成立，49早于proof51不构成否决。"""
        audit,original,seen=self._natural_successor_source('M2')
        for mirrored in (False,True):
            parts=original if not mirrored else [dict(p,
                direction='down' if p['direction']=='up' else 'up',
                start_ticks=3000-p['start_ticks'],end_ticks=3000-p['end_ticks'],
                low_ticks=3000-p['high_ticks'],high_ticks=3000-p['low_ticks']) for p in original]
            parent=dict(event=audit['parent'],published_count=940)
            for event in (audit['parent'],audit['reaction'],audit['successor'],audit['extended']):
                self.assertTrue(manual_xd_certificate_ready(parts,event))
            self.assertIsNone(manual_natural_successor_certificate(parts[:-1],seen[:-1],1182,audit,parent))
            result=manual_natural_successor_certificate(parts,seen,1183,audit,parent)
            self.assertEqual((result['local_proof'],result['successor_proof'],result['published_count']),
                             (51,51,1183))
            state=manual_natural_reaction_state(parts,seen,1183,35,38,parent,audit['reaction'])
            self.assertEqual((state['state'],state['local_proof'],state['published_count']),
                             ('confirmed_without_start_break',51,1183))
        self.assertLess(audit['extended'][1]+1,audit['reaction'][3])
        self.assertEqual((original[38]['start_ticks'],original[38]['end_ticks']),audit['original_first'])
        self.assertGreater(audit['net_end'],audit['original_first'][1])
        # 旧表的35/proof48保留为历史声明，不被当作已证明的更早发布。
        self.assertIn((35,37,1,48),M3_FINITE_SUFFIX_AUDIT['M2']['events'])

    def test_natural_successor_requires_own_completion_and_visible_same_path_parent(self):
        """D最少三笔/交集/净向只是必要条件，须另有完成证书和可见前驱。"""
        audit,parts,seen=self._natural_successor_source('M2')
        for parent in (None,dict(event=audit['parent'],published_count=None),
                       dict(event=audit['parent'],published_count=1200)):
            self.assertIsNone(manual_natural_successor_certificate(parts,seen,1183,audit,parent))
        parent=dict(event=audit['parent'],published_count=940)
        short=dict(audit,successor=(42,42,1,51),extended=(38,42,1,51))
        with self.assertRaisesRegex(ValueError,'至少三笔'):
            manual_natural_successor_certificate(parts,seen,1183,short,parent)
        unproved=dict(audit,successor=(42,48,1,50))
        with self.assertRaisesRegex(ValueError,'局部完成证书'):
            manual_natural_successor_certificate(parts,seen,1183,unproved,parent)
        mismatch=dict(audit,successor=(44,48,1,51))
        with self.assertRaisesRegex(ValueError,'身份不衔接'):
            manual_natural_successor_certificate(parts,seen,1183,mismatch,parent)
        stale=dict(audit,old_boundary=(35,37,1,48))
        with self.assertRaisesRegex(ValueError,'原段分界'):
            manual_natural_successor_certificate(parts,seen,1183,stale,parent)

    def test_natural_state_seed87_all_visible_prefixes_keep_pending_contract(self):
        """17笔有限目标合同：102前仅种子完成，103才逆传；不调用未修正的包算法。"""
        audit = M3_NATURAL_STATE_AUDIT
        source = M3_FINITE_SUFFIX_AUDIT['M2']
        path = ROOT/'tests/fixtures'/source['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==source['id'])
        values = M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks']
        self.assertEqual(tuple([case['foundation']['bis'][87][3]]+
            [b[4] for b in case['foundation']['bis'][87:104]]),values)
        seen = case['foundation']['bis_confirmed_raw_count'][87:104]
        for mirrored in (False,True):
            parts = self._natural_parts([3000-v for v in values] if mirrored else values)
            # 本参考适用前提：给定90的标准旧侧91与首反93无正gap且已笔破坏。
            left,r = parts[4],parts[audit['first']]
            self.assertLessEqual(r['low_ticks'],left['high_ticks'])
            self.assertGreaterEqual(r['high_ticks'],left['low_ticks'])
            self.assertTrue(r['end_ticks']<=left['high_ticks'] if mirrored else
                            r['end_ticks']>=left['low_ticks'])
            context = dict(event=audit['predecessor'],published_count=seen[5])
            for count in range(1,18):
                completed = [audit['predecessor']] if count>=6 else []
                if count>=7:
                    state = manual_natural_reaction_state(parts[:count],seen[:count],seen[count-1],
                        audit['owner'],audit['first'],context,audit['reaction'])
                    self.assertEqual(state['qualification'],'visible')
                    self.assertEqual(state['state'],'pending' if count<17 else
                                     'confirmed_without_start_break')
                    if count<17:
                        self.assertIsNone(state['published_count'])
                    else:
                        self.assertEqual((state['local_proof'],state['local_count'],state['published_count']),
                                         (16,seen[16],seen[16]))
                        completed.append(audit['completed_at17'][1])
                    if count>=16:
                        # 内部93..97/proof102局部确实成立，仍不授予自然新起点。
                        self.assertTrue(manual_xd_certificate_ready(parts[:count],audit['forbidden'][0]))
                expected = () if count<6 else (audit['predecessor'],) if count<17 else audit['completed_at17']
                self.assertEqual(tuple(completed),expected)
                self.assertTrue(all(event not in completed for event in audit['forbidden']))

    def test_natural_state_strict_first_boundaries_and_mirrors(self):
        """等首起/终价仍未选向；严格边界和自然反应确认四态分别保留。"""
        values = list(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])
        variants = [(values[:17],None,'pending',None),
                    (values[:16]+[1029],None,'pending',None),
                    (values[:16]+[1028],None,'first_start_broken',15),
                    (values[:17]+[1091],(7,9,1,16),'confirmed_without_start_break',16),
                    (values[:17]+[1092],(7,9,1,16),'first_end_selected',16),
                    (values,(7,9,1,16),'confirmed_without_start_break',16)]
        for prices,reaction,kind,proof in variants:
            for mirrored in (False,True):
                parts = self._natural_parts([3000-v for v in prices] if mirrored else prices)
                seen = list(range(len(parts)))
                result = manual_natural_reaction_state(parts,seen,seen[-1],3,6,
                    dict(event=(0,2,1,5),published_count=5),reaction)
                self.assertEqual((result['state'],result['local_proof']),(kind,proof))

    def test_natural_state_earlier_confirmation_survives_later_boundary_break(self):
        """自然反应16先确认后，17破首起/18选首终不回撤已成立事件。"""
        values = list(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])+[1028,1092]
        for mirrored in (False,True):
            parts = self._natural_parts([3000-v for v in values] if mirrored else values)
            for count in (17,18,19):
                seen = list(range(count))
                result = manual_natural_reaction_state(parts[:count],seen,seen[-1],3,6,
                    dict(event=(0,2,1,5),published_count=5),(7,9,1,16))
                self.assertEqual((result['state'],result['local_proof'],result['published_count']),
                                 ('confirmed_without_start_break',16,16))

    def test_natural_state_unknown_waiting_and_late_visible_qualification(self):
        """资格晚到只延后发布，局部证明不改写，也不把已知等待降成未知前史。"""
        parts = self._natural_parts(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])
        seen = list(range(100,117))
        unknown = manual_natural_reaction_state(parts,seen,116,3,6,None,(7,9,1,16))
        self.assertEqual((unknown['qualification'],unknown['local_proof'],unknown['published_count']),
                         ('unknown',16,None))
        unpublished = manual_natural_reaction_state(parts,seen,116,3,6,
            dict(event=(0,2,1,5),published_count=None),(7,9,1,16))
        self.assertEqual((unpublished['qualification'],unpublished['predecessor'],unpublished['published_count']),
                         ('waiting',(0,2,1,5),None))
        context = dict(event=(0,2,1,5),published_count=200)
        for observed in (116,199,200):
            result = manual_natural_reaction_state(parts,seen,observed,3,6,context,(7,9,1,16))
            self.assertEqual((result['local_proof'],result['local_count']),(16,116))
            self.assertEqual(result['qualification'],'visible' if observed==200 else 'waiting')
            self.assertEqual(result['published_count'],200 if observed==200 else None)
        # 自然第三笔9在109可见；资格110晚到仍可在当前116应用，不强加<=第三笔。
        late = manual_natural_reaction_state(parts,seen,116,3,6,
            dict(event=(0,2,1,5),published_count=110),(7,9,1,16))
        self.assertEqual((late['qualification'],late['published_count']),('visible',116))

    def test_natural_state_same_observation_start_break_cannot_be_revived(self):
        """同批完成和破首起价不构成未破；晚资格不能复活被否决条件。"""
        values = list(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])+[1028]
        for mirrored in (False,True):
            parts = self._natural_parts([3000-v for v in values] if mirrored else values)
            seen = list(range(100,116))+[200,200]
            for observed in (200,250):
                result = manual_natural_reaction_state(parts,seen,observed,3,6,
                    dict(event=(0,2,1,5),published_count=250),(7,9,1,16))
                self.assertEqual((result['state'],result['local_proof'],result['local_count']),
                                 ('first_start_broken',17,200))
                self.assertEqual(result['published_count'],250 if observed==250 else None)

    def test_natural_state_late_local_certificate_cannot_revive_broken_first_start(self):
        """反应S有有效局部证书也不能复活先破首起价的R；同批/晚资格两侧均核。"""
        values = [30,40,35,50,12,16,10,20,15,18,9,17,12,19]
        for mirrored in (False,True):
            parts = self._natural_parts([100-v for v in values] if mirrored else values)
            self.assertTrue(manual_xd_certificate_ready(parts,(7,9,1,12)))
            seen = list(range(1,10))+[13,13,13,13]
            for observed in (13,20):
                result = manual_natural_reaction_state(parts,seen,observed,3,6,
                    dict(event=(0,2,1,5),published_count=20),(7,9,1,12))
                self.assertEqual((result['state'],result['local_proof'],result['local_count']),
                                 ('first_start_broken',9,13))
                self.assertEqual(result['published_count'],20 if observed==20 else None)

    def test_natural_state_rejects_mismatched_identity_and_future_parts(self):
        """仅同一前驱/R/S身份可累积资格，不能借相同proof索引或未来笔放行。"""
        parts = self._natural_parts(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])
        seen = list(range(17))
        cases = [((1,3,1,6),6,(7,9,1,16),'前驱证书身份'),
                 ((0,2,1,5),4,(7,9,1,16),'累计发布'),
                 ((0,2,1,5),5,(8,10,1,16),'紧邻起点')]
        for event,published,reaction,error in cases:
            with self.assertRaisesRegex(ValueError,error):
                manual_natural_reaction_state(parts,seen,16,3,6,
                    dict(event=event,published_count=published),reaction)
        with self.assertRaisesRegex(ValueError,'当前观察前缀'):
            manual_natural_reaction_state(parts,seen,15,3,6,None,(7,9,1,16))
        with self.assertRaisesRegex(ValueError,'逐项对应且有序'):
            manual_natural_reaction_state(parts,seen[:-1],16,3,6,None,(7,9,1,16))

    def test_m2_given_first_pen_proofs_keep_parent_gates_and_natural_scope(self):
        """65/111局部首笔选向已证；原首起价等价不撤销，发布仍带给定链前提。"""
        tool = compiler()
        source = M3_FINITE_SUFFIX_AUDIT['M2']
        audit = M3_M2_GIVEN_PROOFS_AUDIT
        path = ROOT / 'tests/fixtures' / source['fixture']
        self.assertEqual(tool.digest(path),source['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==source['id'])
        rows = case['raw_rows']
        _, _, bis = tool.foundation(rows,'106')
        fixed = tool.components(rows,bis[:-1],None)
        self.assertEqual(tool.records(bis),case['foundation']['bis'])
        seen = case['foundation']['bis_confirmed_raw_count']
        for j,event in enumerate(audit['events']):
            a,z,mode,proof = event
            first,start,end,equal = audit['original_first'][j]
            self.assertEqual((fixed[first]['start_ticks'],fixed[first]['end_ticks']),(start,end))
            self.assertEqual(fixed[equal]['end_ticks'],start)
            self.assertLess(fixed[proof]['end_ticks'],end)
            self.assertEqual(seen[proof],audit['local_counts'][j])
            self.assertEqual(seen[audit['old_proofs'][j]],1648 if a==65 else 2476)
            self.assertTrue(manual_xd_certificate_ready(fixed,event))
            parent = audit['parent_events'][j]
            self.assertEqual(seen[parent[3]],audit['parent_counts'][j])
            self.assertTrue(manual_xd_certificate_ready(fixed,parent))
            # 仅装配给定的parent+子段；局部证据不改成父证明笔。
            published = max(audit['local_counts'][j],audit['parent_counts'][j])
            self.assertEqual(published,audit['conditional_publication'][j])
            for count in sorted({audit['local_counts'][j]-1,audit['local_counts'][j],
                                 published-1,published}):
                _, _, current = tool.foundation(rows[:count],'106')
                parts = tool.components(rows[:count],current[:-1],None)
                self.assertEqual(tool.records(current[:-1]),case['foundation']['bis'][:len(current)-1])
                self.assertEqual(manual_xd_certificate_ready(parts,event),
                                 count>=audit['local_counts'][j])
                units = tool.xd_records(parts,(parent,event))
                self.assertEqual(len(units)==2,count>=published)
                if len(units)==2:
                    self.assertEqual(units[-1]['proof_bi'],proof)
            # 历史声明保持；新证书并不静默改写继承27项。
            original = next(e for e in source['events'] if e[0]==a)
            self.assertEqual(original,(a,z,mode,audit['old_proofs'][j]))
        self.assertEqual(audit['conditional_publication'][0],1648)
        self.assertEqual(2476-audit['conditional_publication'][1],39)
        self.assertFalse(audit['natural_start111_proven'])

    def test_m2_recent_seed87_requires_pending_natural_reaction_before_later_turns(self):
        """课78近期种子87：前段已破坏，首反93后的自然94未破首底；不得凭旧表补自然起点。"""
        tool = compiler()
        source = M3_FINITE_SUFFIX_AUDIT['M2']
        audit = M3_M2_GIVEN_PROOFS_AUDIT
        case = next(c for c in json.loads((ROOT/'tests/fixtures'/source['fixture']).read_text())['cases']
                    if c['id']==source['id'])
        _, _, bis = tool.foundation(case['raw_rows'],'106')
        fixed = tool.components(case['raw_rows'],bis[:-1],None)
        self.assertEqual(tuple([fixed[87]['start_ticks']]+[u['end_ticks'] for u in fixed[87:104]]),
                         audit['recent_seed87_ticks'])
        seen = case['foundation']['bis_confirmed_raw_count']
        self.assertEqual((seen[92],seen[96]),audit['state_counts'])
        self.assertLess(seen[92],seen[96])
        for mirrored in (False,True):
            parts = fixed if not mirrored else [dict(u,
                direction='down' if u['direction']=='up' else 'up',
                start_ticks=3000-u['start_ticks'],end_ticks=3000-u['end_ticks'],
                low_ticks=3000-u['high_ticks'],high_ticks=3000-u['low_ticks']) for u in fixed]
            for event in audit['natural_events']:
                self.assertTrue(manual_xd_certificate_ready(parts,event))
            first = parts[93]
            reaction = parts[94:97]
            if mirrored:
                self.assertLess(max(u['high_ticks'] for u in reaction),first['start_ticks'])
                self.assertGreater(min(parts[i]['end_ticks'] for i in (95,97,99,101,103)),first['end_ticks'])
            else:
                self.assertGreater(min(u['low_ticks'] for u in reaction),first['start_ticks'])
                self.assertLess(max(parts[i]['end_ticks'] for i in (95,97,99,101,103)),first['end_ticks'])
            # 固定BI前缀截至102时，自然94的103证明未到；None应保持待定，原始行另计。
            self.assertFalse(manual_xd_certificate_ready(parts[:103],audit['natural_events'][1]))
        self.assertEqual(min(u['low_ticks'] for u in fixed[94:97])-fixed[93]['start_ticks'],29)

    def test_additional_g1_common_suffix_uses_bounded_event_specific_active_proofs(self):
        """G1实际消费不超1623；逐事件核首次价，不把同proof126放行时刻合并。"""
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        audit = M3_ADDITIONAL_CONSUMERS_AUDIT['G1']
        path = ROOT / 'tests/fixtures' / audit['fixture']
        self.assertEqual(tool.digest(path),audit['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        packet_path = ROOT / 'validation' / case['source']['packet']
        self.assertEqual(tool.digest(packet_path),audit['packet_sha256'])
        packet = json.loads(packet_path.read_text())
        self.assertEqual(packet['rows'],case['raw_rows'])
        self.assertEqual(packet['manifest_sha256'],case['source']['dataset_manifest_sha256'])
        self.assertEqual(len(packet['rows']),audit['source_rows'])
        first = case['first_point']['first_raw_count']
        actual = (first-1,first,case['formation']['resolution']['first_raw_count'])
        self.assertEqual(actual,audit['actual_prefixes'])
        self.assertEqual(max(actual),audit['limit'])
        rows, events = packet['rows'][:audit['limit']],audit['events']
        self.assertEqual(audit['source_rows']-len(rows),15)
        self.assertTrue(all(r['adj_factor']==1 for r in rows))
        self.assertFalse(audit['global_theory_labels'])
        self.assertFalse(audit['seed0_seed1_resolved'])
        _, _, bis = tool.foundation(rows,'106')
        final = tool.components(rows,bis,None)
        self.assertEqual((len(final),len(final[:-1])),(audit['all_bis'],audit['fixed_bis']))
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(final)-1])
        strict.validate_xd_events(dict(xd_events=events),final)
        start, price, overlap = audit['given_common_start']
        self.assertEqual((events[0][0],final[start]['start_ticks']),(start,price))
        self.assertEqual((max(p['low_ticks'] for p in final[start:start+3]),
                          min(p['high_ticks'] for p in final[start:start+3])),overlap)
        fields = ('direction','start_dt','end_dt','start_ticks','end_ticks',
                  'low_ticks','high_ticks','mode','proof_bi')
        shape = [tuple(u[k] for k in fields) for u in tool.xd_records(final,events)]
        local, published, birth, fixed = {},{},{},{}
        first_prices, actual_lengths = {},{}
        for count in range(1,len(rows)+1):
            _, _, current_bis = tool.foundation(rows[:count],'106')
            current = tool.components(rows[:count],current_bis,None)
            self.assertEqual(tool.records(current_bis[:-1]),tool.records(bis)[:len(current_bis[:-1])])
            ready = [manual_xd_certificate_ready(current,e) for e in events]
            for i,(event,present) in enumerate(zip(events,ready)):
                proof = event[3]
                if len(current)>proof:
                    birth.setdefault(proof,(count,current[proof]['end_ticks']))
                if len(current)>proof+1:
                    fixed.setdefault(proof,(count,current[proof]['end_ticks']))
                if present:
                    local.setdefault(i,count)
                    first_prices.setdefault(i,(count,current[proof]['end_ticks']))
                self.assertEqual(present,audit['local_counts'][i]<=count,(count,i))
            length = next((i for i,present in enumerate(ready) if not present),len(events))
            for i in range(length):
                published.setdefault(i,count)
            self.assertEqual(length,sum(n<=count for n in audit['published_counts']),count)
            # 活动proof索引存在不够；先验价格证书，再装配相邻ready前缀。
            units = tool.xd_records(current,events[:length])
            self.assertEqual([tuple(u[k] for k in fields) for u in units],shape[:length],count)
            if count in actual:
                actual_lengths[count] = length
        self.assertEqual(actual_lengths,{125:0,126:0,1623:8})
        self.assertEqual(tuple(local[i] for i in range(len(events))),audit['local_counts'])
        self.assertEqual(tuple(published[i] for i in range(len(events))),audit['published_counts'])
        stages = tuple(birth[e[3]]+first_prices[i]+fixed[e[3]] for i,e in enumerate(events))
        self.assertEqual(stages,audit['proof_stages'])

    def test_additional_g1_shared_proof126_and_tail132_do_not_use_future_source_rows(self):
        """同一活动126的第二种先成立，第一种另待跨价；132仍在原130范围内。"""
        tool = compiler()
        audit = M3_ADDITIONAL_CONSUMERS_AUDIT['G1']
        labels = json.loads((ROOT / 'tests/fixtures' / audit['fixture']).read_text())
        case = next(c for c in labels['cases'] if c['id']==audit['id'])
        rows = case['raw_rows'][:audit['limit']]
        second, first = audit['events'][5:7]
        self.assertEqual((second[2:],first[2:]),((2,126),(1,126)))
        for count in (1535,1539,1540):
            _, _, bis = tool.foundation(rows[:count],'106')
            parts = tool.components(rows[:count],bis,None)
            self.assertEqual(len(parts)-1,126)
            self.assertEqual(parts[124]['end_ticks'],1152)
            self.assertTrue(manual_xd_certificate_ready(parts,second))
            self.assertEqual(manual_xd_certificate_ready(parts,first),count>=1540)
            if count<1540:
                self.assertGreaterEqual(parts[126]['end_ticks'],parts[124]['end_ticks'])
            else:
                self.assertEqual(parts[126]['end_ticks'],1141)
                self.assertLess(parts[126]['end_ticks'],parts[124]['end_ticks'])
        for count,value,ready in ((1573,1196,False),(1580,1206,True)):
            _, _, bis = tool.foundation(rows[:count],'106')
            parts = tool.components(rows[:count],bis,None)
            self.assertEqual((parts[127]['end_ticks'],parts[129]['end_ticks']),(1196,value))
            self.assertEqual(manual_xd_certificate_ready(parts,audit['events'][-1]),ready)
        _, _, bis = tool.foundation(rows,'106')
        parts = tool.components(rows,bis,None)
        start, endpoint, high, first, threshold, third, price = audit['tail']
        self.assertEqual((audit['events'][-1][1]+1,len(parts)-1),(start,third))
        self.assertEqual((len(parts),len(parts[:-1])),(133,132))
        self.assertEqual((parts[endpoint]['end_ticks'],parts[first]['end_ticks'],
                          parts[third]['end_ticks']),(high,threshold,price))
        self.assertEqual((threshold,price),(1106,1108))
        self.assertTrue(all(parts[i]['end_ticks']>=threshold for i in range(first+2,len(parts),2)))
        self.assertTrue(all(parts[i]['end_ticks']<=high for i in range(first+1,len(parts),2)))
        self.assertLessEqual(max(p['low_ticks'] for p in parts[first:third+1]),
                             min(p['high_ticks'] for p in parts[first:third+1]))

    def test_additional_e_sources_and_both_contracts_use_actual_raw_prefixes(self):
        """E长窗给定近期顶；两BI合同逐300原始前缀核事件和串行可见性。"""
        tool = compiler()
        audit = M3_ADDITIONAL_CONSUMERS_AUDIT['E']
        path = ROOT / 'tests/fixtures' / audit['fixture']
        self.assertEqual(tool.digest(path),audit['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        packet_path = ROOT / 'validation' / case['source']['packet']
        self.assertEqual(tool.digest(packet_path),audit['packet_sha256'])
        packet = json.loads(packet_path.read_text())
        self.assertEqual(packet['rows'],case['raw_rows'])
        self.assertEqual(packet['manifest_sha256'],case['source']['dataset_manifest_sha256'])
        rows, events = packet['rows'],audit['events']
        self.assertEqual(len(rows),audit['limit'])
        self.assertTrue(all(r['adj_factor']==1 for r in rows))
        _, _, bis = tool.foundation(rows,'106')
        self.assertEqual(tool.records(bis),case['foundation_106']['bis'])
        final = tool.components(rows,bis,10)
        self.assertEqual((len(final),len(final[:-1])),(audit['all_bis'],audit['fixed_bis']))
        a, day, value, overlap = audit['seed']
        self.assertEqual((a,final[a]['start_dt'],final[a]['start_ticks']), (0,day,value))
        self.assertEqual((max(p['low_ticks'] for p in final[a:a+3]),
                          min(p['high_ticks'] for p in final[a:a+3])),overlap)
        self.assertFalse(audit['global_theory_labels'])
        final_units = tool.xd_records(final,events)
        fields = ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        final_shape = [tuple(u[k] for k in fields) for u in final_units]
        local = dict((key,{}) for key in audit['local_counts'])
        serial = dict((key,{}) for key in local)
        special = dict((key,{}) for key in local)
        first_bi29 = None
        for count in range(1,len(rows)+1):
            _, _, current_bis = tool.foundation(rows[:count],'106')
            self.assertEqual(tool.records(current_bis[:-1]),tool.records(bis)[:len(current_bis[:-1])])
            current = tool.components(rows[:count],current_bis,10)
            if len(current)>29 and first_bi29 is None:
                first_bi29 = count
            for key,parts in (('all_current',current),('fixed_without_active',current[:-1])):
                ready = [manual_xd_certificate_ready(parts,event) for event in events]
                for i,present in enumerate(ready):
                    if present:
                        local[key].setdefault(i,count)
                        p = events[i][3]
                        if p in audit['special_proof_first'][key]:
                            special[key].setdefault(p,(count,parts[p]['end_dt'],parts[p]['end_ticks']))
                    self.assertEqual(present,audit['local_counts'][key][i]<=count,(key,count,i))
                length = next((i for i,present in enumerate(ready) if not present),len(events))
                for i in range(length):
                    serial[key].setdefault(i,count)
                expected = sum(n<=count for n in audit['published_counts'][key])
                self.assertEqual(length,expected,(key,count))
                units = tool.xd_records(parts,events)
                self.assertEqual([tuple(u[k] for k in fields) for u in units],final_shape[:expected],(key,count))
        self.assertEqual(first_bi29,audit['first_available_bi29'])
        for key in local:
            self.assertEqual(tuple(local[key][i] for i in range(len(events))),audit['local_counts'][key])
            self.assertEqual(tuple(serial[key][i] for i in range(len(events))),audit['published_counts'][key])
            self.assertEqual(special[key],audit['special_proof_first'][key])
            parts = final if key=='all_current' else final[:-1]
            start,last,last_same,end,revoke = audit['tail'][key]
            self.assertEqual((events[-1][1]+1,len(parts)-1),(start,last))
            self.assertEqual((parts[last_same]['direction'],parts[last_same]['end_ticks']),('down',end))
            self.assertEqual((parts[33]['start_ticks'],parts[33]['end_ticks']),(913,955))
            self.assertFalse(any(parts[i]['end_ticks']>955 for i in range(35,len(parts),2)))
            actual_revoke = next((i for i in range(34,len(parts),2) if parts[i]['end_ticks']<913),None)
            self.assertEqual(actual_revoke,revoke)

    def test_additional_e_active_endpoints_and_raw_price_layers_do_not_backfill(self):
        """活动845/1024与固定1185/1039分列；raw跨价不等于BI29已经可用。"""
        tool = compiler()
        foundation_tool = compiler(ROOT / 'validation/tools/gen_real_f1_originals.py')
        audit = M3_ADDITIONAL_CONSUMERS_AUDIT['E']
        data = json.loads((ROOT / 'tests/fixtures' / audit['fixture']).read_text())
        case = next(c for c in data['cases'] if c['id']==audit['id'])
        rows = case['raw_rows'][:audit['limit']]
        for key,proofs in audit['special_proof_first'].items():
            for proof,(count,day,value) in proofs.items():
                _, _, bis = tool.foundation(rows[:count],'106')
                parts = tool.components(rows[:count],bis,10)
                selected = parts if key=='all_current' else parts[:-1]
                self.assertEqual((selected[proof]['end_dt'],selected[proof]['end_ticks']),(day,value))
                if key=='all_current':
                    self.assertEqual(len(parts)-1,proof)
                    self.assertLess(len(parts[:-1]),proof+1)
                    self.assertNotEqual(value,audit['special_proof_first']['fixed_without_active'][proof][2])
                else:
                    self.assertGreater(len(parts)-1,proof)
        for threshold,(count,day,high) in audit['raw_crosses'].items():
            first = next(i+1 for i,row in enumerate(rows) if row['dt'][:10]>='2019-08-30'
                         and foundation_tool.ticks(row['high'])>threshold)
            self.assertEqual(first,count)
            self.assertEqual((rows[count-1]['dt'][:10],foundation_tool.ticks(rows[count-1]['high'])),(day,high))
            _, _, bis = tool.foundation(rows[:count],'106')
            self.assertEqual(len(bis),29)  # 末索引28，尚无proof29。
            self.assertEqual(bis[-1]['direction'],'down')
        self.assertEqual((audit['raw_crosses'][964][0],audit['raw_crosses'][1017][0],
                          audit['first_available_bi29']),(251,252,255))
        for count in (254,255):
            _, _, bis = tool.foundation(rows[:count],'106')
            self.assertEqual(len(bis),29 if count==254 else 30)
        # 同一可用BI快照的第二底和新高，不提升为原始price先后或最早理论确认。
        for count in (audit['active_tail_revoke_raw']-1,audit['active_tail_revoke_raw']):
            _, _, bis = tool.foundation(rows[:count],'106')
            current = tool.components(rows[:count],bis,10)
            revoked = len(current)>34 and current[34]['end_ticks']<913
            self.assertEqual(revoked,count==audit['active_tail_revoke_raw'])

    def test_finite_suffix_events_keep_sources_geometry_and_ordered_raw_visibility(self):
        """两条显式有限后缀由独立基础/结构/逐前缀回放验收，旧标签保持历史。"""
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        self.assertEqual(set(M3_FINITE_SUFFIX_AUDIT), {'Y1','M2'})
        for key, audit in sorted(M3_FINITE_SUFFIX_AUDIT.items()):
            path = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(path), audit['fixture_sha256'])
            case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
            packet_path = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(tool.digest(packet_path), audit['packet_sha256'])
            packet = json.loads(packet_path.read_text())
            self.assertEqual(packet['rows'], case['raw_rows'])
            self.assertEqual(packet['manifest_sha256'], case['source']['dataset_manifest_sha256'])
            rows, events = packet['rows'], audit['events']
            self.assertEqual(len(rows), audit['raw_rows'])
            self.assertEqual(len(events), 39)
            base = audit['inherited_prefix']
            self.assertEqual(tuple(tuple(e) for e in case['foundation']['xd_events'][:base]), events[:base])
            self.assertEqual((base,audit['given_adjacent']), (7,0) if key=='Y1' else (27,4))
            _, _, bis = tool.foundation(rows, '106')
            self.assertEqual(tool.records(bis), case['foundation']['bis'])
            fixed = tool.components(rows, bis[:-1], None)
            self.assertEqual(len(fixed), audit['fixed_bis'])
            strict.validate_xd_events(dict(xd_events=events), fixed)
            reference = dict(standard='106',expected_bis=case['foundation']['bis'])
            bi_seen, published = strict.replay_confirmations(rows, reference, events)
            self.assertEqual(bi_seen, case['foundation']['bis_confirmed_raw_count'])
            self.assertEqual(tuple(bi_seen[e[3]] for e in events), audit['local_counts'])
            self.assertEqual(tuple(published), audit['published_counts'])
            units = tool.xd_records(fixed, events)
            strict.check_adjacency(units)
            self.assertEqual(tuple(u['proof_bi'] for u in units), tuple(e[3] for e in events))
            for count in sorted(set(n for value in published for n in (value-1,value))):
                visible = [u for u, seen in zip(fixed,bi_seen) if seen<=count]
                expected = sum(seen<=count for seen in published)
                self.assertEqual(tool.xd_records(visible,events), units[:expected], (key,count))
            start, last, endpoint, value = audit['tail']
            self.assertEqual((events[-1][1]+1,len(fixed)-1), (start,last))
            self.assertEqual(fixed[endpoint]['end_ticks'], value)
            if key != 'Y1':
                continue

            def band(i):
                return fixed[i]['low_ticks'],fixed[i]['high_ticks']

            def standard(indices, up):
                nodes = []
                for i in indices:
                    low, high = band(i)
                    if nodes and ((low<=nodes[-1][1] and high>=nodes[-1][2]) or
                                  (low>=nodes[-1][1] and high<=nodes[-1][2])):
                        ids, old_low, old_high = nodes[-1]
                        pick = max if up else min
                        nodes[-1] = (ids+(i,),pick(low,old_low),pick(high,old_high))
                    else:
                        if nodes:
                            up = high>nodes[-1][2]
                        nodes.append(((i,),low,high))
                return nodes

            # 原132/后134同高包含；上向合并仍是原gap元素，不能改取134/proof138。
            self.assertEqual((band(130),band(132),band(134),band(136)),
                             ((8937,8967),(8972,8986),(8933,8986),(8944,8963)))
            middle = tuple(max(band(132)[k],band(134)[k]) for k in (0,1))
            self.assertEqual(middle, band(132))
            self.assertEqual(middle[0]-band(130)[1], 5)
            self.assertTrue(all(middle[k]>max(band(130)[k],band(136)[k]) for k in (0,1)))
            self.assertIn((127,131,2,147), events)
            self.assertNotIn((127,133,1,138), events)
            self.assertEqual(max(u['high_ticks'] for u in fixed[132:148]),8986)
            second_bottoms = []
            for last_bi in range(133,148,2):
                nodes = standard(range(133,last_bi+1,2),False)
                if len(nodes)>=3:
                    left, mid, right = nodes[-3:]
                    if all(mid[k]<min(left[k],right[k]) for k in (1,2)):
                        second_bottoms.append(last_bi)
            self.assertEqual(second_bottoms,[147])
            self.assertEqual(nodes[-3:], [((141,),8892,8910),((143,145),8655,8705),
                                         ((147,),8694,8731)])
            # down226首上231尚未越8395，就被238跌破原首底8347；按78原段延续。
            self.assertEqual((fixed[231]['start_ticks'],fixed[231]['end_ticks']), (8347,8395))
            selected = next(i for i in range(233,len(fixed),2) if fixed[i]['end_ticks']>8395)
            revoked = next(i for i in range(232,len(fixed),2) if fixed[i]['end_ticks']<8347)
            self.assertEqual((selected,revoked), (249,238))
            self.assertLess(fixed[238]['end_ticks'],8347)
            for first, revoked in ((233,234),(235,236),(237,238),(239,240)):
                selected = next(i for i in range(first+2,len(fixed),2)
                                if fixed[i]['end_ticks']>fixed[first]['end_ticks'])
                actual = next(i for i in range(first+1,len(fixed),2)
                              if fixed[i]['end_ticks']<fixed[first]['start_ticks'])
                self.assertEqual(actual,revoked)
                self.assertLess(revoked,selected)
            self.assertIn((226,240,1,243), events)
            # 252尾部原gap13，第一底已齐；第二序列只有262，不能制造第二分型。
            self.assertEqual((band(259),band(261),band(263)),
                             ((8396,8412),(8360,8383),(8362,8388)))
            self.assertEqual(band(259)[0]-band(261)[1],13)
            self.assertTrue(all(band(261)[k]<min(band(259)[k],band(263)[k]) for k in (0,1)))
            self.assertEqual(list(range(262,len(fixed),2)), [262])
            self.assertEqual(min(u['low_ticks'] for u in fixed[start:]),value)

    def test_m2_natural_240_context_preserves_original_first239_and_incomplete_303(self):
        """课78先核自然240及父段已破坏状态，不借242/248局部证书重设自然新起点。"""
        tool = compiler()
        audit = M3_FINITE_SUFFIX_AUDIT['M2']
        data = json.loads((ROOT / 'tests/fixtures' / audit['fixture']).read_text())
        case = next(c for c in data['cases'] if c['id']==audit['id'])
        rows = case['raw_rows']
        _, _, bis = tool.foundation(rows, '106')
        fixed, active = tool.components(rows,bis[:-1],None),tool.components(rows,bis,None)
        seen = case['foundation']['bis_confirmed_raw_count']
        # first239后的自然下行从240开始；不能跳到242或248才选择承重上下文。
        self.assertEqual([fixed[239]['start_ticks']]+[u['end_ticks'] for u in fixed[239:256]],
                         [1100,1157,1137,1150,1131,1138,1119,1135,1105,1137,
                          1111,1124,1115,1132,1113,1123,1114,1181])
        overlap = (max(u['low_ticks'] for u in fixed[240:243]),
                   min(u['high_ticks'] for u in fixed[240:243]))
        self.assertEqual(overlap, (1137,1150))
        self.assertEqual(min(u['low_ticks'] for u in fixed[240:247]),1105)
        self.assertGreater(1105,fixed[239]['start_ticks'])
        self.assertEqual((seen[241],seen[242],seen[255]), (4563,4571,4727))
        self.assertIn((201,227,2,241),audit['events'])
        self.assertIn((228,238,1,255),audit['events'])
        self.assertLess(seen[241],seen[242])  # 原down228已破前段201，早于自然第三笔。
        for first, revoked in ((243,244),(245,246)):
            self.assertLess(fixed[revoked]['end_ticks'],fixed[first]['start_ticks'])
        # 自然down240末246，原首反247的1137直到255才先被严格上破。
        self.assertEqual((fixed[247]['start_ticks'],fixed[247]['end_ticks']), (1105,1137))
        self.assertTrue(all(fixed[i]['end_ticks']<=1137 for i in (249,251,253)))
        self.assertTrue(all(fixed[i]['end_ticks']>1105 for i in (248,250,252,254)))
        self.assertGreater(fixed[255]['end_ticks'],1137)
        self.assertGreater(fixed[255]['end_ticks'],fixed[239]['end_ticks'])
        self.assertEqual(min(u['low_ticks'] for u in fixed[240:256]),1105)
        # 1157只在首一笔后出现，不能作为完成上段端点；1181又先被257新高撤销。
        self.assertGreater(fixed[257]['end_ticks'],fixed[256]['start_ticks'])
        self.assertIn((239,257,1,260),audit['events'])
        self.assertNotIn((239,241,1,255),audit['events'])
        self.assertNotIn((239,247,1,255),audit['events'])
        self.assertLess(fixed[260]['end_ticks'],fixed[258]['end_ticks'])
        self.assertEqual((seen[255],seen[260]), (4727,4774))
        # 303尾部的原首反310终1106始1131；等价触达不补严格选向/撤销。
        self.assertEqual(audit['tail'], (303,321,309,1131))
        self.assertEqual((fixed[310]['start_ticks'],fixed[310]['end_ticks']), (1131,1106))
        self.assertTrue(all(fixed[i]['end_ticks']>=1106 for i in range(312,len(fixed),2)))
        self.assertTrue(all(fixed[i]['end_ticks']<=1131 for i in range(311,len(fixed),2)))
        self.assertEqual(fixed[319]['end_ticks'],1131)
        self.assertEqual((len(fixed),len(active)), (322,323))
        self.assertEqual(active[322]['end_ticks'],1106)
        self.assertLess(Decimal(str(rows[-1]['low']))*1000,1106)  # 原始低价不是新固定证明笔。

    def test_portable_revised_parts_and_recursion_match_independent_integer_sources(self):
        """同一显式修订表自足随sdist；独立来源/事件/时序/F1F2算术逐项复核。"""
        table = embedded_table('test_real_xd_f1.py', 'M3_GAP_REVISION_AUDIT')
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        self.assertEqual(set(table), {'G','X1'})
        for key, audit in sorted(table.items()):
            path = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(path), audit['fixture_sha256'])
            case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(tool.digest(packet), case['source']['sha256'])
            self.assertEqual(json.loads(packet.read_text())['rows'], case['raw_rows'])
            rows = case['raw_rows']
            _, _, bis = tool.foundation(rows, '106')
            self.assertEqual(tool.records(bis), case['foundation']['bis'])
            fixed = tool.components(rows, bis[:-1], 10 if '-day-' in case['id'] else None)
            reference = dict(standard='106',expected_bis=case['foundation']['bis'])
            bi_seen, published = strict.replay_confirmations(rows, reference, audit['events'])
            units = tool.xd_records(fixed, audit['events'])
            rebuilt = [(u['direction'],u['start_dt'],u['end_dt'],u['start_ticks'],u['end_ticks'],
                        u['low_ticks'],u['high_ticks'],u['mode'],u['proof_bi'],
                        bi_seen[u['proof_bi']],known) for u,known in zip(units,published)]
            self.assertEqual(tuple(rebuilt), audit['units'], key)
            f1 = [tool.move_record(units, spec) for spec in audit['f1']]
            self.assertEqual(tuple(published[spec[-1]] for spec in audit['f1']),audit['f1_first_counts'])
            self.assertEqual(sum(record['complete'] for record in f1),1 if key=='G' else 4)
            tail = tool.move_record(units,audit['tail'])
            self.assertFalse(tail['complete'])
            self.assertLess(tail['seg_end']-tail['seg_start'],2)
            f2 = [tool.move_record(f1, spec) for spec in audit['f2']]
            self.assertFalse(any(record['complete'] for record in f2))
            if key == 'G':
                waves = [(min(u['low_ticks'] for u in units[j:j+3]),
                          max(u['high_ticks'] for u in units[j:j+3])) for j in (0,3)]
                self.assertEqual(waves, [(613,1185),(871,1185)])
                self.assertGreaterEqual(waves[0][1],waves[1][0])

    def test_512880_second_bottom_uses_observed_active_proof_without_future_extension(self):
        """2022窗局部第二种：活动proof12在raw152出现，不预读最终12-06极值。"""
        tool = compiler()
        data = json.loads((ROOT / 'tests/fixtures/real_xd_originals.json').read_text())
        case = next(c for c in data if c['id'] == '512880-day-2022-04-20-2022-12-09')
        events, previous = [[0,2,2,12], [3,9,1,12]], None
        for count in (151,152,157):
            rows = case['raw_rows'][:count]
            _, _, bis = tool.foundation(rows, '106')
            parts = tool.components(rows, bis)
            left, first, right = [parts[i] for i in (1,3,5)]
            self.assertEqual(first['low_ticks']-left['high_ticks'], 12)
            self.assertGreater(first['low_ticks'], right['low_ticks'])
            self.assertGreater(first['high_ticks'], max(left['high_ticks'],right['high_ticks']))
            units = tool.xd_records(parts, events)
            self.assertEqual(len(units), 0 if count == 151 else 2)
            self.assertEqual(tool.xd_records(parts[:-1], events), [])
            if not units:
                continue
            second = [(min(parts[a]['low_ticks'],parts[z]['low_ticks']),
                       min(parts[a]['high_ticks'],parts[z]['high_ticks'])) for a,z in ((4,6),(8,10))]
            second.append((parts[12]['low_ticks'],parts[12]['high_ticks']))
            self.assertEqual(second[:2], [(861,926),(797,863)])
            self.assertLess(second[1][0], min(second[0][0],second[2][0]))
            self.assertLess(second[1][1], min(second[0][1],second[2][1]))
            self.assertEqual((parts[12]['end_dt'],parts[12]['end_ticks']),
                             ('2022-12-01',929) if count == 152 else ('2022-12-06',933))
            shape = [(u['start_index'],u['end_index'],u['start_ticks'],u['end_ticks'],
                      u['low_ticks'],u['high_ticks'],u['mode']) for u in units]
            self.assertEqual([u['end_ticks'] for u in units], [1052,797])
            if previous is not None:
                self.assertEqual(shape, previous)
            previous = shape

    def test_first_pen_selection_survives_containment_equalities_and_revocation(self):
        """课65/71独立整数见证：原首笔边界选向，不以包含后元素数代替。"""
        cases = [
            ([12,5,10,3,9,3,11], 5, None, 0, 1),
            ([12,5,10,3,9,3,9], None, None, 0, 1),
            ([12,5,10,3,9,3,10], 5, None, 0, 1),
            ([12,5,10,3,9,2,11], 5, 4, 0, 1),
            ([12,5,10,3,9,4,11], 5, None, 0, 2),
            ([12,5,10,3,9,5,8,3,11], 7, None, 0, 1),
            ([12,5,10,3,4,3,6], 5, None, 1, 1),
            ([1048,1031,1043,1025,1042,1028,1038,1025,1033,1025,1042,1025,1044],
             11, None, 0, 1),
        ]
        for prices, selected, revoked, gap, feature_count in cases:
            for mirrored in (False, True):
                values = [3000-v for v in prices] if mirrored else prices
                parts = [tuple(sorted((a,z))) for a,z in zip(values,values[1:])]
                self.assertLessEqual(max(p[0] for p in parts[:3]), min(p[1] for p in parts[:3]))
                self.assertLessEqual(max(p[0] for p in parts[3:6]), min(p[1] for p in parts[3:6]))
                original_start, original_end = values[3:5]
                observed_selected = next((i for i in range(5,len(parts),2)
                    if (values[i+1] < original_end if mirrored else values[i+1] > original_end)), None)
                observed_revoked = next((i for i in range(4,len(parts),2)
                    if (values[i+1] > original_start if mirrored else values[i+1] < original_start)), None)
                actual_gap = max(0, parts[3][0]-parts[1][1] if mirrored else parts[1][0]-parts[3][1])
                self.assertEqual((observed_selected,observed_revoked,actual_gap), (selected,revoked,gap))
                nodes = [parts[3]]
                choose = max if mirrored else min
                for item in parts[5::2]:
                    node = nodes[-1]
                    contained = ((node[0]<=item[0] and node[1]>=item[1]) or
                                 (item[0]<=node[0] and item[1]>=node[1]))
                    if contained:
                        nodes[-1] = (choose(node[0],item[0]), choose(node[1],item[1]))
                    else:
                        nodes.append(item)
                # 上移右侧低点是两个标准元素的对照；等低包含例仍仅一个。
                self.assertEqual(len(nodes), feature_count)

    def test_local_first_pen_proofs_wait_for_pending_gap_predecessors(self):
        """M2/Y1局部首笔证明先到，须等父第二种证明；不替换两条旧尾链。"""
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        audits = [
            ('real_third_point_xd_margin0.json', 'M2',
             [[175,177,2,197],[178,180,1,189],[181,189,1,194],[190,200,1,203]],
             [3956,3811,3928,4016],[3956,3956,3956,4016],
             [1048,1031,1043,1025,1042,1028,1038,1025,1033,1025,1042,1025,1044]),
            ('real_second_point.json', 'Y1', [[49,51,2,65],[52,58,1,61]],
             [661,630],[661,661],[9543,9472,9492,9451,9487,9447,9471,9445,9460,9445,9474]),
        ]
        for filename, key, events, local, published, values in audits:
            labels = json.loads((ROOT / 'tests/fixtures' / filename).read_text())
            case = next(c for c in labels['cases'] if c['window_key'] == key)
            rows, expected = case['raw_rows'], case['foundation']['bis']
            seen = case['foundation']['bis_confirmed_raw_count']
            start, proof = events[1][0], events[1][3]
            self.assertEqual([seen[e[3]] for e in events], local)
            self.assertEqual([expected[start][3]]+[b[4] for b in expected[start:proof+1]], values)
            for count in sorted(set(n for value in local for n in (value-1,value))):
                _, _, bis = tool.foundation(rows[:count], '106')
                self.assertEqual(tool.records(bis[:-1]), expected[:len(bis)-1])
                fixed = tool.components(rows[:count], bis[:-1], None)
                for event, own in zip(events, local):
                    self.assertEqual(len(fixed)>event[3], count>=own)
                units = tool.xd_records(fixed, events)
                self.assertEqual(len(units), sum(value<=count for value in published))
                if units:
                    strict.validate_xd_events(dict(xd_events=events[:len(units)]), fixed)
                    self.assertEqual([u['proof_bi'] for u in units], [e[3] for e in events[:len(units)]])

    def test_pending_gap_conditional_chains_keep_local_proofs_and_ordered_visibility(self):
        """课67/71/81局部修订：实际proof不改写，X1四段须等父缺口同批发布。"""
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        for key, audit in sorted(pending_gap_revisions().items()):
            data = json.loads((ROOT / 'tests/fixtures' / audit['fixture']).read_text())
            case = next(c for c in data['cases'] if c['id'] == audit['id'])
            original = copy.deepcopy(case)
            rows = case['raw_rows']
            reference = dict(standard='106', expected_bis=case['foundation']['bis'])
            _, _, bis = tool.foundation(rows, '106')
            self.assertEqual(tool.records(bis), reference['expected_bis'], key)
            fixed = tool.components(rows, bis[:-1], None)
            events = (case['foundation']['xd_events'][:audit['base']]
                      if audit['base'] else []) + audit['events']
            strict.validate_xd_events(dict(xd_events=events), fixed)
            bi_seen, published = strict.replay_confirmations(rows, reference, events)
            self.assertEqual([bi_seen[e[3]] for e in audit['events']], audit['local_counts'], key)
            self.assertEqual(published[audit['base']:], audit['published_counts'], key)
            units = tool.xd_records(fixed, events)
            self.assertEqual([u['proof_bi'] for u in units[audit['base']:]],
                             [e[3] for e in audit['events']], key)
            for count in sorted(set(audit['published_counts'])):
                visible = [u for u, seen in zip(fixed, bi_seen) if seen <= count]
                expected = sum(seen <= count for seen in published)
                self.assertEqual(len(tool.xd_records(visible, events)), expected, (key,count))
            self.assertEqual(case, original)

    def test_x1_revised_f1_core_does_not_preserve_old_strict_or_point_premises(self):
        """工程三段核心与严格Zn角色分开；新ZG下旧c未离开，不继承一二类裁定。"""
        tool = compiler()
        strict = compiler(ROOT / 'validation/tools/gen_real_strict_trend.py')
        audit = pending_gap_revisions()['X1']
        manual = json.loads((ROOT / 'validation/chan-real-first-point-manual-0.9.9.json').read_text())
        case = next(c for c in manual['cases'] if c['id'] == audit['id'])
        packet = json.loads((ROOT / 'validation' / case['packet']).read_text())
        self.assertEqual(tool.digest(ROOT / 'validation' / case['packet']), case['packet_sha256'])
        _, _, bis = tool.foundation(packet['rows'], '106')
        fixed = tool.components(packet['rows'], bis[:-1], None)
        events = case['xd_events'][:audit['base']] + audit['events']
        units = strict.xd_units(fixed, events)
        self.assertEqual([(u['low_ticks'],u['high_ticks']) for u in units[7:11]],
                         [(1484,2678),(1989,2678),(1989,2402),(2079,2402)])
        engineering_core = (max(u['low_ticks'] for u in units[7:10]),
                            min(u['high_ticks'] for u in units[7:10]))
        zn_core = (max(units[i]['low_ticks'] for i in (8,10)),
                   min(units[i]['high_ticks'] for i in (8,10)))
        self.assertEqual(engineering_core, (1989,2402))
        self.assertEqual(zn_core, (2079,2402))
        self.assertNotEqual(engineering_core, zn_core)
        self.assertLessEqual(units[11]['high_ticks'], zn_core[1])
        self.assertEqual(units[11]['high_ticks'], 2320)
        with self.assertRaisesRegex(ValueError, 'B 首对核心与声明不一致'):
            strict.validate_roles(case, units)
        corrected = copy.deepcopy(case)
        corrected['roles']['B'].update(zd=2079, zg=2402, dd=1989, gg=2678)
        with self.assertRaisesRegex(ValueError, 'B 冻结须中间反向单元离开核心'):
            strict.validate_roles(corrected, units)
        # c11没有离开，不能冻结在旧Zn；u12触核，必须继续延伸。
        extended = dict(zn=[8,10,12], zd=2079, zg=2402, dd=1916, gg=2678,
                        closed_by=None)
        center = strict.validate_zhongshu('B', extended, units)
        self.assertEqual(center['zn'], [8,10,12])
        self.assertFalse(center['frozen_by_departure'])
        self.assertLess(units[13]['high_ticks'], center['zg'])
        self.assertEqual(units[13]['high_ticks'], 2242)

    def test_completed_xd_views_do_not_skip_unavailable_predecessors(self):
        """前段proof9晚于后段proof8；两段应同时发布，不倒填后段已可见。"""
        tool = compiler()
        values = [10,20,15,25,12,22,11,21,13,23,14,24,16,26]
        fixed = [dict(start_index=i, end_index=i+1, start_ticks=a,
                      end_ticks=z, low_ticks=min(a,z), high_ticks=max(a,z),
                      start_dt=str(i), end_dt=str(i+1), direction='up' if z>a else 'down')
                 for i, (a,z) in enumerate(zip(values, values[1:]))]
        # 交替、衔接且前三笔重叠的给定部件；只核事件表的发布时序。
        events = [[0, 2, 2, 9], [3, 5, 1, 8], [6, 8, 1, 12]]
        integer_path = ROOT / 'validation/tools/gen_real_f1_originals.py'
        spec = importlib.util.spec_from_file_location('ordered_xd_integer', integer_path)
        integer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integer)
        for build in (tool.xd_records, integer.completed_xds):
            self.assertEqual(build(fixed[:9], events), [])
            both = build(fixed[:10], events)
            self.assertEqual([u['start_index'] for u in both], [0, 3])
            self.assertEqual([u['proof_bi'] for u in both], [9, 8])
            self.assertEqual([u['start_index'] for u in build(fixed, events)], [0, 3, 6])

    def test_ipo_context_jan10_fixed_bi_is_not_ordinary_xd_confirmation(self):
        """上市史固定笔可映射，不以BI端点或前三笔重叠补课78特殊前提。"""
        parts = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        # 同源IPO上下文：full81为11-16→12-03的上笔，12-22已固定。
        # 以01-10为假设下段端点的4个基本几何候选，其末标准旧侧均为该笔。
        # 完整42假设与原始1110日前缀另存源审计；本测试只核有限条件算术。
        left = (609358802000, 694689112000)
        first, right = [tuple(sorted(parts[i][4:6])) for i in (0, 2)]
        self.assertLessEqual(max(left[0], first[0]), min(left[1], first[1]))
        self.assertLess(first[0], left[0])
        self.assertLess(first[1], left[1])
        self.assertLess(right[0], first[0])
        self.assertLess(right[1], first[1])  # 右侧更低，不能确认以first为底的普通分型。
        self.assertLess(parts[1][5], parts[0][4])
        # full84在raw897(02-18)固定低于01-10；第三笔full85须raw900(02-23)。
        self.assertEqual((parts[1][6] + 868, parts[2][6] + 868), (897, 900))
        self.assertLess(parts[1][6], parts[2][6])

    def test_ipo_context_given_dec3_start_has_later_ordinary_local_boundaries(self):
        """给定12-03起段的普通局部正例；不裁定其全局归属或替换原两窗。"""
        parts = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        band = lambda i: tuple(sorted(parts[i][4:6]))
        overlap = lambda rows: (max(r[0] for r in rows), min(r[1] for r in rows))
        # full82..84从12-03到02-14。01-10是内部折点，不将它改写为新起点。
        prior = (526277196640, 694689112000)
        self.assertEqual(prior[0], parts[0][4])
        self.assertEqual(overlap([prior, band(0), band(1)]), (526277196640, 612350382280))
        left, middle, right = [band(i) for i in (0, 2, 4)]
        self.assertTrue(all(middle[k] < min(left[k], right[k]) for k in (0, 1)))
        self.assertLessEqual(max(left[0], middle[0]), min(left[1], middle[1]))
        self.assertEqual(overlap([band(i) for i in (2, 3, 4)]), (494283349820, 545612041000))
        self.assertGreater(parts[4][5], parts[2][5])
        self.assertEqual(parts[4][6] + 868, 910)  # 03-09可见，不能倒填为02-14。

        # 给定上述后段，03-01端点依课71首反向破坏+第三笔延伸，非严格标准顶。
        left, first, third = [band(i) for i in (3, 5, 7)]
        self.assertGreater(first[1], left[1])
        self.assertLess(first[0], left[0])
        self.assertFalse(all(first[k] > max(left[k], third[k]) for k in (0, 1)))
        self.assertLessEqual(max(left[0], first[0]), min(left[1], first[1]))
        self.assertEqual(overlap([band(i) for i in (5, 6, 7)]), (444731536860, 537079010000))
        self.assertLess(parts[7][5], parts[5][5])
        self.assertEqual(parts[7][6] + 868, 956)  # 05-19固定证据到齐。

    def test_first_seed_candidate_lifecycle_keeps_revocation_order(self):
        """保持start0的14个假设；局部条件、撤销与未知前提分开，不给替代分界。"""
        parts = embedded_table('test_real_f1_originals.py','M3_FACTOR_F1_AUDIT')['cases']['2022-01-01-106']['parts']
        # 候选反向笔、端点首次可见行、更高峰首次可见行、反向三笔齐备行。
        frozen = [(1,26,None,37),(3,32,42,49),(5,42,120,88),(7,52,120,101),
                  (9,94,106,115),(11,106,120,124),(13,120,166,153),(15,133,166,170),
                  (17,166,None,180),(19,173,None,191),(21,184,195,205),
                  (23,195,None,217),(25,212,231,None),(27,231,None,None)]
        self.assertEqual([r[0] for r in frozen],list(range(1,len(parts)+1,2)))
        valid_net = []
        for candidate,endpoint_count,higher_count,three_count in frozen:
            endpoint = candidate-1
            self.assertEqual(parts[endpoint][6],endpoint_count)
            peak = parts[endpoint][5]
            higher = [p for p in parts[endpoint+2::2] if p[5] > peak]
            self.assertEqual(higher[0][6] if higher else None,higher_count)
            self.assertEqual(parts[candidate+2][6] if candidate+2 < len(parts) else None,three_count)
            self.assertEqual(max(p[5] for p in parts[:candidate:2]),612350382280)
            if peak > parts[0][4]:
                valid_net.append(candidate)
        self.assertEqual(valid_net,[1,3,5,7,13,15,17])
        self.assertLess(frozen[0][0],3)  # 最高峰自身不足最低三笔，不能直接用它闭合。
        self.assertEqual((max(min(p[4:6]) for p in parts[:3]),min(max(p[4:6]) for p in parts[:3])),
                         (526277196640,545612041000))

        # 13有正缺口但第二序列第三项须raw173；更高峰raw166已先到。
        self.assertEqual(min(parts[13][4:6])-max(parts[11][4:6]),41149287140)
        self.assertEqual(max(parts[13][4:6]),max(parts[15][4:6]))
        self.assertEqual([parts[i][6] for i in (14,16,18)],[133,166,173])
        self.assertLess(parts[16][6],parts[18][6])
        # 15的反向三笔还要等raw170，不能在更高峰到达前认定完成。
        self.assertLess(parts[16][6],max(parts[i][6] for i in (15,16,17)))
        # 5/17各有局部三笔，仍不得据此推定课78上下文已成立。
        for candidate,count in ((5,88),(17,180)):
            reverse = parts[candidate:candidate+3]
            self.assertEqual(reverse[-1][6],count)
            self.assertLessEqual(max(min(p[4:6]) for p in reverse),min(max(p[4:6]) for p in reverse))
            self.assertLess(reverse[-1][5],reverse[0][5])
            self.assertLess(parts[candidate-1][5],612350382280)

    def test_raw_crossed_start_threshold_is_not_standard_feature_proof(self):
        """8笔整数见证仅证明门槛不等价，不用识别器输出或赋予全局分界标签。"""
        original = [50,100,40,70,45,80,30,60,20]  # 抽象价位以0.1为单位。
        for points,up in ((original,True),([150-p for p in original],False)):
            bis = [(min(a,b),max(a,b)) for a,b in zip(points,points[1:])]
            self.assertEqual(len(bis),8)
            self.assertLessEqual(max(b[0] for b in bis[:3]),min(b[1] for b in bis[:3]))
            self.assertTrue(bis[1][0] <= bis[3][0] and bis[1][1] >= bis[3][1])
            pick = max if up else min
            standard = (pick(bis[1][0],bis[3][0]),pick(bis[1][1],bis[3][1]))
            raw,first = bis[3],bis[5]
            raw_turn = first[1] > raw[1] if up else first[0] < raw[0]
            standard_turn = first[1] > standard[1] if up else first[0] < standard[0]
            self.assertTrue(raw_turn)
            self.assertFalse(standard_turn)
            self.assertLessEqual(max(b[0] for b in bis[5:8]),min(b[1] for b in bis[5:8]))
            self.assertTrue(points[8] < points[6] if up else points[8] > points[6])
            self.assertTrue(points[8] < points[0] if up else points[8] > points[0])

    def test_factor_xd_standard_left_and_second_sequence_stages(self):
        """课67/71/78/81：保留标准旧侧，区分原邻笔条件与未知种子上下文。"""
        inputs = embedded_table('test_real_f1_originals.py', 'M3_FACTOR_F1_AUDIT')
        legacy = embedded_table('test_real_xd_f1.py', 'M3_FACTOR_XD_AUDIT')
        for value,wanted in ((inputs,'8100b6d1128eb2fcf38813678729051831b17798c33315bccef61f9629efd004'),
                             (legacy,'a5e29d244716a2147c97f5f6e83255ab8e9b8cdeac0fed3085926d674953901c')):
            blob = json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            self.assertEqual(hashlib.sha256(blob).hexdigest(),wanted)
        self.assertFalse(legacy['independent_theory_labels'])
        self.assertFalse(legacy['global_segmentation_independently_proven'])

        def groups(parts,indices,up):
            """整数区间顺序包含；旧侧初始方向显式给定，第二序列由相邻项建立。"""
            result = []
            for i in indices:
                low,high = min(parts[i][4:6]),max(parts[i][4:6])
                if result and (low <= result[-1][1] and high >= result[-1][2] or
                               low >= result[-1][1] and high <= result[-1][2]):
                    self.assertIsNotNone(up)
                    pick = max if up else min
                    ids,old_low,old_high = result[-1]
                    result[-1] = (ids+(i,),pick(low,old_low),pick(high,old_high))
                else:
                    if result:
                        up = high > result[-1][2]
                    result.append(((i,),low,high))
            return [(ids,(low,high)) for ids,low,high in result]

        # 调库前补充表：6条标准侧局部条件、1条raw-only、1条第二序列。
        # 起点是给定假设；此表不裁定完整候选生命周期或全局分界。
        sides = [
            ('2022-01-01-106',0,4,1,7,(1,3),(494283349820,612350382280),False),
            ('2022-01-01-106',5,7,2,19,(6,),(444731536860,537079010000),None),
            ('2022-01-01-106',8,16,1,19,(13,15),(511981860000,567165473420),True),
            ('2022-01-01-106',17,23,1,26,(20,22),(393345771840,437021692380),True),
            ('2022-01-01-81',0,12,1,15,(11,),(490900254000,546103945140),True),
            ('2022-01-01-81',13,17,1,20,(16,),(393345771840,444390336000),True),
            ('2022-04-15-106',0,16,1,19,(13,15),(393345771840,437021692380),True),
            ('2022-04-15-81',0,12,1,15,(11,),(393345771840,444390336000),True)]
        self.assertEqual(len(sides),sum(len(c['events']) for c in legacy['cases'].values()))
        supported = []
        for key,a,z,mode,proof,ids,left,wanted in sides:
            parts = inputs['cases'][key]['parts']
            up = parts[a][5] > parts[a][4]
            self.assertEqual(groups(parts,range(a+1,z,2),up)[-1],(ids,left))
            self.assertIn((a,z,mode,proof),[tuple(e[:4]) for e in legacy['cases'][key]['events']])
            if mode == 1:
                first = (min(parts[z+1][4:6]),max(parts[z+1][4:6]))
                protrudes = first[1] > left[1] if up else first[0] < left[0]
                self.assertEqual(protrudes,wanted)
                supported.append(protrudes)
                if wanted:
                    self.assertLessEqual(max(left[0],first[0]),min(left[1],first[1]))
                    reverse = parts[z+1:proof+1]
                    self.assertEqual(len(reverse),3)
                    self.assertLessEqual(max(min(p[4:6]) for p in reverse),min(max(p[4:6]) for p in reverse))
                    self.assertTrue(parts[proof][5] < parts[z+1][5] if up else parts[proof][5] > parts[z+1][5])
                    right = (min(parts[proof][4:6]),max(parts[proof][4:6]))
                    first_break = first[0] < left[0] if up else first[1] > left[1]
                    standard_fx = (all(first[k] > max(left[k],right[k]) for k in (0,1)) if up else
                                   all(first[k] < min(left[k],right[k]) for k in (0,1)))
                    self.assertTrue(first_break or standard_fx)
                else:
                    # BI1包含BI3后高点仍在；不能以较低原BI3直接证明标准顶。
                    self.assertEqual((key,a,z),('2022-01-01-106',0,4))
                    self.assertLess(max(parts[z-1][4:6]),first[1])
                    self.assertGreater(left[1],first[1])
        self.assertEqual((supported.count(True),supported.count(False)),(6,1))

        parts = inputs['cases']['2022-01-01-106']['parts']
        stages = [
            (11,115,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860))),False),
            (13,124,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,),(511981860000,567165473420))),False),
            (15,153,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15),(511981860000,567165473420))),False),
            (17,170,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15,17),(511981860000,577234450000))),False),
            (19,180,(((9,),(390391187680,433678752000)),((11,),(430365928200,470832572860)),((13,15,17),(511981860000,577234450000)),((19,),(407577716000,461988337200))),True)]
        self.assertEqual(parts[10][6],106)  # 第一序列底先到，不代替第二序列顶。
        for last,count,wanted,complete in stages:
            self.assertEqual(parts[last][6],count)
            current = groups(parts,range(9,last+1,2),None)
            self.assertEqual(current,list(wanted))
            tops = [i for i in range(1,len(current)-1)
                    if all(current[i][1][k] > max(current[i-1][1][k],current[i+1][1][k]) for k in (0,1))]
            self.assertEqual(bool(tops),complete)
            if complete:
                self.assertEqual([current[i][0] for i in range(tops[0]-1,tops[0]+2)],[(11,),(13,15,17),(19,)])

    def test_factor_xd_local_proofs_and_shared_second_feature(self):
        """核给定分界的原邻笔几何；标准旧侧与种子前提另核，不称完整证明。"""
        inputs = embedded_table('test_real_f1_originals.py','M3_FACTOR_F1_AUDIT')['cases']
        audit = embedded_table('test_real_xd_f1.py','M3_FACTOR_XD_AUDIT')
        self.assertFalse(audit['independent_theory_labels'])
        self.assertFalse(audit['global_segmentation_independently_proven'])
        totals = [0,0]
        for key,case in audit['cases'].items():
            self.assertEqual(len(case['events']),len(case['local_proofs']))
            rows = inputs[key]['parts']
            bounds = lambda i:(min(rows[i][4:6]),max(rows[i][4:6]))
            for event,proof in zip(case['events'],case['local_proofs']):
                a,z,mode,last,count,known = event
                self.assertEqual(proof['event'],[a,z,mode,last])
                self.assertEqual(rows[last][6],count)
                self.assertGreater(known[:10],rows[last][3])
                self.assertGreater(last,z)
                self.assertEqual(proof['initial_core'],[max(bounds(i)[0] for i in range(a,a+3)),
                                                        min(bounds(i)[1] for i in range(a,a+3))])
                if mode == 1:
                    reverse = [bounds(i) for i in range(z+1,last+1)]
                    self.assertEqual(last-z,3)
                    self.assertLessEqual(max(r[0] for r in reverse),min(r[1] for r in reverse))
                    self.assertEqual(proof['reverse_core'],[max(r[0] for r in reverse),min(r[1] for r in reverse)])
                    up = rows[a][5] > rows[a][4]
                    self.assertTrue(bounds(z+1)[1] > bounds(z-1)[1] if up else bounds(z+1)[0] < bounds(z-1)[0])
                    self.assertTrue(bounds(z+1)[0] <= bounds(z-1)[1] if up else bounds(z+1)[1] >= bounds(z-1)[0])
                    if up:
                        self.assertLess(rows[last][5],rows[z+1][5])
                    else:
                        self.assertGreater(rows[last][5],rows[z+1][5])
                else:
                    self.assertEqual(key,'2022-01-01-106')
                    self.assertEqual(bounds(6)[0]-bounds(8)[1],11052784860)
                    self.assertEqual(proof['gap_ticks'],11052784860)
                    self.assertFalse(proof['gap_unfilled_at_proof'])
                    self.assertGreaterEqual(max(bounds(i)[1] for i in range(9,last+1)),bounds(6)[0])
                    self.assertTrue(bounds(8)[0]<min(bounds(6)[0],bounds(10)[0]))
                    self.assertTrue(bounds(8)[1]<min(bounds(6)[1],bounds(10)[1]))
                    first,container,later = bounds(13),bounds(15),bounds(17)
                    self.assertTrue(first[0]>=container[0] and first[1]<=container[1])
                    merged = (max(first[0],container[0]),max(first[1],container[1]))
                    self.assertTrue(later[0]<=merged[0] and later[1]>=merged[1])
                    merged = (max(merged[0],later[0]),max(merged[1],later[1]))
                    self.assertEqual(proof['second_top'],[*bounds(11),*merged,*bounds(19)])
                    self.assertGreater(merged[0],max(bounds(11)[0],bounds(19)[0]))
                    self.assertGreater(merged[1],max(bounds(11)[1],bounds(19)[1]))
                totals[mode-1] += 1
        self.assertEqual(totals,[7,1])

    def test_xd_f1_lineage_third_table_uses_first_known_core_and_whole_return(self):
        """七个核心全部保留; 首回试破沿与重新离开分开, 不靠库输出反推预期。"""
        tree = ast.parse((ROOT / 'tests/test_real_xd_f1.py').read_text())

        def embedded(name):
            return next(ast.literal_eval(n.value) for n in tree.body
                        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and
                            t.id==name for t in n.targets))

        types,table = embedded('M3_XD_RECURSION_AUDIT'),embedded('M3_XD_THIRD_AUDIT')
        spec = importlib.util.spec_from_file_location('independent_xd_third',
                    ROOT / 'validation/tools/gen_real_f1_originals.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        self.assertEqual(set(table),set(types))
        totals = [0,0,0,0,0]
        for key,audit in sorted(types.items()):
            path = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(path),audit['source_sha256'])
            case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['parent_id'])
            f1 = []
            for row in audit['f1']:
                record = tool.move_record(case['units'],row)
                proof = case['units'][row[-1]]
                record.update(confirmed_raw_count=proof['confirmed_raw_count'],confirmed_dt=proof['confirmed_dt'])
                f1.append(record)
            self.assertEqual([(r[0],r[1],r[2]) for r in table[key]],
                             [(a,b,core) for move,spans in zip(audit['f2'],audit['f2_spans'])
                              for (a,b,_),core in zip(spans,move[5])])
            for start,formed,core,known,extended,expected,pending,failed in table[key]:
                zd,zg = core
                self.assertEqual(formed,start+2)
                self.assertEqual((max(r['low_ticks'] for r in f1[start:formed+1]),
                                  min(r['high_ticks'] for r in f1[start:formed+1])),core)
                self.assertEqual(max(r['confirmed_raw_count'] for r in f1[start:formed+1]),known)
                known_dt = max(r['confirmed_dt'] for r in f1[start:formed+1])
                self.assertEqual([i for i,_ in extended],list(range(formed+1,formed+1+len(extended))))
                for i,count in extended:
                    self.assertEqual(f1[i]['confirmed_raw_count'],count)
                    self.assertTrue(f1[i]['low_ticks']<=zg and f1[i]['high_ticks']>=zd)
                matches,breaches = [],[]
                for i in range(formed+1,len(f1)-1):
                    leave,pull = f1[i:i+2]
                    self.assertEqual((leave['end_dt'],leave['end_ticks']),
                                     (pull['start_dt'],pull['start_ticks']))
                    up = leave['end_ticks']>leave['start_ticks']
                    reverse_up = pull['end_ticks']>pull['start_ticks']
                    if leave['start_dt']<known_dt or leave['low_ticks']>zg or leave['high_ticks']<zd:
                        continue
                    if up==reverse_up or not (leave['end_ticks']>zg if up else leave['end_ticks']<zd):
                        continue
                    margin = pull['low_ticks']-zg if up else zd-pull['high_ticks']
                    count = max(known,leave['confirmed_raw_count'],pull['confirmed_raw_count'])
                    if margin<0:
                        breaches.append((i,i+1,count,margin))
                    else:
                        matches.append(('buy3' if up else 'sell3',i,i+1,pull['end_dt'],pull['end_ticks'],count,margin))
                self.assertEqual(matches[0] if matches else None,expected)
                self.assertEqual(tuple(breaches),failed)
                last = f1[-1]
                outside = last['end_ticks']>zg if last['end_ticks']>last['start_ticks'] else last['end_ticks']<zd
                waiting = (len(f1)-1 if not matches and last['start_dt']>=known_dt and
                           last['low_ticks']<=zg and last['high_ticks']>=zd and outside else None)
                self.assertEqual(waiting,pending)
                totals[0] += 1
                totals[1] += len(extended)
                totals[2] += expected is not None
                totals[3] += len(failed)
                totals[4] += pending is not None
        self.assertEqual(totals,[7,9,2,1,1])

    def test_complete_xd_f1_f2_table_has_independent_intersections_and_proofs(self):
        """AST读取同一冻结表; 独立核返回/反向中枢证明、F2延伸及开放尾部。"""
        source = ROOT / 'tests/test_real_xd_f1.py'
        table = next(ast.literal_eval(n.value) for n in ast.parse(source.read_text()).body
                     if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and
                         t.id=='M3_XD_RECURSION_AUDIT' for t in n.targets))
        tool = compiler()
        spec = importlib.util.spec_from_file_location('independent_xd_recursion',
                    ROOT / 'validation/tools/gen_real_f1_originals.py')
        arithmetic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(arithmetic)

        def touches(unit,core):
            return unit['low_ticks']<=core[1] and unit['high_ticks']>=core[0]

        def core_at(units,start):
            return (max(u['low_ticks'] for u in units[start:start+3]),
                    min(u['high_ticks'] for u in units[start:start+3]))

        total, opposite, completed = 0, [], []
        self.assertEqual(set(table),{'X1','Y1','S3','M1','M2'})
        for key,audit in sorted(table.items()):
            fixture = ROOT / 'tests/fixtures' / audit['fixture']
            self.assertEqual(tool.digest(fixture),audit['source_sha256'])
            case = next(c for c in json.loads(fixture.read_text())['cases'] if c['id']==audit['parent_id'])
            self.assertEqual((case['standard'],case['level']),('106','xd'))
            self.assertTrue(all(r['adj_factor']==1 for r in case['raw_rows']))
            units, records = case['units'], []
            rows = audit['f1']+(audit['tail'],)
            self.assertEqual(rows[0][0],0)
            self.assertEqual(rows[-1][1],len(units)-1)
            for left,right in zip(rows,rows[1:]):
                self.assertEqual(left[1]+1,right[0])
            for row in rows:
                a,z,kind,entry,triples,cores,proof = row
                record = arithmetic.move_record(units,row)
                if not triples:
                    self.assertEqual((kind,proof),('incomplete',None))
                    self.assertLess(z-a,2)
                    continue
                for j in range(a,triples[0]):
                    lo,hi = core_at(units,j)
                    self.assertGreater(lo,hi)
                for n,(j,core) in enumerate(zip(triples,cores)):
                    stop = triples[n+1]+3 if n+1<len(triples) else z+1
                    self.assertTrue(all(not touches(u,core) for u in units[j+3:stop]))
                if proof is None:
                    continue
                if proof==z+1:
                    self.assertTrue(touches(units[proof],cores[-1]))
                else:
                    self.assertEqual(proof,z+3)
                    new = core_at(units,z+1)
                    self.assertLessEqual(*new)
                    self.assertTrue(new[0]>cores[-1][1] or new[1]<cores[-1][0])
                    direction = 'up' if new[0]>cores[-1][1] else 'down'
                    self.assertNotEqual(direction,entry)
                    self.assertTrue(all(not touches(u,cores[-1]) for u in units[z+1:proof+1]))
                    self.assertEqual({u['confirmed_raw_count'] for u in units[z+1:proof+1]},{4727})
                    opposite.append(key)
                record.update(confirmed_raw_count=units[proof]['confirmed_raw_count'])
                records.append(record)
            total += len(records)
            self.assertEqual(len(audit['f2']),len(audit['f2_spans']))
            for row,spans in zip(audit['f2'],audit['f2_spans']):
                record = arithmetic.move_record(records,row)
                a,z,_,_,_,cores,proof = row
                for j in range(a,spans[0][0]):
                    lo,hi = core_at(records,j)
                    self.assertGreater(lo,hi)
                for i,((start,formed,extended),core) in enumerate(zip(spans,cores)):
                    self.assertEqual(formed,start+2)
                    self.assertTrue(all(touches(u,core) for u in records[formed+1:extended+1]))
                    if i+1<len(spans):
                        new_start,new_formed,_ = spans[i+1]
                        self.assertEqual(new_start,extended+1)
                        self.assertTrue(all(not touches(u,core) for u in records[new_start:new_formed+1]))
                leave = spans[-1][2]+1
                self.assertTrue(all(not touches(u,cores[-1]) for u in records[leave:z+1]))
                if proof is None:
                    self.assertLess(z-leave+1,3)
                else:
                    self.assertEqual(proof,z+1)
                    self.assertTrue(touches(records[proof],cores[-1]))
                    self.assertEqual(records[proof]['confirmed_raw_count'],3323)
                    self.assertEqual((record['low_ticks'],record['high_ticks']),(666,1113))
                    self.assertEqual(records[proof]['high_ticks'],1202)
                    completed.append(key)
        self.assertEqual((total,opposite,completed),(38,['M2'],['M1']))

    def test_frozen_sources_and_independent_rebuild(self):
        """原始包与人工表保真；重复编译逐字节一致且不能覆盖证据。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        self.assertEqual(labels['manual_sha256'], tool.digest(MANUAL))
        for case in labels['cases']:
            packet = ROOT / 'validation' / case['source']['packet']
            self.assertEqual(case['source']['sha256'], tool.digest(packet))
            data = json.loads(packet.read_text())
            self.assertEqual(data['rows'], case['raw_rows'])
            self.assertEqual(data['manifest_sha256'], case['source']['dataset_manifest_sha256'])
        for path in (TOOL, ROOT / 'validation/tools/gen_real_f1_originals.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                self.assertTrue(all(name.split('.')[0] != 'chan' for name in names))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'labels.json'
            command = [sys.executable, str(TOOL), '--manual', str(MANUAL),
                       '--packets', str(ROOT / 'validation'), '--output', str(output)]
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('拒绝覆盖', run.stderr)
            self.assertEqual(output.read_bytes(), FIXTURE.read_bytes())

    def test_reject_corrupt_manual_ranges_and_premature_proof(self):
        """负索引/截短三段/空交集/提前证明不得编译成理论真值。"""
        tool = compiler()
        labels = json.loads(FIXTURE.read_text())
        manual = json.loads(MANUAL.read_text())
        fixed = labels['cases'][0]['observations'][str(len(labels['cases'][0]['raw_rows']))]['fixed_bis']
        changes = [
            ('negative', lambda c: c['xd_events'][0].__setitem__(0, -1)),
            ('boolean', lambda c: c['xd_events'][0].__setitem__(0, True)),
            ('early_xd', lambda c: c['xd_events'][0].__setitem__(3, 2)),
            ('missing_xd', lambda c: c['xd_events'][0].__setitem__(3, len(fixed))),
            ('short_triple', lambda c: c['f1_spec'][4].__setitem__(1, 5)),
            ('outside_triple', lambda c: c['f1_spec'][4].__setitem__(0, -1)),
            ('empty_core', lambda c: c['f1_spec'][5].__setitem__(0, [843, 842])),
            ('early_f1', lambda c: c['f1_spec'].__setitem__(6, 5)),
            ('missing_f1', lambda c: c['f1_spec'].__setitem__(6, 7)),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                case = json.loads(json.dumps(manual['cases'][0]))
                mutate(case)
                with self.assertRaises(ValueError):
                    tool.validate_manual(case, fixed)


if __name__ == '__main__':
    unittest.main()
