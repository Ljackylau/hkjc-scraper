import asyncio,json,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch,MagicMock,AsyncMock
from test_cold_partial import ColdPartialTests
from cold_policy import calculate,format_cold
from runner import telegram_send,now
from independent_tip import notify

class GroupTests(ColdPartialTests):
    def groups(self):
        for row,odds in [(self.base,100),(self.end,60)]:
            row['selection_roster_complete']=True
            row['participants'].append({'selection_id':'21','name':'其他練馬師','is_other':True,'current_odds':odds})
    def test_verified_other_has_collective_signal_not_individual(self):
        self.groups();r=calculate(self.tip,[self.base,self.end])
        self.assertEqual(r['cold'],[13]);self.assertFalse(r['cold_partial']);self.assertEqual(r['cold_group'][0]['horse'],9)
        self.assertEqual(r['cold_group'][0]['drop_pct'],40)
        self.assertIn('組合訊號，非個別練王落飛',format_cold(r))
    def test_other_not_assumed_when_roster_incomplete(self):
        self.groups();self.base['selection_roster_complete']=False
        r=calculate(self.tip,[self.base,self.end]);self.assertEqual(r['cold_group'],[]);self.assertTrue(r['cold_partial'])
    def test_membership_change_not_assigned_group_drop(self):
        self.groups();self.base['participants'].append({'name':'Missing','selection_id':'2','current_odds':100})
        r=calculate(self.tip,[self.base,self.end]);self.assertEqual(r['cold_group'],[]);self.assertTrue(r['cold_partial'])
    def test_eliminated_trainer_is_not_missing_quote(self):
        self.end['participants'][0].update(current_odds=None,quote_text='未能勝出')
        self.tip['market']=[13];r=calculate(self.tip,[self.base,self.end])
        self.assertEqual(r['cold_status'],'ready');self.assertEqual(r['cold'],[]);self.assertFalse(r['cold_partial'])
        self.assertEqual(r['cold_excluded'][0]['horse'],13)
    def test_final_race_not_applicable_after_penultimate_off(self):
        self.end['race_context'].append({'race_number':2,'post_time':'2026-10-01T13:30:00+08:00'})
        self.end.update(state='suspended_or_closed')
        r=calculate(self.tip,[self.base,self.end]);self.assertFalse(r['cold_applicable']);self.assertIn('本場不適用',format_cold(r))
    def test_nan_is_rejected(self):
        self.end['participants'][0]['current_odds']=float('nan');self.tip['market']=[13]
        self.assertEqual(calculate(self.tip,[self.base,self.end])['cold_status'],'unavailable')

class TelegramAckTests(unittest.TestCase):
    def test_false_json_ack_never_success(self):
        for payload in [{'ok':False},{'ok':True,'result':{}},{'ok':True,'result':{'message_id':1}}]:
            response=MagicMock();response.status=200;response.read.return_value=json.dumps(payload).encode()
            cm=MagicMock();cm.__enter__.return_value=response
            with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'test','TELEGRAM_CHAT_ID':'test'}),patch('runner.urllib.request.urlopen',return_value=cm):
                if payload.get('result',{}).get('message_id'):self.assertTrue(telegram_send('test'))
                else:
                    with self.assertRaises(RuntimeError):telegram_send('test')

class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_sent_marker_contains_frozen_cold_and_no_duplicates(self):
        at=now();tip={'status':'ready','cutoff':at.isoformat(),'banker':1,'legs':[2,3,4,5],'legs_status':'ready','cold_status':'ready','cold':[3], 'cold_received_at':(at-timedelta(seconds=15)).isoformat()}
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            with patch('independent_tip.telegram_configured',return_value=True),patch('independent_tip.telegram_send',return_value=True) as send:
                await notify(1,tip,folder);await notify(1,tip,folder)
            r=json.loads((folder/'race_01_independent_notification.json').read_text())
            self.assertEqual(send.call_count,1);self.assertTrue(r['telegram_acknowledged']);self.assertIn('最有可能爆冷馬：3號',r['message'])
    async def test_expired_never_sends_late_preoff_tip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            with patch('independent_tip.telegram_send') as send:
                await notify(1,{'cutoff':(now()-timedelta(seconds=91)).isoformat()},folder)
            send.assert_not_called();self.assertEqual(json.loads((folder/'race_01_independent_notification.json').read_text())['status'],'expired')
