"""Normalize cached public sources; fail closed on identity mismatches."""
import argparse,gzip,json,sys,hashlib,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from bs4 import BeautifulSoup
from sources import parse_reports,parse_trial,parse_results,normalize_report,horse_id,iso,text
from features import BASE
HK=timezone(timedelta(hours=8))

def entry_card(data,canonical):
 d=data['data'];date=datetime.fromisoformat(d['raceDate'].replace('Z','+00:00')).astimezone(HK).date().isoformat()
 if (date,d['raceVenue'],d['raceNo'])!=(canonical['date'],canonical['venue'],canonical['race']):raise ValueError('Star card identity mismatch')
 lookup={h['no']:h for h in canonical['horses']};entries=[h for h in d['raceEntries'] if not h.get('standby') and not h.get('withdrawn') and h['horseNo'] not in canonical.get('withdrawn',canonical.get('scratched',[]))];horses=[]
 import statistics
 ratings=[float(h.get('rating') or 0) for h in entries];weights=[float(h.get('actualWeight') or h.get('handicapWeight') or 126) for h in entries]
 for h in entries:
  no=h['horseNo'];name=h['horse']['name'];draw=int(h['stallNumber'])
  if no not in lookup or name!=lookup[no]['name'] or draw!=lookup[no]['draw']:raise ValueError('Card horse/draw mismatch')
  form=[int(x) if x.isdigit() and int(x)>0 else 15 for x in str(h.get('lastRunPlace','')).split('/') if x];f3=form[:3];rating=float(h.get('rating') or 0);weight=float(h.get('actualWeight') or h.get('handicapWeight') or 126)
  x=[form[0] if form else 15,min(f3) if f3 else 15,statistics.mean(f3) if f3 else 15,sum(x<=3 for x in f3),sum(x==1 for x in f3),form[1]-form[0] if len(form)>1 else 0,len(form),int(not form),float(h.get('age') or 0),rating,weight,float(h.get('ratingChange') or 0),float(h.get('handicapWeightChange') or 0),float(h.get('gradeChange') or 0),draw/max(1,len(entries)),rating-statistics.mean(ratings),weight-statistics.mean(weights)]
  horses.append({'no':no,'name':name,'horse_id':h['jcIdHorse'],'jockey_id':h['jcIdJockey'],'jockey':h['jockey']['name'],'draw':draw,'rating':rating,'weight':weight,'X':x})
 if len(horses)!=len([h for h in canonical['horses'] if h['no'] not in canonical.get('withdrawn',canonical.get('scratched',[]))]):raise ValueError('Incomplete Star field')
 return {k:canonical[k] for k in ['date','venue','race','distance','track','rail']}|{'horses':sorted(horses,key=lambda x:x['no'])}

