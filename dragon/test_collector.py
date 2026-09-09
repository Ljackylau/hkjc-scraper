import unittest
from datetime import datetime, timedelta
from collector import pairs, compare, endpoint_ok, snapshot, top_three, HK
class TestCollector(unittest.TestCase):
    def test_top_three_uses_average_drop(self):
        result={'horses':[{'horse':1,'avg_drop_pct':35,'count':4},{'horse':2,'avg_drop_pct':51,'count':1},{'horse':3,'avg_drop_pct':44,'count':2},{'horse':4,'avg_drop_pct':40,'count':9}]}
        self.assertEqual([x['horse'] for x in top_three(result)],[2,3,4])
    def test_strict_threshold(self):
        r=compare({'1-2':'100','1-3':'100'},{'1-2':'70','1-3':'69.9'},'QIN')
        self.assertEqual([x['pair'] for x in r['pairs']],['1-3'])
    def test_direction_and_counts(self):
        r=compare({'1-2':'100','2-1':'100'},{'1-2':'60','2-1':'50'},'FCT')
        self.assertEqual(r['horses'][0],{'horse':1,'count':2,'partners':1,'avg_drop_pct':45.0,'max_drop_pct':50.0})
    def test_invalid_and_dedup(self):
        c=[{'id':'qb_QIN_2_1','value':'10'},{'id':'qb_QIN_1_2','value':'10'},{'id':'qb_QIN_2_3','value':'退'}]
        self.assertEqual(pairs(c,'QIN'),{'1-2':'10'})
    def test_missing_end(self):
        self.assertEqual(compare({'1-2':'100'},{},'QIN')['pairs'],[])
    def test_time_guard(self):
        start=datetime(2026,9,9,19,tzinfo=HK); stop=start+timedelta(minutes=50)
        b={'captured':start.isoformat(),'fresh':True}; f={'captured':stop.isoformat(),'fresh':True}
        self.assertTrue(endpoint_ok(b,f,start,stop))
        f['captured']=(stop+timedelta(seconds=1)).isoformat()
        self.assertFalse(endpoint_ok(b,f,start,stop))
        b['captured']=(start+timedelta(seconds=31)).isoformat()
        self.assertFalse(endpoint_ok(b,f,start,stop))
    def test_stale_source(self):
        raw={'text':'更新時間:09/09/2026 19:00','cells':[]}
        self.assertTrue(snapshot(raw,'QIN',datetime(2026,9,9,19,1,tzinfo=HK))['fresh'])
        self.assertFalse(snapshot(raw,'QIN',datetime(2026,9,9,19,3,tzinfo=HK))['fresh'])
if __name__=='__main__': unittest.main()
