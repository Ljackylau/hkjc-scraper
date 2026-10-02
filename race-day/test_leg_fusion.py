import asyncio
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from leg_fusion import apply, note, METHOD, COLD_POLICY
from leg_selection import select
from independent_tip import message
import hkjc_shadow


def fixture():
    freeze = '2026-10-04T12:26:50+08:00'
    return {'date':'2026-10-04','race':1,'method':'independent_hybrid_v1','status':'ready',
            'freeze':freeze,'cutoff':'2026-10-04T12:27:00+08:00','banker':1,'received_at':freeze,
            'legs':[2,3,4,5],'legs_f':[2,3],'legs_qp':[4,5],'legs_status':'ready',
            'legs_method':'f2_banker_qp2_v1','leg_scores':{h:.5 for h in range(1,7)},
            'golden':[5,6], 'cold_policy':COLD_POLICY,'cold_status':'ready','cold':[6],'cold_win':20,
            'cold_freeze':freeze,'cold_received_at':freeze,'cold_fct_received_at':freeze,
            'cold_sources':{'historical_prepared_at':'2026-10-04T11:00:00+08:00'}}


class FusionTests(unittest.TestCase):
    def test_all_researched_selections_match_frozen_inputs(self):
        cases = json.loads(Path(__file__).with_name('fixtures').joinpath('leg_fusion_replay.json').read_text())
        ready=changed=0
        for case in cases:
            tip=case['tip']
            with self.subTest(day=tip['date'],race=tip['race']):
                current=select(tip['banker'],tip['leg_scores'],case['qp'])
                self.assertEqual(current['legs'],tip['legs'])
                result=apply(tip)
                self.assertEqual(result['legs'],case['expected'])
                if tip['legs_status']=='ready':
                    ready+=1;changed+=result['legs_fusion_changed']
                    self.assertEqual(result['legs_original'],tip['legs'])
                    self.assertEqual(result['legs'][:3],tip['legs'][:3])
        self.assertEqual((ready,changed),(29,12))

    def test_gate_duplicate_and_banker_cases(self):
        t=fixture()
        for cold,win in [(6,10),(6,30.1),(6,float('nan')),(1,20),(3,20),(9,20)]:
            with self.subTest(cold=cold,win=win):
                r=apply({**t,'cold':[cold],'cold_win':win})
                self.assertEqual(r['legs'],t['legs']);self.assertFalse(r['legs_fusion_changed'])
        r=apply({**t,'cold_win':30})
        self.assertEqual(r['legs'],[2,3,4,6])
        self.assertEqual(r['legs_qp'],[4]);self.assertEqual(r['legs_cold'],[6])
        self.assertEqual(r['golden'],[6])

    def test_incomplete_cold_retains_original_four(self):
        t=fixture()
        for fields in [{'cold_status':'unavailable'},{'cold_policy':'old'},{'cold':[]},{'cold':None},
                       {'cold':[4,6]},{'cold_win':None},{'cold_freeze':t['cutoff']},
                       {'cold_received_at':t['cutoff']},{'cold_fct_received_at':t['cutoff']},
                       {'cold_sources':{'historical_prepared_at':t['cutoff']}}]:
            r=apply({**t,**fields})
            self.assertEqual(r['legs'],t['legs']);self.assertFalse(r['legs_fusion_changed'])

    def test_missing_f_legs_are_never_invented(self):
        t=fixture()
        for fields in [{'legs':[],'legs_status':'unavailable'}, {'legs':[2,2,4,5]},
                       {'legs':[1,3,4,5]}, {'status':'unavailable'}]:
            bad={**t,**fields};self.assertEqual(apply(bad),bad)

    def test_saved_fusion_is_idempotent_and_messages_use_final_legs(self):
        t=fixture();before=copy.deepcopy(t);r=apply(t)
        self.assertEqual(t,before);self.assertIs(apply(r),r)
        self.assertEqual(r['legs_method'],METHOD)
        self.assertIn('1號 拖 2號、3號、4號、6號',message(1,r))
        self.assertIn('原5號',note(r));self.assertIn('選腳：',message(1,r))

    def test_freeze_publishes_fused_four_before_notification(self):
        t=fixture();off=datetime.fromisoformat(t['cutoff'])+timedelta(minutes=3)
        async def exercise():
            event=asyncio.Event();saved={}
            async def notify(number,tip,folder):
                self.assertTrue(event.is_set());self.assertEqual(saved['1']['legs'],[2,3,4,6])
                self.assertEqual(tip['legs_original'],[2,3,4,5]);self.assertEqual(tip['legs_method'],METHOD)
                hkjc_shadow.atomic(folder/'race_01_independent_notification.json',{'status':'not_configured'})
            with tempfile.TemporaryDirectory() as tmp:
                with patch.object(hkjc_shadow,'now',return_value=off-timedelta(seconds=189)), \
                     patch.object(hkjc_shadow,'prepare_independent',return_value=t), \
                     patch('cold_top2_live.prepare',return_value={}), \
                     patch.object(hkjc_shadow,'notify_independent',side_effect=notify):
                    await hkjc_shadow.freeze_independent(lambda:(off,[],None),Path(tmp),1,t['date'],[],{},lambda:([],{}),event,saved)
        asyncio.run(exercise())


if __name__=='__main__':unittest.main()
