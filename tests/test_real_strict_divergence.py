# -*- coding: utf-8 -*-
"""课24/27/37/61: R3 严格趋势背驰扫描与R2真实标注对比收据(0.10.3)。

输入为R2独立冻结的真实严格趋势标注单元(四fixture七样本, 人工表
经独立整数编译器冻结, 见test_real_strict_trend*.py)。本文件只消费
冻结单元表构造ConfirmedMove, 运行scan_strict_divergence, 将输出与
R2角色标注逐项对比并冻结为收据; 预期不调用识别器重新生成。

对比结论(2026-10-14冻结):

一致项: 四个输出candidate的样本(159915-day-20260101、
518880-day-20230101、159915-60m-20240101及其镜像方向)上,
separated_centers=True与R2人工gap>0一致; c departed后暂无
反向单元时leave_third_point=None与R2"进行中"一致; 确认时间
不早于最后消费证据。

已知差异(登记不判实现错误): R2 zn成员是人工声明结构(自动
搜索属R3), 本扫描用recurse自动分解, 两者中枢窗口不同——
512880-60m-20210101样本自动分解判定中枢波动重叠, R2人工
标注A/B gap>0且c departed, 该样本candidate在演进中随新
单元落入skipped; xd级两个样本自动分解无比较腿
(no_compare_legs), R2人工标注有完整a/A/b/B/c角色;
518880-5m样本完成切分后u0尾部候选落为最终语义, u29尾部
产生新候选身份。差异归因为分解口径, 次级确认与分解规格
收口前保留为已知差异, 不把自动分解输出冒充人工标注。
逐去重确认时刻截断等价与candidate身份不漂移在全部样本
通过。
"""
from datetime import datetime
import json
import os
import unittest

from chan import (ConfirmedMove, STRICT_CANDIDATE,
                  scan_strict_divergence)

FIXTURES = ('real_strict_trend.json', 'real_strict_trend_completed.json',
            'real_strict_trend_minute.json', 'real_strict_trend_5m.json')

# 末观察点冻结收据: case_id -> (statuses, reasons, completed, open_tail)
RECEIPT = {
    '159915-day-20260101-20260731':
        ((('candidate', 'trend_open'),), 0, True),
    '159915-day-20180101-20191231': ((), 2, True),
    '518880-day-20210101-20260731': ((), 0, True),
    '518880-day-20230101-20230630':
        ((('candidate', 'trend_open'),), 0, True),
    '512880-60m-20210101-20210331': ((), 0, True),
    '159915-60m-20240101-20250331':
        ((('candidate', 'trend_open'),), 0, True),
    '518880-5m-20260501-20260724': ((), 1, True),
}


def _parse(dt):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(dt, fmt)
        except ValueError:
            continue
    raise ValueError('无法解析冻结时间: %r' % dt)


def load_cases():
    """加载R2冻结单元表; 不重新生成预期、不调用编译器。"""
    base = os.path.dirname(__file__)
    out = []
    for name in FIXTURES:
        with open(os.path.join(base, 'fixtures', name),
                  encoding='utf-8') as stream:
            data = json.load(stream)
        for case in data['cases']:
            units = []
            for i, unit in enumerate(case['units']):
                units.append(ConfirmedMove(
                    'u%d' % i, case['level'], unit['direction'],
                    _parse(unit['start_dt']), _parse(unit['end_dt']),
                    unit['start_ticks'] / 1000.0,
                    unit['end_ticks'] / 1000.0,
                    unit['low_ticks'] / 1000.0,
                    unit['high_ticks'] / 1000.0,
                    _parse(unit['confirmed_dt'])))
            out.append((case, units))
    return out


