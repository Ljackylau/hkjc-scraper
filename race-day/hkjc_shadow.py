"""Independent, read-only HKJC odds archive. Experimental market movement ranking.

Does not access 103.plus and does not replace Horse103 T−3 selections.
"""
import argparse
import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runner import REPO, HK, atomic, now, publish, setup_data_branch
import runner

DOM = r"""() => ({
  text: document.body.innerText,
  source_text: document.querySelector('#refreshTime')?.innerText || '',
  runner_rows: Array.from(document.querySelectorAll('table tr')).map(r=>Array.from(r.cells).map(c=>c.innerText.trim())).filter(r=>r.length>=9 && /^\d+$/.test(r[0])),
  win: Array.from(document.querySelectorAll('[id^="odds_WIN_"]')).map(e=>({id:e.id,value:e.innerText})),
  pla: Array.from(document.querySelectorAll('[id^="odds_PLA_"]')).map(e=>({id:e.id,value:e.innerText})),
  qin: Array.from(document.querySelectorAll('[id^="qb_QIN_"]')).map(e=>({id:e.id,value:e.innerText})),
  qpl: Array.from(document.querySelectorAll('[id^="qb_QPL_"]')).map(e=>({id:e.id,value:e.innerText}))
})"""
STAMP_READY = r"() => /更新時間\s*[:：]?\s*\d{2}\/\d{2}\/\d{4}\s+\d{2}:\d{2}/.test(document.querySelector('#refreshTime')?.innerText || '')"


def schedule_times(value):
    clocks=[s.strip() for s in value.split(',')]
    if not 1 <= len(clocks) <= 14:
        raise ValueError('Supply 1 to 14 official race times')
    parsed=[datetime.strptime(s,'%H:%M') for s in clocks]
    if any(b<=a for a,b in zip(parsed,parsed[1:])):
        raise ValueError('Race times must be strictly increasing')
    return clocks


def choose_baseline(samples, target):
    # Never relabel a late snapshot as T-30. Require >=10 minutes to off.
    t30=target-timedelta(minutes=30)
    usable=[]
    for sample in samples:
        received=datetime.fromisoformat(sample['received_at'])
        if t30<=received<=target-timedelta(minutes=10):
            stamps=[datetime.fromisoformat(t) for t in sample['source_updated'].values()]
            if len(stamps)==2 and all(0<=(received-t).total_seconds()<=120 for t in stamps):
                usable.append(sample)
    if not usable:return None
    return min(usable,key=lambda s:s['received_at'])


def baseline_info(sample,target):
    received=datetime.fromisoformat(sample['received_at'])
    offset=(received-(target-timedelta(minutes=30))).total_seconds()
    return {'kind':'t30' if offset<=90 else 'late_start',
            'received_at':sample['received_at'],
            'minutes_to_off':round((target-received).total_seconds()/60,2),
            'source_updated':sample['source_updated']}


def clock_from_page(raw, date, number):
    date_label=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m')
    m=re.search(rf'{date_label}\s*\([^)]*\)\s*,\s*(\d{{1,2}}:\d{{2}})',raw['text'])
    if not m or not re.search(rf'第\s*{number}\s*場',raw['text']):
        raise ValueError('HKJC race/date identity mismatch')
    return m[1]


def parse(raw, date, number, route, received):
    reported_off=clock_from_page(raw,date,number)
    match=re.search(r'更新時間\s*[:：]?\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)',raw.get('source_text') or raw['text'])
    if not match:raise ValueError('HKJC source update timestamp missing')
    fmt='%d/%m/%Y %H:%M:%S' if len(match[2])==8 else '%d/%m/%Y %H:%M'
    updated=datetime.strptime(match[1]+' '+match[2],fmt).replace(tzinfo=HK)
    if updated.date().isoformat()>date or (received-updated).total_seconds() < -60:
        raise ValueError('Source timestamp inconsistent with meeting')
    from decimal import Decimal, InvalidOperation
    odds={}
    for pool in (('WIN','PLA') if route=='wp' else ('QIN','QPL')):
        values={}
        for e in raw[pool.lower()]:
            prefix='odds_' if pool in ('WIN','PLA') else 'qb_'
            m=re.fullmatch(prefix+pool+r'_(\d+)_(\d+)',e['id'])
            if not m:continue
            a,b=map(int,m.groups())
            if pool in ('WIN','PLA'):
                if a!=number:continue
                key=str(b)
            else:
                if a==b:continue
                key=f'{min(a,b)}-{max(a,b)}'
            try:v=Decimal(e['value'].strip().replace(',',''))
            except InvalidOperation:continue
            if not v.is_finite() or v<=0:continue
            if key in values and values[key]!=str(v):raise ValueError('Conflicting duplicate odds')
            values[key]=str(v)
        odds[pool]=values
    if route=='wp' and (len(odds['WIN'])<5 or len(odds['PLA'])<5):raise ValueError('Insufficient WP odds')
    if route=='wpq' and (len(odds['QIN'])<10 or len(odds['QPL'])<10):raise ValueError('Insufficient Q/QP odds')
    return {'received_at':received.isoformat(),'source_updated':updated.isoformat(),
            'post_time':reported_off,
            'odds':odds,'fresh':0 <= (received-updated).total_seconds() <= 120}


