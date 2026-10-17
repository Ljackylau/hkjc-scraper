import copy,tempfile,unittest
from datetime import datetime
from unittest.mock import patch
from draw_stats import rank,parse_result,card_draw
from collector import Store,empty_meeting,run,collect_manual,reconcile
from bs4 import BeautifulSoup
class Draws(unittest.TestCase):
 def setUp(self):
  self.m={'date':'2026-10-19','venue':'ST'}
  self.r={'race':1,'distance':1200,'track':'TURF','rail':'A','horses':[{'no':1,'name':'甲','draw':8,'jockey_id':'A','jockey':'甲騎'},{'no':2,'name':'乙','draw':2,'jockey_id':'B','jockey':'乙騎'},{'no':3,'name':'丙','draw':4,'jockey_id':'C','jockey':'丙騎'}],'scratched':[]}
  self.history=[{'date':'2026-09-06','venue':'ST','race':1,'distance':1200,'track':'TURF','rail':'A','runners':[{'draw':8,'jockey_id':'A','top3':True},{'draw':2,'jockey_id':'B','top3':False},{'draw':4,'jockey_id':'C','top3':True}]}]
 def test_actual_draw_not_saddle(self):
  out=rank(self.m,self.r,self.history);self.assertEqual([h['no'] for h in out['riders']],[1,3,2]);self.assertEqual(out['riders'][0]['draw'],8)
 def test_cutoff_september_prior_day_and_exact_conditions(self):
  other=[]
  for changes in [{'date':'2026-08-31'},{'date':self.m['date']},{'date':'2026-10-20'}]:other.append({**self.history[0],**changes})
  out=rank(self.m,self.r,self.history+other+self.history);self.assertEqual(out['riders'][0]['starts'],1)
 def test_missing_draw_pending_and_withdrawal(self):
  r=copy.deepcopy(self.r);del r['horses'][0]['draw'];self.assertEqual(rank(self.m,r,self.history)['status'],'pending')
  r['scratched']=[1];self.assertEqual([x['no'] for x in rank(self.m,r,self.history)['riders']],[3,2])
 def test_no_prior_history_is_empty(self):self.assertEqual(rank(self.m,self.r,[])['riders'],[])
 def test_card_column_identity(self):
  soup=BeautifulSoup('<table><tr><td>馬號</td><td>檔位</td></tr><tr><td>1</td><td>8</td></tr></table>','html.parser')
  self.assertEqual(card_draw(soup.select('tr')[1]),{'draw':8})
 def test_live_and_manual_never_fetch_index_or_results(self):
  date='2026-10-19';m=empty_meeting({'date':date,'venue':'ST','races':[{**self.r,'date':date,'venue':'ST','off':date+'T12:30:00+08:00'}]})
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.write(date+'.json',m);s.write('latest.json',m)
   with patch('collector.now',return_value=datetime.fromisoformat(date+'T12:34:00+08:00')),patch('collector.prepare_draws',return_value=[]),patch('collector.capture_four'),patch('collector.capture_index',side_effect=AssertionError('Index disabled')),patch('collector.official_result',side_effect=AssertionError('Results disabled')):
    run(s,date,'live');out=s.read(date+'.json');self.assertTrue(out['races'][0]['locked']);self.assertIsNone(out['races'][0]['result']);self.assertFalse(out['collection_policy']['results']);collect_manual(out);reconcile(s)

 def test_other_jockey_same_draw_and_same_jockey_other_draw_excluded(self):
  past=copy.deepcopy(self.history[0]);past['race']=2;past['runners']=[{'draw':8,'jockey_id':'OTHER','top3':False},{'draw':2,'jockey_id':'A','top3':False}]
  out=rank(self.m,self.r,self.history+[past]);a=next(h for h in out['riders'] if h['jockey_id']=='A');self.assertEqual((a['placed'],a['starts']),(1,1))

 def test_pools_venues_distances_tracks_and_rails(self):
  other=[]
  for i,changes in enumerate([{'venue':'HV'},{'distance':1000},{'track':'AWT'},{'rail':'B'}],2):
   other.append({**self.history[0],'race':i,**changes})
  out=rank(self.m,self.r,self.history+other)
  a=next(h for h in out['riders'] if h['jockey_id']=='A')
  self.assertEqual((a['placed'],a['starts']),(5,5))
  self.assertEqual(out['method_version'],'jockey_draw_only_v3')
 def test_rail_distance_track_and_venue_not_required(self):
  r=copy.deepcopy(self.r);r.pop('distance');r.pop('track');r.pop('rail')
  self.assertEqual(rank({'date':self.m['date']},r,self.history)['status'],'ready')
