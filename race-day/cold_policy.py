"""Strict pre-T3 individual trainer signal; Other quotes stay collective."""
import math
from datetime import datetime
POLICY='post_previous_off_receipt120_groups_exclude_banker_v6'

def compact(s):return ''.join(str(s or '').split())
def roster_complete(row):
    ps=row.get('participants',[])
    ids={str(p.get('selection_id')) for p in ps}
    return row.get('selection_roster_complete') is True or ids=={str(i) for i in range(1,22)}
def other(row):
    return next((p for p in row.get('participants',[]) if p.get('is_other') and str(p.get('selection_id'))=='21'),None)
def numeric(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>1

def calculate(tip,rows):
    answer={'cold':[],'cold_status':'unavailable','cold_policy':POLICY,'cold_group':[],'cold_excluded':[]}
    def fail(reason):return {**answer,'cold_reason':reason}
    if int(tip['race'])==1:return {**answer,'cold_status':'ready','cold_note':'首場沒有上一場比較'}
    stamp=lambda s:datetime.fromisoformat(s)
    freeze=stamp(tip['freeze'])
    rows=sorted((r for r in rows if r.get('received_at') and stamp(r['received_at'])<=freeze),key=lambda r:stamp(r['received_at']))
    if not rows:return fail('截止前沒有練王讀取紀錄')
    latest=rows[-1]
    context=latest.get('race_context',[])
    races=[int(r['race_number']) for r in context]
    # The pool closes at the penultimate off. No fresh final-race comparison exists.
    penultimate=next((r for r in context if races and int(r['race_number'])==max(races)-1),None)
    if races and int(tip['race'])==max(races) and penultimate and stamp(penultimate['post_time'])<=freeze:
        return {**answer,'cold_status':'ready','cold_applicable':False,'cold_note':'本場不適用：練王已於尾二場開跑截止'}
    if (freeze-stamp(latest['received_at'])).total_seconds()>120:return fail('截止前120秒內未成功讀取練王報價')
    if latest.get('state')!='observed':return fail('練王暫停受注或未有可讀報價')
    previous=next((r for r in context if int(r['race_number'])==int(tip['race'])-1),None)
    if not previous:return fail('缺上一場開跑時間')
    off=stamp(previous['post_time']);source=latest.get('source_updated_at')
    if not source or not off<stamp(source)<=stamp(latest['received_at']):return fail('上一場後未有更新報價')
    before=[r for r in rows if stamp(r['received_at'])<=off]
    if not before:return fail('缺上一場開跑前的比較報價')
    baseline=before[-1];bs=baseline.get('source_updated_at')
    if baseline.get('state')!='observed' or not bs or stamp(bs)>stamp(baseline['received_at']) or (off-stamp(baseline['received_at'])).total_seconds()>120:
        return fail('缺上一場開跑前120秒內的有效比較報價')
    old={compact(p['name']):p for p in baseline.get('participants',[]) if not p.get('is_other')}
    current={compact(p['name']):p for p in latest.get('participants',[]) if not p.get('is_other')}
    trainers={int(r[0]):compact(r[6]) for r in tip.get('runner_rows',[])}
    candidates=[];missing=[];compared=[];excluded=[];groups=[];changes=[]
    ga,gb=other(baseline),other(latest)
    group_ok=bool(ga and gb and roster_complete(baseline) and roster_complete(latest))
    group_drop=100*(ga['current_odds']-gb['current_odds'])/ga['current_odds'] if group_ok and numeric(ga.get('current_odds')) and numeric(gb.get('current_odds')) else None
    market=list(tip.get('market',[]))[:5]
    banker=tip.get('banker')
    for horse in market:
        if banker is not None and int(horse)==int(banker):continue
        name=trainers.get(int(horse));pa,pb=old.get(name,{}),current.get(name,{})
        a,b=pa.get('current_odds'),pb.get('current_odds')
        identity_ok=str(pa.get('selection_id',name))==str(pb.get('selection_id',name))
        # Membership only inferred from two complete official rosters, never a missing row.
        if name and not pa and not pb and group_ok:
            groups.append({'horse':horse,'trainer':name,'selection_id':'21','before_odds':ga.get('current_odds'),'current_odds':gb.get('current_odds'),
                           'drop_pct':group_drop,'qualifies':group_drop is not None and group_drop>=15,'scope':'collective_not_individual'})
            continue
        if name and pb and identity_ok and any(s in str(pb.get('quote_text','')) for s in ('未能勝出','不能勝出')):
            excluded.append({'horse':horse,'trainer':name,'reason':'練王選項已不能勝出；不是馬匹不能勝出'})
            continue
        if not name or not identity_ok or not numeric(a) or not numeric(b):
            reason='缺獨立練王選項' if not pa or not pb else ('練王選項前後不一致' if not identity_ok else '練王缺前後數字報價')
            missing.append({'horse':horse,'trainer':name,'reason':reason,'before_text':pa.get('quote_text'),'current_text':pb.get('quote_text')})
            continue
        compared.append(horse);drop=100*(a-b)/a
        changes.append({'horse':horse,'trainer':name,'before_odds':a,'current_odds':b,'drop_pct':drop,'selection_id':pb.get('selection_id')})
        if drop>=15:candidates.append(horse)
    known=bool(compared or groups or excluded or market and all(banker is not None and int(h)==int(banker) for h in market))
    return {**answer,'cold_status':'ready' if known else 'unavailable','cold':candidates,'cold_group':groups,'cold_excluded':excluded,'cold_changes':changes,
            'cold_partial':bool(missing),'cold_missing':missing,'cold_compared':compared,
            **({'cold_reason':'市場頭5全部缺可比較練王報價'} if not known else {}),
            'cold_received_at':latest['received_at'],'cold_source_updated_at':source,'cold_quote_age_seconds':(freeze-stamp(source)).total_seconds(),
            'cold_receipt_age_seconds':round((freeze-stamp(latest['received_at'])).total_seconds(),3),'cold_baseline_source_updated_at':bs,'cold_baseline_received_at':baseline['received_at']}

def format_cold(tip,horse=lambda n:f'{n}號'):
    if tip.get('cold_policy')=='cold_top2_priority_v2_exploratory_2026-10-02':
        if tip.get('cold_status')!='ready':return '資料不足：'+tip.get('cold_reason','等待有效賽前快照')
        selected=tip.get('cold',[])
        if not selected:return '無WIN>10候選'
        value='、'.join(horse(n) for n in selected)
        label=tip.get('cold_branch_label','')
        return value+(f'（{label}）' if label else '')+('；部分資料不足' if tip.get('cold_partial') else '')
    if tip.get('cold_applicable') is False:return tip['cold_note']
    missing='、'.join(f'{r["horse"]}號' for r in tip.get('cold_missing',[]))
    if tip.get('cold_status')!='ready':return '無法判定：'+tip.get('cold_reason','缺有效報價')+(f'（資料不足：{missing}）' if missing else '')
    value='、'.join(horse(n) for n in tip.get('cold',[]) if str(n)!=str(tip.get('banker'))) or ('無符合（可比較部分）' if missing else '無')
    group=[g for g in tip.get('cold_group',[]) if str(g['horse'])!=str(tip.get('banker'))]
    if group:
        qualified=[g['horse'] for g in group if g.get('qualifies')]
        if qualified:value+='；其他組合落飛：'+'、'.join(horse(n) for n in qualified)+'（組合訊號，非個別練王落飛）'
        else:value+='（其他組合：'+'、'.join(horse(g['horse']) for g in group)+'；沒有個別報價）'
    if missing:value+=f'（部分資料不足：{missing}）'
    age=tip.get('cold_quote_age_seconds',0)
    return value+(f'（報價發布距今：{round(age)}秒）' if age>120 else '')
