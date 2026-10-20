"""Sha Tin turf confidence-only three-horse Quinella Place trial."""
METHOD='st-turf-confidence-qp-20261021'
EXPERTS=('ball','ma','computer')
def choose_st(r):
    r['selection']=None
    r.pop('st_plan_state',None);r.pop('st_plan_reason',None)
    def state(kind,reason):
        r['st_plan_state'],r['st_plan_reason']=kind,reason
    sources=[r['tips'][k] for k in EXPERTS]
    if any(s['status'] not in ('ready','absent') for s in sources):
        r['score']=None;state('pending','待確認三個專家來源');return
    h=r['score']=sum(bool(s['horses']) for s in sources)
    if h>1:return
    if not r.get('track'):state('pending','待官方跑道資料');return
    if r['track']!='TURF':state('skip','只買沙田草地，本場不買');return
    m=r['tips']['meiji'];b=r.get('banker_initial',{})
    if any(s.get('source_date') not in (None,r.get('date')) for s in [m,*sources]):state('pending','貼士日期不符，待更新');return
    if m['status']!='ready' or len(m['horses'])<4:state('pending','待明治朗四選');return
    B=list(map(int,b.get('numbers',[])))
    if (b.get('status')!='ready' or b.get('as_of_race_no')!=0 or b.get('reason')!='initial'
        or len(B)!=5 or len(set(B))!=5 or (b.get('date'),b.get('venue'),b.get('race'))!=(r.get('date'),'ST',r['race'])):
        state('pending','待膽拖網同場初版推介');return
    M=[int(x['no']) for x in m['horses']]
    if M[0] in B[:3]:state('skip','明治朗首選在膽拖初版前三內，本場不買');return
    if h==0:
        rest=M[1:];order=[M[0],B[0]]+[n for n in rest if n in B[:3]]+[n for n in rest if n not in B[:3]]
    else:
        T=[int(x['no']) for x in next(s for s in sources if s['horses'])['horses']]
        if len(T)<3:state('pending','待唯一專家第2及第3選');return
        order=[M[2],T[1],T[2],B[0],B[3],M[0],M[1],M[3],B[1],T[0],T[3] if len(T)>3 else None,B[2],B[4]]
    field={int(x['no']):x for x in r['horses']};scratched=set(map(int,r.get('scratched',[])+(r.get('result') or {}).get('withdrawn',[])))
    nos=[n for n in dict.fromkeys(order) if n in field and n not in scratched][:3]
    if len(nos)!=3:state('pending','未有三匹有效選馬');return
    state('ready','草地信心條件成立，新D三馬位置Q' if h==0 else '草地信心條件成立，M3＋T2＋T3位置Q')
    r['selection']={'horses':[{'no':n,'name':field[n]['name']} for n in nos],
                    'main':['QP'],'optional':[],'method':METHOD,'roles':'新D' if h==0 else 'M3+T2+T3'}
