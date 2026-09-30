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

const trainerLineCache=new Map(),trainerLineData=new Map();
async function refreshTrainerRaceSignals(phases,root,requested){
 const folders=phases.filter(Boolean);
 const groups=await Promise.all(folders.map(async phase=>{
  const key=root+'/'+phase.phase;
  try{
   let archive=trainerLineCache.get(key);
   if(!archive){const r=await fetch(`${key}/challenge/tnc.jsonl`,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('缺少原始報價');archive=(await r.text()).trim().split('\n').filter(Boolean).map(JSON.parse);if(trainerLineCache.size>30)trainerLineCache.clear();trainerLineCache.set(key,archive)}
   const r=await fetch(`${key}/status.json`,{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('缺少場次時間');const status=await r.json();
   return Object.entries(status.races||{}).map(([n,state])=>{
    const cutoff=Date.parse(state.target),start=cutoff-240000;
    const samples=archive.filter(x=>Date.parse(x.received_at)>=start&&Date.parse(x.received_at)<=cutoff&&x.state==='observed').sort((a,b)=>Date.parse(a.received_at)-Date.parse(b.received_at));
    if(samples.length<2)return {number:Number(n),error:'T−7 至 T−3 缺少足夠報價，暫不繪圖。'};
    const prior=archive.filter(x=>Date.parse(x.received_at)<=start&&Date.parse(x.received_at)>=start-120000&&x.state==='observed').sort((a,b)=>Date.parse(b.received_at)-Date.parse(a.received_at))[0];
    const baseline=prior||samples[0],opening=Object.fromEntries((baseline.participants||[]).filter(p=>!p.is_other&&Number(p.current_odds)>0).map(p=>[p.selection_id,Number(p.current_odds)]));
    const labels=Object.fromEntries((baseline.participants||[]).map(p=>[p.selection_id,p.name]));
    let points=samples.map(sample=>({time:Date.parse(sample.received_at),received:sample.received_at,scores:Object.fromEntries((sample.participants||[]).filter(p=>!p.is_other&&opening[p.selection_id]&&Number(p.current_odds)>0).map(p=>[p.selection_id,Math.max(0,100*(opening[p.selection_id]-Number(p.current_odds))/opening[p.selection_id])]))}));
    const qualifying=new Set(Object.entries(points.at(-1).scores).filter(([,v])=>v>0).map(([h])=>h));points=points.map(p=>({...p,scores:Object.fromEntries(Object.entries(p.scores).filter(([h])=>qualifying.has(h)))}));
    return {number:Number(n),data:{points,cutoff,lastReceived:points.at(-1).received,labels,unit:'%',trainer:true},lateStart:!prior,stale:samples.some(s=>!s.source_recent)};
   });
  }catch(e){return (phase.phase_races||[]).map(n=>({number:n,error:e.message}))}
 }));
 if(requested!==selected||$('challenge').hidden)return;
 const rows=groups.flat().sort((a,b)=>a.number-b.number),choice=$('trainerRaceSelect').value;
 $('trainerRaceSelect').innerHTML='<option value="all">全部場次</option>'+rows.map(r=>`<option value="${r.number}">R${r.number}</option>`).join('');$('trainerRaceSelect').value=rows.some(r=>String(r.number)===choice)?choice:'all';
 $('trainerRaceCards').innerHTML=rows.map(r=>{const id='trainer'+r.number;if(r.data)trainerLineData.set(id,r.data);return `<div class="card trainer-race" data-race="${r.number}"><h3>R${r.number}｜練馬師王賠率縮短 %</h3>${r.stale?'<p class="bad">區間內部分來源報價偏舊；折線只代表當時已收到的資料。</p>':''}${r.lateStart?'<p class="muted">缺少 T−7 起點，使用區間首筆報價作基準。</p>':''}<div class="market-line-chart" id="${id}">${r.data?MarketLines.chart(r.data,id):`<p class="muted">${esc(r.error)}</p>`}</div></div>`}).join('')||'<p class="muted">未有練馬師王區間資料。</p>';
 filterTrainerRaces();
}
// Legend interactions stay local to the displayed numeric archive.
document.addEventListener('click',e=>{const b=e.target.closest('#trainerRaceCards [data-line-horse]');if(!b)return;const id=b.dataset.lineChart,data=trainerLineData.get(id);if(!data)return;MarketLines.toggle(id,b.dataset.lineHorse);document.getElementById(id).innerHTML=MarketLines.chart(data,id)});
