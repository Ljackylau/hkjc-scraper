"""F top two plus two distinct lowest-priced banker QP combinations."""
import math
METHOD='f2_banker_qp2_v1'

def select(banker,scores,qp):
    main=int(banker)
    f={int(h):float(v) for h,v in (scores or {}).items() if int(h)!=main and math.isfinite(float(v))}
    head=sorted(f,key=lambda h:(-f[h],h))[:2]
    prices={}
    for key,value in (qp or {}).items():
        pair=[int(h) for h in str(key).split('-')]
        price=float(value)
        if len(pair)!=2 or len(set(pair))!=2 or main not in pair or not math.isfinite(price) or price<=0:continue
        other=next(h for h in pair if h!=main)
        if other in f:prices[other]=price
    tail=sorted((h for h in prices if h not in head),key=lambda h:(prices[h],-f[h],h))[:2]
    ready=len(head)==2 and len(tail)==2
    return {'legs':head+tail if ready else [],'legs_f':head,'legs_qp':tail,
            'banker_qp_odds':prices,'legs_method':METHOD,'legs_status':'ready' if ready else 'unavailable',
            'legs_reason':'' if ready else ('缺有效T−10份額基準，無法計算F頭兩腳' if len(head)<2 else '缺完整主膽位置Q配搭，無法補足兩腳')}
