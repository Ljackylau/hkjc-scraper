"""Cutoff-safe features; no current-race outcome or current horse-profile totals."""
import statistics
from datetime import date
BASE=['last_place','best_last3','mean_last3','placed_last3','wins_last3','form_improvement','starts_shown','missing_form','age','rating','weight','rating_change','weight_change','grade_change','draw_fraction','rating_relative','weight_relative']
EXTRA=['known_runs','history_missing','days_since_known','early_fraction','style_missing','closing_gain','front_pressure','pace_interaction','same_course_rate','same_distance_rate','rider_horse_rate','rating_headroom','headroom_missing','trip_missing','trip_blocked','trip_wide','trip_slow_start','trip_over_racing','trip_health','trial_missing','trial_rank_fraction','trial_days','trial_positive','trial_negative','trial_failed']

def prior(records,before):return [x for x in records if x['date']<before]
def smooth(runs):return (sum(x['finish']<=3 for x in runs)+1)/(len(runs)+4)
def days(a,b):return (date.fromisoformat(a)-date.fromisoformat(b)).days

def build(card,facts,trials,trip_rows):
 before=card['date'];past=prior(facts,before);available_trials=prior(trials,before)
 byhorse={};styles={}
 for h in card['horses']:
  rs=sorted([x for x in past if x['horse_id']==h['horse_id']],key=lambda x:x['date'],reverse=True);byhorse[h['horse_id']]=rs
  recent=[x for x in rs[:3] if x.get('positions')]
  styles[h['horse_id']]=statistics.median(x['positions'][0]/x['field'] for x in recent) if recent else None
 known=[x for x in styles.values() if x is not None];pressure=sum(x<=.3 for x in known)/len(known) if known else .3
 out=[]
 for h in card['horses']:
  ident=h['horse_id'];rs=byhorse[ident];last=rs[0] if rs else None;early=styles[ident];style=early if early is not None else .5
  recent=[x for x in rs[:3] if x.get('positions')]
  gain=statistics.mean((x['positions'][0]-x['finish'])/x['field'] for x in recent) if recent else 0
  course=[x for x in rs if x['venue']==card['venue'] and x['track']==card['track']]
  distance=[x for x in course if x['distance']==card['distance']]
  rider=[x for x in rs if x['jockey_id']==h['jockey_id']]
  rated=[x['rating'] for x in rs if x['finish']<=3]
  # Last available report is a text-mention signal, never a guarantee of an unlucky run.
  reports=sorted([x for x in trip_rows if x['horse_id']==ident and x['date']<before and ('comment' in x or any(v['available_date']<before for v in x.get('versions',[])))],key=lambda x:x['date'],reverse=True)
  report=reports[0] if reports else None
  from sources import event_flags
  flags={x:0 for x in ['blocked','wide','slow_start','over_racing','health']}
  if report:
   if 'comment' in report:flags=event_flags(report['comment'],before)
   else:
    for version in report.get('versions',[]):
     if version['available_date']<before:
      for key,value in version['flags'].items():flags[key]=max(flags[key],value)
  ts=sorted([x for x in available_trials if x['horse_id']==ident and 0<days(before,x['date'])<=30],key=lambda x:(x['date'],x['batch']),reverse=True);trial=ts[0] if ts else None
  extra=[len(rs),int(not rs),min(days(before,last['date']),180) if last else 180,style,int(early is None),gain,pressure,(2*style-1)*(pressure-.3),smooth(course),smooth(distance),smooth(rider),max(rated)-h['rating'] if rated else 0,int(not rated),int(report is None),*flags.values(),int(trial is None),(trial['rank']-1)/max(1,trial['field']-1) if trial else .5,min(days(before,trial['date']),30) if trial else 30,trial['positive'] if trial else 0,trial['negative'] if trial else 0,trial['failed'] if trial else 0]
  evidence={'known_prior_runs':len(rs),'last_known_run':last['date'] if last else None,'running_style':'unknown' if early is None else 'forward' if style<=.3 else 'closer' if style>=.65 else 'midfield','pace_proxy':pressure,'pace_known':len(known),'pace_field':len(card['horses']),'report_date':report['date'] if report else None,'report_source':report.get('source') if report else None,'report_flags':flags if report else None,'trial':trial,'course_starts':len(course),'distance_starts':len(distance)}
  out.append({**h,'X_base':h['X'],'X_enhanced':h['X']+extra,'evidence':evidence})
  assert len(extra)==len(EXTRA)
 return out
