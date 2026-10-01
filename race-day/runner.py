"""Independent combined runner. Never writes original dragon/ or dragon-webapp/."""
import argparse, asyncio, concurrent.futures, html, json, os, re, signal, subprocess, sys, time, shutil, tempfile, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import dragon_copy as dragon
import horse103_copy as horse
from method_b import decide as decide_method_b

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
PUBLISH_ROOT=REPO
HK=timezone(timedelta(hours=8))
def now(): return datetime.now(HK)
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def telegram_configured():
    return bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'))

def telegram_send(text):
    """Send a private alert without ever logging credentials or response bodies."""
    token=os.getenv('TELEGRAM_BOT_TOKEN');chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:return False
    body=urllib.parse.urlencode({'chat_id':chat,'text':text,'disable_web_page_preview':'true'}).encode()
    request=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=body,method='POST')
    with urllib.request.urlopen(request,timeout=15) as response:
        if response.status!=200:raise RuntimeError(f'Telegram HTTP {response.status}')
    return True

def qp_concentrated(snapshot):
    ranking=snapshot.get('ranking') or []
    if len(ranking)<2:return False
    amount=ranking[0].get('qp_amount');others=[row.get('qp_amount') for row in ranking[1:]]
    if not isinstance(amount,(int,float)) or any(not isinstance(x,(int,float)) for x in others):return False
    return max(others)>0 and amount>=1.5*max(others)

def apply_market_formula(snapshot,win_odds):
    """Re-rank a genuine T-3 Horse103 capture with the independent T-3 WIN snapshot."""
    ranking=snapshot.get('ranking') or []
    odds={}
    for h,value in (win_odds or {}).items():
        try:
            if float(value)>0:odds[int(h)]=float(value)
        except (TypeError,ValueError):pass
    if not ranking or not odds:return False
    qp_max=max((float(row.get('qp_amount') or 0) for row in ranking),default=0)
    q_max=max((float(row.get('q_amount') or 0) for row in ranking),default=0)
    inverse={horse:1/value for horse,value in odds.items()};inverse_max=max(inverse.values(),default=0)
    if not inverse_max:return False
    for row in ranking:
        number=int(row['horse_number'])
        vi=float(row.get('live_value_index') or 0)/100
        qp=float(row.get('qp_amount') or 0)/qp_max if qp_max else 0
        q=float(row.get('q_amount') or 0)/q_max if q_max else 0
        win_strength=inverse.get(number,0)/inverse_max
        row['win_odds']=odds.get(number);row['normalized_win_strength']=round(win_strength,6)
        row['formula_score']=round(.5*vi+(1/3)*qp+(1/12)*q+(1/12)*win_strength,5)
    ranking.sort(key=lambda row:(-row['formula_score'],-row['live_value_index'],row['horse_number']))
    snapshot['formula']='S = 0.50 * (Live103 valueIndex / 100) + 0.3333 * normalized QP amount + 0.0833 * normalized Q amount + 0.0833 * normalized inverse WIN odds'
    snapshot['formula_source']='Horse103 locked T-3 plus independent HKJC T-3 WIN snapshot'
    snapshot['main_pick']=ranking[0];snapshot['other_four']=ranking[1:5]
    return True

PLACE_LABELS={'1':'第一','2':'第二','3':'第三','4':'第四'}

def annotated(number,positions=None):
    label=(positions or {}).get(int(number))
    return f'{int(number)}號'+(f'（{label}）' if label else '')

