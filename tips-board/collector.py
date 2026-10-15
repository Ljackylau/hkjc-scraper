"""Date-validated expert tips, pre-off index capture and official results.
All persisted timestamps use Asia/Hong_Kong. No retrospective index selection.
"""
import argparse,copy,base64,concurrent.futures,hashlib,json,os,re,subprocess,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from cryptography.hazmat.primitives.padding import PKCS7
from sha_tin_four import capture_four, PRO_IDS
HK=ZoneInfo('Asia/Hong_Kong')
ONCC='https://racing.on.cc/racing/fav/current/rjfavf0201x0.html'
ST='https://racing.stheadline.com/api'
CARD='https://racing.hkjc.com/zh-hk/local/information/racecard'
INDEX='https://data.66888.hk/runtime/cache/tips_new_oss_state.json'
EXPERTS={'ball':'波仔','ma':'馬觀微','computer':'電腦評分'}
def now():return datetime.now(HK)
def stamp():return now().isoformat(timespec='seconds')
def request(url,json_data=False):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (HK race tips reader)','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=18) as r:
        raw=r.read();enc=r.headers.get_content_charset() or 'utf-8'
    if json_data:return json.loads(raw)
    if 'on.cc' in url:enc='big5' if b'big5' in raw[:2500].lower() else enc
    return raw.decode(enc,'replace')
def api(path,**query):
    j=request(ST+path+'?'+urllib.parse.urlencode({**query,'rev':2}),True)
    if j.get('code')!=200:raise ValueError('Star API not ready')
    return j['data']
def parse_card(body):
    soup=BeautifulSoup(body,'html.parser');info=soup.find('div',class_='f_fs13',style=re.compile('line-height: 20px'))
    text=info.get_text(' ',strip=True) if info else ''
    d=re.search(r'(\d{4})年(\d+)月(\d+)日',text);n=re.search(r'第\s*(\d+)\s*場',text);clock=re.search(r'\b(\d{1,2}:\d{2})\b',text)
    if not (d and n and clock):raise ValueError('Official race card date/time missing')
    date=f'{int(d[1]):04}-{int(d[2]):02}-{int(d[3]):02}';venue='HV' if '跑馬地' in text else 'ST' if '沙田' in text else None
    horses=[];scratched=[]
    for row in soup.select('#racecardlist tr'):
        cells=row.find_all('td',recursive=False)
        if len(cells)>=4 and cells[0].get_text(strip=True).isdigit():
            horses.append({'no':int(cells[0].get_text(strip=True)),'name':cells[3].get_text(' ',strip=True)})
            if re.search(r'退出|WITHDRAWN|SCRATCHED',row.get_text(' ',strip=True),re.I):scratched.append(int(cells[0].get_text(strip=True)))
    if not venue or len(horses)<4:raise ValueError('Official declared field incomplete')
    off=datetime.fromisoformat(date+'T'+clock[1]+':00').replace(tzinfo=HK).isoformat()
    return {'date':date,'venue':venue,'race':int(n[1]),'off':off,'horses':horses,'scratched':scratched}
def calendar():
    body=request(CARD);one=parse_card(body);count=max([1]+[int(n) for n in re.findall(r'RaceNo=(\d+)',body,re.I)])
    def get(n):
        q=urllib.parse.urlencode({'racedate':one['date'].replace('-','/'),'Racecourse':one['venue'],'RaceNo':n})
        r=parse_card(body if n==1 else request(CARD+'?'+q))
        if (r['date'],r['venue'],r['race'])!=(one['date'],one['venue'],n):raise ValueError('Official card mismatch')
        return r
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:races=list(pool.map(get,range(1,count+1)))
    if any(a['off']>=b['off'] for a,b in zip(races,races[1:])):raise ValueError('Race times not increasing')
    return {'date':one['date'],'venue':one['venue'],'source':CARD,'races':races}
def empty_meeting(c):
    return {**c,'updated_at':stamp(),'status':'upcoming','tips_checked_at':None,'tips_due_at':(datetime.fromisoformat(c['races'][0]['off'])-timedelta(hours=2)).isoformat(),'heartbeat':None,'errors':[],
      'races':[{**r,'tips':{k:{'status':'pending','horses':[]} for k in ['meiji',*EXPERTS]},'index':{'status':'pending','horses':[]},'score':None,'selection':None,'result':None,'locked':False} for r in c['races']]}
