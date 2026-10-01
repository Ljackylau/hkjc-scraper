import asyncio,json,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import AsyncMock,patch
import test_independent_tip
from independent_tip import prepare,message
from runner import format_tip_message,now
from challenge_shadow import collect,critical_quotes

class NewLegsTests(unittest.TestCase):
    def test_f_scores_top_four_excluding_banker(self):
        off,samples=test_independent_tip.TipTests().fixture()
        tip=prepare(samples,off,'2026-10-01',1,samples[0],golden=[6])
        expected=[int(h) for h in sorted(tip['leg_scores'],key=lambda h:(-tip['leg_scores'][h],int(h))) if int(h)!=tip['banker']][:4]
        self.assertEqual(tip['legs'],expected)
        self.assertEqual(len(tip['legs']),4)
        self.assertEqual(tip['legs_method'],'relative_support_f_v1')
    def test_long_only_cannot_invent_f_legs(self):
        off,samples=test_independent_tip.TipTests().fixture()
        tip=prepare([samples[-1]],off,'2026-10-01',1,samples[0])
        self.assertEqual(tip['status'],'ready')
        self.assertEqual(tip['legs'],[])
        self.assertEqual(tip['legs_status'],'unavailable')
        self.assertIn('資料未就緒',message(1,tip))
    def test_closed_cold_still_has_line(self):
        off,samples=test_independent_tip.TipTests().fixture();tip=prepare(samples,off,'2026-10-01',1,samples[0])
        tip.update(cold_status='unavailable',cold_reason='練王沒有可比較数字報價')
        self.assertIn('最有可能爆冷馬：無法判定',message(1,tip))
    def snapshot(self):
        return {'ranking':[{'horse_number':1}], 'method_b':{'method':'independent_hybrid_v1','banker':1},'independent_tip':{'cold_status':'ready','cold':[],'legs_status':'ready'}}
    def test_winner_gets_win_dividend_and_medals(self):
        text=format_tip_message(1,self.snapshot(),[2,3,4,5],positions={1:'🥇',2:'🥈',3:'🥉',4:'4️⃣'},result=True,dividends={'W':[{'combination':'1','dividend_hkd':53}], 'P':[{'combination':'1','dividend_hkd':20}]})
        self.assertIn('1號（🥇）',text);self.assertIn('4號（4️⃣）',text)
        self.assertIn('獨贏派彩 5.3倍',text);self.assertNotIn('位置派彩',text);self.assertNotIn('新方法',text)
    def test_placed_banker_gets_place_only(self):
        text=format_tip_message(1,self.snapshot(),[2,3],positions={1:'第三'},result=True,dividends={'P':[{'combination':'1','dividend_hkd':31.5}]})
        self.assertIn('1號（🥉）',text);self.assertIn('位置派彩 3.15倍',text);self.assertNotIn('獨贏派彩',text)
    def test_fourth_never_gets_payout(self):
        text=format_tip_message(1,self.snapshot(),positions={1:'4️⃣'},result=True,dividends={'P':[{'combination':'1','dividend_hkd':31.5}]})
        self.assertNotIn('派彩',text)
    def test_priority_window(self):
        self.assertTrue(critical_quotes([{'seconds_to_off':420}]))
        self.assertTrue(critical_quotes([{'seconds_to_off':190}]))
        self.assertTrue(critical_quotes([{'seconds_to_off':179}]))
        self.assertFalse(critical_quotes([{'seconds_to_off':-1}]))

class CaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_odds_written_before_points(self):
        class Page:
            async def close(self):pass
        class Context:
            async def new_page(self):return Page()
        at=now();date=at.strftime('%Y-%m-%d');off=at+timedelta(minutes=20)
        sample={'received_at':at.isoformat(),'source_updated_at':at.isoformat(),'state':'observed','participants':[],'source_recent':True,'source_age_seconds':0,'numeric_quotes':0}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'challenge'
            async def points(page,date,kind):
                self.assertTrue((folder/f'{kind}.jsonl').exists())
                self.assertTrue((folder/f'{kind}_latest.json').exists())
                return {'participants':[]}
            with patch('challenge_shadow.read_odds',new=AsyncMock(return_value=(sample.copy(),{'tables':[]}))),patch('challenge_shadow.read_points',side_effect=points):
                await collect(Context(),date,'ST',[off.strftime('%H:%M')],[1],temp,{},once=True)
            status=json.loads((folder/'status.json').read_text())
            self.assertEqual(status['pools']['tnc']['state'],'observed')
            self.assertTrue(status['pools']['tnc']['points_available'])

if __name__=='__main__':unittest.main()

class DeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_freeze_clock_sends_without_market_page_completion(self):
        import hkjc_shadow
        off,samples=test_independent_tip.TipTests().fixture()
        freeze=off-timedelta(minutes=3,seconds=10)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            async def send(number,tip,dest):
                self.assertEqual(tip['banker'],1)
                self.assertEqual(tip['legs_status'],'ready')
                self.assertEqual(tip['cold_status'],'ready') # R1 has no previous race
                (dest/'race_01_independent_notification.json').write_text('{"status":"sent"}')
            with patch('hkjc_shadow.now',return_value=freeze),patch('hkjc_shadow.notify_independent',side_effect=send) as sent:
                await hkjc_shadow.freeze_independent(lambda:(off,samples,samples[0]),folder,1,'2026-10-01',['13:00'],{})
            self.assertEqual(sent.call_count,1)
            self.assertTrue((folder/'race_01_independent.json').exists())
