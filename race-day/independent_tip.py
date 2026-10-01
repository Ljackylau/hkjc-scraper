"""Freeze independent banker + existing market legs before T-3."""
import asyncio
import json
from datetime import datetime, timedelta
from independent_candidate import pick, dt
from runner import atomic, now, telegram_configured, telegram_send


def prepare(samples,off,date,number,baseline=None,golden=None):
    cutoff=off-timedelta(minutes=3);freeze=cutoff-timedelta(seconds=10)
    common={'date':date,'race':number,'off':off.isoformat(),'freeze':freeze.isoformat(),
            'method':'independent_hybrid_v1','cutoff':cutoff.isoformat()}
    ordered=sorted((s for s in samples if s.get('post_time')==off.strftime('%H:%M')),key=lambda s:dt(s['received_at']))
    def fresh(s,at,age):
        return dt(s['received_at'])<=at and all(0<=(at-dt(s['source_updated'][k])).total_seconds()<=age for k in ('wp','wpq'))
    bases=[s for s in ordered if fresh(s,off-timedelta(minutes=10),180)]
    ends=[s for s in ordered if fresh(s,freeze,120)]
    if not bases or not ends:return {**common,'status':'unavailable','reason':'Missing fresh T-10 or pre-T-3 full-field HKJC quotes'}
    try:
        decision=pick(ends[-1],bases[-1],cutoff,baseline)
        from hkjc_shadow import movement
        # Preserve the existing market ranking method. Only remove the new
        # banker; never depend on Horse103 to remove a previous banker.
        market=[r['horse_number'] for r in movement(baseline,ends[-1])[:5]] if baseline else []
        gold=list(golden or [])
        legs=[h for h in dict.fromkeys(gold+market) if h!=decision['banker']]
        rows=ends[-1].get('runner_rows',[])
        return {**common,**decision,'date':date,'race':number,'off':off.isoformat(),
                'status':'ready','legs':legs,'market':list(dict.fromkeys(gold+market)),
                'golden':[h for h in gold if h!=decision['banker']],
                'legs_status':'ready' if baseline and market else 'unavailable',
                'baseline_received_at':bases[-1]['received_at'],
                'long_baseline_received_at':baseline.get('received_at') if baseline else None,
                'runner_rows':rows,'source_updated':ends[-1]['source_updated']}
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as e:return {**common,'status':'unavailable','reason':str(e)}


def message(number,tip):
    if tip.get('status')!='ready':
        return f'⚠️ R{number}｜新方法 T−3 資料不足\n{tip.get("reason","未能取得有效快照")}\n未以較遲資料補作賽前推介。'
    main=tip['banker'];legs='、'.join(f'{h}號' for h in tip['legs']) if tip['legs_status']=='ready' else '資料未就緒'
    return (f'🏇 R{number}\n獨贏&位置信心馬：{main}號\n'
            f'連贏位置Q：{main}號 拖 {legs or "無"}\n最有可能爆冷馬：'
            +cold_text(tip))


def cold_text(tip):
    if tip.get('cold_status')!='ready':return '無法判定：'+tip.get('cold_reason','缺有效報價')
    value='、'.join(f'{h}號' for h in tip.get('cold',[])) or '無'
    age=tip.get('cold_quote_age_seconds',0)
    return value+(f'（報價較舊：{round(age)}秒）' if age>120 else '')


async def notify(number,tip,folder):
    marker=folder/f'race_{number:02d}_independent_notification.json'
    if marker.exists():
        prior=json.loads(marker.read_text())
        if prior.get('status')=='sent':return
    cutoff=dt(tip['cutoff'])
    while now()<cutoff:await asyncio.sleep(min(1,(cutoff-now()).total_seconds()))
    if not telegram_configured():
        atomic(marker,{'status':'not_configured','at':now().isoformat(),'race':number});return
    for attempt in range(3):
        try:
            await asyncio.to_thread(telegram_send,message(number,tip))
            atomic(marker,{'status':'sent','sent_at':now().isoformat(),'race':number,'cutoff':tip['cutoff'],
                           'send_delay_seconds':round((now()-cutoff).total_seconds(),2),'message':message(number,tip)})
            return
        except Exception as e:
            # Never include request URLs / credentials in logs or public markers.
            atomic(marker,{'status':'retrying','at':now().isoformat(),'race':number,'error_type':type(e).__name__})
            if attempt<2:await asyncio.sleep(2)


