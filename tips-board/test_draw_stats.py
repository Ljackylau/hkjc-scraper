import copy,tempfile,unittest
from datetime import datetime
from unittest.mock import patch
from draw_stats import rank,parse_result,card_draw
from collector import Store,empty_meeting,run,collect_manual,reconcile
from bs4 import BeautifulSoup
class Draws(unittest.TestCase):
 def setUp(self):
  self.m={'date':'2026-10-19','venue':'ST'}
  self.r={'race':1,'distance':1200,'track':'TURF','rail':'A','horses':[{'no':1,'name':'甲','draw':8},{'no':2,'name':'乙','draw':2},{'no':3,'name':'丙','draw':4}],'scratched':[]}
  self.history=[{'date':'2026-09-06','venue':'ST','race':1,'distance':1200,'track':'TURF','rail':'A','runners':[{'draw':8,'top3':True},{'draw':2,'top3':False},{'draw':4,'top3':True}]}]
 def test_actual_draw_not_saddle(self):
  out=rank(self.m,self.r,self.history);self.assertEqual([h['no'] for h in out['horses']],[1,3,2]);self.assertEqual(out['horses'][0]['draw'],8)
 def test_cutoff_september_prior_day_and_exact_conditions(self):
  other=[]
  for changes in [{'date':'2026-08-31'},{'date':self.m['date']},{'date':'2026-10-20'},{'venue':'HV'},{'distance':1000},{'rail':'B'},{'track':'AWT'}]:other.append({**self.history[0],**changes})
  out=rank(self.m,self.r,self.history+other+self.history);self.assertEqual(out['horses'][0]['starts'],1)
 def test_missing_draw_pending_and_withdrawal(self):
  r=copy.deepcopy(self.r);del r['horses'][0]['draw'];self.assertEqual(rank(self.m,r,self.history)['status'],'pending')
  r['scratched']=[1];self.assertEqual([x['no'] for x in rank(self.m,r,self.history)['horses']],[3,2])
 def test_no_prior_history_is_empty(self):self.assertEqual(rank(self.m,self.r,[])['horses'],[])
 def test_card_column_identity(self):
  soup=BeautifulSoup('<table><tr><td>馬號</td><td>檔位</td></tr><tr><td>1</td><td>8</td></tr></table>','html.parser')
  self.assertEqual(card_draw(soup.select('tr')[1]),{'draw':8})
 def test_live_and_manual_never_fetch_index_or_results(self):
  date='2026-10-19';m=empty_meeting({'date':date,'venue':'ST','races':[{**self.r,'date':date,'venue':'ST','off':date+'T12:30:00+08:00'}]})
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.write(date+'.json',m);s.write('latest.json',m)
   with patch('collector.now',return_value=datetime.fromisoformat(date+'T12:34:00+08:00')),patch('collector.prepare_draws',return_value=[]),patch('collector.capture_four'),patch('collector.capture_index',side_effect=AssertionError('Index disabled')),patch('collector.official_result',side_effect=AssertionError('Results disabled')):
    run(s,date,'live');out=s.read(date+'.json');self.assertTrue(out['races'][0]['locked']);self.assertIsNone(out['races'][0]['result']);self.assertFalse(out['collection_policy']['results']);collect_manual(out);reconcile(s)
