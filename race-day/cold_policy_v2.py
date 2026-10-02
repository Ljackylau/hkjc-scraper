"""Frozen exploratory selectors: primary14 and simpler12 on the studied sample.

Inputs contain pre-cutoff markets and genuinely earlier history only. Scores
are uncalibrated ranks, and the explored historical hit rate is not a promised
live probability. There is no outcome, current actual weight, or final odds
argument. Missing metadata cannot qualify for a priority branch.
"""
from datetime import datetime
import math,statistics
from market_math import (market_features,numeric,normalized_inverse,
                         pool_info,mass_bounds)

VERSION='cold_top2_priority_v2_exploratory_2026-10-02'

def ranks(values):
    good=[v for v in values if v is not None and math.isfinite(v)]
    n=len(good);out=[]
    for v in values:
        if v is None or not math.isfinite(v) or n<=1:out.append(.5)
        else:out.append((sum(x<v for x in good)+.5*(sum(x==v for x in good)-1))/(n-1))
    return out

def core_rows(pack):
    """Late-entry evidence recalculated without importing labelled studies."""
    cut=datetime.fromisoformat(pack['cut']);s=pack['start_wp'];e=pack['end_wp'];f=pack['end_fct']
    for name,z,age in [('start',s,180),('end',e,120)]:
        recv=datetime.fromisoformat(z['received_at']);assert recv<=cut
        for pool in ['wp','wpq']:
            src=datetime.fromisoformat(z['source_updated'][pool]);assert src<=recv
            assert 0<=(recv-src if name=='start' else cut-src).total_seconds()<=age
    assert datetime.fromisoformat(f['source_updated'])<=datetime.fromisoformat(f['captured'])<=cut
    assert 0<=(cut-datetime.fromisoformat(f['source_updated'])).total_seconds()<=120
    w=normalized_inverse(e['odds']['WIN']);fo=numeric(f['odds'])
    oe,ee=pool_info(e,'QIN');os,es=pool_info(s,'QIN');out=[]
    for h in sorted(w,key=int):
        if float(e['odds']['WIN'][h])<=10:continue
        ke=[k for k in oe if h in k.split('-')];ks=[k for k in os if h in k.split('-')]
        be=mass_bounds(oe,ke);bs=mass_bounds(os,ks)
        pe=sum(ee[k] for k in ke);ps=sum(es[k] for k in ks)
        lo=(be[0]/pe)/(bs[1]/ps)-1;hi=(be[1]/pe)/(bs[0]/ps)-1
        direction=[]
        for g in w:
            if h==g:continue
            a,b=fo.get(h+'-'+g),fo.get(g+'-'+h)
            if a and b and max(a,b)<999:
                direction.append((b/a)/((1-w[g])/(1-w[h])))
        pairs=0
        for k in e['odds']['QIN']:
            if h not in k.split('-') or not all(k in z['odds'][pool] for z,pool in [(s,'QIN'),(s,'QPL'),(e,'QPL')]):continue
            a,b,c,d=[float(z['odds'][pool][k]) for z,pool in [(s,'QIN'),(e,'QIN'),(s,'QPL'),(e,'QPL')]]
            if max(a,b,c,d)<999 and 1-b/a>=.15 and 1-d/c>=.15:pairs+=1
        out.append({'horse':int(h),'WIN':float(e['odds']['WIN'][h]),'q_lo':lo,'q_hi':hi,'direction':statistics.median(direction) if direction else None,'fct_pairs':len(direction),'joint_pairs':pairs})
    for r in out:
        others=[x for x in out if x['horse']!=r['horse']];den=max(1,len(others))
        r['q_rank_lo']=sum(x['q_hi']<r['q_lo'] for x in others)/den
        r['direction_rank']=sum(x['direction'] is not None and r['direction'] is not None and x['direction']<r['direction'] for x in others)/den
        r['core']=r['q_lo']>.1 and r['q_rank_lo']>=.75 and r['direction_rank']>=.75 and r['joint_pairs']>=2 and r['fct_pairs']>=5
    return out

