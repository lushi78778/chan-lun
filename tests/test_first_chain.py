# -*- coding: utf-8 -*-
"""课24/27/101/108: 自动辅助一类与两个不同归属中枢, 实际证据时间。"""
import unittest
from datetime import datetime,timedelta
from chan import (ConfirmedMove, ConfirmedMoveType, ConfirmedCenter, find_first_points, scan_first_points,
                  first_point_contexts, analyze_point_chain)

PRICES=[120,110,115,108,114,90,95,88,94,70,74,68,72,67,69,65,76,70,78,75,82,76,86]
T=datetime(2025,1,1)
def sample(prices=PRICES,n=20):
 rows=[];units=[]
 for i,(a,b) in enumerate(zip(prices,prices[1:])):
  for j in range(n):
   dt=T+timedelta(hours=i*n+j);p=a+(b-a)*j/n
   rows.append(dict(dt=dt,open=p,high=p,low=p,close=p,volume=100.,closed_dt=dt,available_dt=dt+timedelta(minutes=1)))
  s=T+timedelta(hours=i*n);e=T+timedelta(hours=(i+1)*n)
  units.append(ConfirmedMove('u%d'%i,'base','up' if b>a else 'down',s,e,a,b,min(a,b),max(a,b),e+timedelta(minutes=2)))
 dt=T+timedelta(hours=(len(prices)-1)*n);p=prices[-1]
 rows.append(dict(dt=dt,open=p,high=p,low=p,close=p,volume=100.,closed_dt=dt,available_dt=dt+timedelta(minutes=1)))
 return units,rows,dt+timedelta(days=1)

