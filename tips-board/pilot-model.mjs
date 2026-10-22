import {compatible,evaluate,preparedRace,settlePolicy,key} from './roi-policy.mjs?v=pilot1';
export {preparedRace,settlePolicy,key};
export const groupKey=r=>[r.venue,r.track,r.score].join('|');
export function evidence(s,config){
 if(!s)return {ok:false,reason:'沒有賽日前可用樣本'};
 if(s.n<config.min_samples)return {ok:false,reason:`樣本${s.n}，少於${config.min_samples}`};
 if(new Set(s.days||[]).size<config.min_days)return {ok:false,reason:`只覆蓋${new Set(s.days||[]).size}個賽日`};
 if(!(s.cost>0&&s.profit-s.maxreturn>0))return {ok:false,reason:'扣除最大一筆派彩後未有盈利'};
 return {ok:true,score:(s.profit-s.maxreturn)/s.cost};
}
export function allocations(methods,stats,config){
 const out={};for(const venue of ['HV','ST'])for(const track of venue==='HV'?['TURF']:['TURF','AWT'])for(let score=0;score<=3;score++){
  const r={venue,track,score},eligible=methods.filter(m=>m.h===score&&m.rule.type!=='unavailable'&&compatible(m,r)&&evidence(stats[m.id],config).ok);
  eligible.sort((a,b)=>evidence(stats[b.id],config).score-evidence(stats[a.id],config).score||stats[b.id].n-stats[a.id].n||a.id.localeCompare(b.id));
  out[groupKey(r)]=eligible[0]?.id||null;
 }return out;
}
export function choosePilot(r,methods,stats,config,context={}){
 const allocation=context.allocation||config.assignments,id=allocation?.[groupKey(r)];
 if(!Number.isInteger(r.score)||r.score<0||r.score>3)return {status:'skip',reason:'H未確認，不下注'};
 if(!id)return {status:'skip',reason:'此場地／H沒有通過門檻的固定方法'};
 const method=methods.find(m=>m.id===id),s=stats[id],gate=evidence(s,config);
 if(!method||!compatible(method,r)||!gate.ok)return {status:'skip',reason:gate.reason||'固定方法不適用'};
 const m={...method,n:s.n,hits:s.hits,cost:s.cost,profit:s.profit,days:s.days,maxreturn:s.maxreturn,conservative_roi:gate.score};
 const plan=evaluate(m,r,context);
 return {...plan,method:m,reason:plan.status==='ready'?'固定試行方法；沒有候補':(plan.reason||'條件不成立')+'；本場不改買其他方法'};
}
export function inputSignature(r){return JSON.stringify([r.date,r.venue,r.race,r.off,r.horses.map(h=>[h.no,h.draw,h.jockey_id]),r.scratched||[]]);}
export function validSnapshot(s,r,config){
 if(!s||s.version!==config.version||s.date!==r.date||s.venue!==r.venue||s.race!==r.race||s.ledger!=='paper'||!s.finalized||r.date<config.launched_on)return false;
 const t=Date.parse(s.captured_at),off=Date.parse(r.off);
 if(!Number.isFinite(t)||t<off-config.freeze_minutes*60000||t>=off||!s.input||s.input.date!==r.date||s.input.venue!==r.venue||s.input.race!==r.race)return false;
 if(s.plan?.status!=='ready')return s.plan?.status==='skip'||s.plan?.status==='pending';
 const p=s.plan;return p.method?.id===config.assignments[groupKey(r)]&&Array.isArray(p.tickets)&&p.tickets.length>0&&p.cost===p.tickets.length*10&&p.pool===p.method.pool&&p.cost<=config.daily_stake_limit;
}
function inputRecord(r,odds){return structuredClone({date:r.date,venue:r.venue,race:r.race,off:r.off,score:r.score,track:r.track,rail:r.rail,distance:r.distance,horses:r.horses,scratched:r.scratched||[],tips:r.tips,banker_initial:r.banker_initial,draw_top5:r.draw_top5,odds:odds||{}});}
export function planMeeting(meeting,methods,stats,config,context={}){
 const now=context.now??Date.now(),out=[],allocation=context.allocation||config.assignments;let reserved=0;
 for(const raw of [...meeting.races].sort((a,b)=>a.race-b.race)){
  const r=preparedRace(meeting,raw,context),closed=raw.locked||now>=Date.parse(r.off),stored=context.snapshots?.[r.race]||raw.roi_strategy;
  if(context.ledger==='paper'&&validSnapshot(stored,r,config)){
   let plan=structuredClone(stored.plan);
   if(plan.cost>0&&reserved+plan.cost>config.daily_stake_limit)plan={status:'skip',reason:'封存總額超出本版預算，需核對紀錄'};
   reserved+=plan.status==='ready'?plan.cost:0;out.push({r,plan,origin:'sealed',snapshot:stored});continue;
  }
  if(context.ledger==='paper'&&closed){out.push({r,plan:{status:'skip',reason:'沒有本版賽前封存，不補造選馬'},origin:'missing'});continue;}
  const odds=context.oddsByRace?.[r.race]||{},q=choosePilot(r,methods,stats,config,{...context,allocation,odds});let plan=q;
  if(plan.status==='ready'&&reserved+plan.cost>config.daily_stake_limit)plan={status:'skip',reason:`每日紙上預算$${config.daily_stake_limit}已用盡／餘額不足，本場不下注`};
  reserved+=plan.status==='ready'?plan.cost:0;
  const finalized=context.ledger==='paper'&&!closed&&now>=Date.parse(r.off)-config.freeze_minutes*60000;
  const snapshot={version:config.version,ledger:'paper',date:r.date,venue:r.venue,race:r.race,captured_at:new Date(now).toISOString(),finalized,input:inputRecord(r,odds),signature:inputSignature(r),plan:structuredClone(plan),evidence_through:config.trained_through,odds_source:Object.keys(odds).length?'preoff_supplied':'not_available',reserved_before:reserved-(plan.status==='ready'?plan.cost:0)};
  out.push({r,plan,origin:context.ledger==='replay'?'replay':finalized?'sealed':'preview',snapshot});
 }return out;
}
export function summarizePlans(rows){let cost=0,returned=0,hits=0,n=0,pending=0;for(const x of rows){const s=settlePolicy(x.plan,x.r.result);if(!s.cost)continue;cost+=s.cost;if(s.returned===null)pending++;else{returned+=s.returned;n++;hits+=s.status==='hit';}}return {cost,returned,profit:pending?null:returned-cost,hits,n,pending,roi:cost&&!pending?(returned-cost)/cost:null};}
