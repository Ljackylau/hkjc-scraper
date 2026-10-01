import unittest,copy
from datetime import datetime,timedelta,timezone
from independent_candidate import pick

class LongOnlyTests(unittest.TestCase):
 def setUp(self):
  self.cut=datetime(2026,10,1,18,17,tzinfo=timezone(timedelta(hours=8)))
  def snapshot(received,win):
   return {'post_time':'18:20','received_at':received,'source_updated':{'wp':received,'wpq':received},'odds':{'WIN':win,'PLA':{'1':'2','2':'3'},'QIN':{'1-2':'10'},'QPL':{'1-2':'5'}}}
  self.base=snapshot('2026-10-01T17:51:00+08:00',{'1':'10','2':'10'})
  self.end=snapshot('2026-10-01T18:16:40+08:00',{'1':'5','2':'10'})
 def test_long_only_keeps_long_banker(self):
  result=pick(self.end,None,self.cut,self.base)
  self.assertEqual(result['banker'],1)
  self.assertEqual(result['t10_status'],'unavailable')
  self.assertEqual(result['leg_scores'],{})
 def test_missing_both_baselines_fails(self):
  with self.assertRaises(ValueError):pick(self.end,None,self.cut,None)
 def test_after_deadline_or_old_endpoint_fails(self):
  bad=copy.deepcopy(self.end);bad['received_at']='2026-10-01T18:16:51+08:00'
  with self.assertRaises(ValueError):pick(bad,None,self.cut,self.base)
  bad=copy.deepcopy(self.end);bad['source_updated']['wp']='2026-10-01T18:14:00+08:00'
  with self.assertRaises(ValueError):pick(bad,None,self.cut,self.base)
 def test_incomplete_long_pairs_fail(self):
  bad=copy.deepcopy(self.base);bad['odds']['QPL']={}
  with self.assertRaises(ValueError):pick(self.end,None,self.cut,bad)

if __name__=='__main__':unittest.main()
