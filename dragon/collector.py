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
def now(): return datetime.now(HK)
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

def render(state):
    lines=['# Dragon 組合跌幅結果','',f"賽日：{state['date']}　場地：{state['venue']}",'',
    'T−60 至 T−10；跌幅嚴格大過 30%。馬號次數係組合出現次數，唔係入位機率。',
    '時間容差：起點後最多 30 秒；終點前最多 30 秒。用原定開跑時間，延遲開跑唔會自動改時間。','']
    for race in state['races']:
        lines += [f"## R{race['race']} — {race['status']}",'']
        total=Counter()
        for p in race.get('pools',[]):
            lines += [f"### {p['pool']}",'',f"實際快照：{p['baseline_time']} → {p['final_time']}",'',
            f"可比較 {p['compared_pairs']} 組；終點缺少 {len(p['missing_at_end'])} 組。",'',
            '| 馬號 | 出現次數 | 不同拍檔 |','|---|---:|---:|']
            for h in p['horses']:
                lines.append(f"| {h['horse']} | {h['count']} | {h['partners']} |")
                total[h['horse']]+=h['count']
            lines += ['', '| 組合 | 起點賠率 | 終點賠率 | 跌幅 |','|---|---:|---:|---:|']
            for x in p['pairs']: lines.append(f"| {x['pair']} | {x['start']} | {x['end']} | {x['drop_pct']:.2f}% |")
            if not p['pairs']: lines += ['','冇符合條件嘅組合。']
            lines += ['']
        if total: lines += ['兩池合計（FCT 正反方向分開計）：'+ '、'.join(f'{h}號 {n}次' for h,n in sorted(total.items(),key=lambda x:(-x[1],x[0]))),'']
    return '\n'.join(lines)+'\n'

def render_chart(state):
    data=json.dumps(state,ensure_ascii=False)
    return '''<!doctype html><meta charset="utf-8"><title>Dragon live pair signals</title>
<style>body{font:14px system-ui;margin:24px;color:#17202a}h1{font-size:20px}section{margin:24px 0}svg{width:100%;max-width:1100px;height:360px;border-bottom:1px solid #ccd}.q{fill:#2878d0}.f{fill:#e58b2a}.both{stroke:#b48b00;stroke-width:4}.muted{fill:#68737d;font-size:12px}.lineq{stroke:#2878d0}.linef{stroke:#e58b2a}line{stroke:#d9dee3}.legend{margin:6px 0}.legend span{margin-right:16px}</style>
<h1>Dragon T−60 → T−10 市場跌幅訊號</h1><p>柱＝合資格組合出現次數；線＝平均跌幅；金色粗框＝QIN／FCT 同時支持。唔代表實際入位機率。</p><div id="app"></div>
<script>const state='''+data+''';const app=document.querySelector('#app');
function chart(r){let q=(r.pools||[]).find(x=>x.pool==='QIN')||{horses:[]},f=(r.pools||[]).find(x=>x.pool==='FCT')||{horses:[]};let all=[...new Set([...q.horses,...f.horses].map(x=>x.horse))].sort((a,b)=>a-b),qm=Object.fromEntries(q.horses.map(x=>[x.horse,x])),fm=Object.fromEntries(f.horses.map(x=>[x.horse,x])),mx=Math.max(1,...all.map(h=>Math.max(qm[h]?.count||0,fm[h]?.count||0))),svg=`<svg viewBox="0 0 1000 360" role="img" aria-label="R${r.race} 馬號訊號圖"><line x1="55" y1="300" x2="970" y2="300"/>`;all.forEach((h,i)=>{let x=75+i* (890/Math.max(1,all.length-1)),a=qm[h],b=fm[h],both=a&&b,scale=220/mx;svg+=`<text x="${x}" y="325" text-anchor="middle">${h}</text>`;if(a)svg+=`<rect class="q ${both?'both':''}" x="${x-12}" y="${300-a.count*scale}" width="10" height="${a.count*scale}" data-tooltip="${h}號 QIN ${a.count}次；平均跌幅 ${a.avg_drop_pct}%"/>`;if(b)svg+=`<rect class="f ${both?'both':''}" x="${x+2}" y="${300-b.count*scale}" width="10" height="${b.count*scale}" data-tooltip="${h}號 FCT ${b.count}次；平均跌幅 ${b.avg_drop_pct}%"/>`;if(a)svg+=`<circle class="lineq" cx="${x-7}" cy="${300-Math.min(100,a.avg_drop_pct)*2}" r="3"/>`;if(b)svg+=`<circle class="linef" cx="${x+7}" cy="${300-Math.min(100,b.avg_drop_pct)*2}" r="3"/>`});return `<section><h2>R${r.race}｜${r.status}</h2><div class="legend"><span class="q">■ QIN 次數</span><span class="f">■ FCT 次數</span><span>● 平均跌幅％</span></div>${svg}</svg></section>`}state.races.forEach(r=>app.insertAdjacentHTML('beforeend',chart(r)));</script>'''

