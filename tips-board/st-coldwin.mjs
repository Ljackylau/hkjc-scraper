// Independent add-on. Never changes the existing selections or confidence rules.
export const ST_WIN_METHOD='st-turf-coldwin-v1';
export const HV_WIN_METHOD='hv-confidence-coldwin-v1';
export const AUTHORS=['西門獨','諸葛數','陳志懷','兆文'];
const validDate=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||'');
export function coldWinCandidates(r,support,isConfidence){return candidatesFor(r,support,isConfidence,'ST',ST_WIN_METHOD)}
export function hvWinCandidates(r,support){return candidatesFor(r,support,r.score===1,'HV',HV_WIN_METHOD)}
function candidatesFor(r,support,isConfidence,venue,method){
 if(r.venue!==venue||r.track!=='TURF'||!isConfidence)return{status:'not_applicable',candidates:[]};
 const pending=reason=>({status:'pending',reason,candidates:[]});
 if(!support||support.method!==method||support.date!==r.date||support.race!==r.race||support.venue!==venue)return pending('待補Win賽前資料');
 const m=r.tips?.meiji,b=r.banker_initial;
 if(m?.status!=='ready'||m.horses?.length!==4||m.source_date&&m.source_date!==r.date||b?.status!=='ready'||b.as_of_race_no!==0||b.reason!=='initial'||b.date!==r.date||b.venue!==venue||b.race!==r.race||b.numbers?.length!==5)return pending('待明治朗及膽拖初版');
 if(support.captured_at&&Date.parse(support.captured_at)>=Date.parse(r.off))return pending('補Win資料在開跑後才取得，不作賽前推介');
 if(support.status!=='ready'||AUTHORS.some(a=>support.authors?.[a]?.status!=='ready'))return pending('待四位作者及往績資料齊全');
 const core=new Set([...m.horses.map(h=>Number(h.no)),...b.numbers.map(Number)]),scratched=new Set((r.scratched||[]).map(Number));
 const candidates=[];
 for(const h of r.horses){
  const no=Number(h.no);if(core.has(no)||scratched.has(no))continue;
  const authors=AUTHORS.flatMap(a=>{const list=support.authors[a].numbers.map(Number),rank=list.indexOf(no);return rank<0?[]:[{name:a,rank:rank+1}]});
  if(!authors.length)continue;
  const f=support.forms?.[no];
  if(!f||f.status!=='ready')return pending('部分候選馬往績未齊，暫不排名');
  if(f.style_n<2)continue;
  if(!validDate(f.last_date)||f.last_date>=r.date)return pending('候選馬往績日期未能核對');
  const gap=Math.round((Date.parse(r.date+'T00:00:00Z')-Date.parse(f.last_date+'T00:00:00Z'))/86400000);
  if(!Number.isFinite(f.median)||f.style_n<2||f.median<4)continue;
  const branch=gap>=60?'A':gap<60&&Number.isFinite(f.last_finish)&&f.last_finish<=3&&authors.length>=2?'B':null;
  if(branch)candidates.push({no,name:h.name,authors,support_count:authors.length,best_rank:Math.min(...authors.map(a=>a.rank)),branch,gap,median:f.median,style_n:f.style_n});
 }
 candidates.sort((a,b)=>b.support_count-a.support_count||a.best_rank-b.best_rank||a.no-b.no);
 return{status:'ready',candidates};
}
export function coldWinSelect(candidates,odds){
 if(candidates.status!=='ready')return{...candidates,picks:[]};
 // Every candidate needs a price: do not promote a lower-ranked horse while a
 // higher-ranked candidate has an unknown price. Filter first, then cap at two.
 const unknown=candidates.candidates.filter(h=>!Number.isFinite(Number(odds?.[h.no]))||Number(odds[h.no])<=0);
 if(unknown.length)return{...candidates,status:'awaiting_odds',unknown:unknown.map(h=>h.no),picks:[]};
 return{...candidates,picks:candidates.candidates.filter(h=>Number(odds[h.no])>8).slice(0,2).map(h=>({...h,odds:Number(odds[h.no])}))};
}

