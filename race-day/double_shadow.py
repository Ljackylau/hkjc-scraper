"""Read-only HKJC Double archive; research only, never changes selections."""
import asyncio
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from runner import HK, atomic, now

DOM = """() => ({text:document.body.innerText,
 source_text:document.querySelector('#refreshTime')?.innerText || '',
 cells:Array.from(document.querySelectorAll('[id^="qb_DBL_"]')).map(e=>({id:e.id,value:e.innerText})),
 win:Array.from(document.querySelectorAll('[id^="odds_WIN_"]')).map(e=>({id:e.id,value:e.innerText}))})"""


def parse(raw, date, venue, number, received):
    text=raw['text']
    label=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
    name={'ST':'沙田','HV':'跑馬地'}[venue]
    times={}
    for n in (number,number+1):
        m=re.search(rf'第\s*{n}\s*場\s*{name},\s*{re.escape(label)}\s+(\d{{1,2}}:\d{{2}})',text)
        if not m:raise ValueError('Double meeting/race identity mismatch')
        times[str(n)]=m[1]
    m=re.search(r'更新時間\s*[:：]?\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)',raw.get('source_text') or text)
    if not m:raise ValueError('Double source timestamp missing')
    stamp=datetime.strptime(m[1]+' '+m[2],'%d/%m/%Y %H:%M:%S' if len(m[2])==8 else '%d/%m/%Y %H:%M').replace(tzinfo=HK)
    age=(received-stamp).total_seconds()
    if not 0<=age<=120:raise ValueError('Double stale source timestamp')
    odds={};excluded=[]
    for cell in raw['cells']:
        key=re.fullmatch(r'qb_DBL_(\d+)_(\d+)',cell['id'])
        if not key:continue
        a,b=map(int,key.groups())
        if not (1<=a<=14 and 1<=b<=14):continue
        pair=f'{a}-{b}'  # Ordered: first leg horse, second leg horse. Never sort.
        try:value=Decimal(cell['value'].strip().replace(',',''))
        except InvalidOperation:excluded.append(pair);continue
        if not value.is_finite() or value<=0:excluded.append(pair);continue
        if pair in odds and odds[pair]!=str(value):raise ValueError('Conflicting Double odds')
        odds[pair]=str(value)
    if len(odds)<10:raise ValueError('Double odds unavailable/insufficient')
    first=sorted({int(k.split('-')[0]) for k in odds})
    second=sorted({int(k.split('-')[1]) for k in odds})
    wins={str(number):{},str(number+1):{}}
    for cell in raw.get('win',[]):
        m=re.fullmatch(r'odds_WIN_(\d+)_(\d+)',cell['id'])
        if not m or m[1] not in wins:continue
        try:v=Decimal(cell['value'].strip().replace(',',''))
        except InvalidOperation:continue
        if v.is_finite() and v>0:wins[m[1]][m[2]]=str(v)
    capped=[k for k,v in odds.items() if Decimal(v)>=999]
    expected={f'{a}-{b}' for a in wins[str(number)] for b in wins[str(number+1)]}
    return {'date':date,'venue':venue,'first_race':number,'second_race':number+1,
            'received_at':received.isoformat(),'source_updated':stamp.isoformat(),
            'source_age_seconds':age,'post_times':times,'odds':{'DBL':odds},
            'first_horses':first,'second_horses':second,'excluded_cells':excluded,
            'win_by_race':wins,'capped_cells':capped,
            'matrix_complete':set(odds)==expected if expected else len(odds)==len(first)*len(second),
            'coverage_verified':bool(expected),'missing_pairs':sorted(expected-set(odds)),
            'research_only':True}


def eligible(sample, cutoff, target):
    return bool(sample and sample['post_times'][str(sample['first_race'])]==target.strftime('%H:%M')
                and 0<=(cutoff-datetime.fromisoformat(sample['source_updated'])).total_seconds()<=120
                and 0<=(cutoff-datetime.fromisoformat(sample['received_at'])).total_seconds()<=120)


