import {applyManual,confidenceReason} from './manual-tips.mjs?v=20261021-st-qp';
import {settle} from './settlement.mjs';
export const VERSION='confidence-cover-v1-20261022',LAUNCH='2026-10-22',UNIT=10,MAX_COVER=3;
export const SECONDARY_VERSION='h0-intersection2-gt7.5-v1-20261022';
export const key=r=>[r.date,r.venue,r.race].join('|');
const nums=a=>[...new Set((a||[]).map(Number))],active=r=>new Set(r.horses.filter(h=>!nums([...(r.scratched||[]),...(r.result?.withdrawn||[])]).includes(h.no)).map(h=>h.no));
export const surface=r=>r.venue==='HV'?'HV_TURF':r.track==='AWT'?'ST_AWT':'ST_TURF';
export function prepare(source,saved=null,now=Date.now()){const m=applyManual(source,saved,now);for(const r of m.races){r.date=m.date;r.venue=m.venue;}return m;}
export function primary(r){if(r.score==null||r.st_plan_state==='pending')return {status:'pending',picks:[],bets:[],reason:(r.st_plan_reason||r.hv_plan_reason||'待專家來源及信心條件核實')+(r.tips?.meiji?.status==='stale'?'；明治朗來源日期 '+r.tips.meiji.source_date:'')};if(!confidenceReason(r))return {status:'skip',picks:[],bets:[],reason:'非信心場，沒有主買法'};const picks=(r.selection?.horses||[]).map(h=>h.no);return picks.length?{status:'ready',picks,bets:[...new Set(r.selection.main||[])].map(pool=>({pool,picks})),reason:r.selection.roles||r.selection.method||'信心場主買法'}:{status:'pending',picks:[],bets:[],reason:'信心場選馬未齊'};}
export function fourCandidate(r,{archive=null,replay=false}={}){
 const no=(status,reason,extra={})=>({status,reason,...extra}),a=active(r),tip=r.tips?.meiji;
 if(tip?.status!=='ready'||tip.source_date&&tip.source_date!==r.date||tip.horses?.length!==4)return no('pending','待同日明治四選');
 const M=tip.horses.map(h=>Number(h.no));if(new Set(M).size!==4)return no('pending','明治選馬重複，待核對');
 let B=r.banker_initial;
 if(replay&&(!B||B.status!=='ready')&&archive?.B)B={status:'ready',date:r.date,venue:r.venue,race:r.race,as_of_race_no:0,reason:'initial',numbers:archive.B};
 if(B?.status!=='ready'||B.date!==r.date||B.venue!==r.venue||B.race!==r.race||B.as_of_race_no!==0||B.reason!=='initial'||B.numbers?.length!==5||new Set(B.numbers.map(Number)).size!==5)return no('pending','待同場膽拖初版');
 const first=[];for(const n of B.numbers.slice(0,2).map(Number))if(M.includes(n)&&a.has(n)&&!first.includes(n))first.push(n);
 for(const n of M){if(first.length===3)break;if(a.has(n)&&!first.includes(n))first.push(n)}
 if(first.length!==3)return no('pending','不足三匹有效原選馬');
 let ranked,excluded=[];
 if(replay&&archive){
  const actual=[...a].sort((x,y)=>x-y),expected=archive.active.slice().sort((x,y)=>x-y);
  if(archive.date!==r.date||archive.venue!==r.venue||archive.race!==r.race||JSON.stringify(actual)!==JSON.stringify(expected)||r.horses.some(h=>a.has(h.no)&&archive.field[h.no]!==h.name))return no('pending','歷史跑法資料與出賽名單不符');
  ranked=archive.ranked;excluded=archive.unknown||[];
 }else{
  const f=r.front_support;
  if(f?.status!=='ready'||f.method!=='front-three-starts-v1'||f.date!==r.date||f.before_date!==r.date||f.venue!==r.venue||f.race!==r.race||Date.parse(f.captured_at)>=Date.parse(r.off))return no('pending','待全場賽前跑法往績');
  ranked=[];for(const h of r.horses){if(!a.has(h.no))continue;const q=f.forms?.[h.no];if(q?.status!=='ready'||q.horse_id!==h.horse_id)return no('pending','部分馬匹跑法往績未齊');
   const early=(q.recent||[]).filter(x=>x.date<r.date&&Array.isArray(x.positions)&&x.positions.length>=2&&Number.isInteger(x.positions[0])&&x.positions[0]>0).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,3).map(x=>x.positions[0]);
   if(early.length<2){excluded.push(h.no);continue}const sorted=early.slice().sort((x,y)=>x-y),mid=sorted.length%2?sorted[(sorted.length-1)/2]:(sorted[sorted.length/2-1]+sorted[sorted.length/2])/2;
   ranked.push({no:h.no,median:mid,mean:early.reduce((s,n)=>s+n,0)/early.length,n:early.length});
  }ranked.sort((x,y)=>x.median-y.median||x.mean-y.mean||x.no-y.no);ranked=ranked.slice(0,5);
 }
 const candidates=ranked.filter(h=>a.has(h.no)&&!first.includes(h.no));if(!candidates.length)return no('skip','跑法前五沒有未重複候選',{first,ranked,excluded,candidates:[]});
 return {status:'awaiting_odds',first,ranked,excluded,candidates,reason:'核對全部候選賠率，最高者須>10倍'};
}
export function pricedCandidate(candidate,odds){if(candidate.status!=='awaiting_odds')return candidate;const missing=candidate.candidates.filter(h=>!(Number(odds?.[h.no])>0));if(missing.length)return {...candidate,status:'pending',reason:'待所有候選的賽前W賠率',missing:missing.map(h=>h.no)};
 const chosen=candidate.candidates.slice().sort((a,b)=>Number(odds[b.no])-Number(odds[a.no])||a.no-b.no)[0],price=Number(odds[chosen.no]);return {...candidate,status:price>10?'ready':'skip',pick:chosen.no,odds:price,reason:price>10?'第四匹>10倍，待每日首三注名額':'第四匹賠率≤10，不買補Win'};
}
export function validSnapshot(s,r){
 const off=Date.parse(r.off),inWindow=t=>Number.isFinite(Date.parse(t))&&Date.parse(t)>=off-180000&&Date.parse(t)<off;
 if(s?.version!==VERSION||s.date!==r.date||s.venue!==r.venue||s.race!==r.race||s.ledger!=='paper'||r.date<LAUNCH||!s.finalized||!s.primary||!s.cover||s.input?.date!==r.date||s.input?.venue!==r.venue||s.input?.race!==r.race)return false;
 if(s.secondary_finalized&&(s.secondary_version!==SECONDARY_VERSION||!inWindow(s.secondary_captured_at)))return false;
 if(s.primary_finalized&&!inWindow(s.primary_captured_at))return false;
 if(s.cover_finalized&&!inWindow(s.cover_captured_at))return false;
 return !!(s.primary_finalized||s.cover_finalized);
}
export function mergeSnapshots(server,local,r){
 const a=validSnapshot(server,r)?server:null,b=validSnapshot(local,r)?local:null;if(!a)return b;if(!b)return a;
 const primary=a.primary_finalized?a:b.primary_finalized?b:a,cover=a.cover_finalized?a:b.cover_finalized?b:a,secondary=a.secondary_finalized?a:b.secondary_finalized?b:a;
 return {...a,secondary:secondary.secondary,secondary_version:secondary.secondary_version,secondary_finalized:!!secondary.secondary_finalized,secondary_captured_at:secondary.secondary_captured_at,secondary_input:secondary.secondary_input,primary:structuredClone(primary.primary),primary_finalized:!!primary.primary_finalized,primary_captured_at:primary.primary_captured_at,input:primary.input,cover:structuredClone(cover.cover),cover_finalized:!!cover.cover_finalized,cover_captured_at:cover.cover_captured_at,cover_input:cover.cover_input,finalized:true};
}
function evaluateOriginalMeeting(m,{ledger='replay',archives={},snapshots={},oddsByRace={},now=Date.now(),saved=null}={}){
 const prepared=prepare(m,saved,now),rows=[];let used=0,unknownPrior=false;
 for(const r of [...prepared.races].sort((a,b)=>a.race-b.race)){
  const closed=r.locked||now>=Date.parse(r.off),sealed=mergeSnapshots(r.combined_snapshot,snapshots[r.race],r);
  if(ledger==='paper'&&sealed&&(closed||sealed.primary_finalized&&sealed.cover_finalized)){
   let cover=structuredClone(sealed.cover);if(!sealed.cover_finalized)cover={...cover,status:'pending',reason:'未有開跑前補Win核實，不補造'};
   if(cover.status==='ready'){if(used>=MAX_COVER)cover={...cover,status:'skip',reason:'封存補Win超出每日三注，需核對'};else used++;}if(cover.status==='pending')unknownPrior=true;
   const main=sealed.primary_finalized?structuredClone(sealed.primary):{status:'skip',bets:[],picks:[],reason:'未保存賽前主買法'};
   rows.push({r,primary:main,cover,origin:'sealed',snapshot:sealed});continue;
  }
  if(ledger==='paper'&&closed){unknownPrior=true;rows.push({r,primary:{status:'skip',bets:[],picks:[],reason:'未保存本版賽前主買法'},cover:{status:'pending',reason:'未保存本版賽前補Win核實'},origin:'missing'});continue;}
  const archive=ledger==='replay'?archives[key(r)]:null,odds=ledger==='replay'?archive?.final_odds||{}:oddsByRace[r.race]||{};
  const main=sealed?.primary_finalized?structuredClone(sealed.primary):primary(r),candidate=fourCandidate(r,{archive,replay:ledger==='replay'});let cover=sealed?.cover_finalized?structuredClone(sealed.cover):pricedCandidate(candidate,odds);
  if(used>=MAX_COVER)cover={...cover,status:'skip',reason:'每日首三注名額已用完'};
  else if(cover.status==='ready'&&unknownPrior&&ledger==='paper')cover={...cover,status:'pending',reason:'前場未核實，不能確認每日首三注次序'};
  else if(cover.status==='ready'){cover={...cover,slot:++used,reason:'每日第'+used+'注補Win，每匹$10W'};}
  if(cover.status==='pending'&&ledger==='paper')unknownPrior=true;
  const window=ledger==='paper'&&r.date>=LAUNCH&&!closed&&now>=Date.parse(r.off)-180000;
  const input=structuredClone({date:r.date,venue:r.venue,race:r.race,off:r.off,score:r.score,track:r.track,distance:r.distance,rail:r.rail,horses:r.horses,scratched:r.scratched||[],tips:r.tips,banker_initial:r.banker_initial,draw_top5:r.draw_top5,front_support:r.front_support,odds});
  const primaryFinal=sealed?.primary_finalized||window&&main.status!=='pending',coverFinal=sealed?.cover_finalized||window&&['ready','skip'].includes(cover.status),stamp=new Date(now).toISOString();
  const snapshot={version:VERSION,ledger:'paper',date:r.date,venue:r.venue,race:r.race,captured_at:sealed?.captured_at||stamp,finalized:!!(primaryFinal||coverFinal),primary_finalized:!!primaryFinal,cover_finalized:!!coverFinal,primary_captured_at:sealed?.primary_captured_at||(primaryFinal?stamp:null),cover_captured_at:sealed?.cover_captured_at||(coverFinal?stamp:null),primary:structuredClone(main),cover:structuredClone(cover),input:sealed?.primary_finalized?sealed.input:input,cover_input:sealed?.cover_finalized?sealed.cover_input:coverFinal?input:null};
  rows.push({r,primary:main,cover,origin:ledger==='replay'?'replay':snapshot.finalized?'sealed':'preview',snapshot});
 }return rows;
}

