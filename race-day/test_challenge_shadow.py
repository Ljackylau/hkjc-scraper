import unittest
from datetime import datetime,timedelta
from challenge_shadow import HK,parse,parse_points,race_context,t3_candidate

class ChallengeTests(unittest.TestCase):
    def setUp(self):
        self.at=datetime(2026,9,27,12,42,30,tzinfo=HK)
        self.raw={'url':'https://bet.hkjc.com/ch/racing/jkc/2026-09-27/ST/1',
          'header':'騎師王 1\n27/09/2026, 星期日, 沙田\n更新時間: 27/09/2026 12:42',
          'tables':[[['選項','騎師','指定坐騎','開售\n賠率','最近\n賠率','現時\n賠率'],
             ['1','潘頓','10','2.50','','2.00'],['14','其他騎師','詳情','45','','暫停']]]}
    def parse(self):return parse(self.raw,'2026-09-27','ST','jkc',self.at)
    def test_real_columns_no_invented_points_or_remaining_rides(self):
        s=self.parse();p=s['participants'][0]
        self.assertEqual(p['opening_drop_pct'],20)
        self.assertEqual(p['scheduled_rides'],10)
        self.assertIsNone(p['remaining_rides']);self.assertIsNone(p['points'])
        self.assertIsNone(s['participants'][1]['current_odds'])
        self.assertTrue(s['participants'][1]['is_other'])
        self.assertTrue(s['source_recent'])
    def test_mismatched_date_and_venue_rejected(self):
        self.raw['header']=self.raw['header'].replace('27/09/2026','26/09/2026')
        with self.assertRaisesRegex(ValueError,'identity'):self.parse()
        self.setUp();self.raw['url']=self.raw['url'].replace('/ST/','/HV/')
        with self.assertRaisesRegex(ValueError,'identity'):self.parse()
    def test_old_or_missing_source_saved_but_not_t3(self):
        self.raw['source_text']='更新時間: 27/09/2026 11:00'
        s=self.parse();self.assertFalse(s['source_recent'])
        self.assertEqual(t3_candidate(s,[{'seconds_to_off':150}]),[])
        self.raw['source_text']='none';self.assertIsNone(self.parse()['source_updated_at'])
    def test_duplicate_or_broken_table_rejected(self):
        self.raw['tables'][0].append(self.raw['tables'][0][1])
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.parse()
        self.raw['tables']=[]
        with self.assertRaisesRegex(ValueError,'schema'):self.parse()
    def test_t3_no_postrace_or_backfill_and_delay_retained(self):
        s=self.parse();rc=race_context('2026-09-27',['12:45'],{},self.at)
        self.assertEqual(len(t3_candidate(s,rc)),1)
        self.assertEqual(t3_candidate(s,[{'seconds_to_off':-1}]),[])
        delayed=race_context('2026-09-27',['12:45'],{'1':{'target':'2026-09-27T12:47:00+08:00'}},self.at)
        self.assertEqual(t3_candidate(s,delayed),[])
        self.assertEqual(delayed[0]['post_time'],'2026-09-27T12:50:00+08:00')
    def test_previous_meeting_points_cannot_leak(self):
        raw={'text':'賽事日期:23/09/2026 練馬師王 1','url':'example',
          'tables':[[['編號','練馬師','賽日 積分','冠','亞','季'],['1','游達榮','28','2','0','1']]]}
        with self.assertRaisesRegex(ValueError,'another meeting'):parse_points(raw,'2026-09-27','tnc',self.at)
        p=parse_points(raw,'2026-09-23','tnc',self.at)
        self.assertEqual(p['participants'][0]['points'],28)
        self.assertEqual(p['freshness'],'not_verifiable')

if __name__=='__main__':unittest.main()
