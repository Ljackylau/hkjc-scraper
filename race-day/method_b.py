"""Conditional banker replacement from contemporaneous HKJC WIN/PLA/QPL quotes."""
import math
from datetime import datetime, timedelta


def _time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _features(snapshot):
    odds = snapshot['odds']
    def positive(value):
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError('invalid odds')
        return number
    win = {int(h): positive(v) for h, v in odds['WIN'].items()}
    place = {int(h): positive(v) for h, v in odds['PLA'].items()}
    horses = set(win)
    if len(horses) < 5 or set(place) != horses:
        raise ValueError('incomplete WIN/PLA field')
    pairs = {}
    for key, value in odds['QPL'].items():
        a, b = sorted(map(int, key.split('-')))
        if a == b or a not in horses or b not in horses:
            raise ValueError('QPL pair outside active field')
        pairs[a, b] = 1 / positive(value)
    if len(pairs) != len(horses) * (len(horses) - 1) // 2:
        raise ValueError('incomplete QPL pairs')
    inv = {h: 1 / place[h] for h in horses}
    total = sum(inv.values())
    pair_total = sum(pairs.values())
    q = {h: 0.0 for h in horses}
    for (a, b), value in pairs.items():
        q[a] += value / pair_total / 2
        q[b] += value / pair_total / 2
    return win, place, {h: inv[h] / total for h in horses}, q


def _fresh(sample, boundary, seconds):
    received = _time(sample['received_at'])
    if received > boundary:
        return False
    return all(0 <= (received - _time(sample['source_updated'][pool])).total_seconds()
               and 0 <= (boundary - _time(sample['source_updated'][pool])).total_seconds() <= seconds
               for pool in ('wp', 'wpq'))


def prepare(samples, off, date, race):
    """Freeze the latest available quotes at T−10 and T−3:10; never use later quotes."""
    off = _time(off) if isinstance(off, str) else off
    baseline_at = off - timedelta(minutes=10)
    freeze = off - timedelta(minutes=3, seconds=10)
    base = final = None
    ordered = sorted((s for s in samples if s.get('post_time') == off.strftime('%H:%M')),
                     key=lambda s: _time(s['received_at']))
    for sample in ordered:
        if _fresh(sample, baseline_at, 180):
            base = sample
        if _fresh(sample, freeze, 120):
            final = sample
    common = {'date': date, 'race': race, 'off': off.isoformat(),
              'freeze': freeze.isoformat(), 'method': 'B: max mean PLA and QPL share gain'}
    if base is None or final is None:
        return {**common, 'status': 'unavailable', 'reason': 'T−10 or pre-T−3 market quote unavailable or stale'}
    try:
        bw, bp, bps, bqs = _features(base)
        fw, fp, fps, fqs = _features(final)
        if set(bw) != set(fw):
            raise ValueError('active field changed between snapshots')
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        return {**common, 'status': 'unavailable', 'reason': str(exc)}
    horses = {str(h): {'base_win': bw[h], 'final_win': fw[h],
                        'base_place': bp[h], 'final_place': fp[h],
                        'place_share_gain': fps[h] - bps[h],
                        'qpl_share_gain': fqs[h] - bqs[h],
                        'score': ((fps[h] - bps[h]) + (fqs[h] - bqs[h])) / 2}
              for h in sorted(bw)}
    return {**common, 'status': 'ready', 'baseline_received_at': base['received_at'],
            'final_received_at': final['received_at'], 'horses': horses}


def decide(source, original, lock_time):
    """Keep the original unless the data are aligned and raw WIN falls while PLA rises."""
    answer = {'status': 'kept', 'original_banker': int(original), 'banker': int(original),
              'reason': 'B condition not met'}
    if not source or source.get('status') != 'ready':
        answer['reason'] = (source or {}).get('reason', 'B market data unavailable')
        return answer
    try:
        if _time(source['off']) - timedelta(minutes=3) != _time(lock_time):
            raise ValueError('HKJC schedule does not match Horse103 lock')
        rows = source['horses']
        old = rows[str(original)]
        if len(rows) < 5:
            raise ValueError('B market field incomplete')
        answer.update(baseline_received_at=source['baseline_received_at'],
                      final_received_at=source['final_received_at'],
                      original_win=[old['base_win'], old['final_win']],
                      original_place=[old['base_place'], old['final_place']])
        if old['final_win'] < old['base_win'] and old['final_place'] > old['base_place']:
            choice = min((int(h) for h in rows if int(h) != int(original)),
                         key=lambda h: (-rows[str(h)]['score'], h))
            answer.update(status='switched', banker=choice, score=rows[str(choice)]['score'],
                          reason='Original WIN shorter and PLA longer; largest PLA/QPL share gain')
    except (KeyError, ValueError, TypeError) as exc:
        answer['reason'] = str(exc)
    return answer
