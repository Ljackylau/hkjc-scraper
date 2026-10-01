import unittest
from test_cold_partial import ColdPartialTests
from cold_policy import calculate,format_cold
class ExcludeBankerTests(unittest.TestCase):
 def fixture(self):
  obj=ColdPartialTests();obj.setUp();return obj
 def test_main_not_a_cold_candidate(self):
  f=self.fixture();f.tip.update(banker=13,market=[13]);r=calculate(f.tip,[f.base,f.end]);self.assertEqual(r['cold'],[]);self.assertEqual(r['cold_status'],'ready');self.assertTrue(format_cold(r).startswith('無'))
 def test_retains_other_qualifier(self):
  f=self.fixture();f.tip.update(banker=9);r=calculate(f.tip,[f.base,f.end]);self.assertEqual(r['cold'],[13]);self.assertFalse(r['cold_partial'])
 def test_display_filters_old_frozen_tip(self):
  self.assertEqual(format_cold({'banker':13,'cold_status':'ready','cold':[13,9]}),'9號')
 def test_group_banker_is_not_displayed(self):
  self.assertEqual(format_cold({'banker':13,'cold_status':'ready','cold':[],'cold_group':[{'horse':13,'qualifies':True}]}),'無')