def format_tip_message(number,snapshot,market=None,cold=None,positions=None,result=False):
    ranking=snapshot.get('ranking') or [];original_main=int(ranking[0]['horse_number'])
    decision=snapshot.get('method_b') or {};main=int(decision.get('banker',original_main))
    original={int(row['horseNumber']) for row in snapshot.get('live103_raw',{}).get('candidates',[]) if row.get('horseNumber') is not None}
    extras=[int(row['horse_number']) for row in ranking[1:5] if int(row['horse_number']) not in original and int(row['horse_number'])!=main]
    if decision.get('method')=='independent_hybrid_v1':extras=[]
    confidence='（QP集中）' if main==original_main and qp_concentrated(snapshot) else ''
    switch=f"（B換膽，原{original_main}號）" if decision.get('status')=='switched' else ''
    if decision.get('method')=='independent_hybrid_v1':confidence='';switch='（新方法）'
    confidence_horses=f'{annotated(main,positions)}{confidence}{switch}'+(('，'+'、'.join(annotated(n,positions) for n in extras)) if extras else '')
    legs='、'.join(annotated(n,positions) for n in (market or []) if int(n)!=main) or '無'
    cold_text='、'.join(annotated(n,positions) for n in (cold or [])) or '無'
    independent=snapshot.get('independent_tip',{})
    if independent.get('cold_status')=='unavailable':cold_text='無法判定：缺有效報價'
    elif independent.get('cold_quote_age_seconds',0)>120:
        cold_text+=f'（報價較舊：{round(independent["cold_quote_age_seconds"])}秒）'
    title=f'🏁 R{number}｜正式賽果更新' if result else f'🏇 R{number}｜T−3 已鎖定'
    return (title+'\n'
            f'獨贏&位置信心馬：{confidence_horses}\n'
            f'連贏位置Q：{annotated(main,positions)} 拖 {legs}\n'
            f'最有可能爆冷馬：{cold_text}\n\n'
            '查看完整資料：https://ljackylau.github.io/hkjc-scraper/race-day/')

def parse_result_html(body):
    match=re.search(r'<div[^>]*class="[^"]*performance[^"]*"[^>]*>.*?<tbody[^>]*>(.*?)</tbody>',body,re.I|re.S)
    if not match:raise RuntimeError('Official result table not ready')
    entries=[]
    for raw_row in re.findall(r'<tr[^>]*>(.*?)</tr>',match.group(1),re.I|re.S):
        cells=[]
        for raw_cell in re.findall(r'<td[^>]*>(.*?)</td>',raw_row,re.I|re.S):
            text=html.unescape(re.sub(r'<[^>]+>',' ',raw_cell))
            cells.append(' '.join(text.split()))
        if len(cells)<2:continue
        placing=re.match(r'^(\d+)',cells[0]);horse_number=re.match(r'^(\d+)$',cells[1])
        if placing and horse_number:
            entries.append({'placing':placing[1],'placing_text':cells[0],'horse_number':int(horse_number[1])})
    if len(entries)<4 or entries[0]['placing']!='1' or len({row['horse_number'] for row in entries[:4]})<4:
        raise RuntimeError('Official top-four result incomplete')
    return entries

def parse_dividends_html(body):
    """Read HKJC's official per-race dividend table; keep the published HK$ unit."""
    match=re.search(r'<div[^>]*class="[^"]*dividend_tab[^\"]*"[^>]*>.*?<table[^>]*>.*?<tbody[^>]*>(.*?)</tbody>',body,re.I|re.S)
    if not match:raise RuntimeError('Official dividends not ready')
    pools={'WIN':'W','PLACE':'P','QUINELLA':'Q','QUINELLA PLACE':'QP',
           'FORECAST':'FCT','TIERCE':'TIERCE','TRIO':'TRIO','FIRST 4':'FIRST4','QUARTET':'QUARTET'}
    found={};current=None
    for raw in re.findall(r'<tr[^>]*>(.*?)</tr>',match.group(1),re.I|re.S):
        cells=[' '.join(html.unescape(re.sub(r'<[^>]+>',' ',cell)).split()) for cell in re.findall(r'<td[^>]*>(.*?)</td>',raw,re.I|re.S)]
        if len(cells)==3:current=cells[0].upper().strip();combination,amount=cells[1:]
        elif len(cells)==2 and current:combination,amount=cells
        else:continue
        try:value=float(amount.replace(',','').replace('$',''))
        except ValueError:continue
        if current in pools and value>=0 and combination:
            found.setdefault(pools[current],[]).append({'combination':combination,'dividend_hkd':value})
    if not all(found.get(pool) for pool in ('W','P','Q','QP')):
        raise RuntimeError('Official W/P/Q/QP dividends incomplete')
    return found