def movement(start,end):
    from statistics import mean
    pools=('WIN','PLA','QIN','QPL')
    if not all(start['odds'].get(p) and end['odds'].get(p) for p in pools):return []
    horses=set(map(int,end['odds']['WIN'])) & set(map(int,end['odds']['PLA']))
    weights={'WIN':.35,'PLA':.25,'QIN':.20,'QPL':.20}
    ranked=[]
    for h in horses:
        changes={}
        for pool in pools:
            vals=[]
            for key,a in start['odds'][pool].items():
                if key not in end['odds'][pool]:continue
                if pool in ('WIN','PLA'):
                    if key!=str(h):continue
                elif str(h) not in key.split('-'):continue
                before=float(a);after=float(end['odds'][pool][key])
                vals.append(max(0,min(100,100*(before-after)/before)))
            changes[pool]=round((mean(sorted(vals,reverse=True)[:3]) if vals else 0),2)
        score=round(sum(weights[p]*changes[p] for p in pools),3)
        ranked.append({'horse_number':h,'score':score,'drops_pct':changes})
    ranked.sort(key=lambda x:(-x['score'],x['horse_number']))
    return ranked if ranked and ranked[0]['score']>0 else []


async def capture(page, date, venue, number, route):
    url=f'https://bet.hkjc.com/ch/racing/{route}/{date}/{venue}/{number}'
    await page.goto(url,wait_until='domcontentloaded',timeout=25000)
    selector='[id^="odds_WIN_"]' if route=='wp' else '[id^="qb_QPL_"]'
    await page.wait_for_selector(selector,timeout=15000)
    await page.wait_for_function(STAMP_READY,timeout=15000)
    received=now()
    raw=await page.evaluate(DOM)
    result=parse(raw,date,number,route,received)
    result['url']=url
    if route=='wp':result['runner_rows']=raw.get('runner_rows',[])
    # Preserve contemporaneous horse / jockey / trainer mapping for challenge research.
    return result


