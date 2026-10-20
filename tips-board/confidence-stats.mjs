import {applyManual,confidenceReason} from './manual-tips.mjs?v=20261021-hv-trial';
import {settle} from './settlement.mjs';
export const poolLabels={W:'獨贏W',P:'位置P',Q:'連贏Q',QP:'位置Q'};
// Count a meeting once even when latest.json and its dated archive both exist.
export function monthlyConfidence(sources,{savedFor=()=>null,time=Date.now()}={}){
 const meetings=new Map();for(const m of sources)if(m?.date&&m?.venue&&Array.isArray(m.races))meetings.set(m.date+':'+m.venue,m);
 const groups=new Map();
 for(const source of meetings.values()){
  const m=applyManual(source,savedFor(source),time);
  for(const r of m.races){
   r.venue=m.venue;r.date=m.date;
   if(!confidenceReason(r))continue;
   const main=[...new Set(r.selection?.main||[])],optional=[...new Set(r.selection?.optional||[])].filter(p=>!main.includes(p));
   const plans=[...main.map(pool=>({pool,role:'main'})),...optional.map(pool=>({pool,role:'optional'}))];
   if(!plans.length)plans.push({pool:'pending',role:'main'});
   for(const {pool,role} of plans){
    const month=m.date.slice(0,7),key=[month,m.venue,r.score,pool,role].join(':');
    if(!groups.has(key))groups.set(key,{month,venue:m.venue,score:r.score,pool,role,races:0,settled:0,hits:0,pending:0,refunds:0,notOffered:0,recalculated:0,backfilled:0});
    const g=groups.get(key);g.races++;g.recalculated+=Number(Boolean(r.strategy_recalculated));g.backfilled+=Number(m.record_type==='historical_backfill');
    if(pool==='pending'||!r.selection?.horses?.length){g.pending++;continue}
    const s=settle(pool,r.selection.horses.map(h=>h.no),r.result);
    if(s.status==='hit'||s.status==='miss'){g.settled++;g.hits+=Number(s.status==='hit')}
    else if(s.status==='refund')g.refunds++;else if(s.status==='not_offered')g.notOffered++;else g.pending++;
   }
  }
 }
 const order={QP:0,Q:1},venueOrder={ST:0,HV:1};
 return [...groups.values()].filter(g=>g.pool==='QP'||g.pool==='Q').map(g=>({...g,rate:g.settled?g.hits/g.settled:null})).sort((a,b)=>(venueOrder[a.venue]??2)-(venueOrder[b.venue]??2)||a.venue.localeCompare(b.venue)||a.score-b.score||b.month.localeCompare(a.month)||order[a.pool]-order[b.pool]||a.role.localeCompare(b.role));
}
