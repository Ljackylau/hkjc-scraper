"""Read-only HKJC pair collector. No betting, credentials or race results."""
import argparse, asyncio, json, os, re, subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo
HK = ZoneInfo('Asia/Hong_Kong')
ROOT = Path(__file__).resolve().parent
DOM = """() => ({text:document.body.innerText, cells:Array.from(document.querySelectorAll('[id^="qb_QIN_"], [id^="qb_FCT_"]')).map(e=>({id:e.id,value:e.innerText}))})"""
HKJC_ENTRIES = 'https://racing.hkjc.com/en-us/local/information/entries'
HKJC_RACECARD = 'https://racing.hkjc.com/en-us/local/information/racecard'
def now(): return datetime.now(HK)

def meeting_candidates(hrefs, today):
    """Return official HKJC meetings from today onward, nearest first."""
    found=set()
    for href in hrefs:
        date_match=re.search(r'racedate=(\d{4})(?:%2F|/)(\d{2})(?:%2F|/)(\d{2})',href,re.I)
        venue_match=re.search(r'Racecourse=(ST|HV)',href,re.I)
        if not date_match or not venue_match: continue
        date='-'.join(date_match.groups())
        if date >= today.isoformat(): found.add((date,venue_match[1].upper()))
    return sorted(found)

def race_time_from_text(text, race_no):
    """Read the advertised post time from an official HKJC race-card heading."""
    match=re.search(rf'Race\s+{race_no}\s+-[\s\S]*?(\d{{1,2}}:\d{{2}})',text,re.I)
    if not match: return None
    datetime.strptime(match[1],'%H:%M')
    return match[1]

async def discover_meeting(context, today=None):
    """Discover the current/next HK meeting and every official race time."""
    today=today or now().date()
    page=await context.new_page()
    try:
        candidates=[]
        # Race-card links carry the declared post times and are the authoritative
        # source. Entries is a fallback for days when navigation is reorganised.
        for landing in (HKJC_RACECARD,HKJC_ENTRIES):
            await page.goto(landing,wait_until='domcontentloaded',timeout=30000)
            hrefs=await page.locator('a').evaluate_all("els => els.map(e => e.href)")
            candidates=meeting_candidates(hrefs,today)
            if candidates: break
        if not candidates:
            raise RuntimeError('HKJC entries page did not expose a current or future meeting')
        date,venue=candidates[0]
        times=[]
        for race_no in range(1,13):
            url=f'{HKJC_RACECARD}?RaceNo={race_no}&Racecourse={venue}&racedate={date.replace("-","%2F")}'
            await page.goto(url,wait_until='domcontentloaded',timeout=30000)
            clock=race_time_from_text(await page.locator('body').inner_text(),race_no)
            if not clock:
                if race_no==1: raise RuntimeError('HKJC race card has no readable first-race time')
                break
            times.append(clock)
        if not times: raise RuntimeError('HKJC race card returned no race times')
        return {'date':date,'venue':venue,'times':times,'source':'HKJC automatic discovery'}
    finally:
        await page.close()

def validate_config(config):
    datetime.strptime(config['date'],'%Y-%m-%d')
    if config['venue'] not in ('HV','ST'): raise ValueError('Invalid venue')
    if not config.get('times'): raise ValueError('No race times')
    for clock in config['times']: datetime.strptime(clock,'%H:%M')
    return config
def pairs(cells, pool):
    out = {}
    for c in cells:
        m = re.fullmatch(r'qb_'+pool+r'_(\d+)_(\d+)', c['id'])
        if not m: continue
        a,b = map(int,m.groups())
        if a == b: continue
        try: value = Decimal(c['value'].strip().replace(',',''))
        except InvalidOperation: continue
        if not value.is_finite() or value <= 0: continue
        if pool == 'QIN': a,b = sorted((a,b))
        key = f'{a}-{b}'
        if key in out and out[key] != str(value): raise ValueError('Conflicting duplicate odds')
        out[key] = str(value)
    return out

def compare(start, end, pool):
    found=[]; counts=Counter(); partners=defaultdict(set); drops=defaultdict(list)
    for key, val in start.items():
        if key not in end: continue
        a,b = Decimal(val),Decimal(end[key])
        if a <= 0 or b <= 0: continue
        if (a-b)*100 > a*30:
            x,y = map(int,key.split('-'))
            found.append({'pair':key,'start':str(a),'end':str(b),'drop_pct':float((a-b)*100/a)})
            counts.update((x,y)); partners[x].add(y); partners[y].add(x)
            drops[x].append(float((a-b)*100/a)); drops[y].append(float((a-b)*100/a))
    return {'pool':pool,'pairs':sorted(found,key=lambda x:(-x['drop_pct'],x['pair'])),
            'horses':[{'horse':h,'count':c,'partners':len(partners[h]),
                      'avg_drop_pct':round(sum(drops[h])/len(drops[h]),2),
                      'max_drop_pct':round(max(drops[h]),2)}
                      for h,c in sorted(counts.items(),key=lambda x:(-x[1],x[0]))],
            'compared_pairs':len(start.keys() & end.keys()),'missing_at_end':sorted(start.keys()-end.keys())}

