import unittest,copy
from datetime import datetime
from unittest.mock import patch
from front_forms import collect
class FrontFormsTests(unittest.TestCase):
 def test_all_venues_identity_and_preoff_only(self):
  t=datetime.fromisoformat('2026-10-23T12:00:00+08:00')
  for venue,track in [('HV','TURF'),('ST','TURF'),('ST','AWT')]:
   m={'date':'2026-10-23','venue':venue,'races':[{'race':1,'track':track,'off':'2026-10-23T13:00:00+08:00','horses':[{'no':1,'horse_id':'HK_2025_L001'}]}]}
   with patch('front_forms.parse_form',return_value={'status':'ready','recent':[]}):collect(m,lambda url:'form',lambda:t.isoformat(),lambda:t)
   self.assertEqual(m['races'][0]['front_support']['status'],'ready');self.assertEqual(m['races'][0]['front_support']['before_date'],m['date'])
   old=copy.deepcopy(m);m['races'][0]['locked']=True
   collect(m,lambda url:self.fail('locked request'),lambda:t.isoformat(),lambda:t)
   old['races'][0]['locked']=True;self.assertEqual(m,old)
 def test_partial_forms_fail_closed(self):
  t=datetime.fromisoformat('2026-10-23T12:00:00+08:00');m={'date':'2026-10-23','venue':'HV','races':[{'race':1,'off':'2026-10-23T13:00:00+08:00','horses':[{'no':1,'horse_id':'HK_2025_L001'},{'no':2,'horse_id':'invalid'}]}]}
  with patch('front_forms.parse_form',return_value={'status':'ready','recent':[]}):collect(m,lambda url:'form',lambda:t.isoformat(),lambda:t)
  self.assertEqual(m['races'][0]['front_support']['status'],'pending');self.assertEqual(m['races'][0]['front_support']['forms']['2']['status'],'error')
