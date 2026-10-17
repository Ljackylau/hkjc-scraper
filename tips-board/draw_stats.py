"""Jockey place rates at the current draw since September 2026; prior days only."""
import concurrent.futures,re,urllib.parse
from collections import defaultdict
from bs4 import BeautifulSoup
import jockey_top5
START='2026-09-01'

def parse_result(body,date,venue,race):
    item=jockey_top5.parse_result(body,date,venue,race)
    soup=BeautifulSoup(body,'html.parser');table=soup.select_one('table.draggable')
    headers=[re.sub(r'\s','',c.get_text()) for c in table.select('thead tr')[-1].find_all(['th','td'])]
    if '檔位' not in headers:raise ValueError('Official draw column missing')
    ix=headers.index('檔位');draws={}
    for tr in table.select('tbody tr'):
        c=tr.find_all('td',recursive=False)
        if len(c)>ix and c[1].get_text(strip=True).isdigit() and c[ix].get_text(strip=True).isdigit():draws[int(c[1].get_text(strip=True))]=int(c[ix].get_text(strip=True))
    for h in item['runners']:
        h['draw']=draws.get(h['no'])
        if not h['draw']:raise ValueError('Official runner draw missing')
    return item

def card_draw(row):
    table=row.find_parent('table')
    if not table:return {}
    headers=[re.sub(r'\s','',c.get_text()) for c in table.select('tr')[0].find_all(['td','th'],recursive=False)]
    c=row.find_all('td',recursive=False)
    for i,title in enumerate(headers):
        if title in ('檔位','Draw') and len(c)>i and c[i].get_text(strip=True).isdigit():return {'draw':int(c[i].get_text(strip=True))}
    return {}

def rank(meeting,race,history,errors=None):
    ctx={'rail':race.get('rail')}
    out={'status':'pending','start_date':START,'before_date':meeting['date'],**ctx,'riders':[],'method_version':'jockey_rail_draw_v2',
         'method':'top3/starts; exact jockey, rail, draw; all venues, tracks and distances; prior days only; rate desc, starts desc, saddle asc'}
    active=[h for h in race['horses'] if h['no'] not in race.get('scratched',[])]
    if not all(ctx.values()) or any(not h.get('draw') or not h.get('jockey_id') for h in active):return out
    stats=defaultdict(lambda:[0,0]);seen=set()
    for past in history:
        key=(past['date'],past['venue'],past['race'])
        if key in seen:continue
        seen.add(key)
        if not START<=past['date']<meeting['date']:continue
        if past.get('rail')!=ctx['rail']:continue
        for h in past['runners']:
            if not h.get('draw') or not h.get('jockey_id'):continue
            s=stats[(h['jockey_id'],int(h['draw']))];s[1]+=1;s[0]+=int(h['top3'])
    for h in active:
        placed,starts=stats[(h['jockey_id'],int(h['draw']))]
        if starts:out['riders'].append({'no':h['no'],'jockey':h['jockey'],'jockey_id':h['jockey_id'],'draw':h['draw'],'placed':placed,'starts':starts,'rate':placed/starts})
    out['riders'].sort(key=lambda h:(-h['rate'],-h['starts'],h['no']));out['riders']=out['riders'][:5]
    out['status']='ready'
    if errors:out['coverage_note']='部分歷史場次待補'
    return out

def update_history(store,request,before):
    cache=store.read('draw-history.json',{'races':[]});lookup={(x['date'],x['venue'],x['race']):x for x in cache['races']};jobs=[]
    for path in sorted(store.path.glob('2026-??-??.json')):
        m=store.read(path.name)
        if not START<=m['date']<before:continue
        for r in m['races']:
            key=(m['date'],m['venue'],r['race'])
            if key not in lookup:jobs.append(key)
    def get(key):
        date,venue,n=key;url=jockey_top5.BASE+'?'+urllib.parse.urlencode({'racedate':date.replace('-','/'),'Racecourse':venue,'RaceNo':n})
        try:return key,parse_result(request(url),date,venue,n),None
        except Exception as e:return key,None,str(e)
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for key,item,error in pool.map(get,jobs):
            if item:lookup[key]=item
            else:errors.append({'race':list(key),'error':error})
    cache.update({'start_date':START,'races':sorted(lookup.values(),key=lambda x:(x['date'],x['venue'],x['race'])),'errors':errors})
    store.write('draw-history.json',cache);return cache

def rebuild(store,request,parse_card,before):
    cache=update_history(store,request,before);lookup={(r['date'],r['venue'],r['race']):r for r in cache['races']};latest=store.read('latest.json',{}).get('date')
    errors=[]
    for path in sorted(store.path.glob('2026-??-??.json')):
        m=store.read(path.name)
        if m['date']>=before:
            m['collection_policy']={'index':False,'results':False,'draw_start_date':START}
            for r in m['races']:
                if r['index']['status']!='ready':r['index']['status']='disabled'
        for r in m['races']:
            old=lookup.get((m['date'],m['venue'],r['race']))
            if old:
                for k in ('distance','track','rail'):r[k]=old[k]
                field={h['no']:h for h in old['runners']}
                for h in r['horses']:
                    if h['no'] in field:h['draw']=field[h['no']]['draw']
                # Withdrawals are excluded from draw statistics; keep original selections intact.
                r['draw_stats_scratched']=sorted(set(r.get('scratched',[]))|{h['no'] for h in r['horses'] if h['no'] not in field})
            elif m['date']>=before and any(not h.get('draw') for h in r['horses'] if h['no'] not in r.get('scratched',[])):
                try:
                    q=urllib.parse.urlencode({'racedate':m['date'].replace('-','/'),'Racecourse':m['venue'],'RaceNo':r['race']})
                    fresh=parse_card(request('https://racing.hkjc.com/zh-hk/local/information/racecard?'+q))
                    if (fresh['date'],fresh['venue'],fresh['race'])!=(m['date'],m['venue'],r['race']):raise ValueError('Official card mismatch')
                    for k in ('horses','distance','track','rail','scratched'):
                        if k in fresh:r[k]=fresh[k]
                except Exception as e:errors.append({'date':m['date'],'race':r['race'],'error':str(e)})
            context={**r,'scratched':r.get('draw_stats_scratched',r.get('scratched',[]))}
            r['draw_top5']=rank(m,context,cache['races'],cache['errors'])
            if old:r['draw_top5']['record_type']='historical_reconstruction'
        store.write(path.name,m)
        if m['date']==latest:store.write('latest.json',m)
    return {'history':len(cache['races']),'history_errors':cache['errors'],'card_errors':errors}
