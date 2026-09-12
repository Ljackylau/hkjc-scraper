"""Independent combined runner. Never writes original dragon/ or dragon-webapp/."""
import argparse, asyncio, concurrent.futures, json, os, signal, subprocess, sys, time, shutil, tempfile
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
    if not live.get('candidates') or live.get('dataQuality')!='ready':return False
    target=horse.hk_datetime(date,race['post_time'])-timedelta(minutes=3)
    return live.get('phase') in ('locked','started') and abs((horse.parse_utc(live['lockTime'])-target).total_seconds())<=2

async def horse_job(race,date,folder,states,executor):
    n=race['race_number'];target=horse.hk_datetime(date,race['post_time'])-timedelta(minutes=3)
    dest=folder/'horse103'/f'race_{n:02d}.json'
    if dest.exists():
        saved=json.loads(dest.read_text())
        states[str(n)]={'status':'saved','target':saved['lock_time'],'delay_seconds':saved.get('capture_delay_seconds'),'picks':saved['ranking'][:5],'original':[a['horseNumber'] for a in saved['live103_raw']['candidates']]}
        return
    states[str(n)]={'status':'waiting','target':target.isoformat()}
    while now()<target:await asyncio.sleep(min(5,(target-now()).total_seconds()))
    # Never manufacture a T-3 snapshot by querying a race long after its lock.
    if now()>target+timedelta(seconds=90):
        states[str(n)]={'status':'missed','target':target.isoformat(),'reason':'Started more than 90 seconds after T-3'};return
    loop=asyncio.get_running_loop()
    def capture():
        base=horse.get_base_race_id(date,None)
        # Request Live103 before slower ticket pagination.
        live=horse.request('/functions/v1/live103-decision',{'raceId':race['id']})
        if not valid_live(live,race,date):raise RuntimeError('T-3 response not ready or lockTime mismatches schedule')
        fetched=now().isoformat()
        tickets=horse.get_tickets(date)
        # capture_race must consume exactly the response obtained above.
        return horse.capture_race(race,date,base,tickets,live_override=live),fetched
    while now()<=target+timedelta(seconds=90):
        try:
            result,fetched=await loop.run_in_executor(executor,capture)
            lag=(datetime.fromisoformat(fetched)-target).total_seconds()
            if lag>90:raise RuntimeError('Response received outside 90-second capture window')
            result['live_received_at']=fetched;result['capture_delay_seconds']=round(lag,2)
            result['timing_note']='First valid response after T-3; actual receipt timestamp retained.'
            if not result['ranking']:raise RuntimeError('No eligible runners')
            atomic(dest,result)
            states[str(n)]={'status':'saved','target':target.isoformat(),'delay_seconds':round(lag,2),'picks':result['ranking'][:5],'original':[r['horseNumber'] for r in result['live103_raw']['candidates']]}
            print('Horse103 R',n,'saved', [r['horse_number'] for r in result['ranking'][:5]],flush=True);return
        except Exception as e:
            states[str(n)]={'status':'retrying','target':target.isoformat(),'error':str(e)[:250]}
            await asyncio.sleep(5)
    states[str(n)]['status']='unavailable'

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
    stop=asyncio.Event();loop=asyncio.get_running_loop()
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
            if all(t.done() for t in tasks):break
            try:await asyncio.wait_for(stop.wait(),timeout=3)
            except asyncio.TimeoutError:pass
    finally:
        for t in tasks:
            if not t.done():t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
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