def fetch_official_result(date,venue,number):
    venue='ST' if venue in ('ST','沙田') else 'HV'
    query=urllib.parse.urlencode({'racedate':date.replace('-','/'),'Racecourse':venue,'RaceNo':number})
    url='https://racing.hkjc.com/en-us/local/information/archive/localresults?'+query
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Horse103 result monitor)'})
    with urllib.request.urlopen(request,timeout=20) as response:body=response.read().decode('utf-8','replace')
    entries=parse_result_html(body)
    dividends=parse_dividends_html(body)
    return {'source':'HKJC official local results','source_url':url,'received_at':now().isoformat(),'entries':entries,'top4':[row['horse_number'] for row in entries[:4]],'dividends':dividends,'dividend_unit':'HKJC published HK$ unit','settlement_status':'complete'}

def remote_json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'hkjc-race-day-runner','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=12) as response:return json.load(response)

class MarketLegs(list):
    pass

def remote_market(date,phase,number):
    root=f'https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/{date}/hkjc-{phase}'
    stamp=int(time.time())
    status=remote_json(f'{root}/status.json?v={stamp}')
    race=(status.get('races') or {}).get(str(number)) or {}
    ranking=[int(row['horse_number']) for row in race.get('ranking') or []]
    if not ranking:return None,None,None
    golden=[int(r['horse_number']) for r in race.get('golden_legs') or []]
    ranking=MarketLegs(dict.fromkeys(golden+ranking));ranking.golden=golden
    cold=[]
    try:
        t3=remote_json(f'{root}/race_{number:02d}_t3.json?v={stamp}')
        win_odds=(t3.get('odds') or {}).get('WIN') or {}
    except Exception:return ranking,cold,None
    try:
        signal=remote_json(f'{root}/challenge/race_{number:02d}_tnc_signal.json?v={stamp}')
        trainers={''.join(str(row.get('name','')).split()) for row in signal.get('qualifying') or []}
        trainer_by_horse={int(row[0]):''.join(str(row[6]).split()) for row in t3.get('runner_rows') or []}
        cold=[horse for horse in ranking[:5] if trainer_by_horse.get(horse) in trainers]
    except Exception:pass
    return ranking,cold,win_odds

def remote_method_b(date,phase,number):
    root=f'https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/{date}/hkjc-{phase}'
    source=remote_json(f'{root}/race_{number:02d}_method_b.json?v={int(time.time())}')
    if source.get('date')!=date or source.get('race')!=number:
        raise ValueError('Method B archive race/date mismatch')
    return source

def remote_independent(date,phase,number):
    root=f'https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/{date}/hkjc-{phase}'
    source=remote_json(f'{root}/race_{number:02d}_independent.json?v={int(time.time())}')
    if source.get('date')!=date or source.get('race')!=number or source.get('method')!='independent_hybrid_v1':
        raise ValueError('Independent archive race/date/method mismatch')
    if source.get('status')=='ready':
        cut=datetime.fromisoformat(source['cutoff']);freeze=cut-timedelta(seconds=10)
        if datetime.fromisoformat(source['received_at'])>freeze:raise ValueError('Independent quote received after cutoff')
        if any(not 0<=(freeze-datetime.fromisoformat(v)).total_seconds()<=120 for v in source['source_updated'].values()):
            raise ValueError('Independent source stale at freeze')
    return source

async def independent_notification(date,phase,folder,number,state,marker):
    target=datetime.fromisoformat(state['target']) if state.get('target') else None
    if target and now()<target:return
    try:source=await asyncio.to_thread(remote_independent,date,phase,number)
    except Exception:
        if target and now()>target+timedelta(minutes=3):
            text=f'⚠️ R{number}｜未能取得新方法 T−3 快照\n請查看網站系統狀態；未改用較遲資料或 Horse103 原膽。'
            if telegram_configured():
                try:await asyncio.to_thread(telegram_send,text)
                except Exception:pass
            atomic(marker,{'status':'failed','race':number,'reason':'Independent pre-T-3 archive unavailable'})
        return
    state['independent_tip']=source
    root=f'https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/{date}/hkjc-{phase}'
    try:sent=await asyncio.to_thread(remote_json,f'{root}/race_{number:02d}_independent_notification.json?v={int(time.time())}')
    except Exception:sent={}
    if sent.get('status') not in ('sent','not_configured'):
        if target and now()>target+timedelta(minutes=3):
            atomic(marker,{'status':'failed','race':number,'reason':'Independent Telegram send not confirmed','independent_tip':source})
        return  # The HKJC worker owns T-3 sending/retries.
    decision={'method':'independent_hybrid_v1','status':'independent','banker':source.get('banker'),
              'reason':source.get('banker_source',source.get('reason')),'received_at':source.get('received_at')}
    atomic(marker,{'sent_at':sent.get('sent_at'),'race':number,'status':'saved' if source.get('status')=='ready' else 'failed',
                   'message':sent.get('message'),'method_b':decision,'independent_tip':source,
                   'market':source.get('market',[]),'golden':source.get('golden',[]),'cold':source.get('cold',[])})

