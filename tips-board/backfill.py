"""Read historical archives and reconstruct the fixed rules, with explicit provenance.
Does not change the current meeting or claim a captured pre-race timestamp.
"""
import concurrent.futures,json,re,time,hashlib,argparse
from pathlib import Path
from datetime import datetime
from collector import request,api,HK,empty_meeting,safe_horses,parse_meiji,choose,official_result,stamp,INDEX,EXPERTS,decode_index
CACHE=Path('/tmp/tips-backfill-cache');CACHE.mkdir(exist_ok=True)
def cached(key,getter):
    path=CACHE/(key+'.json')
    if path.exists():return json.loads(path.read_text())
    for attempt in range(3):
        try:
            j=getter();path.write_text(json.dumps(j,ensure_ascii=False));return j
        except Exception:
            if attempt==2:raise
            time.sleep(2+attempt)
def hkdate(s):return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(HK).date().isoformat()
def archive_sources(day):
    date=hkdate(day['date']);compact=date.replace('-','');url='https://racing.on.cc/racing/fav/'+compact+'/rjfavf0201x0.html'
    try:
        body=cached('oncc-'+compact,lambda:request(url));d,tips=parse_meiji(body,date)
        if d!=date:raise ValueError('Wrong archive date')
        on={'source':url,'source_date':d,'horses_by_race':tips,'sha256':hashlib.sha256(body.encode()).hexdigest()}
    except Exception as e:on={'error':str(e),'source':url}
    try:st=cached('experts-'+compact,lambda:api('/raceDay/expertTips',date=compact))
    except Exception as e:st={'error':str(e)}
    return on,st

def one(day,meta,on,experts,indices):
    date=hkdate(day['date']);n=meta['raceNo'];compact=date.replace('-','');errors=[]
    try:
        entry=cached(f'entry-{compact}-{n}',lambda:api('/raceEntry',date=compact,raceNo=n))
        if hkdate(entry['raceDate'])!=date or entry['raceNo']!=n or entry['raceVenue']!=day['raceVenue']:raise ValueError('Historical declaration date/race/venue mismatch')
        field=[{'no':int(x['horseNo']),'name':x['horse']['name']} for x in entry['raceEntries'] if int(x.get('horseNo',0))>0 and not x.get('standby')]
        lookup={x['jcIdHorse']:x for x in entry['raceEntries'] if int(x.get('horseNo',0))>0 and not x.get('standby')}
        off=datetime.fromisoformat(meta['startTime'].replace('Z','+00:00')).astimezone(HK).isoformat()
        r=empty_meeting({'date':date,'venue':day['raceVenue'],'races':[{'date':date,'venue':day['raceVenue'],'race':n,'off':off,'horses':sorted(field,key=lambda h:h['no'])}]})['races'][0]
        r['record_type']='historical_backfill';r['backfilled_at']=stamp()
        if on.get('error'):r['tips']['meiji']={'status':'error','horses':[],'error':on['error'],'source':on['source']}
        else:
            hs=on['horses_by_race'].get(str(n),on['horses_by_race'].get(n,[]))
            try:r['tips']['meiji']={'status':'ready' if len(hs)==4 else 'error','horses':safe_horses(hs,r),'source':on['source'],'source_date':date,'captured_at':stamp(),'record_type':'historical_backfill','source_sha256':on['sha256']}
            except Exception as e:r['tips']['meiji']={'status':'error','horses':[],'error':str(e),'source':on['source']}
        for key,name in EXPERTS.items():
            try:
                if isinstance(experts,dict):raise ValueError(experts['error'])
                expert=next((x for x in experts if x['expert']['name']==name),None)
                if expert is None:raise ValueError('Expert record not found')
                tip=next((t for t in expert['tipsList'] if int(t['raceNo'])==n),None)
                if tip is None:raise ValueError('Expert race record not found')
                items=[]
                for i in range(1,5):
                    ident=tip.get('jcIdHorse'+str(i))
                    if not ident:continue
                    x=lookup.get(ident)
                    if x is None:raise ValueError('Tip horse not in historical declaration')
                    items.append({'no':x['horseNo'],'name':x['horse']['name']})
                r['tips'][key]={'status':'ready' if items else 'absent','horses':safe_horses(items,r),'source':'https://racing.stheadline.com/api/raceDay/expertTips?date='+compact,'source_date':date,'captured_at':stamp(),'record_type':'historical_backfill'}
            except Exception as e:r['tips'][key]={'status':'error','horses':[],'error':str(e)}
        rid=compact+'-'+day['raceVenue']+f'-{n:02}'
        rows=indices.get('index_top4_by_race',{}).get(rid,[])
        if not rows:rows=[{'no':int(a),'name':b} for a,b in re.findall(r'(\d+)\.([^\s]+)',indices.get('index_w_by_race',{}).get(rid,''))]
        if len(rows)!=4:
            try:
                url='https://data.66888.hk/runtime/board_pack/'+rid+'.json'
                pack=cached('board-'+rid,lambda:decode_index(request(url,True),request('https://66888.hk/board')))
                ai=pack.get('race_ai',{})
                if pack.get('raceid')==rid and ai.get('meeting_date')==date and ai.get('venue')==day['raceVenue'] and int(ai.get('race_no',0))==n and len(ai.get('index_top4',[]))==4:
                    rows=ai['index_top4'];indices.setdefault('archive_provenance',{})[rid]={'source':url,'reported_live_created_at':ai.get('live_created_at'),'pack_generated_at':pack.get('generated_at')}
            except Exception:pass
        if len(rows)==4:
            try:r['index']={'status':'ready','horses':safe_horses(rows,r),'raceid':rid,'source':indices.get('archive_provenance',{}).get(rid,{}).get('source',INDEX),'captured_at':stamp(),'record_type':'historical_backfill','source_updated_at':indices.get('updated_at'),**indices.get('archive_provenance',{}).get(rid,{})}
            except Exception as e:r['index']={'status':'error','horses':[],'error':str(e)}
        else:r['index']={'status':'historical_missing','horses':[],'source':INDEX,'raceid':rid}
        reported=r['index'].get('reported_live_created_at')
        if reported:
            try:
                relation=(datetime.fromisoformat(reported).replace(tzinfo=HK)-datetime.fromisoformat(off)).total_seconds()
                r['index']['reported_seconds_from_advertised_off']=relation
                r['index']['timing_note']='來源標示時間在公布開跑時間之後，非已驗證T−2快照' if relation>=0 else '歷史來源標示時間；未驗證T−2發佈版本'
            except ValueError:r['index']['timing_note']='歷史來源時間未能解析'
        elif r['index']['status']=='ready':r['index']['timing_note']='歷史存檔；未保存該場T−2取得時間'
        choose(r)
        if r['selection']:r['selection']['reconstructed']=True
        r['locked']=True;r['lock_type']='historical_reconstruction'
        try:r['result']=cached(f'result-{compact}-{n}',lambda:official_result({'date':date,'venue':day['raceVenue']},r))
        except Exception as e:r['result_error']=str(e)
        return r
    except Exception as e:return {'race':n,'failed':str(e)}

