import {resolveDataSource,freshJson} from './data-source.mjs?v=20261020-mobile-sync';
import {METHODS,roi,rate,venueName,metric,interval,nextMeeting,prepareMeeting,currentPlan,researchPlans,drawRanking} from './strategy-model.mjs?v=20261021-support';
const $=id=>document.getElementById(id),e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const percent=n=>n==null?'—':(n*100).toFixed(1)+'%',money=n=>'$'+Number(n).toLocaleString('en-HK',{maximumFractionDigits:1}),signed=n=>(n>0?'+':'')+money(n);
const clock=s=>new Date(s).toLocaleTimeString('en-GB',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit'});
let source=null,context={},loading=false;
function evidence(m){if(!m?.n)return '<span class="muted">無歷史樣本</span>';const ci=interval(m.hits,m.n);return `<span class="rate-value">${percent(rate(m))}</span>${e(metric(m))}<small>${m.hits}/${m.n}${e(m.unit||'注')} · 歷史樣本<br>95%參考區間 ${percent(ci[0])}–${percent(ci[1])}</small>`}
function catalog(){
 const v=$('venue-filter').value,h=$('h-filter').value,k=$('kind-filter').value;
 let list=METHODS.filter(m=>(v==='all'||v===m.venue+':'+m.track)&&(h==='all'||m.h==='all'||String(m.h)===h)&&(k==='all'||k==='current'&&m.kind==='current'||k==='high'&&roi(m)>1.5));
 const byROI=(a,b)=>(roi(b)??-Infinity)-(roi(a)??-Infinity);
 list.sort($('sort-filter').value==='roi'?byROI:$('sort-filter').value==='sample'?(a,b)=>b.n-a.n:((a,b)=>(a.venue==='HV'?0:a.track==='TURF'?1:2)-(b.venue==='HV'?0:b.track==='TURF'?1:2)||(a.h==='all'?4:a.h)-(b.h==='all'?4:b.h)||byROI(a,b)));
 $('catalog-count').textContent=`${list.length}個方法 · 全部H研究列與對應H子組可能重疊`;
 $('method-rows').innerHTML=list.length?list.map(m=>`<tr><td><b>${e(venueName(m))}</b><small>${m.h==='all'?'全部H合併':'H='+m.h}</small></td><td><b>${e(m.title)}</b><small>${e(m.rule)}</small></td><td><span class="tag ${m.kind==='research'?'study':''}">${m.kind==='current'?'現行主買法':'研究候選'}</span><br>${e(m.pool||'不下注')}</td><td>${m.n?m.hits+' / '+m.n+m.unit:'無下注樣本'}</td><td>${m.n?percent(rate(m)):'—'}<small>${m.n?e(metric(m)):''}</small></td><td>${money(m.cost)}</td><td class="${m.profit<0?'negative':'positive'}">${m.cost?signed(m.profit):'—'}</td><td class="${roi(m)>0?'positive':roi(m)<0?'negative':''}">${percent(roi(m))}${roi(m)>1.5?'<br><span class="tag high">&gt;150%</span>':''}</td><td>${m.n===0?'無樣本，不估勝率':m.n<10?'小樣本（少於10）':'歷史探索，待前測'}${m.h==='all'?'<small>不可當作相同H的獨立勝率</small>':''}</td></tr>`).join(''):'<tr><td colspan="9">沒有符合篩選的規律</td></tr>';
}
function horse(r,no){const h=r.horses.find(h=>Number(h.no)===Number(no));return e(no+'. '+(h?.name||'未核對馬名'))}
function ticketHtml(r,p){return `<b>${p.pool} · ${p.picks.map(n=>horse(r,n)).join(' ＋ ')}</b><small>${p.tickets.map(c=>c.join('–')).join('、')} · 每組$10 · 共${money(p.cost)}</small>`}
const signature=r=>r.horses.map(h=>[h.no,h.draw,h.jockey_id].join(':')).join('|')+'#'+(r.scratched||[]).join(',');
const oddsKey=r=>'hkjc-strategy-odds-v1:'+r.date+':'+r.venue+':'+r.race;
function savedOdds(r){try{const s=JSON.parse(localStorage.getItem(oddsKey(r))||'null');return s&&s.signature===signature(r)&&Date.parse(s.at)<Date.parse(r.off)&&Date.now()-Date.parse(s.at)<600000?s.odds:{}}catch{return {}}}
function savedManual(m){try{return JSON.parse(localStorage.getItem('hkjc-manual-tips-v1:'+m.date+':'+m.venue)||'null')}catch{return null}}
function renderPlan(){
 if(!source)return;
 const now=Date.now(),meeting=nextMeeting([source],now);
 if(!meeting){$('next-title').textContent='尚未有下一賽日的完整賽程';$('plan-rows').innerHTML='<tr><td colspan="5" class="no-plan">最新保存的賽日已全部開跑，或未提供未開跑場次。待網站更新下一賽日；不沿用舊馬號推介。</td></tr>';$('main-budget').textContent=$('extra-budget').textContent=$('total-budget').textContent='$0';return}
 const prepared=structuredClone(meeting);
 for(const r of prepared.races){
  const s=context.support;
  if(s?.date===prepared.date&&s.venue===prepared.venue&&s.races?.[r.race]&&!r.hv_win_support)r.hv_win_support=s.races[r.race];
 }
 const m=prepareMeeting(prepared,savedManual(prepared),now),mainTickets=new Set(),extraTickets=new Set();
 $('next-title').textContent=m.date+' · '+(m.venue==='HV'?'跑馬地':'沙田')+' · 每場買法';
 $('plan-rows').innerHTML=m.races.map(r=>{
  const p=currentPlan(r,now),plans=researchPlans(r,{...context,odds:savedOdds(r),now}),d=drawRanking(r,context.seed,context.history,context.index),key=ns=>[r.date,r.venue,r.race,...ns].join('|');
  if(p.state==='ready')p.tickets.forEach(t=>mainTickets.add(key([p.pool,...t.sort((a,b)=>a-b)])));
  const displayedWin=new Set();
  const research=plans.map(q=>{
   if(q.state==='ready')for(const n of q.picks)extraTickets.add(key(['W',n]));
   const fresh=q.state==='ready'?q.picks.filter(n=>!displayedWin.has(n)):[];
   if(q.state==='ready')q.picks.forEach(n=>displayedWin.add(n));
   let bet=q.state==='ready'?`<b>W · ${q.picks.map(n=>horse(r,n)).join('、')} · ${fresh.length?money(fresh.length*10):'已在上列，只買一注、不另加注'}</b>`:q.state==='odds'?q.candidates.map(n=>horse(r,n)).join('、')+' · 待賠率':e(q.reason);
   return `<div class="study-plan"><span class="tag study">${q.state==='ready'?(fresh.length?'研究加注':'同馬重疊'):q.state==='odds'?'待價格':q.state==='skip'?'未觸發':'待資料'}</span><b>${e(q.method.title)}</b><small>${bet}</small>${q.method.n&&(q.state==='ready'||q.state==='odds'||q.candidates?.length)?`<div class="study-metrics" aria-label="研究方法歷史績效"><div><span>命中率</span><strong>${percent(rate(q.method))}</strong></div><div><span>Expected ROI</span><strong>${percent(roi(q.method))}</strong></div></div><small>${q.method.hits}/${q.method.n}注 · 歷史勝出率及回測ROI${q.method.h==='all'?' · 全H合併參考':''}；非本場校準預測</small>`:''}</div>`;
  }).join('')||'<span class="muted">此場地／H沒有上述高ROI研究可配對</span>';
  const needsOdds=[...new Set(plans.filter(q=>['odds','ready','skip'].includes(q.state)&&(q.method.id.startsWith('stcold')||['hvcommon2','hvcover1'].includes(q.method.id))).flatMap(q=>q.candidates||q.picks||[]))],odds=savedOdds(r);
  const oddsForm=needsOdds.length?`<form class="odds-form" data-race="${r.race}">${needsOdds.map(n=>`<label>${horse(r,n)}<input name="${n}" type="number" min="0.1" step="0.1" inputmode="decimal" value="${e(odds[n]||'')}" aria-label="第${r.race}場${n}號獨贏賠率" required></label>`).join('')}<button type="submit">核實賠率並更新研究買法</button><small>只存此瀏覽器，10分鐘後須重核；8.0不入選。</small></form>`:'';
  return `<tr><td><b>第${r.race}場</b><small>${clock(r.off)} · ${r.distance||'—'}米<br>${e(r.rail||r.track||'—')} · H=${r.score??'待確認'}</small>${r.manual_local?'<span class="tag">本機手動貼士</span>':''}</td><td>${p.state==='ready'?ticketHtml(r,p):`<span class="tag ${p.state==='pending'?'wait':''}">${p.state==='pending'?'待資料':p.state==='closed'?'已開跑':'跳過'}</span><p>${e(p.reason)}</p>`}</td><td>${p.state==='ready'?evidence(p.method):'<span class="muted">未產生買法，不估命中率</span>'}</td><td>${research}</td><td>${d.status==='ready'?d.draws.map((x,i)=>`${i+1}. ${x.draw}檔 · ${x.placed}/${x.starts}（${percent(x.rate)}）`).join('<br>'):`<span class="muted">${e(d.reason)}</span>`}${oddsForm}</td></tr>`;
 }).join('');
 const extras=[...extraTickets].filter(t=>!mainTickets.has(t));
 $('main-budget').textContent=money(mainTickets.size*10);$('extra-budget').textContent=money(extras.length*10);$('total-budget').textContent=money((mainTickets.size+extras.length)*10);
 $('plan-note').textContent='預算只計尚未開跑且已確認的票；跨方法同場同馬同彩池只算一次。現行及研究百分比不能當作整日盈利概率。H或排位更新後會重新匹配。';
 for(const form of document.querySelectorAll('.odds-form'))form.onsubmit=event=>{
  event.preventDefault();const r=m.races.find(r=>r.race===Number(form.dataset.race));
  if(!r||r.locked||Date.now()>=Date.parse(r.off)){alert('本場已開跑，不能再輸入賠率。');renderPlan();return}
  const odds=Object.fromEntries([...new FormData(form)].map(([k,v])=>[k,Number(v)]));
  if(Object.values(odds).some(v=>!Number.isFinite(v)||v<=0))return;
  try{localStorage.setItem(oddsKey(r),JSON.stringify({at:new Date().toISOString(),signature:signature(r),odds}));$('data-error').textContent='';renderPlan()}catch{$('data-error').textContent='無法保存賠率，請容許瀏覽器儲存資料。'}
 };
}
async function load(){
 if(loading||document.activeElement?.tagName==='INPUT')return;loading=true;$('refresh').disabled=true;
 try{
  let saved;try{saved=localStorage.getItem('hkjc-tips-data-revision')}catch{}
  const resolved=await resolveDataSource({saved,fallback:'328365912f76f8262fca5a8adc64c8378b55b263'});
  const results=await Promise.allSettled([freshJson(resolved.base+'latest.json'),freshJson('./strategy-draw-seed.json'),freshJson(resolved.base+'draw-history.json'),freshJson(resolved.base+'history.json'),freshJson('./strategy-support/latest.json')]);
  if(results[0].status!=='fulfilled')throw Error('最新賽程暫時無法讀取');
  source=results[0].value;context={seed:results[1].status==='fulfilled'?results[1].value:null,history:results[2].status==='fulfilled'?results[2].value:null,index:results[3].status==='fulfilled'?results[3].value:null,support:results[4].status==='fulfilled'?results[4].value:null};
  if(!context.history||!context.index)context.seed=null;
  if(resolved.notice.includes('存檔'))throw Error('目前只能讀到備用存檔，暫停新買法；請重新連線核對最新資料。');
  if(resolved.sha)try{localStorage.setItem('hkjc-tips-data-revision',resolved.sha)}catch{}
  $('data-status').textContent='最近保存：'+new Date(source.updated_at).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'})+'（香港時間）'+(resolved.notice?' · '+resolved.notice:'')+(context.seed?' · 檔位往績已載入':' · 檔位往績待連線，現行方法仍可顯示');
  $('data-error').textContent='';renderPlan();
 }catch(err){$('data-error').textContent=err.message;source=null;$('plan-rows').innerHTML='<tr><td colspan="5">未能確認最新資料，暫不提供新下注建議。請按重新讀取。</td></tr>';$('main-budget').textContent=$('extra-budget').textContent=$('total-budget').textContent='—'}
 finally{loading=false;$('refresh').disabled=false}
}
for(const id of ['venue-filter','h-filter','kind-filter','sort-filter'])$(id).onchange=catalog;
$('refresh').onclick=load;window.addEventListener('pageshow',load);window.addEventListener('online',load);window.addEventListener('storage',()=>{if(source)renderPlan()});document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});setInterval(()=>{if(!document.hidden)load()},20000);catalog();load();