export function intersectionCandidate(r,{archive=null,replay=false}={}){
 const no=(status,reason,extra={})=>({status,reason,...extra});
 if(r.score==null)return no('pending','待H條件核實');
 if(r.score!==0)return no('skip','只限H=0');
 const tip=r.tips?.meiji;
 if(tip?.status!=='ready'||tip.source_date&&tip.source_date!==r.date||tip.horses?.length!==4)return no('pending','待同日明治四選');
 const M=tip.horses.map(h=>Number(h.no));if(new Set(M).size!==4)return no('pending','明治四選重複，待核對');
 let B=r.banker_initial;
 if(replay&&(!B||B.status!=='ready')&&archive?.B)B={status:'ready',date:r.date,venue:r.venue,race:r.race,as_of_race_no:0,reason:'initial',numbers:archive.B};
 if(B?.status!=='ready'||B.date!==r.date||B.venue!==r.venue||Number(B.race)!==r.race||B.as_of_race_no!==0||B.reason!=='initial'||B.numbers?.length!==5||new Set(B.numbers.map(Number)).size!==5)return no('pending','待同場膽拖初版');
 const intersection=B.numbers.map(Number).filter(n=>M.includes(n)),pick=intersection[1];
 if(!pick)return no('skip','不足兩個交集，不買',{intersection});
 if(!active(r).has(pick))return no('skip','原第2個交集已退出，不補位',{intersection,pick});
 return no('conditional','候選買W：只在臨場賠率>7.5，且本場不屬原首三注補Win時買$10W',{intersection,pick,threshold:7.5});
}
export function evaluateMeeting(m,options={}){
 const {ledger='replay',archives={},snapshots={},oddsByRace={},now=Date.now()}=options;
 const rows=evaluateOriginalMeeting(m,options);
 for(const row of rows){const r=row.r,sealed=mergeSnapshots(r.combined_snapshot,snapshots[r.race],r),closed=r.locked||now>=Date.parse(r.off);
  if(ledger==='paper'&&sealed?.secondary_finalized&&sealed.secondary_version===SECONDARY_VERSION){row.secondary=structuredClone(sealed.secondary);if(row.snapshot)Object.assign(row.snapshot,{secondary:row.secondary,secondary_version:SECONDARY_VERSION,secondary_finalized:true,secondary_captured_at:sealed.secondary_captured_at,secondary_input:sealed.secondary_input});continue;}
  if(ledger==='paper'&&closed){row.secondary={status:'pending',reason:'未保存本版賽前交集補Win核實，不補造'};continue;}
  const archive=ledger==='replay'?archives[key(r)]:null,odds=ledger==='replay'?archive?.final_odds||{}:oddsByRace[r.race]||{};let secondary=intersectionCandidate(r,{archive,replay:ledger==='replay'});
  if(secondary.status==='conditional'){
   if(row.cover.status==='ready')secondary={...secondary,status:'skip',reason:'本場已屬原首三注補Win，排除交集補Win'};
   else if(row.cover.status!=='skip')secondary={...secondary,status:'conditional',reason:'候選買W，僅當W>7.5；須先確認本場不屬原首三注補Win'};
   else if(Number(odds[secondary.pick])>0){const price=Number(odds[secondary.pick]);secondary={...secondary,status:price>7.5?'ready':'skip',odds:price,reason:price>7.5?'H=0第2個交集，W>7.5，買$10W':'W≤7.5，不買交集補Win'};}
  }
  row.secondary=secondary;
  if(row.snapshot){const final=ledger==='paper'&&r.date>=LAUNCH&&!closed&&now>=Date.parse(r.off)-180000&&['ready','skip'].includes(secondary.status);Object.assign(row.snapshot,{secondary_version:SECONDARY_VERSION,secondary:structuredClone(secondary),secondary_finalized:final,secondary_captured_at:final?new Date(now).toISOString():null,secondary_input:final?structuredClone({date:r.date,venue:r.venue,race:r.race,off:r.off,score:r.score,tips:r.tips,banker_initial:r.banker_initial,odds,original_cover:row.cover}):null});if(final)row.snapshot.finalized=true;}
 }return rows;
}