async def race_job(context,date,venue,number,off,folder,states):
    target=datetime.strptime(date+' '+off,'%Y-%m-%d %H:%M').replace(tzinfo=HK)
    baseline=None;samples=[];dest=folder/f'race_{number:02d}.jsonl'
    states[str(number)]={'status':'waiting','target':(target-timedelta(minutes=3)).isoformat()}
    while now()<target-timedelta(minutes=32):await asyncio.sleep(min(20,(target-timedelta(minutes=32)-now()).total_seconds()))
    wp=await context.new_page();wpq=await context.new_page()
    errors=[];last_source=None
    try:
        while now()<=target-timedelta(minutes=3)+timedelta(seconds=90):
            cycle=now()
            try:
                w,p=await asyncio.gather(capture(wp,date,venue,number,'wp'),capture(wpq,date,venue,number,'wpq'))
                revised=datetime.strptime(date+' '+w['post_time'],'%Y-%m-%d %H:%M').replace(tzinfo=HK)
                if abs((revised-target).total_seconds())>0:
                    if abs((revised-target).total_seconds())>1800:raise ValueError('Schedule changed >30 minutes; review required')
                    target=revised;baseline=None
                    for suffix in ('t30','baseline'):
                        (folder/f'race_{number:02d}_{suffix}.json').unlink(missing_ok=True)
                if w['post_time']!=p['post_time']:raise ValueError('WP/WPQ post times mismatch')
                if not (w['fresh'] and p['fresh']):raise ValueError('Stale source timestamp')
                active=set(w['odds']['WIN']) & set(w['odds']['PLA'])
                if len(active)<5 or any(len(p['odds'][pool]) < len(active)*(len(active)-1)*.4 for pool in ('QIN','QPL')):
                    raise ValueError('Incomplete combination coverage')
                combined={'received_at':max(w['received_at'],p['received_at']),
                          'source_updated':{'wp':w['source_updated'],'wpq':p['source_updated']},
                          'post_time':w['post_time'],'runner_rows':w.get('runner_rows',[]),'odds':{**w['odds'],**p['odds']},'urls':[w['url'],p['url']]}
                stamp=tuple(combined['source_updated'].values())
                if stamp!=last_source:
                    with dest.open('a',encoding='utf-8') as f:f.write(json.dumps(combined,ensure_ascii=False)+'\n')
                    last_source=stamp
                    samples.append(combined)
                received=datetime.fromisoformat(combined['received_at'])
                t30=target-timedelta(minutes=30);t3=target-timedelta(minutes=3)
                if baseline is None:
                    baseline=choose_baseline(samples,target)
                    if baseline:
                        info=baseline_info(baseline,target)
                        atomic(folder/f'race_{number:02d}_baseline.json',{'baseline':info,'snapshot':baseline})
                        if info['kind']=='t30':atomic(folder/f'race_{number:02d}_t30.json',baseline)
                if t3<=received<=t3+timedelta(seconds=90):
                    if any((t3-datetime.fromisoformat(t)).total_seconds()>90 for t in combined['source_updated'].values()):
                        raise ValueError('T−3 odds source older than 90 seconds')
                    atomic(folder/f'race_{number:02d}_t3.json',combined)
                    if baseline:
                        ranked=movement(baseline,combined)
                        states[str(number)]={'status':'shadow' if ranked else 'no_signal','target':t3.isoformat(),
                                            'received_at':combined['received_at'],'source_updated':combined['source_updated'],
                                            'baseline':baseline_info(baseline,target),
                                            'ranking':ranked[:5], 'source':'HKJC odds movement; experimental'}
                    else:states[str(number)]={'status':'missing_baseline','target':t3.isoformat(),'reason':'No fresh baseline between T−30 and T−10; T−3 raw saved'}
                    return
                states[str(number)]={'status':'collecting','target':t3.isoformat(),
                                     'baseline':bool(baseline),'last_received':combined['received_at']}
            except Exception as e:
                errors.append(str(e)[:180]);states[str(number)]={'status':'retrying','target':(target-timedelta(minutes=3)).isoformat(),'errors':errors[-3:]}
                with (folder/f'race_{number:02d}_errors.jsonl').open('a',encoding='utf-8') as f:
                    f.write(json.dumps({'at':now().isoformat(),'error':str(e)[:300]},ensure_ascii=False)+'\n')
            interval=10 if (baseline is None and target-timedelta(minutes=32)<=now()<=target-timedelta(minutes=10)) or now()>=target-timedelta(minutes=4) else 60
            await asyncio.sleep(max(1,interval-(now()-cycle).total_seconds()))
        states[str(number)]={'status':'unavailable','target':(target-timedelta(minutes=3)).isoformat(),'errors':errors[-3:]}
    finally:
        await wp.close();await wpq.close()


async def run(args):
    if now().date().isoformat()!=args.date:raise RuntimeError('Run only on the Hong Kong race date')
    clocks=schedule_times(args.times)
    if args.venue not in ('HV','ST'):raise ValueError('Expected venue HV/ST')
    if args.push:setup_data_branch()
    cut=max(1,len(clocks)//2)
    numbers=list(range(1,cut+1)) if args.phase=='early' else list(range(cut+1,len(clocks)+1))
    folder=REPO/'race-day-data'/args.date/f'hkjc-{args.phase}';folder.mkdir(parents=True,exist_ok=True)
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch();context=await browser.new_context(locale='zh-HK',timezone_id='Asia/Hong_Kong')
        states={};tasks=[asyncio.create_task(race_job(context,args.date,args.venue,n,clocks[n-1],folder,states)) for n in numbers]
        from challenge_shadow import collect as collect_challenges
        if numbers:tasks.append(asyncio.create_task(collect_challenges(context,args.date,args.venue,clocks,numbers,folder,states)))
        last=0
        try:
            while not all(t.done() for t in tasks):
                atomic(folder/'status.json',{'date':args.date,'updated_at':now().isoformat(),'mode':'shadow','races':states,
                                             'errors':[str(t.exception()) for t in tasks if t.done() and t.exception()]})
                if args.push and time.monotonic()-last>=60:
                    try:await asyncio.to_thread(publish,folder)
                    except Exception as e:print('Publish retry:',e,flush=True)
                    last=time.monotonic()
                await asyncio.sleep(5)
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            atomic(folder/'status.json',{'date':args.date,'updated_at':now().isoformat(),'mode':'shadow','races':states})
            if args.push:await asyncio.to_thread(publish,folder)
            await browser.close()


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--date',required=True);a.add_argument('--venue',required=True)
    a.add_argument('--times',required=True);a.add_argument('--phase',choices=('early','late'),required=True);a.add_argument('--push',action='store_true')
    asyncio.run(run(a.parse_args()))
