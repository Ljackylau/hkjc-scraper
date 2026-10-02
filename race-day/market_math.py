"""Pure pre-cutoff market features; no results or final-odds inputs."""
from datetime import datetime
import itertools,math

def numeric(vals):
    return {str(k):float(v) for k,v in vals.items()
            if str(v).replace('.','',1).isdigit() and float(v)>0}

def normalized_inverse(vals):
    vals=numeric(vals);z=sum(1/v for v in vals.values())
    return {h:1/v/z for h,v in vals.items()}

def expected(w,pool):
    if pool=='FCT':
        return {f'{h}-{g}':w[h]*w[g]/(1-w[h]) for h in w for g in w if h!=g}
    out={ '-'.join(sorted([h,g],key=int)):w[h]*w[g]*(1/(1-w[h])+1/(1-w[g]))
          for h,g in itertools.combinations(w,2)}
    if pool=='QIN':return out
    out={k:0 for k in out}
    for h,g,j in itertools.permutations(w,3):
        p=w[h]*w[g]/(1-w[h])*w[j]/(1-w[h]-w[g])/3
        for a,b in [(h,g),(h,j),(g,j)]:out['-'.join(sorted([a,b],key=int))]+=p
    return out

def mass_bounds(odds,keys):
    keys=set(keys);A=sum(1/v for v in odds.values() if v<999)
    C=sum(v>=999 for v in odds.values())
    B=sum(1/v for k,v in odds.items() if k in keys and v<999)
    c=sum(v>=999 for k,v in odds.items() if k in keys)
    lo=B/(A+(C-c)/999);hi=(B+c/999)/(A+c/999)
    return lo,hi

def pool_info(wp,pool,fct=None):
    w=normalized_inverse(wp['odds']['WIN'])
    odds=numeric(fct['odds'] if pool=='FCT' else wp['odds'][pool])
    odds={k:v for k,v in odds.items() if all(h in w for h in k.split('-'))}
    return odds,expected(w,pool)

def validate(pack):
    cut=datetime.fromisoformat(pack['cut']);off=datetime.fromisoformat(pack['off'])
    # The advertised post time used for the cutoff was itself visible in the
    # accepted snapshot, rather than a later unseen schedule correction.
    assert pack['end_wp'].get('post_time')==off.strftime('%H:%M')
    for name,age in [('end_wp',120),('start_q',180)]:
        s=pack[name];rec=datetime.fromisoformat(s['received_at'])
        assert rec<=cut
        for pool in ['wp','wpq']:
            src=datetime.fromisoformat(s['source_updated'][pool])
            assert src<=rec and 0<=(cut-src if name=='end_wp' else rec-src).total_seconds()<=age
    assert 1500<=(off-datetime.fromisoformat(pack['start_q']['received_at'])).total_seconds()<=1920
    for name,age in [('end_fct',120),('start_fct',180)]:
        s=pack.get(name)
        if s is None:continue
        rec=datetime.fromisoformat(s['captured']);src=datetime.fromisoformat(s['source_updated'])
        assert src<=rec<=cut
        assert 0<=(cut-src if name=='end_fct' else rec-src).total_seconds()<=age
    if pack.get('start_fct'):
        f=pack['start_fct'];w=pack['start_fct_wp']
        t=datetime.fromisoformat(f['captured']);r=datetime.fromisoformat(w['received_at']);s=datetime.fromisoformat(w['source_updated']['wp'])
        assert s<=r<=t and 0<=(t-s).total_seconds()<=180
        assert 1500<=(off-t).total_seconds()<=1920

def market_features(pack):
    validate(pack)
    end=pack['end_wp'];start=pack['start_q'];w1=normalized_inverse(end['odds']['WIN']);w0=normalized_inverse(start['odds']['WIN'])
    p1=normalized_inverse(end['odds']['PLA']);p0=normalized_inverse(start['odds']['PLA'])
    order=sorted(w1,key=lambda h:(-w1[h],int(h)));end_infos={};start_infos={}
    for pool in ['QIN','QPL','FCT']:
        end_infos[pool]=pool_info(end,pool,pack['end_fct'])
        if pool=='FCT':
            if pack.get('start_fct'):
                start_infos[pool]=pool_info(pack['start_fct_wp'],pool,pack['start_fct'])
        else:start_infos[pool]=pool_info(start,pool)
    rows=[]
    for h in sorted(w1,key=int):
        if float(end['odds']['WIN'][h])<=10:continue
        r={'horse':int(h),'win_share_gain':w1[h]/w0[h]-1,'place_share_gain':p1[h]/p0[h]-1,
           'win_quote_gain':1-float(end['odds']['WIN'][h])/float(start['odds']['WIN'][h]),
           'place_quote_gain':1-float(end['odds']['PLA'][h])/float(start['odds']['PLA'][h])}
        for pool in ['QIN','QPL','FCT']:
            tag={'QIN':'q','QPL':'qp','FCT':'fct'}[pool];oe,ee=end_infos[pool]
            start_info=start_infos.get(pool)
            for partners_n in [None,1,3,5]:
                partners=set(g for g in order if g!=h)
                if partners_n:partners=set([g for g in order if g!=h][:partners_n])
                for direction in (['both','first','second'] if pool=='FCT' else ['both']):
                    def belongs(k):
                        a,b=k.split('-')
                        return ((a==h and b in partners) if direction=='first' else
                                (b==h and a in partners) if direction=='second' else
                                ((a==h and b in partners) or (b==h and a in partners)))
                    ke=[k for k in oe if belongs(k)];be=mass_bounds(oe,ke);expe=sum(ee[k] for k in ke)
                    suffix=f'{tag}_{direction}_'+('all' if partners_n is None else f'top{partners_n}')
                    r[suffix+'_level_lo']=be[0]/expe;r[suffix+'_level_hi']=be[1]/expe
                    r[suffix+'_cap_width']=(be[1]-be[0])/max(be[1],1e-12)
                    r[suffix+'_mass_growth_lo']=None;r[suffix+'_res_growth_lo']=None
                    if start_info:
                        os,es=start_info;ks=[k for k in os if belongs(k)];bs=mass_bounds(os,ks);exps=sum(es[k] for k in ks)
                        if bs[0]>0 and exps>0:
                            r[suffix+'_mass_growth_lo']=be[0]/bs[1]-1
                            r[suffix+'_res_growth_lo']=(be[0]/expe)/(bs[1]/exps)-1
            if pool!='FCT' and start_info:
                os,_=start_info;vals=[];weights=[]
                for g in order:
                    if g==h:continue
                    k='-'.join(sorted([h,g],key=int))
                    if k in os and k in oe and max(os[k],oe[k])<999:
                        vals.append(math.log(os[k]/oe[k]));weights.append(w1[g])
                r[tag+'_partner_weighted_log_gain']=sum(v*z for v,z in zip(vals,weights))/sum(weights) if weights else None
        for n in [None,1,3,5]:
            t='all' if n is None else f'top{n}'
            first=r[f'fct_first_{t}_level_hi'];second=r[f'fct_second_{t}_level_lo']
            r[f'fct_second_over_first_{t}_lo']=second/first if first>0 else None
            r[f'q_over_fct_first_{t}_lo']=r[f'q_both_{t}_level_lo']/first if first>0 else None
        rows.append(r)
    return rows
