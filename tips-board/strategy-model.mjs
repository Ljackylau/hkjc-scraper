import {chooseManual,confidenceReason} from './manual-tips.mjs?v=20261021-st-qp';
import {coldWinCandidates,coldWinSelect,hvWinCandidates} from './st-coldwin.mjs?v=20261021-support';
const current=(id,venue,track,h,title,pool,n,hits,cost,profit,rule)=>({id,venue,track,h,title,pool,n,hits,cost,profit,rule,kind:'current',unit:'場'});
const research=(id,venue,h,title,n,hits,profit,rule)=>({id,venue,track:'TURF',h,title,pool:'W',n,hits,cost:n*10,profit,rule,kind:'research',unit:'注'});
export const METHODS=[
 current('hv0','HV','TURF',0,'M1在初版前三外 → J2位置','P',15,9,150,171,'M1不在B1–B3；J2原位，退出不順延'),
 current('hv1','HV','TURF',1,'唯一專家原首選獨贏','W',7,5,70,93,'只買唯一專家原第1選，不設賠率門檻'),
 current('hv2','HV','TURF',2,'明治前三互拖位置Q','QP',6,6,180,128,'M1、M2、M3三馬互拖，三組各$10'),
 current('hv3','HV','TURF',3,'明治前三互拖位置Q','QP',2,2,60,89.5,'M1、M2、M3三馬互拖，三組各$10'),
 current('st0','ST','TURF',0,'新D三馬互拖位置Q','QP',24,16,720,1135,'M1在初版前三外；依新D去重及候補取三匹'),
 current('st1','ST','TURF',1,'M3＋T2＋T3互拖位置Q','QP',7,5,210,91.5,'M1在初版前三外；依既有候補取三匹'),
 current('st2','ST','TURF',2,'明治前三互拖位置Q','QP',4,2,120,-59.5,'H2沿用現行明治前三QP'),
 current('st3','ST','TURF',3,'明治前三互拖位置Q','QP',0,0,0,0,'沒有已結算H3樣本'),
 current('aw0','ST','AWT',0,'跳過','',0,0,0,0,'現行低H只買草地；母體7場'),
 current('aw1','ST','AWT',1,'跳過','',0,0,0,0,'現行低H只買草地；母體2場'),
 current('aw2','ST','AWT',2,'明治前三互拖位置Q','QP',1,1,30,-10,'有中QP仍可能虧損'),
 current('aw3','ST','AWT',3,'明治前三互拖位置Q','QP',0,0,0,0,'沒有已結算H3樣本'),
 research('m2d','HV',0,'M2＋檔位前三',6,3,110,'同場同程同欄；檔位至少1仗；M2原位買W'),
 research('m2d8','HV',0,'M2＋檔位前三（至少8仗）',4,2,96,'只在至少8仗的合資格檔位重新排前三'),
 research('m2dj','HV',0,'M2＋檔位前三＋同檔騎師頭5',3,2,53,'同時滿足M2、檔前三及J榜；買W'),
 research('stcold0','ST',0,'M1＋檔位前三＋獨贏>8',3,2,192,'沙草H0；M1原位；檔位至少1仗'),
 research('stcoldall','ST','all','M1＋檔位前三＋獨贏>8（全部H）',6,2,162,'沙草全部H合併；含H0三注，非另一獨立樣本'),
 research('hvcommon2','HV',2,'M四選∩B五選＋檔前三＋獨贏>8',1,1,93,'共同馬按明治次序，過濾條件後最多2匹；僅1注'),
 research('hvcover1','HV',1,'谷草H1補冷Win（44注方案子組）',8,2,123,'核心外、>8、過往首段中位數≥4；休後/回勇＋作者支持；每場最多2匹；歷史資格回算，研究加注'),
];
export const roi=m=>m.cost?m.profit/m.cost:null;
export const rate=m=>m.n?m.hits/m.n:null;
export const venueName=m=>m.venue==='HV'?'谷草':m.track==='AWT'?'沙田泥地':'沙田草地';
export const metric=m=>m.pool==='W'?'勝出率':m.pool==='P'?'上名命中率':'QP至少中一組';
export function interval(hits,n){if(!n)return null;const z=1.96,d=1+z*z/n,c=(hits/n+z*z/(2*n))/d,e=z*Math.sqrt((hits/n*(1-hits/n)+z*z/(4*n))/n)/d;return [Math.max(0,c-e),Math.min(1,c+e)]}
export const applies=(m,r)=>m.venue===r.venue&&m.track===r.track&&(m.h==='all'||m.h===r.score);
export function nextMeeting(meetings,now=Date.now()){
 return meetings.filter(m=>m?.races?.some(r=>!r.locked&&Date.parse(r.off)>now)).sort((a,b)=>Date.parse(a.races[0].off)-Date.parse(b.races[0].off))[0]||null;
}
export function prepareMeeting(source,saved,now=Date.now()){
 const m=structuredClone(source);
 for(const r of m.races){r.date=m.date;r.venue=m.venue;
  if(r.locked||Date.parse(r.off)<=now)continue;
  const entry=saved?.date===m.date&&saved.venue===m.venue?saved.races?.[r.race]:null;
  for(const [key,tip]of Object.entries(entry?.overrides||{}))if(['meiji','ball','ma','computer'].includes(key))r.tips[key]=structuredClone(tip);
  const sources=['ball','ma','computer'].map(k=>r.tips?.[k]);
  if(sources.some(s=>!s||!['ready','absent'].includes(s.status)||s.source_date&&s.source_date!==r.date)) {r.score=null;r.selection=null;r.strategy_pending='待核對三個專家來源';continue}
  r.score=sources.filter(s=>s.horses?.length).length;
  const mt=r.tips?.meiji;
  if(r.score>=2&&(mt?.status!=='ready'||mt.source_date&&mt.source_date!==r.date||mt.horses?.length<3)){r.selection=null;r.strategy_pending='待明治朗當日貼士';continue}
  chooseManual(r);
 }
 return m;
}
export function currentPlan(r,now=Date.now()){
 const method=METHODS.find(m=>m.kind==='current'&&applies(m,r));
 if(r.locked||Date.parse(r.off)<=now)return{state:'closed',reason:r.selection?'已開跑／鎖定，不產生新買法':'已開跑；賽前資料不足，沒有鎖定買法',method};
 if(!method)return{state:'pending',reason:r.strategy_pending||'待確認場地及H',method};
 if(r.strategy_pending||r.hv_plan_state==='pending'||r.st_plan_state==='pending')return{state:'pending',reason:r.strategy_pending||r.hv_plan_reason||r.st_plan_reason,method};
 if(r.hv_plan_state==='skip'||r.st_plan_state==='skip'||!method.pool)return{state:'skip',reason:r.hv_plan_reason||r.st_plan_reason||method.rule,method};
 const picks=(r.selection?.horses||[]).map(h=>Number(h.no));
 const withdrawn=new Set([...(r.scratched||[]),...(r.result?.withdrawn||[])].map(Number));
 if(!picks.length||picks.some(n=>withdrawn.has(n)||!r.horses.some(h=>Number(h.no)===n)))return{state:'pending',reason:'所選馬退出或資料未齊，待主頁重新確認',method};
 const pairs=method.pool==='QP'?picks.flatMap((n,i)=>picks.slice(i+1).map(x=>[n,x])):picks.map(n=>[n]);
 return{state:'ready',method,picks,pool:method.pool,tickets:pairs,cost:10*pairs.length};
}
export function drawRanking(r,seed,history,index,minStarts=1){
 const pending=reason=>({status:'pending',reason,draws:[]});
 if(r.track!=='TURF')return pending('檔位研究只限草地');
 if(!seed||r.date<seed.before_date)return pending('目標日期早於檔位基準，不能使用未來資料');
 const key=[r.venue,r.distance,r.rail].join('|'),stats=structuredClone(seed.groups[key]||{}),seen=new Set();
 const additions=(history?.races||[]).filter(x=>x.date>=seed.before_date&&x.date<r.date);
 for(const x of additions){const id=[x.date,x.venue,x.race].join('|');if(seen.has(id))return pending('檔位往績出現重複場次');seen.add(id);
  if(x.track!=='TURF'||[x.venue,x.distance,x.rail].join('|')!==key)continue;
  if(x.runners?.some(h=>!h.draw||typeof h.top3!=='boolean'))return pending('檔位往績不完整');
  for(const h of x.runners){const a=stats[h.draw]??=[0,0];a[0]+=Number(h.top3);a[1]++}
 }
 for(const m of index?.meetings||[])if(m.complete&&m.date>=seed.before_date&&m.date<r.date){const got=additions.filter(x=>x.date===m.date&&x.venue===m.venue);if(!got.length||m.races&&got.length<m.races)return pending('待補齊較新賽日的檔位往績')}
 const active=r.horses.filter(h=>!(r.scratched||[]).includes(h.no));
 if(active.some(h=>!Number.isInteger(h.draw)))return pending('待最新出賽檔位');
 const draws=[...new Set(active.map(h=>h.draw))].map(draw=>({draw,placed:stats[draw]?.[0]||0,starts:stats[draw]?.[1]||0})).filter(x=>x.starts>=minStarts).map(x=>({...x,rate:x.placed/x.starts})).sort((a,b)=>b.rate-a.rate||b.starts-a.starts||a.draw-b.draw).slice(0,3);
 return{status:'ready',draws,minStarts,before_date:r.date};
}
export function researchPlans(r,{seed,history,index,odds={},now=Date.now()}={}){
 const plans=[];
 if(r.locked||Date.parse(r.off)<=now||r.score==null)return plans;
 const M=r.tips?.meiji,B=r.banker_initial,validM=M?.status==='ready'&&(!M.source_date||M.source_date===r.date);
 const d=drawRanking(r,seed,history,index),d8=drawRanking(r,seed,history,index,8);
 const active=n=>r.horses.some(h=>h.no===n)&&!(r.scratched||[]).includes(n);
 for(const method of METHODS.filter(m=>m.kind==='research'&&applies(m,r))){
  const pending=reason=>plans.push({method,state:'pending',reason});
  if(method.id==='hvcover1'){
   const c=hvWinCandidates(r,r.hv_win_support);
   if(c.status!=='ready'){pending(c.reason||'待四位作者及往績資料');continue}
   if(!c.candidates.length){plans.push({method,state:'skip',reason:'資料已核對，沒有符合休後／回勇及作者條件的補Win馬'});continue}
   const q=coldWinSelect(c,odds);
   if(q.status==='awaiting_odds'){plans.push({method,state:'odds',candidates:c.candidates.map(h=>h.no),reason:'待賽前獨贏賠率>8確認；未列入投注額'});continue}
   plans.push({method,state:q.picks.length?'ready':'skip',picks:q.picks.map(h=>h.no),candidates:c.candidates.map(h=>h.no),cost:q.picks.length*10,reason:q.picks.length?'符合條件；屬研究加注':'賠率未高於8，不買'});continue
  }
  if(!validM){pending('待明治朗當日原次序');continue}
  const rank=method.id==='m2d8'?d8:d;
  if(rank.status!=='ready'){pending(rank.reason);continue}
  let candidates;
  if(method.id.startsWith('m2'))candidates=M.horses[1]?[Number(M.horses[1].no)]:[];
  else if(method.id.startsWith('stcold'))candidates=M.horses[0]?[Number(M.horses[0].no)]:[];
  else {
   if(B?.status!=='ready'||B.date!==r.date||B.venue!==r.venue||B.race!==r.race||B.as_of_race_no!==0||B.reason!=='initial'||B.numbers?.length!==5){pending('待同場膽拖初版');continue}
   candidates=M.horses.map(h=>Number(h.no)).filter(n=>B.numbers.map(Number).includes(n));
  }
  candidates=[...new Set(candidates)].filter(active).filter(n=>rank.draws.some(d=>d.draw===r.horses.find(h=>h.no===n).draw));
  if(method.id==='m2dj'){
   const j=r.draw_top5;
   if(j?.status!=='ready'||j.method_version!=='jockey_draw_only_v3'||j.before_date!==r.date){pending('待同檔騎師榜');continue}
   if(j.riders.some(x=>{const h=r.horses.find(h=>h.no===x.no);return !h||h.draw!==x.draw||h.jockey_id&&x.jockey_id&&h.jockey_id!==x.jockey_id})){pending('騎師榜與最新排位不符');continue}
   candidates=candidates.filter(n=>j.riders.some(x=>x.no===n));
  }
  if(!candidates.length){plans.push({method,state:'skip',reason:'沒有馬匹符合檔位／交集條件'});continue}
  const priceCandidates=[...candidates];
  if(method.id.startsWith('stcold')||method.id==='hvcommon2'){
   if(candidates.some(n=>!Number.isFinite(Number(odds[n]))||Number(odds[n])<=0)){plans.push({method,state:'odds',candidates,reason:'待賽前獨贏賠率>8確認；未列入投注額'});continue}
   candidates=candidates.filter(n=>Number(odds[n])>8).slice(0,2);
  }
  plans.push({method,state:candidates.length?'ready':'skip',picks:candidates,candidates:priceCandidates,cost:candidates.length*10,reason:candidates.length?'符合條件；屬研究加注':'賠率未高於8，不買'});
 }
 // Existing Sha Tin supplement stays separate from the >150% catalogue.
 if(r.venue==='ST'&&confidenceReason(r)){
  const c=coldWinSelect(coldWinCandidates(r,r.st_win_support,Boolean(confidenceReason(r))),odds);
  plans.push({method:{id:'existing-cover',title:'現有沙草信心場補Win',kind:'addon',n:0,hits:0,pool:'W'},state:c.status==='ready'?(c.picks.length?'ready':'skip'):'pending',picks:c.picks?.map(h=>h.no)||[],cost:(c.picks?.length||0)*10,reason:c.reason||'補Win候選或賠率待確認；未提供此組未來勝率'});
 }
 return plans;
}

