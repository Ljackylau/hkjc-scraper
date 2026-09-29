import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from method_b import decide, prepare
from runner import format_tip_message

HK = timezone(timedelta(hours=8))
OFF = datetime(2026, 9, 30, 20, 0, tzinfo=HK)


def quote(minutes, win1, place1, pair1=2):
    at = OFF - timedelta(minutes=minutes)
    horses = range(1, 6)
    return {'post_time': '20:00', 'received_at': at.isoformat(),
            'source_updated': {'wp': at.isoformat(), 'wpq': at.isoformat()},
            'odds': {'WIN': {str(h): str(win1 if h == 1 else 10) for h in horses},
                     'PLA': {str(h): str(place1 if h == 1 else 3) for h in horses},
                     'QPL': {f'{a}-{b}': str(pair1 if a == 2 or b == 2 else 10)
                             for a in horses for b in horses if a < b}}}


class MethodBTests(unittest.TestCase):
    def test_switch_uses_support_share_and_matches_telegram(self):
        base = quote(10, 6, 1.5, 10)
        final = quote(3.3, 5, 2, 2)
        source = prepare([base, final], OFF, '2026-09-30', 1)
        chosen = decide(source, 1, (OFF-timedelta(minutes=3)).isoformat())
        self.assertEqual((chosen['status'], chosen['banker']), ('switched', 2))
        snapshot = {'ranking': [{'horse_number': h, 'qp_amount': 10} for h in range(1, 6)],
                    'method_b': chosen, 'live103_raw': {'candidates': [{'horseNumber': h} for h in range(1, 6)]}}
        tip = format_tip_message(1, snapshot, [1, 2, 3], [])
        self.assertIn('獨贏&位置信心馬：2號（B換膽，原1號）', tip)
        self.assertIn('連贏位置Q：2號 拖 1號、3號', tip)

    def test_future_quote_cannot_change_a_decision(self):
        base = quote(10, 6, 1.5)
        pre = quote(3.3, 6, 1.5)
        after_freeze = quote(3.05, 5, 2, 1.1)
        source = prepare([base, pre, after_freeze], OFF, '2026-09-30', 1)
        chosen = decide(source, 1, (OFF-timedelta(minutes=3)).isoformat())
        self.assertEqual(chosen['status'], 'kept')
        self.assertEqual(source['final_received_at'], pre['received_at'])

    def test_missing_pairs_or_mismatched_lock_preserves_original(self):
        base = quote(10, 6, 1.5)
        final = quote(3.3, 5, 2)
        del final['odds']['QPL']['1-2']
        source = prepare([base, final], OFF, '2026-09-30', 1)
        self.assertEqual(decide(source, 1, (OFF-timedelta(minutes=3)).isoformat())['status'], 'kept')
        valid = prepare([base, quote(3.3, 5, 2)], OFF, '2026-09-30', 1)
        wrong = decide(valid, 1, (OFF-timedelta(minutes=8)).isoformat())
        self.assertEqual((wrong['banker'], wrong['status']), (1, 'kept'))


if __name__ == '__main__':
    unittest.main()
