import unittest
from cold_history import parse_card, parse_last_run, parse_field_size, parse_trials


class HistoryTests(unittest.TestCase):
    def test_declared_horse_and_jockey_identifiers_with_surface(self):
        data='''<p>Race 1 - TEST HANDICAP Sunday, October 04, 2026, Sha Tin, 12:30 All Weather Track, 1650M Prize Money: $1</p>
        <table class="starter"><tr><td>1</td><td><a href="/horse?horseid=HK_2023_J309">Horse</a></td>
        <td><a href="/jockeyprofile?jockeyid=YHY">Rider</a></td></tr></table>'''
        card=parse_card(data,'2026-10-04','ST',1)
        self.assertEqual(card['track'],'AWT')
        self.assertEqual(card['entries'][1]['horseid'],'HK_2023_J309')
        self.assertEqual(card['entries'][1]['jockeyid'],'YHY')
        with self.assertRaises(ValueError):parse_card(data,'2026-10-01','ST',1)

    def test_current_day_results_are_excluded_before_last_race_lookup(self):
        data='''<table class="horseProfile"></table><table class="bigborder">
        <tr><td>050</td><td>1</td><td>04/10/26</td><td>ST / Turf</td><td>1200</td><td><a href="/localresults?racedate=2026/10/04">result</a></td></tr>
        <tr><td>040</td><td>2</td><td>27/09/26</td><td>ST / AWT</td><td>1200</td><td><a href="/localresults?racedate=2026/09/27">result</a></td></tr></table>'''
        last=parse_last_run(data,'2026-10-04')
        self.assertEqual(last['past_date'],'2026-09-27');self.assertEqual(last['track'],'AWT')
        with self.assertRaises(ValueError):parse_last_run('<p>Service unavailable</p>','2026-10-04')

    def test_trial_finish_uses_last_running_position_and_heat_size(self):
        data='''<div class="divFLeft general_eng_text">29/09/2026</div><table>Batch 1</table><table class="bigborder">
        <tr><td><a href="/horse?horseid=HK_2023_J309">Horse</a></td><td></td><td></td><td></td><td></td><td></td><td>4 2 1</td><td>1.02.34</td><td>Passed</td><td></td></tr>
        <tr><td><a href="/horse?horseid=HK_2023_J508">Horse</a></td><td></td><td></td><td></td><td></td><td></td><td>1 1 2</td><td>1.03.34</td><td>Failed</td><td></td></tr></table>'''
        rows=parse_trials(data,'2026-09-29')
        self.assertEqual(rows[0]['trial_rank'],1);self.assertEqual(rows[0]['trial_score'],1)
        self.assertTrue(rows[1]['trial_failed'])
        with self.assertRaises(ValueError):parse_trials(data,'2026-09-28')

    def test_non_finisher_counts_as_starter_but_withdrawn_does_not(self):
        data='<div class="performance"><table><tbody>'+''.join(f'<tr><td>{p}</td><td>{h}</td><td>Horse</td></tr>' for p,h in [('1',2),('UR',3),('WV',4)])+'</tbody></table></div>'
        self.assertEqual(parse_field_size(data),2)


if __name__ == '__main__':unittest.main()
