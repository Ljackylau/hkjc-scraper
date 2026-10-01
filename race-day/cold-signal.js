/* Cold candidates from immutable pre-deadline trainer observations. */
(function(root){
 const policy='post_previous_off_max600_v2',cache=new Map();
 const clean=x=>String(x||'').replace(/\s+/g,'');
 function calculate(tip,rows){
  const answer={cold:[],cold_status:'unavailable',cold_policy:policy};
  if(Number(tip.race)===1)return {...answer,cold_status:'ready'};
  const freeze=Date.parse(tip.freeze);
  const history=rows.filter(s=>s.state==='observed'&&s.source_updated_at&&Date.parse(s.received_at)<=freeze&&Date.parse(s.source_updated_at)<=Date.parse(s.received_at));
  const last=history.slice().sort((a,b)=>Date.parse(a.received_at)-Date.parse(b.received_at)).at(-1);
  const previous=(last?.race_context||[]).find(r=>Number(r.race_number)===Number(tip.race)-1);
  if(!previous)return {...answer,cold_reason:'缺上一場開跑時間'};
  const off=Date.parse(previous.post_time);
  const newest=history.filter(s=>Date.parse(s.source_updated_at)>off).sort((a,b)=>Date.parse(a.source_updated_at)-Date.parse(b.source_updated_at)).at(-1);
  if(!newest)return {...answer,cold_reason:'上一場後未有更新報價'};
  const newestAge=Math.round((freeze-Date.parse(newest.source_updated_at))/1000);
  if(newestAge>600)return {...answer,cold_reason:`練王報價已舊${newestAge}秒；上限600秒`};
  const latest=history.filter(s=>Date.parse(s.source_updated_at)>off&&freeze-Date.parse(s.source_updated_at)<=600000).sort((a,b)=>Date.parse(a.source_updated_at)-Date.parse(b.source_updated_at)||Date.parse(a.received_at)-Date.parse(b.received_at)).at(-1);
  const baseline=history.filter(s=>Date.parse(s.received_at)<=off&&Date.parse(s.source_updated_at)<=off&&off-Date.parse(s.source_updated_at)<=600000).sort((a,b)=>Date.parse(a.source_updated_at)-Date.parse(b.source_updated_at)||Date.parse(a.received_at)-Date.parse(b.received_at)).at(-1);
  if(!latest||!baseline)return {...answer,cold_reason:'缺上一場開跑前的有效比較報價'};
  const before=new Map((baseline.participants||[]).map(p=>[clean(p.name),Number(p.current_odds)]));
  const qualifying=new Set((latest.participants||[]).filter(p=>{const a=before.get(clean(p.name)),b=Number(p.current_odds);return a>0&&b>0&&100*(a-b)/a>=15}).map(p=>clean(p.name)));
  const trainers=new Map((tip.runner_rows||[]).map(r=>[Number(r[0]),clean(r[6])]));
  const age=(freeze-Date.parse(latest.source_updated_at))/1000;
  return {...answer,cold_status:'ready',cold:(tip.market||[]).slice(0,5).filter(h=>qualifying.has(trainers.get(Number(h)))),
   cold_source_updated_at:latest.source_updated_at,cold_received_at:latest.received_at,cold_quote_age_seconds:age,cold_baseline_source_updated_at:baseline.source_updated_at};
 }
 async function update(tip,base,phase){
  if(tip.cold_policy===policy&&(tip.cold_status==='ready'||tip.cold_reason))return tip;
  const key=[tip.date,tip.race,tip.freeze].join('/');
  if(cache.has(key))return {...tip,...cache.get(key)};
  try{
   const response=await fetch(`${base}/hkjc-${phase}/challenge/tnc.jsonl`,{cache:'no-store',signal:AbortSignal.timeout(10000)});
   if(!response.ok)return {...tip,cold_reason:'練王歷史資料暫未發布'};
   const rows=(await response.text()).trim().split('\n').filter(Boolean).map(JSON.parse);
   const answer=calculate(tip,rows);if(answer.cold_status==='ready')cache.set(key,answer);
   return {...tip,...answer};
  }catch(e){return {...tip,cold_reason:'練王歷史資料讀取失敗，稍後自動重試'}}
 }
 function text(tip,horse=n=>`${n}號`){
  if(tip.cold_status!=='ready')return `無法判定：${tip.cold_reason||'缺有效報價'}`;
  const value=(tip.cold||[]).map(horse).join('、')||'無';
  return value+(tip.cold_quote_age_seconds>120?`（報價較舊：${Math.round(tip.cold_quote_age_seconds)}秒）`:'');
 }
 const api={calculate,update,text};if(typeof module!=='undefined')module.exports=api;else root.ColdSignal=api;
})(typeof window==='undefined'?globalThis:window);
