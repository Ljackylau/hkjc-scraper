(function(){
 'use strict';
 const el=id=>document.getElementById(id),panel=el('trackBiasEditor');if(!panel)return;
 const escape=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let rows=TrackBias.read(localStorage),date='',races=[],root='',version=0,previews=new Map(),savedConfig=null;
 const contexts=new Map(),checked=new Map();
 const names={inside:'內檔',outside:'外檔',unknown:'未知／重新觀察',neutral:'未見明顯偏差',observe:'觀察更新',watering:'灑水後',rolling:'壓地後',rain:'天雨後',reset:'手動重設',low:'低',medium:'中',high:'高'};
 function render(){
  el('biasDate').textContent=date;
  previews=new Map();
  el('biasHistory').innerHTML=rows.filter(e=>e.date===date).slice().reverse().map(e=>`<li>${escape(e.venue)} ${escape(e.rail)}｜${e.family==='straight1000'?'直路1000':'轉彎1200–1800'}｜R${e.from}–R${e.until}：${escape(names[e.direction])}（信心${escape(names[e.confidence])}）<br><small>${escape(names[e.kind])}；依據${e.evidence.length?e.evidence.map(n=>'R'+n).join('、'):'無'}；${escape(e.note)}<br>編輯時間 ${escape(new Date(e.created_at).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'}))}</small></li>`).join('')||'<li>今日未有手動編輯。</li>';
  el('biasPreviews').innerHTML=races.filter(r=>r.tip).map(r=>{
   const c=contexts.get(`${date}:${r.number}`),event=TrackBias.active(rows,r.tip,c),p=TrackBias.preview(r.tip,event,c);
   if(!event)return '';
   if(p.changed)previews.set(r.number,`R${r.number}｜手動場地調整\n主膽：${p.banker}號\n拖腳：${p.legs.join('、')}\n${p.reason}\n依據R${event.evidence.join('、R')}；${names[event.confidence]}信心；非原Telegram推介`);
   return `<div class="card"><strong>R${r.number}｜手動場地調整</strong><p>${escape(p.reason)}</p><p>原膽 ${escape(p.banker)}號｜原腳 ${escape((r.tip.legs||[]).join('、'))}<br>調整腳 ${escape(p.legs.join('、'))}</p>${p.changed?`<button type="button" data-bias-copy="${r.number}">複製手動調整</button>`:''}<small>依據R${event.evidence.join('、R')||'—'}；${escape(names[event.confidence])}信心。只在本機顯示，正式推介及Telegram仍保留原記錄。</small></div>`;
  }).join('')||'<p class="muted">尚未有符合編輯範圍及截止時間的快照。已鎖定場次不會被事後改寫。</p>';
 }
 function make(kind){
  return TrackBias.validate({version:1,date,venue:el('biasVenue').value,rail:el('biasRail').value,
   family:el('biasFamily').value,direction:kind==='observe'?el('biasDirection').value:'unknown',
   pace:kind==='observe'?el('biasPace').value:'unknown',confidence:kind==='observe'?el('biasConfidence').value:'low',
   from:Number(el('biasFrom').value),until:Number(el('biasUntil').value),kind,
   evidence:kind==='observe'?el('biasEvidence').value.split(/[,，\s]+/).filter(Boolean).map(Number):[],
   note:el('biasNote').value.trim(),created_at:new Date().toISOString()});
 }
 function append(kind){try{
  if(!date)throw Error('請先選擇賽日');
  const event=make(kind);
  if(event.evidence.some(n=>!races.some(r=>r.number===n&&r.completed)))throw Error('依據場次尚未有已公布賽果');
  if(event.evidence.some(n=>!TrackBias.matches(event,contexts.get(`${date}:${n}`))))throw Error('依據須為相同馬場、草地類別及欄位；場地資料未載入時請稍後再試');
  rows=TrackBias.save(localStorage,rows,event);render();
  el('biasMessage').textContent=kind==='observe'?'已保存。本機之後的適用場次會顯示手動調整腳。':'已重設為未知；早段偏差停止沿用，請等新賽果再更新。';
 }catch(e){el('biasMessage').textContent=e.message;}}
 el('biasSave').onclick=()=>append('observe');
 el('biasPreviews').onclick=async e=>{const button=e.target.closest('[data-bias-copy]');if(!button)return;try{await navigator.clipboard.writeText(previews.get(Number(button.dataset.biasCopy)));el('biasMessage').textContent='已複製手動調整，包含依據及信心標記。'}catch{el('biasMessage').textContent='未能複製；請選取上面的調整腳。'}};
 el('biasReset').onclick=()=>append(el('biasResetReason').value);
 el('biasExport').onclick=()=>{const blob=new Blob([JSON.stringify({version:1,events:rows.filter(e=>e.date===date)},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`track-bias-${date}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 el('biasImport').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>1000000)throw Error('檔案過大');const data=JSON.parse(await file.text());if(data.version!==1||!Array.isArray(data.events)||data.events.length>200)throw Error('檔案格式不符');
  // Imported facts are new local edits, never historical proof of a pre-cutoff edit.
  const imported=data.events.map(event=>TrackBias.validate({...event,created_at:new Date().toISOString()}));
  localStorage.setItem(TrackBias.KEY,JSON.stringify([...rows,...imported]));rows=[...rows,...imported];render();el('biasMessage').textContent='已匯入；編輯時間以現在計算，不會補作舊場次賽前調整。';
 }catch(error){el('biasMessage').textContent=error.message;}finally{e.target.value=''}};
 window.TrackBiasEditor={async refresh(config){
  savedConfig=config;
  const token=++version,changed=date!==config.date;date=config.date;races=config.races;root=config.root;
  if(changed){el('biasMessage').textContent='';el('biasEvidence').value='';el('biasNote').value='';el('biasDirection').value='unknown';el('biasPace').value='unknown';el('biasConfidence').value='low';el('biasFrom').value=Math.min(20,Math.max(1,...races.filter(r=>r.completed).map(r=>r.number+1)));}
  render();
  if(!panel.open&&!rows.some(e=>e.date===date))return;
  await Promise.all(races.map(async r=>{const key=`${config.date}:${r.number}`;if(contexts.has(key)||Date.now()-(checked.get(key)||0)<30000)return;checked.set(key,Date.now());try{
   const response=await fetch(`${config.root}/hkjc-${r.number<=5?'early':'late'}/race_${String(r.number).padStart(2,'0')}_cold_history.json`,{cache:'no-store',signal:AbortSignal.timeout(10000)});
   if(!response.ok)return;const c=await response.json();if(c.date!==config.date||c.race!==r.number)return;contexts.set(key,c);
  }catch{}}));
  if(token===version&&date===config.date)render();
 }};
 panel.addEventListener('toggle',()=>{if(panel.open&&savedConfig)window.TrackBiasEditor.refresh(savedConfig)});
})();
