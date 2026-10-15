"""Versioned Sha Tin score 0/1 box selections; inputs are pre-off tips only."""
METHOD='st-d-qqp-20261015'
EXPERTS=('ball','ma','computer')
def choose_st(r):
    r['selection']=None
    sources=[r['tips'][k] for k in EXPERTS]
    if any(s['status'] not in ('ready','absent') for s in sources):r['score']=None;return
    h=r['score']=sum(bool(s['horses']) for s in sources)
    if h>1:return
    m=r['tips']['meiji'];b=r.get('banker_initial',{})
    if any(s.get('source_date') not in (None,r.get('date')) for s in [m,*sources]):return
    if (m['status']!='ready' or len(m['horses'])<4 or b.get('status')!='ready' or b.get('as_of_race_no')!=0
        or b.get('reason')!='initial' or len(b.get('numbers',[]))!=5
        or (b.get('date'),b.get('venue'),b.get('race'))!=(r.get('date'),'ST',r['race'])):return
    M=[int(x['no']) for x in m['horses']];B=list(map(int,b['numbers']))
    if h==0:
        rest=M[1:];order=[M[0],B[0]]+[n for n in rest if n in B[:3]]+[n for n in rest if n not in B[:3]]
    else:
        T=[int(x['no']) for x in next(s for s in sources if s['horses'])['horses']]
        if len(T)<3:return
        order=[M[2],T[1],T[2],B[0],B[3],M[0],M[1],M[3],B[1],T[0],T[3] if len(T)>3 else None,B[2],B[4]]
    field={int(x['no']):x for x in r['horses']};scratched=set(map(int,r.get('scratched',[])))
    nos=[n for n in dict.fromkeys(order) if n in field and n not in scratched][:3]
    if len(nos)!=3:return
    r['selection']={'horses':[{'no':n,'name':field[n]['name']} for n in nos],
                    'main':['QP'] if h==0 else ['Q','QP'],'optional':[],
                    'method':METHOD,'roles':'新D' if h==0 else 'M3+T2+T3'}