def select(pack,early_pack,prior_form,metadata,extended=True,parameters=None):
    """Return one cold candidate and its priority branch; no labels accepted.

    metadata is keyed by horse number with declared jockey_strength, last
    30-day trial fields, and declared venue/track matching prior race. The
    caller must prove these were published before cut; validation research
    uses pre-cutoff runner rows plus pre-existing official history.
    """
    params={'jockey_strength':.30,'trial_max':3,'form_threshold':.6 if extended else None,
            'q_growth_min':0,'confirmation':'either','blend_baseline':0}
    if parameters:params.update(parameters)
    rows=market_features(pack);cut=datetime.fromisoformat(pack['cut']);today=cut.date().isoformat()
    if not rows:return {'status':'no_cold_candidates','candidate':None}
    win=numeric(pack['end_wp']['odds']['WIN']);fav=min(win,key=lambda h:(win[h],int(h)))
    oldq=numeric(pack['start_q']['odds']['QIN']);newq=numeric(pack['end_wp']['odds']['QIN'])
    nowcore={r['horse']:r for r in core_rows({'cut':pack['cut'],'start_wp':pack['start_q'],'end_wp':pack['end_wp'],'end_fct':pack['end_fct']})}
    earlycore={r['horse']:r for r in core_rows(early_pack)} if early_pack else {}
    for r in rows:
        h=r['horse'];prior=prior_form.get(h,{})
        r['last_finish_score']=None;r['last_finish']=None
        if prior.get('past_date') and not prior.get('missing_history'):
            assert prior['past_date']<today
            r['last_finish'] = prior['past_finish']
            r['last_finish_score']=(prior['past_field_size']-prior['past_finish'])/(prior['past_field_size']-1)
        key='-'.join(sorted([str(h),fav],key=int));a,b=oldq.get(key),newq.get(key)
        r['favorite_q_drop']=1-b/a if a and b and max(a,b)<999 else None
        m=metadata.get(h,{})
        r['jockey_strength']=m.get('jockey_strength')
        r['trial_score']=m.get('trial_score')
        r['rider_trial_eligible']=False
        if m.get('trial_date'):
            assert m['trial_date']<today
            age=(cut.date()-datetime.fromisoformat(m['trial_date']).date()).days
            r['rider_trial_eligible']=(m.get('jockey_strength') is not None and m['jockey_strength']>=params['jockey_strength'] and m.get('trial_rank') is not None and m['trial_rank']<=params['trial_max'] and 0<age<=30 and m.get('trial_failed')==False and m.get('same_venue_track')==True)
        r['late_entry']=h in earlycore and nowcore[h]['core'] and not earlycore[h]['core']
    columns=['q_both_all_res_growth_lo','fct_first_all_res_growth_lo','last_finish_score','favorite_q_drop','fct_second_all_level_lo','fct_second_top5_res_growth_lo','jockey_strength','trial_score']
    for c in columns:
        v=ranks([r[c] for r in rows])
        for r,z in zip(rows,v):r.setdefault('ranks',{})[c]=z
    for r in rows:
        z=r['ranks'];r['baseline_score']=(z['q_both_all_res_growth_lo']+z['fct_first_all_res_growth_lo']+2*z['last_finish_score'])/4
        raw_market=(z['favorite_q_drop']+z['fct_second_all_level_lo']+z['fct_second_top5_res_growth_lo'])/3
        r['market_score']=params['blend_baseline']*r['baseline_score']+(1-params['blend_baseline'])*raw_market
        r['agreement_score']=sum(sorted(z[c] for c in ['q_both_all_res_growth_lo','last_finish_score','jockey_strength','trial_score'])[1:])/3
    def best(eligible,score):return min(eligible,key=lambda r:(-round(r[score],12),r['horse']))
    ent=[r for r in rows if r['late_entry']];rider=[r for r in rows if r['rider_trial_eligible']]
    baseline=best(rows,'baseline_score')
    f=baseline['last_finish_score'];growth=baseline['q_both_all_res_growth_lo']
    drop=baseline['favorite_q_drop'];finish=baseline['last_finish']
    favorite_confirm=(drop is not None and drop>0);form_confirm=(finish is not None and finish<=2)
    confirm=favorite_confirm if params['confirmation']=='favorite_positive' else form_confirm if params['confirmation']=='previous_top2' else favorite_confirm or form_confirm
    if ent:chosen=best(ent,'baseline_score');branch='late_entry'
    elif rider:chosen=best(rider,'agreement_score');branch='rider_trial_same_context'
    elif params['form_threshold'] is not None and f is not None and f>=params['form_threshold'] and growth is not None and growth>params['q_growth_min'] and confirm:
        chosen=baseline;branch='confirmed_prior_form'
    else:chosen=best(rows,'market_score');branch='market_second'
    return {'status':'ready','candidate':chosen['horse'],'branch':branch,'ranking':rows,'version':VERSION,'extended':extended,'parameters':params,'probability_calibrated':False,'cut':pack['cut']}
