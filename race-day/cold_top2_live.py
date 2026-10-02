"""Pre-deadline adapter for the frozen 2026-10-02 one-cold-horse policy.

No result lookup, late odds fallback, or trainer-challenge dependency. The
selector is unchanged from the exploratory 14/30 study. Missing core pools
or unfinished historical preparation produce an explicit unavailable state.
"""
from datetime import datetime, timedelta
import itertools
import json
from pathlib import Path
import re

from cold_policy_v2 import select, VERSION

ACTIVATION_DATE = '2026-10-02'
BRANCH_LABELS = {
    'late_entry': '最後兩分鐘新入市場訊號',
    'rider_trial_same_context': '強騎師＋最近30日有效試閘前三＋同場地、同跑道',
    'confirmed_prior_form': '原B＋賽績確認',
    'market_second': '二重彩第二位市場支持',
}


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Missing timestamp timezone')
    return result


def wp_valid(row, at, max_age, same_clock=None):
    try:
        received = stamp(row['received_at'])
        return (received <= at and (same_clock is None or row.get('post_time') == same_clock)
                and all(stamp(row['source_updated'][p]) <= received
                        and 0 <= (at - stamp(row['source_updated'][p])).total_seconds() <= max_age
                        for p in ('wp', 'wpq'))
                and all(row.get('odds', {}).get(p) for p in ('WIN', 'PLA', 'QIN', 'QPL')))
    except (ValueError, KeyError, TypeError):
        return False


def fct_valid(row, at, max_age, same_clock=None):
    try:
        source, received = stamp(row['source_updated']), stamp(row['captured'])
        return (row.get('pool', 'FCT') == 'FCT' and bool(row.get('odds'))
                and source <= received <= at and 0 <= (at - source).total_seconds() <= max_age
                and (not row.get('post_time') or same_clock is None or row['post_time'] == same_clock))
    except (ValueError, KeyError, TypeError):
        return False


def assemble_pack(samples, fcts, off, cut, date, number):
    clock = off.strftime('%H:%M')
    endpoints = [s for s in samples if wp_valid(s, cut, 120, clock)]
    starts = [s for s in samples if off - timedelta(minutes=32) <= stamp(s['received_at']) <= off - timedelta(minutes=25)
              and wp_valid(s, stamp(s['received_at']), 180) and stamp(s['received_at']) <= cut]
    ends_fct = [s for s in fcts if fct_valid(s, cut, 120, clock)]
    if not endpoints:
        raise ValueError('缺T−3截止前120秒內完整獨贏／位置／連贏／位置Q快照')
    if not starts:
        raise ValueError('缺T−32至T−25有效比較基準；請提早啟動Runner')
    if not ends_fct:
        raise ValueError('缺截止前120秒內有效二重彩快照')
    end = max(endpoints, key=lambda s: stamp(s['received_at']))
    start = min(starts, key=lambda s: abs((off - stamp(s['received_at'])).total_seconds() - 1800))
    end_fct = max(ends_fct, key=lambda s: stamp(s['captured']))
    horses = sorted(end['odds']['WIN'], key=int)
    if set(horses) != set(end['odds']['PLA']):
        raise ValueError('獨贏及位置出馬名單不一致')
    pairs = {'-'.join(p) for p in itertools.combinations(horses, 2)}
    directed = {a + '-' + b for a in horses for b in horses if a != b}
    if any(not pairs.issubset(end['odds'][p]) for p in ('QIN', 'QPL')):
        raise ValueError('缺完整連贏／位置Q組合')
    if not directed.issubset(end_fct['odds']):
        raise ValueError('缺完整二重彩方向組合')
    long_fct = [s for s in fcts if off - timedelta(minutes=32) <= stamp(s['captured']) <= off - timedelta(minutes=25)
                and fct_valid(s, stamp(s['captured']), 180) and stamp(s['captured']) <= cut]
    start_fct = start_fct_wp = None
    for f in sorted(long_fct, key=lambda s: abs((off - stamp(s['captured'])).total_seconds() - 1800)):
        at = stamp(f['captured'])
        available = [s for s in samples if stamp(s['received_at']) <= at
                     and s.get('odds', {}).get('WIN') and s.get('source_updated', {}).get('wp')
                     and stamp(s['source_updated']['wp']) <= stamp(s['received_at'])
                     and 0 <= (at - stamp(s['source_updated']['wp'])).total_seconds() <= 180]
        if available:
            start_fct, start_fct_wp = f, max(available, key=lambda s: stamp(s['received_at']))
            break
    return {'day': date, 'race': number, 'cut': cut.isoformat(), 'off': off.isoformat(),
            'start_q': start, 'end_wp': end, 'start_fct': start_fct,
            'start_fct_wp': start_fct_wp, 'end_fct': end_fct}