def cold_signal(tip,folder,number,clocks=None,states=None):
    tip['cold']=[];tip['cold_status']='unavailable';tip['cold_policy']='post_previous_off_max600_v2'
    if number==1:
        tip['cold_status']='ready';return
    path=folder/'challenge'/f'race_{number:02d}_tnc_signal.json'
    try:
        if clocks:
            from challenge_shadow import market_drop_signal,race_context
            history_path=folder/'challenge'/'tnc.jsonl'
            if not history_path.exists():return
            freeze=dt(tip['freeze'])
            history=[json.loads(line) for line in history_path.read_text().splitlines() if line.strip()]
            history=[s for s in history if dt(s['received_at'])<=freeze and s.get('state')=='observed' and s.get('source_updated_at')]
            context=race_context(tip['date'],clocks,states or {},freeze)
            race=next(r for r in context if r['race_number']==number);previous=next(r for r in context if r['race_number']==number-1)
            previous_off=dt(previous['post_time'])
            post=[s for s in history if previous_off<dt(s['source_updated_at'])<=dt(s['received_at'])]
            if not post:
                tip['cold_reason']='上一場後未有更新報價';return
            newest=max(post,key=lambda s:dt(s['source_updated_at']))
            age=round((freeze-dt(newest['source_updated_at'])).total_seconds())
            if age>600:
                tip['cold_reason']=f'練王報價已舊{age}秒；上限600秒';return
            current=[s for s in history if previous_off<dt(s['source_updated_at'])<=dt(s['received_at']) and 0<=(freeze-dt(s['source_updated_at'])).total_seconds()<=600]
            if not current:return
            sample=max(current,key=lambda s:(dt(s['source_updated_at']),dt(s['received_at'])))
            usable=[s for s in history if dt(s['received_at'])<=previous_off or dt(s['source_updated_at'])>previous_off]
            usable=[s for s in usable if dt(s['source_updated_at'])>previous_off or 0<=(previous_off-dt(s['source_updated_at'])).total_seconds()<=600]
            signal=market_drop_signal(usable,sample,race,context)
            tip['cold_received_at']=sample['received_at']
            tip['cold_source_updated_at']=sample['source_updated_at']
            tip['cold_quote_age_seconds']=(freeze-dt(sample['source_updated_at'])).total_seconds()
        elif path.exists():
            signal=json.loads(path.read_text());stamp=signal.get('t3_received_at') or signal.get('received_at') or signal.get('at')
            if not stamp or dt(stamp)>dt(tip['freeze']):return
            source=signal.get('t3_source_updated_at');baseline=signal.get('baseline_source_updated_at')
            if not source or not baseline or not 0<=(dt(tip['freeze'])-dt(source)).total_seconds()<=600:return
            tip['cold_source_updated_at']=source;tip['cold_quote_age_seconds']=(dt(tip['freeze'])-dt(source)).total_seconds()
        else:return
        if signal.get('status')!='observed':
            tip['cold_reason']='缺上一場開跑前的有效比較報價';return
        trainers={''.join(str(r['name']).split()) for r in signal.get('qualifying',[])}
        mapping={int(r[0]):''.join(str(r[6]).split()) for r in tip.get('runner_rows',[])}
        tip['cold']=[h for h in tip.get('market',[])[:5] if mapping.get(h) in trainers]
        tip['cold_status']='ready'
    except (ValueError,KeyError,TypeError):pass
