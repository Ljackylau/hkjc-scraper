"""Experimental HKJC-only candidate model. Not deployed, not a probability.
Accept only contemporaneous snapshots already received by T-3 minus 10sec.
CLI: python independent_candidate.py --latest last_pre_t3.json --baseline10 t10.json --baseline-long baseline.json --cutoff 2026-09-27T12:42:00+08:00
The long baseline is optional. No Horse103 valueIndex or money-ticket input.
"""
import argparse,json,math
from datetime import datetime,timedelta,timezone

def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def ranks(values):
    n=len(values)
    return {h:(sum(x<v for x in values.values())+.5*(sum(x==v for x in values.values())-1))/(n-1) if n>1 else .5 for h,v in values.items()}
def support(s):
    odds=s['odds'];w={int(h):1/float(v) for h,v in odds['WIN'].items()};p={int(h):1/float(v) for h,v in odds['PLA'].items()}
    norm=lambda d:{h:v/sum(d.values()) for h,v in d.items()}
    pairs={tuple(sorted(map(int,k.split('-')))):1/float(v) for k,v in odds['QPL'].items()};pairs=norm(pairs);q={h:0. for h in w}
    for pair,value in pairs.items():
        for h in pair:q[h]+=value/2
    return {'W':norm(w),'P':norm(p),'Q':q}
def movement(base,end):
    out={}
    for h in map(int,end['odds']['WIN']):
        score=0.
        for pool,weight in [('WIN',.35),('PLA',.25),('QIN',.20),('QPL',.20)]:
            vals=[]
            for key,a in base['odds'][pool].items():
                b=end['odds'][pool].get(key)
                if b is None:continue
                if pool in ('WIN','PLA') and key!=str(h):continue
                if pool in ('QIN','QPL') and str(h) not in key.split('-'):continue
                vals.append(max(0,min(100,100*(float(a)-float(b))/float(a))))
            if not vals:raise ValueError('Missing pool coverage')
            top=sorted(vals,reverse=True)[:3];score+=weight*round(sum(top)/len(top),2)
        out[h]=round(score,3)
    return out

def validate(s,cutoff,clock,source_age):
    if s.get('post_time')!=clock:raise ValueError('Off-time mismatch')
    if dt(s['received_at'])>cutoff:raise ValueError('Quote received after permitted deadline')
    for k in ('wp','wpq'):
        age=(cutoff-dt(s['source_updated'][k])).total_seconds()
        if not 0<=age<=source_age:raise ValueError('Missing, future or stale source quote')
    hs=set(s['odds']['WIN'])
    if set(s['odds']['PLA'])!=hs:raise ValueError('WIN/PLA field mismatch')
    for pool in ('WIN','PLA','QIN','QPL'):
        if not all(math.isfinite(float(v)) and float(v)>0 for v in s['odds'][pool].values()):raise ValueError('Invalid odds')
    for pool in ('QIN','QPL'):
        if len(s['odds'][pool])!=len(hs)*(len(hs)-1)//2:raise ValueError('Incomplete combination field')
        if any(len(set(k.split('-')))!=2 or not set(k.split('-'))<=hs for k in s['odds'][pool]):raise ValueError('Invalid pair identities')
    return hs

def pick(latest,baseline10,cutoff,baseline_long=None):
    cutoff=dt(cutoff) if isinstance(cutoff,str) else cutoff
    off=cutoff+timedelta(minutes=3);clock=off.astimezone(timezone(timedelta(hours=8))).strftime('%H:%M');freeze=cutoff-timedelta(seconds=10)
    hs=validate(latest,freeze,clock,120);hs10=validate(baseline10,off-timedelta(minutes=10),clock,180)
    if hs!=hs10:raise ValueError('Field changed since T-10; need consistent snapshots')
    a,b=support(latest),support(baseline10);rp,rw,rq=[ranks(a[k]) for k in ('P','W','Q')]
    change={h:((a['P'][h]-b['P'][h])+(a['Q'][h]-b['Q'][h]))/2 for h in a['W']};rd=ranks(change)
    foot={h:.4*rp[h]+.2*rw[h]+.2*rq[h]+.2*rd[h] for h in a['W']}
    valid_long=False
    if baseline_long:
        baseline_long=baseline_long.get('snapshot',baseline_long)
        age=(off-dt(baseline_long['received_at'])).total_seconds()/60
        valid_long=10<=age<=30 and baseline_long.get('post_time')==clock and set(baseline_long['odds']['WIN'])==hs
        if valid_long:
            t=dt(baseline_long['received_at'])
            valid_long=all(0<=(t-dt(baseline_long['source_updated'][k])).total_seconds()<=180 for k in ('wp','wpq'))
    banker_scores=movement(baseline_long,latest) if valid_long else foot
    main=sorted(banker_scores,key=lambda h:(-banker_scores[h],h))[0]
    legs=[h for h in sorted(foot,key=lambda h:(-foot[h],h)) if h!=main][:4]
    return {'banker':main,'legs':legs,'banker_source':'fixed-baseline market movement' if valid_long else 'relative support fallback','banker_scores':banker_scores,'leg_scores':foot,'cutoff':cutoff.isoformat(),'received_at':latest['received_at'],'experimental':True,'not_a_probability':True}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--latest',required=True);p.add_argument('--baseline10',required=True);p.add_argument('--baseline-long');p.add_argument('--cutoff',required=True)
    a=p.parse_args();read=lambda f:json.load(open(f)) if f else None
    print(json.dumps(pick(read(a.latest),read(a.baseline10),a.cutoff,read(a.baseline_long)),ensure_ascii=False,indent=2))