async def notification_monitor(date,phase,folder,states,finished):
    notify_folder=folder/'notifications';notify_folder.mkdir(exist_ok=True)
    pending_since={}
    terminal={'missed','unavailable','partial'}
    def pending():
        return any(state.get('status') in ({'saved'}|terminal) and not (notify_folder/f'race_{int(n):02d}.json').exists() for n,state in states.items())
    while not finished.is_set() or pending():
        for n,state in list(states.items()):
            number=int(n);marker=notify_folder/f'race_{number:02d}.json'
            if marker.exists():continue
            if date>='2026-10-01':
                await independent_notification(date,phase,folder,number,state,marker)
                continue
            if state.get('status') in terminal:
                message=f'⚠️ R{number}｜T−3未能完成\n狀態：{state.get("status")}\n原因：{state.get("reason") or state.get("error") or "資料不足"}'
                if telegram_configured():
                    try:
                        await asyncio.to_thread(telegram_send,message)
                        atomic(marker,{'sent_at':now().isoformat(),'race':number,'message':message,'status':'failed'})
                    except Exception as e:print('Telegram failure alert R',number,'retry:',str(e)[:160],flush=True)
                else:atomic(marker,{'processed_at':now().isoformat(),'race':number,'notification':'not configured','status':'failed'})
                continue
            if state.get('status')!='saved':continue
            pending_since.setdefault(number,time.monotonic())
            snapshot_path=folder/'horse103'/f'race_{number:02d}.json'
            if not snapshot_path.exists():continue
            snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
            market=cold=win_odds=method_source=None
            try:market,cold,win_odds=await asyncio.to_thread(remote_market,date,phase,number)
            except Exception:pass
            try:method_source=await asyncio.to_thread(remote_method_b,date,phase,number)
            except Exception:pass
            # Independent collector publishes after the T−3 snapshot; allow it
            # time to publish both the ordinary market and the B evidence.
            if (market is None or method_source is None) and time.monotonic()-pending_since[number]<125:continue
            if win_odds and apply_market_formula(snapshot,win_odds):
                state['picks']=snapshot['ranking'][:5]
                state['formula']='market_normalized_v2'
            original=int(snapshot['ranking'][0]['horse_number'])
            decision=decide_method_b(method_source,original,snapshot['lock_time'])
            snapshot['method_b']=decision
            state['method_b']=decision
            atomic(snapshot_path,snapshot)
            message=format_tip_message(number,snapshot,market,cold)
            if not telegram_configured():
                atomic(marker,{'processed_at':now().isoformat(),'race':number,'notification':'not configured','method_b':decision,'market':market or [],'golden':getattr(market,'golden',[]),'cold':cold or []})
                continue
            try:
                await asyncio.to_thread(telegram_send,message)
                atomic(marker,{'sent_at':now().isoformat(),'race':number,'message':message,'market':market or [],'golden':getattr(market,'golden',[]),'cold':cold or [],'method_b':decision,'status':'saved'})
                print('Telegram R',number,'sent',flush=True)
            except Exception as e:print('Telegram R',number,'retry:',str(e)[:160],flush=True)
        try:await asyncio.wait_for(finished.wait(),timeout=5)
        except asyncio.TimeoutError:pass