def safe_horses(items,race):
    field={r['no']:r['name'] for r in race['horses']};out=[]
    for h in items:
        n=int(h['no']);name=h.get('name','').replace(' ','')
        canonical=field.get(n,'').replace(' ','')
        # Old Big5 archives sometimes publish a literal '?' for an unsupported glyph.
        # Repair only one missing glyph when every other character and horse number match.
        repaired=name!=canonical and len(name)==len(canonical) and len(name)>=3 and sum(c in '?�' for c in name)==1 and all(a==b or a in '?�' for a,b in zip(name,canonical))
        if n not in field or (name and name!=canonical and not repaired):raise ValueError('Horse number/name mismatch')
        if n in [x['no'] for x in out]:raise ValueError('Duplicate horse')
        out.append({'no':n,'name':field[n],**({'source_name':h.get('name'),'name_repair':'single missing archive glyph; other characters match'} if repaired else {})})
    return out

def parse_meiji(body,date):
    soup=BeautifulSoup(body,'html.parser');text=soup.get_text(' ',strip=True)
    match=re.search(r'賽事日期\s*[：:]\s*(\d{1,2})/(\d{1,2})/(\d{4})',text)
    if not match:raise ValueError('On.cc source date missing')
    source_date=f'{int(match[3]):04}-{int(match[2]):02}-{int(match[1]):02}'
    if source_date!=date:return source_date,{}
    start=text.find('明治朗貼士')
    if start<0:raise ValueError('Meiji section missing')
    section=text[start+len('明治朗貼士'):];end=re.search(r'[^\s]{2,8}貼士',section)
    if end:section=section[:end.start()]
    out={}
    for m in re.finditer(r'第\s*(\d+)\s*場\s*(.*?)(?=第\s*\d+\s*場|$)',section):
        picks=re.findall(r'(\d+)\s*([^\d\s]+)',m[2])[:4]
        if len(picks)!=4:raise ValueError('Meiji four picks incomplete')
        out[int(m[1])]=[{'no':int(n),'name':name} for n,name in picks]
    return source_date,out

def collect_tips(meeting):
    if meeting.get('tips_checked_at'):return
    meeting['tips_checked_at']=stamp()
    try:
        meiji_url='https://racing.on.cc/racing/fav/'+meeting['date'].replace('-','')+'/rjfavf0201x0.html'
        date,m=parse_meiji(request(meiji_url),meeting['date'])
        for r in meeting['races']:
            r['tips']['meiji']={'status':'ready' if r['race'] in m else 'stale' if date!=meeting['date'] else 'error','source_date':date,'source':meiji_url,'captured_at':stamp(),'horses':safe_horses(m.get(r['race'],[]),r)}
    except Exception as e:
        for r in meeting['races']:r['tips']['meiji']={'status':'error','horses':[],'error':str(e)}
    try:
        date=meeting['date'].replace('-','');published=api('/raceDay/published',date=date)
        if datetime.fromisoformat(published['date'].replace('Z','+00:00')).astimezone(HK).date().isoformat()!=meeting['date'] or published['raceVenue']!=meeting['venue']:raise ValueError('Star published meeting date mismatch')
        experts=api('/raceDay/expertTips',date=date)
        for r in meeting['races']:
            entry=api('/raceEntry',date=date,raceNo=r['race'])
            if datetime.fromisoformat(entry['raceDate'].replace('Z','+00:00')).astimezone(HK).date().isoformat()!=meeting['date'] or entry['raceNo']!=r['race']:raise ValueError('Star entry date/race mismatch')
            lookup={x['jcIdHorse']:x for x in entry['raceEntries'] if not x.get('standby')}
            for key,name in EXPERTS.items():
                expert=next((x for x in experts if (str(x.get('expert',{}).get('_id',x.get('expert',{}).get('id','')))==PRO_IDS[key] if key in PRO_IDS else x.get('expert',{}).get('name')==name)),None)
                if expert is None:r['tips'][key]={'status':'error','horses':[],'error':'Expert missing'};continue
                tip=next((t for t in expert['tipsList'] if t['raceNo']==r['race']),None)
                ids=[tip.get('jcIdHorse'+str(i)) for i in range(1,5)] if tip else []
                items=[]
                for ident in filter(None,ids):
                    h=lookup.get(ident)
                    if not h:raise ValueError('Expert horse is outside declared field')
                    items.append({'no':h['horseNo'],'name':h['horse']['name']})
                r['tips'][key]={'status':'ready' if items else 'absent','horses':safe_horses(items,r),'source':ST+'/raceDay/expertTips?date='+date,'source_date':meeting['date'],'captured_at':stamp()}
    except Exception as e:
        for r in meeting['races']:
            for key in EXPERTS:
                if r['tips'][key]['status']=='pending':r['tips'][key]={'status':'error','horses':[],'error':str(e)}
    for r in meeting['races']:choose(r)
    capture_four(meeting,request,stamp,now)

