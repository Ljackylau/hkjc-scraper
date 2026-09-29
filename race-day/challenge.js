// Read-only trainer-king research panel; the underlying numeric archives stay unchanged.
async function refreshChallenges(){
 const requested=selected,root=base();
 const phases=await Promise.all(['hkjc-early','hkjc-late'].map(async phase=>{
  try{const r=await fetch(`${root}/${phase}/challenge/status.json?v=${Math.floor(Date.now()/60000)}`,{cache:'no-store',signal:AbortSignal.timeout(10000)});
   return r.ok?{...await r.json(),phase}:null}catch(e){return null}
 }));
 if(requested!==selected)return;
 const candidates=phases.filter(d=>d?.date===requested&&d.pools?.tnc).sort((a,b)=>Date.parse(b.updated_at)-Date.parse(a.updated_at));
 const phase=candidates[0],s=phase?.pools.tnc;
 if(s){
  const clock=t=>t?new Date(t).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'}):'未知';
  const drops=(s.participants||[]).filter(p=>!p.is_other&&Number(p.opening_drop_pct)>0&&Number.isFinite(Number(p.opening_drop_pct)))
   .sort((a,b)=>Number(b.opening_drop_pct)-Number(a.opening_drop_pct)).slice(0,5);
  const bars=barChart(drops.map(p=>({label:p.name,value:Number(p.opening_drop_pct),display:`${p.opening_drop_pct}%`,detail:`${p.opening_odds} → ${p.current_odds} 倍`})),'最後一次報價未有可比較的縮短賠率。');
  $('challengeCards').innerHTML=`<div class="card"><h3>練馬師王｜${esc(s.state==='observed'?'已保存賠率':s.state==='no_numeric_quotes'?'未有可讀賠率':s.state||'未取得')}</h3>
   <p class="muted">${phase.state==='collecting'&&Date.now()-Date.parse(phase.updated_at)>180000?'超過3分鐘未更新｜':''}收到：${esc(clock(s.received_at))}<br>來源更新：${esc(clock(s.source_updated_at))}</p>
   ${!s.source_recent?'<p class="bad">來源時間偏舊或不明；僅供觀察。</p>':''}
   <p class="bar-meta">開售至最後一次報價；只顯示最大 5 項縮短跌幅。</p>${bars}
   <p><a target="_blank" rel="noopener" href="${root}/${phase.phase}/challenge/tnc.jsonl">原始數字紀錄 ↗</a></p></div>`;
 }else $('challengeCards').innerHTML='<p class="muted">此賽日沒有練馬師王研究紀錄。</p>';
 if(!$('latestChallenge').dataset.initialized){$('latestChallenge').open=phases.some(p=>p?.state==='collecting');$('latestChallenge').dataset.initialized='true'}
 if(!$('challenge').hidden)await refreshTrainerRaceSignals(phases,root,requested);
}

function filterTrainerRaces(){
 const choice=$('trainerRaceSelect').value;
 document.querySelectorAll('#trainerRaceCards .trainer-race').forEach(card=>{card.hidden=choice!=='all'&&card.dataset.race!==choice});
}

async function refreshTrainerRaceSignals(phases,root,requested){
 const raceFolders=new Map();
 for(const phase of phases)for(const number of phase?.phase_races||[])raceFolders.set(Number(number),phase.phase);
 const races=[...raceFolders].filter(([number])=>Number.isInteger(number)&&number>0).sort((a,b)=>a[0]-b[0]);
 if(!races.length){$('trainerRaceCards').innerHTML='<p class="muted">此賽日沒有保存逐場練馬師王比較。</p>';return}
 const rows=await Promise.all(races.map(async([number,folder])=>{
  const rootPath=`${root}/${folder}/challenge/race_${String(number).padStart(2,'0')}`;
  for(const suffix of ['_tnc_movement.json','_tnc_signal.json']){
   const path=rootPath+suffix;
   try{const response=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(10000)});if(response.ok)return {number,path,signal:await response.json()}}catch(e){}
  }
  return {number,signal:null};
 }));
 if(requested!==selected||$('challenge').hidden)return;
 const choice=$('trainerRaceSelect').value;
 $('trainerRaceSelect').innerHTML='<option value="all">全部場次</option>'+races.map(([n])=>`<option value="${n}">R${n}</option>`).join('');
 $('trainerRaceSelect').value=races.some(([n])=>String(n)===choice)?choice:'all';
 const clock=t=>t?new Date(t).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit'}):'未知';
 $('trainerRaceCards').innerHTML=rows.map(({number,path,signal})=>{
  if(!signal)return `<div class="card trainer-race" data-race="${number}"><h3>R${number}</h3><p class="muted">沒有保存逐場 T−3 練馬師王比較。</p></div>`;
  if(signal.status!=='observed')return `<div class="card trainer-race" data-race="${number}"><h3>R${number}</h3><p class="muted">${number===1?'第一場沒有上一場作比較。':'本場沒有足夠的可讀賽前賠率。'}</p></div>`;
  const drops=(signal.changes||[]).filter(x=>Number(x.drop_pct)>0&&Number.isFinite(Number(x.drop_pct)))
   .sort((a,b)=>Number(b.drop_pct)-Number(a.drop_pct)).slice(0,5);
  const bars=barChart(drops.map(x=>({label:x.name,value:Number(x.drop_pct),display:`${x.drop_pct}%`,detail:`${x.before_odds} → ${x.t3_odds} 倍`})),'本場沒有練馬師王賠率縮短。');
  const age=signal.t3_received_at&&signal.t3_source_updated_at?(Date.parse(signal.t3_received_at)-Date.parse(signal.t3_source_updated_at))/60000:null;
  const stale=signal.source_recent===false||age!=null&&age>2;
  return `<div class="card trainer-race" data-race="${number}"><h3>R${number}｜最大 ${drops.length} 項落飛</h3>${stale?'<p class="bad">來源時間偏舊；只供觀察，並非新鮮 T−3 訊號。</p>':''}<p class="bar-meta">上一場來源 ${esc(clock(signal.baseline_source_updated_at))} → 本場來源 ${esc(clock(signal.t3_source_updated_at))}${age!=null?`｜本場報價距接收 ${esc(Math.round(age))} 分鐘`:''}</p>${bars}<a href="${esc(path)}" target="_blank" rel="noopener">原始逐場比較 JSON ↗</a></div>`;
 }).join('');
 filterTrainerRaces();
}
