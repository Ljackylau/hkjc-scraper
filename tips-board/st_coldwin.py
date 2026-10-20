"""Public tip/form support for the adopted ST turf confidence Win add-on.

No race-day results, odds, ratings or private prediction models are read.
The browser applies the price filter before taking the first two candidates.
"""
import concurrent.futures,re,statistics,urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

METHOD='st-turf-coldwin-v1'
AUTHORS=('西門獨','諸葛數','陳志懷','兆文')

def parse_authors(body,date):
    text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
    m=re.search(r'賽事日期\s*[：:]\s*(\d{1,2})/(\d{1,2})/(\d{4})',text)
    if not m or f'{int(m[3]):04}-{int(m[2]):02}-{int(m[1]):02}'!=date:raise ValueError('Extra tipster meeting date mismatch')
    heads=list(re.finditer(r'(\S{2,8})貼士',text));out={}
    for i,h in enumerate(heads):
        if h[1] not in AUTHORS:continue
        block=text[h.end():heads[i+1].start() if i+1<len(heads) else len(text)];races={}
        for r in re.finditer(r'第\s*(\d+)\s*場\s*(.*?)(?=第\s*\d+\s*場|$)',block):
            picks=[{'no':int(n),'name':name} for n,name in re.findall(r'(\d+)\s*([^\d\s]+)',r[2])[:4]]
            if len(picks)!=4 or len({h['no'] for h in picks})!=4:raise ValueError('Extra tipster four picks incomplete')
            races[int(r[1])]=picks
        out[h[1]]=races
    if any(a not in out for a in AUTHORS):raise ValueError('Extra tipster section missing')
    return out

def parse_form(body,ident,before):
    soup=BeautifulSoup(body,'html.parser');head=soup.select_one('table.horseProfile')
    if not head or '('+ident.split('_')[-1]+')' not in head.get_text(' ',strip=True):raise ValueError('Horse identity mismatch')
    tables=[t for t in soup.select('table.bigborder') if all(w in re.sub(r'\s','',t.get_text()) for w in ('實際負磅','沿途走位'))]
    if not tables:
        if '找不到昔日的比賽資料' in soup.get_text(' ',strip=True):return {'status':'ready','style_n':0,'median':None,'last_date':None,'last_finish':None}
        raise ValueError('Official dated horse history missing')
    records=[]
    for tr in tables[0].select('tr'):
        ss=[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)]
        if len(ss)<18 or not re.fullmatch(r'\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})',ss[2]):continue
        day=datetime.strptime(ss[2],'%d/%m/%Y' if len(ss[2].split('/')[-1])==4 else '%d/%m/%y').date().isoformat();finish=re.match(r'^\d+',ss[1])
        if not ('2025-09-01'<=day<before) or not finish or not any(v in ss[3] for v in ('跑馬地','沙田')):continue
        records.append({'date':day,'finish':int(finish[0]),'positions':[int(n) for n in re.findall(r'\d+',ss[14])]})
    records.sort(key=lambda x:x['date'],reverse=True);recent=records[:3];early=[x['positions'][0] for x in recent if len(x['positions'])>=2];last=records[0] if records else {}
    return {'status':'ready','last_date':last.get('date'),'last_finish':last.get('finish'),'style_n':len(early),'median':statistics.median(early) if early else None,'recent':recent}

def collect(meeting,request,stamp,now,safe_horses):
    if meeting['venue']!='ST':return
    races=[r for r in meeting['races'] if r.get('track')=='TURF' and not r.get('locked') and (datetime.fromisoformat(r['off'])-now()).total_seconds()>600 and r.get('st_win_support',{}).get('status')!='ready']
    if not races:return
    url='https://racing.on.cc/racing/fav/'+meeting['date'].replace('-','')+'/rjfavf0201x0.html'
    try:authors=parse_authors(request(url),meeting['date'])
    except Exception as exc:
        for r in races:
            if now()<datetime.fromisoformat(r['off']):r['st_win_support']={'method':METHOD,'date':meeting['date'],'venue':'ST','race':r['race'],'status':'error','error':str(exc),'source':url,'captured_at':stamp()}
        return
    jobs=[];prepared={}
    for r in races:
        try:
            tips={a:{'status':'ready','numbers':[h['no'] for h in safe_horses(authors[a][r['race']],r)]} for a in AUTHORS}
            core={h['no'] for h in r['tips']['meiji'].get('horses',[])}|set(r.get('banker_initial',{}).get('numbers',[]));wanted=set(n for t in tips.values() for n in t['numbers'])-core-set(r.get('scratched',[]))
            forms=dict(r.get('st_win_support',{}).get('forms',{}))
            for h in r['horses']:
                if h['no'] in wanted and forms.get(str(h['no']),{}).get('status')!='ready' and len(jobs)<12:jobs.append((r,h))
            prepared[r['race']]={'method':METHOD,'date':meeting['date'],'venue':'ST','race':r['race'],'status':'ready','source':url,'authors':tips,'forms':forms,'wanted':sorted(wanted),'captured_at':stamp()}
        except Exception as exc:prepared[r['race']]={'method':METHOD,'date':meeting['date'],'venue':'ST','race':r['race'],'status':'error','error':str(exc),'source':url,'captured_at':stamp()}
    def one(job):
        r,h=job;ident=h.get('horse_id');source='https://racing.hkjc.com/zh-hk/local/information/horse?'+urllib.parse.urlencode({'HorseId':ident,'Option':1})
        try:
            if not re.fullmatch(r'HK_\d{4}_[A-Z]\d{3}',ident or ''):raise ValueError('Official horse identity unavailable')
            return r['race'],str(h['no']),{**parse_form(request(source),ident,meeting['date']),'horse_id':ident,'source':source,'captured_at':stamp()}
        except Exception as exc:return r['race'],str(h['no']),{'status':'error','error':str(exc),'source':source}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for race,no,form in pool.map(one,jobs):
            prepared[race]['forms'][no]=form
            if form['status']!='ready':prepared[race]['status']='pending'
    for r in races:
        s=prepared[r['race']]
        if s['status']!='error' and any(s['forms'].get(str(n),{}).get('status')!='ready' for n in s['wanted']):s['status']='pending'
        if not r.get('locked') and now()<datetime.fromisoformat(r['off']):r['st_win_support']=prepared[r['race']]
