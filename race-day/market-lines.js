/* Market score history uses the existing fixed baseline, not rolling odds. */
const MarketLines=(()=>{
 const cache=new Map(),hidden=new Map();
 const colors=['#ff786f','#79cfff','#f6ce69','#96e096','#d5a6ff','#ffac6e','#72e4d2','#efa9d0','#adc7ff','#d4dd79','#b7a59a','#5fc2a6','#e6edf7','#a78cff'];
 const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function scores(base,end){
  const out={};
  for(const h of Object.keys(end.odds?.WIN||{})){
   if(!end.odds?.PLA?.[h])continue;
   let score=0,valid=true;
   for(const [pool,weight] of [['WIN',.35],['PLA',.25],['QIN',.20],['QPL',.20]]){
    const values=[];
    for(const [key,a] of Object.entries(base.odds?.[pool]||{})){
     const b=end.odds?.[pool]?.[key];
     if(!(Number(a)>0&&Number(b)>0))continue;
     if(pool==='WIN'||pool==='PLA'){if(key!==h)continue}
     else if(!key.split('-').includes(h))continue;
     values.push(Math.max(0,Math.min(100,100*(Number(a)-Number(b))/Number(a))));
    }
    if(!values.length){valid=false;break}
    values.sort((a,b)=>b-a);const top=values.slice(0,3);
    const change=Math.round(top.reduce((a,b)=>a+b,0)/top.length*100)/100;
    score+=weight*change;
   }
   out[h]=valid?Math.round(score*1000)/1000:null;
  }
  return out;
 }
 async function load(root,phase,n,state){
  const key=`${root}/${phase}/race_${String(n).padStart(2,'0')}`;
  const cacheKey=`${root.split('/').at(-1)}/${phase}/${n}/${state.received_at||''}`;
  if(cache.has(cacheKey))return cache.get(cacheKey);
  try{
   const read=async suffix=>{const r=await fetch(key+suffix,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('缺少市場快照');return suffix==='.jsonl'?r.text():r.json()};
   const [archive,base,end]=await Promise.all([read('.jsonl'),read('_baseline.json'),read('_t3.json').catch(()=>null)]);
   const baseline=base.snapshot||base,cutoff=Date.parse(state.target);
   if(!Number.isFinite(cutoff))return {error:'尚未有有效 T−3 目標時間'};
   const samples=archive.trim().split('\n').filter(Boolean).map(s=>JSON.parse(s));
   const start=cutoff-240000,off=cutoff+180000;
   const clock=new Date(off).toLocaleTimeString('en-GB',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit'});
   if(baseline.post_time!==clock)return {error:'比較基準開跑時間不符；暫不繪圖'};
   const points=samples.filter(s=>{const t=Date.parse(s.received_at);return t>=start&&t<=cutoff&&s.post_time===clock}).map(s=>({time:Date.parse(s.received_at),received:s.received_at,scores:scores(baseline,s)}));
   points.sort((a,b)=>a.time-b.time);
   const data={points,cutoff,baseline:base.baseline?.minutes_to_off,lastReceived:points.at(-1)?.received};
   if(end&&points.length)cache.set(cacheKey,data);
   if(cache.size>100)cache.clear();
   return data;
  }catch(e){return {error:e.message}}
 }
 function chart(data,id){
  if(data.error)return `<p class="muted">${escape(data.error)}</p>`;
  const points=data.points;if(!points.length)return '<p class="muted">T−7 至 T−3 尚未有已收到的市場快照。</p>';
  const all=[...new Set(points.flatMap(p=>Object.keys(p.scores)))].sort((a,b)=>Number(a)-Number(b));
  const horses=all.filter(h=>{if(!data.noPullback)return true;const values=points.map(p=>p.scores[h]);return values.length>=2&&values.every(v=>v!=null)&&values.every((v,i)=>!i||v>=values[i-1]-1e-9)}),hide=hidden.get(id)||new Set();
  if(!horses.length)return data.trainer?'<p class="muted">此時段沒有末段賠率縮短的練馬師。</p>':'<p class="muted">此時段沒有符合「途中沒有回調」且有足夠觀察點的馬匹。</p>';
  const name=h=>data.labels?.[h]||h+'號';
  const width=720,height=290,left=45,right=665,top=20,bottom=240;
  const max=Math.max(5,...points.flatMap(p=>Object.values(p.scores).filter(v=>v!==null))),ceiling=Math.ceil(max/5)*5;
  const x=t=>left+(t-(data.cutoff-240000))/240000*(right-left),y=v=>bottom-v/ceiling*(bottom-top);
  let svg='';
  for(let i=0;i<=4;i++){const v=ceiling*i/4;svg+=`<line x1="${left}" y1="${y(v)}" x2="${right}" y2="${y(v)}" stroke="#30445c"/><text x="${left-9}" y="${y(v)+4}" text-anchor="end" fill="#aabcce" font-size="12">${v.toFixed(1)}</text>`}
  for(let m=7;m>=3;m--){const xx=x(data.cutoff-(m-3)*60000);svg+=`<text x="${xx}" y="265" text-anchor="middle" fill="#aabcce" font-size="13">T−${m}</text>`}
  for(const [i,h] of horses.entries()){
   const color=colors[i%colors.length];if(hide.has(h))continue;
   // Separate paths at missing observations rather than inventing missing scores.
   const segments=[];let segment=[];for(const p of points){if(p.scores[h]==null){if(segment.length)segments.push(segment);segment=[]}else segment.push(`${x(p.time).toFixed(1)},${y(p.scores[h]).toFixed(1)}`)}if(segment.length)segments.push(segment);
   svg+=segments.map(s=>`<polyline points="${s.join(' ')}" fill="none" stroke="${color}" stroke-width="2.2"/>`).join('');
   for(const p of points)if(p.scores[h]!=null)svg+=`<circle cx="${x(p.time)}" cy="${y(p.scores[h])}" r="3" fill="${color}"><title>${escape(name(h))}｜${p.scores[h].toFixed(3)} ${data.unit||'分'}｜收到 ${escape(new Date(p.received).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong'}))}</title></circle>`;
  }
  const legend=horses.map((h,i)=>{const last=[...points].reverse().find(p=>p.scores[h]!=null)?.scores[h];return `<button data-line-chart="${escape(id)}" data-line-horse="${h}" aria-pressed="${!hide.has(h)}" style="border-color:${colors[i%colors.length]};opacity:${hide.has(h)?.4:1}"><span style="color:${colors[i%colors.length]}">●</span> ${escape(name(h))} <b>${last==null?'—':last.toFixed(1)}</b></button>`}).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="T−7 至 T−3 走勢">${svg}</svg><div class="line-legend">${legend}</div><p class="bar-meta">${data.trainer?'點擊練馬師名稱可顯示／隱藏折線；數值為相對區間起點的賠率縮短百分比。':'點擊馬號可顯示／隱藏折線；只顯示每筆已保存分數均不下降的馬，持平亦符合。'}只顯示 T−7 至 T−3 期間已收到的快照；最後資料 ${escape(new Date(data.lastReceived).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong'}))}，不補造 T−3 端點。</p>`;
 }
 function toggle(id,h){const set=hidden.get(id)||new Set();set.has(h)?set.delete(h):set.add(h);hidden.set(id,set)}
 function golden(data){
  const points=data.points||[];if(points.length<2)return [];
  return Object.keys(points.at(-1).scores).filter(h=>{
   const v=points.map(p=>p.scores[h]);return v.every(x=>x!=null)&&v.at(-1)>=20&&v.every((x,i)=>!i||x>=v[i-1]-1e-9);
  }).sort((a,b)=>points.at(-1).scores[b]-points.at(-1).scores[a]||Number(a)-Number(b)).map(Number);
 }
 return {load,chart,toggle,scores,golden};
})();
