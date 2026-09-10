import unittest
from datetime import datetime, timedelta
from collector import (pairs, compare, endpoint_ok, snapshot, top_three,
                       record_due_snapshots, meeting_candidates,
                       race_time_from_text, validate_config, HK)
class TestCollector(unittest.TestCase):
    def test_meeting_candidates_choose_today_then_next(self):
        hrefs=['https://x?Racecourse=HV&racedate=2026%2F09%2F09',
               'https://x?Racecourse=ST&racedate=2026%2F09%2F13',
               'https://x?Racecourse=HV&racedate=2026/09/16']
        self.assertEqual(meeting_candidates(hrefs,datetime(2026,9,10).date()),
                         [('2026-09-13','ST'),('2026-09-16','HV')])
    def test_race_time_from_official_heading(self):
        text='Race 6 - TEST HANDICAP\nSunday, September 13, 2026, Sha Tin, 15:35\nTurf'
        self.assertEqual(race_time_from_text(text,6),'15:35')
        self.assertIsNone(race_time_from_text(text,7))
    def test_config_validation(self):
        config={'date':'2026-09-13','venue':'ST','times':['13:00','13:30']}
        self.assertIs(validate_config(config),config)
        with self.assertRaises(ValueError): validate_config({'date':'2026-09-13','venue':'XX','times':['13:00']})
    def test_top_three_uses_average_drop(self):
        result={'horses':[{'horse':1,'avg_drop_pct':35,'count':4},{'horse':2,'avg_drop_pct':51,'count':1},{'horse':3,'avg_drop_pct':44,'count':2},{'horse':4,'avg_drop_pct':40,'count':9}]}
        self.assertEqual([x['horse'] for x in top_three(result)],[2,3,4])
    def test_automatic_snapshots_record_once(self):
        off=datetime(2026,9,9,22,tzinfo=HK); race={}
        result={'final_time':(off-timedelta(minutes=10)).isoformat(),'source_updated':'x','top3':[{'horse':2,'score':51}]}
        record_due_snapshots(race,result,off,off-timedelta(minutes=10))
        self.assertEqual(race['snapshots']['T−10']['top3'][0]['horse'],2)
        later=dict(result,top3=[{'horse':9,'score':99}])
        record_due_snapshots(race,later,off,off-timedelta(minutes=9))
        self.assertEqual(race['snapshots']['T−10']['top3'][0]['horse'],2)
        record_due_snapshots(race,later,off,off-timedelta(minutes=3))
        self.assertIn('T−3',race['snapshots'])
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