async def result_job(race,date,folder,states,executor):
    number=int(race['race_number']);destination=folder/'results'/f'race_{number:02d}.json'
    result_marker=folder/'notifications'/f'race_{number:02d}_result.json'
    states[str(number)]={'status':'waiting'}
    if destination.exists() and result_marker.exists():
        states[str(number)]={'status':'saved'};return
    off=horse.hk_datetime(date,race['post_time'])
    while now()<off+timedelta(minutes=2):
        try:
            current=await asyncio.get_running_loop().run_in_executor(executor,horse.get_races,date)
            updated=next(r for r in current if r['id']==race['id'])
            off=horse.hk_datetime(date,updated['post_time'])
        except Exception:pass
        await asyncio.sleep(min(30,max(1,(off+timedelta(minutes=2)-now()).total_seconds())))
    deadline=off+timedelta(minutes=90);result=None
    while now()<=deadline:
        try:
            result=await asyncio.get_running_loop().run_in_executor(executor,fetch_official_result,date,race.get('venue'),number)
            break
        except Exception as e:
            states[str(number)]={'status':'waiting','error':str(e)[:180]};await asyncio.sleep(30)
    if result is None:
        states[str(number)]={'status':'unavailable','reason':'Official result/dividends not complete within 90 minutes; overnight reconciliation will retry'};return
    snapshot_path=folder/'horse103'/f'race_{number:02d}.json'
    snapshot=json.loads(snapshot_path.read_text(encoding='utf-8')) if snapshot_path.exists() else None
    if date>='2026-10-01':snapshot=None
    tip_marker=folder/'notifications'/f'race_{number:02d}.json'
    market=[];cold=[];saved_cold=None
    if tip_marker.exists():
        tip=json.loads(tip_marker.read_text(encoding='utf-8'));market=tip.get('market') or [];cold=tip.get('cold') or []
        if 'cold' in tip:saved_cold=[int(x) for x in tip['cold']]
        independent=tip.get('independent_tip')
        if independent and independent.get('status')=='ready':
            snapshot={'ranking':[{'horse_number':independent['banker']}],
                      'method_b':tip['method_b'],'independent_tip':independent}
    elif snapshot:
        try:market,cold,_=await asyncio.to_thread(remote_market,date,folder.name,number)
        except Exception:pass
    if date>='2026-10-01' and snapshot is None:
        try:
            independent=await asyncio.to_thread(remote_independent,date,folder.name,number)
            if independent.get('status')=='ready':
                snapshot={'ranking':[{'horse_number':independent['banker']}],
                          'method_b':{'method':'independent_hybrid_v1','status':'independent','banker':independent['banker']},'independent_tip':independent}
                market=independent.get('market',[]);cold=independent.get('cold',[])
                saved_cold=cold if independent.get('cold_status')=='ready' else None
        except Exception:pass
    result['date']=date;result['race']=number
    result['banker']=int(snapshot.get('method_b',{}).get('banker',snapshot['ranking'][0]['horse_number'])) if snapshot else None
    if snapshot and snapshot.get('method_b'):result['method_b']=snapshot['method_b']
    if snapshot and snapshot.get('independent_tip'):result['independent_tip']=snapshot['independent_tip']
    result['legs']=[int(x) for x in market if int(x)!=result['banker']]
    result['cold']=saved_cold
    if saved_cold is not None:result['cold_source']='saved_tip'
    atomic(destination,result);states[str(number)]={'status':'saved','top4':result['top4']}
    if snapshot and not result_marker.exists():
        positions={row['horse_number']:PLACE_LABELS.get(row['placing'],row['placing_text']) for row in result['entries'] if int(row['placing'])<=4}
        message=format_tip_message(number,snapshot,market,cold,positions=positions,result=True)
        message='正式賽果：'+'－'.join(str(x) for x in result['top4'])+'\n'+message
        if telegram_configured():
            for attempt in range(6):
                try:
                    await asyncio.to_thread(telegram_send,message)
                    atomic(result_marker,{'sent_at':now().isoformat(),'race':number,'message':message})
                    break
                except Exception as e:
                    states[str(number)]['notification_error']=str(e)[:160]
                    if attempt<5:await asyncio.sleep(10)
        else:atomic(result_marker,{'processed_at':now().isoformat(),'race':number,'notification':'not configured'})
