/* Frozen trainer quotes: fresh read, post-previous-race publication. */
(function(root){
 const policy='post_previous_off_receipt120_groups_exclude_banker_v6',cache=new Map(),journals=new Map(),clean=x=>String(x||'').replace(/\s+/g,'');
 async function journal(url){
  if(journals.has(url))return journals.get(url);
  const pending=(async()=>{const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Journal unavailable');return (await r.text()).trim().split('\n').filter(Boolean).map(JSON.parse)})();
  journals.set(url,pending);if(journals.size>24)journals.delete(journals.keys().next().value);
  try{return await pending}catch(e){journals.delete(url);throw e}
 }
 function calculate(tip,rows){
  const answer={cold:[],cold_status:'unavailable',cold_policy:policy,cold_group:[],cold_excluded:[]},fail=cold_reason=>({...answer,cold_reason});
  if(Number(tip.race)===1)return {...answer,cold_status:'ready',cold_note:'首場沒有上一場比較'};
  const freeze=Date.parse(tip.freeze),history=rows.filter(r=>r.received_at&&Date.parse(r.received_at)<=freeze).sort((a,b)=>Date.parse(a.received_at)-Date.parse(b.received_at)),latest=history.at(-1);
  if(!latest)return fail('截止前沒有練王讀取紀錄');
  const context=latest.race_context||[],last=Math.max(...context.map(r=>Number(r.race_number))),penultimate=context.find(r=>Number(r.race_number)===last-1);
  if(Number(tip.race)===last&&penultimate&&Date.parse(penultimate.post_time)<=freeze)return {...answer,cold_status:'ready',cold_applicable:false,cold_note:'本場不適用：練王已於尾二場開跑截止'};
  if(freeze-Date.parse(latest.received_at)>120000)return fail('截止前120秒內未成功讀取練王報價');
  if(latest.state!=='observed')return fail('練王暫停受注或未有可讀報價');
  const previous=context.find(r=>Number(r.race_number)===Number(tip.race)-1);if(!previous)return fail('缺上一場開跑時間');
  const off=Date.parse(previous.post_time),source=Date.parse(latest.source_updated_at);
  if(!(off<source&&source<=Date.parse(latest.received_at)))return fail('上一場後未有更新報價');
  const baseline=history.filter(r=>Date.parse(r.received_at)<=off).at(-1);if(!baseline)return fail('缺上一場開跑前的比較報價');
  if(baseline.state!=='observed'||!baseline.source_updated_at||Date.parse(baseline.source_updated_at)>Date.parse(baseline.received_at)||off-Date.parse(baseline.received_at)>120000)return fail('缺上一場開跑前120秒內的有效比較報價');
  const old=new Map((baseline.participants||[]).filter(p=>!p.is_other).map(p=>[clean(p.name),p])),current=new Map((latest.participants||[]).filter(p=>!p.is_other).map(p=>[clean(p.name),p]));
  const roster=r=>r.selection_roster_complete===true||new Set((r.participants||[]).map(p=>String(p.selection_id))).size===21&&Array.from({length:21},(_,i)=>String(i+1)).every(id=>(r.participants||[]).some(p=>String(p.selection_id)===id));
  const other=r=>(r.participants||[]).find(p=>p.is_other&&String(p.selection_id)==='21'),ga=other(baseline),gb=other(latest),groupOK=!!(ga&&gb&&roster(baseline)&&roster(latest));
  const numeric=x=>typeof x==='number'&&Number.isFinite(x)&&x>1,groupDrop=groupOK&&numeric(ga.current_odds)&&numeric(gb.current_odds)?100*(ga.current_odds-gb.current_odds)/ga.current_odds:null;
  const trainers=new Map((tip.runner_rows||[]).map(r=>[Number(r[0]),clean(r[6])])),cold=[],missing=[],compared=[],groups=[],excluded=[],changes=[];
  const market=(tip.market||[]).slice(0,5);
  for(const horse of market){
   if(tip.banker!=null&&Number(horse)===Number(tip.banker))continue;
   const name=trainers.get(Number(horse)),pa=old.get(name)||{},pb=current.get(name)||{},a=pa.current_odds,b=pb.current_odds,identityOK=String(pa.selection_id??name)===String(pb.selection_id??name);
   if(name&&!old.has(name)&&!current.has(name)&&groupOK){groups.push({horse,trainer:name,selection_id:'21',before_odds:ga.current_odds,current_odds:gb.current_odds,drop_pct:groupDrop,qualifies:groupDrop!==null&&groupDrop>=15,scope:'collective_not_individual'});continue;}
   if(name&&Object.keys(pb).length&&identityOK&&/未能勝出|不能勝出/.test(pb.quote_text||'')){excluded.push({horse,trainer:name,reason:'練王選項已不能勝出；不是馬匹不能勝出'});continue;}
   if(!name||!identityOK||!numeric(a)||!numeric(b)){
    const reason=!Object.keys(pa).length||!Object.keys(pb).length?'缺獨立練王選項':!identityOK?'練王選項前後不一致':'練王缺前後數字報價';
    missing.push({horse,trainer:name||null,reason,before_text:pa.quote_text??null,current_text:pb.quote_text??null});continue;
   }
   compared.push(horse);const drop=100*(a-b)/a;changes.push({horse,trainer:name,before_odds:a,current_odds:b,drop_pct:drop,selection_id:pb.selection_id});if(drop>=15)cold.push(horse);
  }
  const known=!!(compared.length||groups.length||excluded.length||market.length&&market.every(h=>tip.banker!=null&&Number(h)===Number(tip.banker)));
  return {...answer,cold_status:known?'ready':'unavailable',cold,cold_group:groups,cold_excluded:excluded,cold_changes:changes,cold_partial:!!missing.length,cold_missing:missing,cold_compared:compared,...(!known?{cold_reason:'市場頭5全部缺可比較練王報價'}:{}),cold_source_updated_at:latest.source_updated_at,cold_received_at:latest.received_at,cold_quote_age_seconds:(freeze-source)/1000,cold_receipt_age_seconds:Math.round((freeze-Date.parse(latest.received_at))/10)/100,cold_baseline_source_updated_at:baseline.source_updated_at,cold_baseline_received_at:baseline.received_at};
 }
 async function update(tip,base,phase){
  if(tip.cold_policy===policy)return tip;
  const key=[tip.date,tip.race,tip.freeze].join('/');if(cache.has(key))return {...tip,...cache.get(key)};
  try{
   const phases=phase==='all'?['early','late']:[phase];
   const results=await Promise.allSettled(phases.map(p=>journal(`${base}/hkjc-${p}/challenge/tnc.jsonl`)));
   const rows=results.filter(r=>r.status==='fulfilled').flatMap(r=>r.value);
   if(!rows.length)return {...tip,cold_status:'unavailable',cold_reason:'練王歷史資料暫未發布'};
   const answer=calculate(tip,rows);
   if(answer.cold_status==='ready')cache.set(key,answer);return {...tip,...answer};
  }catch(e){return {...tip,cold_status:'unavailable',cold_reason:'練王歷史資料讀取失敗，稍後自動重試'}}
 }
 function text(tip,horse=n=>`${n}號`){
  if(tip.cold_applicable===false)return tip.cold_note;
  const missing=(tip.cold_missing||[]).map(r=>`${r.horse}號`).join('、');
  if(tip.cold_status!=='ready')return `無法判定：${tip.cold_reason||'缺有效報價'}`+(missing?`（資料不足：${missing}）`:'');
  let value=(tip.cold||[]).filter(h=>tip.banker==null||Number(h)!==Number(tip.banker)).map(horse).join('、')||(missing?'無符合（可比較部分）':'無');
  const group=(tip.cold_group||[]).filter(g=>tip.banker==null||Number(g.horse)!==Number(tip.banker)),qualified=group.filter(g=>g.qualifies);
  if(group.length)value+=qualified.length?'；其他組合落飛：'+qualified.map(g=>horse(g.horse)).join('、')+'（組合訊號，非個別練王落飛）':'（其他組合：'+group.map(g=>horse(g.horse)).join('、')+'；沒有個別報價）';
  return value+(missing?`（部分資料不足：${missing}）`:'')+(tip.cold_quote_age_seconds>120?`（報價發布距今：${Math.round(tip.cold_quote_age_seconds)}秒）`:'');
 }
 const api={calculate,update,text};if(typeof module!=='undefined')module.exports=api;else root.ColdSignal=api;
})(typeof window==='undefined'?globalThis:window);