def jockey_strengths():
    profiles = json.loads(Path(__file__).with_name('jockey_profiles_2025_26.json').read_text())
    p0 = sum(p['placed'] for p in profiles.values()) / sum(p['n'] for p in profiles.values())
    return {j: (p['placed'] + 50 * p0) / (p['n'] + 50) for j, p in profiles.items()}


def prepare(samples, fcts, off, date, number, context, audit=None):
    cut = off - timedelta(minutes=3, seconds=10)
    result = {'cold': [], 'cold_status': 'unavailable', 'cold_policy': VERSION,
              'cold_freeze': cut.isoformat(), 'cold_target': 'top2',
              'cold_probability_calibrated': False, 'cold_group': [], 'cold_missing': []}
    try:
        pack = assemble_pack(samples, fcts, off, cut, date, number)
        if context.get('status') != 'ready':
            raise ValueError('賽前往績／試閘資料未準備完成：' + context.get('reason', context.get('status', 'missing')))
        if context.get('date') != date or int(context.get('race', -1)) != number:
            raise ValueError('往績資料日期／場次不符')
        if stamp(context['prepared_at']) > cut:
            raise ValueError('往績資料準備時間遲於截止')
        prior = {int(h): p for h, p in context['prior_form'].items()}
        metadata = {int(h): dict(p) for h, p in context['metadata'].items()}
        active = {int(h) for h, v in pack['end_wp']['odds']['WIN'].items() if float(v) > 10}
        if not active.issubset(prior) or not active.issubset(metadata):
            raise ValueError('出馬名單更新；缺新增馬匹賽前往績')
        if pack['start_fct'] is None:
            result['cold_missing'].append({'reason': '缺長窗二重彩基準；增長項用凍結公式的中性排名'})
        # A late jockey change is taken from the last pre-cutoff live roster.
        names = json.loads(Path(__file__).with_name('jockey_name_ids.json').read_text())
        strengths = jockey_strengths()
        rows = pack['end_wp'].get('runner_rows', [])
        for row in rows:
            if len(row) > 5 and str(row[0]).isdigit() and int(row[0]) in metadata:
                name = re.sub(r'\s*\([^)]*\)', '', row[5]).strip()
                jid = names.get(name)
                metadata[int(row[0])]['jockey_strength'] = strengths.get(jid)
        early = None
        try:
            e = assemble_pack(samples, fcts, off, off - timedelta(minutes=5), date, number)
            early = {'cut': e['cut'], 'start_wp': e['start_q'], 'end_wp': e['end_wp'], 'end_fct': e['end_fct']}
        except ValueError:
            result['cold_missing'].append({'reason': '缺有效T−5比較快照；新入訊號分支不適用'})
        chosen = select(pack, early, prior, metadata)
        candidate = chosen.get('candidate')
        result.update(cold_status='ready', cold=[] if candidate is None else [candidate],
                      cold_branch=chosen.get('branch'), cold_branch_label=BRANCH_LABELS.get(chosen.get('branch'), ''),
                      cold_win=float(pack['end_wp']['odds']['WIN'][str(candidate)]) if candidate is not None else None,
                      cold_received_at=pack['end_wp']['received_at'], cold_fct_received_at=pack['end_fct']['captured'],
                      cold_sources={'wp': pack['end_wp']['source_updated'], 'fct': pack['end_fct']['source_updated'],
                                    'historical_prepared_at': context['prepared_at']},
                      cold_partial=bool(result['cold_missing']))
        if audit is not None:
            audit.update(selection=chosen, inputs=pack, early_inputs=early, prior_form=prior, metadata=metadata)
        return result
    except (ValueError, KeyError, TypeError, AssertionError, ZeroDivisionError, OverflowError):
        import sys
        reason = str(sys.exc_info()[1]) or '市場快照或歷史日期驗證失敗'
        return {**result, 'cold_reason': reason[:200]}
