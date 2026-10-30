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


# 本表仅承接既有M2/Y1有限分界；活动证据价、固定证据价和前驱资格分列。
M3_CONTEXT_COUNTEREXAMPLES_AUDIT = {
    'M2': dict(seed=201,events=((201,227,2,241),(228,238,1,255),(239,257,1,260)),
               owner=239,first=248,predecessor=(228,238,1,255),cancel=255,
               false_following=(248,252,1,255),raw_window=(4016,4774),
               current_counts=(4554,4716,4767),fixed_counts=(4563,4727,4774),
               current_cancel=4716,fixed_cancel=4727,
               current_proof_prices=(1150,1170,1146),fixed_proof_prices=(1150,1181,1146),
               current_proof_dates=('2026-06-25 14:40:00','2026-07-01 10:20:00','2026-07-02 10:30:00'),
               fixed_proof_dates=('2026-06-25 14:40:00','2026-07-01 10:50:00','2026-07-02 10:30:00')),
    'Y1': dict(seed=221,events=((221,225,1,228),(226,240,1,243)),
               owner=226,first=231,predecessor=(221,225,1,228),cancel=238,
               false_following=(231,235,1,238),raw_window=(2392,2580),
               current_counts=(2434,2568),fixed_counts=(2440,2580),
               current_cancel=2507,fixed_cancel=2512,
               current_proof_prices=(8351,8362),fixed_proof_prices=(8351,8362),
               current_proof_dates=('2026-07-15 13:35:00','2026-07-20 11:00:00'),
               fixed_proof_dates=('2026-07-15 13:35:00','2026-07-20 11:00:00')),
}


def manual_feature_nodes(parts, indices, initial_up):
    """课67/78整数标准元素；仅处理指定同一侧，不搜索分界或调用包算法。"""
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


def manual_feature_fractal(nodes, top):
    """课67严格顶/底；反向形状不代替本次所需分型。"""
    return len(nodes)==3 and all(nodes[1][j]>max(nodes[0][j],nodes[2][j]) if top else
                                nodes[1][j]<min(nodes[0][j],nodes[2][j]) for j in (0,1))


def manual_gap_lifecycle(parts, owner, first, observed):
    """课67/71/78给定正缺口的独立状态证书，不寻找或发布自然XD。

    逐前缀重算标准元素，固定原缺口和原首起价；第一分型尚未形成、
    等待所需第二分型、严格撤销与确认分别返回。同笔先核所需第二
    分型，后核首起突破。observed是待检验分界的证据前缀，不是全窗末笔。
    """
    if not owner+3 <= first <= observed < len(parts):
        raise ValueError('须显式给定旧起点、首反向笔和可见证据前缀')
    up = parts[owner]['direction'] == 'up'
    original = parts[first]
    left = manual_feature_nodes(parts, range(owner+1,first,2), up)[-1]
    gap = original['low_ticks']-left[1] if up else left[0]-original['high_ticks']
    record = dict(original_gap_ticks=gap, first_fractal_proof_bi=None,
                  second_fractal_proof_bi=None, strict_revocation_bi=None,
                  state='not_gap', last_old=left)
    if gap <= 0:
        return record
    record['state'] = 'await_first'
    for stop in range(first+1,observed+1):
        right = manual_feature_nodes(parts, range(first,stop+1,2), up)
        second = manual_feature_nodes(parts, range(first+1,stop+1,2), not up)
        if (record['first_fractal_proof_bi'] is None and len(right)>=2 and
                manual_feature_fractal([left]+right[:2],up)):
            record['first_fractal_proof_bi'] = stop
        revokes = (parts[stop]['direction']!=original['direction'] and
                   (parts[stop]['end_ticks']>original['start_ticks'] if up else
                    parts[stop]['end_ticks']<original['start_ticks']))
        if revokes:
            record['strict_revocation_bi'] = stop
        if (record['first_fractal_proof_bi'] is not None and
                manual_feature_fractal(second[-3:],not up)):
            record.update(state='confirmed',second_fractal_proof_bi=stop)
            return record
        if revokes:
            record['state'] = 'revoked'
            return record
    if record['first_fractal_proof_bi'] is not None:
        record['state'] = 'waiting'
    return record


def manual_xd_certificate_ready(parts, event):
    """只验给定分界的整数证书，不搜索XD；课67包含与课71原首笔选向分列。"""
    a, z, mode, proof = event
    if len(parts) <= proof:
        return False
    up = parts[a]['direction'] == 'up'
    turn = z + 1

    for start in (a,turn):
        group = parts[start:start+3]
        if len(group)!=3 or max(p['low_ticks'] for p in group)>min(p['high_ticks'] for p in group):
            return False
    left = manual_feature_nodes(parts,range(a+1,turn,2),up)[-1]
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
    right = manual_feature_nodes(parts,range(turn,proof+1,2),up)
    if gap<=0 or len(right)<2 or not manual_feature_fractal([left]+right[:2],up):
        return False
    second = manual_feature_nodes(parts,range(turn+1,proof+1,2),not up)
    # 同一可用BI快照的第二分型可与新极值同批；不声称原始price先后已证。
    return manual_feature_fractal(second[-3:],not up) and (canceled is None or canceled>=proof)


