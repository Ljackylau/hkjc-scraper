// Read-only research panel: no betting or automatic selection changes.
async function refreshChallenges(){
 const requested=selected,root=base();
 const phases=await Promise.all(['hkjc-early','hkjc-late'].map(async phase=>{
  try{const r=await fetch(`${root}/${phase}/challenge/status.json?v=${Math.floor(Date.now()/60000)}`,{cache:'no-store',signal:AbortSignal.timeout(10000)});
   return r.ok?{...await r.json(),phase}:null}catch(e){return null}
 }));
 if(requested!==selected)return;
 const states={observed:'已保存賠率',no_numeric_quotes:'未有可讀賠率',suspended_or_closed:'暫停／截止',retrying:'來源重試中'};
 const cards=[];
 for(const kind of ['jkc','tnc']){
  const candidates=phases.filter(d=>d?.date===requested&&d.pools?.[kind]).sort((a,b)=>Date.parse(b.updated_at)-Date.parse(a.updated_at));
  if(!candidates.length)continue;
  const phase=candidates[0],s=phase.pools[kind];
  const old=Date.now()-Date.parse(phase.updated_at)>180000;
  const clock=t=>t?new Date(t).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'}):'未知';
  const participants=(s.participants||[]).filter(p=>!p.is_other);
  const drop=participants.filter(p=>p.opening_drop_pct!=null&&Number.isFinite(Number(p.opening_drop_pct))).sort((a,b)=>Number(b.opening_drop_pct)-Number(a.opening_drop_pct));
  const odds=participants.filter(p=>p.current_odds!=null&&Number.isFinite(Number(p.current_odds))&&Number(p.current_odds)>0).sort((a,b)=>Number(a.current_odds)-Number(b.current_odds));
  const dropBars=barChart(drop.map(p=>({label:p.name,value:Number(p.opening_drop_pct),display:`${Number(p.opening_drop_pct)>0?'+':''}${p.opening_drop_pct}%`})),'未有開售與現時兩個有效賠率，暫時無法比較跌幅。');
  const oddsBars=barChart(odds.map(p=>({label:p.name,value:1/Number(p.current_odds),display:`${p.current_odds} 倍`})),'未有有效現時賠率。');
  cards.push(`<div class="card"><h3>${kind==='jkc'?'騎師王':'練馬師王'}｜${esc(states[s.state]||s.state)}</h3>
   <p class="muted">工作：${esc(phase.state)}${old?'｜超過3分鐘未更新':''}<br>收到：${esc(clock(s.received_at))}<br>來源更新：${esc(clock(s.source_updated_at))}</p>
   ${!s.source_recent?'<p class="bad">來源時間偏舊或不明；僅存檔，不視為新鮮 T−3 訊號。</p>':''}
   <p class="muted">本次保存 ${esc(s.samples_this_run||0)} 筆；積分：${s.points_available?'已讀取（來源更新時間未能確認）':'未取得／日期未對上'}</p>
   <div class="bar-section"><h4>開售至現時賠率跌幅</h4><p class="bar-meta">棒長按最大絕對變幅比較；橙色代表賠率上升。</p>${dropBars}</div>
   <div class="bar-section"><h4>現時賠率</h4><p class="bar-meta">賠率愈低，棒愈長；數字為原始賠率。</p>${oddsBars}</div>
   <p class="bad">${esc(s.error||'')}</p>
   <p>${phases.filter(d=>d?.pools?.[kind]?.samples_this_run>0).map(d=>`<a target="_blank" rel="noopener" href="${root}/${d.phase}/challenge/${kind}.jsonl">${d.phase==='hkjc-early'?'前':'後'}半場原始紀錄 ↗</a>`).join(' ｜ ')}</p></div>`);
 }
 $('challengeCards').innerHTML=cards.join('')||'<p class="muted">此賽日未有研究紀錄。賽日啟動 Race Day Runner（Run）後一併收集；舊賽日不會補造即時資料。</p>';
 if(!$('challenge').hidden)await refreshJockeyRaceSignals(phases,root,requested);
}

async function refreshJockeyRaceSignals(phases,root,requested){
 const raceFolders=new Map();
 for(const phase of phases)for(const number of phase?.phase_races||[])raceFolders.set(Number(number),phase.phase);
 const races=[...raceFolders].filter(([number])=>Number.isInteger(number)&&number>0).sort((a,b)=>a[0]-b[0]);
 if(!races.length){$('jockeyRaceCards').innerHTML='<p class="muted">此賽日沒有保存逐場騎師王比較。</p>';return}
 const rows=await Promise.all(races.map(async([number,folder])=>{
  const path=`${root}/${folder}/challenge/race_${String(number).padStart(2,'0')}_jkc_signal.json`;
  try{const response=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(10000)});return {number,path,signal:response.ok?await response.json():null}}
  catch(e){return {number,path,signal:null}}
 }));
 if(requested!==selected||$('challenge').hidden)return;
 const time=t=>t?new Date(t).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit'}):'未知';
 $('jockeyRaceCards').innerHTML=rows.map(({number,path,signal})=>{
  if(!signal)return `<div class="card"><h3>R${number}</h3><p class="muted">沒有保存逐場 T−3 騎師王比較，無法重建。</p></div>`;
  if(signal.status!=='observed')return `<div class="card"><h3>R${number}</h3><p class="muted">${number===1?'第一場沒有上一場作比較。':esc(signal.reason||'沒有足夠的賽前報價。')}</p></div>`;
  const bars=barChart((signal.changes||[]).slice(0,5).map(change=>({label:change.name,value:Number(change.drop_pct),display:`${Number(change.drop_pct)>0?'+':''}${change.drop_pct}%`,detail:`${change.before_odds} → ${change.t3_odds} 倍`})));
  const age=`前場來源距開跑 ${Math.round(signal.baseline_age_at_off_seconds/60)} 分鐘；本場來源距接收 ${Math.round(signal.t3_source_age_seconds/60)} 分鐘`;
  return `<div class="card"><h3>R${number}｜最大 5 項變化</h3>${signal.source_recent?'<p class="good">兩個比較時點的來源時間均在 2 分鐘內</p>':'<p class="bad">來源時間偏舊；只供觀察，並非新鮮 T−3 訊號</p>'}<p class="bar-meta">上一場 ${esc(time(signal.baseline_source_updated_at))} → 本場 ${esc(time(signal.t3_source_updated_at))}<br>${esc(age)}</p>${bars}<a href="${path}" target="_blank" rel="noopener">原始逐場比較 JSON ↗</a></div>`;
 }).join('');
}