class TestAutomaticFirstChain(unittest.TestCase):
    def test_buy_and_opposite_mirror(self):
        """两个严格分离中枢、B回零与C减弱; 上涨镜像给卖一。"""
        for mirror in (False,True):
            u,b,now=sample([200-p for p in PRICES] if mirror else PRICES)
            point=find_first_points(u,b,now,'main')[0]
            self.assertEqual(point.kind,'sell1' if mirror else 'buy1')
            self.assertEqual(point.reference_ids,('u8',))
            self.assertEqual(point.leave_ids,('u12','u13','u14'))
            self.assertGreater(point.reference_area,point.leave_area)
            self.assertGreater(point.confirmed_dt,point.dt)
            self.assertEqual(point.method,'macd_area')

    def test_no_future_endpoint_confirmation(self):
        """C已到达但趋势完成证据未到达, 不将候选回填C端点。"""
        u,b,now=sample()
        self.assertEqual(find_first_points(u,b,u[14].confirmed_dt,'main'),[])
        self.assertEqual(len(find_first_points(u,b,u[15].confirmed_dt,'main')),1)

    def test_every_arrival_prefix_is_stable(self):
        """粗观察与逐到达等价; 辅助面积不吸收C之后未来价格。"""
        u,b,now=sample();old=set()
        for i,unit in enumerate(u):
            cutoff=unit.confirmed_dt
            points=find_first_points(u,b,cutoff,'main')
            short=[r for r in b if r['available_dt']<=cutoff]
            self.assertEqual(points,find_first_points(u[:i+1],short,cutoff,'main'))
            self.assertTrue(old.issubset(set(points)));old=set(points)

    def test_future_poison_not_read(self):
        """未来身份/级别/价格和行情close毒值不会影响已确认结果。"""
        u,b,now=sample();cutoff=u[15].confirmed_dt
        poison=u[16]._replace(move_id=None,level=None,low=None,start_price=float('nan'))
        poisoned=[dict(r,close=None,low=None) if r['available_dt']>cutoff else r for r in b]
        self.assertEqual(find_first_points(u[:16]+[poison],poisoned,cutoff,'main'),
                         find_first_points(u[:16],b,cutoff,'main'))

    def test_zero_axis_is_explicit_quantification(self):
        """B未达到所设零轴阈值时不判; 不偷用后续EMA回零。"""
        u,b,now=sample()
        self.assertEqual(find_first_points(u,b,now,'main',0.),[])
        for invalid in (-1,float('nan'),True):
            with self.assertRaises(ValueError):find_first_points(u,b,now,'main',invalid)

    def test_single_center_is_not_first_point(self):
        """课27单中枢盘整背驰不能直接称本级一买。"""
        u,b,now=sample([120,110,115,108,114,90,94,88,116])
        self.assertEqual(find_first_points(u,b,now,'main'),[])

    def test_missing_endpoint_not_approximated(self):
        """原始端点没有行情时不使用附近一根代替。"""
        u,b,now=sample();b=[r for r in b if r['dt']!=u[8].end_dt]
        with self.assertRaises(ValueError):find_first_points(u,b,now,'main')

    def test_late_price_evidence_delays_confirmation(self):
        """实际价格到达比结构更迟, 最晚证据到达前无结果。"""
        u,b,now=sample();late=u[15].confirmed_dt+timedelta(hours=1)
        for r in b:
            if r['dt']>=u[14].end_dt:r['available_dt']=max(r['available_dt'],late)
        self.assertEqual(find_first_points(u,b,late-timedelta(seconds=1),'main'),[])
        self.assertEqual(find_first_points(u,b,late,'main')[0].confirmed_dt,late)

    def test_two_center_roles_and_first_formation_are_fixed(self):
        """课101原下跌末中枢与课108一买引发中枢分开, 延伸不回写边界。"""
        u,b,now=sample();point=find_first_points(u,b,now,'main')[0]
        contexts=first_point_contexts(u,[point],now,'main');c=contexts[0]
        self.assertEqual((c.previous_center.zd,c.previous_center.zg),(70,72))
        self.assertEqual((c.causal_center.zd,c.causal_center.zg),(70,76))
        self.assertNotEqual(c.previous_center.center_id,c.causal_center.center_id)
        self.assertEqual(c.causal_center.confirmed_dt,u[17].confirmed_dt)
        early=first_point_contexts(u,[point],u[17].confirmed_dt,'main')[0]
        self.assertEqual(c.causal_center,early.causal_center)

    def test_center_wait_and_no_future_point(self):
        """第三段未确认时中枢为空; 未来点位价格不读取。"""
        u,b,now=sample();point=find_first_points(u,b,now,'main')[0]
        c=first_point_contexts(u,[point],u[16].confirmed_dt,'main')[0]
        self.assertIsNone(c.causal_center)
        poison=point._replace(price=None,center=None,confirmed_dt=now+timedelta(days=1))
        self.assertEqual(first_point_contexts(u,[poison],now,'main'),[])

    def test_complete_chain_to_third_and_bottom(self):
        """引发中枢首次三买结束底部构造, 不靠调用方手工填center_id。"""
        u,b,now=sample();chain=analyze_point_chain(u,b,now,'main')
        self.assertEqual([p.kind for p in chain.first_points],['buy1'])
        self.assertEqual([p.kind for p in chain.second_points],['buy2'])
        self.assertEqual([p.kind for p in chain.third_points],['buy3'])
        self.assertEqual(chain.formations[0].phase,'completed')
        self.assertEqual(chain.formations[0].end_dt,u[20].confirmed_dt)
        self.assertEqual(chain.contexts[0].second_context.ended_dt,chain.formations[0].end_dt)

    def test_top_and_failed_bottom(self):
        """课108镜像顶部完成及底部先三卖的失败分支。"""
        u,b,now=sample([200-p for p in PRICES]);chain=analyze_point_chain(u,b,now,'main')
        self.assertEqual((chain.formations[0].kind,chain.formations[0].phase),('top','completed'))
        u,b,now=sample(PRICES[:19]+[73,67,69,63])
        chain=analyze_point_chain(u,b,now,'main')
        self.assertEqual([p.kind for p in chain.third_points],['sell3'])
        self.assertEqual(chain.formations[0].phase,'failed')

    def test_identity_level_and_anchor_validation(self):
        """不同级别、重复身份和锚点错接不能拼出因果中枢。"""
        u,b,now=sample();p=find_first_points(u,b,now,'main')[0]
        for points in ([p,p],[p._replace(sub_level='other')],[p._replace(price=64)]):
            with self.assertRaises(ValueError):first_point_contexts(u,points,now,'main')

    def test_nonprefix_price_arrival_rejected(self):
        """迟到历史缺口可能重算EMA, 必须声明新版本, 不能跳过缺口。"""
        u,b,now=sample();b[20]['available_dt']=now+timedelta(days=1)
        with self.assertRaises(ValueError):find_first_points(u,b,now,'main')

    def test_flat_type_is_reported_without_joining_across_it(self):
        """平端点是有效走势类型, 不能猜方向; 先前有效点保留且诊断可见。"""
        u,b,now=sample(PRICES+[PRICES[-1]])
        flat=u[-1]
        u[-1]=ConfirmedMoveType(flat.move_id,'base','consolidation',None,
            flat.start_dt,flat.end_dt,flat.start_price,flat.end_price,
            flat.low,flat.high,flat.confirmed_dt,('part',),('part',),((flat.low,flat.high),))
        chain=analyze_point_chain(u,b,now,'main')
        self.assertEqual(chain.unresolved_move_ids,(flat.move_id,))
        self.assertEqual([p.kind for p in chain.third_points],['buy3'])

    def test_flat_pull_blocks_later_points_in_this_cycle(self):
        """首次回试无法表达方向时不能绕过它找后面同向回试。"""
        prices=PRICES[:17]+[PRICES[16]]+PRICES[17:]
        u,b,now=sample(prices);flat=u[16]
        u[16]=ConfirmedMoveType(flat.move_id,'base','consolidation',None,
            flat.start_dt,flat.end_dt,flat.start_price,flat.end_price,
            flat.low,flat.high,flat.confirmed_dt,('part',),('part',),((flat.low,flat.high),))
        chain=analyze_point_chain(u,b,now,'main')
        self.assertEqual(len(chain.first_points),1)
        self.assertEqual(chain.second_points,[])
        self.assertEqual(chain.third_points,[])
        self.assertEqual(chain.formations[0].phase,'constructing')

    def test_negative_scan_keeps_the_actual_rejected_condition(self):
        """没有一类候选时仍区分趋势完成数与具体条件排除, 不混作无数据。"""
        u,b,now=sample()
        scan=scan_first_points(u,b,now,'main',0.)
        self.assertEqual(scan.points,[])
        self.assertGreater(scan.completed_types,0)
        self.assertIn('no_zero_axis_pull',[reason for identity,reason in scan.exclusions])
