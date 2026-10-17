"""Cache public source pages with receipt hashes and identity checks before reuse."""
import argparse,concurrent.futures,hashlib,json,time,urllib.parse,urllib.request
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from sources import parse_results,parse_reports,parse_trial,iso

def fetch(url):
 for attempt in range(2):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (public racing research)'}),timeout=20) as r:return r.read()
  except (OSError,TimeoutError):
   if attempt:raise
   time.sleep(1)

def collect(records,cache,future_date,venue,races,history_through):
 cache=Path(cache);raw=cache/'raw';receipts=cache/'receipts';raw.mkdir(parents=True,exist_ok=True);receipts.mkdir(exist_ok=True);jobs=[]
 for path in sorted(Path(records).glob('2026-??-??.json')):
  m=json.loads(path.read_text());date=m['date'];v=m['venue']
  if not '2026-09-01'<=date<=history_through:continue
  jobs.append((f'report-{date}-{v}','https://racing.hkjc.com/zh-hk/local/information/archive/racereportfull?Date='+date.replace('-','%2F'),'report',date,v,0))
  for r in m['races']:
   n=r['race'];q=urllib.parse.urlencode({'racedate':date.replace('-','/'),'Racecourse':v,'RaceNo':n})
   jobs.extend([(f'result-{date}-{v}-{n}','https://racing.hkjc.com/zh-hk/local/information/archive/localresults?'+q,'result',date,v,n),(f'entry-{date}-{v}-{n}',f'https://racing.stheadline.com/api/raceEntry?date={date.replace("-","")}&raceNo={n}','entry',date,v,n)])
 landing=fetch('https://racing.hkjc.com/zh-hk/local/information/btresult');soup=BeautifulSoup(landing,'html.parser')
 for o in soup.select('select#selectId option'):
  try:d=iso(o.get('value',''))
  except ValueError:continue
  if '2026-08-01'<=d<future_date:jobs.append(('trial-'+d,'https://racing.hkjc.com/zh-hk/local/information/archive/btresult?Date='+d.replace('-','%2F'),'trial',d,'',0))
 for n in range(1,races+1):
  q=urllib.parse.urlencode({'racedate':future_date.replace('-','/'),'Racecourse':venue,'RaceNo':n})
  jobs.extend([(f'card-{future_date}-{venue}-{n}','https://racing.hkjc.com/zh-hk/local/information/racecard?'+q,'card',future_date,venue,n),(f'ext-{future_date}-{venue}-{n}','https://racing.hkjc.com/zh-hk/local/information/racereportext?'+q,'ext',future_date,venue,n),(f'entry-{future_date}-{venue}-{n}',f'https://racing.stheadline.com/api/raceEntry?date={future_date.replace("-","")}&raceNo={n}','entry',future_date,venue,n)])
 def validate(body,kind,date,v,n):
  if kind=='result':parse_results(body,date,v,n)
  elif kind=='report':parse_reports(body,date,v)
  elif kind=='trial':parse_trial(body,date)
  elif kind=='entry':
   d=json.loads(body)['data'];actual=datetime.fromisoformat(d['raceDate'].replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Hong_Kong')).date().isoformat()
   if (actual,d['raceVenue'],d['raceNo'])!=(date,v,n):raise ValueError('Entry identity mismatch')
  else:
   t=BeautifulSoup(body,'html.parser').get_text(' ',strip=True);day=datetime.fromisoformat(date)
   if f'{day.year}年{day.month}月{day.day}日' not in t or f'第 {n} 場' not in t:raise ValueError('Pre-off page identity mismatch')
 def one(job):
  key,url,kind,date,v,n=job;p=raw/(key+'.txt');rp=receipts/(key+'.json')
  if p.exists() and rp.exists():
   try:validate(p.read_bytes(),kind,date,v,n);return key,'cached'
   except (ValueError,KeyError):pass
  body=fetch(url);validate(body,kind,date,v,n);p.write_bytes(body);rp.write_text(json.dumps({'url':url,'received_at':datetime.now(ZoneInfo('Asia/Hong_Kong')).isoformat(),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}));return key,'fetched'
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for i,item in enumerate(pool.map(one,jobs),1):
   if i%20==0:print(i,'/',len(jobs),item,flush=True)
 return len(jobs)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--cache',required=True);p.add_argument('--future-date',default='2026-10-19');p.add_argument('--future-venue',default='ST');p.add_argument('--future-races',type=int,default=11);p.add_argument('--history-through',default='2026-10-14');a=p.parse_args();print('Complete',collect(a.records,a.cache,a.future_date,a.future_venue,a.future_races,a.history_through))