def endpoint_ok(baseline, final, start, stop):
    if baseline is None or final is None: return False
    b=datetime.fromisoformat(baseline['captured']); f=datetime.fromisoformat(final['captured'])
    return 0 <= (b-start).total_seconds() <= 30 and 0 <= (stop-f).total_seconds() <= 30 and baseline['fresh'] and final['fresh']

def snapshot(raw, pool, captured):
    match=re.search(r'更新時間\s*[:：]?\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)',raw['text'])
    source=None
    if match:
        fmt='%d/%m/%Y %H:%M:%S' if len(match[2])==8 else '%d/%m/%Y %H:%M'
        source=datetime.strptime(match[1]+' '+match[2],fmt).replace(tzinfo=HK)
    return {'captured':captured.isoformat(),'source_updated':source.isoformat() if source else None,
            'fresh':source is not None and 0 <= (captured-source).total_seconds() <= 120,
            'odds':pairs(raw['cells'],pool)}

def top_three(result):
    return [{'horse':h['horse'],'score':h['avg_drop_pct'],'count':h['count']}
            for h in sorted(result['horses'],key=lambda h:(-h['avg_drop_pct'],-h['count'],h['horse']))[:3]]

def render(state):
    lines=['# Dragon FCT 即時跌幅結果','',f"賽日：{state['date']}　場地：{state['venue']}",'',
    '首次可用取樣至最新資料；只顯示 FCT。分數係跌幅大過 30% 組合嘅平均跌幅，唔係入位機率。','']
    for race in state['races']:
        lines += [f"## R{race['race']} — {race['status']}",'']
        for p in race.get('pools',[]):
            if p['pool']!='FCT': continue
            lines += ['### FCT','',f"實際快照：{p['baseline_time']} → {p['final_time']}",'',
            f"可比較 {p['compared_pairs']} 組；終點缺少 {len(p['missing_at_end'])} 組。",'',
            '| 馬號 | FCT 分數 | 出現次數 |','|---|---:|---:|']
            for h in p['horses']:
                lines.append(f"| {h['horse']} | {h['avg_drop_pct']:.2f}% | {h['count']} |")
            if not p['horses']: lines += ['','暫時冇跌幅大過 30% 嘅 FCT 組合。']
            lines += ['']
    return '\n'.join(lines)+'\n'

def publish(state, push):
    state['published_at']=now().isoformat()
    payload=json.dumps(state,ensure_ascii=False,indent=2)
    ROOT.joinpath('results.json').write_text(payload)
    archive=ROOT.joinpath('archive',state['date']+'.json')
    archive.parent.mkdir(exist_ok=True)
    archive.write_text(payload)
    ROOT.joinpath('RESULTS.md').write_text(render(state))
    if push:
        def git(*args): return subprocess.run(['git',*args],cwd=ROOT.parent,check=True,capture_output=True)
        git('add','dragon/results.json','dragon/RESULTS.md','dragon/archive/'+state['date']+'.json')
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT.parent).returncode:
            git('commit','-m','Update Dragon pair-drop results')
            for attempt in range(3):
                try: git('push'); break
                except subprocess.CalledProcessError:
                    if attempt==2: raise
                    git('pull','--rebase')

def live_pool(pool, baseline, current):
    valid=bool(baseline and current.get('source_updated') and
               baseline.get('source_updated') != current.get('source_updated'))
    result=compare(baseline['odds'],current['odds'],pool) if valid else compare({}, {}, pool)
    result.update(baseline_time=baseline['captured'] if baseline else None,
                  final_time=current['captured'],source_updated=current['source_updated'],
                  fresh=current['fresh'],comparison_ready=valid,
                  baseline_label='首次可用取樣；非 T−60 比較',
                  current_odds=current['odds'])
    result['top3']=top_three(result)
    return result

def record_due_snapshots(race, result, off, captured):
    """Persist the first sample within 90 seconds after each target time."""
    saved=race.setdefault('snapshots',{})
    for label,minutes in [('T−10',10),('T−3',3)]:
        target=off-timedelta(minutes=minutes)
        if label not in saved and target <= captured <= target+timedelta(seconds=90):
            saved[label]={'label':label,'target_time':target.isoformat(),
                          'captured':result['final_time'],
                          'source_updated':result['source_updated'],
                          'top3':result['top3']}

