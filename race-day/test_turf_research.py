import copy
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from turf_research import cold_divergence, turf_candidate, observe
from cold_history import parse_card


def markets():
    off = datetime.fromisoformat('2026-10-04T13:00:00+08:00')
    horses = list(map(str, range(1, 6)))
    pairs = {f'{a}-{b}': '20' for a in range(1, 6) for b in range(a+1, 6)}
    def snapshot(at):
        return {'received_at': at.isoformat(), 'source_updated': {'wp': at.isoformat(), 'wpq': at.isoformat()},
                'post_time': '13:00', 'odds': {'WIN': {h: '15' for h in horses},
                'PLA': {h: '4' for h in horses}, 'QIN': dict(pairs), 'QPL': dict(pairs)}}
    start, end = snapshot(off-timedelta(minutes=30)), snapshot(off-timedelta(minutes=3, seconds=12))
    start['odds']['WIN']['1'] = end['odds']['WIN']['1'] = '2'
    end['odds']['WIN']['5'] = '20'
    end['odds']['PLA']['5'] = '5'
    end['odds']['QIN']['1-5'] = end['odds']['QPL']['1-5'] = '15'
    return off, start, end


def turf():
    tip = {'date': '2026-10-04', 'race': 7, 'status': 'ready', 'banker': 1,
           'freeze': '2026-10-04T16:00:00+08:00', 'received_at': '2026-10-04T15:59:50+08:00',
           'legs': [4, 5, 6, 7], 'legs_status': 'ready',
           'leg_scores': {str(h): 1-h/10 for h in range(1, 10)},
           'runner_rows': [[str(h), '', '', str(h), '', '', '', '10'] for h in range(1, 10)]}
    c = {'status': 'ready', 'date': tip['date'], 'race': 7, 'venue': 'ST', 'track': 'TURF',
         'distance': 1400, 'rail': 'A', 'prepared_at': '2026-10-04T12:00:00+08:00'}
    prior = [{'context': {**c, 'race': i}, 'tip': {**tip, 'race': i},
              'result': {'received_at': '2026-10-04T15:00:00+08:00', 'top4': [1, 2, 3, 4]}}
             for i in range(1, 4)]
    return tip, c, prior


class ResearchTests(unittest.TestCase):
    def test_divergence_selects_cold_without_fct_or_history(self):
        off, s, e = markets()
        result = cold_divergence([s, e], off)
        self.assertEqual([x['horse'] for x in result['candidates']], [5])
        self.assertTrue(result['observation_only'])

    def test_late_stale_and_incomplete_snapshots_do_not_qualify(self):
        off, s, e = markets()
        for mutate in ('late', 'stale', 'missing', 'future_source'):
            bad = copy.deepcopy(e)
            if mutate == 'late': bad['received_at'] = (off-timedelta(minutes=3)).isoformat()
            if mutate == 'stale': bad['source_updated']['wp'] = (off-timedelta(minutes=10)).isoformat()
            if mutate == 'missing': bad['odds']['QPL'].pop('1-5')
            if mutate == 'future_source': bad['source_updated']['wp'] = (off-timedelta(minutes=3, seconds=11)).isoformat()
            self.assertEqual(cold_divergence([s, bad], off)['status'], 'unavailable')

    def test_capped_price_and_missing_baseline_are_not_signals(self):
        off, s, e = markets()
        s['odds']['QPL']['1-5'] = '999'
        self.assertEqual(cold_divergence([s, e], off)['candidates'], [])
        self.assertEqual(cold_divergence([e], off)['status'], 'unavailable')

    def test_changed_clock_or_field_requires_matching_baseline(self):
        off, s, e = markets()
        s['post_time'] = '12:55'
        self.assertEqual(cold_divergence([s, e], off)['status'], 'unavailable')

    def test_turf_shadow_preserves_input_and_banker(self):
        t, c, p = turf(); saved = copy.deepcopy(t)
        result = turf_candidate(t, c, p)
        self.assertEqual(result['legs'], [4, 5, 6, 2])
        self.assertEqual(result['banker'], t['banker']); self.assertEqual(t, saved)
        self.assertTrue(result['observation_only'])

    def test_no_borrowing_future_results_duplicate_races_or_different_rails(self):
        t, c, p = turf()
        p[-1]['result']['received_at'] = '2026-10-04T16:01:00+08:00'
        self.assertFalse(turf_candidate(t, c, p)['active'])
        self.assertFalse(turf_candidate(t, c, [p[0]]*3)['active'])
        p[-1]['context']['rail'] = 'B'
        self.assertFalse(turf_candidate(t, c, p)['active'])

    def test_straight_mud_missing_and_late_context_do_not_change_legs(self):
        t, c, p = turf()
        for change in ({'track': 'AWT'}, {'distance': 1000}, {'rail': None},
                       {'prepared_at': '2026-10-04T16:01:00+08:00'}):
            r = turf_candidate(t, {**c, **change}, p)
            self.assertFalse(r['changed']); self.assertEqual(r['legs'], t['legs'])

    def test_card_retains_distance_and_rail_before_race(self):
        html = '''<p>Race 1 - TEST Sunday, October 04, 2026, Sha Tin, 12:30
        Turf - "A+3" Course, 1400M Prize Money: $1</p><table class="starter"><tr><td>1</td>
        <td><a href="/horse?horseid=HK_2023_J309">Horse</a></td></tr></table>'''
        c = parse_card(html, '2026-10-04', 'ST', 1)
        self.assertEqual((c['distance'], c['rail']), (1400, 'A+3'))

    def test_missing_local_archive_does_not_block_observation(self):
        off, s, e = markets(); t, c, _ = turf()
        with tempfile.TemporaryDirectory() as root:
            out = observe(t, [s, e], off, c, Path(root)/'hkjc-early')
        self.assertEqual(out['turf']['prior_races'], [])
        self.assertEqual(out['cold_divergence']['status'], 'ready')


if __name__ == '__main__': unittest.main()
