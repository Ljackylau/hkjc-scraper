import copy,unittest
from jockey_top5 import rank,parse_result,context
class JockeyTop5Tests(unittest.TestCase):
 def setUp(self):
  self.m={'date':'2026-10-11','venue':'ST'}
  self.r={'race':2,'distance':1200,'track':'TURF','rail':'C','horses':[{'no':n,'jockey_id':str(n),'jockey':'騎師'+str(n)} for n in range(1,8)],'scratched':[7]}
 def past(self,date='2026-10-01',race=1,**changes):
  return {'date':date,'race':race,'venue':'ST','distance':1200,'track':'TURF','rail':'C','runners':[{'jockey_id':str(n),'top3':n%2==1} for n in range(1,8)],**changes}
 def test_cutoff_exact_conditions_and_current_riders(self):
  history=[self.past(),self.past('2026-10-11',1),self.past('2026-10-11',2),self.past('2026-10-11',3),self.past('2026-10-14'),self.past('2025-10-01'),self.past('2026-10-02',venue='HV'),self.past('2026-10-03',rail='B'),self.past('2026-10-04',distance=1000),self.past('2026-10-05',track='AWT')]
  result=rank(self.m,self.r,history+[history[0]])
  self.assertEqual([h['no'] for h in result['riders']],[1,3,5,2,4])
  self.assertTrue(all(h['starts']==2 for h in result['riders']))
  self.assertEqual(result['riders'][0]['rate'],1)
 def test_tie_break_by_sample_then_saddle_and_zero_sample(self):
  p=self.past();p['runners']=[{'jockey_id':'2','top3':True}]
  first=self.past('2026-09-01');first['runners']=[{'jockey_id':'1','top3':True},{'jockey_id':'2','top3':True}]
  x=rank(self.m,self.r,[first,p]);self.assertEqual([h['no'] for h in x['riders']],[2,1])
  self.assertEqual(rank(self.m,self.r,[])['riders'],[])
 def test_all_weather_context_and_missing_rail(self):
  self.assertEqual(context('1200米 賽道 : 全天候跑道'),{'distance':1200,'track':'AWT','rail':'AWT'})
  self.assertEqual(context('1200米 草地 - "C+3" 賽道')['rail'],'C+3')
  with self.assertRaises(ValueError):context('1200米 草地')
 def test_dead_heat_dnf_and_withdrawals(self):
  rows=''.join('<tr><td>'+p+'</td><td>'+str(n)+'</td><td>馬</td><td><a href="jockeyprofile?jockeyid=J'+str(n)+'">騎師</a></td></tr>' for n,p in enumerate(['1','2 平頭馬','2 平頭馬','DNF','WV','TNP'],1))
  html='<option selected value=\'{"date":"11/10/2026"}\'></option><div class="race_tab">第 2 場 1200米 草地 "C"</div><table class="draggable"><tbody>'+rows+'</tbody></table>'
  x=parse_result(html,'2026-10-11','ST',2)
  self.assertEqual(len(x['runners']),4);self.assertEqual(sum(h['top3'] for h in x['runners']),3)
  with self.assertRaises(ValueError):parse_result(html,'2026-10-04','ST',2)
if __name__=='__main__':unittest.main()
