"""Recover official race results and dividends independently of the live runner."""
import argparse
import concurrent.futures
import json
from datetime import datetime, timedelta
from pathlib import Path

from runner import HK, atomic, fetch_official_result


def archived_cold(day, number, phase):
    """Recover only a signal based on source data received before race off."""
    folder=day/('hkjc-early' if phase=='early' else 'hkjc-late')
    signal_path=folder/'challenge'/f'race_{number:02d}_tnc_signal.json'
    t3_path=folder/f'race_{number:02d}_t3.json'
    status_path=folder/'status.json'
    if not all(p.exists() for p in (signal_path,t3_path,status_path)):
        return None
    signal=json.loads(signal_path.read_text());t3=json.loads(t3_path.read_text())
    race=json.loads(status_path.read_text()).get('races',{}).get(str(number),{})
    if signal.get('status')!='observed' or not race.get('ranking') or not race.get('target'):
        return None
    try:
        off=datetime.fromisoformat(race['target'])+timedelta(minutes=3)
        if datetime.fromisoformat(t3['received_at'])>off or datetime.fromisoformat(signal['t3_received_at'])>off:
            return None
    except (ValueError,KeyError,TypeError):
        return None
    trainers={''.join(str(x['name']).split()) for x in signal.get('qualifying',[])}
    trainer_by_horse={int(row[0]):''.join(str(row[6]).split()) for row in t3.get('runner_rows',[]) if len(row)>6}
    return list(dict.fromkeys(int(row['horse_number']) for row in race['ranking'][:5]
                              if trainer_by_horse.get(int(row['horse_number'])) in trainers))


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
            if 'cold' in sent:
                result['cold']=[int(x) for x in sent['cold']]
                result['cold_source']='saved_tip'
        if 'cold' not in result:
            recovered=archived_cold(day,number,folder.name)
            result['cold']=recovered
            if recovered is not None:result['cold_source']='archived_preoff_reconstruction'
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
