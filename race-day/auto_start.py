"""Schedule existing race-day workflow; all times are Hong Kong time.
No predictions or bets are generated here. Uses the existing runner's schedule.
"""
import argparse,json,os,re,urllib.request,urllib.parse
from datetime import datetime,timedelta,timezone
from horse103_copy import get_races
HK=timezone(timedelta(hours=8))
WORKFLOW='race-day-combined.yml'

def meeting(rows,date):
    if not rows:return None
    rows=sorted(rows,key=lambda r:int(r['race_number']))
    if [int(r['race_number']) for r in rows]!=list(range(1,len(rows)+1)) or not 1<=len(rows)<=14:
        raise ValueError('Incomplete race schedule')
    venues={'ST' if r.get('venue') in ('ST','沙田') else 'HV' if r.get('venue') in ('HV','跑馬地') else None for r in rows}
    if len(venues)!=1 or None in venues:raise ValueError('Invalid or mixed venues')
    clocks=[]
    for row in rows:
        clock=str(row.get('post_time',''))
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('Invalid advertised time')
        clocks.append(clock)
    if any(b<=a for a,b in zip(clocks,clocks[1:])):raise ValueError('Race times not increasing')
    first=datetime.fromisoformat(date+'T'+clocks[0]+':00').replace(tzinfo=HK)
    return {'date':date,'venue':next(iter(venues)),'post_times':','.join(clocks),'first_off':first.isoformat(),'race_count':len(rows),'source':'existing Horse103 race schedule; HKJC collector observes subsequent revisions'}

def decision(config,now,runs):
    if config is None:return 'no_meeting'
    remaining=(datetime.fromisoformat(config['first_off'])-now).total_seconds()/60
    if remaining>120:return 'too_early'
    if remaining<=0:return 'already_started'
    # New run-name identifies both manual and automatic Run dispatches.
    marker=f"Race Day {config['date']} · Run ·"
    matching=[r for r in runs if r.get('display_title','').startswith(marker)]
    if matching:return 'already_dispatched'  # Failed runs require deliberate manual retry.
    if remaining<60:return 'missed_start_window'
    return 'dispatch'

class GitHub:
    def __init__(self,repo,token):self.repo=repo;self.token=token
    def request(self,path,body=None):
        url=f'https://api.github.com/repos/{self.repo}/'+path
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(url,data=data,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'},method='POST' if body is not None else 'GET')
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read();return json.loads(raw) if raw else None
    def runs(self,date):
        # Midnight HK is the preceding UTC day at 16:00.
        since=datetime.fromisoformat(date+'T00:00:00').replace(tzinfo=HK).astimezone(timezone.utc).isoformat()
        query=urllib.parse.urlencode({'event':'workflow_dispatch','created':'>='+since,'per_page':100})
        rows=[]
        for page in range(1,11):
            data=self.request(f'actions/workflows/{WORKFLOW}/runs?{query}&page={page}');chunk=data['workflow_runs'];rows.extend(chunk)
            if len(chunk)<100:return rows
        raise RuntimeError('Run history exceeds safe pagination limit')
    def dispatch(self,c):
        self.request(f'actions/workflows/{WORKFLOW}/dispatches',{'ref':'main','inputs':{'date':c['date'],'mode':'Run','venue':c['venue'],'post_times':c['post_times']}})

def notify(text):
    from runner import telegram_configured,telegram_send
    if telegram_configured():telegram_send(text)

def check(now=None,dry_run=False):
    now=now or datetime.now(HK);date=now.astimezone(HK).date().isoformat()
    c=meeting(get_races(date),date)
    if c is None:return {'status':'no_meeting','date':date}
    client=GitHub(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN'])
    status=decision(c,now,client.runs(date))
    if status=='dispatch' and not dry_run:
        client.dispatch(c)
        # A notification error after accepted dispatch must not imply no dispatch.
        try:notify(f"✅ 賽日Runner已自動提交\n{date}｜{c['venue']}｜{c['race_count']}場\n第一場 {datetime.fromisoformat(c['first_off']).strftime('%H:%M')}\n現有workflow將執行檢查及分段收集；並非所有快照已就緒。")
        except Exception:print('Startup notification failed (dispatch already accepted)',flush=True)
    if status=='missed_start_window' and not dry_run:
        notify(f'⚠️ {date} 自動啟動遲於第一場前60分鐘；未自動提交，請查看GitHub Actions並按需要手動Run。')
    return {'status':status,'dry_run':dry_run,**c}

def report_results():
    results=json.loads(os.environ['JOB_RESULTS'])
    bad=[name for name,item in results.items() if item.get('result') in ('failure','cancelled')]
    if bad:notify('⚠️ 賽日workflow有失敗／取消工作\n'+os.environ.get('RACE_DATE','')+'｜'+', '.join(bad)+'\n'+os.environ.get('RUN_URL',''))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--report-results',action='store_true');a=p.parse_args()
    if a.report_results:report_results()
    else:
        try:print(json.dumps(check(dry_run=a.dry_run),ensure_ascii=False))
        except Exception as exc:
            if not a.dry_run:
                try:notify('⚠️ 自動賽日啟動檢查失敗｜'+type(exc).__name__+'\n請查看GitHub Actions；未自動補用其他日期或時間。')
                except Exception:pass
            raise RuntimeError('Automatic startup check failed; inspect schedule/API access') from None
