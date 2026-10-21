import {settle} from './settlement.mjs';
import {prepareMeeting,currentPlan,researchPlans} from './strategy-model.mjs?v=20261021-support';
export function historyRows(meeting,{mode='saved',context={}}={}){
 const initial=Date.parse(meeting.races[0]?.off)-1;
 const replaySource=structuredClone(meeting);
 for(const r of replaySource.races){r.locked=false;r.result=null}
 const replay=mode==='current'?prepareMeeting(replaySource,null,initial):null;
 return meeting.races.map((raw,i)=>{
  const r={...raw,date:meeting.date,venue:meeting.venue};
  let picks=[],pools=[],reason='',method='';
  if(mode==='current'){
   const p=currentPlan(replay.races[i],initial);picks=p.picks||[];pools=p.pool?[p.pool]:[];reason=p.reason||p.method?.rule||'';method=p.method?.title||'';
  }else{
   picks=(r.selection?.horses||[]).map(h=>Number(h.no));pools=[...new Set((r.selection?.main||[]).filter(p=>['W','P','Q','QP'].includes(p)))];
   reason=r.hv_plan_reason||r.st_plan_reason||(r.selection?'':'沒有保存賽前買法');method=r.selection?.roles||r.selection?.method||'已保存主買法';
  }
  const valid=picks.length&&picks.every(n=>r.horses.some(h=>Number(h.no)===n));
  const bets=valid?pools.map(pool=>{
   const s=settle(pool,picks,r.result),cost=s.total*10,settled=['hit','miss','refund','not_offered'].includes(s.status),effective=s.status==='not_offered'?0:cost;
   const returned=s.status==='not_offered'?0:s.hits.reduce((a,h)=>a+h.dividend,0)+s.refunds*10;
   return {pool,picks,status:s.status,cost:effective,returned:settled?returned:null,profit:settled?returned-effective:null,hits:s.hits};
  }):[];
  const researchRace={...r,locked:false,result:null};
  const research=researchPlans(researchRace,{...context,now:Date.parse(r.off)-1,odds:{}});
  return {r,method,reason,bets,research,mode};
 });
}
export function summarize(rows){
 const bets=rows.flatMap(x=>x.bets),settled=bets.filter(b=>b.returned!==null),cost=settled.reduce((s,b)=>s+b.cost,0),returned=settled.reduce((s,b)=>s+b.returned,0);
 const paidRows=rows.filter(x=>x.bets.some(b=>b.cost>0&&b.returned!==null)),hits=paidRows.filter(x=>x.bets.some(b=>b.status==='hit')).length;
 return {cost,returned,profit:returned-cost,roi:cost?(returned-cost)/cost:null,races:paidRows.length,hits,pending:bets.filter(b=>b.status==='pending').length,rate:paidRows.length?hits/paidRows.length:null};
}