def plan(date):
    datetime.strptime(date,'%Y-%m-%d')
    races=horse.get_races(date)
    if not races or any(not r.get('post_time') for r in races):raise RuntimeError('Meeting schedule unavailable')
    races.sort(key=lambda r:r['race_number'])
    cut=max(1,len(races)//2)
    return {'date':date,'races':races,'early':[r['race_number'] for r in races[:cut]],'late':[r['race_number'] for r in races[cut:]],'source':'Horse103 race schedule; rechecked at startup'}
def git(*args,check=True):
    return subprocess.run(['git',*args],cwd=PUBLISH_ROOT,check=check,capture_output=True,text=True,timeout=40)
def publish(folder):
    # Each phase owns a different directory. Rebase concurrent commits; never force-push.
    rel=str(folder.relative_to(REPO))
    shutil.copytree(folder,PUBLISH_ROOT/rel,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.tmp'))
    git('add','--',rel)
    if git('diff','--cached','--quiet',check=False).returncode==0:return
    git('commit','-m','Race Day snapshot [skip ci]')
    for attempt in range(3):
        try:git('push','origin','HEAD:refs/heads/race-day-data');return
        except subprocess.CalledProcessError:
            if attempt==2:raise
            git('fetch','origin','race-day-data')
            git('rebase','FETCH_HEAD')
def setup_data_branch():
    global PUBLISH_ROOT
    git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    result=git('ls-remote','--heads','origin','race-day-data')
    if result.stdout.strip():
        git('fetch','origin','race-day-data')
    ref='FETCH_HEAD' if result.stdout.strip() else 'HEAD'
    destination=Path(tempfile.mkdtemp(prefix='race-day-publish-'))/'worktree'
    git('worktree','add','--detach',str(destination),ref)
    PUBLISH_ROOT=destination
    if (destination/'race-day-data').exists():
        shutil.copytree(destination/'race-day-data',REPO/'race-day-data',dirs_exist_ok=True)

def valid_live(live,race,date):
    candidates=live.get('candidates') or []
    quality=live.get('dataQuality')
    if not candidates or quality not in ('ready','partial'):return False
    # Live103 can mark an otherwise usable locked response as partial when one
    # preview horse has no valueIndex. Preserve that genuine T-3 response when
    # at least three candidates remain independently scoreable; never accept a
    # sparse/placeholder partial response.
    if quality=='partial':
        scoreable=sum(
            1 for row in candidates
            if row.get('horseNumber') is not None and isinstance(row.get('valueIndex'),(int,float))
        )
        if scoreable<3:return False
    target=horse.hk_datetime(date,race['post_time'])-timedelta(minutes=3)
    return live.get('phase') in ('locked','started') and abs((horse.parse_utc(live['lockTime'])-target).total_seconds())<=2

class ScheduleMoved(RuntimeError):
    def __init__(self,target):
        super().__init__(f'Schedule moved to {target.isoformat()}')
        self.target=target

async def horse_job(race,date,folder,states,executor):
    n=race['race_number'];target=horse.hk_datetime(date,race['post_time'])-timedelta(minutes=3)
    dest=folder/'horse103'/f'race_{n:02d}.json'
    if dest.exists():
        saved=json.loads(dest.read_text())
        states[str(n)]={'status':'saved','target':saved['lock_time'],'delay_seconds':saved.get('capture_delay_seconds'),'picks':saved['ranking'][:5],'original':[a['horseNumber'] for a in saved['live103_raw']['candidates']]}
        return
    states[str(n)]={'status':'waiting','target':target.isoformat()}
    # Re-read the authoritative schedule while waiting; meetings can be delayed.
    while True:
        try:
            current=await asyncio.get_running_loop().run_in_executor(executor,horse.get_races,date)
            updated=next(r for r in current if r['id']==race['id'])
            race=updated;target=horse.hk_datetime(date,race['post_time'])-timedelta(minutes=3)
            states[str(n)]={'status':'waiting','target':target.isoformat()}
        except Exception as e:
            states[str(n)]['error']='Schedule refresh: '+str(e)[:150]
        if now()>=target:break
        await asyncio.sleep(min(20,max(0,(target-now()).total_seconds())))
    # Never manufacture a T-3 snapshot by querying a race long after its lock.
    if now()>target+timedelta(seconds=90):
        states[str(n)]={'status':'missed','target':target.isoformat(),'reason':'Started more than 90 seconds after T-3'};return
    loop=asyncio.get_running_loop()
    evidence=None
    def capture():
        nonlocal evidence
        # Request Live103 before slower ticket pagination.
        live=evidence['live'] if evidence else horse.request('/functions/v1/live103-decision',{'raceId':race['id']})
        try:reported=horse.parse_utc(live['lockTime']).astimezone(HK)
        except Exception:reported=None
        # Live103 lockTime is the final authority when its schedule update reaches
        # the decision endpoint before the races table.
        if reported and target+timedelta(seconds=2)<reported<=target+timedelta(minutes=30):
            atomic(folder/'horse103'/f'race_{n:02d}_schedule_update.json',{'received_at':now().isoformat(),'old_lock':target.isoformat(),'new_lock':reported.isoformat(),'live':live})
            raise ScheduleMoved(reported)
        if not valid_live(live,race,date):
            atomic(folder/'horse103'/f'race_{n:02d}_rejected.json',{'received_at':now().isoformat(),'expected_lock':target.isoformat(),'live':live})
            raise RuntimeError(f"Live103 quality={live.get('dataQuality')}, phase={live.get('phase')}, lockTime={live.get('lockTime')}; expected={target.isoformat()}")
        fetched=evidence['live_received_at'] if evidence else now().isoformat()
        lag=(datetime.fromisoformat(fetched)-target).total_seconds()
        if not 0<=lag<=90:raise RuntimeError('Response received outside 90-second capture window')
        if evidence is None:
            evidence={'source':'103.plus Live103','race':race,'date':date,'expected_lock':target.isoformat(),'live_received_at':fetched,'capture_delay_seconds':round(lag,2),'live':live}
            # Keep the first valid response even if tickets, entries or publication fail.
            atomic(folder/'horse103'/f'race_{n:02d}_live.json',evidence)
        base=horse.get_base_race_id(date,None)
        tickets=horse.get_tickets(date)
        cutoff=horse.parse_utc(live['lockTime'])
        eligible=[t for t in tickets if int(t['race_id'])==base+n-1 and horse.parse_utc(t['scraped_at'])<=cutoff]
        atomic(folder/'horse103'/f'race_{n:02d}_tickets.json',{'received_at':now().isoformat(),'cutoff':live['lockTime'],'tickets':eligible})
        # capture_race must consume exactly the response obtained above.
        return horse.capture_race(race,date,base,tickets,live_override=live),fetched
    while now()<=target+timedelta(seconds=90):
        try:
            result,fetched=await loop.run_in_executor(executor,capture)
            lag=(datetime.fromisoformat(fetched)-target).total_seconds()
            if lag>90:raise RuntimeError('Response received outside 90-second capture window')
            result['live_received_at']=fetched;result['capture_delay_seconds']=round(lag,2)
            result['timing_note']='First valid response after T-3; actual receipt timestamp retained.'
            result['source_data_quality']=result['live103_raw'].get('dataQuality')
            result['incomplete_live_candidates']=[
                row.get('horseNumber') for row in result['live103_raw'].get('candidates',[])
                if not isinstance(row.get('valueIndex'),(int,float))
            ]
            if not result['ranking']:raise RuntimeError('No eligible runners')
            atomic(dest,result)
            states[str(n)]={'status':'saved','target':target.isoformat(),'delay_seconds':round(lag,2),'data_quality':result['source_data_quality'],'incomplete_live_candidates':result['incomplete_live_candidates'],'picks':result['ranking'][:5],'original':[r['horseNumber'] for r in result['live103_raw']['candidates']]}
            print('Horse103 R',n,'saved', [r['horse_number'] for r in result['ranking'][:5]],flush=True);return
        except ScheduleMoved as moved:
            evidence=None
            target=moved.target
            race={**race,'post_time':(target+timedelta(minutes=3)).strftime('%H:%M')}
            states[str(n)]={'status':'waiting','target':target.isoformat(),'reason':'Schedule delayed; following Live103 lockTime'}
            while now()<target:await asyncio.sleep(min(20,max(0,(target-now()).total_seconds())))
        except Exception as e:
            states[str(n)]={'status':'retrying','target':target.isoformat(),'error':str(e)[:250]}
            try:
                latest=await loop.run_in_executor(executor,horse.get_races,date)
                updated=next(r for r in latest if r['id']==race['id'])
                revised=horse.hk_datetime(date,updated['post_time'])-timedelta(minutes=3)
                if evidence is None and revised!=target and now()<=revised+timedelta(seconds=90):
                    return await horse_job(updated,date,folder,states,executor)
            except Exception:pass
            await asyncio.sleep(5)
    states[str(n)]['status']='unavailable'
    if evidence:
        states[str(n)]['status']='partial'
        states[str(n)]['reason']='T−3 Live103 saved; ranking incomplete. See raw evidence.'

async def run(args):
    config=json.loads((HERE/'plan.json').read_text())
    if args.date!=config['date']:raise RuntimeError('Date mismatch')
    if now().date().isoformat()!=args.date:raise RuntimeError('Run only on the selected Hong Kong race date; use Preflight today')
    numbers=config[args.phase];races=[r for r in config['races'] if r['race_number'] in numbers]
    if not races:return
    if args.push:setup_data_branch()
    folder=REPO/'race-day-data'/args.date/args.phase;folder.mkdir(parents=True,exist_ok=True)
    dragon.ROOT=folder/'dragon';dragon.ROOT.mkdir(exist_ok=True)
    def dragon_save(state,push):
        state['published_at']=now().isoformat();atomic(dragon.ROOT/'results.json',state)
    dragon.publish=dragon_save
    states={};result_states={};executor=concurrent.futures.ThreadPoolExecutor(max_workers=4)
    dragon_config={'date':args.date,'venue':'ST' if races[0]['venue'] in ('沙田','ST') else 'HV','times':[r['post_time'] for r in races],'race_numbers':numbers,'source':config['source']}
    tasks=[asyncio.create_task(dragon.collect(dragon_config,False,False))]
    tasks += [asyncio.create_task(horse_job(r,args.date,folder,states,executor)) for r in races]
    tasks += [asyncio.create_task(result_job(r,args.date,folder,result_states,executor)) for r in races]
    stop=asyncio.Event();jobs_finished=asyncio.Event();loop=asyncio.get_running_loop()
    notifier=asyncio.create_task(notification_monitor(args.date,args.phase,folder,states,jobs_finished))
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
    last_push=0;publish_error=None
    try:
        while not stop.is_set():
            errors=[str(t.exception())[:250] for t in tasks if t.done() and not t.cancelled() and t.exception()]
            atomic(folder/'status.json',{'date':args.date,'phase':args.phase,'updated_at':now().isoformat(),'state':'running','horse103':states,'results':result_states,'errors':errors,'publish_error':publish_error})
            if args.push and time.monotonic()-last_push>=60:
                try:await asyncio.to_thread(publish,folder);publish_error=None
                except Exception as e:publish_error=str(e)[:250];print('Publish retry next minute:',publish_error,flush=True)
                last_push=time.monotonic()
            if all(t.done() for t in tasks):
                jobs_finished.set()
                try:await asyncio.wait_for(notifier,timeout=95)
                except asyncio.TimeoutError:notifier.cancel()
                break
            try:await asyncio.wait_for(stop.wait(),timeout=3)
            except asyncio.TimeoutError:pass
    finally:
        jobs_finished.set()
        for t in tasks:
            if not t.done():t.cancel()
        if not notifier.done():notifier.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await asyncio.gather(notifier,return_exceptions=True)
        atomic(folder/'status.json',{'date':args.date,'phase':args.phase,'updated_at':now().isoformat(),'state':'stopped' if stop.is_set() else 'finished','horse103':states,'results':result_states,'publish_error':publish_error})
        if args.push:
            try:await asyncio.to_thread(publish,folder)
            except Exception as e:print('Final publish failed:',e,flush=True)
        executor.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--date',required=True);p.add_argument('--phase',choices=['early','late']);p.add_argument('--plan',action='store_true');p.add_argument('--push',action='store_true');a=p.parse_args()
    if a.plan:
        c=plan(a.date);atomic(HERE/'plan.json',c)
        early=c['races'][0]; late=next((r for r in c['races'] if r['race_number'] in c['late']),None)
        # Release late job 30 minutes before its T-60 window. Delay happens in its own job.
        release=horse.hk_datetime(a.date,late['post_time'])-timedelta(minutes=90) if late else now()
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('release='+release.isoformat()+'\n')
        print(json.dumps(c,ensure_ascii=False,indent=2))
    else:asyncio.run(run(a))