def choose(r):
    if r.get('locked'):return
    sources=[r['tips'][k] for k in EXPERTS]
    if any(s['status'] not in ('ready','absent') for s in sources):r['score']=None;r['selection']=None;return
    r['score']=sum(bool(s['horses']) for s in sources);h=r['score'];m=r['tips']['meiji']['horses'];p=[]
    if h==0:p=r['index']['horses'][:2]
    elif h==1:
        first=next(s['horses'][0] for s in sources if s['horses'])
        other=next((x for x in m[:2] if x['no']!=first['no']),None)
        if other:p=[first,other]
    elif len(m)>=3:p=m[:3]
    need=2 if h<2 else 3
    if len(p)!=need:r['selection']=None;return
    r['selection']={'horses':p,'main':['W','P'] if h<2 else ['QP'],'optional':[] if h==0 else ['QP'] if h==1 else ['W','Q'],'generated_at':stamp()}

def decode_index(j,shell):
    if j.get('v')!=1:return j
    sk=re.search(r'"wqpFeedCipherKey":"([^"]+)"',shell)
    if not sk:raise ValueError('Public page cipher config missing')
    key=hashlib.sha256((sk[1]+'|66888.hk|wqp-feed-aes-v1').encode()).digest();b=base64.b64decode(j['d'])
    dec=Cipher(algorithms.AES(key),modes.CBC(b[:16])).decryptor();raw=dec.update(b[16:])+dec.finalize();u=PKCS7(128).unpadder()
    return json.loads(u.update(raw)+u.finalize())
def capture_index(meeting,shell):
    j=decode_index(request(INDEX+'?t='+str(int(time.time())),True),shell)
    captured=now()
    for r in meeting['races']:
        off=datetime.fromisoformat(r['off'])
        if r.get('locked') or not (off-timedelta(minutes=3)<=captured<off) or r['index']['status']=='ready':continue
        rid=meeting['date'].replace('-','')+'-'+meeting['venue']+f'-{r["race"]:02}'
        rows=j.get('index_top4_by_race',{}).get(rid,[])
        if not rows:
            line=j.get('index_w_by_race',{}).get(rid,'')
            rows=[{'no':int(n),'name':name} for n,name in re.findall(r'(\d+)\.([^\s]+)',line)]
        if len(rows)!=4:continue
        r['index']={'status':'ready','horses':safe_horses(rows,r),'captured_at':captured.isoformat(),'source':INDEX,'source_updated_at':j.get('updated_at'),'raceid':rid}
        choose(r)

def parse_dividends(table,require_qp=True):
    if table is None:raise ValueError('Official dividends not published')
    names={'獨贏':'W','位置':'P','連贏':'Q','位置Q':'QP','WIN':'W','PLACE':'P','QUINELLA':'Q','QUINELLAPLACE':'QP'}
    found={};current=None
    for tr in table.select('tr'):
        c=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
        if len(c)==3:
            current=names.get(re.sub(r'\s+','',c[0]).upper());combination,amount=c[1:]
        elif len(c)==2 and current:combination,amount=c
        else:continue
        if not current:continue
        try:value=float(amount.replace(',','').replace('$',''))
        except ValueError:continue
        if value>=0 and re.fullmatch(r'\d+(?:\s*[,，]\s*\d+)*',combination):found.setdefault(current,[]).append({'combination':combination,'dividend_hkd':value})
    if not all(found.get(k) for k in (('W','P','Q','QP') if require_qp else ('W','P','Q'))):raise ValueError('Official W/P/Q/QP dividends incomplete')
    return found

