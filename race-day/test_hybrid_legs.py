import unittest
from leg_selection import select
class HybridTests(unittest.TestCase):
 def test_low_qp_pairs_skip_head_and_banker(self):
  r=select(1,{1:1,2:.9,3:.8,4:.7,5:.6,6:.5},{'1-2':1,'1-3':2,'1-4':30,'1-5':20,'1-6':10})
  self.assertEqual(r['legs'],[2,3,6,5]);self.assertEqual(r['legs_qp'],[6,5])
 def test_missing_f_never_invents_two(self):
  self.assertEqual(select(1,{}, {'1-2':3})['legs_status'],'unavailable')
 def test_missing_qp_never_uses_other_pairs(self):
  r=select(1,{2:.9,3:.8,4:.7,5:.6},{'2-4':1,'3-5':1})
  self.assertEqual(r['legs'],[]);self.assertIn('位置Q',r['legs_reason'])
 def test_tie_uses_f_then_horse(self):
  r=select(1,{2:.9,3:.8,4:.5,5:.6,6:.5},{'1-4':10,'1-5':10,'1-6':10})
  self.assertEqual(r['legs'],[2,3,5,4])