def main(destination):
    days=cached('meetings',lambda:api('/raceDay',limit=100));indices=cached('index',lambda:decode_index(request(INDEX+'?t='+str(int(time.time())),True),request('https://66888.hk/board')))
    days=[d for d in days if '2026-09-01'<=hkdate(d['date'])<=datetime.now(HK).date().isoformat()]
    out=Path(destination);out.mkdir(exist_ok=True,parents=True);summaries=[]
    for day in sorted(days,key=lambda d:d['date']):
        date=hkdate(day['date']);print('Fetching',date,day['numOfRace'],'races',flush=True);on,experts=archive_sources(day)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as p:
            races=list(p.map(lambda meta:one(day,meta,on,experts,indices),day['races']))
        bad=[r for r in races if r.get('failed')]
        if bad:print('FAILED',bad,flush=True);raise ValueError('Historical declaration missing; not publishing partial rows')
        meeting={'date':date,'venue':day['raceVenue'],'source':'https://racing.stheadline.com/api/raceDay?date='+date.replace('-',''),'status':'archived','record_type':'historical_backfill','backfilled_at':stamp(),'updated_at':stamp(),'tips_checked_at':None,'tips_due_at':None,'heartbeat':None,'errors':[],'races':sorted(races,key=lambda r:r['race']),
        'notice':'歷史補錄：按來源現存日期存檔重建，並非當日即時保存；沒有驗證賽前發佈版本；部分指數來源時間在公布開跑時間之後，不能視作T−2實盤回測。缺失指數馬不會用其他AI選馬代替。'}
        (out/(date+'.json')).write_text(json.dumps(meeting,ensure_ascii=False,indent=2)+'\n')
        summary={'date':date,'venue':day['raceVenue'],'status':'archived','complete':all(r['result'] for r in races),'record_type':'historical_backfill','races':len(races),'meiji':sum(len(r['tips']['meiji']['horses'])==4 for r in races),'index':sum(len(r['index']['horses'])==4 for r in races),'results':sum(bool(r['result']) for r in races),'scored':sum(r['score'] is not None for r in races),'selections':sum(r['selection'] is not None for r in races)}
        summaries.append(summary);print('Saved',summary,flush=True)
    (out/'history.json').write_text(json.dumps({'meetings':sorted(summaries,key=lambda x:x['date'],reverse=True)},ensure_ascii=False,indent=2)+'\n')
    print('DONE',json.dumps(summaries,ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',default='/tmp/tips-history-records');a=p.parse_args();main(a.destination)
