"""Race-order-only track-bias persistence study; no tip/ROI backtest."""
import csv, json, math, collections, itertools, statistics
from pathlib import Path

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runners', required=True)
parser.add_argument('--output', default='bias_backtest_results.json')
args = parser.parse_args()
PATH = Path(args.runners)
rows = list(csv.DictReader(PATH.open()))
groups = collections.defaultdict(list)
for r in rows:
    if r['track'] != 'TURF': continue
    d = int(r['distance'])
    family = 'straight1000' if r['venue']=='ST' and d==1000 else 'turn1200_1800' if 1200<=d<=1800 else 'other'
    if family == 'other': continue
    groups[(r['date'],r['venue'],r['rail'],family,int(r['race']))].append(r)

def expectation(field):
    weights = {i: 1/float(r['odds']) for i,r in enumerate(field)}
    if any(not math.isfinite(v) or v<=0 for v in weights.values()): raise ValueError('odds')
    w={i:v/sum(weights.values()) for i,v in weights.items()}
    inner={i for i,r in enumerate(field) if r['draw_group']=='inside'}
    return sum(w[i]*w[j]/(1-w[i])*w[k]/(1-w[i]-w[j])*sum(h in inner for h in (i,j,k)) for i,j,k in itertools.permutations(w,3))

races=[]
for key, field in sorted(groups.items()):
    placed=[r for r in field if r['top3']=='1']
    if len(placed)!=3: continue
    try: e=expectation(field)
    except (ValueError,ZeroDivisionError): continue
    obs=sum(r['draw_group']=='inside' for r in placed)
    races.append({'date':key[0], 'venue':key[1], 'rail':key[2], 'family':key[3], 'race':key[4],
                  'observed':obs,'expected':e,'residual':obs-e,'field':len(field)})
meetings=collections.defaultdict(list)
for r in races: meetings[(r['date'],r['venue'],r['rail'],r['family'])].append(r)
maxrace={}
for r in rows: maxrace[(r['date'],r['venue'])]=max(maxrace.get((r['date'],r['venue']),0),int(r['race']))

def run(mode, threshold=.75):
    predictions=[]
    for key,rs in meetings.items():
        rs=sorted(rs,key=lambda r:r['race']);half=math.ceil(maxrace[key[:2]]/2)
        for index,target in enumerate(rs):
            prior=rs[:index]
            if mode=='mid_reset': prior=[r for r in prior if (r['race']>half)==(target['race']>half)]
            if not prior: continue
            if mode=='rolling2' and len(prior)<2: continue
            if mode=='rolling3' and len(prior)<3: continue
            if mode in ('first','mid_reset'): used=prior[:1]
            elif mode=='rolling2': used=prior[-2:]
            elif mode=='rolling3': used=prior[-3:]
            else: used=prior
            signal=statistics.mean(r['residual'] for r in used)
            if abs(signal)<threshold: continue
            direction=1 if signal>0 else -1
            predictions.append({**target,'direction':direction,'signal':signal,
                                'same_sign':direction*target['residual']>0,
                                'signed_residual':direction*target['residual'],
                                'late':target['race']>half,'evidence_n':len(used)})
    return predictions

def summary(p):
    n=len(p)
    return {'n':n,'meetings':len({(r['date'],r['venue']) for r in p}),
            'sign_correct':sum(r['same_sign'] for r in p),
            'sign_rate':sum(r['same_sign'] for r in p)/n if n else None,
            'signed_excess_per_race':statistics.mean(r['signed_residual'] for r in p) if n else None}

output={'scope_races':len(races),'meetings':len(meetings),'split':'2025 development / 2026 validation',
        'notes':['Official final odds are used for a retrospective expectation proxy, not pre-race odds or a calibrated probability.',
                 'Previous results assumed available in race order; no receipt/maintenance timestamps exist in this CSV.',
                 'Midpoint reset is a stress test, not observed watering/rolling.'], 'rules':{}}
for mode in ('first','rolling2','rolling3','cumulative','mid_reset'):
    ps=run(mode)
    output['rules'][mode]={period:{part:summary([r for r in ps if (r['date'].startswith('2025') if period=='2025' else r['date'].startswith('2026')) and (part=='all' or r['late']==(part=='late'))]) for part in ('all','early','late')} for period in ('2025','2026')}
    output['rules'][mode]['by_context_2026']={k:summary([r for r in ps if r['date'].startswith('2026') and r['venue']+'_'+r['family']==k]) for k in sorted({r['venue']+'_'+r['family'] for r in ps})}

# Threshold selected by 2025 signed-excess totals only, then held fixed in 2026.
grid=[]
for mode in ('first','rolling2','rolling3','cumulative','mid_reset'):
    for threshold in (.5,.75,1.0):
        p=run(mode,threshold);dev=[r for r in p if r['date'].startswith('2025')]
        if len(dev)<30 or len({r['date'] for r in dev})<15: continue
        grid.append((sum(r['signed_residual'] for r in dev),mode,threshold,p))
best=max(grid,key=lambda x:x[0]);output['development_selected']={'rule':best[1],'threshold':best[2],'development':summary([r for r in best[3] if r['date'].startswith('2025')]),'validation':summary([r for r in best[3] if r['date'].startswith('2026')])}

# A meeting-level bootstrap respects correlation among races of the same day.
import random
def interval(p):
    by=collections.defaultdict(list)
    for r in p:by[(r['date'],r['venue'])].append(r['signed_residual'])
    vals=list(by.values());random.seed(20261004);means=[]
    if not vals:return None
    for _ in range(2000):
        pick=[x for v in random.choices(vals,k=len(vals)) for x in v];means.append(statistics.mean(pick))
    means.sort();return [means[50],means[1949]]
output['development_selected']['validation_cluster_interval']=interval([r for r in best[3] if r['date'].startswith('2026')])
validation=[r for r in best[3] if r['date'].startswith('2026')]
output['development_selected']['validation_always_inner_sign_rate']=sum(r['residual']>0 for r in validation)/len(validation)
output['development_selected']['validation_always_noninner_sign_rate']=sum(r['residual']<0 for r in validation)/len(validation)
output['unique_meeting_dates']=len({(r['date'],r['venue']) for r in races})
transitions=[]
for key,rs in meetings.items():
    half=math.ceil(maxrace[key[:2]]/2)
    early=[r['residual'] for r in rs if r['race']<=half];late=[r['residual'] for r in rs if r['race']>half]
    if len(early)<2 or len(late)<2:continue
    a,b=statistics.mean(early),statistics.mean(late)
    if abs(a)<.3 or abs(b)<.3:continue
    transitions.append({'date':key[0], 'reversal':a*b<0})
output['strong_half_transition']={year:{'n':len([r for r in transitions if r['date'].startswith(year)]),'reversed':sum(r['reversal'] for r in transitions if r['date'].startswith(year))} for year in ('2025','2026')}
Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(json.dumps(output,ensure_ascii=False,indent=2))
