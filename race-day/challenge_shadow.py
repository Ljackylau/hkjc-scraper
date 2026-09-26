"""Read-only JKC/TNC research archive; never contributes to Horse103 picks.

Source timestamps are last-update times, not proof of a fresh quote. Missing
points/remaining rides stay unknown. No retrospectively manufactured T-3 data.
"""
import asyncio
import json
import math
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from runner import HK, atomic, now

DOM = r"""() => ({
  url: location.href,
  header: document.querySelector('header')?.innerText || '',
  text: document.body.innerText,
  source_text: document.querySelector('#refreshTime')?.innerText || '',
  tables: Array.from(document.querySelectorAll('table')).map(t=>
    Array.from(t.rows).map(r=>Array.from(r.cells).map(c=>c.innerText.trim())))
})"""


def number(value):
    try:
        n=float(str(value).replace(',','').strip())
        return n if math.isfinite(n) and n>=0 else None
    except (ValueError,TypeError):return None


def compact(s):return re.sub(r'\s+','',s)


def parse(raw,date,venue,kind,received):
    title={'jkc':'騎師王','tnc':'練馬師王'}[kind]
    # The odds header contains meeting identity; never match a historic footer date.
    header=raw.get('header','')
    label=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
    place={'ST':'沙田','HV':'跑馬地'}[venue]
    if label not in header or place not in header or title not in header:
        raise ValueError('Challenge meeting/date/venue identity mismatch')
    url=raw.get('url','')
    if f'/racing/{kind}/{date}/{venue}/' not in url:
        raise ValueError('Challenge URL identity mismatch')
    match=re.search(r'更新時間\s*[:：]?\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)',raw.get('source_text','') or header)
    updated=None
    if match:
        fmt='%d/%m/%Y %H:%M:%S' if len(match[2])==8 else '%d/%m/%Y %H:%M'
        updated=datetime.strptime(match[1]+' '+match[2],fmt).replace(tzinfo=HK)
        if updated>received+timedelta(seconds=60):raise ValueError('Future source timestamp')
    found=[]
    for table in raw.get('tables',[]):
        for i,row in enumerate(table):
            cols=[compact(c) for c in row]
            if '現時賠率' not in cols or '選項' not in cols:continue
            name_col='騎師' if kind=='jkc' else '練馬師'
            if name_col not in cols:continue
            for cells in table[i+1:]:
                if len(cells)!=len(cols):continue
                d=dict(zip(cols,cells));sel=d.get('選項','')
                if not sel.isdigit():continue
                odds=number(d['現時賠率']);opening=number(d.get('開售賠率'))
                if odds is not None and odds<=1:odds=None
                if opening is not None and opening<=1:opening=None
                found.append({'selection_id':sel,'name':d[name_col],
                    'is_other':'其他' in d[name_col],
                    'scheduled_rides':number(d.get('指定坐騎',d.get('出賽馬匹'))),
                    'remaining_rides':number(d.get('剩餘坐騎',d.get('剩餘出賽馬匹'))),
                    'points':number(d.get('賽日積分',d.get('積分'))),
                    'opening_odds':opening,'previous_odds':number(d.get('最近賠率')),
                    'current_odds':odds,'quote_text':d['現時賠率'],
                    'opening_drop_pct':round(100*(opening-odds)/opening,2) if opening and odds else None})
            break
    if len(found)<2:raise ValueError('Challenge odds table not ready or schema changed')
    if len({x['selection_id'] for x in found})!=len(found):raise ValueError('Duplicate challenge selections')
    age=round((received-updated).total_seconds(),1) if updated else None
    valid=sum(x['current_odds'] is not None for x in found)
    state='observed' if valid else 'no_numeric_quotes'
    if re.search(r'暫停受注|暫停投注|停止受注|已截止',header):state='suspended_or_closed'
    weights=[1/x['current_odds'] for x in found if x['current_odds']]
    total=sum(weights)
    for x in found:x['normalized_implied_share']=round((1/x['current_odds'])/total,6) if x['current_odds'] and total else None
    return {'schema_version':1,'date':date,'venue':venue,'kind':kind,'received_at':received.isoformat(),
        'url':url,'source_updated_at':updated.isoformat() if updated else None,'source_age_seconds':age,
        'source_recent':age is not None and 0<=age<=120,'state':state,'numeric_quotes':valid,
        'participants':found,'header':header,'research_only':True}


def parse_points(raw,date,kind,received):
    label=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
    if not re.search(r'賽事日期\s*[:：]\s*'+re.escape(label),raw.get('text','')):
        raise ValueError('Points belong to another meeting or not published yet')
    title='騎師王' if kind=='jkc' else '練馬師王'
    if title not in raw['text']:raise ValueError('Points kind mismatch')
    rows=[]
    for table in raw.get('tables',[]):
        for i,row in enumerate(table):
            cols=[compact(c) for c in row]
            if '賽日積分' not in cols or '編號' not in cols:continue
            name_col='騎師' if kind=='jkc' else '練馬師'
            if name_col not in cols:continue
            for cells in table[i+1:]:
                if len(cells)!=len(cols):continue
                d=dict(zip(cols,cells));points=number(d.get('賽日積分'))
                if points is None:continue
                rows.append({'name':d[name_col].lstrip('#').strip(),'selection_id':d['編號'],
                             'points':points,'wins':number(d.get('冠')),'seconds':number(d.get('亞')),'thirds':number(d.get('季'))})
            break
    if not rows:raise ValueError('Points table missing')
    return {'date':date,'kind':kind,'received_at':received.isoformat(),'source_updated_at':None,
            'freshness':'not_verifiable','url':raw['url'],'participants':rows}