def official_result(m,r):
    q=urllib.parse.urlencode({'racedate':m['date'].replace('-','/'),'Racecourse':m['venue'],'RaceNo':r['race']})
    url='https://racing.hkjc.com/zh-hk/local/information/archive/localresults?'+q
    soup=BeautifulSoup(request(url),'html.parser');table=soup.select_one('.performance tbody')
    if not table:raise ValueError('Official result not published')
    body=soup.get_text(' ',strip=True)
    declared=re.search(r'賽事日期\s*[：:]\s*(\d{1,2})/(\d{1,2})/(\d{4})',body)
    actual_date=f'{int(declared[3]):04}-{int(declared[2]):02}-{int(declared[1]):02}' if declared else None
    actual_race=re.search(r'第\s*(\d+)\s*場',body)
    if actual_date!=m['date'] or not actual_race or int(actual_race[1])!=r['race']:raise ValueError('Official result selected date/race not verified')
    rows=[]
    for tr in table.select('tr'):
        c=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
        if len(c)>=3 and re.match(r'^\d+',c[0]) and c[1].isdigit():rows.append({'placing':c[0],'no':int(c[1]),'name':c[2].split('(')[0].strip()})
    if len(rows)<4 or not rows[0]['placing'].startswith('1'):raise ValueError('Top four incomplete')
    # Names from the date-validated declared field are stable across language variants.
    field={h['no']:h['name'] for h in r['horses']}
    for h in rows[:4]:
        if h['no'] not in field:raise ValueError('Official result field mismatch')
        h['name']=field[h['no']]
    dividends=parse_dividends(soup.select_one('.dividend_tab table'),require_qp=len(r['horses'])>=7)
    withdrawn=[]
    for tr in table.select('tr'):
        c=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
        if len(c)>=2 and c[1].isdigit() and ('退出' in c[0] or c[0].upper() in ('WV','WX','WD')):withdrawn.append(int(c[1]))
    return {'horses':rows[:4],'source':url,'captured_at':stamp(),'verified_date':actual_date,'verified_race':int(actual_race[1]),'dividends':dividends,'pool_status':{k:('settled' if dividends.get(k) else 'not_offered') for k in ('W','P','Q','QP')},'dividend_unit':'HKD per $10 stake, including principal','withdrawn':withdrawn}
class Store:
    def __init__(self,path,publish=False):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True);self.publish=publish
    def read(self,name,default=None):
        p=self.path/name;return json.loads(p.read_text()) if p.exists() else default
    def write(self,name,j):
        p=self.path/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
    def save(self,m):
        m['updated_at']=stamp();self.write(m['date']+'.json',m);self.write('latest.json',m)
        hist=self.read('history.json',{'meetings':[]});row={'date':m['date'],'venue':m['venue'],'status':m['status'],'complete':all(r['result'] for r in m['races'])}
        if m['status']=='archived':
            hist['meetings']=[x for x in hist['meetings'] if x['date']!=m['date']]+[row];hist['meetings'].sort(key=lambda x:x['date'],reverse=True);self.write('history.json',hist)
        if self.publish:self.push()
    def push(self):
        root=self.path.parent
        def git(*args,check=True):return subprocess.run(['git',*args],cwd=root,check=check,capture_output=True,text=True)
        git('add',self.path.name)
        if git('diff','--cached','--quiet',check=False).returncode==0:return
        git('commit','-m','Save expert tips and race records [skip ci]')
        for attempt in range(3):
            if git('push','origin','HEAD:tips-data',check=False).returncode==0:return
            git('pull','--rebase','origin','tips-data');time.sleep(2)
        raise RuntimeError('Could not publish data branch')

def initialize(store):
    old=store.read('latest.json')
    if old and old['date']==now().date().isoformat() and now()<datetime.fromisoformat(old['races'][-1]['off'])+timedelta(hours=1):return old
    c=calendar()
    if c['date']<now().date().isoformat():raise ValueError('Official calendar is stale')
    m=store.read(c['date']+'.json') or empty_meeting(c)
    if not old or old['date']!=m['date']:store.save(m)
    return m

