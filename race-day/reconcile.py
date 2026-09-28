"""Recover official race results and dividends independently of the live runner."""
import argparse
import concurrent.futures
import json
from datetime import datetime, timedelta
from pathlib import Path

from runner import HK, atomic, fetch_official_result


def reconcile(date, root, workers=4):
    day=root/date
    if not day.is_dir():
        print(f'No archived meeting for {date}')
        return {'found': 0, 'complete': 0, 'failed': []}
    source={}
    for phase in ('early','late','recovery'):
        folder=day/phase
        status=folder/'status.json'
        if status.exists():
            for number in json.loads(status.read_text()).get('horse103',{}):
                source.setdefault(int(number),folder)
    if not source:
        print(f'No archived races for {date}')
        return {'found':0,'complete':0,'failed':[]}
    destination=day/'settlement';destination.mkdir(exist_ok=True)
    meeting_venue=None
    for number,folder in sorted(source.items()):
        path=folder/'horse103'/f'race_{number:02d}.json'
        if path.exists():
            meeting_venue=json.loads(path.read_text()).get('race',{}).get('venue')
            if meeting_venue:break
    def one(item):
        number,folder=item
        path=destination/f'race_{number:02d}.json'
        if path.exists():
            saved=json.loads(path.read_text())
            if saved.get('settlement_status')=='complete':return number,None
        snapshot=folder/'horse103'/f'race_{number:02d}.json'
        tip=folder/'notifications'/f'race_{number:02d}.json'
        archive=folder/'results'/f'race_{number:02d}.json'
        race=json.loads(snapshot.read_text()).get('race',{}) if snapshot.exists() else {}
        if not race and archive.exists():
            old=json.loads(archive.read_text())
            race={'venue':'ST' if 'Racecourse=ST' in old.get('source_url','') else 'HV'}
        venue=race.get('venue') or meeting_venue
        if not venue:return number,'Venue missing from archived race'
        result=fetch_official_result(date,venue,number)
        result.update(date=date,race=number)
        if snapshot.exists():
            snap=json.loads(snapshot.read_text())
            result['banker']=int(snap['ranking'][0]['horse_number'])
            original={int(x['horseNumber']) for x in snap.get('live103_raw',{}).get('candidates',[]) if x.get('horseNumber') is not None}
            result['additional_picks']=[int(x['horse_number']) for x in snap['ranking'][1:5] if int(x['horse_number']) not in original]
        if tip.exists():
            sent=json.loads(tip.read_text());result['legs']=[int(x) for x in sent['market']] if 'market' in sent else None
            result['tip_sent_at']=sent.get('sent_at')
        atomic(path,result)
        return number,None
    failed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(one,item):item[0] for item in sorted(source.items())}
        for future in concurrent.futures.as_completed(futures):
            number=futures[future]
            try:_,error=future.result()
            except Exception as exc:error=str(exc)[:250]
            if error:failed.append({'race':number,'error':error})
    report={'date':date,'found':len(source),'complete':len(source)-len(failed),'failed':sorted(failed,key=lambda x:x['race']),'checked_at':datetime.now(HK).isoformat()}
    atomic(destination/'status.json',report)
    print(json.dumps(report,ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--date',default=(datetime.now(HK)-timedelta(days=1)).date().isoformat())
    parser.add_argument('--data-root',type=Path,required=True)
    args=parser.parse_args()
    report=reconcile(args.date,args.data_root)
    # The next scheduled run may retry missing races. A report never invents results.
