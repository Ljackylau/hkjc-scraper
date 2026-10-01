"""Trainer quote validity uses observed receipt, preserving publication age."""
from datetime import datetime

POLICY = 'post_previous_off_receipt120_partial_v4'

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
    old = {''.join(p['name'].split()): p for p in baseline.get('participants', []) if not p.get('is_other')}
    current = {''.join(p['name'].split()): p for p in latest.get('participants', []) if not p.get('is_other')}
    trainers = {int(r[0]): ''.join(str(r[6]).split()) for r in tip.get('runner_rows', [])}
    market = list(tip.get('market', []))[:5]
    candidates, missing, compared = [], [], []
    for horse in market:
        name = trainers.get(int(horse))
        pa, pb = old.get(name, {}), current.get(name, {})
        a, b = pa.get('current_odds'), pb.get('current_odds')
        identity_ok = str(pa.get('selection_id', name)) == str(pb.get('selection_id', name))
        if not name or not identity_ok or not isinstance(a, (int,float)) or not isinstance(b, (int,float)) or a <= 1 or b <= 1:
            reason = '缺獨立練王選項' if not pa or not pb else ('練王選項前後不一致' if not identity_ok else '練王缺前後數字報價')
            missing.append({'horse': horse, 'trainer': name, 'reason': reason, 'before_text': pa.get('quote_text'), 'current_text': pb.get('quote_text')})
            continue
        compared.append(horse)
        if 100*(a-b)/a >= 15:
            candidates.append(horse)
    return {**answer, 'cold_status': 'ready' if compared else 'unavailable', 'cold': candidates,
            'cold_partial': bool(missing), 'cold_missing': missing, 'cold_compared': compared,
            **({'cold_reason':'市場頭5全部缺可比較練王報價'} if not compared else {}),
            'cold_received_at': latest['received_at'], 'cold_source_updated_at': source,
            'cold_quote_age_seconds': (freeze-stamp(source)).total_seconds(),
            'cold_receipt_age_seconds': round((freeze-stamp(latest['received_at'])).total_seconds(),3),
            'cold_baseline_source_updated_at': bs, 'cold_baseline_received_at': baseline['received_at']}

def format_cold(tip, horse=lambda n: f'{n}號'):
    missing = '、'.join(f'{r["horse"]}號' for r in tip.get('cold_missing', []))
    if tip.get('cold_status') != 'ready':
        return '無法判定：'+tip.get('cold_reason','缺有效報價')+(f'（資料不足：{missing}）' if missing else '')
    value = '、'.join(horse(n) for n in tip.get('cold', [])) or ('無符合（可比較部分）' if missing else '無')
    if missing: value += f'（部分資料不足：{missing}）'
    age = tip.get('cold_quote_age_seconds',0)
    return value+(f'（報價發布距今：{round(age)}秒）' if age>120 else '')