export function settledBet(pool,picks,result){const s=settle(pool,picks,result),cost=s.status==='not_offered'?0:s.total*UNIT,returned=s.status==='pending'?null:s.hits.reduce((a,h)=>a+h.dividend,0)+s.refunds*UNIT;return{pool,picks,cost,returned,profit:returned===null?null:returned-cost,status:s.status,hit:s.hits.length>0};}
export function raceBets(row,role='combined'){let bs=[];if(['combined','original','main'].includes(role)&&row.primary.status==='ready')bs=row.primary.bets.map(b=>({...settledBet(b.pool,b.picks,row.r.result),role:'main'}));if(['combined','original','cover'].includes(role)&&row.cover.status==='ready')bs.push({...settledBet('W',[row.cover.pick],row.r.result),role:'cover'});if(['combined','secondary'].includes(role)&&row.secondary?.status==='ready')bs.push({...settledBet('W',[row.secondary.pick],row.r.result),role:'secondary'});return bs;}
export function summarize(rows,{role='combined',surfaceFilter='all'}={}){
 let cost=0,returned=0,pending_cost=0,bet_races=0,settled_races=0,hits=0,profitable_races=0,pending=0;
 for(const row of rows){if(surfaceFilter!=='all'&&surface(row.r)!==surfaceFilter)continue;const bs=raceBets(row,role);if(!bs.length)continue;bet_races++;for(const b of bs){if(b.returned===null){pending++;pending_cost+=b.cost}else{cost+=b.cost;returned+=b.returned;}}
  if(bs.every(b=>b.returned!==null)&&bs.some(b=>b.cost>0&&b.status!=='refund')){settled_races++;hits+=bs.some(b=>b.hit);profitable_races+=bs.reduce((a,b)=>a+b.profit,0)>0;}
 }return{cost,returned,profit:returned-cost,roi:cost?(returned-cost)/cost:null,pending_cost,bet_races,settled_races,hits,accuracy:settled_races?hits/settled_races:null,profitable_races,pending};
}
