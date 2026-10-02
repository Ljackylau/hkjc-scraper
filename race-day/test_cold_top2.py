import asyncio
import copy
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from cold_policy_v2 import select, VERSION
from cold_top2_live import prepare
from cold_policy import format_cold
from independent_tip import message
import hkjc_shadow


def cases():
    with gzip.open(Path(__file__).with_name('fixtures') / 'cold_v2_replay.json.gz', 'rt') as f:
        return json.load(f)


def journals(case):
    p, early = case['pack'], case['early']
    wp = [p['start_q'], p['end_wp']]
    fct = [p['end_fct']]
    if p.get('start_fct'):
        wp.append(p['start_fct_wp']); fct.append(p['start_fct'])
    if early:
        wp += [early['start_wp'], early['end_wp']]
        fct.append(early['end_fct'])
    # Preparation receipts are simulated here; fixture history contains no
    # current race labels and is not presented as a historic live capture.
    context = {'status': 'ready', 'date': p['day'], 'race': p['race'],
               'prepared_at': p['start_q']['received_at'],
               'prior_form': case['prior_form'], 'metadata': case['metadata']}
    return wp, fct, context


class ColdTopTwoTests(unittest.TestCase):
    def test_all_30_frozen_candidates_are_unchanged(self):
        for case in cases():
            p = case['pack']
            with self.subTest(day=p['day'], race=p['race']):
                chosen = select(p, case['early'], {int(k): v for k, v in case['prior_form'].items()},
                                {int(k): v for k, v in case['metadata'].items()})
                self.assertEqual(chosen['candidate'], case['expected'])

    def test_live_journal_adapter_matches_all_30_candidates(self):
        for case in cases():
            p = case['pack']; wp, fct, context = journals(case)
            with self.subTest(day=p['day'], race=p['race']):
                result = prepare(wp, fct, datetime.fromisoformat(p['off']), p['day'], p['race'], context)
                self.assertEqual(result['cold_status'], 'ready', result.get('cold_reason'))
                self.assertEqual(result['cold'], [case['expected']])
                self.assertGreater(result['cold_win'], 10)

    def test_missing_and_late_pool_fail_closed(self):
        case = cases()[0]; p = case['pack']; wp, fct, context = journals(case)
        off = datetime.fromisoformat(p['off'])
        for rows in ([], [{**p['end_fct'], 'captured': (off - timedelta(minutes=3)).isoformat()}]):
            result = prepare(wp, rows, off, p['day'], p['race'], context)
            self.assertEqual(result['cold_status'], 'unavailable')
            self.assertEqual(result['cold'], [])
        context['prepared_at'] = (off - timedelta(minutes=3)).isoformat()
        self.assertIn('遲於截止', prepare(wp, fct, off, p['day'], p['race'], context)['cold_reason'])

    def test_incomplete_fct_and_wrong_metadata_are_not_silent_fallbacks(self):
        case = cases()[0]; p = case['pack']; wp, fct, context = journals(case)
        off = datetime.fromisoformat(p['off']); bad = copy.deepcopy(fct)
        for row in bad:
            row['odds'].pop(next(iter(row['odds'])))
        self.assertEqual(prepare(wp, bad, off, p['day'], p['race'], context)['cold_status'], 'unavailable')
        context['date'] = '2020-01-01'
        self.assertEqual(prepare(wp, fct, off, p['day'], p['race'], context)['cold_status'], 'unavailable')

    def test_cold_is_not_hidden_when_it_is_also_banker_or_banker_is_unavailable(self):
        tip = {'cold_policy': VERSION, 'cold_status': 'ready', 'cold': [9], 'banker': 9,
               'cold_branch_label': '二重彩第二位市場支持', 'status': 'unavailable', 'reason': '缺T−10'}
        self.assertIn('9號', format_cold(tip))
        self.assertIn('9號', message(8, tip))

    def test_deadline_freeze_requests_publish_before_notification_wait(self):
        case = cases()[0]; p = case['pack']; wp, fct, context = journals(case)
        off = datetime.fromisoformat(p['off']); frozen = {}
        async def exercise():
            event = asyncio.Event()
            async def notify(number, tip, folder):
                self.assertTrue(event.is_set())
                self.assertEqual(frozen[str(number)]['cold'], [case['expected']])
                hkjc_shadow.atomic(folder / f'race_{number:02d}_independent_notification.json', {'status': 'not_configured'})
            with tempfile.TemporaryDirectory() as tmp:
                with patch.object(hkjc_shadow, 'now', return_value=off-timedelta(minutes=3,seconds=9)), \
                     patch.object(hkjc_shadow, 'notify_independent', side_effect=notify):
                    await hkjc_shadow.freeze_independent(lambda: (off, wp, None), Path(tmp), p['race'], p['day'], [], {},
                                                        lambda: (fct, context), event, frozen)
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
