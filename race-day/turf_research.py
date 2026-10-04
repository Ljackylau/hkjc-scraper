"""Frozen turf/cold observations. These outputs never overwrite published picks.

Inner-draw thresholds were explored on 2026-10-04: prospective validation only.
Cold divergence thresholds were fixed in the 2026-10-01 study.
"""
import itertools
import json
import math
from datetime import timedelta

from independent_candidate import dt, validate

VERSION = 'turf_cold_shadow_2026_10_04'


def cold_divergence(samples, off):
    freeze = off - timedelta(minutes=3, seconds=10)
    clock = off.strftime('%H:%M')
    output = {'version': VERSION, 'status': 'unavailable', 'candidates': [],
              'freeze': freeze.isoformat(), 'observation_only': True}
    valid = []
    for sample in samples:
        try:
            validate(sample, freeze, clock, 120)
            if any(dt(sample['source_updated'][p]) > dt(sample['received_at']) for p in ('wp', 'wpq')):
                continue
            valid.append(sample)
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
    if not valid:
        return {**output, 'reason': '缺有效截止前終點'}
    end = max(valid, key=lambda s: dt(s['received_at']))
    field = set(end['odds']['WIN'])
    starts = []
    for sample in samples:
        try:
            received = dt(sample['received_at'])
            if not 25 <= (off - received).total_seconds() / 60 <= 32:
                continue
            if validate(sample, received, clock, 180) != field:
                continue
            if any(dt(sample['source_updated'][p]) > received for p in ('wp', 'wpq')):
                continue
            starts.append(sample)
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
    if not starts:
        return {**output, 'reason': '缺同開跑時間、同出馬名單的T−32至T−25基準'}
    start = min(starts, key=lambda s: (abs((off-dt(s['received_at'])).total_seconds()-1800), dt(s['received_at'])))
    a, b = start['odds'], end['odds']
    favorite = min(field, key=lambda h: (float(b['WIN'][h]), int(h)))
    candidates = []
    for h in sorted(field, key=int):
        if h == favorite or float(b['WIN'][h]) <= 10:
            continue
        key = '-'.join(sorted((h, favorite), key=int))
        prices = [float(z[p][key]) for z in (a, b) for p in ('QIN', 'QPL')]
        # 999 is a capped quote, not a measured price decline.
        if max(prices) >= 999:
            continue
        q = 1-float(b['QIN'][key])/float(a['QIN'][key])
        qp = 1-float(b['QPL'][key])/float(a['QPL'][key])
        if (float(b['WIN'][h]) > float(a['WIN'][h])
                and float(b['PLA'][h]) > float(a['PLA'][h]) and q >= .15 and qp >= .15):
            candidates.append({'horse': int(h), 'win': float(b['WIN'][h]),
                               'favorite': int(favorite), 'q_drop': q, 'qp_drop': qp})
    return {**output, 'status': 'ready', 'candidates': candidates,
            'start_received_at': start['received_at'], 'end_received_at': end['received_at']}


def inside_expectation(rows):
    """Market-adjusted descriptive proxy, not calibrated finishing probabilities."""
    draws = {int(r[0]): int(r[3]) for r in rows}
    raw = {int(r[0]): 1/float(r[7]) for r in rows}
    if len(draws) < 5 or len(set(draws.values())) != len(draws) or any(d <= 0 for d in draws.values()):
        raise ValueError('Invalid declared draws')
    if any(not math.isfinite(v) or v <= 0 for v in raw.values()):
        raise ValueError('Invalid WIN')
    inside = {h for h, draw in draws.items() if 0 < draw <= math.ceil(len(draws)/3)}
    w = {h: v/sum(raw.values()) for h, v in raw.items()}
    expected = sum(w[i]*w[j]/(1-w[i])*w[k]/(1-w[i]-w[j])
                   * sum(h in inside for h in (i, j, k))
                   for i, j, k in itertools.permutations(w, 3))
    return inside, expected


