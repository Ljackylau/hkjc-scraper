import {prepareMeeting,currentPlan,drawRanking} from './strategy-model.mjs?v=20261021-support';
import {hvWinCandidates,coldWinCandidates} from './st-coldwin.mjs?v=20261021-support';
import {settle} from './settlement.mjs';
export const key=r=>[r.date,r.venue,r.race].join('|');
export const roi=m=>m.cost?m.profit/m.cost:null;
export const rate=m=>m.n?m.hits/m.n:null;
const uniq=a=>[...new Set(a.map(Number))],pairs=a=>a.flatMap((n,i)=>a.slice(i+1).map(x=>[n,x]));
export function compatible(m,r){return Number.isInteger(r.score)&&r.score>=0&&r.score<=3&&m.venue===r.venue&&m.track===r.track&&(m.h==='all'||m.h===r.score)&&(!m.rule.confidenceOnly||r.score>=1)}
export function preparedRace(meeting,r,context={}){
 const race=structuredClone(r);race.date=meeting.date;race.venue=meeting.venue;
 const input=context.replay?.inputs?.[key(race)];
 if(input?.B&&!race.banker_initial)race.banker_initial={status:'ready',date:race.date,venue:race.venue,race:race.race,as_of_race_no:0,reason:'initial',numbers:input.B,record_type:'retrospective_public_archive'};
 const sup=context.support;if(!race.hv_win_support&&sup?.date===race.date&&sup.venue===race.venue)race.hv_win_support=sup.races?.[race.race];
 return race;
}
export function evaluate(m,r,context={}){
 const no=(status,reason,candidates=[])=>({status,reason,candidates});
 if(!compatible(m,r))return no('not_applicable','場地／H不適用');
 const rule=m.rule,inp=context.replay?.inputs?.[key(r)],active=uniq((inp?.active||r.horses.map(h=>h.no)).filter(n=>!(r.scratched||[]).includes(Number(n)))),activeSet=new Set(active),field=new Map(r.horses.map(h=>[Number(h.no),h])),Mtip=r.tips?.meiji,M=Mtip?.status==='ready'&&(!Mtip.source_date||Mtip.source_date===r.date)?Mtip.horses.map(h=>Number(h.no)):null;
 const banker=r.banker_initial,B=banker?.status==='ready'&&banker.date===r.date&&banker.venue===r.venue&&banker.race===r.race&&banker.as_of_race_no===0&&banker.reason==='initial'?banker.numbers.map(Number):null;
 const J=r.draw_top5?.status==='ready'?r.draw_top5.riders.map(h=>Number(h.no)):null;
 const sources=['ball','ma','computer'].map(k=>r.tips?.[k]);
 const ex=sources.filter(s=>s?.status==='ready'&&(!s.source_date||s.source_date===r.date)&&s.horses?.length);
 const E=ex.length===1?ex[0].horses.map(h=>Number(h.no)):null;
 const T=inp?.T||r.tianxi?.numbers||null,firstOnly=inp?.T_first_only||T?.length<4;
 const lists={M,B,J,E,T};
 const need=(...names)=>names.some(n=>!lists[n]?.length);
 const legacy=()=>!M?.length||r.score===1&&!E?.length?null:r.score===1?uniq([E[0],M[0]===E[0]?M[1]:M[0]]).filter(n=>activeSet.has(n)):uniq(M).filter(n=>activeSet.has(n)).slice(0,3);
 const ranked=(scope='rail',min=1)=>{
  if(inp?.draws?.[scope+min])return {status:'ready',draws:inp.draws[scope+min]};
  if(scope!=='rail'){
   if(!context.seed)return {status:'pending',reason:'待同程任意欄基準'};
   const stats={};for(const [k,ds] of Object.entries(context.seed.groups||{})){const [v,d]=k.split('|');if(v!==r.venue||Number(d)!==r.distance)continue;for(const [draw,a] of Object.entries(ds)){const t=stats[draw]??=[0,0];t[0]+=a[0];t[1]+=a[1]}}
   const group=[r.venue,r.distance,'ALL'].join('|'),history={races:(context.history?.races||[]).map(h=>({...h,rail:'ALL'}))};
   const q=drawRanking({...r,rail:'ALL'},{...context.seed,groups:{[group]:stats}},history,context.index,min);return {...q,draws:q.draws?.map(d=>d.draw)};
  }
  const q=drawRanking(r,context.seed,context.history,context.index,min);return {...q,draws:q.draws?.map(d=>d.draw)};
 };
 const filteredPrice=(ns,gt,cap=Infinity)=>{
  const odds=context.odds||{},unknown=ns.filter(n=>!Number.isFinite(Number(odds[n]))||Number(odds[n])<=0);
  if(unknown.length)return no('pending','待賽前W>'+gt+'賠率核實，順延下一方法',ns);
  return {status:'ready',picks:ns.filter(n=>Number(odds[n])>gt).slice(0,cap)};
 };
 let ns=[],bank=null;
 if(rule.type==='unavailable')return no('pending','尚未接入原研究的同口徑輸入，順延');
 if(rule.type==='current'){
  const c=structuredClone(r);c.locked=false;c.result=null;
  const t=Date.parse(r.off)-1;
  const meeting=prepareMeeting({date:r.date,venue:r.venue,races:[c]},null,t),p=currentPlan(meeting.races[0],t);
  if(p.state!=='ready')return no(p.state==='skip'?'skip':'pending',p.reason||'沒有合資格主買法');ns=p.picks;
 }else if(rule.type==='single'||rule.type==='draw'){
  if(need(rule.source))return no('pending','待'+rule.source+'原次序');
  ns=lists[rule.source].slice(rule.rank-1,rule.rank).filter(n=>activeSet.has(n));
  if(rule.gate==='outside_core'){
   if(need('M','B'))return no('pending','待M四選及B五選');ns=ns.filter(n=>!M.includes(n)&&!B.includes(n));
  }
  if(rule.type==='draw'){
   const d=ranked(rule.scope,rule.min);if(d.status!=='ready')return no('pending',d.reason||'待賽日前檔位基準');ns=ns.filter(n=>d.draws.includes(field.get(n)?.draw));
   if(rule.inJ){if(!J)return no('pending','待同檔騎師榜');ns=ns.filter(n=>J.includes(n))}
  }
 }else if(rule.type==='cold'){
  const source=rule.source;
  if((['M1','M2','M4','MnotB','both','union','unionJ'].includes(source)&&!M)||(['B1','B5','MnotB','both','union','unionJ'].includes(source)&&!B))return no('pending','待M／B原次序');
  ns=source==='M1'?M.slice(0,1):source==='M2'?M.slice(1,2):source==='M4'?M:source==='B1'?B.slice(0,1):source==='B5'?B:source==='both'?M.filter(n=>B.includes(n)):source==='MnotB'?M.filter(n=>!B.includes(n)):uniq([...M,...B]);
  ns=uniq(ns).filter(n=>activeSet.has(n));
  if(rule.min){const d=ranked(rule.scope,rule.min);if(d.status!=='ready')return no('pending',d.reason||'待檔位基準');ns=ns.filter(n=>d.draws.includes(field.get(n)?.draw))}
  if(source==='unionJ'){if(!J)return no('pending','待同檔騎師榜');ns=ns.filter(n=>J.includes(n))}
  const p=filteredPrice(ns,rule.gt,rule.cap);if(p.status!=='ready')return p;ns=p.picks;
 }else if(rule.type==='legacy'||rule.type==='txLegacy'){
  ns=legacy();if(!ns)return no('pending','待舊信心組合的專家／明治貼士');
  if(rule.type==='txLegacy'){
   if(!T?.length)return no('pending','待天喜原發布選序');
   const varnt=rule.variant,O=ns.filter(n=>T.includes(n)),U=T.filter(n=>!ns.includes(n)&&activeSet.has(n));
   if(['gate1','gate2','intersection','replace_last','add1'].includes(varnt)&&firstOnly)return no('pending','只有天喜首選，欠其餘原序');
   if(varnt==='gate_T1'&& !ns.includes(T[0])||varnt==='gate1'&&O.length<1||varnt==='gate2'&&O.length<2)ns=[];
   if(varnt==='intersection')ns=O;
   if(varnt==='add1')ns=ns.concat(U.slice(0,1));
   if(varnt==='replace_last'&&!T.includes(ns.at(-1))&&U.length)ns=ns.slice(0,-1).concat(U.slice(0,1));
   if(varnt==='banker_T1_inside'){if(ns.includes(T[0]))bank=T[0];else ns=[]}
  }
 }else if(rule.type==='tx0'){
  if(!T?.length)return no('pending','待天喜同口徑鎖定資料');
  if(need('M','B'))return no('pending','待明治及膽拖初版');
  const rest=M.slice(1),order=r.venue==='ST'?[M[0],B[0],...rest.filter(n=>B.slice(0,3).includes(n)),...rest.filter(n=>!B.slice(0,3).includes(n))]:M.concat(B);
  ns=uniq(order).filter(n=>activeSet.has(n)).slice(0,3);const v=rule.variant,conf=!B.slice(0,3).includes(M[0]);
  if(['conf','conf_gateT1','conf_bankerT1'].includes(v)&&!conf)ns=[];
  if(v!=='base'&&v!=='conf'){
   if(!T?.length)return no('pending','待天喜原發布選序');
   if(['intersection','add1','T3'].includes(v)&&firstOnly)return no('pending','只有天喜首選，欠其餘原序');
   if(['gateT1','bankerT1','conf_gateT1','conf_bankerT1'].includes(v)){if(!ns.includes(T[0]))ns=[];else if(v.toLowerCase().includes('banker'))bank=T[0]}
   if(v==='intersection')ns=ns.filter(n=>T.includes(n));
   if(v==='T1bankerS'){bank=T[0];ns=uniq([T[0],...ns])}
   if(v==='add1')ns=ns.concat(T.filter(n=>!ns.includes(n)).slice(0,1));
   if(v==='T3')ns=T.slice(0,3);
   if(v==='M1T1'||v==='M2T1'){ns=[M[v==='M1T1'?0:1],T[0]];if(ns[0]===ns[1])ns=[]}
  }
 }else if(rule.type==='cover'){
  let c;
  if(inp?.cover_known)c=inp.cover.map(h=>h.no);
  else {const q=hvWinCandidates(r,r.hv_win_support);if(q.status!=='ready')return no('pending',q.reason||'待四位作者及往績');c=q.candidates.map(h=>h.no)}
  const q=filteredPrice(c.filter(n=>activeSet.has(n)),8,2);if(q.status!=='ready')return q;ns=q.picks;
 }
 ns=uniq(ns).filter(n=>activeSet.has(n));
 const tickets=['W','P'].includes(m.pool)?ns.map(n=>[n]):bank===null?pairs(ns):ns.filter(n=>n!==bank).map(n=>[bank,n]);
 if(!tickets.length)return no('skip','條件不成立／無合資格馬');
 return {status:'ready',picks:ns,pool:m.pool,tickets,cost:tickets.length*10,banker:bank};
}
export function choosePolicy(r,methods,context={},stats=null){
 const eligible=methods.filter(m=>compatible(m,r)).map(m=>({...m,...(stats?(stats[m.id]||{n:0,hits:0,cost:0,profit:0}):{})})).filter(m=>m.cost>0&&roi(m)>0&&m.n>=(context.minSamples||1));
 eligible.sort((a,b)=>roi(b)-roi(a)||b.n-a.n||a.id.localeCompare(b.id));
 const attempts=[];
 for(const m of eligible){const p=evaluate(m,r,context);attempts.push({method:m,...p});if(p.status==='ready')return {status:'ready',method:m,...p,attempts}}
 return {status:'skip',reason:attempts.length?'所有正ROI方法均不成立或欠資料':'沒有已驗證正ROI方法',attempts};
}
export function settlePolicy(p,result){
 if(p.status!=='ready')return {status:'skip',cost:0,returned:0,profit:0};
 if(result?.pool_status?.[p.pool]==='not_offered')return {status:'not_offered',cost:0,returned:0,profit:0};
 const paid=result?.dividends?.[p.pool];if(!paid?.length)return {status:'pending',cost:p.cost,returned:null,profit:null};
 const wanted=new Set(p.tickets.map(t=>[...t].sort((a,b)=>a-b).join(','))),withdrawn=new Set(result.withdrawn||[]);
 const returned=paid.filter(h=>wanted.has(String(h.combination).split(',').map(Number).sort((a,b)=>a-b).join(','))).reduce((s,h)=>s+Number(h.dividend_hkd),0),refunds=p.tickets.filter(t=>t.some(n=>withdrawn.has(n))).length*10;
 return {status:returned?'hit':refunds===p.cost?'refund':'miss',cost:p.cost,returned:returned+refunds,profit:returned+refunds-p.cost};
}
