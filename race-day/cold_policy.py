"""Trainer quote validity uses observed receipt, preserving publication age."""
from datetime import datetime

POLICY = 'post_previous_off_receipt120_v3'

def calculate(tip, rows):
    answer = {'cold': [], 'cold_status': 'unavailable', 'cold_policy': POLICY}
    def fail(reason):
        return {**answer, 'cold_reason': reason}
    if int(tip['race']) == 1:
        return {**answer, 'cold_status': 'ready'}
    stamp = lambda s: datetime.fromisoformat(s)
    freeze = stamp(tip['freeze'])
    rows = [r for r in rows if r.get('received_at') and stamp(r['received_at']) <= freeze]
    if not rows:
        return fail('截止前沒有練王讀取紀錄')
    latest = max(rows, key=lambda r: stamp(r['received_at']))
    if (freeze-stamp(latest['received_at'])).total_seconds() > 120:
        return fail('截止前120秒內未成功讀取練王報價')
    if latest.get('state') != 'observed':
        return fail('練王暫停受注或未有可讀報價')
    context = latest.get('race_context', [])
    previous = next((r for r in context if int(r['race_number']) == int(tip['race'])-1), None)
    if not previous:
        return fail('缺上一場開跑時間')
    off = stamp(previous['post_time'])
    source = latest.get('source_updated_at')
    if not source or not off < stamp(source) <= stamp(latest['received_at']):
        return fail('上一場後未有更新報價')
    before = [r for r in rows if stamp(r['received_at']) <= off]
    if not before:
        return fail('缺上一場開跑前的比較報價')
    baseline = max(before, key=lambda r: stamp(r['received_at']))
    bs = baseline.get('source_updated_at')
    if baseline.get('state') != 'observed' or not bs or stamp(bs) > stamp(baseline['received_at']) or (off-stamp(baseline['received_at'])).total_seconds() > 120:
        return fail('缺上一場開跑前120秒內的有效比較報價')
    identity = lambda r: sorted((str(p.get('selection_id', p['name'])), ''.join(p['name'].split())) for p in r.get('participants', []))
    if not identity(latest) or identity(latest) != identity(baseline):
        return fail('練王選項不完整或前後不一致')
    old = {''.join(p['name'].split()): p.get('current_odds') for p in baseline['participants']}
    current = {''.join(p['name'].split()): p.get('current_odds') for p in latest['participants']}
    trainers = {int(r[0]): ''.join(str(r[6]).split()) for r in tip.get('runner_rows', [])}
    market = list(tip.get('market', []))[:5]
    candidates = []
    for horse in market:
        name = trainers.get(int(horse))
        a, b = old.get(name), current.get(name)
        if not name or not isinstance(a, (int,float)) or not isinstance(b, (int,float)) or a <= 1 or b <= 1:
            return fail('市場頭5練馬師缺可比較數字報價')
        if 100*(a-b)/a >= 15:
            candidates.append(horse)
    return {**answer, 'cold_status': 'ready', 'cold': candidates,
            'cold_received_at': latest['received_at'], 'cold_source_updated_at': source,
            'cold_quote_age_seconds': (freeze-stamp(source)).total_seconds(),
            'cold_receipt_age_seconds': round((freeze-stamp(latest['received_at'])).total_seconds(),3),
            'cold_baseline_source_updated_at': bs, 'cold_baseline_received_at': baseline['received_at']}