async def collect(config, push, auto_meeting=True):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(timezone_id='Asia/Hong_Kong',locale='zh-HK')
        if auto_meeting:
            try:
                config=validate_config(await discover_meeting(context))
            except Exception as e:
                print(f'Automatic meeting discovery failed; using meeting.json: {type(e).__name__}: {e}')
        state={'date':config['date'],'venue':config['venue'],'meeting_source':config.get('source','meeting.json fallback'),
               'races':[{'race':config.get('race_numbers',list(range(1,len(config['times'])+1)))[i],'off_time':t,'status':'正在開啟'} for i,t in enumerate(config['times'])]}
        saved=ROOT.joinpath('results.json')
        if saved.exists():
            previous=json.loads(saved.read_text())
            if previous.get('date')==config['date'] and previous.get('venue')==config['venue']:
                for race in state['races']:
                    prior=next((r for r in previous.get('races',[]) if r['race']==race['race']),{})
                    race.update(prior)
                    race['off_time']=config['times'][config.get('race_numbers',list(range(1,len(config['times'])+1))).index(race['race'])]
                    race['status']='正在重新連接'
        dirty=asyncio.Event()
        async def race_job(race, clock):
            off=datetime.fromisoformat(config['date']+'T'+clock).replace(tzinfo=HK)
            stop=off+timedelta(minutes=15)
            start=off-timedelta(minutes=60)
            while now()<start:
                await asyncio.sleep(min(30,(start-now()).total_seconds()))
            pages={}; bases=race.setdefault('baselines',{}); errors=[]
            race.setdefault('history',[])
            try:
                while now()<stop:
                    cycle_start=now()
                    for pool,route in [('FCT','fct')]:
                        try:
                            page=pages.get(pool)
                            if page is None:
                                page=await context.new_page()
                                pages[pool]=page
                                await page.goto(f"https://bet.hkjc.com/ch/racing/{route}/{config['date']}/{config['venue']}/{race['race']}",wait_until='domcontentloaded',timeout=25000)
                            raw=await page.evaluate(DOM)
                            s=snapshot(raw,pool,now())
                            with ROOT.joinpath(f"raw-R{race['race']}.jsonl").open('a') as f:
                                f.write(json.dumps({'pool':pool,**s},ensure_ascii=False)+'\n')
                            if s['odds']:
                                if pool not in bases: bases[pool]=s
                                result=live_pool(pool,bases.get(pool),s)
                                race['pools']=[result]
                                record_due_snapshots(race,result,off,datetime.fromisoformat(s['captured']))
                                if result['comparison_ready']:
                                    point={'captured':s['captured'],'source_updated':s['source_updated'],
                                           'top3':result['top3']}
                                    if not race['history'] or race['history'][-1].get('source_updated')!=point['source_updated']:
                                        race['history'].append(point)
                        except Exception as e:
                            errors.append(type(e).__name__+': '+str(e)[:200])
                            page=pages.pop(pool,None)
                            if page: await page.close()
                    race['horse_numbers']=sorted({int(h) for s in race.get('pools',[]) for k in s.get('current_odds',{}) for h in k.split('-')})
                    race['last_attempt']=now().isoformat()
                    race['errors']=errors[-5:]
                    race['status']='收集中' if race.get('pools') else '暫無數據；每分鐘重試'
                    dirty.set()
                    await asyncio.sleep(max(0,min(60-(now()-cycle_start).total_seconds(),(stop-now()).total_seconds())))
                race['status']='已停止取樣；保留最後資料' if race.get('pools') else '暫無數據；本次取樣已結束'
            finally:
                for page in pages.values(): await page.close()
                dirty.set()
        tasks=[asyncio.create_task(race_job(r,t)) for r,t in zip(state['races'],config['times'])]
        try:
            while any(not t.done() for t in tasks):
                try: await asyncio.wait_for(dirty.wait(),timeout=30)
                except asyncio.TimeoutError: continue
                dirty.clear()
                await asyncio.sleep(3)
                await asyncio.to_thread(publish,json.loads(json.dumps(state)),push)
            await asyncio.gather(*tasks)
            await asyncio.to_thread(publish,json.loads(json.dumps(state)),push)
        finally:
            for t in tasks:
                if not t.done(): t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            await browser.close()
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary: Path(summary).write_text(render(state))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--push',action='store_true')
    ap.add_argument('--no-auto-meeting',action='store_true',help='Use meeting.json without HKJC discovery')
    args=ap.parse_args()
    config=validate_config(json.loads(ROOT.joinpath('meeting.json').read_text()))
    asyncio.run(collect(config,args.push,not args.no_auto_meeting))