def dispatch(store):
    m=initialize(store);first=datetime.fromisoformat(m['races'][0]['off']);last=datetime.fromisoformat(m['races'][-1]['off']);t=now()
    modes=[]
    if first-timedelta(minutes=160)<=t<first-timedelta(minutes=110) and not m['tips_checked_at']:modes.append('tips')
    if first-timedelta(minutes=40)<=t<last+timedelta(minutes=30) and m['status']!='archived':modes.append('live')
    if not modes:return
    repo=os.environ['GITHUB_REPOSITORY'];token=os.environ['GH_TOKEN'];workflow='expert-tips-run.yml'
    def gh(path,payload=None):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+'/'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'},method='POST' if payload is not None else 'GET')
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read()) if r.status!=204 else None
    runs=gh('actions/workflows/'+workflow+'/runs?per_page=100')['workflow_runs']
    for mode in modes:
        name=f'Expert Tips {m["date"]} · {mode}'
        matches=[r for r in runs if r.get('display_title')==name]
        if any(r['status'] in ('queued','in_progress','waiting','pending') or r.get('conclusion')=='success' for r in matches):continue
        if len(matches)>=3:continue
        gh('actions/workflows/'+workflow+'/dispatches',{'ref':'main','inputs':{'date':m['date'],'mode':mode}})
        print('Dispatched',name)

def collect_manual(m):
    """One bounded source pass. Never revise any race that has started."""
    started=stamp();candidate=copy.deepcopy(m)
    candidate['tips_checked_at']=None
    candidate['races']=[r for r in candidate['races'] if not r.get('locked') and now()<datetime.fromisoformat(r['off'])]
    for r in candidate['races']:
        r['tips']={k:{'status':'pending','horses':[]} for k in ['meiji',*EXPERTS]}
    if candidate['races']:collect_tips(candidate)
    errors=[]
    for fresh in candidate['races']:
        r=next(r for r in m['races'] if r['race']==fresh['race'])
        if r.get('locked') or now()>=datetime.fromisoformat(r['off']):continue
        for key,tip in fresh['tips'].items():
            if tip['status'] in ('ready','absent'):r['tips'][key]=tip
            else:
                errors.append({'race':r['race'],'source':key,'status':tip['status'],'source_date':tip.get('source_date'),'error':tip.get('error')})
                if r['tips'][key]['status'] not in ('ready','absent'):r['tips'][key]=tip
        choose(r)
    if any(not r.get('locked') and datetime.fromisoformat(r['off'])-timedelta(minutes=3)<=now()<datetime.fromisoformat(r['off']) and r['index']['status']!='ready' for r in m['races']):
        try:capture_index(m,request('https://66888.hk/raceid/'+m['date'].replace('-','')+'-'+m['venue']+'-01'))
        except Exception as e:errors.append({'source':'index','error':str(e)})
    for r in m['races']:
        if now()>=datetime.fromisoformat(r['off'])+timedelta(minutes=3) and (not r['result'] or not r['result'].get('dividends')):
            try:r['result']=official_result(m,r)
            except Exception as e:errors.append({'race':r['race'],'source':'result','error':str(e)})
    capture_four(m,request,stamp,now)
    m['manual_checked_at']=stamp()
    m.setdefault('manual_checks',[]).append({'started_at':started,'finished_at':m['manual_checked_at'],'errors':errors})

