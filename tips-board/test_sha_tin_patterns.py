import copy,json,os,unittest
from sha_tin_patterns import choose_st
class STPatterns(unittest.TestCase):
 def test_js_python_archive_parity(self):
  if not os.path.exists('/tmp/st-pattern-parity.json'):self.skipTest('Run test_sha_tin_patterns.mjs first for archived parity fixtures')
  with open('/tmp/st-pattern-parity.json') as f:rows=json.load(f)
  self.assertEqual(len(rows),59)
  for row in rows:
   r=copy.deepcopy(row['input']);choose_st(r)
   self.assertEqual(r['selection'],row['selection'],(r.get('date'),r['race']))
 def test_live_inputs_pending_duplicates_and_pool_rules(self):
  from collector import choose
  r={'date':'2026-10-19','venue':'ST','race':1,'locked':False,'horses':[{'no':n,'name':str(n)} for n in range(1,15)],'tips':{k:{'status':'absent','horses':[]} for k in ['meiji','ball','ma','computer']}}
  r['tips']['meiji']={'status':'ready','horses':[{'no':n} for n in [2,3,10,11]]}
  choose(r);self.assertEqual(r['score'],0);self.assertIsNone(r['selection'])
  r['banker_initial']={'status':'ready','as_of_race_no':0,'reason':'initial','date':r['date'],'venue':'ST','race':1,'numbers':[11,10,1,12,3]}
  choose(r);self.assertEqual([x['no'] for x in r['selection']['horses']],[2,11,10]);self.assertEqual(r['selection']['main'],['QP'])
  r['tips']['ball']={'status':'ready','horses':[{'no':n} for n in [7,10,4,12]]}
  choose(r);self.assertEqual([x['no'] for x in r['selection']['horses']],[10,4,11]);self.assertEqual(r['selection']['main'],['Q','QP'])
  frozen=copy.deepcopy(r['selection']);r['locked']=True;r['tips']['ball']['horses']=[];choose(r);self.assertEqual(r['selection'],frozen)
