import copy,unittest
from hv_patterns import choose_hv,HV_METHOD
class HappyValley(unittest.TestCase):
 def base(self):
  return {'date':'2026-10-21','venue':'HV','race':2,'horses':[{'no':n,'name':str(n),'draw':n,'jockey_id':str(n)} for n in range(1,13)],'tips':{'meiji':{'status':'ready','horses':[{'no':n} for n in [11,3,8,4]]},**{k:{'status':'absent','horses':[]} for k in ['ball','ma','computer']}},'banker_initial':{'status':'ready','date':'2026-10-21','venue':'HV','race':2,'as_of_race_no':0,'reason':'initial','numbers':[1,3,8,9,10]},'draw_top5':{'status':'ready','method_version':'jockey_draw_only_v3','before_date':'2026-10-21','riders':[{'no':3,'draw':3,'jockey_id':'3'},{'no':1,'draw':1,'jockey_id':'1'}]}}
 def test_h0(self):
  r=self.base();choose_hv(r);self.assertEqual(r['selection']['horses'][0]['no'],1);self.assertEqual(r['selection']['main'],['P']);self.assertEqual(r['selection']['method'],HV_METHOD)
 def test_inside_gate(self):
  r=self.base();r['tips']['meiji']['horses'][0]['no']=3;choose_hv(r);self.assertIsNone(r['selection']);self.assertEqual(r['hv_plan_state'],'skip')
 def test_initial_identity(self):
  for field,value in [('reason','bias'),('date','2026-10-14'),('venue','ST'),('race',3)]:
   r=self.base();r['banker_initial'][field]=value;choose_hv(r);self.assertIsNone(r['selection']);self.assertEqual(r['hv_plan_state'],'pending')
 def test_scratched_and_stale_draw(self):
  r=self.base();r['scratched']=[1];choose_hv(r);self.assertEqual(r['hv_plan_state'],'skip')
  r=self.base();r['draw_top5']['riders'][1]['draw']=99;choose_hv(r);self.assertEqual(r['hv_plan_state'],'pending')
 def test_h1_only_expert_first(self):
  r=self.base();r['tips']['ball']={'status':'ready','horses':[{'no':7}]};choose_hv(r);self.assertEqual(r['selection']['horses'][0]['no'],7);self.assertEqual(r['selection']['main'],['W']);self.assertEqual(r['selection']['optional'],[])
if __name__=='__main__':unittest.main()
