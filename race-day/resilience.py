"""Bounded source checks and portable, checksummed Horse103 backups."""
import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import horse103_copy as horse


def health(date):
    report={'date':date,'checked_at':datetime.now(timezone.utc).isoformat(),'source':'103.plus','checks':{}}
    races=[]
    def check(name,fn):
        try:
            detail=fn()
            report['checks'][name]={'ok':True,'detail':detail}
        except Exception as e:
            report['checks'][name]={'ok':False,'error':str(e)[:250]}
    def schedule():
        races.extend(horse.get_races(date))
        if not races:raise ValueError('No races for selected date; not necessarily a source outage')
        for r in races:
            horse.hk_datetime(date,r['post_time'])
            if not r.get('id'):raise ValueError('Missing race ID')
        return {'race_count':len(races)}
    check('schedule',schedule)
    if races:
        def live():
            x=horse.request('/functions/v1/live103-decision',{'raceId':races[0]['id']})
            horse.parse_utc(x['lockTime'])
            if not isinstance(x.get('candidates'),list):raise ValueError('Missing candidates list')
            return {'phase':x.get('phase'),'dataQuality':x.get('dataQuality'),'lockTime':x['lockTime'],'note':'Connectivity/schema check only; not a T−3 capture'}
        check('live_schema',live)
        check('entries',lambda:{'count':len(horse.get_entries(races[0]['id']))})
    def tickets():
        rows=horse.rest('smart_money_tickets',{'select':'id,race_id,bet_type,scraped_at,amount,horse_or_combo','race_date':f'eq.{date}','limit':'1'})
        return {'sample_count':len(rows),'note':'An empty sample is allowed before betting starts'}
    check('tickets_schema',tickets)
    report['ok']=all(c['ok'] for c in report['checks'].values())
    return report


def archive(root,output):
    root=Path(root);output=Path(output)
    files=sorted(p for p in root.rglob('*.json') if p.is_file() and
                 ('horse103' in p.relative_to(root).parts or p.name in ('status.json','source-health.json','plan.json')))
    if not files:raise RuntimeError('No Horse103 backup files found')
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'files':{}}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            data=p.read_bytes();name=p.relative_to(root).as_posix()
            manifest['files'][name]=hashlib.sha256(data).hexdigest()
            z.writestr(name,data)
        z.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
    print(f'Backup: {len(files)} files, {output.stat().st_size} bytes')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    h=sub.add_parser('health');h.add_argument('--date',required=True);h.add_argument('--output',required=True)
    a=sub.add_parser('archive');a.add_argument('--root',required=True);a.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='archive':archive(args.root,args.output)
    else:
        result=health(args.date);dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
