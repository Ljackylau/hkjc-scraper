import unittest,json,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from independent_tip import prepare,notify,message
HK=timezone(timedelta(hours=8))

class TipTests(unittest.TestCase):
    def fixture(self):
        off=datetime(2026,10,1,13,tzinfo=HK)
        def snap(minutes,changed=False):
            at=off-timedelta(minutes=minutes)
            odds={'WIN':{str(i):'10' for i in range(1,7)},'PLA':{str(i):'4' for i in range(1,7)},
                  'QIN':{f'{i}-{j}':'30' for i in range(1,7) for j in range(i+1,7)},
                  'QPL':{f'{i}-{j}':'15' for i in range(1,7) for j in range(i+1,7)}}
            if changed:
                odds['WIN']['1']='3';odds['PLA']['1']='2'
                odds['WIN']['2']='7';odds['PLA']['2']='3'
            return {'received_at':at.isoformat(),'source_updated':{'wp':at.isoformat(),'wpq':at.isoformat()},'post_time':'13:00','odds':odds}
        return off,[snap(30),snap(10),snap(3.2,True)]
    def test_new_banker_and_existing_market_legs(self):
        off,s=self.fixture();tip=prepare(s,off,'2026-10-01',1,s[0])
        self.assertEqual(tip['banker'],1)
        self.assertIn(2,tip['legs']) # Former Horse103 banker 2 is not removed.
        self.assertNotIn(1,tip['legs'])
    def test_late_quote_never_changes_pick(self):
        off,s=self.fixture();late=json.loads(json.dumps(s[-1]));late['received_at']=(off-timedelta(minutes=3)+timedelta(seconds=1)).isoformat();late['odds']['WIN']['6']='1.1'
        self.assertEqual(prepare(s+[late],off,'2026-10-01',1,s[0])['banker'],1)
    def test_missing_baseline_no_fake_banker(self):
        off,s=self.fixture();tip=prepare(s[-1:],off,'2026-10-01',1)
        self.assertEqual(tip['status'],'unavailable');self.assertNotIn('banker',tip)
    def test_message_single_banker(self):
        off,s=self.fixture();tip=prepare(s,off,'2026-10-01',1,s[0]);tip['cold_status']='unavailable'
        self.assertIn('獨贏&位置信心馬：1號\n',message(1,tip));self.assertIn('無法判定：缺有效報價',message(1,tip));self.assertNotIn('查看完整資料',message(1,tip));self.assertNotIn('已鎖定',message(1,tip))
    def test_settlement_keeps_independent_banker(self):
        import runner,reconcile
        with tempfile.TemporaryDirectory() as f:
            root=Path(f);day=root/'2026-10-01';phase=day/'early'
            runner.atomic(phase/'status.json',{'horse103':{'1':{'status':'saved'}}})
            runner.atomic(phase/'horse103'/'race_01.json',{'race':{'venue':'ST'},'ranking':[{'horse_number':7}],'live103_raw':{'candidates':[]}})
            runner.atomic(day/'hkjc-early'/'race_01_independent.json',{'status':'ready','banker':1,'legs':[2,3,4,5],'cold_status':'unavailable'})
            with patch.object(reconcile,'fetch_official_result',return_value={'settlement_status':'complete','top4':[1,2,3,4],'dividends':{}}):
                reconcile.reconcile('2026-10-01',root,workers=1)
            result=json.loads((day/'settlement'/'race_01.json').read_text())
            self.assertEqual(result['banker'],1);self.assertEqual(result['legs'],[2,3,4,5]);self.assertEqual(result['additional_picks'],[])

class NotifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_marker_prevents_repeat(self):
        t=datetime(2026,10,1,12,57,tzinfo=HK);tip={'status':'unavailable','cutoff':t.isoformat(),'reason':'test'}
        with tempfile.TemporaryDirectory() as f,patch('independent_tip.now',return_value=t),patch('independent_tip.telegram_configured',return_value=True),patch('independent_tip.telegram_send',return_value=True) as send:
            await notify(1,tip,Path(f));await notify(1,tip,Path(f))
            self.assertEqual(send.call_count,1)
            self.assertEqual(json.loads((Path(f)/'race_01_independent_notification.json').read_text())['send_delay_seconds'],0)

if __name__=='__main__':unittest.main()