def publish(state, push):
    ROOT.joinpath('results.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
    ROOT.joinpath('RESULTS.md').write_text(render(state))
    ROOT.joinpath('chart.html').write_text(render_chart(state))
    if push:
        def git(*args): return subprocess.run(['git',*args],cwd=ROOT.parent,check=True,capture_output=True)
        git('add','dragon/results.json','dragon/RESULTS.md')
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT.parent).returncode:
            git('commit','-m','Update Dragon pair-drop results')
            for attempt in range(3):
                try: git('push'); break
                except subprocess.CalledProcessError:
                    if attempt==2: raise
                    git('pull','--rebase')

async def collect(config, push):
    from playwright.async_api import async_playwright
    state={'date':config['date'],'venue':config['venue'],'races':[{'race':i+1,'status':'等候 T−60'} for i in range(len(config['times']))]}
    publish(state,push)
    lock=asyncio.Lock()
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(timezone_id='Asia/Hong_Kong',locale='zh-HK')
        async def race_job(race, clock):
            off=datetime.fromisoformat(config['date']+'T'+clock).replace(tzinfo=HK)
            start,stop=off-timedelta(minutes=60),off-timedelta(minutes=10)
            pages={}; bases={}; finals={}; errors=[]
            async def save():
                async with lock: publish(state,push)
            if now()>start+timedelta(seconds=30):
                race['status']='錯過 T−60；冇結果'; await save(); return
            await asyncio.sleep(max(0,(start-now()).total_seconds()-45))
            try:
                for pool,route in [('QIN','wpq'),('FCT','fct')]:
                    page=await context.new_page(); pages[pool]=page
                    await page.goto(f"https://bet.hkjc.com/ch/racing/{route}/{config['date']}/{config['venue']}/{race['race']}",wait_until='domcontentloaded',timeout=40000)
                    await page.locator(f'[id^="qb_{pool}_"]').first.wait_for(timeout=30000)
                await asyncio.sleep(max(0,(start-now()).total_seconds()))
                race['status']='收集中'; await save()
                while now()<=stop:
                    for pool,page in pages.items():
                        if now()>stop: break
                        try:
                            raw=await page.evaluate(DOM); stamp=now()
                            if stamp>stop: continue
                            s=snapshot(raw,pool,stamp)
                            with ROOT.joinpath(f"raw-R{race['race']}.jsonl").open('a') as f:
                                f.write(json.dumps({'pool':pool,**s},ensure_ascii=False)+'\n')
                            if s['fresh'] and s['odds']:
                                if pool not in bases and stamp<=start+timedelta(seconds=30): bases[pool]=s
                                finals[pool]=s
                        except Exception as e: errors.append(type(e).__name__+': '+str(e)[:200])
                    if now()>start+timedelta(seconds=30) and len(bases)<2:
                        race['status']='起點資料缺漏／來源時間未能核實'; break
                    await asyncio.sleep(min(10,max(0,(stop-now()).total_seconds())))
                race['pools']=[]
                for pool in pages:
                    b,f=bases.get(pool),finals.get(pool)
                    if endpoint_ok(b,f,start,stop):
                        result=compare(b['odds'],f['odds'],pool)
                        result.update(baseline_time=b['captured'],final_time=f['captured'])
                        race['pools'].append(result)
                race['status']='完成' if len(race['pools'])==2 else '資料不足；未完成兩池比較'
            except Exception as e:
                race['status']='收集失敗'; errors.append(type(e).__name__+': '+str(e)[:200])
            finally:
                race['errors']=errors[-5:]
                for page in pages.values(): await page.close()
                await save()
        await asyncio.gather(*(race_job(r,t) for r,t in zip(state['races'],config['times'])))
        await browser.close()
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary: Path(summary).write_text(render(state))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--push',action='store_true'); args=ap.parse_args()
    config=json.loads(ROOT.joinpath('meeting.json').read_text())
    datetime.strptime(config['date'],'%Y-%m-%d')
    if config['venue'] not in ('HV','ST'): raise ValueError('Invalid venue')
    for clock in config['times']: datetime.strptime(clock,'%H:%M')
    asyncio.run(collect(config,args.push))

