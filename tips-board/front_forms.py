"""Pre-off, prior-day running-position support for the first-three cover-W policy."""
import concurrent.futures,re,urllib.parse
from datetime import datetime
from st_coldwin import parse_form
METHOD='front-three-starts-v1'
def collect(meeting,request,stamp,now,max_jobs=36):
    races=[r for r in meeting.get('races',[]) if not r.get('locked') and now()<datetime.fromisoformat(r['off'])]
    if not races:return
    prepared={};jobs=[]
    for r in races:
        prior=r.get('front_support',{});forms=dict(prior.get('forms',{})) if prior.get('before_date')==meeting['date'] else {}
        for h in r.get('horses',[]):
            if h['no'] in r.get('scratched',[]):continue
            ident=h.get('horse_id');old=forms.get(str(h['no']),{})
            if old.get('status')=='ready' and old.get('horse_id')==ident:continue
            if len(jobs)<max_jobs:jobs.append((r,h))
        prepared[r['race']]={'method':METHOD,'status':'pending','date':meeting['date'],'before_date':meeting['date'],'venue':meeting['venue'],'race':r['race'],'captured_at':stamp(),'forms':forms}
    def one(job):
        r,h=job;ident=h.get('horse_id');url='https://racing.hkjc.com/zh-hk/local/information/horse?'+urllib.parse.urlencode({'HorseId':ident,'Option':1})
        try:
            if not re.fullmatch(r'HK_\d{4}_[A-Z]\d{3}',ident or ''):raise ValueError('Official horse identity missing')
            form={**parse_form(request(url),ident,meeting['date']),'horse_id':ident,'source':url,'captured_at':stamp()}
            return r['race'],str(h['no']),form
        except Exception as e:return r['race'],str(h['no']),{'status':'error','horse_id':ident,'source':url,'error':str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for race,no,form in pool.map(one,jobs):prepared[race]['forms'][no]=form
    for r in races:
        s=prepared[r['race']];active=[h for h in r.get('horses',[]) if h['no']not in r.get('scratched',[])]
        if all(s['forms'].get(str(h['no']),{}).get('status')=='ready' and s['forms'][str(h['no'])].get('horse_id')==h.get('horse_id') for h in active):s['status']='ready'
        if not r.get('locked') and now()<datetime.fromisoformat(r['off']):r['front_support']=s
