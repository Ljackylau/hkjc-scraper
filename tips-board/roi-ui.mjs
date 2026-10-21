import {freshJson,resolveDataSource} from './data-source.mjs?v=20261020-mobile-sync';
import {mergeManualResults} from './manual-results.mjs?v=20261021-results';
import {choosePolicy,evaluate,preparedRace,settlePolicy,roi,rate,key,compatible} from './roi-policy.mjs?v=roi1';
import {historyRows,summarize} from './strategy-history-model.mjs?v=20261021-history';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),pct=n=>n==null?'—':(n*100).toFixed(1)+'%',money=n=>n==null?'待派彩':(n<0?'−':'')+'$'+Math.abs(n).toLocaleString('en-HK',{maximumFractionDigits:1});
const historyPage=document.body.dataset.history==='true';
let registry=null,replay=null,audit=null,meeting=null,live=null,context={},overlay=null,base='',loading=false,dateRequest=0;
const place=m=>m.venue==='HV'?'谷草':m.venue==='ST'?(m.track==='AWT'?'沙田泥地':'沙田草地'):'跨場研究';
const horse=(r,n)=>esc(n+' '+(r.horses.find(h=>Number(h.no)===Number(n))?.name||''));
const sig=r=>r.horses.map(h=>[h.no,h.draw,h.jockey_id].join(':')).join('|')+'#'+(r.scratched||[]).join(',');
const oddsKey=r=>'hkjc-strategy-odds-v1:'+r.date+':'+r.venue+':'+r.race;
function saved(r,kind){try{const s=JSON.parse(localStorage.getItem(kind==='odds'?oddsKey(r):'hkjc-roi-tx:'+key(r))||'null');return s&&s.signature===sig(r)&&Date.parse(s.at)<Date.parse(r.off)&&(kind!=='odds'||Date.now()-Date.parse(s.at)<600000)?s:null}catch{return null}}
function priorStats(date){return context.prior?.[date]||null}
async function loadPrior(date){context.prior??={};if(context.prior[date])return;try{context.prior[date]=await freshJson('./roi-stats/'+(date>audit.latest_date?'after':date)+'.json')}catch{context.prior[date]={}}}
function catalog(){
 const v=$('catalog-venue').value,h=$('catalog-h').value,cut=$('catalog-cut').value;
 const ms=registry.methods.filter(m=>(v==='all'||m.venue===v)&&(h==='all'||m.h==='all'||String(m.h)===h)&&(cut==='all'||cut==='150'&&roi(m)>1.5||cut==='positive'&&roi(m)>0));ms.sort((a,b)=>(roi(b)??-Infinity)-(roi(a)??-Infinity)||b.n-a.n||a.id.localeCompare(b.id));
 $('catalog-count').textContent=`${ms.length}個方法 · 方法庫${registry.methods.length}個；ROI>150%共${registry.methods.filter(m=>roi(m)>1.5).length}個。樣本重疊，不能相加。`;
 $('method-rows').innerHTML=ms.map(m=>`<tr><td>${esc(place(m))}<small>H=${m.h==='all'?'全部':m.h}</small></td><td><b>${esc(m.title)}</b><small>${esc(m.description||m.source)}</small></td><td>${m.pool}</td><td>${m.hits}/${m.n}${m.unit}</td><td><b>${pct(rate(m))}</b><small>${m.pool==='W'?'勝出':m.pool==='P'?'上名':'至少中一組'}</small></td><td><b>${pct(roi(m))}</b></td><td>${money(m.profit)}</td><td>${m.rule.type==='unavailable'?'未接入原口徑，順延':'已接入條件判斷'}${m.n<10?'<small class="error">少於10個樣本</small>':''}<small>${esc(m.source)}</small></td></tr>`).join('');
}
function render(){
 if(!meeting||!registry)return;
 const mode=$('mode').value,minSamples=Number($('min-samples').value),historical=historyPage||meeting.races.every(r=>r.locked||Date.parse(r.off)<=Date.now());
 $('meeting-title').textContent=meeting.date+' · '+(meeting.venue==='HV'?'跑馬地':'沙田')+(historical?' · 策略回算':' · 最高ROI逐場買法');
 $('policy-note').textContent=mode==='prior'?'排序只用該賽日前累計ROI；規則於10月21日整理，仍存在規則選擇偏差，並非真正盲測。':historical?'固定10月21日方法庫回算；包含事後選規則／排名偏差，不是當日實單。':'按已知歷史ROI降序，符合條件才選；沒有資料／未核實價格便順延。每場只採用一個方法。';
 $('price-note').textContent=historical?'本歷史回算使用官方最終獨贏賠率代理價格門檻；不能當作已保存賽前價。今日天喜首選來自用戶提供，未有獨立賽前時間封存。':'賠率只接受開跑前輸入並保存10分鐘；沒有即時價便順延。天喜可填首選1匹或原序4匹；只填1匹時不套用四選交集規則。';
 let cost=0,returned=0,hits=0,n=0,pending=0;const h=$('h').value,rows=[];
 const baseline=historyRows(meeting);const bsummary=summarize(baseline.filter(x=>h==='all'||String(x.r.score)===h));
 for(const raw of meeting.races){const r=preparedRace(meeting,raw,context);if(h!=='all'&&String(r.score)!==h)continue;
  const closed=r.locked||Date.parse(r.off)<=Date.now(),archived=context.replay.inputs[key(r)],tx=saved(r,'tx');if(!closed&&tx)r.tianxi={numbers:tx.numbers};
  // No final prices enter a live evaluation, even when a replay file exists.
  const odds=closed?archived?.final_odds||{}:saved(r,'odds')?.odds||{};
  const stats=mode==='prior'?priorStats(r.date)||{}:null;
  let snapshot=r.roi_strategy;
  try{const local=JSON.parse(localStorage.getItem('hkjc-roi-snapshot:'+key(r))||'null');if(local?.signature===sig(r)&&Date.parse(local.at)<Date.parse(r.off))snapshot={...local,status:'ready',captured_at:local.at}}catch{}
  const useSnapshot=closed&&mode==='fixed'&&minSamples===1&&snapshot?.version===registry.version&&Date.parse(snapshot.captured_at)<Date.parse(r.off);
  const p=useSnapshot?{...snapshot,attempts:[],reason:snapshot.reason||'已保存的賽前策略'}:choosePolicy(r,registry.methods,{...context,odds,minSamples},stats),s=settlePolicy(p,r.result);
  if(s.cost&&s.returned!==null){cost+=s.cost;returned+=s.returned;n++;hits+=s.status==='hit'}else if(s.status==='pending'){pending++;cost+=s.cost}
  const attempts=p.attempts.map((a,i)=>`<tr><td>${i+1}</td><td>${esc(a.method.title)}</td><td>${pct(roi(a.method))}</td><td>${a.status==='ready'?'採用':esc(a.reason)}</td></tr>`).join('');
  const selected=p.status==='ready'?`<b>${esc(p.method.title)}</b><div class="study-metrics"><div><span>歷史命中率</span><strong>${pct(rate(p.method))}</strong></div><div><span>Expected ROI（歷史回測）</span><strong>${pct(roi(p.method))}</strong></div></div><small>${p.method.hits}/${p.method.n}${p.method.unit} · ${p.method.pool==='W'?'勝出':p.method.pool==='P'?'上名':'至少中一組'}${p.method.n<10?' · 小樣本':''}</small>`:`<b>不買</b><small>${esc(p.reason)}</small>`;
  const bet=p.status==='ready'?`<b>${p.pool} ${p.banker!=null?'膽 '+horse(r,p.banker)+' 拖 ':''}${p.picks.filter(x=>x!==p.banker).map(x=>horse(r,x)).join(' ＋ ')}</b><small>${p.tickets.map(t=>t.join('–')).join('、')} · 每組$10 · 共${money(p.cost)}</small><small>${s.status==='pending'?'尚未結算':'派回 '+money(s.returned)+' · 淨盈虧 '+money(s.profit)}</small>`:'—';
  const res=r.result?.horses?.filter(h=>parseInt(h.placing)<=3).map(h=>`${esc(h.placing)}. ${horse(r,h.no)}`).join('<br>')||'未有官方賽果';
  const needOdds=[...new Set(p.attempts.filter(a=>a.status==='pending'&&a.candidates?.length).flatMap(a=>a.candidates))];
  const inputs=!closed?`<form class="odds-form" data-race="${r.race}">${needOdds.map(no=>`<label>${horse(r,no)} W<input name="odd-${no}" type="number" min="0.1" step="0.1" value="${esc(odds[no]||'')}" inputmode="decimal"></label>`).join('')}<label>天喜首選／原序四選<input name="tx" value="${esc(tx?.numbers?.join(',')||'')}" placeholder="例如 2 或 2,4,6,8"></label><button>核實並重排本場</button><small>資料未齊的高排名方法會順延；不會與已選方法疊加。</small></form>`:'';
  rows.push(`<tr><td><b>第${r.race}場</b><small>${useSnapshot?'賽前已保存':closed?'事後規則回算':'未開跑即時配對'}</small><small>H=${r.score??'待確認'} · ${r.distance||'—'}米<br>${esc(r.rail||r.track)}</small></td><td>${selected}<details><summary>查看排名及順延原因</summary><table><thead><tr><th>序</th><th>方法</th><th>ROI</th><th>判斷</th></tr></thead><tbody>${attempts}</tbody></table></details></td><td>${bet}${inputs}</td><td>${res}</td></tr>`);
  if(!closed&&mode==='fixed'&&minSamples===1&&p.status==='ready'&&Date.now()<Date.parse(r.off))try{localStorage.setItem('hkjc-roi-snapshot:'+key(r),JSON.stringify({version:registry.version,status:'ready',at:new Date().toISOString(),signature:sig(r),method:p.method,pool:p.pool,picks:p.picks,tickets:p.tickets,banker:p.banker,cost:p.cost}))}catch{}
 }
 $('race-rows').innerHTML=rows.join('')||'<tr><td colspan="4">沒有符合H篩選的場次</td></tr>';
 $('stake').textContent=money(cost);$('returned').textContent=money(returned);$('profit').textContent=pending?'待全部結算':money(returned-cost);$('roi').textContent=pending?'待結算':pct(cost?(returned-cost)/cost:null);$('hit-rate').textContent=pct(n?hits/n:null);$('hit-count').textContent=`${hits}/${n}已結算場 · ${pending}待派彩`;
 $('baseline').textContent=`原網站A（只計保存主買法）：投入${money(bsummary.cost)}、派回${money(bsummary.returned)}、淨盈虧${money(bsummary.profit)}，ROI ${pct(bsummary.roi)}。不與新策略相加。`;
 for(const form of document.querySelectorAll('form[data-race]'))form.onsubmit=event=>{
  event.preventDefault();const raw=meeting.races.find(r=>r.race===Number(form.dataset.race)),r=preparedRace(meeting,raw,context);if(r.locked||Date.now()>=Date.parse(r.off)){alert('本場已開跑，不能修改賽前輸入。');return}
  const entries=[...new FormData(form)],odds={...(saved(r,'odds')?.odds||{})};for(const [k,v] of entries)if(k.startsWith('odd-')&&v){const q=Number(v);if(!Number.isFinite(q)||q<=0)return;odds[k.slice(4)]=q}
  const tx=String(entries.find(([k])=>k==='tx')?.[1]||'').trim(),numbers=tx?tx.split(/[,，\s]+/).map(Number):[];
  if(numbers.length&&(![1,4].includes(numbers.length)||new Set(numbers).size!==numbers.length||numbers.some(n=>!r.horses.some(h=>h.no===n)))){alert('天喜請填原首選1匹或原序4匹，馬號不可重複。');return}
  try{const stamp={at:new Date().toISOString(),signature:sig(r)};localStorage.setItem(oddsKey(r),JSON.stringify({...stamp,odds}));if(numbers.length)localStorage.setItem('hkjc-roi-tx:'+key(r),JSON.stringify({...stamp,numbers}));else localStorage.removeItem('hkjc-roi-tx:'+key(r));render()}catch(e){$('error').textContent='無法保存本機輸入：'+e.message}
 };
}
function renderDays(){
 $('day-rows').innerHTML=audit.days.map(d=>`<tr><td><a href="strategy-history.html?date=${d.date}">${d.date}</a><small>${d.venue==='HV'?'跑馬地':'沙田'}</small></td><td>${money(d.cost)}</td><td>${money(d.profit)}</td><td>${pct(d.cost?d.profit/d.cost:null)}</td><td>${d.hits}/${d.n}</td><td>${money(d.walk_profit)}</td><td>${money(d.robust_profit)}</td></tr>`).join('');
 const total=k=>audit.days.reduce((s,d)=>s+(d[k]||0),0),active=audit.days.filter(d=>d.cost),walk=audit.days.filter(d=>d.walk_cost);
 $('day-summary').textContent=`固定排名回算：${active.filter(d=>d.profit>0).length}/${active.length}個下注賽日盈利，淨利${money(total('profit'))}；只用較早賽日排名：${walk.filter(d=>d.walk_profit>0).length}/${walk.length}個下注賽日盈利，淨利${money(total('walk_profit'))}。兩者仍為事後方法庫回算、價格使用最終賠率代理，不能承諾每日盈利。`;
}
async function dateChanged(){const id=++dateRequest;try{const date=$('date').value;let m=replay.meetings.find(m=>m.date===date);if(m)m=await freshJson('./'+m.file);else m=await freshJson(base+date+'.json');if(id!==dateRequest)return;meeting=mergeManualResults(m,overlay);if($('mode').value==='prior')await loadPrior(meeting.date);$('error').textContent='';render();const u=new URL(location.href);u.searchParams.set('date',date);window.history.replaceState(null,'',u)}catch(e){$('error').textContent=e.message}}
async function load(){if(loading||document.activeElement?.tagName==='INPUT')return;loading=true;try{
 const r=await resolveDataSource({fallback:'8c62563d682424b873701d00a4f3dba9e6afefdb'});if(r.notice.includes('存檔'))throw Error('無法核對最新資料，請重新連線');base=r.base;
 const rs=await Promise.allSettled([freshJson('./roi-methods.json'),freshJson('./roi-replay.json'),freshJson('./roi-audit.json'),freshJson(base+'latest.json'),freshJson('./manual-results.json'),freshJson('./strategy-draw-seed.json'),freshJson(base+'draw-history.json'),freshJson(base+'history.json'),freshJson('./strategy-support/latest.json')]);
 for(const i of [0,1,2,3])if(rs[i].status!=='fulfilled')throw Error('策略資料讀取失敗，請重新讀取');
 const get=i=>rs[i].status==='fulfilled'?rs[i].value:null;registry=get(0);replay=get(1);audit=get(2);live=get(3);overlay=get(4);context={replay,seed:get(5),history:get(6),index:get(7),support:get(8)};
 const old=$('date').value,q=new URL(location.href).searchParams.get('date'),dates=[...new Set([...replay.meetings.map(m=>m.date),...(get(7)?.meetings||[]).map(m=>m.date),live.date])].filter(d=>d>='2026-09-01').sort().reverse();
 $('date').innerHTML=dates.map(d=>`<option value="${d}">${d}</option>`).join('');$('date').value=historyPage?(old||q||live.date):live.date;
 if(historyPage)await dateChanged();else{meeting=mergeManualResults(live,overlay);if($('mode').value==='prior')await loadPrior(meeting.date);render()}
 catalog();renderDays();$('status').textContent=`方法庫 ${registry.version} · 歷史統計截至${registry.trained_through} · 最近保存 ${live.updated_at}`;
 }catch(e){$('error').textContent=e.message;meeting=null;$('race-rows').innerHTML='<tr><td colspan="4">未能核對資料，不提供新買法。</td></tr>';for(const id of ['stake','returned','profit','roi','hit-rate','hit-count'])$(id).textContent='—'}finally{loading=false}}
for(const id of ['catalog-venue','catalog-h','catalog-cut'])$(id).onchange=catalog;
for(const id of ['h','min-samples'])$(id).onchange=render;$('mode').onchange=async()=>{if(meeting&&$('mode').value==='prior')await loadPrior(meeting.date);render()};$('date').onchange=dateChanged;$('refresh').onclick=load;
window.addEventListener('pageshow',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});setInterval(()=>{if(!document.hidden&&!historyPage)load()},20000);load();
