import unittest,copy
from collector import choose,empty_meeting,parse_meiji,safe_horses
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
if __name__=='__main__':unittest.main()