def manual_natural_reaction_state(parts, seen, observed, owner, first, predecessor, reaction,
                                  origin=None):
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
    proposed_boundary=(起笔,假设分界后起笔)只绑定待证前驱；即使只含
    一笔也不能省略成未知前史，更不能携带已发布计数冒充完成线段。
    origin为另行声明的起点前提，不能和前驱证书混用。anchor绑定
    (owner,方向,起价)，available_count与seen使用同一时钟。显式
    no_prior_history仅适用于输入首笔，声明可见后可代替不存在的前驱；
    given_recent只给出选定边界，不证明前驱破坏。两者都不由缺少
    前史数据推断，条件的真实性由输入方另证。此函数不生成XD链。
    """
    if len(parts)!=len(seen) or not parts or any(a>b for a,b in zip(seen,seen[1:])):
        raise ValueError('可见固定笔与到达计数须逐项对应且有序')
    if seen[-1]>observed or owner<0 or first<owner+3 or first>=len(parts):
        raise ValueError('只允许当前观察前缀内的首反向笔')
    if parts[owner]['direction']==parts[first]['direction']:
        raise ValueError('首反向笔须与原段反向')
    qualification, identity, prior_count = 'unknown', None, None
    origin_status, origin_identity = None, None
    if origin is not None:
        if (not isinstance(origin,dict) or
                set(origin)!=set(('basis','anchor','available_count'))):
            raise ValueError('起点前提须仅含basis/anchor/available_count')
        if predecessor is not None:
            raise ValueError('起点前提不能代替或混入前驱证书')
        basis,anchor,count = origin['basis'],origin['anchor'],origin['available_count']
        if basis not in ('unknown','no_prior_history','given_recent'):
            raise ValueError('起点前提须区分未知、无前史和给定近期起点')
        if (not isinstance(anchor,(list,tuple)) or len(anchor)!=3 or
                isinstance(anchor[0],bool) or not isinstance(anchor[0],int) or
                isinstance(anchor[2],bool) or
                tuple(anchor)!=(owner,parts[owner]['direction'],parts[owner]['start_ticks'])):
            raise ValueError('起点前提与owner方向及起价不一致')
        if basis=='unknown':
            if count is not None:
                raise ValueError('未知前史不能携带已知计数')
            origin_status = 'unknown'
        else:
            if isinstance(count,bool) or not isinstance(count,int) or count<0:
                raise ValueError('起点前提到达计数须为非负整数')
            origin_status = 'visible' if count<=observed else 'waiting'
        if basis=='no_prior_history':
            if owner!=0:
                raise ValueError('无前史仅可声明输入首笔，不可抹去已给前史')
            qualification,prior_count = origin_status,count
        origin_identity = (basis,tuple(anchor),count)
    if predecessor is not None:
        if 'proposed_boundary' in predecessor:
            a,stop = predecessor['proposed_boundary']
            if (a<0 or stop<=a or stop!=owner or predecessor.get('event') is not None or
                    predecessor.get('published_count') is not None):
                raise ValueError('待证前驱仅绑定衔接边界，不能声明完成或发布')
            identity = ('provisional',a,stop)
            qualification = 'waiting'
        else:
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
    result = dict(qualification=qualification,state=state,local_proof=local_proof,
                  local_count=local_count,published_count=published,predecessor=identity)
    if origin is not None:
        result.update(origin=origin_identity,origin_status=origin_status)
    return result


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
    def _m2_joined_source(self):
        audit=embedded_table('test_real_xd_f1.py','M3_M2_JOINED_ROLE_AUDIT')
        head=embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')['M2_recent16']
        self.assertEqual(audit['head_certificate_sha256'],head['certificate_sha256'])
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        tool=compiler();_,_,bis=tool.foundation(case['raw_rows'][:2476],'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
        parts=tool.components(case['raw_rows'][:2476],bis[:-1],None)
        units=tool.xd_records(parts,audit['events'])
        names=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual([tuple(u[k] for k in names) for u in units],[u[:9] for u in audit['units']])
        return audit,case,parts,units

    @staticmethod
    def _m2_joined_given_ready(parts,audit):
        """只核已声明的两组R/S/D和局部证书，不搜索全链自然分界。"""
        ready=[manual_xd_certificate_ready(parts,e) for e in audit['events']]
        for index,first,s,reaction in ((1,38,audit['successors'][0],audit['reactions'][0]),
                                      (10,93,audit['successors'][1],audit['reactions'][1])):
            good=manual_xd_certificate_ready(parts,reaction)
            if good:
                stop=reaction[3];r=parts[first];up=r['direction']=='up'
                good=(all(parts[i]['end_ticks']<=r['end_ticks'] if up else parts[i]['end_ticks']>=r['end_ticks']
                          for i in range(first+2,stop+1,2)) and
                      all(parts[i]['end_ticks']>=r['start_ticks'] if up else parts[i]['end_ticks']<=r['start_ticks']
                          for i in range(first+1,stop+1,2)))
            ready[index]=good
            ready[index+1]=ready[index+1] and good and manual_xd_certificate_ready(parts,s)
        return ready

    def test_m2_joined_seed16_reaction94_and_completed_successor97_bind_the_new_bridge(self):
        """87处不能用93..97/proof102；相邻S94与完整D97共同支持93..103。"""
        audit,case,parts,units=self._m2_joined_source()
        seen=case['foundation']['bis_confirmed_raw_count']
        bridge=dict(owner=90,first=93,old_boundary=audit['events'][10],reaction=audit['reactions'][1],
                    successor=audit['successors'][1],extended=audit['events'][11])
        parent=dict(event=audit['events'][9],published_count=seen[92])
        for mirrored in (False,True):
            supplied=parts if not mirrored else [dict(u,direction='down' if u['direction']=='up' else 'up',
                 start_ticks=20000-u['start_ticks'],end_ticks=20000-u['end_ticks'],
                 low_ticks=20000-u['high_ticks'],high_ticks=20000-u['low_ticks']) for u in parts]
            left=manual_feature_nodes(supplied,range(91,93,2),mirrored)[-1]
            first=supplied[93]
            self.assertTrue(first['high_ticks']>left[1] if mirrored else first['low_ticks']<left[0])
            self.assertLessEqual(max(left[0],first['low_ticks']),min(left[1],first['high_ticks']))
            pending=manual_natural_reaction_state(supplied[:103],seen[:103],seen[102],90,93,parent,None)
            self.assertEqual(pending['state'],'pending')
            self.assertTrue(manual_xd_certificate_ready(supplied[:103],(93,97,1,102)))
            self.assertFalse(manual_xd_certificate_ready(supplied[:103],audit['reactions'][1]))
            self.assertIsNone(manual_natural_successor_certificate(supplied[:104],seen[:104],seen[103],bridge,parent))
            result=manual_natural_successor_certificate(supplied[:107],seen[:107],seen[106],bridge,parent)
            self.assertEqual((result['local_proof'],result['successor_proof'],result['published_count']),
                             (106,106,seen[106]))
            for first in (100,102):
                left=manual_feature_nodes(supplied,range(98,first,2),not mirrored)[-1]
                self.assertTrue(supplied[first]['low_ticks']>=left[0] if mirrored else
                                supplied[first]['high_ticks']<=left[1])
        tool=compiler()
        for spec in audit['f1']+(audit['tail'],):tool.move_record(units,spec)
        self.assertEqual([(min(u['low_ticks'] for u in units[s[0]:s[1]+1]),
                           max(u['high_ticks'] for u in units[s[0]:s[1]+1])) for s in audit['f1']],
                         [(1105,1200),(1025,1140),(1010,1056)])

    def test_m2_joined_earlier_revocations_and_equal_first_start_preserve_qualified111_scope(self):
        """更早gap/首反向身份先撤销；115等1079不撤销114，111资格只限已接通祖先。"""
        audit,_,parts,_=self._m2_joined_source()
        for owner,first,cancel,kind in audit['earlier_revoked']:
            r=parts[first];up=r['direction']=='up'
            observed=next(i for i in range(first+1,cancel+1,2) if
                          (parts[i]['end_ticks']<r['start_ticks'] if up else parts[i]['end_ticks']>r['start_ticks']))
            self.assertEqual(observed,cancel)
            if kind=='gap':self.assertEqual(manual_gap_lifecycle(parts,owner,first,cancel)['state'],'revoked')
        self.assertEqual(audit['events'][11:14],((93,103,1,106),(104,110,1,113),(111,113,1,116)))
        self.assertTrue(all(manual_xd_certificate_ready(parts,e) for e in audit['events'][11:14]))
        self.assertTrue(audit['natural111_qualified_in_seed16_chain'])
        self.assertFalse(M3_M2_GIVEN_PROOFS_AUDIT['natural_start111_proven'])
        self.assertEqual(M3_M2_GIVEN_PROOFS_AUDIT['parent_events'][1],(108,110,1,113))
        self.assertNotIn(M3_M2_GIVEN_PROOFS_AUDIT['parent_events'][1],audit['events'])
        values=[parts[0]['start_ticks']]+[u['end_ticks'] for u in parts[:117]]
        self.assertEqual((parts[114]['start_ticks'],parts[115]['end_ticks']),(1079,1079))
        for delta in (-1,0,1):
            changed=list(values);changed[116]=1079+delta
            for mirrored in (False,True):
                variant=self._natural_parts([20000-v for v in changed] if mirrored else changed)
                self.assertEqual(manual_xd_certificate_ready(variant,(111,113,1,116)),delta<=0)

    def test_m2_joined_actual_local_and_serial_clocks_keep_proof_prices_and_old_head(self):
        """两合同首达前一行/本行重算；65仍等父段，111活动1072不回填固定1064。"""
        audit,case,_,_=self._m2_joined_source();tool=compiler()
        head=embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')['M2_recent16']
        self.assertEqual(audit['events'][:6],head['events'])
        self.assertEqual(audit['current_counts'][:6],head['current_counts'])
        fixed_local=tuple(u[-2] for u in audit['units']);fixed=tuple(u[-1] for u in audit['units'])
        self.assertEqual(fixed[:6],head['fixed_counts'])
        counts=sorted({n for at in audit['current_local_counts']+audit['current_counts']+fixed_local+fixed for n in (at-1,at)}|{2476})
        for count in counts:
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
            for contract,bs,local,published in (('current',bis,audit['current_local_counts'],audit['current_counts']),
                                               ('fixed',bis[:-1],fixed_local,fixed)):
                parts=tool.components(rows,bs,None);ready=self._m2_joined_given_ready(parts,audit)
                self.assertEqual(ready,[count>=at for at in local])
                size=next((i for i,ok in enumerate(ready) if not ok),14)
                self.assertEqual(size,sum(at<=count for at in published))
                for label,firsts in (('local',local),('publication',published)):
                    for i,at in enumerate(firsts):
                        if count==at:
                            proof=audit['events'][i][3];p=parts[proof]
                            self.assertEqual((p['end_ticks'],p['end_dt'],contract=='current' and proof==len(parts)-1),
                                             audit[label+'_proofs'][contract][i])
        self.assertEqual((fixed[12],fixed[13]),(2365,2437))
        self.assertLess(fixed[13],2476)
        self.assertEqual((audit['publication_proofs']['current'][13][0],
                          audit['publication_proofs']['fixed'][13][0]),(1072,1064))

    def _y1_recursive_source(self):
        head,case,units,clock=self._y1_three_unit_roles()
        audit=embedded_table('test_real_xd_f1.py','M3_Y1_RECURSIVE_CONSUMERS_AUDIT')
        self.assertEqual(audit['source_sha256'],head['source_sha256'])
        self.assertEqual(audit['fixed_role_certificate_sha256'],head['fixed_role_certificate_sha256'])
        self.assertEqual(audit['current_clock_certificate_sha256'],clock['certificate_sha256'])
        self.assertEqual(audit['head_role_certificate_sha256'],head['certificate_sha256'])
        return audit,case,units,clock

    def test_y1_recursive_declared_centers_extensions_and_external_proofs_use_integer_ranges(self):
        """有限角色不搜索切点；逐个核形成、延伸、首次全离开与反向三段外证。"""
        audit,_,units,_=self._y1_recursive_source()
        tool=compiler()
        for j,(a,formed,last,zd,zg) in enumerate(audit['centers']):
            self.assertEqual(formed,a+2)
            self.assertEqual((max(u['low_ticks'] for u in units[a:formed+1]),
                              min(u['high_ticks'] for u in units[a:formed+1])),(zd,zg))
            self.assertTrue(all(u['low_ticks']<=zg and u['high_ticks']>=zd for u in units[formed+1:last+1]))
            self.assertTrue(units[last+1]['high_ticks']<zd or units[last+1]['low_ticks']>zg)
            if j and j!=5:
                for k in range(audit['centers'][j-1][2]+1,a):
                    self.assertGreater(max(u['low_ticks'] for u in units[k:k+3]),
                                       min(u['high_ticks'] for u in units[k:k+3]))
        first,second=[tool.move_record(units,s) for s in audit['completed']]
        self.assertEqual((first['seg_start'],first['seg_end'],first['proof_unit'],
                          first['low_ticks'],first['high_ticks']),(0,30,33,8224,9933))
        self.assertEqual((second['seg_start'],second['seg_end'],second['proof_unit']),(31,37,38))
        self.assertGreater(audit['centers'][5][3],audit['centers'][4][4])
        self.assertTrue(units[38]['low_ticks']<=8605 and units[38]['high_ticks']>=8551)
        self.assertEqual((first['end_dt'],second['start_dt']),(units[30]['end_dt'],units[31]['start_dt']))
        # 第一完成项最后两枢的反向回试尾为20/30；c=[31,31)为空。
        tails=[]
        for a,formed,last,_,_ in audit['centers'][3:5]:
            tails.append(next(i for i in range(last,formed-1,-1) if units[i]['direction']=='up'))
        self.assertEqual(tails,[20,30])
        self.assertEqual(tuple(range(tails[0]+1,audit['centers'][4][0])),audit['completed_reference'])
        self.assertEqual(tuple(range(tails[1]+1,first['seg_end']+1)),audit['completed_leave'])

    def test_y1_recursive_open_candidate_and_skipped_prefix_roles_are_distinct(self):
        """手工范围上重算比较腿与波动；开放新低未知不是负标签，力度未参与。"""
        audit,_,units,_=self._y1_recursive_source()
        found=[]
        for size in range(1,40):
            cs=([c for c in audit['centers'][:5] if c[1]<size] if size<34
                else [audit['centers'][5]] if size<39 else [])
            spans=[(a,f,min(last,size-1)) for a,f,last,_,_ in cs]
            reason='not_two_separated_centers';candidate=None
            if size<34 and len(spans)>=2:
                previous,last=spans[-2:]
                ends=[next((i for i in range(z,f-1,-1) if units[i]['direction']=='up'),None)
                      for a,f,z in (previous,last)]
                reason='no_comparable_center_tail'
                if all(v is not None for v in ends):
                    reference=tuple(range(ends[0]+1,last[0]));leave=tuple(range(ends[1]+1,size))
                    reason='no_compare_legs'
                    if reference and leave:
                        p=units[previous[0]:ends[0]+1];c=units[last[0]:ends[1]+1]
                        reason='center_waves_overlap'
                        if max(u['high_ticks'] for u in c)<min(u['low_ticks'] for u in p):
                            made=min(units[i]['low_ticks'] for i in leave)<min(u['low_ticks'] for u in units[:ends[1]+1])
                            third=any(units[i]['direction']=='up' for i in leave)
                            candidate=(size,reference,leave,tuple(cs[-1][-2:]),True if made else None,True if third else None)
            if candidate:found.append(candidate)
            else:self.assertIn(size,audit['open_skip_sizes'][reason])
        self.assertEqual(tuple(found),audit['candidates'])
        self.assertEqual([s for s,_,_,_,made,_ in found if made is None],[20,22,23])
        self.assertEqual(audit['final_first_exclusions'],('no_directional_compare_legs','not_trend'))

    def test_y1_recursive_actual_raw_boundaries_do_not_observe_transient_batch_sizes(self):
        """每个真实首达前一行/本行重建基础；同批10/24及fixed的12不伪造。"""
        audit,case,units,clock=self._y1_recursive_source();tool=compiler()
        role=embedded_table('test_real_xd_f1.py','M3_Y1_JOINED_ROLE_AUDIT')
        for contract in ('current','fixed'):
            counts=clock['published_counts'] if contract=='current' else tuple(u['confirmed_raw_count'] for u in units)
            observed=[]
            for count in sorted({n for at in counts for n in (at-1,at)}|{2793}):
                rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
                parts=tool.components(rows,bis if contract=='current' else bis[:-1],None)
                ready=self._y1_current_given_ready(parts,role['events'])
                size=next((i for i,ok in enumerate(ready) if not ok),39)
                self.assertEqual(size,sum(at<=count for at in counts))
                actual=tool.xd_records(parts,role['events'][:size])
                for spec in audit['completed']:
                    if spec[-1]<size:self.assertEqual(tool.move_record(actual,spec),tool.move_record(units,spec))
                if count in counts:observed.append(size)
            self.assertNotIn(10,observed);self.assertNotIn(24,observed)
            if contract=='fixed':self.assertNotIn(12,observed)
            candidate_sizes={c[0] for c in audit['candidates']}
            expected=tuple((n,sum(at<=n for at in counts)) for n in sorted(set(counts))
                           if sum(at<=n for at in counts) in candidate_sizes)
            self.assertEqual(expected,audit['arrivals'][contract]['candidate_raw'])
            self.assertEqual(tuple(counts[s[-1]] for s in audit['completed']),audit['arrivals'][contract]['completed_raw'])
            self.assertEqual(tuple(sum(at<=counts[s[-1]] for at in counts) for s in audit['completed']),
                             audit['arrivals'][contract]['evidence_sizes'])

    def _y1_three_unit_roles(self):
        role,case,_,units,_=self._joined_y1_role_source()
        audit=embedded_table('test_real_xd_f1.py','M3_Y1_HEAD_ROLE_AUDIT')
        clock=embedded_table('test_real_xd_f1.py','M3_Y1_CURRENT_CLOCK_AUDIT')
        self.assertEqual(audit['source_sha256'],role['fixture_sha256'])
        self.assertEqual(audit['fixed_role_certificate_sha256'],role['certificate_sha256'])
        self.assertEqual(audit['current_clock_certificate_sha256'],clock['certificate_sha256'])
        units=[dict(u,confirmed_raw_count=row[-1]) for u,row in zip(units,role['units'])]
        return audit,case,units,clock

    def test_y1_general_three_unit_roles_keep_legacy_pair_contract_and_mirror_bounds(self):
        """课20完整公式显式选用；内部低9441不改价，核心下沿由中间9445约束。"""
        audit,_,units,_=self._y1_three_unit_roles()
        tool=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        spec=audit['roles']['B']
        result=tool.validate_zhongshu('B',spec,units)
        self.assertEqual((result['zd'],result['zg'],result['core_basis']),(9445,9540,'three_units'))
        with self.assertRaisesRegex(ValueError,'首对核心与声明不一致'):
            tool.validate_zhongshu('B',dict(spec,core_basis='same_direction_pair'),units)
        with self.assertRaisesRegex(ValueError,'中间单元未覆盖核心'):
            tool.validate_zhongshu('B',dict(spec,core_basis='same_direction_pair',zd=9441),units)
        with self.assertRaisesRegex(ValueError,'三段核心与声明不一致'):
            tool.validate_zhongshu('B',dict(spec,zd=9441),units)
        with self.assertRaisesRegex(ValueError,'core_basis无效'):
            tool.validate_zhongshu('B',dict(spec,core_basis='automatic'),units)
        for middle_low,expected in ((9440,9441),(9441,9441),(9442,9442),(9445,9445)):
            changed=[dict(u) for u in units]
            changed[7]['low_ticks']=middle_low
            for mirror in (False,True):
                supplied=[dict(u) for u in changed]
                declared=dict(spec,zd=expected)
                if mirror:
                    for u in supplied:
                        u['low_ticks'],u['high_ticks']=20000-u['high_ticks'],20000-u['low_ticks']
                        u['direction']='down' if u['direction']=='up' else 'up'
                    declared.update(zd=20000-spec['zg'],zg=20000-expected,
                                    dd=20000-spec['gg'],gg=20000-spec['dd'])
                checked=tool.validate_zhongshu('B',declared,supplied)
                self.assertEqual((checked['zd'],checked['zg']),(declared['zd'],declared['zg']))

    def test_y1_new_head_bc_has_no_return_proof_and_lower_center_waves_overlap(self):
        """独立角色只证头部条件划分，c9创新低但proof10差31格，不是新一类裁定。"""
        audit,case,units,_=self._y1_three_unit_roles()
        tool=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        given=dict(case,trend=dict(direction='down',status='ongoing'),roles=audit['roles'])
        centers=tool.validate_roles(given,units)
        self.assertEqual([(centers[n]['zd'],centers[n]['zg']) for n in ('A','B','C')],
                         [(9714,9906),(9445,9540),(9266,9414)])
        self.assertEqual((centers['A']['closed_by'],centers['B']['closed_by'],centers['C']['closed_by']),(6,10,16))
        self.assertEqual((audit['roles']['b']['unit'],audit['roles']['c']['unit']),(5,9))
        B,C=centers['B'],centers['C']
        self.assertEqual((B['zd']-C['zg'],C['gg']-B['dd']),(31,82))
        self.assertEqual((min(u['low_ticks'] for u in units[:9]),units[9]['low_ticks']),(9332,9108))
        self.assertEqual([i for i in range(10,39) if units[i]['low_ticks']<=B['zg'] and units[i]['high_ticks']>=B['zd']],[])
        forced=dict(given,trend=dict(direction='down',status='completed'),
                    roles=dict(audit['roles'],proof=dict(unit=10)))
        with self.assertRaisesRegex(ValueError,'证明段须为c后首个触核心单元'):
            tool.validate_roles(forced,units)
        first=compiler(ROOT/'validation/tools/gen_real_first_point.py')
        with self.assertRaisesRegex(ValueError,'一类裁定仅施于完成严格趋势'):
            first.derive_first_point(given,units,centers,case['raw_rows'],'5m',[],[],[],[])
        self.assertEqual((case['first_point']['reason'],case['second_point']['premise']['category']),
                         ('no_new_extreme','minor_to_major'))

    def test_y1_head_role_ledger_keeps_actual_batches_and_general_core_identity(self):
        """角色台账按组成发布；C形成/延伸/封口分开，不把后来封口当即时回B。"""
        audit,case,units,clock=self._y1_three_unit_roles()
        tool=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        given=dict(trend=dict(direction='down',status='ongoing'),roles=audit['roles'])
        centers=tool.validate_roles(given,units)
        ledger=tool.derive_ledger(audit['roles'],centers)
        self.assertEqual(ledger,[[name,i] for name,i,_ in audit['ledger']['fixed']])
        reference=compiler()
        events=embedded_table('test_real_xd_f1.py','M3_Y1_JOINED_ROLE_AUDIT')['events']
        for contract in ('current','fixed'):
            counts=(clock['published_counts'] if contract=='current' else tuple(u['confirmed_raw_count'] for u in units))
            self.assertEqual(tuple((name,i,counts[i]) for name,i in ledger),audit['ledger'][contract])
            for count in sorted({n for _,_,at in audit['ledger'][contract] for n in (at-1,at)}):
                rows=case['raw_rows'][:count]
                _,_,bis=reference.foundation(rows,'106')
                parts=reference.components(rows,bis if contract=='current' else bis[:-1],None)
                # 组成发布沿用已独立验收的链门控，证明价仍从当前前缀取。
                ready=self._y1_current_given_ready(parts,events)
                size=next((i for i,ok in enumerate(ready) if not ok),39)
                self.assertEqual(size,sum(at<=count for at in counts),(contract,count))
                actual_units=reference.xd_records(parts,events[:size])
                for name in ('A','B','C'):
                    spec=audit['roles'][name];i=spec['zn'][0]
                    if size>i+2:
                        core=(max(u['low_ticks'] for u in actual_units[i:i+3]),min(u['high_ticks'] for u in actual_units[i:i+3]))
                        self.assertEqual(core,(spec['zd'],spec['zg']))

    def _y1_current_clock_source(self):
        role,case,_,units,_=self._joined_y1_role_source()
        clock=embedded_table('test_real_xd_f1.py','M3_Y1_CURRENT_CLOCK_AUDIT')
        self.assertEqual(clock['source_sha256'],role['fixture_sha256'])
        self.assertEqual(clock['fixed_role_certificate_sha256'],role['certificate_sha256'])
        return role,clock,case,units

    @staticmethod
    def _y1_current_given_ready(parts,events):
        """给定39段的局部准入；头部R/S/D复用已裁定证书，不搜索自然分界。"""
        ready=[manual_xd_certificate_ready(parts,e) for e in events]
        head=M3_NATURAL_SUCCESSOR_AUDIT['Y1']
        s,d=head['reaction'],head['successor']
        s_ready=manual_xd_certificate_ready(parts,s)
        if len(parts)>s[3] and s_ready:
            first=head['first']
            r=parts[first]
            up=r['direction']=='up'
            unselected=all(parts[i]['end_ticks']<=r['end_ticks'] if up else
                           parts[i]['end_ticks']>=r['end_ticks'] for i in range(first+2,s[3]+1,2))
            unbroken=all(parts[i]['end_ticks']>=r['start_ticks'] if up else
                         parts[i]['end_ticks']<=r['start_ticks'] for i in range(first+1,s[3]+1,2))
            ready[1]=ready[1] or (unselected and unbroken)
        ready[2]=ready[2] and s_ready and manual_xd_certificate_ready(parts,d)
        return ready

    def test_y1_current39_actual_local_and_publication_boundaries_use_prefix_prices(self):
        """每段局部和公开首达各核前一行/本行；活动证明版本不按固定计数推算。"""
        role,clock,case,units=self._y1_current_clock_source()
        tool=compiler()
        counts=sorted({n for at in clock['local_counts']+clock['published_counts'] for n in (at-1,at)})
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        for count in counts:
            rows=case['raw_rows'][:count]
            _,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
            parts=tool.components(rows,bis,None)
            local=self._y1_current_given_ready(parts,role['events'])
            self.assertEqual(local,[count>=at for at in clock['local_counts']],count)
            size=next((i for i,good in enumerate(local) if not good),len(local))
            self.assertEqual(size,sum(at<=count for at in clock['published_counts']),count)
            visible=tool.xd_records(parts,role['events'][:size])
            self.assertEqual([tuple(u[k] for k in fields) for u in visible],
                             [tuple(u[k] for k in fields) for u in units[:size]])
            for name in ('local','publication'):
                firsts=clock['local_counts'] if name=='local' else clock['published_counts']
                for i,at in enumerate(firsts):
                    if count==at:
                        proof=role['events'][i][3]
                        actual=(parts[proof]['end_ticks'],parts[proof]['end_dt'],proof==len(parts)-1)
                        self.assertEqual(actual,clock[name+'_proofs'][i],(name,i,count))
        self.assertEqual(clock['published_counts'],tuple(max(clock['local_counts'][:i+1]) for i in range(39)))

    def test_y1_current_proof94_has_two_qualification_prices_and_strict_boundary_mirrors(self):
        """gap的第二分型先齐；下一段须再严格越原first92终9279，不能共享首达。"""
        role,clock,case,_=self._y1_current_clock_source()
        tool=compiler()
        first,second=role['events'][11:13]
        self.assertEqual((first,second),((84,86,2,94),(87,91,1,94)))
        for count in (1006,1007,1012,1013,1017):
            _,_,bis=tool.foundation(case['raw_rows'][:count],'106')
            parts=tool.components(case['raw_rows'][:count],bis,None)
            self.assertEqual(manual_xd_certificate_ready(parts,first),count>=1007)
            self.assertEqual(manual_xd_certificate_ready(parts,second),count>=1013)
            self.assertEqual((parts[92]['start_ticks'],parts[92]['end_ticks']),(9414,9279))
            if count==1007:
                self.assertEqual((parts[94]['end_ticks'],parts[94]['end_dt']),(9293,'2026-06-03 13:05:00'))
                values=[parts[0]['start_ticks']]+[p['end_ticks'] for p in parts]
                for delta in (-1,0,1):
                    changed=list(values)
                    changed[-1]=parts[92]['end_ticks']+delta
                    for mirrored in (False,True):
                        variant=self._natural_parts([20000-v for v in changed] if mirrored else changed)
                        self.assertTrue(manual_xd_certificate_ready(variant,first))
                        self.assertEqual(manual_xd_certificate_ready(variant,second),delta<0,(delta,mirrored))
            if count>=1013:
                self.assertEqual((parts[94]['end_ticks'],parts[94]['end_dt']),(9268,'2026-06-03 13:35:00'))
        self.assertEqual((clock['publication_proofs'][11],clock['publication_proofs'][12]),
                         ((9293,'2026-06-03 13:05:00',True),(9268,'2026-06-03 13:35:00',True)))

    def test_y1_current_parent_gate_and_f1_clocks_keep_first_versions_and_fixed_contract_separate(self):
        """child61先到但等parent65；十个F1提前量来自真实前缀，证明旧价不回填。"""
        role,clock,case,_=self._y1_current_clock_source()
        tool=compiler()
        for count,size,active in ((624,6,True),(655,8,False)):
            _,_,bis=tool.foundation(case['raw_rows'][:count],'106')
            parts=tool.components(case['raw_rows'][:count],bis,None)
            ready=self._y1_current_given_ready(parts,role['events'])
            self.assertTrue(ready[7])
            self.assertEqual(next((i for i,ok in enumerate(ready) if not ok),39),size)
            self.assertEqual((parts[61]['end_ticks'],parts[61]['end_dt'],len(parts)-1==61),
                             (9474,'2026-05-22 13:50:00',active))
        self.assertEqual((clock['local_counts'][7],clock['published_counts'][7]),(624,655))
        self.assertEqual(clock['publication_proofs'][0],(9801,'2026-05-11 09:45:00',True))
        _,_,bis=tool.foundation(case['raw_rows'][:163],'106')
        later=tool.components(case['raw_rows'][:163],bis,None)
        self.assertEqual(later[14]['end_ticks'],9780)
        self.assertNotEqual(clock['publication_proofs'][0][0],later[14]['end_ticks'])
        self.assertEqual(clock['f1_first_counts'],tuple(clock['published_counts'][s[-1]] for s in role['f1']))
        self.assertEqual(clock['f1_evidence_counts'],tuple(sum(at<=n for at in clock['published_counts'])
                                                         for n in clock['f1_first_counts']))
        self.assertEqual(clock['f1_evidence_counts'],role['f1_evidence_counts'])
        self.assertTrue(all(a<b for a,b in zip(clock['f1_first_counts'],role['f1_first_counts'])))
        self.assertEqual((clock['f1_first_counts'][2],role['f1_first_counts'][2]),(1013,1017))

    def _joined_y1_role_source(self):
        audit=embedded_table('test_real_xd_f1.py','M3_Y1_JOINED_ROLE_AUDIT')
        path=ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        tool=compiler()
        _,_,bis=tool.foundation(case['raw_rows'],'106')
        self.assertEqual(tool.records(bis),case['foundation']['bis'])
        parts=tool.components(case['raw_rows'],bis[:-1],None)
        units=tool.xd_records(parts,audit['events'])
        seen=case['foundation']['bis_confirmed_raw_count']
        local=[seen[e[3]] for e in audit['events']]
        published=[]
        for n in local:
            published.append(max(published[-1] if published else 0,n))
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual(tuple(tuple(u[n] for n in fields)+(local[i],published[i])
                               for i,u in enumerate(units)),audit['units'])
        return audit,case,parts,units,published

    def test_y1_joined39_keeps_corrected_head_bridge_and_retained_suffix_source_identity(self):
        """给seed1，头部止29后经30..51普通/缺口桥接；不沿用旧头部角色。"""
        audit,case,parts,units,published=self._joined_y1_role_source()
        head=embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')['Y1_recent1']
        old=M3_FINITE_SUFFIX_AUDIT['Y1']
        self.assertEqual(audit['events'][:4],head['events'])
        self.assertEqual(audit['events'][4:],old['events'][4:])
        self.assertEqual(audit['units'][:4],tuple(u+(n,n) for u,n in zip(head['units'],head['fixed_counts'])))
        self.assertEqual(tuple(published),old['published_counts'])
        self.assertEqual(len(units),39)
        for event in audit['events'][3:7]:
            self.assertTrue(manual_xd_certificate_ready(parts,event))
        for left,right in zip(units,units[1:]):
            self.assertEqual((left['end_dt'],left['end_ticks']),(right['start_dt'],right['start_ticks']))
        self.assertEqual(audit['units'][7][-2:],(630,661))
        self.assertEqual(audit['events'][7],(52,58,1,61))
        self.assertEqual(audit['events'][6],(49,51,2,65))
        for filename in ('real_strict_trend_5m.json','real_first_point.json'):
            alias=next(c for c in json.loads((ROOT/'tests/fixtures'/filename).read_text())['cases']
                       if c['id']==audit['id'])
            for field in ('raw_rows','foundation','roles','trend'):
                self.assertEqual(alias[field],case[field],(filename,field))

    def test_y1_joined39_does_not_reuse_old_strict_B_or_first_second_point_roles(self):
        """旧B成员重映射不满足Zn步2；改首对后，中间覆盖仍精确缺4格。"""
        audit,case,_,units,_=self._joined_y1_role_source()
        strict=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        old=case['roles']
        self.assertEqual((old['A']['zd'],old['A']['zg']),(9780,9834))
        with self.assertRaisesRegex(ValueError,'首对核心与声明不一致'):
            strict.validate_zhongshu('A',old['A'],units)
        revised_A=dict(old['A'],zd=9714,zg=9906)
        checked=strict.validate_zhongshu('A',revised_A,units)
        self.assertEqual((checked['dd'],checked['gg']),(9702,9933))
        guard=audit['legacy_guard']
        candidate_B=dict(old['B'],zd=9441,zg=9540,dd=9332,gg=9543)
        self.assertEqual((units[8]['start_ticks'],units[8]['low_ticks']),(9445,9441))
        self.assertEqual(units[7]['low_ticks']-candidate_B['zd'],guard['middle_misses_ticks'])
        self.assertEqual((max(u['low_ticks'] for u in units[6:9]),
                          min(u['high_ticks'] for u in units[6:9])),(9445,9540))
        with self.assertRaisesRegex(ValueError,'中间单元未覆盖核心'):
            strict.validate_zhongshu('B',candidate_B,units)
        with self.assertRaisesRegex(ValueError,'Zn同向步2被破坏'):
            strict.validate_zhongshu('B',dict(old['B'],zn=list(guard['remapped_B_zn'])),units)
        self.assertNotIn(guard['old_anchor_event'],audit['events'])
        self.assertFalse(guard['strict_roles_reusable'])
        self.assertFalse(guard['old_first_and_second_reusable'])
        # 只沿用数值下标会把先验低9108/c低9266，错换为9332/9108并翻转新低判定。
        self.assertEqual((case['first_point']['prior_extreme_ticks'],case['first_point']['c_extreme_ticks']),
                         (9108,9266))
        self.assertEqual((min(u['low_ticks'] for u in units[:9]),units[9]['low_ticks']),(9332,9108))
        self.assertEqual(case['first_point']['reason'],'no_new_extreme')
        self.assertEqual(case['second_point']['premise']['category'],'minor_to_major')

    def test_y1_joined39_f1_cuts_frozen_batches_and_open_f2_have_separate_semantics(self):
        """同级切分10个F1；F2允许延伸，首F1进入方向None不替换为净上涨。"""
        audit,_,_,units,published=self._joined_y1_role_source()
        tool=compiler()
        f1=[tool.move_record(units,s) for s in audit['f1']]
        tail=tool.move_record(units,audit['tail'])
        self.assertEqual([published[s[-1]] for s in audit['f1']],list(audit['f1_first_counts']))
        self.assertEqual([sum(n<=at for n in published) for at in audit['f1_first_counts']],
                         list(audit['f1_evidence_counts']))
        self.assertEqual((audit['f1'][1][-1],audit['f1_evidence_counts'][1]),(9,11))
        self.assertEqual((tail['seg_start'],tail['seg_end'],tail['kind'],tail['complete']),
                         (38,38,'incomplete',False))
        self.assertIsNone(f1[0]['direction'])
        self.assertGreater(f1[0]['end_ticks'],f1[0]['start_ticks'])
        for spec in (audit['f1'][1],audit['f1'][6]):
            waves=[(min(u['low_ticks'] for u in units[j:j+3]),
                    max(u['high_ticks'] for u in units[j:j+3])) for j in spec[4]]
            self.assertGreaterEqual(waves[1][1],waves[0][0])  # 核心下移不证明完整波动严格分离。
        f2=tool.move_record(f1,audit['f2'][0])
        self.assertEqual((f2['kind'],f2['direction'],f2['complete'],f2['low_ticks'],f2['high_ticks']),
                         ('down','down',False,8224,9933))
        self.assertEqual(f2['centers_ticks'],[[9332,9414],[8418,8986]])
        self.assertTrue(all(u['low_ticks']<=8986 and u['high_ticks']>=8418 for u in f1[7:10]))
        # 最后反向回试3与8之间，b参考腿[4,4)为空，保持no_compare_legs而非背驰否决。
        self.assertEqual(audit['f2_spans'],(((1,3,3),(4,6,9)),))
        self.assertGreater(f1[3]['end_ticks'],f1[3]['start_ticks'])
        self.assertGreater(f1[8]['end_ticks'],f1[8]['start_ticks'])
        self.assertEqual(audit['strict_tail_skip'],'no_compare_legs')

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

    def test_g1_source_heads_keep_earlier_revocations_and_natural_reaction_separate(self):
        """课67/71/78：给源BI1，4/6先撤销；R19先破首起，不能借后来S20翻案。"""
        a=embedded_table('test_real_xd_f1.py','M3_G1_SOURCE_BRIDGE_AUDIT')
        old=M3_ADDITIONAL_CONSUMERS_AUDIT['G1'];tool=compiler()
        payload=(ROOT/'tests/fixtures'/old['fixture']).read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(),old['fixture_sha256'])
        case=next(c for c in json.loads(payload)['cases'] if c['id']==old['id'])
        rows=case['raw_rows'][:old['limit']];_,_,bis=tool.foundation(rows,'106');source=tool.components(rows,bis,None)
        for mirrored in (False,True):
            parts=copy.deepcopy(source)
            if mirrored:
                for p in parts:
                    p.update(start_ticks=3000-p['start_ticks'],end_ticks=3000-p['end_ticks'],
                             low_ticks=3000-p['high_ticks'],high_ticks=3000-p['low_ticks'],
                             direction='up' if p['direction']=='down' else 'down')
            for seed,h in a['heads'].items():
                for event in h['events']:self.assertTrue(manual_xd_certificate_ready(parts,event))
            for owner,key in ((1,'root1_first_candidates'),(8,'root8_candidates')):
                up=parts[owner]['direction']=='up'
                for turn,gap,cancel in a[key]:
                    left=manual_feature_nodes(parts,range(owner+1,turn,2),up)[-1]
                    actual=parts[turn]['low_ticks']-left[1] if up else left[0]-parts[turn]['high_ticks']
                    self.assertEqual(actual,gap)
                    if cancel is not None:
                        self.assertTrue(parts[cancel]['end_ticks']>parts[turn]['start_ticks'] if up else parts[cancel]['end_ticks']<parts[turn]['start_ticks'])
                    if gap>0:
                        state=manual_gap_lifecycle(parts,owner,turn,52)
                        self.assertEqual(state['state'],'confirmed' if turn==35 else 'revoked')
                        if turn==35:self.assertEqual((state['first_fractal_proof_bi'],state['second_fractal_proof_bi']),(37,52))
                        else:self.assertEqual(state['strict_revocation_bi'],cancel)
            self.assertTrue(manual_xd_certificate_ready(parts,(20,34,2,52)))
            for width in (23,24,25,53):
                state=manual_natural_reaction_state(parts[:width],list(range(1,width+1)),width,8,19,
                    dict(event=(1,7,1,10),published_count=11),(20,34,2,52))
                self.assertEqual(state['state'],'pending' if width<25 else 'first_start_broken')
                self.assertEqual(state['local_proof'],None if width<25 else 24)
        self.assertFalse(a['automatic_origin_proven']);self.assertFalse(a['global_unique_origin_proven'])

    def test_g1_source_head_actual_arrivals_do_not_use_final_BI52_price(self):
        """独立整数前缀：先有BI10/raw138，BI52/raw606只到1076，末价1058不可回填。"""
        a=embedded_table('test_real_xd_f1.py','M3_G1_SOURCE_BRIDGE_AUDIT');old=M3_ADDITIONAL_CONSUMERS_AUDIT['G1'];tool=compiler()
        case=next(c for c in json.loads((ROOT/'tests/fixtures'/old['fixture']).read_text())['cases'] if c['id']==old['id'])
        rows=case['raw_rows'][:old['limit']];first={seed:[None]*len(h['events']) for seed,h in a['heads'].items()};proof52={}
        for count in range(1,len(rows)+1):
            _,_,bis=tool.foundation(rows[:count],'106');parts=tool.components(rows[:count],bis,None)
            for seed,h in a['heads'].items():
                for j,event in enumerate(h['events']):
                    if manual_xd_certificate_ready(parts,event) and first[seed][j] is None:first[seed][j]=count
            if count in (606,len(rows)):proof52[count]=(parts[52]['end_ticks'],parts[52]['end_dt'])
        self.assertEqual(first,{0:[606],1:[138,606]})
        count,price,dt,final_price,final_dt=a['active_proof52']
        self.assertEqual(proof52[count],(price,dt));self.assertEqual(proof52[len(rows)],(final_price,final_dt))
        self.assertNotEqual(proof52[count],proof52[len(rows)])

    def test_g1_whole_chain_F1_has_new_groups_and_actual_external_proof(self):
        """仅验给定三段组与外部证明算术；前部接通后不继承BI35后缀的F1角色。"""
        a=embedded_table('test_real_xd_f1.py','M3_G1_SOURCE_BRIDGE_AUDIT');old=embedded_table('test_real_xd_f1.py','M3_G1_CONSUMERS_AUDIT');tool=compiler()
        names=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi','local_raw_count','confirmed_raw_count')
        suffix=[dict(zip(names,row)) for row in old['units']]
        for seed,h in a['heads'].items():
            units=[dict(zip(names,row)) for row in h['units']]+suffix
            for spec,count,width in zip(h['f1'],h['f1_first'],h['f1_evidence']):
                record=tool.move_record(units,spec)
                self.assertTrue(record['complete'])
                self.assertEqual(max(u['confirmed_raw_count'] for u in units[:spec[-1]+1]),count)
                self.assertEqual(sum(u['confirmed_raw_count']<=count for u in units),width)
                self.assertEqual(sum(u['confirmed_raw_count']<count for u in units),width-1)
            self.assertEqual(h['f1'][0][5],((1027,1126),))
            self.assertNotEqual(h['f1'][0][5],old['f1'][0][5])
            if seed==1:
                lo=max(u['low_ticks'] for u in units[:3]);hi=min(u['high_ticks'] for u in units[:3])
                self.assertGreater(lo,hi)
                self.assertEqual(h['f1'][0][4],(1,))
            self.assertEqual(h['f1_first'],(777,1535))
            self.assertNotEqual(h['f1_first'],old['f1_first'])
            self.assertFalse(tool.move_record(units,h['tail'])['complete'])

    def test_origin_premises_separate_known_absence_from_a_given_recent_boundary(self):
        """同一局部证书下，仅给定起点不补前驱；无前史为另行声明的条件。"""
        values = M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'][3:]
        for mirrored in (False,True):
            parts = self._natural_parts([3000-v for v in values] if mirrored else values)
            anchor = (0,parts[0]['direction'],parts[0]['start_ticks'])
            seen = list(range(103,117))
            legacy = manual_natural_reaction_state(parts,seen,116,0,3,None,(4,6,1,13))
            for basis in ('unknown','given_recent','no_prior_history'):
                origin = dict(basis=basis,anchor=anchor,
                              available_count=None if basis=='unknown' else 103)
                r = manual_natural_reaction_state(parts,seen,116,0,3,None,(4,6,1,13),origin)
                self.assertEqual((r['state'],r['local_proof'],r['local_count']),
                                 ('confirmed_without_start_break',13,116))
                self.assertEqual(r['qualification'],'visible' if basis=='no_prior_history' else 'unknown')
                self.assertEqual(r['published_count'],116 if basis=='no_prior_history' else None)
                self.assertEqual(r['origin_status'],'unknown' if basis=='unknown' else 'visible')
                self.assertIsNone(r['predecessor'])
            self.assertEqual((legacy['qualification'],legacy['published_count']),('unknown',None))

    def test_origin_arrival_delays_publication_without_retiming_local_proof(self):
        """起点声明晚到不回填历史，也不能让给定近期起点自动取得前驱资格。"""
        parts = self._natural_parts(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'][3:])
        seen = list(range(103,117))
        anchor = (0,parts[0]['direction'],parts[0]['start_ticks'])
        for basis in ('no_prior_history','given_recent'):
            for observed in (116,199,200):
                origin = dict(basis=basis,anchor=anchor,available_count=200)
                r = manual_natural_reaction_state(parts,seen,observed,0,3,None,(4,6,1,13),origin)
                self.assertEqual((r['local_proof'],r['local_count']),(13,116))
                self.assertEqual(r['origin_status'],'visible' if observed==200 else 'waiting')
                self.assertEqual(r['published_count'],200 if basis=='no_prior_history' and observed==200 else None)

    def test_origin_premises_reject_mismatched_anchors_and_fabricated_predecessors(self):
        """声明不能换起点、抹去已给前史，或夹带完成/发布字段。"""
        parts = self._natural_parts(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'][3:])
        seen = list(range(103,117))
        anchor = (0,parts[0]['direction'],parts[0]['start_ticks'])
        invalid = [dict(basis='unknown',anchor=anchor,available_count=103),
                   dict(basis='no_prior_history',anchor=(False,anchor[1],anchor[2]),available_count=103),
                   dict(basis='no_prior_history',anchor=(0,'up',anchor[2]),available_count=103),
                   dict(basis='no_prior_history',anchor=(0,anchor[1],anchor[2]+1),available_count=103),
                   dict(basis='no_prior_history',anchor=anchor,available_count=True),
                   dict(basis='no_prior_history',anchor=anchor,available_count=-1),
                   dict(basis='no_prior_history',anchor=anchor,available_count=103,published_count=103)]
        for origin in invalid:
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                manual_natural_reaction_state(parts,seen,116,0,3,None,(4,6,1,13),origin)
        full = self._natural_parts(M3_M2_GIVEN_PROOFS_AUDIT['recent_seed87_ticks'])
        origin = dict(basis='no_prior_history',anchor=(3,full[3]['direction'],full[3]['start_ticks']),available_count=103)
        with self.assertRaisesRegex(ValueError,'无前史仅可'):
            manual_natural_reaction_state(full,list(range(100,117)),116,3,6,None,(7,9,1,16),origin)
        origin = dict(basis='given_recent',anchor=origin['anchor'],available_count=103)
        with self.assertRaisesRegex(ValueError,'不能代替或混入'):
            manual_natural_reaction_state(full,list(range(100,117)),116,3,6,
                dict(event=(0,2,1,5),published_count=105),(7,9,1,16),origin)
        mutable_anchor = list(anchor)
        origin = dict(basis='no_prior_history',anchor=mutable_anchor,available_count=103)
        r = manual_natural_reaction_state(parts,seen,116,0,3,None,(4,6,1,13),origin)
        mutable_anchor[2] += 1
        origin['available_count'] = 200
        self.assertEqual(r['origin'],('no_prior_history',anchor,103))

    def test_author_no_history_premise_is_explicit_and_does_not_generate_xd_labels(self):
        """课78的无前史条件显式传入；状态发布时间不充作03/38分段证明。"""
        cases = json.loads((ROOT/'tests/fixtures/xd_originals.json').read_text())
        case = next(c for c in cases if c['id']=='78-reply-0-3-8-11')
        self.assertEqual((case['source_role'],case['pdf_page']),('author_reply',616))
        self.assertIn('前面无任何走势',case['assumptions'])
        parts = self._natural_parts(case['values'])
        origin = dict(basis='no_prior_history',anchor=(0,'down',8),available_count=1)
        r = manual_natural_reaction_state(parts,list(range(1,12)),11,0,3,None,None,origin)
        self.assertEqual((r['state'],r['local_proof'],r['published_count']),('first_start_broken',10,11))
        self.assertIsNone(r['predecessor'])
        unknown = manual_natural_reaction_state(parts,list(range(1,12)),11,0,3,None,None)
        self.assertEqual((unknown['local_proof'],unknown['published_count']),(10,None))

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

    def _context_counterexample_source(self,key):
        source = M3_FINITE_SUFFIX_AUDIT[key]
        path = ROOT/'tests/fixtures'/source['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==source['id'])
        tool = compiler()
        _,_,bis = tool.foundation(case['raw_rows'],'106')
        self.assertEqual(tool.records(bis),case['foundation']['bis'])
        return M3_CONTEXT_COUNTEREXAMPLES_AUDIT[key],case,tool.components(case['raw_rows'],bis[:-1],None)

    def test_context_counterexamples_revoke_original_first_before_accepting_local_following(self):
        """M2/Y1局部同起点小段虽成立，原首起已破就不能反传旧段完成。"""
        for key in ('M2','Y1'):
            audit,_,original = self._context_counterexample_source(key)
            values = [original[0]['start_ticks']]+[p['end_ticks'] for p in original]
            for mirrored in (False,True):
                parts = self._natural_parts([20000-v for v in values] if mirrored else values)
                owner,first,cancel = audit['owner'],audit['first'],audit['cancel']
                seen = list(range(len(parts)))  # 本项只比笔快照；raw到达另项核验。
                parent = dict(event=audit['predecessor'],published_count=audit['predecessor'][3])
                before = manual_natural_reaction_state(parts[:cancel],seen[:cancel],cancel-1,
                    owner,first,parent,None)
                self.assertEqual(before['state'],'pending')
                at = manual_natural_reaction_state(parts[:cancel+1],seen[:cancel+1],cancel,
                    owner,first,parent,None)
                self.assertEqual((at['qualification'],at['state'],at['local_proof']),
                                 ('visible','first_start_broken',cancel))
                # 错误路线从first自身找完成小段；自然反应应从first+1起，方向相反。
                self.assertEqual(audit['false_following'][0],first)
                self.assertTrue(manual_xd_certificate_ready(parts[:cancel+1],audit['false_following']))
                self.assertNotEqual(parts[first]['direction'],parts[first+1]['direction'])
                later = manual_natural_reaction_state(parts,seen,seen[-1],owner,first,parent,None)
                self.assertEqual((later['state'],later['local_proof']),('first_start_broken',cancel))
                self.assertTrue(manual_xd_certificate_ready(parts,audit['events'][-1]))

    def test_provisional_parent_keeps_original_first247_waiting_before_active_price_selection(self):
        """M2 raw4705..4715的局部253不能替换原247；待证R239不改成未知前史。"""
        audit,case,_ = self._context_counterexample_source('M2')
        tool = compiler()
        for raw,price in ((4705,1126),(4715,1135),(4716,1170)):
            _,_,bis = tool.foundation(case['raw_rows'][:raw],'106')
            original = tool.components(case['raw_rows'][:raw],bis,None)
            self.assertEqual((len(original),original[255]['end_ticks']),(256,price))
            values = [original[0]['start_ticks']]+[p['end_ticks'] for p in original]
            for mirrored in (False,True):
                parts = self._natural_parts([20000-v for v in values] if mirrored else values)
                seen = list(range(len(parts)))
                provisional = dict(proposed_boundary=(239,240),published_count=None)
                state = manual_natural_reaction_state(parts,seen,255,240,247,provisional,(248,252,1,255))
                self.assertEqual(state['qualification'],'waiting')
                self.assertEqual(state['predecessor'],('provisional',239,240))
                self.assertIsNone(state['published_count'])
                self.assertEqual(state['state'],'first_end_selected' if raw==4716 else
                                 'confirmed_without_start_break')
                self.assertTrue(manual_xd_certificate_ready(parts,(240,252,1,255)))
                self.assertEqual(manual_xd_certificate_ready(parts,(240,246,1,255)),raw==4716)
                self.assertEqual(manual_xd_certificate_ready(parts,audit['events'][1]),raw==4716)
                # 原first247底1105低于later253底1113；没有新低撤销原首身份。
                self.assertTrue(parts[247]['start_ticks']>parts[253]['start_ticks'] if mirrored else
                                parts[247]['start_ticks']<parts[253]['start_ticks'])
                bad = dict(provisional,published_count=255)
                with self.assertRaisesRegex(ValueError,'待证前驱'):
                    manual_natural_reaction_state(parts,seen,255,240,247,bad,(248,252,1,255))
                with self.assertRaisesRegex(ValueError,'待证前驱'):
                    manual_natural_reaction_state(parts,seen,255,240,247,
                        dict(proposed_boundary=(239,241)),(248,252,1,255))

    def test_context_counterexample_actual_raw_boundaries_keep_active_and_fixed_proofs_separate(self):
        """948点独立收据的首达边界防回填；本测试不依赖临时目录或原型。"""
        tool = compiler()
        for key in ('M2','Y1'):
            audit,case,_ = self._context_counterexample_source(key)
            counts = set(audit['current_counts']+audit['fixed_counts']+
                         (audit['current_cancel'],audit['fixed_cancel']))
            counts = sorted(n for c in counts for n in (c-1,c)
                            if audit['raw_window'][0]<=n<=audit['raw_window'][1])
            for raw in counts:
                rows = case['raw_rows'][:raw]
                _,_,bis = tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
                for contract,visible in (('current',bis),('fixed',bis[:-1])):
                    parts = tool.components(rows,visible,None)
                    for i,event in enumerate(audit['events']):
                        ready = manual_xd_certificate_ready(parts,event)
                        first_raw = audit[contract+'_counts'][i]
                        self.assertEqual(ready,raw>=first_raw,(key,contract,raw,event))
                        if raw==first_raw:
                            proof = parts[event[3]]
                            self.assertEqual((proof['end_ticks'],proof['end_dt']),
                                (audit[contract+'_proof_prices'][i],audit[contract+'_proof_dates'][i]))
                    first,cancel = audit['first'],audit['cancel']
                    broken = False
                    if len(parts)>cancel:
                        broken = (parts[cancel]['end_ticks']>parts[first]['start_ticks'] if
                                  parts[first]['direction']=='down' else
                                  parts[cancel]['end_ticks']<parts[first]['start_ticks'])
                    self.assertEqual(broken,raw>=audit[contract+'_cancel'],(key,contract,raw))

    def _m2_gap_parts(self):
        audit = M3_FINITE_SUFFIX_AUDIT['M2']
        path = ROOT/'tests/fixtures'/audit['fixture']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),audit['fixture_sha256'])
        case = next(c for c in json.loads(path.read_text())['cases'] if c['id']==audit['id'])
        tool = compiler()
        _,_,bis = tool.foundation(case['raw_rows'],'106')
        self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:-1])
        return tool.components(case['raw_rows'],bis[:-1],None)

    def test_positive_gap_waits_for_required_second_fractal_before_later_lower_top(self):
        """M2已知前驱201：原first212未撤销时，218的局部证明没有自然准入。"""
        original = self._m2_gap_parts()
        cases = ((212,214,'await_first',None,None,None,10),
                 (212,216,'waiting',216,None,None,10),
                 (212,220,'waiting',216,None,None,10),
                 (212,222,'waiting',216,None,None,10),
                 (212,226,'waiting',216,None,None,10),
                 (212,227,'revoked',216,None,227,10),
                 (228,230,'waiting',230,None,None,84),
                 (228,240,'waiting',230,None,None,84),
                 (228,241,'confirmed',230,241,None,84))
        for mirrored in (False,True):
            values = [original[0]['start_ticks']]+[p['end_ticks'] for p in original]
            parts = self._natural_parts([10000-v for v in values] if mirrored else values)
            for first,stop,state,first_proof,second_proof,cancel,gap in cases:
                result = manual_gap_lifecycle(parts,201,first,stop)
                actual = tuple(result[k] for k in ('state','first_fractal_proof_bi',
                               'second_fractal_proof_bi','strict_revocation_bi','original_gap_ticks'))
                self.assertEqual(actual,(state,first_proof,second_proof,cancel,gap),(mirrored,first,stop))
            self.assertTrue(manual_xd_certificate_ready(parts,(201,217,1,220)))
            self.assertTrue(manual_xd_certificate_ready(parts,(201,227,2,241)))
            stronger = (parts[212]['start_ticks']<parts[218]['start_ticks'] if mirrored else
                        parts[212]['start_ticks']>parts[218]['start_ticks'])
            self.assertTrue(stronger)
            # 222已有第二序列顶(镜像底)，不是向上旧段所需的第二底(镜像顶)。
            second = manual_feature_nodes(parts,range(213,223,2),mirrored)
            self.assertTrue(manual_feature_fractal(second[-3:],not mirrored))
            self.assertFalse(manual_feature_fractal(second[-3:],mirrored))
            # 后续回补缺口也不把原正缺口改判为第一种；first218本身却无正缺口。
            self.assertEqual(manual_gap_lifecycle(parts,201,218,220)['state'],'not_gap')

    def test_gap_revocation_is_strict_and_cannot_authorize_a_past_evidence_prefix(self):
        """原首起价等值继续等；未来227的严格撤销不能回写220的自然资格。"""
        original = self._m2_gap_parts()
        prices = [original[0]['start_ticks']]+[p['end_ticks'] for p in original]
        for mirrored in (False,True):
            values = [10000-v for v in prices] if mirrored else list(prices)
            parts = self._natural_parts(values)
            at220 = manual_gap_lifecycle(parts,201,212,220)
            self.assertEqual(at220,manual_gap_lifecycle(parts[:221],201,212,220))
            self.assertEqual(at220['state'],'waiting')
            self.assertEqual(manual_gap_lifecycle(parts,201,212,227)['state'],'revoked')
            # 严格穿越前一格、等价、严格穿越后一格使用同一个原首身份。
            original_start = values[212]
            for delta,state in ((-1,'waiting'),(0,'waiting'),(1,'revoked')):
                changed = list(values[:229])
                changed[228] = original_start+(-delta if mirrored else delta)
                result = manual_gap_lifecycle(self._natural_parts(changed),201,212,227)
                self.assertEqual(result['state'],state,(mirrored,delta))
                self.assertEqual(result['strict_revocation_bi'],227 if state=='revoked' else None)
            # 较长输入中的极值毒值不改变较早的证据前缀。
            future = list(values)
            future[228:] = [20000 if i%2 else -20000 for i in range(len(future)-228)]
            self.assertEqual(manual_gap_lifecycle(self._natural_parts(future),201,212,220),at220)

    def test_gap_second_fractal_and_same_snapshot_extreme_keep_confirmation_precedence(self):
        """课67/78同笔第二分型与新极值先确认；较早撤销则不能被未来分型复活。"""
        prices = [0,5,3,10,8,9,6,8,4,7,6,11]
        for mirrored in (False,True):
            values = [100-v for v in prices] if mirrored else list(prices)
            parts = self._natural_parts(values)
            self.assertEqual(manual_gap_lifecycle(parts,0,3,4)['state'],'await_first')
            before = manual_gap_lifecycle(parts,0,3,9)
            self.assertEqual((before['state'],before['first_fractal_proof_bi']),('waiting',5))
            after = manual_gap_lifecycle(parts,0,3,10)
            self.assertEqual((after['state'],after['second_fractal_proof_bi'],
                              after['strict_revocation_bi']),('confirmed',10,10))
            early = list(prices)
            early[9],early[11] = 11,12
            early_parts = self._natural_parts([100-v for v in early] if mirrored else early)
            revoked = manual_gap_lifecycle(early_parts,0,3,10)
            self.assertEqual((revoked['state'],revoked['strict_revocation_bi'],
                              revoked['second_fractal_proof_bi']),('revoked',8,None))

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

    def _m2_suffix_source(self):
        head,case,_,_=self._m2_joined_source()
        audit=embedded_table('test_real_xd_f1.py','M3_M2_SUFFIX_ROLE_AUDIT')
        self.assertEqual(audit['head_certificate_sha256'],head['certificate_sha256'])
        tool=compiler();_,_,bis=tool.foundation(case['raw_rows'],'106')
        self.assertEqual(tool.records(bis),case['foundation']['bis'])
        parts=tool.components(case['raw_rows'],bis,None)
        full=dict(head,events=head['events']+audit['events']+(audit['current_tail_event'],),
                  reactions=head['reactions']+(audit['reaction'],),successors=head['successors']+(audit['successor'],))
        units=tool.xd_records(parts,full['events'])
        self.assertEqual([tuple(u[k] for k in ('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')) for u in units],
                         [u[:9] for u in head['units']+audit['units']+(audit['current_tail_unit'],)])
        return audit,head,full,case,parts,units

    def _m2_suffix_ready(self,parts,full):
        ready=self._m2_joined_given_ready(parts,full)
        reaction=full['reactions'][2];good=manual_xd_certificate_ready(parts,reaction)
        if good:
            first=parts[164]
            good=(all(parts[i]['end_ticks']>=first['end_ticks'] for i in range(166,173,2)) and
                  all(parts[i]['end_ticks']<=first['start_ticks'] for i in range(165,173,2)))
        ready[21]=good
        ready[22]=ready[22] and good and manual_xd_certificate_ready(parts,full['successors'][2])
        ready[35]=(manual_xd_certificate_ready(parts,(311,319,1,322)) and
                   all(parts[i]['end_ticks']>=1106 for i in range(312,min(323,len(parts)),2)) and
                   all(parts[i]['end_ticks']<=1131 for i in range(311,min(323,len(parts)),2)))
        return ready

    def test_m2_suffix_equal_first_end_requires_adjacent_natural_reaction(self):
        """168等终1034不选向；322等终1106亦不选向，但S311已独立完成。"""
        audit,head,full,case,parts,_=self._m2_suffix_source()
        self.assertEqual((parts[168]['end_ticks'],parts[164]['end_ticks']),(1034,1034))
        self.assertFalse(manual_xd_certificate_ready(parts,(161,163,1,168)))
        self.assertTrue(manual_xd_certificate_ready(parts,audit['reaction']))
        seen=case['foundation']['bis_confirmed_raw_count'][:181]
        bridge=dict(owner=161,first=164,old_boundary=full['events'][21],reaction=audit['reaction'],
                    successor=audit['successor'],extended=full['events'][22])
        parent=dict(event=full['events'][20],published_count=audit['published_counts']['fixed'][6])
        self.assertIsNone(manual_natural_successor_certificate(parts[:180],seen[:180],seen[179],bridge,parent))
        result=manual_natural_successor_certificate(parts[:181],seen,seen[180],bridge,parent)
        self.assertEqual((result['local_proof'],result['successor_proof'],result['published_count']),(180,180,3681))
        # 原首310保持；319仅等起价，S从311紧接而非从内部313另起。
        self.assertEqual((parts[310]['start_ticks'],parts[319]['end_ticks'],parts[310]['end_ticks'],parts[322]['end_ticks']),
                         (1131,1131,1106,1106))
        self.assertFalse(manual_xd_certificate_ready(parts,audit['current_tail_event']))
        self.assertTrue(manual_xd_certificate_ready(parts,audit['tail_reaction']))
        for raw in (5563,5564,5577,5586):
            rows=case['raw_rows'][:raw];tool=compiler();_,_,bis=tool.foundation(rows,'106');p=tool.components(rows,bis,None)
            good=self._m2_suffix_ready(p,full)
            self.assertEqual(good[35],raw>=5564)
            if raw>=5564:
                self.assertIn(p[322]['end_ticks'],(1107,1106))
                self.assertGreaterEqual(p[322]['end_ticks'],p[310]['end_ticks'])
            if raw==5564:
                # 活动首证为1107；不把固定笔到达表套给活动322或回填1106。
                self.assertEqual(p[322]['end_ticks'],1107)
                values=[p[0]['start_ticks']]+[v['end_ticks'] for v in p]
                values[320]+=1  # BI319严格越过原首起价，必须先撤销。
                self.assertFalse(self._m2_suffix_ready(self._natural_parts(values),full)[35])
            self.assertFalse(self._m2_suffix_ready(tool.components(rows,bis[:-1],None),full)[35])
        # 这里只核严格选向分支的±1及镜像；自然反应是另一独立证书。
        for owner,end,proof,bound in ((161,163,168,1034),(303,309,322,1106)):
            values=[parts[owner]['start_ticks']]+[p['end_ticks'] for p in parts[owner:proof+1]]
            for delta in (-1,0,1):
                for mirror in (False,True):
                    changed=list(values);changed[-1]=bound+delta
                    if mirror:changed=[3000-v for v in changed]
                    self.assertEqual(manual_xd_certificate_ready(self._natural_parts(changed),(0,end-owner,1,proof-owner)),delta<0)
        self.assertEqual(head['events'],full['events'][:14])

    def test_m2_suffix_earlier_revocations_and_retained_gap_do_not_revive_internal_first(self):
        audit,_,_,_,parts,_=self._m2_suffix_source()
        self.assertEqual((len(audit['revocations']),len(audit['ineligible_turns'])),(38,24))
        for owner,first,canceled,kind in audit['revocations']:
            up=parts[owner]['direction']=='up';r=parts[first]
            earlier=[i for i in range(first+1,canceled+1,2) if
                     (parts[i]['end_ticks']>r['start_ticks'] if up else parts[i]['end_ticks']<r['start_ticks'])]
            self.assertEqual(earlier[0],canceled)
            if kind=='gap':self.assertEqual(manual_gap_lifecycle(parts,owner,first,canceled)['state'],'revoked')
        for owner,first in audit['ineligible_turns']:
            up=parts[owner]['direction']=='up';left=manual_feature_nodes(parts,range(owner+1,first,2),up)[-1]
            self.assertTrue(parts[first]['high_ticks']<=left[1] if up else parts[first]['low_ticks']>=left[0])
        self.assertIn((190,200,1,203),audit['events'])
        self.assertIn((201,227,2,241),audit['events'])
        for observed in (220,222):self.assertEqual(manual_gap_lifecycle(parts,201,212,observed)['state'],'waiting')
        self.assertTrue(manual_xd_certificate_ready(parts,(201,217,1,220)))
        self.assertEqual(manual_gap_lifecycle(parts,201,212,227)['state'],'revoked')
        self.assertGreater(parts[227]['end_ticks'],parts[218]['start_ticks'])
        self.assertEqual(manual_gap_lifecycle(parts,303,306,322)['state'],'revoked')
        for first in (308,312,314,316,318,320):
            left=manual_feature_nodes(parts,range(304,first,2),True)[-1]
            self.assertLessEqual(parts[first]['high_ticks'],left[1])

    def test_m2_suffix_actual_clock_boundaries_keep_local_proof_and_published_batch(self):
        audit,head,full,case,_,_=self._m2_suffix_source();tool=compiler();clocks={}
        for contract in ('current','fixed'):
            local=(head['current_local_counts'] if contract=='current' else tuple(u[-2] for u in head['units']))+audit['local_counts'][contract]
            published=(head['current_counts'] if contract=='current' else tuple(u[-1] for u in head['units']))+audit['published_counts'][contract]
            clocks[contract]=(local,published)
            self.assertEqual(published,tuple(max(local[:i+1]) for i in range(len(local))))
            self.assertEqual(len(local),36 if contract=='current' else 35)
            self.assertEqual(published[23:26],(3940,)*3 if contract=='current' else (3956,)*3)
            self.assertLess(local[24],local[23]);self.assertLess(local[25],local[23])
        counts=sorted({5563,5564,5577,5586}|{n for pair in clocks.values() for clock in pair for at in clock for n in (at-1,at)})
        for count in counts:
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
            for contract,bs in (('current',bis),('fixed',bis[:-1])):
                p=tool.components(rows,bs,None);ready=self._m2_suffix_ready(p,full);local,pub=clocks[contract]
                self.assertEqual(ready,[count>=at for at in local]+([False] if contract=='fixed' else []))
                self.assertEqual(next((i for i,ok in enumerate(ready) if not ok),36),sum(at<=count for at in pub))
                for key,clock in (('local_proofs',local),('publication_proofs',pub)):
                    expected=head[key][contract]+audit[key][contract]
                    for i,at in enumerate(clock):
                        if at==count:
                            proof=full['events'][i][3];v=p[proof]
                            self.assertEqual((v['end_ticks'],v['end_dt'],contract=='current' and proof==len(p)-1),expected[i])
        self.assertEqual(audit['publication_proofs']['current'][-1],(1107,'2026-07-24 13:05:00',True))

    def test_m2_suffix_f1_f2_and_recursive_roles_use_full_wave_ranges(self):
        audit,head,_,_,_,units=self._m2_suffix_source();tool=compiler()
        self.assertEqual((units[14]['start_ticks'],units[14]['high_ticks']),(1079,1085))
        specs=head['f1']+audit['f1']
        for a,z,kind,entry,centers,cores,proof in specs:
            first=centers[0];lo,hi=cores[0]
            self.assertEqual((max(u['low_ticks'] for u in units[first:first+3]),min(u['high_ticks'] for u in units[first:first+3])),(lo,hi))
            for start in range(a,first):self.assertGreater(max(u['low_ticks'] for u in units[start:start+3]),min(u['high_ticks'] for u in units[start:start+3]))
            self.assertEqual(entry,units[a]['direction'] if first>a else None)
            self.assertEqual((kind,proof),('consolidation',z+1))
            self.assertTrue(all(u['low_ticks']>hi or u['high_ticks']<lo for u in units[first+3:proof]))
            self.assertTrue(units[proof]['low_ticks']<=hi and units[proof]['high_ticks']>=lo)
        f1=[tool.move_record(units,s) for s in specs]
        for spec,spans in zip(audit['f2'],audit['f2_spans']):
            a,z,_,_,centers,cores,_=spec
            for start,(lo,hi),(begin,formed,last) in zip(centers,cores,spans):
                self.assertEqual(start,begin)
                self.assertEqual((max(u['low_ticks'] for u in f1[begin:formed+1]),min(u['high_ticks'] for u in f1[begin:formed+1])),(lo,hi))
                self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in f1[formed+1:last+1]))
            tool.move_record(f1,spec)
        self.assertGreater(max(u['low_ticks'] for u in f1[:3]),min(u['high_ticks'] for u in f1[:3]))
        self.assertGreater(f1[5]['low_ticks'],1056)
        self.assertTrue(f1[6]['low_ticks']<=1056 and f1[6]['high_ticks']>=1029)
        for a,formed,last,lo,hi in audit['auto_centers']:
            self.assertEqual((max(u['low_ticks'] for u in units[a:formed+1]),min(u['high_ticks'] for u in units[a:formed+1])),(lo,hi))
            self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in units[formed+1:last+1]))
            self.assertTrue(units[last+1]['high_ticks']<lo or units[last+1]['low_ticks']>hi)
        for previous,last,end in ((audit['auto_centers'][0],audit['auto_centers'][1],11),(audit['auto_centers'][2],audit['auto_centers'][3],27)):
            tails=[next(i for i in range(z,f-1,-1) if units[i]['direction']=='up') for a,f,z,_,_ in (previous,last)]
            self.assertTrue(tuple(range(tails[0]+1,last[0])))
            self.assertEqual(tuple(range(tails[1]+1,end+1)),())

    def _m2_zn_role_source(self):
        suffix,head,full,case,parts,units=self._m2_suffix_source()
        audit=embedded_table('test_real_xd_f1.py','M3_M2_ZN_ROLE_AUDIT')
        self.assertEqual((audit['head_certificate_sha256'],audit['suffix_certificate_sha256'],audit['source_sha256']),
                         (head['certificate_sha256'],suffix['certificate_sha256'],head['fixture_sha256']))
        return audit,suffix,head,full,case,parts,units

    def test_m2_zn_roles_c_fail_and_late_touch_cannot_be_frozen_as_completed(self):
        audit,_,_,_,case,_,units=self._m2_zn_role_source();tool=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        given=dict(first_point={},trend=audit['trend'],roles=audit['roles']);centers=tool.validate_roles(given,units)
        self.assertEqual([(centers[n]['zd'],centers[n]['zg'],centers[n]['dd'],centers[n]['gg']) for n in ('A','B','C')],
                         [(1113,1135,1100,1140),(1031,1049,1010,1091),(1070,1079,1039,1111)])
        self.assertEqual((centers['A']['closed_by'],centers['B']['closed_by'],centers['C']['closed_by']),(5,13,23))
        self.assertEqual((audit['roles']['b']['unit'],audit['roles']['c']['unit']),(4,12))
        B,C=centers['B'],centers['C'];self.assertEqual((C['zd']-B['zg'],B['gg']-C['dd']),(21,52))
        self.assertEqual(units[12]['low_ticks']-B['zg'],21)
        first=next(i for i in range(13,len(units)) if units[i]['low_ticks']<=B['zg'] and units[i]['high_ticks']>=B['zd'])
        self.assertEqual(first,20)
        for proof in (13,20):
            forced=dict(given,trend=dict(direction='down',status='completed'),roles=dict(audit['roles'],proof=dict(unit=proof)))
            with self.assertRaisesRegex(ValueError,'c_fail状态须为no_departure'):tool.validate_roles(forced,units)
        forced=dict(given,roles=dict(audit['roles'],c=dict(unit=12,outcome='departed')))
        with self.assertRaisesRegex(ValueError,'c结局与核心算术不一致'):tool.validate_roles(forced,units)
        first_tool=compiler(ROOT/'validation/tools/gen_real_first_point.py')
        with self.assertRaisesRegex(ValueError,'一类裁定仅施于完成严格趋势'):
            first_tool.derive_first_point(given,units,centers,case['raw_rows'],'5m',[],[],[],[])

    def test_m2_retained_old_A_needs_new_closure_and_old_attempt_bodies_are_missing(self):
        audit,_,_,full,case,_,units=self._m2_zn_role_source();tool=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        old_events=[tuple(e) for e in case['foundation']['xd_events']];events=full['events']
        for old,new in audit['legacy_A_member_map']:
            self.assertEqual(old_events[old],events[new])
        # 中间单元161的身体仍同，但proof168改172；身份/时钟必须另行绑定。
        old,new=case['units'][25],units[21]
        self.assertEqual(tuple(old[k] for k in ('direction','start_dt','end_dt','low_ticks','high_ticks')),
                         tuple(new[k] for k in ('direction','start_dt','end_dt','low_ticks','high_ticks')))
        self.assertEqual((old_events[25],events[21]),(audit['legacy_A_proof_changed_from'],audit['legacy_A_proof_changed_to']))
        checked=tool.validate_zhongshu('retained_A',audit['retained_A'],units)
        self.assertEqual(tuple(checked[k] for k in ('zd','zg','dd','gg','closed_by')),(1073,1100,1015,1111,24))
        old_close,new_index=audit['legacy_A_closed_by_map'];self.assertEqual(old_events[old_close],events[new_index])
        with self.assertRaisesRegex(ValueError,r'封口单元须为zn\[-1\]\+2且存在'):
            tool.validate_zhongshu('retained_A',dict(audit['retained_A'],closed_by=new_index),units)
        for i in audit['missing_legacy_units']:self.assertNotIn(old_events[i],events)
        pairs=tuple((v['leave'],v['pull']) for name in ('A','B') for v in case['attempts'][name])
        self.assertEqual(pairs,audit['legacy_attempt_pairs'])
        self.assertTrue(all(old_events[leave] not in events for leave,_ in pairs))
        old,new=audit['surviving_pullback_map'];self.assertEqual(old_events[old],events[new])
        with self.assertRaisesRegex(ValueError,'首对核心与声明不一致'):
            tool.validate_zhongshu('old_B',case['centers']['B'],units)
        self.assertFalse(audit['old_labels_reusable'])

    def test_m2_zn_actual_ledger_boundaries_keep_first_C_wave_and_retained_closure(self):
        audit,suffix,head,full,case,_,_=self._m2_zn_role_source();tool=compiler();strict=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        # 只由既有角色工具推台账，再分别绑定两合同的实际累计发布时间。
        centers=strict.validate_roles(dict(trend=audit['trend'],roles=audit['roles']),tool.xd_records(
            tool.components(case['raw_rows'],tool.foundation(case['raw_rows'],'106')[2],None),full['events']))
        ledger=strict.derive_ledger(audit['roles'],centers)
        clocks={name:(head['current_counts'] if name=='current' else tuple(u[-1] for u in head['units']))+suffix['published_counts'][name] for name in ('current','fixed')}
        for name,counts in clocks.items():self.assertEqual(tuple((n,i,counts[i]) for n,i in ledger),audit['ledger'][name])
        indices={i for _,i in ledger}|set(audit['event_clock_units'])
        observations=0
        for count in sorted({5586}|{n for clock in clocks.values() for i in indices for n in (clock[i]-1,clock[i])}):
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
            for contract,pens in (('current',bis),('fixed',bis[:-1])):
                observations+=1;p=tool.components(rows,pens,None);ready=self._m2_suffix_ready(p,full)
                size=next((i for i,ok in enumerate(ready) if not ok),36)
                self.assertEqual(size,sum(at<=count for at in clocks[contract]))
                available=tool.xd_records(p,full['events'][:size])
                for name in ('A','B','C'):
                    spec=audit['roles'][name];start=spec['zn'][0]
                    if size>start+2:
                        triple=available[start:start+3]
                        self.assertEqual((max(u['low_ticks'] for u in triple),min(u['high_ticks'] for u in triple)),(spec['zd'],spec['zg']))
                if count==clocks[contract][15]:
                    self.assertEqual(min(u['low_ticks'] for u in available[13:16]),1050)
                if count==clocks[contract][20]:
                    self.assertEqual(min(u['low_ticks'] for u in available[13:21]),1039)
                    self.assertLess(count,clocks[contract][21])
                if count==clocks[contract][24]:
                    self.assertEqual(size,26)  # 23/24/25是同批，不构造批内封口时间。
                    self.assertLess(count,clocks[contract][26])
        self.assertEqual(observations,122)

    def _m2_third_source(self):
        zn,suffix,head,full,case,parts,units=self._m2_zn_role_source()
        a=embedded_table('test_real_xd_f1.py','M3_M2_THIRD_LIFECYCLE_AUDIT')
        self.assertEqual((a['source_sha256'],a['head_certificate_sha256'],a['suffix_certificate_sha256'],a['zn_certificate_sha256']),
                         (head['fixture_sha256'],head['certificate_sha256'],suffix['certificate_sha256'],zn['certificate_sha256']))
        return a,zn,suffix,head,full,case,parts,units

    @staticmethod
    def _m2_causal_attempts(units,spec,known):
        """给定形成三段及确认时刻，整数枚举首次回试；不搜索中枢或读取包算法。"""
        first,formed,zd,zg,parent=spec;active=[];suppressed=[];terminal=False
        for i in range(formed+1,len(units)-1):
            leave,pull=units[i:i+2];up=leave['direction']=='up'
            if leave['low_ticks']>zg or leave['high_ticks']<zd or not (leave['end_ticks']>zg if up else leave['end_ticks']<zd):continue
            margin=pull['low_ticks']-zg if up else zd-pull['high_ticks']
            status='before_center_known' if leave['start_dt']<known else 'established' if margin>=0 else 'fail'
            row=('buy3' if up else 'sell3',i,i+1,margin,pull['end_ticks'],status)
            if terminal:suppressed.append(row)
            else:
                active.append(row)
                if status=='established':terminal=True
        pending=None
        if not terminal and len(units)>formed+1:
            leave=units[-1];up=leave['direction']=='up'
            if leave['start_dt']>=known and leave['low_ticks']<=zg and leave['high_ticks']>=zd and (leave['end_ticks']>zg if up else leave['end_ticks']<zd):pending=('buy3' if up else 'sell3',len(units)-1)
        return active,suppressed,pending

    def test_m2_causal_attempt_geometry_keeps_failed_excluded_and_terminal_rows_distinct(self):
        a,_,_,_,_,case,_,units=self._m2_third_source();time_tool=compiler(ROOT/'validation/tools/gen_real_third_point.py')
        for contract in ('current','fixed'):
            supplied=units[:36 if contract=='current' else 35];totals=dict(fail=0,before_center_known=0,established=0)
            for name,spec in a['contexts'].items():
                known=time_tool.arrival_dt(case['raw_rows'][a['known_raw'][contract][name]-1]['dt'],'5m')
                active,suppressed,pending=self._m2_causal_attempts(supplied,spec,known)
                expected=[r for r in a['attempts'][name] if r[2]<len(supplied)]
                self.assertEqual(active,expected)
                self.assertEqual(tuple((r[1],r[2]) for r in suppressed),tuple(p for p in a['suppressed_pairs'][name] if p[1]<len(supplied)))
                self.assertEqual(pending,('sell3',34) if name=='N' and contract=='fixed' else None)
                for side,leave,pull,margin,price,status in active:
                    totals[status]+=1
                    self.assertEqual((supplied[leave]['end_dt'],supplied[leave]['end_ticks']),
                                     (supplied[pull]['start_dt'],supplied[pull]['start_ticks']))
                    self.assertNotEqual(supplied[leave]['direction'],supplied[pull]['direction'])
            self.assertEqual(totals,dict(fail=7,before_center_known=6,established=a['terminal_counts'][contract]))

    def test_m2_causal_point_boundaries_rebuild_raw_inputs_and_publish_batches(self):
        a,_,suffix,head,full,case,_,_=self._m2_third_source();tool=compiler();time_tool=compiler(ROOT/'validation/tools/gen_real_third_point.py')
        clocks={name:(head['current_counts'] if name=='current' else tuple(u[-1] for u in head['units']))+suffix['published_counts'][name] for name in ('current','fixed')}
        total=0
        counts=sorted({5586}|{n for clock in clocks.values() for i in a['clock_units'] if i<len(clock) for n in (clock[i]-1,clock[i])})
        for count in counts:
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis)-1])
            for contract,pens in (('current',bis),('fixed',bis[:-1])):
                total+=1;parts=tool.components(rows,pens,None);ready=self._m2_suffix_ready(parts,full);size=next((i for i,ok in enumerate(ready) if not ok),36)
                self.assertEqual(size,sum(at<=count for at in clocks[contract]))
                visible=tool.xd_records(parts,full['events'][:size])
                for name,spec in a['contexts'].items():
                    first,formed,zd,zg,parent=spec
                    if size<=formed:continue
                    triple=visible[first:formed+1]
                    self.assertEqual((max(u['low_ticks'] for u in triple),min(u['high_ticks'] for u in triple)),(zd,zg))
                    known=time_tool.arrival_dt(case['raw_rows'][a['known_raw'][contract][name]-1]['dt'],'5m')
                    active,_,_=self._m2_causal_attempts(visible,spec,known)
                    successes=[r for r in active if r[-1]=='established'];raw=a['point_raw'][contract][name]
                    self.assertEqual(bool(successes),raw is not None and raw<=count)
                    if successes:
                        side,leave,pull,margin,price,_=successes[0]
                        self.assertEqual((side,leave,pull,price,margin),a['points'][name])
                if count in (3940,3956) and count==clocks[contract][23]:self.assertEqual(size,26)
        self.assertEqual(total,198)

    def test_m2_newborn_N_has_fresh_core_and_fixed_tail_has_no_completed_return(self):
        a,_,_,_,full,case,_,units=self._m2_third_source();tool=compiler()
        self.assertEqual(a['contexts']['N'],(29,31,1139,1177,'R'))
        self.assertEqual(a['contexts']['N'][0],a['parent_N_pull']+1)
        for contract in ('current','fixed'):
            self.assertLess(a['point_raw'][contract]['R'],a['known_raw'][contract]['N'])
            self.assertEqual(a['points']['R'][2],a['parent_N_pull'])
        self.assertNotEqual((a['contexts']['N'][2],a['contexts']['N'][3]),(1111,1137))  # 历史B核心不迁移。
        for count in (5563,5564,5577,5586):
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            for contract,pens in (('current',bis),('fixed',bis[:-1])):
                p=tool.components(rows,pens,None);ready=self._m2_suffix_ready(p,full);size=next((i for i,ok in enumerate(ready) if not ok),36)
                self.assertEqual(size,36 if contract=='current' and count>=5564 else 35)
                if size==36:
                    self.assertEqual((p[322]['end_ticks'],p[322]['end_dt']),
                                     (1107,'2026-07-24 13:05:00') if count==5564 else (1106,'2026-07-24 14:10:00'))
                    self.assertEqual(units[35]['end_ticks'],1131)
                else:self.assertEqual(full['events'][34],(294,302,1,305))
        self.assertEqual((a['point_raw']['current']['N'],a['point_raw']['fixed']['N']),(5564,None))

    def test_m2_causal_attempts_do_not_apply_future_final_Zn_membership_filter(self):
        a,zn,_,_,_,case,_,units=self._m2_third_source();tool=compiler(ROOT/'validation/tools/gen_real_third_point.py')
        for name,i in a['legacy_Zn_members_do_not_filter_causal_attempts']:
            self.assertIn(i,zn['roles'][name]['zn'])
            self.assertIn(i,[r[1] for r in a['attempts'][name]])
        legacy=tool.enumerate_attempts(units,zn['roles']['B'])
        self.assertNotIn(11,[r['leave'] for r in legacy])
        self.assertEqual(a['points']['B'][1:3],(11,12))
        # R的早期几何25格守沿先被时间门控挡住；不能回填形成时刻取得早期点。
        for contract in ('current','fixed'):
            known=tool.arrival_dt(case['raw_rows'][a['known_raw'][contract]['R']-1]['dt'],'5m')
            self.assertGreater(known,units[22]['start_dt'])
            self.assertEqual(a['attempts']['R'][0],('sell3',22,23,25,1048,'before_center_known'))
        self.assertEqual(a['attempts']['N'][0],('sell3',32,33,0,1139,'before_center_known'))

    def _e_consumers_source(self):
        a=embedded_table('test_real_xd_f1.py','M3_E_CONSUMERS_AUDIT');old=M3_ADDITIONAL_CONSUMERS_AUDIT['E']
        self.assertEqual((a['id'],a['fixture_sha256'],a['prior_event_receipt_sha256']),
                         (old['id'],old['fixture_sha256'],old['receipt_sha256']))
        self.assertEqual(a['events'],old['events'])
        path=ROOT/'tests/fixtures'/a['fixture'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),a['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==a['id']);tool=compiler();_,_,bis=tool.foundation(case['raw_rows'],'106')
        self.assertEqual(tool.records(bis),case['foundation_106']['bis'])
        parts=tool.components(case['raw_rows'],bis,10);units=tool.xd_records(parts,a['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual([tuple(u[k] for k in fields) for u in units],[u[:9] for u in a['units']])
        return a,old,case,parts,units

    def test_e_given_events_and_consumer_proofs_use_every_actual_daily_prefix(self):
        a,old,case,_,_=self._e_consumers_source();tool=compiler();clocks=dict(current=a['current_counts'],fixed=tuple(u[-1] for u in a['units']))
        first={k:{} for k in clocks};evidence={k:{} for k in clocks};total=0
        for count in range(1,301):
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation_106']['bis'][:len(bis[:-1])])
            for contract,pens in (('current',bis),('fixed',bis[:-1])):
                total+=1;p=tool.components(rows,pens,10);ready=[manual_xd_certificate_ready(p,e) for e in a['events']]
                self.assertEqual(ready,[at<=count for at in clocks[contract]])
                size=next((i for i,ok in enumerate(ready) if not ok),8)
                for j,spec in enumerate(a['f1']):
                    if size>spec[-1] and j not in first[contract]:first[contract][j]=count;evidence[contract][j]=size
                for i,at in enumerate(clocks[contract]):
                    if count==at:
                        proof=a['events'][i][3];b=p[proof]
                        self.assertEqual((b['end_ticks'],b['end_dt'],contract=='current' and proof==len(p)-1),a['publication_proofs'][contract][i])
        self.assertEqual(total,600)
        for contract in clocks:
            self.assertEqual(tuple(first[contract][i] for i in (0,1)),a['f1_first'][contract])
            self.assertEqual(tuple(evidence[contract][i] for i in (0,1)),a['f1_evidence'][contract])
        self.assertEqual(a['current_counts'],old['published_counts']['all_current'])

    def test_e_same_cores_do_not_reuse_legacy_proof_or_mix_recursive_wave_roles(self):
        a,_,case,_,units=self._e_consumers_source();tool=compiler();strict=compiler(ROOT/'validation/tools/gen_real_strict_trend.py')
        for spec in a['f1']:tool.move_record(units,spec)
        legacy=case['paths']['xd-106'];self.assertEqual(legacy['completed'][0]['confirmed_raw_count'],175)
        self.assertEqual(a['f1_first']['fixed'][0],204)
        self.assertEqual(tuple(legacy['units'][3][k] for k in ('mode','proof_bi','end_ticks')),a['legacy_mode_proof_end'])
        self.assertEqual(tuple(units[3][k] for k in ('mode','proof_bi','end_ticks')),a['new_mode_proof_end'])
        self.assertEqual([r['centers_ticks'] for r in legacy['completed']],[[[695,737]],[[887,1017]]])
        for start,formed,last,lo,hi in a['auto_centers']:
            self.assertEqual((max(u['low_ticks'] for u in units[start:formed+1]),min(u['high_ticks'] for u in units[start:formed+1])),(lo,hi))
            self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in units[formed+1:last+1]))
        # 递归完整覆盖范围0..3/4..7与严格接口回抽尾2/6的窗口分别保留。
        waves=[(min(u['low_ticks'] for u in group),max(u['high_ticks'] for u in group)) for group in (units[:4],units[4:])]
        self.assertEqual(min(hi for lo,hi in waves)-max(lo for lo,hi in waves),a['auto_wave_overlap'])
        centers=strict.validate_roles(dict(trend=dict(direction='up',status='ongoing'),roles=a['strict_roles']),units)
        self.assertEqual(centers['B']['dd']-centers['A']['gg'],a['strict_gap_ticks'])
        self.assertEqual((max(u['high_ticks'] for u in units[:7]),units[7]['high_ticks']),(a['strict_prior_high'],a['strict_c_high']))
        self.assertLess(a['strict_c_high'],a['strict_prior_high'])
        self.assertEqual((a['strict_roles']['b']['unit'],a['strict_roles']['c']['unit']),(3,7))
        self.assertIsNone(a['strict_roles']['proof'])

    def test_e_simultaneous_XD_proofs_skip_finite_candidate_only_sizes(self):
        a,_,case,_,_=self._e_consumers_source();tool=compiler()
        self.assertEqual(a['impact_contracts'],((9,'all_current',300),(10,'fixed_without_active',300)))
        self.assertEqual(a['impact_snapshot_sha256'],'7414303cf5ed9e7dc1c62c565c4e69009baeb996da4de200b4b3a9e058f5972e')
        for clock in (a['current_counts'],tuple(u[-1] for u in a['units'])):
            sizes={sum(v<=n for v in clock) for n in range(1,301)}
            self.assertEqual(sizes,{0,1,2,3,5,7,8})
            self.assertEqual((clock[3],clock[5]),(clock[4],clock[6]))
            self.assertNotIn(4,sizes);self.assertNotIn(6,sizes)
        for count in (298,299,300):
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106');p=tool.components(rows,bis,10)
            self.assertEqual(bool(len(p)>34 and p[34]['end_ticks']<p[33]['start_ticks']),count>=299)
            for pens in (p,p[:-1]):self.assertTrue(all(manual_xd_certificate_ready(pens,e) for e in a['events']))

    def _gx_clock_source(self,key):
        base=embedded_table('test_real_xd_f1.py','M3_GAP_REVISION_AUDIT')[key]
        a=embedded_table('test_real_xd_f1.py','M3_GX_CLOCK_CONSUMERS_AUDIT')[key]
        digest=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        self.assertEqual(a['base_sha256'],digest)
        path=ROOT/'tests/fixtures'/base['fixture'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),a['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==base['id']);tool=compiler()
        _,_,bis=tool.foundation(case['raw_rows'],'106');self.assertEqual(tool.records(bis),case['foundation']['bis'])
        parts=tool.components(case['raw_rows'],bis,10 if key=='G' else None);units=tool.xd_records(parts,base['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual([tuple(u[k] for k in fields) for u in units],[u[:9] for u in base['units']])
        self.assertEqual((a['inherited_base'],a['seed']),(0,0) if key=='G' else (7,1))
        return a,base,case,parts,units

    def test_gx_actual_raw_windows_rebuild_local_and_parent_gated_publication_proofs(self):
        tool=compiler();total=0;prefixes=0
        for key in ('G','X1'):
            a,base,case,_,_=self._gx_clock_source(key);seen={c:dict(local={},published={}) for c in ('current','fixed')}
            for count in range(1,max(a['bounds'].values())+1):
                prefixes+=1;rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
                for contract,pens in (('current',bis),('fixed',bis[:-1])):
                    if count>a['bounds'][contract]:continue
                    total+=1;clock=a['contracts'][contract];p=tool.components(rows,pens,10 if key=='G' else None)
                    ready=[manual_xd_certificate_ready(p,e) for e in base['events']]
                    self.assertEqual(ready,[at<=count for at in clock['local']])
                    size=next((i for i,ok in enumerate(ready) if not ok),len(ready))
                    self.assertEqual(size,sum(at<=count for at in clock['published']))
                    for kind,indices in (('local',[i for i,ok in enumerate(ready) if ok]),('published',range(size))):
                        for i in indices:
                            if i in seen[contract][kind]:continue
                            seen[contract][kind][i]=count;b=p[base['events'][i][3]]
                            expected=clock['local_proofs' if kind=='local' else 'publication_proofs'][i]
                            self.assertEqual((count,b['end_ticks'],b['end_dt'],contract=='current' and base['events'][i][3]==len(p)-1),(clock[kind][i],)+expected)
            for contract,clock in a['contracts'].items():
                for kind in ('local','published'):self.assertEqual(tuple(seen[contract][kind][i] for i in range(len(base['events']))),clock[kind])
                self.assertEqual(clock['published'],tuple(max(clock['local'][:i+1]) for i in range(len(base['events']))))
                self.assertEqual(clock['f1_first'],tuple(clock['published'][s[-1]] for s in base['f1']))
                self.assertEqual(clock['f1_evidence'],tuple(sum(v<=at for v in clock['published']) for at in clock['f1_first']))
            self.assertEqual(a['contracts']['fixed']['local'],tuple(u[-2] for u in base['units']))
            self.assertEqual(a['contracts']['fixed']['published'],tuple(u[-1] for u in base['units']))
        self.assertEqual((prefixes,total),(1762,3432))

    def test_gx_recursive_integer_roles_do_not_borrow_preformation_tails_or_confirm_open_leaves(self):
        tool=compiler()
        for key in ('G','X1'):
            a,base,_,_,units=self._gx_clock_source(key)
            for spec in base['f1']+(base['tail'],):tool.move_record(units,spec)
            tool.move_record(units,a['auto'])
            for j,(start,formed,last) in enumerate(a['spans']):
                lo,hi=a['auto'][5][j]
                self.assertEqual((max(u['low_ticks'] for u in units[start:formed+1]),min(u['high_ticks'] for u in units[start:formed+1])),(lo,hi))
                self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in units[formed+1:last+1]))
                if last+1<len(units):self.assertTrue(units[last+1]['low_ticks']>hi or units[last+1]['high_ticks']<lo)
            self.assertIsNone(a['auto'][-1])
            if key=='G':
                self.assertEqual(units[1]['direction'],'down')
                self.assertFalse(any(units[i]['direction']=='down' for i in range(a['spans'][0][1],a['spans'][0][2]+1)))
                self.assertEqual(a['reasons'][5:],('no_comparable_center_tail',)*2)
                self.assertFalse(a['candidates'])
            else:
                for size,c in a['candidates'].items():
                    ends=[next(i for i in range(last,formed-1,-1) if units[i]['direction']=='down') for _,formed,last in ((0,2,7),(8,10,size-1))]
                    self.assertEqual(ends,[6,10 if size==12 else 12])
                    self.assertEqual((tuple(range(ends[0]+1,8)),tuple(range(ends[1]+1,size))),(c['reference'],c['leave']))
                    self.assertEqual(min(u['low_ticks'] for u in units[8:ends[1]+1])-max(u['high_ticks'] for u in units[:ends[0]+1]),c['gap'])
                    self.assertEqual((max(u['high_ticks'] for u in units[:ends[1]+1]),max(units[i]['high_ticks'] for i in c['leave'])),(c['prior_high'],c['leave_high']))
                    self.assertLess(c['leave_high'],c['prior_high'])
                self.assertEqual(a['reasons'][10:],('no_compare_legs','trend_open','no_compare_legs','trend_open'))
                self.assertEqual(base['f1'][2][2:4],('consolidation','down'))
                self.assertGreater(units[9]['end_ticks'],units[6]['start_ticks'])

    def test_gx_inventory_caps_and_candidate_epochs_keep_actual_batches_distinct_from_finite_sizes(self):
        for key in ('G','X1'):
            a,base,case,_,_=self._gx_clock_source(key)
            expected=((15,'all_current',267),(16,'fixed_without_active',267)) if key=='G' else ((57,'all_current',1403),(58,'fixed_without_active',1495))
            self.assertEqual(a['impact_contracts'],expected)
            self.assertEqual(a['source_rows'],len(case['raw_rows']))
            self.assertFalse(a['production_merged']);self.assertFalse(a['source_origin_bridge_proven'])
            for contract,clock in a['contracts'].items():
                sizes={sum(at<=n for at in clock['published']) for n in range(1,a['bounds'][contract]+1)}
                self.assertEqual(clock['candidate_raw'],tuple((size,clock['published'][size-1]) for size in a['candidates']))
                if key=='G':self.assertEqual(sizes,{0,1,2,4,6,7})
                else:
                    self.assertEqual(sizes,set(range(15))-{8,9,10})
                    self.assertEqual(clock['published'][7:11],(1126,)*4 if contract=='current' else (1138,)*4)
                    self.assertEqual(clock['candidate_raw'],((12,1157),(14,1393)) if contract=='current' else ((12,1165),(14,1403)))
                    self.assertEqual(clock['published'][12],1275 if contract=='current' else 1285)
                    self.assertEqual(tuple(e[3] for e in base['events'][7:11]),(84,74,81,84))
            if key=='X1':
                self.assertEqual(a['bounds']['fixed']-a['bounds']['current'],92)
                active=a['contracts']['current']
                self.assertEqual((active['local_proofs'][9][0],active['publication_proofs'][9][0]),(2100,2079))
                self.assertEqual((active['publication_proofs'][7][0],a['contracts']['fixed']['publication_proofs'][7][0]),(2247,2320))
            else:
                active=a['contracts']['current'];fixed=a['contracts']['fixed']
                self.assertEqual((active['publication_proofs'][1][0],fixed['publication_proofs'][1][0]),(845,1185))
                self.assertEqual((active['publication_proofs'][4][0],fixed['publication_proofs'][4][0]),(1024,1039))


    def _g1_consumers_source(self):
        a=embedded_table('test_real_xd_f1.py','M3_G1_CONSUMERS_AUDIT');old=M3_ADDITIONAL_CONSUMERS_AUDIT['G1']
        digest=hashlib.sha256(json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        self.assertEqual(a['base_sha256'],digest)
        self.assertEqual((a['events'],a['fixture_sha256'],a['prior_receipt_sha256']),(old['events'],old['fixture_sha256'],old['receipt_sha256']))
        path=ROOT/'tests/fixtures'/a['fixture'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),a['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==a['id']);packet=ROOT/'validation'/case['source']['packet']
        self.assertEqual(hashlib.sha256(packet.read_bytes()).hexdigest(),a['packet_sha256']);self.assertEqual(json.loads(packet.read_text())['rows'],case['raw_rows'])
        rows=case['raw_rows'][:a['limit']];tool=compiler();_,_,bis=tool.foundation(rows,'106');parts=tool.components(rows,bis,None);units=tool.xd_records(parts,a['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual([tuple(u[k] for k in fields) for u in units],[u[:9] for u in a['units']])
        self.assertEqual(tuple(u[-1] for u in a['units']),old['published_counts'])
        return a,old,case,parts,units

    def test_g1_consumer_integer_roles_keep_two_same_level_cores_but_only_one_recursive_core(self):
        a,_,_,_,units=self._g1_consumers_source();tool=compiler()
        for spec in a['f1']+(a['tail'],a['auto']):tool.move_record(units,spec)
        for spec in a['f1']:
            start,end,kind,entry,triples,cores,proof=spec;lo,hi=cores[0]
            self.assertEqual((kind,entry,triples,proof),('consolidation',None,(start,),end+1))
            self.assertEqual((max(u['low_ticks'] for u in units[start:end+1]),min(u['high_ticks'] for u in units[start:end+1])),(lo,hi))
            self.assertTrue(units[proof]['low_ticks']<=hi and units[proof]['high_ticks']>=lo)
        self.assertEqual(a['auto_spans'],((0,2,6),))
        self.assertTrue(all(u['low_ticks']<=1066 and u['high_ticks']>=1027 for u in units[3:7]))
        self.assertGreater(units[7]['low_ticks'],1066)
        self.assertEqual(a['auto'][4:6],((0,),((1027,1066),)))
        self.assertIsNone(a['auto'][-1]);self.assertEqual(a['f2'],((0,1,'incomplete',None,(),(),None),))
        self.assertEqual(a['f1_first'],(924,1540));self.assertEqual(a['f1_evidence'],(4,7))

    def test_g1_new_F1_proof_boundaries_rebuild_raw_rows_without_merging_shared_BI126(self):
        a,_,case,_,_=self._g1_consumers_source();tool=compiler();observations=0
        counts=sorted({125,126,a['limit']}|{n for u in a['units'] for n in (u[-1]-1,u[-1])})
        for count in counts:
            observations+=1;rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
            self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
            p=tool.components(rows,bis,None);ready=[manual_xd_certificate_ready(p,e) for e in a['events']]
            size=next((i for i,ok in enumerate(ready) if not ok),8)
            self.assertEqual(size,sum(u[-1]<=count for u in a['units']))
            self.assertEqual(tuple(i for i,spec in enumerate(a['f1']) if size>spec[-1]),tuple(i for i,at in enumerate(a['f1_first']) if at<=count))
            for i,u in enumerate(a['units']):
                if count==u[-1]:
                    b=p[a['events'][i][3]]
                    self.assertEqual((b['end_ticks'],b['end_dt'],a['events'][i][3]==len(p)-1),a['publication_proofs'][i])
        self.assertEqual(observations,17)
        self.assertEqual((a['publication_proofs'][5][0],a['publication_proofs'][6][0]),(1155,1141))
        self.assertNotEqual(a['publication_proofs'][5][1],a['publication_proofs'][6][1])
        self.assertEqual(a['units'][5][-1],1535);self.assertEqual(a['units'][6][-1],1540)

    def test_g1_registered_window_does_not_inherit_early_first_point_or_full_source_tail(self):
        a,old,case,parts,units=self._g1_consumers_source()
        self.assertEqual((a['contract'],a['impact_contract']),('all_current',(0,'all_current',1623)))
        self.assertEqual((a['source_rows'],len(case['raw_rows'])-a['limit']),(1638,15))
        self.assertEqual((len(parts),len(parts[:-1])),(133,132))
        self.assertEqual(a['seed'],35);self.assertEqual((a['events'][0][0],units[0]['start_ticks']),(35,910))
        self.assertEqual(a['actual_observations'],((125,0,0),(126,0,0),(1623,8,2)))
        self.assertLess(case['first_point']['first_dt'],units[0]['start_dt'])
        self.assertLess(case['first_point']['first_raw_count'],old['local_counts'][0])
        self.assertEqual((old['actual_prefixes'],case['formation']['resolution']['first_raw_count']),((125,126,1623),1623))
        for flag in ('source_origin_bridge_proven','seed0_seed1_resolved','production_merged'):self.assertFalse(a[flag])

    def _expanded_suffix_source(self,key):
        a=embedded_table('test_real_xd_f1.py','M3_EXPANDED_SUFFIX_AUDIT')[key]
        base=(embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')['S3_recent10'] if key=='S3' else M3_EXPANDED_FIRST_AUDIT['T_day'])
        digest=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest();self.assertEqual(a['base_sha256'],digest)
        self.assertEqual(a['events'][:6] if key=='S3' else a['events'],base['events'] if key=='S3' else (base['parent'],base['target']))
        path=ROOT/'tests/fixtures'/a['fixture'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),a['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==a['id']);tool=compiler();rows=case['raw_rows'][:max(a['bounds'].values())]
        _,_,bis=tool.foundation(rows,'106');self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])]);p=tool.components(rows,bis,None);units=tool.xd_records(p,a['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi')
        self.assertEqual([tuple(u[k] for k in fields) for u in units],list(a['units']))
        return a,case,p,units

    @staticmethod
    def _expanded_suffix_ready(parts,a,key):
        ready=[manual_xd_certificate_ready(parts,e) for e in a['events']]
        if key=='S3':
            ready[3]=(len(parts)>42 and ready[2] and manual_xd_certificate_ready(parts,a['natural_reaction']) and
                      max(parts[i]['end_ticks'] for i in range(37,43,2))<=parts[36]['start_ticks'] and
                      max(u['low_ticks'] for u in parts[36:39])<=min(u['high_ticks'] for u in parts[36:39]))
        elif len(parts)>59:
            ready[1]=(ready[0] and manual_xd_certificate_ready(parts,a['natural_reaction']) and
                      max(parts[i]['end_ticks'] for i in range(41,60,2))<=parts[40]['start_ticks'])
        return ready

    def test_expanded_S3_T_all_actual_raw_clocks_bind_natural_reactions_and_first_proof_prices(self):
        total=0;prefixes=0;tool=compiler()
        for key in ('S3','T'):
            a,case,_,_=self._expanded_suffix_source(key);seen={c:{} for c in a['bounds']}
            for count in range(1,max(a['bounds'].values())+1):
                prefixes+=1;rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106')
                self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
                for contract in a['bounds']:
                    if count>a['bounds'][contract]:continue
                    total+=1;p=tool.components(rows,bis if contract=='current' else bis[:-1],None);ready=self._expanded_suffix_ready(p,a,key);clock=a['clocks'][contract]
                    self.assertEqual(ready,[at<=count for at in clock['local']])
                    size=next((i for i,ok in enumerate(ready) if not ok),len(ready));self.assertEqual(size,sum(at<=count for at in clock['published']))
                    for i in range(size):
                        if i in seen[contract]:continue
                        seen[contract][i]=count;b=p[a['events'][i][3]]
                        self.assertEqual((b['end_ticks'],b['end_dt'],contract=='current' and a['events'][i][3]==len(p)-1),clock['publication_proofs'][i])
            for contract,c in a['clocks'].items():
                self.assertEqual(tuple(seen[contract][i] for i in range(len(a['units']))),c['published'])
                self.assertEqual(c['f1_first'],tuple(c['published'][s[-1]] for s in a['f1']))
                self.assertEqual(c['f1_evidence'],tuple(sum(at<=n for at in c['published']) for n in c['f1_first']))
        self.assertEqual((prefixes,total),(2029,3378))

    def test_expanded_S3_parent_second_sequence_does_not_complete_child_first_sequence(self):
        a,_,parts,_=self._expanded_suffix_source('S3')
        parent=manual_gap_lifecycle(parts,105,150,164);child=manual_gap_lifecycle(parts,150,161,164)
        self.assertEqual((parent['state'],parent['original_gap_ticks'],parent['second_fractal_proof_bi']),('confirmed',328,163))
        self.assertEqual((child['state'],child['original_gap_ticks'],child['first_fractal_proof_bi'],child['second_fractal_proof_bi']),('waiting',319,163,None))
        for mode in (1,2):self.assertFalse(manual_xd_certificate_ready(parts,(150,160,mode,163)))
        self.assertEqual(a['events'][-1],(105,149,2,163))
        for owner,turns in a['rejected'].items():
            for turn,cancel in turns.items():
                first=parts[turn];up=first['direction']=='up'
                broken=next(i for i in range(turn+1,len(parts),2) if (parts[i]['end_ticks']<first['start_ticks'] if up else parts[i]['end_ticks']>first['start_ticks']))
                self.assertEqual(broken,cancel)
                owner_up=parts[owner]['direction']=='up';left=manual_feature_nodes(parts,range(owner+1,turn,2),owner_up)[-1]
                gap=first['low_ticks']-left[1] if owner_up else left[0]-first['high_ticks']
                if gap>0:
                    lifecycle=manual_gap_lifecycle(parts,owner,turn,164)
                    self.assertEqual((lifecycle['state'],lifecycle['strict_revocation_bi']),('revoked',cancel))
                else:
                    self.assertTrue(all(parts[i]['end_ticks']<=first['end_ticks'] if up else parts[i]['end_ticks']>=first['end_ticks'] for i in range(turn+2,cancel+1,2)))
        self.assertEqual(manual_gap_lifecycle(parts,154,161,164)['state'],'waiting')
        self.assertFalse(manual_xd_certificate_ready(parts,a['events'][3]))
        self.assertTrue(manual_xd_certificate_ready(parts,a['natural_reaction']))

    def test_expanded_given_suffix_integer_F1_auto_roles_and_T_actual_cap_remain_distinct(self):
        tool=compiler()
        for key in ('S3','T'):
            a,case,parts,units=self._expanded_suffix_source(key)
            for spec in a['f1']+(a['tail'],)+a['auto']:tool.move_record(units,spec)
            for spec,spans in zip(a['auto'],a['auto_spans']):
                for j,(start,formed,last) in enumerate(spans):
                    lo,hi=spec[5][j];self.assertEqual((max(u['low_ticks'] for u in units[start:formed+1]),min(u['high_ticks'] for u in units[start:formed+1])),(lo,hi))
                    self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in units[formed+1:last+1]))
            self.assertFalse(a['source_origin_bridge_proven']);self.assertFalse(a['production_merged'])
            if key=='S3':self.assertEqual((a['bounds'],a['impact_contracts']),({'current':1349,'fixed':1350},((6,'all_current',1349),(7,'fixed_without_active',1350))))
            else:
                self.assertEqual((a['bounds'],a['impact_contracts']),({'current':679},((8,'all_current',679),)))
                self.assertEqual(len(case['raw_rows'])-679,47);self.assertEqual((len(parts),len(parts[67:])),(69,2))
                self.assertTrue(manual_xd_certificate_ready(parts,a['natural_reaction']))
                self.assertFalse(manual_xd_certificate_ready(parts,a['events'][1]))
                self.assertTrue(manual_xd_certificate_ready(parts,(31,39,1,64)))
                self.assertEqual(manual_gap_lifecycle(parts,40,57,68)['state'],'revoked')

    def _m1_full_suffix_source(self):
        a=embedded_table('test_real_xd_f1.py','M3_M1_FULL_SUFFIX_AUDIT');base=M3_EXPANDED_FIRST_AUDIT['M1_30m']
        digest=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest();self.assertEqual(a['base_sha256'],digest)
        self.assertEqual(a['events'][:2],(base['parent'],base['target']))
        path=ROOT/'tests/fixtures'/a['fixture'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),a['fixture_sha256'])
        case=next(c for c in json.loads(path.read_text())['cases'] if c['id']==a['id']);tool=compiler();_,_,bis=tool.foundation(case['raw_rows'],'106');self.assertEqual(tool.records(bis),case['foundation']['bis']);parts=tool.components(case['raw_rows'],bis,None);units=tool.xd_records(parts,a['events'])
        fields=('direction','start_dt','end_dt','start_ticks','end_ticks','low_ticks','high_ticks','mode','proof_bi');self.assertEqual([tuple(u[k] for k in fields) for u in units],list(a['units']))
        return a,case,parts,units

    @staticmethod
    def _m1_full_suffix_ready(parts,a):
        ready=[manual_xd_certificate_ready(parts,e) for e in a['events']]
        ready[24]=(len(parts)>285 and ready[23] and manual_xd_certificate_ready(parts,a['natural_reaction']) and max(parts[i]['end_ticks'] for i in range(280,286,2))<=parts[279]['start_ticks'])
        return ready

    def test_m1_full_suffix_both_raw_clocks_and_first_proof_prices_use_actual_caps(self):
        a,case,_,_=self._m1_full_suffix_source();tool=compiler();seen={k:{} for k in a['bounds']};total=0
        for count in range(1,3979):
            rows=case['raw_rows'][:count];_,_,bis=tool.foundation(rows,'106');self.assertEqual(tool.records(bis[:-1]),case['foundation']['bis'][:len(bis[:-1])])
            for contract in a['bounds']:
                if count>a['bounds'][contract]:continue
                total+=1;p=tool.components(rows,bis if contract=='current' else bis[:-1],None);ready=self._m1_full_suffix_ready(p,a);clock=a['clocks'][contract]
                self.assertEqual(ready,[at<=count for at in clock['local']]);size=next((i for i,ok in enumerate(ready) if not ok),28);self.assertEqual(size,sum(at<=count for at in clock['published']))
                for i in range(size):
                    if i in seen[contract]:continue
                    seen[contract][i]=count;b=p[a['events'][i][3]];self.assertEqual((b['end_ticks'],b['end_dt'],contract=='current' and a['events'][i][3]==len(p)-1),clock['publication_proofs'][i])
        self.assertEqual(total,7920)
        for contract,c in a['clocks'].items():
            self.assertEqual(tuple(seen[contract][i] for i in range(28)),c['published'])
            self.assertEqual(c['f1_first'],tuple(c['published'][s[-1]] for s in a['f1']))
            self.assertEqual(c['f1_evidence'],tuple(sum(at<=n for at in c['published']) for n in c['f1_first']))
            self.assertEqual(c['candidate_raw'],tuple((size,c['published'][size-1]) for size in a['candidates']))
        self.assertEqual(a['impact_contracts'],((4,'all_current',3942),(5,'fixed_without_active',3978)))
        self.assertEqual(a['bounds']['fixed']-a['bounds']['current'],36)

    def test_m1_given38_integer_F1_F2_auto_and_candidate_windows_keep_separate_roles(self):
        a,_,_,units=self._m1_full_suffix_source();tool=compiler()
        for spec in a['f1']+(a['tail'],)+a['auto']:tool.move_record(units,spec)
        types=[tool.move_record(units,s) for s in a['f1']]
        for spec in a['f2']:self.assertFalse(tool.move_record(types,spec)['complete'])
        for spec,spans in zip(a['auto'],a['auto_spans']):
            for j,(start,formed,last) in enumerate(spans):
                lo,hi=spec[5][j];self.assertEqual((max(u['low_ticks'] for u in units[start:formed+1]),min(u['high_ticks'] for u in units[start:formed+1])),(lo,hi))
                self.assertTrue(all(u['low_ticks']<=hi and u['high_ticks']>=lo for u in units[formed+1:last+1]))
        self.assertEqual(a['auto'][0][-1],8);self.assertIsNone(a['auto'][1][-1])
        for size,c in a['candidates'].items():
            self.assertEqual((c['reference'],c['leave']),((14,),(size-1,)))
            self.assertEqual(min(u['low_ticks'] for u in units[15:size-1])-max(u['high_ticks'] for u in units[6:14]),48)
            self.assertEqual(max(u['high_ticks'] for u in units[6:size-1]),1202);self.assertLess(units[size-1]['high_ticks'],1202)
        self.assertEqual(a['f2_spans'],(((1,3,4),(5,7,7)),))

    def test_m1_complete_standard_left_rejections_and_natural_proof_do_not_splice_recent266(self):
        a,_,parts,_=self._m1_full_suffix_source()
        for i,e in enumerate(a['events']):
            if i==24:self.assertFalse(manual_xd_certificate_ready(parts,e))
            else:self.assertTrue(manual_xd_certificate_ready(parts,e))
        self.assertTrue(manual_xd_certificate_ready(parts,a['natural_reaction']))
        for owner,turns in a['rejected'].items():
            for turn,cancel in turns.items():
                first=parts[turn];owner_up=parts[owner]['direction']=='up';left=manual_feature_nodes(parts,range(owner+1,turn,2),owner_up)[-1]
                gap=first['low_ticks']-left[1] if owner_up else left[0]-first['high_ticks']
                if gap>0:
                    lifecycle=manual_gap_lifecycle(parts,owner,turn,a['events'][-1][3]);self.assertEqual((lifecycle['state'],lifecycle['strict_revocation_bi']),('revoked',cancel))
                else:
                    up=first['direction']=='up';self.assertTrue(all(parts[i]['end_ticks']<=first['end_ticks'] if up else parts[i]['end_ticks']>=first['end_ticks'] for i in range(turn+2,cancel+1,2)))
        for owner,turns in a['excluded'].items():
            for turn in turns:
                up=parts[owner]['direction']=='up';left=manual_feature_nodes(parts,range(owner+1,turn,2),up)[-1];self.assertFalse(parts[turn]['high_ticks']>left[1] if up else parts[turn]['low_ticks']<left[0])
        recent=embedded_table('test_real_xd_f1.py','M3_CONDITIONAL_F1_ADMISSION_AUDIT')['M1_recent266']
        self.assertEqual((a['events'][22][0],recent['seed']),(264,266))
        self.assertEqual((parts[264]['start_ticks'],parts[266]['start_ticks']),(1016,1019))
        self.assertTrue(manual_xd_certificate_ready(parts,(264,270,1,273)));self.assertTrue(manual_xd_certificate_ready(parts,(266,270,1,273)))
        self.assertFalse(a['source_origin_bridge_proven']);self.assertFalse(a['production_merged'])


if __name__ == '__main__':
    unittest.main()
