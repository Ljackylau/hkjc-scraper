import unittest
from datetime import datetime, timedelta
from hkjc_shadow import HK, parse, movement, choose_baseline, baseline_info, schedule_times


class HKJCShadowTests(unittest.TestCase):
    def sample(self, at, age=30):
        return {'received_at':at.isoformat(),'source_updated':dict.fromkeys(('wp','wpq'),(at-timedelta(seconds=age)).isoformat())}

    def test_late_start_is_labelled_and_too_late_is_rejected(self):
        off=datetime(2026,9,23,19,10,tzinfo=HK)
        late=self.sample(off-timedelta(minutes=27))
        self.assertEqual(choose_baseline([late],off),late)
        self.assertEqual(baseline_info(late,off)['kind'],'late_start')
        self.assertIsNone(choose_baseline([self.sample(off-timedelta(minutes=9))],off))
        self.assertIsNone(choose_baseline([self.sample(off-timedelta(minutes=30),age=180)],off))
        early=self.sample(off-timedelta(minutes=30)+timedelta(seconds=10))
        self.assertEqual(choose_baseline([late,early],off),early)
        self.assertEqual(baseline_info(early,off)['kind'],'t30')

    def test_delayed_schedule_reselects_baseline(self):
        off=datetime(2026,9,23,19,10,tzinfo=HK)
        a=self.sample(off-timedelta(minutes=30))
        b=self.sample(off-timedelta(minutes=25))
        self.assertEqual(choose_baseline([a,b],off+timedelta(minutes=5)),b)
        self.assertIsNone(choose_baseline([a,b],off+timedelta(minutes=10)))

    def test_variable_meeting_lengths_and_invalid_clocks(self):
        for n in (1,8,9,10,11,12,14):
            clocks=','.join(f'{12+i//2:02d}:{(i%2)*30:02d}' for i in range(n))
            self.assertEqual(len(schedule_times(clocks)),n)
        for clocks in ('','13:00,12:30','13:00,13:00','25:00'):
            with self.assertRaises(ValueError):schedule_times(clocks)

    def raw(self):
        odds=lambda prefix,pool:[{'id':f'{prefix}_{pool}_1_{i}','value':'15'} for i in range(1,7)]
        pairs=lambda pool:[{'id':f'qb_{pool}_{i}_{j}','value':'20'} for i in range(1,7) for j in range(i+1,7)]
        return {'text':'23/09/2026, 星期三, 跑馬地\n更新時間: 23/09/2026 18:10\n第 1 場\n23/09 (三), 18:40, 第五班',
                'win':odds('odds','WIN'),'pla':odds('odds','PLA'),'qin':pairs('QIN'),'qpl':pairs('QPL')}

    def test_official_wp_and_wpq_have_validated_identity_and_timestamp(self):
        received=datetime(2026,9,23,18,10,30,tzinfo=HK);raw=self.raw()
        wp=parse(raw,'2026-09-23',1,'wp',received)
        wpq=parse(raw,'2026-09-23',1,'wpq',received)
        self.assertTrue(wp['fresh'] and wpq['fresh'])
        self.assertEqual(wp['post_time'],'18:40')
        self.assertEqual(len(wpq['odds']['QPL']),15)
        with self.assertRaisesRegex(ValueError,'identity'):
            parse(raw,'2026-09-23',2,'wp',received)
        self.assertFalse(parse(raw,'2026-09-23',1,'wp',received+timedelta(minutes=3))['fresh'])
        raw['text']=raw['text'].replace('更新時間: 23/09/2026 18:10','')
        raw['source_text']='更新時間: 23/09/2026 18:10'
        self.assertTrue(parse(raw,'2026-09-23',1,'wp',received)['fresh'])

    def test_market_movement_is_separate_and_has_no_arbitrary_zero_score_pick(self):
        baseline={'odds':{'WIN':{'1':'10','2':'10'},'PLA':{'1':'4','2':'4'},
                          'QIN':{'1-2':'20','1-3':'20'},'QPL':{'1-2':'15','1-3':'15'}}}
        self.assertEqual(movement(baseline,baseline),[])
        t3={'odds':{'WIN':{'1':'8','2':'10'},'PLA':{'1':'3','2':'4'},
                    'QIN':{'1-2':'15','1-3':'12'},'QPL':{'1-2':'12','1-3':'8'}}}
        ranked=movement(baseline,t3)
        self.assertEqual(ranked[0]['horse_number'],1)
        self.assertGreater(ranked[0]['score'],ranked[1]['score'])


if __name__=='__main__':unittest.main()
