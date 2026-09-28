"""Independent combined runner. Never writes original dragon/ or dragon-webapp/."""
import argparse, asyncio, concurrent.futures, json, os, signal, subprocess, sys, time, shutil, tempfile, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import dragon_copy as dragon
import horse103_copy as horse

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

def format_tip_message(number,snapshot,market=None,cold=None):
    ranking=snapshot.get('ranking') or [];main=int(ranking[0]['horse_number'])
    original={int(row['horseNumber']) for row in snapshot.get('live103_raw',{}).get('candidates',[]) if row.get('horseNumber') is not None}
    extras=[int(row['horse_number']) for row in ranking[1:5] if int(row['horse_number']) not in original]
    confidence='（QP集中）' if qp_concentrated(snapshot) else ''
    confidence_horses=f'{main}號{confidence}'+(('，'+'、'.join(f'{n}號' for n in extras)) if extras else '')
    legs='、'.join(f'{int(n)}號' for n in (market or []) if int(n)!=main) or '無'
    cold_text='、'.join(f'{int(n)}號' for n in (cold or [])) or '無'
    return (f'🏇 R{number}｜T−3 已鎖定\n'
            f'獨贏&位置信心馬：{confidence_horses}\n'
            f'連贏位置Q：{main}號 拖 {legs}\n'
            f'最有可能爆冷馬：{cold_text}\n\n'
            '查看完整資料：https://ljackylau.github.io/hkjc-scraper/race-day/')

def remote_json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'hkjc-race-day-runner','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=12) as response:return json.load(response)

def remote_market(date,phase,number):
    root=f'https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/{date}/hkjc-{phase}'
    stamp=int(time.time())
    status=remote_json(f'{root}/status.json?v={stamp}')
    race=(status.get('races') or {}).get(str(number)) or {}
    ranking=[int(row['horse_number']) for row in race.get('ranking') or []]
    if not ranking:return None,None,None
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

async def notification_monitor(date,phase,folder,states,finished):
    notify_folder=folder/'notifications';notify_folder.mkdir(exist_ok=True)
    pending_since={}
    while not finished.is_set() or any(state.get('status')=='saved' and not (notify_folder/f'race_{int(n):02d}.json').exists() for n,state in states.items()):
        for n,state in list(states.items()):
            number=int(n);marker=notify_folder/f'race_{number:02d}.json'
            if state.get('status')!='saved' or marker.exists():continue
            pending_since.setdefault(number,time.monotonic())
            snapshot_path=folder/'horse103'/f'race_{number:02d}.json'
            if not snapshot_path.exists():continue
            snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
            market=cold=win_odds=None
            try:market,cold,win_odds=await asyncio.to_thread(remote_market,date,phase,number)
            except Exception:pass
            # Allow the parallel HKJC collector one minute to publish the full signal.
            if market is None and time.monotonic()-pending_since[number]<75:continue
            if win_odds and apply_market_formula(snapshot,win_odds):
                atomic(snapshot_path,snapshot)
                state['picks']=snapshot['ranking'][:5]
                state['formula']='market_normalized_v2'
            message=format_tip_message(number,snapshot,market,cold)
            if not telegram_configured():
                atomic(marker,{'processed_at':now().isoformat(),'race':number,'notification':'not configured'})
                continue
            try:
                await asyncio.to_thread(telegram_send,message)
                atomic(marker,{'sent_at':now().isoformat(),'race':number,'message':message})
                print('Telegram R',number,'sent',flush=True)
            except Exception as e:print('Telegram R',number,'retry:',str(e)[:160],flush=True)
        try:await asyncio.wait_for(finished.wait(),timeout=5)
        except asyncio.TimeoutError:pass
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
    states={};executor=concurrent.futures.ThreadPoolExecutor(max_workers=3)
    dragon_config={'date':args.date,'venue':'ST' if races[0]['venue'] in ('沙田','ST') else 'HV','times':[r['post_time'] for r in races],'race_numbers':numbers,'source':config['source']}
    tasks=[asyncio.create_task(dragon.collect(dragon_config,False,False))]
    tasks += [asyncio.create_task(horse_job(r,args.date,folder,states,executor)) for r in races]
    stop=asyncio.Event();jobs_finished=asyncio.Event();loop=asyncio.get_running_loop()
    notifier=asyncio.create_task(notification_monitor(args.date,args.phase,folder,states,jobs_finished))
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
    last_push=0;publish_error=None
    try:
        while not stop.is_set():
            errors=[str(t.exception())[:250] for t in tasks if t.done() and not t.cancelled() and t.exception()]
            atomic(folder/'status.json',{'date':args.date,'phase':args.phase,'updated_at':now().isoformat(),'state':'running','horse103':states,'errors':errors,'publish_error':publish_error})
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
        atomic(folder/'status.json',{'date':args.date,'phase':args.phase,'updated_at':now().isoformat(),'state':'stopped' if stop.is_set() else 'finished','horse103':states,'publish_error':publish_error})
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
