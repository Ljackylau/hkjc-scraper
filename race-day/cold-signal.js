/* Frozen trainer quotes: fresh read, post-previous-race publication. */
(function(root){
 const policy='post_previous_off_receipt120_v3',cache=new Map(),clean=x=>String(x||'').replace(/\s+/g,'');
 function calculate(tip,rows){
  const answer={cold:[],cold_status:'unavailable',cold_policy:policy},fail=cold_reason=>({...answer,cold_reason});
  if(Number(tip.race)===1)return {...answer,cold_status:'ready'};
  const freeze=Date.parse(tip.freeze);
  const history=rows.filter(r=>r.received_at&&Date.parse(r.received_at)<=freeze).sort((a,b)=>Date.parse(a.received_at)-Date.parse(b.received_at));
  const latest=history.at(-1);if(!latest)return fail('截止前沒有練王讀取紀錄');
  if(freeze-Date.parse(latest.received_at)>120000)return fail('截止前120秒內未成功讀取練王報價');
  if(latest.state!=='observed')return fail('練王暫停受注或未有可讀報價');
  const previous=(latest.race_context||[]).find(r=>Number(r.race_number)===Number(tip.race)-1);
  if(!previous)return fail('缺上一場開跑時間');
  const off=Date.parse(previous.post_time),source=Date.parse(latest.source_updated_at);
  if(!(off<source&&source<=Date.parse(latest.received_at)))return fail('上一場後未有更新報價');
  const baseline=history.filter(r=>Date.parse(r.received_at)<=off).at(-1);
  if(!baseline)return fail('缺上一場開跑前的比較報價');
  if(baseline.state!=='observed'||!baseline.source_updated_at||Date.parse(baseline.source_updated_at)>Date.parse(baseline.received_at)||off-Date.parse(baseline.received_at)>120000)return fail('缺上一場開跑前120秒內的有效比較報價');
  const identity=r=>JSON.stringify((r.participants||[]).map(p=>[String(p.selection_id??p.name),clean(p.name)]).sort());
  if(!(latest.participants||[]).length||identity(latest)!==identity(baseline))return fail('練王選項不完整或前後不一致');
  const old=new Map(baseline.participants.map(p=>[clean(p.name),p.current_odds])),current=new Map(latest.participants.map(p=>[clean(p.name),p.current_odds]));
  const trainers=new Map((tip.runner_rows||[]).map(r=>[Number(r[0]),clean(r[6])])),cold=[];
  for(const horse of (tip.market||[]).slice(0,5)){
   const name=trainers.get(Number(horse)),a=old.get(name),b=current.get(name);
   if(!name||typeof a!=='number'||typeof b!=='number'||!(a>1&&b>1))return fail('市場頭5練馬師缺可比較數字報價');
   if(100*(a-b)/a>=15)cold.push(horse);
  }
  return {...answer,cold_status:'ready',cold,cold_source_updated_at:latest.source_updated_at,cold_received_at:latest.received_at,cold_quote_age_seconds:(freeze-source)/1000,cold_receipt_age_seconds:(freeze-Date.parse(latest.received_at))/1000,cold_baseline_source_updated_at:baseline.source_updated_at,cold_baseline_received_at:baseline.received_at};
 }
 async function update(tip,base,phase){
  if(tip.cold_policy===policy)return tip;
  const key=[tip.date,tip.race,tip.freeze].join('/');if(cache.has(key))return {...tip,...cache.get(key)};
  try{
   const response=await fetch(`${base}/hkjc-${phase}/challenge/tnc.jsonl`,{cache:'no-store',signal:AbortSignal.timeout(15000)});
   if(!response.ok)return {...tip,cold_status:'unavailable',cold_reason:'練王歷史資料暫未發布'};
   const answer=calculate(tip,(await response.text()).trim().split('\n').filter(Boolean).map(JSON.parse));
   if(answer.cold_status==='ready')cache.set(key,answer);return {...tip,...answer};
  }catch(e){return {...tip,cold_status:'unavailable',cold_reason:'練王歷史資料讀取失敗，稍後自動重試'}}
 }
 function text(tip,horse=n=>`${n}號`){
  if(tip.cold_status!=='ready')return `無法判定：${tip.cold_reason||'缺有效報價'}`;
  const value=(tip.cold||[]).map(horse).join('、')||'無';
  return value+(tip.cold_quote_age_seconds>120?`（報價發布距今：${Math.round(tip.cold_quote_age_seconds)}秒）`:'');
 }
 const api={calculate,update,text};if(typeof module!=='undefined')module.exports=api;else root.ColdSignal=api;
})(typeof window==='undefined'?globalThis:window);
