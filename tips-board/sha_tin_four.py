"""Sha Tin initial-card four, independent of the expert-count score."""
import re
from datetime import datetime
from bs4 import BeautifulSoup
BANKER='https://hkjc-banker-live.l-jackylau1.workers.dev'
PRIORITY=('ball','ma','computer','meiji')
PRO_IDS={'ball':'68b93dfacfe105001db9cd28','ma':'65e9422683c2c7001297e300','computer':'65e9600b960d550012a89716'}

def parse_initial(body,date,race_no):
    soup=BeautifulSoup(body,'html.parser')
    text=soup.get_text(' ',strip=True)
    if not re.search(fr'{int(date[:4])}年{int(date[5:7])}月{int(date[8:])}日\s*·\s*沙田',text):
        raise ValueError('Initial card meeting mismatch')
    heading=soup.find('h1')
    if not heading or not re.search(fr'第\s*{race_no}\s*場',heading.get_text(' ',strip=True)):
        raise ValueError('Initial card race mismatch')
    # v=1 alone is insufficient: the published version must explicitly be pre-off.
    version=soup.find('a',href=f'/race/{date}~ST~{race_no}?v=1')
    if not version or not re.fullmatch(r'v\s*1\s*賽前排位',version.get_text(' ',strip=True)):
        raise ValueError('Published initial version not verified')
    badge=next((x for x in soup.select('.silk-banker') if x.find_parent('table') is None),None)
    if not badge:raise ValueError('Initial banker missing')
    summary=badge.parent
    while summary and len(summary.select('.silk-leg'))<4:summary=summary.parent
    if not summary:raise ValueError('Initial legs missing')
    nums=[int(badge.get_text(strip=True))]+[int(x.get_text(strip=True)) for x in summary.select('.silk-leg')[:4]]
    if len(set(nums))!=5:raise ValueError('Initial card has duplicate picks')
    return {'status':'ready','date':date,'venue':'ST','race':race_no,
            'as_of_race_no':0,'reason':'initial','numbers':nums,
            'verification':'published v1 賽前排位 label','source':f'{BANKER}/race/{date}~ST~{race_no}?v=1'}

def choose_four(race):
    if race.get('venue')!='ST':return None
    initial=race.get('banker_initial',{})
    pending={'status':'pending','numbers':[]}
    if (initial.get('status')!='ready' or initial.get('as_of_race_no')!=0 or initial.get('reason')!='initial'
        or (initial.get('date'),initial.get('venue'),initial.get('race'))!=(race.get('date'),'ST',race.get('race'))):return pending
    field={int(h['no']) for h in race['horses']}
    scratched={int(n) for n in race.get('scratched',[])}
    active=lambda n:n in field and n not in scratched
    bank=list(dict.fromkeys(initial.get('numbers',[])))
    picks=[n for n in bank if active(n)][:3]
    if len(picks)!=3:return pending
    source=None;fourth_source=None
    for key in PRIORITY:
        tip=race['tips'].get(key,{})
        if tip.get('status') not in ('ready','absent'):return pending
        if tip.get('source_date') not in (None,race['date']):return pending
        listed=[int(h['no']) for h in tip.get('horses',[])]
        if not listed:continue
        source=key
        fourth=next((n for n in listed if active(n) and n not in picks),None)
        if fourth is not None:picks.append(fourth);fourth_source=key
        # Once a published tipster is chosen, never switch to the next tipster.
        break
    if len(picks)==3:
        fourth=next((n for n in bank[3:] if active(n) and n not in picks),None)
        if fourth is not None:picks.append(fourth);fourth_source='banker_legs'
    if len(picks)!=4:return pending
    return {'status':'ready','numbers':picks,'fourth_source':fourth_source,
            'initial_source':initial.get('source')}

def capture_four(meeting,request,stamp,now):
    if meeting['venue']!='ST':return
    for r in meeting['races']:
        if r.get('locked') or now()>=datetime.fromisoformat(r['off']):continue
        try:
            if r.get('banker_initial',{}).get('status')!='ready':
                url=f'{BANKER}/race/{meeting["date"]}~ST~{r["race"]}?v=1'
                body=request(url)
                if now()>=datetime.fromisoformat(r['off']):continue
                r['banker_initial']={**parse_initial(body,meeting['date'],r['race']),'captured_at':stamp()}
            r['sha_tin_four']={**choose_four(r),'generated_at':stamp()}
        except Exception as e:
            r['sha_tin_four']={'status':'pending','numbers':[],'error':str(e)}

def backfill_four(meeting,request,stamp):
    """Add a separate historical indicator; never rewrite original bets/results."""
    import concurrent.futures
    if meeting['venue']!='ST':return
    def get(r):
        url=f'{BANKER}/race/{meeting["date"]}~ST~{r["race"]}?v=1'
        try:
            initial={**parse_initial(request(url),meeting['date'],r['race']),
                     'captured_at':stamp(),'record_type':'historical_initial_reconstruction'}
            # Only official withdrawal identity is used, never finishing order/odds.
            context={**r,'banker_initial':initial,
                     'scratched':list(set(r.get('scratched',[]))|set((r.get('result') or {}).get('withdrawn',[])))}
            indicator={**choose_four(context),'generated_at':stamp(),
                       'record_type':'historical_initial_reconstruction',
                       'timing_note':'按來源現存初版重建，非當日獨立封存'}
            return r,initial,indicator
        except Exception as e:return r,None,{'status':'pending','numbers':[],'error':str(e),'record_type':'historical_initial_reconstruction'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for r,initial,indicator in pool.map(get,meeting['races']):
            if initial:r['banker_initial']=initial
            r['sha_tin_four']=indicator
