"""Frozen research arms. Scores are rankings, not calibrated race probabilities."""
import argparse,gzip,hashlib,itertools,json,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from features import build,BASE,EXTRA
VERSION='meiji-evidence-v2-20261017'
ARMS={'baseline_M1':('X_base','M1'),'evidence_M1':('X_enhanced','M1'),'evidence_place':('X_enhanced','place')}

def train(rows,key,target):
 x=[h[key] for card,hs in rows for h in hs];y=[card['labels'][str(h['no'])][target] for card,hs in rows for h in hs]
 model=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=0));model.fit(x,y);return model

def ordered(model,horses,key):
 scores=model.predict_proba([h[key] for h in horses])[:,1]
 return sorted([{**h,'ranking_score':float(p)} for h,p in zip(horses,scores)],key=lambda h:(-h['ranking_score'],h['no']))

def settle(card,numbers):
 s=card['settlement']
 if s['pool_status'].get('QP')!='settled':return None
 pay={tuple(sorted(map(int,x['combination'].split(',')))):float(x['dividend_hkd']) for x in s['dividends'].get('QP',[])};pairs=list(itertools.combinations(numbers,2));ret=sum(pay.get(tuple(sorted(x)),0) for x in pairs)
 return {'cost':10*len(pairs),'return':ret,'hit':int(ret>0)}

def measure(rows,method=None,key=None):
 out={'races':len(rows),'top1_place':0,'top1_win':0,'cover4_places':0,'cover_all_three_races':0,'qp_cost':0,'qp_return':0,'qp_hit_races':0,'qp_races':0,'per_day':{},'per_race':[]}
 for card,hs in rows:
  ordered_h=ordered(method,hs,key) if method is not None else sorted([h for h in hs if card['labels'][str(h['no'])]['selected']],key=lambda h:card['published'].index(h['no']))
  chosen=ordered_h[:4];labels=[card['labels'][str(h['no'])] for h in chosen];top=labels[0];coverage=sum(x['place'] for x in labels)
  out['top1_place']+=top['place'];out['top1_win']+=top['win'];out['cover4_places']+=coverage;out['cover_all_three_races']+=coverage>=3
  s=settle(card,[h['no'] for h in chosen]);daily=out['per_day'].setdefault(card['date'],{'races':0,'top1_place':0,'cover4_places':0,'qp_profit':0});daily['races']+=1;daily['top1_place']+=top['place'];daily['cover4_places']+=coverage
  if s:
   out['qp_races']+=1;out['qp_cost']+=s['cost'];out['qp_return']+=s['return'];out['qp_hit_races']+=s['hit'];daily['qp_profit']+=s['return']-s['cost']
  out['per_race'].append({'date':card['date'],'venue':card['venue'],'race':card['race'],'numbers':[h['no'] for h in chosen],'top1_place':top['place'],'cover4_places':coverage})
 out['qp_profit']=out['qp_return']-out['qp_cost'];out['qp_roi_pct']=100*out['qp_profit']/out['qp_cost'] if out['qp_cost'] else None
 return out

def export_model(model,key,target):
 return {'feature_order':BASE+(EXTRA if key=='X_enhanced' else []),'target':target,'mean':model[0].mean_.tolist(),'scale':model[0].scale_.tolist(),'coef':model[-1].coef_[0].tolist(),'intercept':model[-1].intercept_.tolist()}

def run(input_path,outdir,evaluate_only=False):
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True);raw=Path(input_path).read_bytes();data=json.loads(gzip.decompress(raw));allrows=[]
 for card in sorted(data['historical_cards'],key=lambda c:(c['date'],c['venue'],c['race'])):
  card['published']=[int(k) for k in card['labels'] if card['labels'][k]['selected']]
  # Stored original published order is authoritative, including a scratched slot.
  card['published']=card['published_order'];hs=build(card,data['facts'],data['trials'],data['reports']);allrows.append((card,hs))
 training=[x for x in allrows if x[0]['date']<'2026-10-01'];testing=[x for x in allrows if x[0]['date']>='2026-10-01']
 if not training or not testing:raise ValueError('Chronological split empty')
 evaluation={'version':VERSION,'train_races':len(training),'test_races':len(testing),'split':'train before 2026-10-01; test 2026-10-01 through 2026-10-14','independent_blind_test':False,'methods':{'meiji':measure(testing)}}
 meeting=data['future_cards'][0]['date']+'-'+data['future_cards'][0]['venue']
 receipt=datetime.now(ZoneInfo('Asia/Hong_Kong')).isoformat();codehash=hashlib.sha256(b''.join((Path(__file__).parent/n).read_bytes() for n in ['sources.py','features.py','model.py'])).hexdigest()
 snapshot={'version':VERSION,'frozen_at':receipt,'input_sha256':hashlib.sha256(raw).hexdigest(),'code_sha256':codehash,'meeting':meeting,'primary_research_arm':'evidence_M1','selection_rule':'top 4 distinct active saddle numbers by ranking_score, tie smaller number','known_limitations':data['limitations'],'models':{},'races':[]}
 frozen={}
 for arm,(key,target) in ARMS.items():
  model=train(training,key,target);evaluation['methods'][arm]=measure(testing,model,key);frozen[arm]=train(allrows,key,target);snapshot['models'][arm]=export_model(frozen[arm],key,target)
 evaluation['evidence_coverage']={'historical_runner_seats':sum(len(hs) for _,hs in allrows),'with_prior_run':sum(h['evidence']['known_prior_runs']>0 for _,hs in allrows for h in hs),'with_report':sum(h['evidence']['report_date'] is not None for _,hs in allrows for h in hs),'with_trial_30d':sum(h['evidence']['trial'] is not None for _,hs in allrows for h in hs)}
 (outdir/'evaluation.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)) if evaluate_only else None
 for card in ([] if evaluate_only else data['future_cards']):
  if card['date']+'-'+card['venue']!=meeting:raise ValueError('Mixed future meetings')
  if datetime.fromisoformat(receipt)>=datetime.fromisoformat(card['off']):raise ValueError('Prediction would be post-off')
  hs=build(card,data['facts'],data['trials'],data['reports']);result={'race':card['race'],'off':card['off'],'distance':card['distance'],'track':card['track'],'rail':card['rail'],'arms':{}}
  for arm,(key,target) in ARMS.items():
   ranked=ordered(frozen[arm],hs,key);chosen=ranked[:4]
   if len(chosen)!=4 or len({h['no'] for h in chosen})!=4:raise ValueError('Need exactly 4 active horses')
   result['arms'][arm]={'numbers':[h['no'] for h in chosen],'horses':[{k:h[k] for k in ['no','name','draw','jockey','ranking_score','evidence']} for h in chosen]}
  snapshot['races'].append(result)
 snapshot['receipt_sha256']=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 (outdir/'evaluation.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2))
 if not evaluate_only:
  target=outdir/(meeting+'-initial.json')
  if target.exists():raise ValueError('Refusing to overwrite a frozen pre-off receipt; choose another output directory')
  target.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in evaluation.items() if k!='methods'},ensure_ascii=False))
 for name,s in evaluation['methods'].items():print(name,{k:v for k,v in s.items() if k not in ['per_day','per_race']})
 print('PREOFF RECEIPT',snapshot['frozen_at'],snapshot['receipt_sha256'])
 return evaluation,snapshot
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--evaluate-only',action='store_true');a=p.parse_args();run(a.input,a.out,a.evaluate_only)
