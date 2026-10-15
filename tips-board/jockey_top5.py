"""Exact-condition, calendar-2026 jockey place rates, with pre-race cutoffs."""
import concurrent.futures,json,re,urllib.parse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
BASE='https://racing.hkjc.com/zh-hk/local/information/archive/localresults'

def context(text):
    distance=re.search(r'(\d{3,4})\s*米',text)
    awt='全天候' in text
    rail=re.search(r'[「"“]([ABC](?:\s*\+\s*\d+)?)[」"”]',text)
    if not distance or (not awt and not rail):raise ValueError('Official distance/rail missing')
    return {'distance':int(distance[1]),'track':'AWT' if awt else 'TURF','rail':'AWT' if awt else re.sub(r'\s','',rail[1])}

def rider(cell):
    link=cell.select_one('a[href*="jockey"]')
    match=re.search(r'jockeyid=([^&]+)',link.get('href',''),re.I) if link else None
    return {'jockey_id':match[1].upper(),'jockey':re.sub(r'\s*\(-?\d+\)\s*$','',link.get_text(' ',strip=True))} if match else {}

def parse_result(body,date,venue,race):
    soup=BeautifulSoup(body,'html.parser');meta=soup.select_one('.race_tab')
    if not meta:raise ValueError('Official race metadata missing')
    text=meta.get_text(' ',strip=True)
    if not re.search(r'第\s*'+str(race)+r'\s*場',text):raise ValueError('Official race mismatch')
    # The selected result date and local venue must match, never accept a redirected latest card.
    chosen=soup.select_one('option[selected]')
    if chosen:
        selected=json.loads(chosen.get('value','{}')).get('date','')
        if selected and datetime.strptime(selected,'%d/%m/%Y').strftime('%Y-%m-%d')!=date:raise ValueError('Official result date mismatch')
    declared=re.search(r'賽事日期\s*[：:]\s*(\d{1,2})/(\d{1,2})/(\d{4})',soup.get_text(' ',strip=True))
    if declared and f'{int(declared[3]):04}-{int(declared[2]):02}-{int(declared[1]):02}'!=date:raise ValueError('Official result date mismatch')
    heading=meta.parent.get_text(' ',strip=True)
    actual_venue=re.search(r'賽事日期\s*[：:]\s*\d{1,2}/\d{1,2}/\d{4}\s*(沙田|跑馬地)',heading)
    if actual_venue and ('ST' if actual_venue[1]=='沙田' else 'HV')!=venue:raise ValueError('Official result venue mismatch')
    runners=[]
    for row in soup.select('table.draggable tbody tr'):
        c=row.find_all('td',recursive=False)
        if len(c)<4 or not c[1].get_text(strip=True).isdigit():continue
        placing=c[0].get_text(' ',strip=True);who=rider(c[3])
        if not who:continue
        if re.search(r'WV|WX|TNP|退出|未出賽',placing,re.I):continue
        m=re.match(r'(\d+)',placing)
        runners.append({'no':int(c[1].get_text(strip=True)),**who,'top3':bool(m and int(m[1])<=3)})
    if len(runners)<3 or sum(x['top3'] for x in runners)<3:raise ValueError('Official full result incomplete')
    return {'date':date,'venue':venue,'race':race,**context(text),'runners':runners,'source':BASE+'?'+urllib.parse.urlencode({'racedate':date.replace('-','/'),'Racecourse':venue,'RaceNo':race})}

def rank(meeting,race,history):
    ctx={k:race.get(k) for k in ('distance','track','rail')}
    out={'status':'pending','year':2026,**ctx,'riders':[],'cutoff':meeting['date']+f" R{race['race']}", 'method':'top3/starts; exact venue, track, distance, rail; rate desc, starts desc, saddle asc'}
    if not all(ctx.values()) or not all(h.get('jockey_id') for h in race['horses'] if h['no'] not in race.get('scratched',[])):return out
    stats=defaultdict(lambda:[0,0]);seen=set()
    for past in history:
        key=(past['date'],past['venue'],past['race'])
        if key in seen:continue
        seen.add(key)
        if not '2026-01-01'<=past['date']<=min(meeting['date'],'2026-12-31'):continue
        # Same-day results only for earlier races at the same meeting.
        if past['date']==meeting['date'] and (past['venue']!=meeting['venue'] or past['race']>=race['race']):continue
        if past['venue']!=meeting['venue'] or any(past.get(k)!=v for k,v in ctx.items()):continue
        for h in past['runners']:
            s=stats[h['jockey_id']];s[1]+=1;s[0]+=int(h['top3'])
    for h in race['horses']:
        if h['no'] in race.get('scratched',[]):continue
        placed,starts=stats[h['jockey_id']]
        if starts:out['riders'].append({'no':h['no'],'jockey':h['jockey'],'jockey_id':h['jockey_id'],'placed':placed,'starts':starts,'rate':placed/starts})
    out['riders'].sort(key=lambda h:(-h['rate'],-h['starts'],h['no']))
    out['riders']=out['riders'][:5];out['status']='ready';return out

def refresh(meeting,history):
    for race in meeting['races']:race['jockey_top5']=rank(meeting,race,history)

def update_history(store,request,through):
    """Append completed meeting races to the durable cache; retry gaps on later passes."""
    cache=store.read('jockey-2026.json',{'races':[]});lookup={(x['date'],x['venue'],x['race']):x for x in cache['races']}
    jobs=[]
    for path in sorted(store.path.glob('2026-??-??.json')):
        m=store.read(path.name)
        if m['date']>through:continue
        for r in m['races']:
            key=(m['date'],m['venue'],r['race'])
            if r.get('result') and key not in lookup:jobs.append(key)
    def get(key):
        date,venue,n=key
        url=BASE+'?'+urllib.parse.urlencode({'racedate':date.replace('-','/'),'Racecourse':venue,'RaceNo':n})
        try:return key,parse_result(request(url),date,venue,n),None
        except Exception as e:return key,None,str(e)
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for key,item,error in pool.map(get,jobs):
            if item:lookup[key]=item
            else:errors.append({'race':list(key),'error':error})
    cache.update({'year':2026,'source':BASE,'races':sorted(lookup.values(),key=lambda x:(x['date'],x['venue'],x['race'])),'errors':errors})
    store.write('jockey-2026.json',cache)
    return cache['races']


def rebuild(store,request,through,prepare):
    history=update_history(store,request,through)
    lookup={(x['date'],x['venue'],x['race']):x for x in history}
    latest=store.read('latest.json',{}).get('date')
    for path in sorted(store.path.glob('2026-??-??.json')):
        m=store.read(path.name)
        for r in m['races']:
            old=lookup.get((m['date'],m['venue'],r['race']))
            if old:
                for k in ('distance','track','rail'):r[k]=old[k]
                riders={h['no']:h for h in old['runners']}
                for h in r['horses']:
                    if h['no'] in riders:
                        h.update({k:riders[h['no']][k] for k in ('jockey','jockey_id')})
                r['scratched']=sorted(set(r.get('scratched',[]))|{h['no'] for h in r['horses'] if h['no'] not in riders})
                r['jockey_top5']=rank(m,r,history)
                r['jockey_top5']['record_type']='historical_reconstruction'
        if m['date']>=through:prepare(store,m)
        store.write(path.name,m)
        if m['date']==latest:store.write('latest.json',m)