def race_context(date,clocks,states,received):
    result=[]
    for i,clock in enumerate(clocks,1):
        manual=datetime.strptime(date+' '+clock,'%Y-%m-%d %H:%M').replace(tzinfo=HK)
        target=states.get(str(i),{}).get('target')
        off=datetime.fromisoformat(target)+timedelta(minutes=3) if target else manual
        result.append({'race_number':i,'post_time':off.isoformat(),
            'schedule_source':'hkjc_shadow' if target else 'workflow_input',
            'seconds_to_off':round((off-received).total_seconds(),1)})
    return result


def t3_candidate(sample,context):
    # Index only genuinely observed fresh pre-off data; timestamp is not relabelled.
    if not sample['source_recent'] or sample['state']!='observed':return []
    return [r for r in context if 90<=r['seconds_to_off']<=180]


def append(path,value):
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')


async def read_odds(page,date,venue,kind):
    url=f'https://bet.hkjc.com/ch/racing/{kind}/{date}/{venue}/1'
    await page.goto(url,wait_until='domcontentloaded',timeout=20000)
    await page.wait_for_selector(f'[id^="odds_{kind.upper()}_"]',timeout=10000)
    raw=await page.evaluate(DOM)
    received=now()
    return parse(raw,date,venue,kind,received),raw


async def read_points(page,date,kind):
    url=f'https://racing.hkjc.com/zh-hk/local/information/{kind}result?racedate={date.replace("-","/")}'
    await page.goto(url,wait_until='domcontentloaded',timeout=15000)
    raw=await page.evaluate(DOM)
    return parse_points(raw,date,kind,now())


async def collect(context,date,venue,clocks,numbers,parent,states,once=False):
    """Runs within existing shadow job. Own files; exceptions cannot stop race capture."""
    folder=Path(parent)/'challenge';folder.mkdir(parents=True,exist_ok=True)
    status={'date':date,'venue':venue,'state':'starting','pools':{},'research_only':True,
            'interval_seconds':60,'phase_races':numbers}
    pages={};point_pages={};started=time.monotonic()
    try:
        for kind in ('jkc','tnc'):
            pages[kind]=await context.new_page();point_pages[kind]=await context.new_page()
        async def cycle(kind):
            old=status['pools'].get(kind,{})
            try:
                sample,raw=await asyncio.wait_for(read_odds(pages[kind],date,venue,kind),timeout=35)
                rc=race_context(date,clocks,states,datetime.fromisoformat(sample['received_at']))
                sample['race_context']=rc
                # Complete visible table evidence retained; no account/credential content.
                sample['raw_tables']=raw['tables']
                sample['points_snapshot']=None
                try:
                    ps=await asyncio.wait_for(read_points(point_pages[kind],date,kind),timeout=18)
                    sample['points_snapshot']=ps
                except Exception as e:sample['points_error']=str(e)[:200]
                append(folder/f'{kind}.jsonl',sample)
                for race in t3_candidate(sample,rc):
                    # Keyed by schedule target. Delays create a new index, not a silent overwrite.
                    key=re.sub(r'[^0-9]','',race['post_time'])
                    dest=folder/f'race_{race["race_number"]:02d}_{kind}_t3_{key}.json'
                    if not dest.exists():atomic(dest,{'timing':'first_observed_T-3_to_T-1.5','race':race,'snapshot':sample})
                atomic(folder/f'{kind}_latest.json',sample)
                status['pools'][kind]={'state':sample['state'],'samples_this_run':old.get('samples_this_run',0)+1,
                    'received_at':sample['received_at'],'source_updated_at':sample['source_updated_at'],
                    'source_recent':sample['source_recent'],'source_age_seconds':sample['source_age_seconds'],
                    'numeric_quotes':sample['numeric_quotes'],'participants':sample['participants'],
                    'points_available':sample['points_snapshot'] is not None,
                    'points_freshness':'not_verifiable','points_error':sample.get('points_error')}
            except Exception as e:
                error={'at':now().isoformat(),'kind':kind,'error':str(e)[:250]}
                append(folder/'errors.jsonl',error)
                status['pools'][kind]={**old,'state':'retrying','error':error['error']}
        while True:
            tick=time.monotonic()
            status['state']='collecting'
            await asyncio.gather(*(cycle(k) for k in pages))
            status['updated_at']=now().isoformat();atomic(folder/'status.json',status)
            if once:break
            rc=race_context(date,clocks,states,now())
            last=max(datetime.fromisoformat(r['post_time']) for r in rc if r['race_number'] in numbers)
            if now()>last+timedelta(minutes=5) or time.monotonic()-started>310*60:break
            await asyncio.sleep(max(1,60-(time.monotonic()-tick)))
        status['state']='finished'
    except asyncio.CancelledError:
        status['state']='cancelled';raise
    except Exception as e:
        status['state']='failed';status['error']=str(e)[:250]
    finally:
        status['updated_at']=now().isoformat();atomic(folder/'status.json',status)
        for page in [*pages.values(),*point_pages.values()]:
            try:await page.close()
            except Exception:pass