def run(store,date,mode):
    if date=='latest':date=(store.read('latest.json') or {})['date']
    m=store.read(date+'.json')
    if not m:raise ValueError('Meeting not initialized')
    if mode=='manual':
        if (store.read('latest.json') or {}).get('date')!=date:raise ValueError('Manual collection is restricted to the latest meeting')
        collect_manual(m);store.save(m);return
    due=datetime.fromisoformat(m['tips_due_at'])
    if mode=='tips':
        while now()<due:time.sleep(min(20,max(0,(due-now()).total_seconds())))
        if now()>=datetime.fromisoformat(m['races'][0]['off']):raise ValueError('Tips cutoff missed; refusing post-race collection')
        collect_tips(m);store.save(m);return
    shell=None;end=time.monotonic()+335*60;last_publish=0;result_try={};calendar_try={};four_try=0
    while time.monotonic()<end:
        cycle_start=time.monotonic();t=now();changed=False;m['heartbeat']=t.isoformat();m['status']='live'
        if any(datetime.fromisoformat(r['off'])-timedelta(minutes=3)<=t<datetime.fromisoformat(r['off']) and r['index']['status']!='ready' for r in m['races']):
            try:
                if not shell:shell=request('https://66888.hk/raceid/'+date.replace('-','')+'-'+m['venue']+'-01')
                before=json.dumps([r['index'] for r in m['races']]);capture_index(m,shell);changed|=before!=json.dumps([r['index'] for r in m['races']]);m['index_error']=None
            except Exception as e:m['index_error']=str(e)
        if m['venue']=='ST' and time.monotonic()-four_try>=90:
            four_try=time.monotonic()
            capture_four(m,request,stamp,now)
            t=now()
        # Respect single preflight check. Live mode never silently fetches the experts again.
        for r in m['races']:
            off=datetime.fromisoformat(r['off']);n=r['race']
            if not r['locked'] and off-timedelta(minutes=6)<=t<off and time.monotonic()-calendar_try.get(n,0)>60:
                calendar_try[n]=time.monotonic()
                try:
                    q=urllib.parse.urlencode({'racedate':m['date'].replace('-','/'),'Racecourse':m['venue'],'RaceNo':n});fresh=parse_card(request(CARD+'?'+q))
                    if (fresh['date'],fresh['venue'],fresh['race'])==(m['date'],m['venue'],n):
                        if fresh['off']!=r['off']:r['off']=fresh['off'];off=datetime.fromisoformat(r['off']);changed=True
                        r['horses']=fresh['horses'];r['scratched']=fresh.get('scratched',[])
                        if m['venue']=='ST':
                            from sha_tin_four import choose_four
                            r['sha_tin_four']=choose_four(r)
                except Exception as e:r['schedule_error']=str(e)
            if t>=off and not r['locked']:
                r['locked']=True;r['locked_at']=stamp();changed=True
                if r['index']['status']!='ready':r['index']['status']='missed'
            if t>=off+timedelta(minutes=3) and not r['result'] and time.monotonic()-result_try.get(n,0)>=60:
                result_try[n]=time.monotonic()
                try:r['result']=official_result(m,r);r.pop('result_error',None);changed=True
                except Exception as e:r['result_error']=str(e)
        last=datetime.fromisoformat(m['races'][-1]['off'])
        if all(r['result'] for r in m['races']) or t>=last+timedelta(minutes=45):m['status']='archived';store.save(m);return
        if changed or time.monotonic()-last_publish>=60:store.save(m);last_publish=time.monotonic()
        time.sleep(max(0,20-(time.monotonic()-cycle_start)))
    m['status']='archived' if now()>=datetime.fromisoformat(m['races'][-1]['off'])+timedelta(minutes=3) else 'interrupted';store.save(m)

def reconcile(store):
    for path in store.path.glob('20??-??-??.json'):
        m=store.read(path.name)
        if not (now()-timedelta(days=3)).date().isoformat()<=m['date']<=now().date().isoformat():continue
        changed=False
        for r in m['races']:
            if (not r['result'] or not r['result'].get('dividends')) and now()>=datetime.fromisoformat(r['off'])+timedelta(minutes=3):
                try:r['result']=official_result(m,r);changed=True
                except Exception:pass
        if changed:
            m['status']='archived';store.write(path.name,m)
            hist=store.read('history.json',{'meetings':[]});hist['meetings']=[x for x in hist['meetings'] if x['date']!=m['date']]+[{'date':m['date'],'venue':m['venue'],'status':'archived','complete':all(r['result'] for r in m['races'])}];hist['meetings'].sort(key=lambda x:x['date'],reverse=True);store.write('history.json',hist)
            if (store.read('latest.json') or {}).get('date')==m['date']:store.write('latest.json',m)
    if store.publish:store.push()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['bootstrap','dispatch','run','reconcile','backfill-four']);p.add_argument('--data',default='tips-board/data');p.add_argument('--publish',action='store_true');p.add_argument('--date');p.add_argument('--mode',choices=['tips','live','manual']);a=p.parse_args();s=Store(a.data,a.publish)
    if a.command=='bootstrap':print(json.dumps(initialize(s),ensure_ascii=False)[:500])
    elif a.command=='dispatch':dispatch(s)
    elif a.command=='reconcile':reconcile(s)
    elif a.command=='backfill-four':
        from sha_tin_four import backfill_four
        paths=[s.path/(a.date+'.json')] if a.date else sorted(s.path.glob('20??-??-??.json'))
        for path in paths:
            m=s.read(path.name)
            if m['venue']!='ST' or m.get('status')!='archived':continue
            backfill_four(m,request,stamp);s.write(path.name,m)
            if (s.read('latest.json') or {}).get('date')==m['date']:s.write('latest.json',m)
            print(m['date'],sum(r.get('sha_tin_four',{}).get('status')=='ready' for r in m['races']),'/',len(m['races']),flush=True)
        if s.publish:s.push()
    else:run(s,a.date,a.mode)
