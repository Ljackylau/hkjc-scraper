import unittest,copy
from unittest.mock import patch
from collector import choose,empty_meeting,parse_meiji,safe_horses,official_result,parse_dividends,collect_manual
class Rules(unittest.TestCase):
 def setUp(self):
  capture=patch('collector.capture_four');capture.start();self.addCleanup(capture.stop)
  self.r=empty_meeting({'date':'2026-10-14','venue':'HV','races':[{'race':1,'off':'2026-10-14T18:35:00+08:00','horses':[{'no':n,'name':str(n)} for n in range(1,13)]}]})['races'][0]
  for k in self.r['tips']:self.r['tips'][k]={'status':'absent','horses':[]}
  self.r['tips']['meiji']={'status':'ready','horses':[{'no':n,'name':str(n)} for n in [3,7,10,11]]}
 def test_zero_ignores_index_without_initial(self):
  choose(self.r);self.assertEqual(self.r['score'],0);self.assertIsNone(self.r['selection'])
  self.r['index']['horses']=[{'no':n,'name':str(n)} for n in [5,8,3,1]];choose(self.r);self.assertIsNone(self.r['selection']);self.assertEqual(self.r['hv_plan_state'],'pending')
 def test_one_duplicate(self):
  self.r['tips']['ball']={'status':'ready','horses':[{'no':3,'name':'3'}]};choose(self.r);self.assertEqual([h['no'] for h in self.r['selection']['horses']],[3])
 def test_same_horse_two_experts_counts_two(self):
  for k in ['ball','ma']:self.r['tips'][k]={'status':'ready','horses':[{'no':3,'name':'3'}]}
  choose(self.r);self.assertEqual(self.r['score'],2);self.assertEqual(self.r['selection']['main'],['QP'])
 def test_unknown_not_zero(self):
  self.r['tips']['ma']['status']='error';choose(self.r);self.assertIsNone(self.r['score'])
 def test_locked_no_reselection(self):
  self.r['locked']=True;self.r['score']=1;choose(self.r);self.assertEqual(self.r['score'],1)
 def test_stale_date_rejected(self):
  date,rows=parse_meiji('<div>賽事日期：11/10/2026 明治朗貼士 第1場 3馬甲 7馬乙 10馬丙 11馬丁</div>','2026-10-14');self.assertEqual(rows,{})
 def test_wrong_horse_rejected(self):
  with self.assertRaises(ValueError):safe_horses([{'no':3,'name':'另一匹'}],self.r)
 def test_archive_single_bad_glyph_repaired_with_evidence(self):
  r={'horses':[{'no':6,'name':'綫路英雄'}]}
  h=safe_horses([{'no':6,'name':'?路英雄'}],r)[0]
  self.assertEqual(h['name'],'綫路英雄');self.assertEqual(h['source_name'],'?路英雄')
 def test_result_date_navigation_cannot_validate_wrong_selected_date(self):
  markup='<div>賽事日期: 09/09/2026 06/09/2026 第1場</div><div class="performance"><table><tbody></tbody></table></div>'
  with patch('collector.request',return_value=markup):
   with self.assertRaises(ValueError):official_result({'date':'2026-09-06','venue':'ST'},{'race':1,'horses':[]})
 def test_dividend_rowspan_and_pool_boundary(self):
  from bs4 import BeautifulSoup
  html='<table><tr><td>獨贏</td><td>3</td><td>82.50</td></tr><tr><td>位置</td><td>3</td><td>26.00</td></tr><tr><td>7</td><td>40.00</td></tr><tr><td>連贏</td><td>3,7</td><td>574.50</td></tr><tr><td>位置Q</td><td>3,7</td><td>174.00</td></tr><tr><td>二重彩</td><td>3,7</td><td>1,107.00</td></tr></table>'
  d=parse_dividends(BeautifulSoup(html,'html.parser').table)
  self.assertEqual(len(d['P']),2);self.assertEqual(d['W'][0]['dividend_hkd'],82.5);self.assertEqual(len(d['QP']),1)
 def test_manual_preserves_locked_and_automatic_check(self):
  from datetime import datetime
  m=empty_meeting({'date':'2026-10-14','venue':'HV','races':[copy.deepcopy(self.r)]})
  m['races'][0]=copy.deepcopy(self.r);m['tips_checked_at']=None
  locked=copy.deepcopy(self.r);locked['race']=2;locked['locked']=True;m['races'].append(locked)
  previous=copy.deepcopy(locked)
  def fetch(candidate):
   self.assertEqual([r['race'] for r in candidate['races']],[1])
   candidate['tips_checked_at']='automatic-temporary'
   candidate['races'][0]['tips']['ball']={'status':'ready','horses':[{'no':3,'name':'3'}]}
  with patch('collector.now',return_value=datetime.fromisoformat('2026-10-13T19:00:00+08:00')),patch('collector.collect_tips',side_effect=fetch):collect_manual(m)
  self.assertIsNone(m['tips_checked_at']);self.assertEqual(m['races'][1],previous)
  self.assertEqual(m['races'][0]['tips']['ball']['horses'][0]['no'],3)
  self.assertEqual(len(m['manual_checks']),1)
 def test_manual_failures_keep_previous_valid_tips(self):
  from datetime import datetime
  m=empty_meeting({'date':'2026-10-14','venue':'HV','races':[copy.deepcopy(self.r)]});m['races'][0]=copy.deepcopy(self.r)
  previous=copy.deepcopy(m['races'][0]['tips'])
  def fetch(candidate):
   for tip in candidate['races'][0]['tips'].values():tip['status']='error'
  with patch('collector.now',return_value=datetime.fromisoformat('2026-10-13T19:00:00+08:00')),patch('collector.collect_tips',side_effect=fetch):collect_manual(m)
  self.assertEqual(m['races'][0]['tips'],previous);self.assertEqual(len(m['manual_checks'][0]['errors']),4)
if __name__=='__main__':unittest.main()

class MissingMeijiRetry(unittest.TestCase):
 def test_retry_updates_only_open_incomplete_races(self):
  import collector
  from datetime import datetime
  t=datetime.fromisoformat('2026-10-21T18:45:00+08:00')
  meeting={'date':'2026-10-21','races':[
   {'race':1,'off':'2026-10-21T18:40:00+08:00','tips':{'meiji':{'status':'pending'}}},
   {'race':2,'off':'2026-10-21T19:10:00+08:00','tips':{'meiji':{'status':'ready','source_date':'2026-10-21','horses':[{'no':9}]}}},
   {'race':3,'off':'2026-10-21T19:40:00+08:00','tips':{'meiji':{'status':'error'}}}]}
  before=copy.deepcopy(meeting)
  with patch('collector.now',return_value=t),patch('collector.stamp',return_value=t.isoformat()),patch('collector.request',return_value='source'),patch('collector.parse_meiji',return_value=('2026-10-21',{1:[{'no':1}],2:[{'no':2}],3:[{'no':3}]})),patch('collector.safe_horses',side_effect=lambda h,r:h),patch('collector.choose') as choose:
   collector.retry_missing_meiji(meeting)
  self.assertEqual(meeting['races'][:2],before['races'][:2])
  self.assertEqual(meeting['races'][2]['tips']['meiji']['horses'],[{'no':3}])
  self.assertEqual(choose.call_count,1)