async def race_job(context,date,venue,number,off,folder,states):
    target=datetime.strptime(date+' '+off,'%Y-%m-%d %H:%M').replace(tzinfo=HK)
    state={'status':'waiting','first_race':number,'second_race':number+1}
    states[str(number)]=state
    saved=folder/f'double_{number:02d}_{number+1:02d}_t3.json'
    if saved.exists():
        try:
            prior=json.loads(saved.read_text())
            old_target=datetime.strptime(date+' '+prior['post_times'][str(number)],'%Y-%m-%d %H:%M').replace(tzinfo=HK)
            if prior['date']==date and prior['venue']==venue and eligible(prior,old_target-timedelta(minutes=3,seconds=10),old_target):
                state.update(status='saved',restored=True,received_at=prior['received_at'],source_updated=prior['source_updated'])
                return
        except (ValueError,KeyError,TypeError):pass
    while now()<target-timedelta(minutes=32):
        await asyncio.sleep(min(20,(target-timedelta(minutes=32)-now()).total_seconds()))
    page=await context.new_page();last=None;latest=None
    prefix=folder/f'double_{number:02d}_{number+1:02d}'
    url=f'https://bet.hkjc.com/ch/racing/dbl/{date}/{venue}/{number}'
    try:
        while now()<=target-timedelta(minutes=3):
            cycle=now()
            try:
                await page.goto(url,wait_until='domcontentloaded',timeout=15000)
                await page.wait_for_selector('[id^="qb_DBL_"]',timeout=10000)
                raw=await page.evaluate(DOM);received=now()
                sample=parse(raw,date,venue,number,received);sample['url']=url
                revised=datetime.strptime(date+' '+sample['post_times'][str(number)],'%Y-%m-%d %H:%M').replace(tzinfo=HK)
                if abs((revised-target).total_seconds())>1800:raise ValueError('Double schedule shift >30 minutes')
                target=revised;cutoff=target-timedelta(minutes=3,seconds=10)
                sample['cutoff']=cutoff.isoformat()
                signature=(sample['source_updated'],json.dumps(sample['odds'],sort_keys=True))
                if signature!=last:
                    with prefix.with_suffix('.jsonl').open('a',encoding='utf-8') as f:
                        f.write(json.dumps(sample,ensure_ascii=False)+'\n')
                    last=signature
                if received<=cutoff:latest=sample
                state.update(status='collecting',target=cutoff.isoformat(),last_received=sample['received_at'])
                if received>=cutoff:
                    valid=eligible(latest,cutoff,target)
                    if valid:
                        atomic(folder/f'double_{number:02d}_{number+1:02d}_t3.json',latest)
                        state.update(status='saved',received_at=latest['received_at'],source_updated=latest['source_updated'],matrix_complete=latest['matrix_complete'])
                    else:state.update(status='unavailable',error='No fresh Double snapshot received before strict T-3 cutoff')
                    return
            except Exception as e:
                state.update(status='retrying',error=str(e)[:240])
                with (folder/f'double_{number:02d}_{number+1:02d}_errors.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps({'at':now().isoformat(),'error':str(e)[:300]})+'\n')
            interval=10 if now()>=target-timedelta(minutes=7) else 60
            await asyncio.sleep(max(1,interval-(now()-cycle).total_seconds()))
        state.update(status='unavailable',error=state.get('error','Strict cutoff missed'))
    finally:await page.close()


async def collect(context,date,venue,clocks,numbers,folder):
    states={}
    tasks=[asyncio.create_task(race_job(context,date,venue,n,clocks[n-1],folder,states)) for n in numbers if n<len(clocks)]
    try:
        while any(not t.done() for t in tasks):
            atomic(folder/'double_status.json',{'date':date,'updated_at':now().isoformat(),'research_only':True,'pairs':states})
            await asyncio.sleep(5)
        results=await asyncio.gather(*tasks,return_exceptions=True)
        for n,result in zip((n for n in numbers if n<len(clocks)),results):
            if isinstance(result,Exception):states[str(n)]={'status':'unavailable','error':str(result)[:240]}
    finally:
        for t in tasks:
            if not t.done():t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        atomic(folder/'double_status.json',{'date':date,'updated_at':now().isoformat(),'research_only':True,'pairs':states})
