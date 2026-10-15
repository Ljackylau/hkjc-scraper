import copy,unittest
from sha_tin_four import choose_four,parse_initial,capture_four
from datetime import datetime
class Four(unittest.TestCase):
 def setUp(self):
  self.r={'date':'2026-10-19','venue':'ST','race':1,'off':'2026-10-19T12:30:00+08:00','horses':[{'no':n,'name':str(n)} for n in range(1,15)],'tips':{k:{'status':'absent','horses':[]} for k in ['ball','ma','computer','meiji']},'banker_initial':{'status':'ready','date':'2026-10-19','venue':'ST','race':1,'reason':'initial','as_of_race_no':0,'numbers':[12,1,4,14,9]}}
 def tip(self,key,nums):self.r['tips'][key]={'status':'ready','horses':[{'no':n} for n in nums],'source_date':self.r['date']}
 def test_priority_and_original_order(self):
  self.tip('ball',[12,1,13,2]);self.tip('ma',[7,8]);self.assertEqual(choose_four(self.r)['numbers'],[12,1,4,13])
 def test_absent_priority(self):
  self.tip('ma',[4,2,13]);self.assertEqual(choose_four(self.r)['numbers'],[12,1,4,2])
 def test_first_source_all_overlap_never_next_tipster(self):
  self.tip('ball',[4,12,1]);self.tip('ma',[7]);self.assertEqual(choose_four(self.r)['numbers'],[12,1,4,14])
 def test_scratch_bank_and_tip(self):
  self.r['scratched']=[12,13];self.tip('ball',[12,13,2]);self.assertEqual(choose_four(self.r)['numbers'],[1,4,14,2])
 def test_legs_fallback_scratch(self):
  self.r['scratched']=[14];self.tip('ball',[12,1,4]);self.assertEqual(choose_four(self.r)['numbers'],[12,1,4,9])
 def test_bias_and_wrong_date_rejected(self):
  for key,val in [('as_of_race_no',1),('reason','track_bias'),('date','2026-10-18')]:
   r=copy.deepcopy(self.r);r['banker_initial'][key]=val;self.assertEqual(choose_four(r)['numbers'],[])
 def test_unknown_priority_does_not_guess(self):
  self.r['tips']['ball']['status']='error';self.tip('meiji',[2]);self.assertEqual(choose_four(self.r)['numbers'],[])
 def test_hv_not_applicable_and_no_fifth(self):
  self.tip('ball',[8,9,10,11]);self.assertEqual(len(choose_four(self.r)['numbers']),4);self.r['venue']='HV';self.assertIsNone(choose_four(self.r))
 def test_insufficient_field_no_partial_output(self):
  self.r['horses']=self.r['horses'][:2];self.assertEqual(choose_four(self.r)['numbers'],[])
 def test_preoff_lock(self):
  m={'date':self.r['date'],'venue':'ST','races':[self.r]};self.r['sha_tin_four']={'numbers':[1,2,3,4]};self.r['locked']=True;before=copy.deepcopy(self.r)
  capture_four(m,lambda u: (_ for _ in ()).throw(Exception('must not fetch')),lambda:'now',lambda:datetime.fromisoformat('2026-10-19T12:00:00+08:00'));self.assertEqual(self.r,before)
 def test_parser_uses_summary_not_table_or_ranking(self):
  html='<h1>第1場</h1><div>2026年10月19日 · 沙田</div><a href="/race/2026-10-19~ST~1?v=1">v1賽前排位</a><section><span class="silk-banker">12</span>'+''.join(f'<span class="silk-leg">{n}</span>' for n in [1,4,14,9])+'</section><table><span class="silk-banker">3</span></table>'
  self.assertEqual(parse_initial(html,'2026-10-19',1)['numbers'],[12,1,4,14,9])
  with self.assertRaises(ValueError):parse_initial(html.replace('賽前排位','偏差更新'),'2026-10-19',1)
if __name__=='__main__':unittest.main()