class TestRealStrictDivergenceReceipt(unittest.TestCase):
    def test_final_scan_matches_frozen_receipt(self):
        """末观察点输出与冻结收据一致; candidate与R2方向一致。"""
        for case, units in load_cases():
            scan = scan_strict_divergence(
                units, units[-1].confirmed_dt, 'trend')
            expected = RECEIPT[case['id']]
            self.assertEqual(
                tuple((r.status, r.reason) for r in scan.results),
                expected[0], case['id'])
            self.assertEqual(scan.completed_types, expected[1], case['id'])
            self.assertEqual(scan.open_tail, expected[2], case['id'])
            for r in scan.results:
                self.assertEqual(r.status, STRICT_CANDIDATE, case['id'])
                # R2趋势方向与买卖语义一致: 上涨趋势输出sell1。
                self.assertEqual(
                    r.kind,
                    'sell1' if case['trend']['direction'] == 'up' else 'buy1',
                    case['id'])
                # 与R2人工gap>0一致: 中枢波动分离条件成立。
                self.assertIn(('separated_centers', True), r.conditions,
                              case['id'])
                # c departed且暂无反向单元: 三类回试条件未决。
                self.assertIn(('leave_third_point', None), r.conditions,
                              case['id'])

    def test_prefix_equivalence_every_confirmation(self):
        """逐去重确认时刻: 截断前缀与全量输入同观察时刻等价。

        冻结单元表存在同一时刻确认的多单元(如518880-5m u7/u8),
        观察网格按确认时刻去重, 截断前缀取该时刻全部已确认单元;
        未来单元不读取。
        """
        for case, units in load_cases():
            moments = []
            for unit in units:
                if not moments or moments[-1] != unit.confirmed_dt:
                    moments.append(unit.confirmed_dt)
            for cut in moments:
                prefix = [u for u in units if u.confirmed_dt <= cut]
                self.assertEqual(
                    scan_strict_divergence(prefix, cut, 'trend'),
                    scan_strict_divergence(units, cut, 'trend'),
                    (case['id'], cut))

    def test_candidate_identity_continuity(self):
        """candidate身份不漂移; 语义随前缀演进不回填。

        开放尾部条件随前缀演进: candidate可因尾部中枢结构变化
        暂不满足而落入skipped, 再随前缀恢复; 完成切分后新尾部
        起点产生新身份(如518880-5m u0尾部与u29尾部)。演进中
        出现过的身份记入集合, 末观察点candidate身份必须来自
        该集合(无凭空身份); 同身份不漂移由合成测试保证。
        """
        for case, units in load_cases():
            seen = set()
            moments = []
            for unit in units:
                if not moments or moments[-1] != unit.confirmed_dt:
                    moments.append(unit.confirmed_dt)
            for cut in moments:
                scan = scan_strict_divergence(units, cut, 'trend')
                current = [r for r in scan.results
                           if r.status == STRICT_CANDIDATE]
                if not current:
                    continue
                self.assertFalse(any(
                    r.status != STRICT_CANDIDATE for r in scan.results),
                    (case['id'], cut, 'candidate与非候选并存'))
                for r in current:
                    seen.add(r.divergence_id)
            final = scan_strict_divergence(
                units, units[-1].confirmed_dt, 'trend')
            for r in final.results:
                if r.status == STRICT_CANDIDATE:
                    self.assertIn(r.divergence_id, seen,
                                  (case['id'], '末点候选身份凭空出现'))

    def test_confirmation_not_before_evidence(self):
        """确认时间不早于任何被消费证据单元的确认时间。"""
        for case, units in load_cases():
            scan = scan_strict_divergence(
                units, units[-1].confirmed_dt, 'trend')
            for r in scan.results:
                consumed = [u for u in units
                            if u.move_id in r.reference_ids or
                            u.move_id in r.leave_ids]
                self.assertGreaterEqual(
                    r.confirmed_dt, max(u.confirmed_dt for u in consumed),
                    (case['id'], '确认早于证据'))
                self.assertLessEqual(r.dt, r.confirmed_dt,
                                     (case['id'], '端点晚于确认'))


if __name__ == '__main__':
    unittest.main()