def parse_summary(body,card):
 soup=BeautifulSoup(body,'html.parser');table=soup.select_one('#PastRacingIncidentExt');out=[]
 if table is None:raise ValueError('Future official trip summary unavailable')
 for tr in table.select('tr'):
  if '後備馬匹' in text(tr):break
  c=tr.find_all('td',recursive=False)
  if len(c)!=6 or not text(c[0]).isdigit() or not text(c[3]):continue
  try:date=iso(text(c[3]))
  except ValueError:continue
  ident=horse_id(c[2]);no=int(text(c[0]));match=next((h for h in card['horses'] if h['no']==no),None)
  if match is None:continue
  if date>=card['date'] or ident!=match['horse_id']:raise ValueError('Future summary identity/cutoff mismatch')
  out.append(normalize_report({'date':date,'horse_id':ident,'comment':text(c[5])})|{'for_race':card['race'],'for_no':no,'source':f"https://racing.hkjc.com/zh-hk/local/information/racereportext?racedate={card['date'].replace('-','/')}&Racecourse={card['venue']}&RaceNo={card['race']}"})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--raw',required=True);ap.add_argument('--records',required=True);ap.add_argument('--output',required=True);ap.add_argument('--future-date',default='2026-10-19');ap.add_argument('--future-venue',default='ST');ap.add_argument('--future-races',type=int,default=11);ap.add_argument('--history-through',default='2026-10-14');a=ap.parse_args();raw=Path(a.raw);rows=[]
 for p in sorted(Path(a.records).glob('2026-??-??.json')):
  meeting=json.loads(p.read_text())
  if not '2026-09-01'<=meeting['date']<=a.history_through:continue
  for race in meeting['races']:
   if race['tips']['meiji']['status']!='ready' or not race.get('result'):continue
   result=race['result'];rows.append({**{k:race[k] for k in ['race','horses','distance','track','rail']},'date':meeting['date'],'venue':meeting['venue'],'tips':[h['no'] for h in race['tips']['meiji']['horses']],'top3':[h['no'] for h in result['horses'] if re.match(r'^\d+',str(h['placing'])) and int(re.match(r'^\d+',str(h['placing']))[0])<=3],'win':[h['no'] for h in result['horses'] if h['placing']=='1'],'withdrawn':sorted(set(result.get('withdrawn',[]))|set(race.get('scratched',[]))),'dividends':result.get('dividends',{}),'pool_status':result.get('pool_status',{})})
 cards=[];facts=[];reports=[];trials=[];receipts=[]
 for r in rows:
  date,venue,n=r['date'],r['venue'],r['race'];d=json.loads(Path(a.raw,f'entry-{date}-{venue}-{n}.txt').read_text());card=entry_card(d,r);card['published_order']=r['tips'];card['settlement']={k:r[k] for k in ['dividends','pool_status','withdrawn']};card['labels']={str(h['no']):{'selected':int(h['no'] in r['tips']),'M1':int(h['no']==r['tips'][0]),'place':int(h['no'] in r['top3']),'win':int(h['no'] in r['win'])} for h in card['horses']};cards.append(card)
  fs=parse_results((raw/f'result-{date}-{venue}-{n}.txt').read_bytes(),date,venue,n);field={h['no']:h for h in card['horses']}
  if set(h['no'] for h in fs)!=set(field):raise ValueError(f'Official starters mismatch {date} R{n}')
  for f in fs:
   h=field[f['no']]
   if f['horse_id']!=h['horse_id'] or f['draw']!=h['draw'] or int(f['finish']<=3)!=card['labels'][str(h['no'])]['place']:raise ValueError(f'Official results mismatch {date} {venue} R{n} no{h["no"]}: official={f} card={h} label={card["labels"][str(h["no"])]}')
   f.update({'distance':card['distance'],'track':card['track'],'rail':card['rail'],'jockey_id':h['jockey_id'],'rating':h['rating']});facts.append(f)
 for date,venue in sorted({(r['date'],r['venue']) for r in rows}):
  url=f'https://racing.hkjc.com/zh-hk/local/information/archive/racereportfull?Date={date.replace("-","/")}'
  for r in parse_reports((raw/f'report-{date}-{venue}.txt').read_bytes(),date,venue):reports.append(normalize_report(r)|{'source':url})
 for p in sorted(raw.glob('trial-*.txt')):
  date=p.stem[6:];url='https://racing.hkjc.com/zh-hk/local/information/archive/btresult?Date='+date.replace('-','/')
  trials.extend([x|{'source':url} for x in parse_trial(p.read_bytes(),date)])
 sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tips-board'));from collector import parse_card
 future=[];ext=[]
 for n in range(1,a.future_races+1):
  canonical=parse_card((raw/f'card-{a.future_date}-{a.future_venue}-{n}.txt').read_text());d=json.loads((raw/f'entry-{a.future_date}-{a.future_venue}-{n}.txt').read_text());
  if (canonical['date'],canonical['venue'],canonical['race'])!=(a.future_date,a.future_venue,n):raise ValueError('Future canonical meeting mismatch')
  card=entry_card(d,canonical);card['off']=canonical['off'];future.append(card)
  ext.extend(parse_summary((raw/f'ext-{a.future_date}-{a.future_venue}-{n}.txt').read_bytes(),card))
 for p in sorted(raw.parent.joinpath('receipts').glob('*.json')):receipts.append(json.loads(p.read_text())|{'cache_key':p.stem})
 payload={'schema':1,'historical_cards':cards,'facts':facts,'reports':reports,'trials':trials,'future_cards':future,'future_extra_reports_not_used_in_model':ext,'receipts':receipts,'limitations':['Historical replay sources collected after race, not independently sealed pre-off data.','Race form/style/trip features cover only the collected September-October 107 races.','Trial comment markers are text evidence; no visual trial or paddock analysis.']}
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 with gzip.GzipFile(filename=str(out),mode='wb',mtime=0) as f:f.write(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())
 print('Normalized:',len(cards),'races,',len(facts),'starts,',len(reports),'reports,',len(trials),'trial starts;',len(future),'future races;',out.stat().st_size,'bytes')
if __name__=='__main__':main()
