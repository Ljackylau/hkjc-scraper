import {freshJson,resolveDataSource} from './data-source.mjs?v=20261020-mobile-sync';
import {mergeManualResults} from './manual-results.mjs?v=20261021-results';
import {planMeeting,summarizePlans,validSnapshot,key} from './pilot-model.mjs?v=pilot1';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),pct=n=>n==null?'—':(n*100).toFixed(1)+'%',money=n=>n==null?'待結算':(n<0?'−':'')+'$'+Math.abs(n).toLocaleString('en-HK',{maximumFractionDigits:1});
const historyPage=document.body.dataset.history==='true';let registry,config,evidence,audit,replay,meeting,overlay,base,context={},loading=false,requestId=0;
const place=(v,t)=>v==='HV'?'谷草':t==='AWT'?'田泥':'田草';
const localKey=r=>'hkjc-paper-v1:'+key(r);
function localSnapshots(m){const out={};for(const r of m.races){try{const s=JSON.parse(localStorage.getItem(localKey({...r,date:m.date,venue:m.venue}))||'null');if(validSnapshot(s,{...r,date:m.date,venue:m.venue},config)&&!validSnapshot(r.roi_strategy,{...r,date:m.date,venue:m.venue},config))out[r.race]=s}catch{}}return out;}
function fixedMethods(){
 $('fixed-methods').innerHTML=Object.entries(config.assignments).filter(([,id])=>id).map(([g,id])=>{const m=registry.methods.find(m=>m.id===id),[v,t,h]=g.split('|'),s=evidence.stats[id];return `<tr><td>${place(v,t)} H=${h}</td><td><b>${esc(m.title)}</b><small>條件不成立即不買，沒有候補。</small></td><td>${s.n}樣本／${s.days.length}賽日</td><td>${pct(s.hits/s.n)}</td><td>${pct(s.profit/s.cost)}</td><td>${money(s.profit-s.maxreturn)}</td></tr>`}).join('');
 $('version').textContent=`紙上試行 ${config.version} · 規則於${config.launched_on}鎖定 · 證據截至${config.trained_through}`;
 $('budget-note').textContent=`每組$10，每日最多$${config.daily_stake_limit}；按場次先後計整組成本，餘額不足不拆單。T−${config.freeze_minutes}分鐘起首次收集時封存；實際時間會記錄，未能及時收集則沒有紀錄。`;
}
function summary(sum){for(const [id,v] of Object.entries({stake:money(sum.cost),returned:money(sum.returned),profit:money(sum.profit),roi:pct(sum.roi),'hit-rate':pct(sum.n?sum.hits/sum.n:null),'hit-count':`${sum.hits}/${sum.n}已結算場 · ${sum.pending}待結算`}))$(id).textContent=v;}
function render(rows){
 const view=$('ledger').value,h=$('h').value,shown=rows.filter(x=>h==='all'||String(x.r.score)===h);summary(summarizePlans(shown));
 $('meeting-title').textContent=meeting.date+' · '+(meeting.venue==='HV'?'跑馬地':'沙田')+' · '+(view==='replay'?'歷史規則重建':view==='paper'?'賽前封存紙上帳':'實際下注帳');
 $('ledger-note').textContent=view==='replay'?'這是按各賽日前資料重新分配方法的歷史重建，並非當日實單。規則經事後研究，價格門檻可能使用最終賠率，不能當成獨立盲測。':view==='actual'?'尚未接入實際下注收據；本頁不把選馬或紙上封存當作實際下注。':'本版只記錄2026年10月22日起、開跑前3分鐘內封存的紙上決策；沒有封存的已跑場次不補造。未到封存時間的內容是預覽，可隨賽前資料更新。';
 if(view==='actual'){$('race-rows').innerHTML='<tr><td colspan="4">未有已核對的實際下注紀錄。</td></tr>';for(const id of ['stake','returned','profit','roi','hit-rate'])$(id).textContent='—';$('hit-count').textContent='未有已核對收據';return}
 $('race-rows').innerHTML=shown.map(x=>{
  const {r,plan:p}=x,horse=n=>esc(n+' '+(r.horses.find(h=>h.no===n)?.name||''));
  const settled=summarizePlans([x]),s=p.method;
  const evidence=s?`<small>${s.n}樣本 · ${s.days?.length||0}賽日 · 歷史命中率 ${pct(s.hits/s.n)}<br>歷史回測ROI ${pct(s.profit/s.cost)}<br>扣最大一場派回後淨利 ${money(s.profit-s.maxreturn)}</small>`:'';
  const method=p.status==='ready'?`<b>${esc(s.title)}</b>${evidence}`:`<b>${p.status==='pending'?'資料不足，不買':'不買'}</b><small>${esc(p.reason)}</small>${evidence}`;
  const bet=p.status==='ready'?`<b>${esc(p.pool)} ${p.picks.map(horse).join(' ＋ ')}</b><small>${p.tickets.map(t=>t.join('–')).join('、')} · 每組$10 · 共${money(p.cost)}</small><small>${r.result?'派回 '+money(settled.returned)+' · 淨利 '+money(settled.profit):'未結算；這是紙上測試'}</small>`:'—';
  const res=r.result?.horses?.filter(h=>parseInt(h.placing)<=3).map(h=>`${esc(h.placing)}. ${horse(h.no)}`).join('<br>')||'未有官方賽果';
  const origin=x.origin==='replay'?'事後規則重建':x.origin==='sealed'?(x.local?'本機紙上封存':'紙上已封存'):x.origin==='missing'?'沒有本版賽前封存':'賽前預覽，未封存';
  const snap=x.snapshot?`<details><summary>封存輸入與依據</summary><pre>${esc(JSON.stringify(x.snapshot,null,2))}</pre></details>`:'';
  return `<tr><td><b>第${r.race}場</b><small>${origin}<br>H=${r.score??'待確認'} · ${r.distance||'—'}米 · ${esc(r.rail||r.track)}</small>${x.snapshot?.finalized?'<small>'+esc(x.snapshot.captured_at)+'</small>':''}</td><td>${method}${snap}</td><td>${bet}</td><td>${res}</td></tr>`;
 }).join('')||'<tr><td colspan="4">沒有符合H篩選的場次。</td></tr>';
}
async function evaluateMeeting(){
 if(!meeting)return;const id=++requestId,view=$('ledger').value;let stats=evidence.stats,allocation=config.assignments,ctx={...context,ledger:view,now:Date.now()};
 if(view==='replay'){
  const prior=await freshJson('./pilot-stats/'+meeting.date+'.json');if(id!==requestId)return;
  if(prior.before_date!==meeting.date)throw Error('賽日前證據日期不符');stats=prior.stats;allocation=prior.assignments;ctx.replay=replay;ctx.oddsByRace=Object.fromEntries(meeting.races.map(r=>[r.race,replay.inputs[key({...r,date:meeting.date,venue:meeting.venue})]?.final_odds||{}]));
 }else if(view==='paper'){ctx.snapshots=localSnapshots(meeting);delete ctx.replay;}
 if(view==='actual'){render([]);return}
 const rows=planMeeting(meeting,registry.methods,stats,config,{...ctx,allocation});
 if(view==='paper')for(const x of rows){x.local=!!ctx.snapshots?.[x.r.race];if(x.origin==='sealed'&&x.snapshot?.finalized&&!validSnapshot(x.r.roi_strategy,x.r,config)){try{localStorage.setItem(localKey(x.r),JSON.stringify(x.snapshot));x.local=true}catch{}}}
 render(rows);
}
function days(){
 const active=audit.days.filter(d=>d.cost>0),wins=active.filter(d=>d.profit>0).length,losses=active.filter(d=>d.profit<0).length;
 $('day-summary').textContent=`本版歷史規則重建：${wins}個盈利日、${losses}個虧損日、${audit.days.length-active.length}個不下注日；合計淨利${money(audit.days.reduce((s,d)=>s+d.profit,0))}。不下注不算贏；這些數字不是未來預期收入。`;
 $('day-rows').innerHTML=audit.days.map(d=>`<tr><td><a href="strategy-history.html?date=${d.date}&ledger=replay">${d.date}</a></td><td>${d.n?d.hits+'/'+d.n:'不下注'}</td><td>${money(d.cost)}</td><td>${money(d.profit)}</td><td>${pct(d.roi)}</td></tr>`).join('');
}
async function dateChanged(){const id=++requestId;try{const date=$('date').value,ref=replay.meetings.find(m=>m.date===date),m=await freshJson(ref?'./'+ref.file:base+date+'.json');if(id!==requestId)return;meeting=mergeManualResults(m,overlay);if(!historyPage)$('ledger').value=date<config.launched_on?'replay':'paper';await evaluateMeeting();$('error').textContent='';}catch(e){fail(e)}}
function fail(e){meeting=null;$('error').textContent='無法核對策略資料：'+e.message;$('race-rows').innerHTML='<tr><td colspan="4">資料未核對，不提供新買法。</td></tr>';for(const id of ['stake','returned','profit','roi','hit-rate','hit-count'])$(id).textContent='—';}
async function load(){if(loading)return;loading=true;try{
 const source=await resolveDataSource({fallback:'8c62563d682424b873701d00a4f3dba9e6afefdb'});if(source.notice.includes('存檔'))throw Error('未能核對最新資料');base=source.base;
 const files=['./roi-methods.json','./pilot-config.json','./pilot-evidence.json','./pilot-audit.json','./roi-replay.json',base+'latest.json','./manual-results.json',base+'history.json'];
 const rs=await Promise.allSettled(files.map(f=>freshJson(f)));for(let i=0;i<6;i++)if(rs[i].status!=='fulfilled')throw Error('必要資料未能讀取：'+files[i]);const get=i=>rs[i].status==='fulfilled'?rs[i].value:null;
 registry=get(0);config=get(1);evidence=get(2);audit=get(3);replay=get(4);const latest=get(5);overlay=get(6);context={};
 if(audit.version!==config.version||evidence.trained_through!==config.trained_through)throw Error('版本更新中，請重新讀取');
 const query=new URL(location.href).searchParams,old=$('date').value,dates=[...new Set([...replay.meetings.map(m=>m.date),...(get(7)?.meetings||[]).map(m=>m.date),latest.date])].sort().reverse();$('date').innerHTML=dates.map(d=>`<option value="${d}">${d}</option>`).join('');$('date').value=historyPage?(old||query.get('date')||latest.date):latest.date;
 if(!old)$('ledger').value=query.get('ledger')||($('date').value<config.launched_on?'replay':'paper');fixedMethods();days();
 if($('date').value===latest.date){meeting=mergeManualResults(latest,overlay);await evaluateMeeting()}else await dateChanged();$('status').textContent='資料更新 '+latest.updated_at;$('error').textContent='';
 }catch(e){fail(e)}finally{loading=false}}
$('date').onchange=dateChanged;for(const id of ['h','ledger'])$(id).onchange=()=>evaluateMeeting().catch(fail);$('refresh').onclick=load;window.addEventListener('pageshow',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});setInterval(()=>{if(!historyPage&&!document.hidden)load()},20000);load();
