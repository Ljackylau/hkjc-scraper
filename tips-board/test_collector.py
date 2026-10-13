import unittest,copy
from unittest.mock import patch
from collector import choose,empty_meeting,parse_meiji,safe_horses,official_result,parse_dividends
class Rules(unittest.TestCase):
 def setUp(self):
  self.r=empty_meeting({'date':'2026-10-14','venue':'HV','races':[{'race':1,'off':'2026-10-14T18:35:00+08:00','horses':[{'no':n,'name':str(n)} for n in range(1,13)]}]})['races'][0]
  for k in self.r['tips']:self.r['tips'][k]={'status':'absent','horses':[]}
  self.r['tips']['meiji']={'status':'ready','horses':[{'no':n,'name':str(n)} for n in [3,7,10,11]]}
 def test_zero_needs_index(self):
  choose(self.r);self.assertEqual(self.r['score'],0);self.assertIsNone(self.r['selection'])
  self.r['index']['horses']=[{'no':n,'name':str(n)} for n in [5,8,3,1]];choose(self.r);self.assertEqual([h['no'] for h in self.r['selection']['horses']],[5,8])
 def test_one_duplicate(self):
  self.r['tips']['ball']={'status':'ready','horses':[{'no':3,'name':'3'}]};choose(self.r);self.assertEqual([h['no'] for h in self.r['selection']['horses']],[3,7])
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
if __name__=='__main__':unittest.main()