def turf_candidate(tip, context, prior):
    output = {'version': VERSION, 'status': 'unavailable', 'observation_only': True,
              'banker': tip.get('banker'), 'legs': tip.get('legs', []), 'changed': False}
    try:
        freeze = dt(tip['freeze'])
        if tip.get('status') != 'ready' or dt(tip['received_at']) > freeze:
            raise ValueError('缺截止前有效主膽及拖腳')
        if (context.get('status') != 'ready' or context['date'] != tip['date']
                or int(context['race']) != int(tip['race']) or dt(context['prepared_at']) > freeze):
            raise ValueError('缺截止前有效場地資料')
        if context.get('track') != 'TURF' or not 1200 <= context.get('distance', 0) <= 1800:
            return {**output, 'status': 'not_applicable', 'reason': '泥地、直路及其他途程獨立處理'}
        if not context.get('rail'):
            raise ValueError('缺賽前欄位；不混合不同欄位')
        inside, _ = inside_expectation(tip['runner_rows'])
        usable = []
        for row in prior:
            c, t, result = row['context'], row['tip'], row['result']
            if (c.get('status') != 'ready' or c.get('date') != tip['date']
                    or t.get('date') != tip['date'] or int(t['race']) >= int(tip['race'])
                    or c.get('race') != t.get('race') or c.get('venue') != context.get('venue')
                    or c.get('track') != 'TURF' or c.get('rail') != context['rail']
                    or not 1200 <= c.get('distance', 0) <= 1800
                    or t.get('status') != 'ready' or dt(c['prepared_at']) > dt(t['freeze'])
                    or dt(t['received_at']) > dt(t['freeze']) or dt(result['received_at']) > freeze):
                continue
            previous_inside, expected = inside_expectation(t['runner_rows'])
            top = list(map(int, result['top4'][:3]))
            if len(top) != 3 or len(set(top)) != 3 or not set(top).issubset({int(r[0]) for r in t['runner_rows']}):
                continue
            usable.append({'race': t['race'], 'received_at': result['received_at'],
                           'observed': sum(h in previous_inside for h in top), 'expected': expected})
        # Duplicate files cannot turn one completed race into three observations.
        usable = list({r['race']: r for r in usable}.values())
        excess = sum(r['observed']-r['expected'] for r in usable)
        active = len(usable) >= 3 and excess >= 2
        output.update(status='ready', prior_races=usable, inside_excess=excess, active=active)
        legs = list(map(int, tip['legs']))
        if tip.get('legs_status') != 'ready' or len(legs) != 4 or len(set(legs)) != 4 or tip['banker'] in legs:
            raise ValueError('缺完整原四腳')
        if not active or sum(h in inside for h in legs) >= 2:
            return output
        scores = {int(h): float(v) for h, v in tip['leg_scores'].items() if math.isfinite(float(v))}
        add = sorted((h for h in inside if h not in legs and h != tip['banker'] and h in scores), key=lambda h: (-scores[h], h))
        remove = sorted((h for h in legs if h not in inside and h in scores), key=lambda h: (scores[h], -legs.index(h)))
        if add and remove:
            legs[legs.index(remove[0])] = add[0]
            output.update(legs=legs, changed=True, added=add[0], removed=remove[0])
        return output
    except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        return {**output, 'status': 'unavailable', 'reason': str(exc)[:160], 'legs': tip.get('legs', []), 'changed': False}


def observe(tip, samples, off, context, folder):
    """Only local archived inputs; no requests or notification side effects."""
    prior = []
    for phase in ('early', 'late'):
        for path in sorted((folder.parent / ('hkjc-'+phase)).glob('race_*_independent.json')):
            try:
                number = int(path.stem.split('_')[1])
                if number >= int(tip['race']):
                    continue
                c = json.loads(path.with_name(f'race_{number:02d}_cold_history.json').read_text())
                t = json.loads(path.read_text())
                result = json.loads((folder.parent/phase/'results'/f'race_{number:02d}.json').read_text())
                prior.append({'context': c, 'tip': t, 'result': result})
            except (OSError, ValueError, TypeError):
                continue
    return {'version': VERSION, 'observation_only': True,
            'turf': turf_candidate(tip, context or {}, prior),
            'cold_divergence': cold_divergence(samples, off)}
