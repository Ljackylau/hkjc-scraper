import {resolveDataSource,freshJson} from './data-source.mjs?v=20261020-mobile-sync';
import {mergeManualResults} from './manual-results.mjs?v=20261021-results';
import {historyRows,summarize} from './strategy-history-model.mjs?v=20261021-history';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),money=n=>n===null?'待派彩':'$'+Number(n).toLocaleString('en-HK',{maximumFractionDigits:1}),pct=n=>n===null?'—':(n*100).toFixed(1)+'%';
let base='',index=null,meeting=null,overlay=null,context={},request=0;
function horse(r,n){return esc(n+' '+(r.horses.find(h=>Number(h.no)===n)?.name||''))}
function render(){
 if(!meeting)return;
 const all=historyRows(meeting,{mode:$('mode').value,context}),rows=all.filter(x=>$('h').value==='all'||String(x.r.score)===$('h').value),s=summarize(rows);
 $('meeting-title').textContent=meeting.date+' · '+(meeting.venue==='HV'?'跑馬地':'沙田');
 $('stake').textContent=money(s.cost);$('returned').textContent=money(s.returned);$('profit').textContent=money(s.profit);$('roi').textContent=pct(s.roi);$('hit-rate').textContent=pct(s.rate);$('hit-count').textContent=s.hits+'/'+s.races+'場 · '+s.pending+'項待派彩';
 $('mode-note').textContent=$('mode').value==='saved'?'按已保存的選馬及主買彩池，每組$10作統一結算；不是用戶交易紀錄。可選彩池不混入合計。':'按現行規則及當時保存的賽前資料回算，並非當日發布推介；資料不足保留缺失，不以賽果補選。';
 $('race-rows').innerHTML=rows.map(x=>{
  const {r,bets}=x,top=r.result?.horses?.filter(h=>parseInt(h.placing)<=3)||[],result=top.length?top.map(h=>`${esc(h.placing)}. ${horse(r,Number(h.no))}`).join('<br>'):'待官方賽果';
  const bet=bets.length?bets.map(b=>`<b>${b.pool} · ${b.picks.map(n=>horse(r,n)).join(' ＋ ')}</b><small>${b.hits.length?'命中'+b.hits.length+'組／匹':b.status==='pending'?'待派彩':b.status==='refund'?'退款':b.status==='not_offered'?'不設彩池':'未中'} · 投入${money(b.cost)}<br>派回${money(b.returned)} · 淨盈虧${money(b.profit)}</small>`).join('<hr>'):'<b>沒有投注</b><small>'+esc(x.reason)+'</small>';
  const research=x.research.length?x.research.map(q=>`<div class="study-plan"><b>${esc(q.method.title)}</b><small>${q.state==='ready'?'回算候選：'+q.picks.map(n=>horse(r,n)).join('、'):q.state==='odds'?'條件候選：'+q.candidates.map(n=>horse(r,n)).join('、')+'；缺賽前賠率確認':esc(q.reason||'未觸發')}</small>${q.state==='ready'||q.state==='odds'?'<small>候選結果：'+(q.picks||q.candidates||[]).map(n=>{const paid=r.result?.dividends?.W?.filter(p=>Number(p.combination)===n)||[];return horse(r,n)+(r.result?(paid.length?' 勝出（每$10 W派'+money(paid.reduce((s,p)=>s+p.dividend_hkd,0))+'）':' 未勝出'):' 待賽果')}).join('；')+'<br>非已保存研究投注，不計入盈虧</small>':''}</div>`).join(''):'<span class="muted">沒有對應研究方法</span>';
  return `<tr><td><b>第${r.race}場</b><small>${r.distance||'—'}米 · ${esc(r.rail||r.track)}<br>H=${r.score??'待確認'}</small></td><td>${result}</td><td>${bet}<small>${esc(x.method)}</small>${r.selection?.generated_at&&x.mode==='saved'?'<small>選馬保存：'+esc(r.selection.generated_at)+'</small>':''}</td><td>${research}</td></tr>`;
 }).join('')||'<tr><td colspan="4">此篩選沒有場次</td></tr>';
 const groups=new Map();for(const row of rows)for(const b of row.bets){const key=row.r.score+'|'+b.pool;if(!groups.has(key))groups.set(key,[]);groups.get(key).push({...row,bets:[b]})}
 $('group-rows').innerHTML=[...groups].map(([key,rs])=>{const [h,pool]=key.split('|'),g=summarize(rs);return `<tr><td>H=${esc(h)}</td><td>${pool}</td><td>${g.hits}/${g.races}</td><td>${pct(g.rate)}</td><td>${money(g.cost)}</td><td>${money(g.returned)}</td><td>${money(g.profit)}</td><td>${pct(g.roi)}</td></tr>`}).join('')||'<tr><td colspan="8">沒有已保存買法</td></tr>';
}
async function loadDate(){
 const id=++request,date=$('date').value;if(!date)return;
 $('error').textContent='';$('status').textContent='正在讀取賽日…';
 try{
  const data=await freshJson(base+date+'.json');if(id!==request)return;
  meeting=mergeManualResults(data,overlay);
  const support=context.support;if(support?.date===meeting.date&&support.venue===meeting.venue)for(const r of meeting.races)if(!r.hv_win_support&&support.races?.[r.race])r.hv_win_support=support.races[r.race];
  if(!/^\d{4}-\d{2}-\d{2}$/.test(meeting.date)||meeting.date!==date)throw Error('賽日資料不符');
  $('status').textContent='已保存賽果：'+meeting.races.filter(r=>r.result).length+'/'+meeting.races.length+'場 · 賽前選馬保持原紀錄';
  const u=new URL(location.href);u.searchParams.set('date',date);history.replaceState(null,'',u);render();
 }catch(e){if(id===request){meeting=null;$('error').textContent=e.message;$('race-rows').innerHTML='<tr><td colspan="4">讀取失敗，請重新整理</td></tr>';for(const id of ['stake','returned','profit','roi','hit-rate','hit-count'])$(id).textContent='—'}}
}
async function load(){
 try{
  const revision=await resolveDataSource({fallback:'8c62563d682424b873701d00a4f3dba9e6afefdb'});if(revision.notice.includes('存檔'))throw Error('無法核對最新版本，請重新連線');base=revision.base;
  const results=await Promise.allSettled([freshJson(base+'history.json'),freshJson('./manual-results.json'),freshJson('./strategy-draw-seed.json'),freshJson(base+'draw-history.json'),freshJson('./strategy-support/latest.json')]);
  if(results[0].status!=='fulfilled')throw Error('歷史目錄無法讀取');index=results[0].value;overlay=results[1].status==='fulfilled'?results[1].value:null;context={index,seed:results[2].status==='fulfilled'?results[2].value:null,history:results[3].status==='fulfilled'?results[3].value:null,support:results[4].status==='fulfilled'?results[4].value:null};
  const old=$('date').value,chosen=new URL(location.href).searchParams.get('date');
  $('date').innerHTML=index.meetings.filter(m=>m.date>='2026-09-01').sort((a,b)=>b.date.localeCompare(a.date)).map(m=>`<option value="${esc(m.date)}">${esc(m.date)} · ${m.venue==='HV'?'跑馬地':'沙田'}</option>`).join('');
  if([...$('date').options].some(o=>o.value===(old||chosen)))$('date').value=old||chosen;
  await loadDate();
 }catch(e){$('error').textContent=e.message}
}
$('date').onchange=loadDate;$('h').onchange=$('mode').onchange=render;$('refresh').onclick=load;
$('older').onclick=()=>{const s=$('date');if(s.selectedIndex<s.options.length-1){s.selectedIndex++;loadDate()}};$('newer').onclick=()=>{const s=$('date');if(s.selectedIndex>0){s.selectedIndex--;loadDate()}};load();
