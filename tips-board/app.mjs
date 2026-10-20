import {RAW,resolveDataSource,freshJson} from './data-source.mjs?v=20261020-mobile-sync';
import {settle} from './settlement.mjs';
import {parseManual,applyManual,confidenceReason} from './manual-tips.mjs?v=20261017-confidence3';
import {monthlyConfidence,poolLabels} from './confidence-stats.mjs?v=20261017-confidence3';
import {coldWinCandidates,coldWinSelect} from './st-coldwin.mjs?v=20261020-stwin';
import {coldWinArchives} from './st-coldwin-history.mjs?v=20261020-stwin';
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id),history=document.body.dataset.history==='true';let meeting=null,sourceMeeting=null,busy=false,base=RAW,revisionCheckedAt=0;
const clock=d=>d?new Date(d).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false}):'—';
async function read(name,revision=base){try{return await freshJson(revision+name)}catch(err){throw Error('數據讀取失敗（'+err.message+'）')}}
const fallbackRevision='820812adbd944cda87a76c84a9739ee313f00e90',revisionKey='hkjc-verified-data-revision-v1';let dataVersion=null;
async function pinDataRevision(force=false){
 if(!force&&revisionCheckedAt&&Date.now()-revisionCheckedAt<90000)return;
 let saved;try{saved=localStorage.getItem(revisionKey)}catch{}
 const resolved=await resolveDataSource({saved,fallback:fallbackRevision});
 if(resolved.sha)try{localStorage.setItem(revisionKey,resolved.sha)}catch{}
 if(dataVersion!==resolved.version){monthlyRevision=null;historyIndexRevision=null;dataVersion=resolved.version}
 $('revision-notice').textContent=resolved.notice;
 base=resolved.base;revisionCheckedAt=Date.now();
}
function horses(h){return h.map(x=>`<div class="horse"><span class="num">${e(x.no)}</span><span>${e(x.name)}</span></div>`).join('')}
function tips(t,index=false){if(!t)return '<span class="muted">待更新</span>';let text=t.horses?.length?horses(t.horses):t.status==='absent'?'/':t.status==='stale'?'待更新（來源 '+e(t.source_date)+'）':t.status==='error'?'<span class="error">讀取失敗'+(t.error?'：'+e(t.error):'')+'</span>':t.status==='missed'?'未取得賽前資料':t.status==='historical_missing'?'歷史資料未找到':index?'待開跑前2分鐘':'待賽前檢查';if(t.timing_note)text+=`<div class="error">${e(t.timing_note)}</div>`;if(t.captured_at)text+=`<details><summary>${t.manual?'輸入':t.record_type==='historical_backfill'?'補錄':'取得'} ${e(clock(t.captured_at))}</summary><p>${e(t.source_date||t.raceid||'')}<br>${e(t.captured_at)}${t.reported_live_created_at?`<br>來源生成時間：${e(t.reported_live_created_at)}`:''}${t.source&&!t.manual?`<br><a href="${e(t.source)}" target="_blank" rel="noopener">原始來源</a>`:''}</p></details>`;return (t.manual?'<span class="manual-badge">手動輸入</span>':'')+text}
function bankerTips(r){
 const b=r.banker_initial;if(b?.status!=='ready'||b.numbers?.length!==5)return '<span class="muted">待初版推介</span>';
 const field=new Map(r.horses.map(h=>[Number(h.no),h.name])),roles=['膽','腳1','腳2','腳3','腳4'];
 const list=b.numbers.map((no,i)=>`<div class="horse"><span class="muted">${roles[i]}</span><span class="num">${e(no)}</span><span>${e(field.get(Number(no))||'')}</span></div>`).join('');
 const p=b.banker_top3_probability;
 return list+(typeof p==='number'&&Number.isFinite(p)&&p>=0&&p<=1?`<div class="muted" data-banker-probability>膽入三甲估計：<b>${(p*100).toFixed(1)}%</b>${b.source_type==='user_provided'?'<br><small>用戶提供的預測估計</small>':''}</div>`:'');
}
function drawTop5(r){
 const v=r.draw_top5;if((v?.status!=='ready'||v.method_version!=='jockey_draw_only_v3'))return '<span class="muted">待騎師同檔往績</span>';
 return `<div class="muted">只計同檔<br>2026-09-01起・賽日前往績</div>`+(v.coverage_note?`<div class="error">${e(v.coverage_note)}</div>`:'')+(v.riders.length?v.riders.map((h,i)=>`<div class="horse"><span class="muted">${i+1}.</span><span class="num">${e(h.no)}</span><span>${e(h.jockey)}・${e(h.draw)}檔<br><small>${(h.rate*100).toFixed(1)}%（${h.placed}/${h.starts}）</small></span></div>`).join(''):'<span class="muted">當場騎師無同檔往績</span>');
}

const coldOddsKey=r=>'hkjc-st-win-odds-v1:'+r.date+':'+r.race;
function savedColdOdds(r){try{return JSON.parse(localStorage.getItem(coldOddsKey(r))||'null')}catch{return null}}
function coldWinState(r){
 const isConfidence=Boolean(confidenceReason(r)),past=r.locked||Date.now()>=Date.parse(r.off),saved=savedColdOdds(r);
 if(r.venue!=='ST'||r.track!=='TURF'||!isConfidence)return{status:'not_applicable',candidates:[],picks:[]};
 if(past&&saved?.plan&&saved.date===r.date&&saved.race===r.race&&Date.parse(saved.at)<Date.parse(r.off))return{...saved.plan,at:saved.at,odds:saved.odds,frozen:true};
 const old=coldWinArchives[r.date+'~'+r.race],archive=old&&r.horses.every(h=>r.scratched?.includes(h.no)||old.field[h.no]===h.name)?old:null;
 const support=r.st_win_support||archive?.support,candidates=coldWinCandidates(r,support,isConfidence);
 if(past&&archive)return{...coldWinSelect(candidates,archive.final_odds),odds:archive.final_odds,historical:true};
 if(past)return{...candidates,status:'missed',picks:[],reason:'未保存完整賽前賠率確認，不回填買馬'};
 return{...coldWinSelect(candidates,saved?.odds||{}),odds:saved?.odds||{},at:saved?.at};
}
function coldWinBetHtml(r){
 const s=coldWinState(r);if(s.status==='not_applicable')return '';
 if(s.status!=='ready')return '<div class="st-win-bet muted">沙草補Win：'+e(s.status==='awaiting_odds'?'待確認全部候選賠率':s.reason||'待補Win資料')+'</div>';
 if(!s.picks.length)return '<div class="st-win-bet muted">沙草補Win：沒有符合條件的買入馬</div>';
 let text=`<div class="st-win-bet"><b>沙草補Win｜每匹 $10 W</b><br>${s.picks.map(h=>e(h.no+'. '+h.name)+'（'+e(h.odds)+'倍）').join('<br>')}`;
 if(r.result){const p=settle('W',s.picks.map(h=>h.no),r.result);if(p.status==='hit')text+=`<div class="hit">有中 ${p.hits.length}/${s.picks.length}匹 · 實收 $${p.hits.reduce((n,h)=>n+h.dividend,0).toFixed(1)}</div>`;else text+='<div class="muted">'+(p.status==='pending'?'派彩待更新':p.status==='refund'?'退款':'未中')+'</div>'}
 return text+`<div class="muted">${s.historical?'最終賠率回算，非賽前實單':s.frozen?'已鎖定賽前確認':'按已輸入賠率；臨場仍須 >8'}${s.at?' · '+e(clock(s.at)):''}</div></div>`;
}
function renderColdWin(m){
 $('st-win-section').hidden=m.venue!=='ST';if(m.venue!=='ST')return;
 if(document.activeElement?.id?.startsWith('st-odd-'))return;
 const races=m.races.filter(r=>r.track==='TURF'&&confidenceReason(r));
 $('st-win-rows').innerHTML=races.length?races.map(r=>{
  const s=coldWinState(r),can=!history&&!r.locked&&Date.now()<Date.parse(r.off),c=s.candidates||[];
  const candidates=c.length?c.map(h=>`<div class="st-win-candidate"><b>${e(h.no)} ${e(h.name)}</b><br><small>${h.branch==='A'?'休後'+h.gap+'日':'上仗前三・相隔'+h.gap+'日'} · 首段中位數 ${e(h.median)}<br>${h.authors.map(a=>e(a.name)+'第'+a.rank+'選').join('、')}</small></div>`).join(''):'<span class="muted">'+e(s.status==='ready'?'沒有合資格候選':s.reason||'待補Win資料')+'</span>';
  const odds=c.length?c.map(h=>`<label class="st-odd-label" for="st-odd-${r.race}-${h.no}">${e(h.no)}號 <input id="st-odd-${r.race}-${h.no}" type="number" min="0.1" step="any" inputmode="decimal" placeholder="待核對" value="${e(s.odds?.[h.no]??'')}" ${can?'':'disabled'}></label>`).join(''):'—';
  return `<tr><td>第${e(r.race)}場<br><small>H=${e(r.score)}</small></td><td>${candidates}</td><td>${odds}${s.historical?'<div class="muted">歷史最終賠率</div>':s.at?'<div class="muted">確認 '+e(clock(s.at))+'</div>':''}</td><td>${coldWinBetHtml(r)}</td></tr>`;
 }).join(''):'<tr><td colspan="4" class="muted">本賽日暫無已確認的沙草信心場。</td></tr>';
 $('st-win-save').hidden=history||!races.some(r=>!r.locked&&Date.now()<Date.parse(r.off));
}

function pattern(r){
 if(r.score==null)return r.venue==='ST'?'待確認條件分<br><span class="muted">T=0：新D位置Q；T=1：M3＋T2＋T3，Q＋位置Q</span>':'待確認條件分';
 if(r.venue==='ST'&&r.score===0)return 'T=0 新D｜三馬互拖位置Q<br><span class="muted">先 M1＋B1（去重）；M2–M4 中與 B1–B3 相交者優先，再按明治朗原序補滿3匹</span>';
 if(r.venue==='ST'&&r.score===1)return 'T=1｜M3＋T2＋T3<br><span class="muted">T＝唯一有貼士專家；三馬互拖Q＋位置Q<br>去重候補：B1→B4→M1→M2→M4→B2→T1→T4→B3→B5</span>';
 if(r.score===0&&r.index?.status==='disabled')return '舊來源已停用，暫無自動買法';
 return r.score===0?'指數馬第1、2匹':r.score===1?'有貼士專家首選＋明治朗首選<br><span class="muted">重覆則明治朗第2匹</span>':'明治朗第1、2、3匹'
}
const labels={W:'獨贏W',P:'位置P',QP:'位置Q',Q:'連贏Q'};
function betLine(pool,r){
 const nos=r.selection.horses.map(h=>h.no),p=settle(pool,nos,r.result),unit=pool==='W'||pool==='P'?'匹':'組';
 let text='';
 if(r.result){
  if(p.status==='not_offered')text=`<div class="bet-result muted">此場未設${labels[pool]}</div>`;
  else if(p.status==='pending')text='<div class="bet-result muted">派彩待更新</div>';
  else if(p.status==='hit')text=`<div class="bet-result hit">有中 ${p.hits.length}/${p.total}${unit}<br>${p.hits.map(h=>`${e(h.horses.join('–'))}${h.horses.length===1?'號':''}：<b title="每$10派$${h.dividend.toFixed(2)}，包含本金">${new Intl.NumberFormat('zh-HK',{maximumFractionDigits:3}).format(h.multiple)}倍</b>`).join('<br>')}${p.refunds?`<br>${p.refunds}${unit}退款`:''}</div>`;
  else text=`<div class="bet-result ${p.status==='refund'?'muted':'miss'}">${p.status==='refund'?'退款':`未中（0/${p.total}${unit}）`}${p.refunds&&p.status!=='refund'?`；${p.refunds}${unit}退款`:''}</div>`;
 }
 return `<div class="bet-item"><div class="bets">${labels[pool]} ${e(nos.join('、'))}${pool==='Q'||pool==='QP'?` 互拖（${nos.length*(nos.length-1)/2}組）`:''}</div>${text}</div>`;
}
function bets(r){const s=r.selection;if(!s&&r.venue!=='ST'&&r.score===0&&r.index?.status==='disabled')return '<span class="muted">舊來源已停用，未設定替代買法</span>';if(!s)return '<span class="muted">'+(r.locked?(r.lock_type==='historical_reconstruction'?'歷史資料不足，未重建買法':'賽前資料不足，未產生買法'):'等待所需貼士')+'</span>';return s.main.map(k=>betLine(k,r)).join('')+`<div class="muted">${e(s.horses.map(h=>h.no+'.'+h.name).join('　'))}</div>`+(s.optional.length?`<div class="optional">可選：${s.optional.map(k=>betLine(k,r)).join('')}</div>`:'')+(r.locked?'<div class="locked">'+(r.strategy_recalculated?'按新規則回算（非原賽前買法）':r.lock_type==='historical_reconstruction'?'按歷史存檔重建':r.manual_local?'已鎖定手動選擇（本機）':'已鎖定賽前選擇')+'</div>':'')+coldWinBetHtml(r)}

let monthlySources=[],monthlyRevision=null,monthlyError=null,monthlyRequest=0;
function resultHtml(r){return r.result?r.result.horses.map(h=>`<div class="horse"><span class="muted">${(['','冠','亞','季','四'][parseInt(h.placing)]||e(h.placing))}</span><span class="num">${e(h.no)}</span>${e(h.name)}</div>`).join(''):'<span class="muted">'+(r.date>='2026-10-16'?'不收集賽果':r.locked?'未保存賽果':'未開跑')+'</span>'}
function renderConfidence(m){
 const races=m.races.filter(r=>confidenceReason(r));
 $('confidence-summary').textContent=m.date+' · '+(m.venue==='HV'?'跑馬地':'沙田')+' · '+races.length+'場信心';
 $('confidence-rows').innerHTML=races.length?races.map(r=>`<tr><td><div class="race-label"><b>第${e(r.race)}場</b>${confidenceBadge(r)}</div><div class="clock">H=${e(r.score)} · ${e(clock(r.off).slice(0,5))}</div></td><td>${bets(r)}</td><td>${resultHtml(r)}</td></tr>`).join(''):'<tr><td colspan="3" class="empty-state">本賽日暫無已確認的信心場；條件分或貼士未齊時會等待更新。</td></tr>';
}
function renderMonthly(){
 if(monthlyError){$('monthly-status').textContent=monthlyError;$('monthly-rows').innerHTML='<tr><td colspan="9" class="empty-state">歷史紀錄未完整讀取，命中率暫不顯示。請按「重新讀取」重試。</td></tr>';return}
 if(monthlyRevision!==base){$('monthly-status').textContent='正在讀取全部歷史賽日…';$('monthly-rows').innerHTML='<tr><td colspan="9">正在讀取…</td></tr>';return}
 const rows=monthlyConfidence([...monthlySources,...(sourceMeeting?[sourceMeeting]:[])],{savedFor:getManual});
 $('monthly-status').textContent='按目前信心規則及頁面買法回算；包含歷史補錄／新規則回算，不代表當時實際投注。';
 $('monthly-rows').innerHTML=rows.length?rows.map(g=>`<tr><td>${g.venue==='HV'?'跑馬地':'沙田'}</td><td>H=${g.score}</td><td>${e(g.month)}</td><td>${poolLabels[g.pool]||'待買法'}<div class="muted">${g.role==='main'?'主買法':'可選買法'}</div></td><td>${g.races}</td><td>${g.settled}</td><td>${g.hits}</td><td class="monthly-rate">${g.rate===null?'—':(g.rate*100).toFixed(1)+'%'}</td><td>${g.pending}待核對<br><span class="muted">${g.refunds}退款 · ${g.notOffered}不設彩池</span></td></tr>`).join(''):'<tr><td colspan="9" class="empty-state">暫無符合規則的信心場紀錄。</td></tr>';
}
async function refreshMonthly(){
 const revision=base,request=++monthlyRequest;monthlyError=null;$('monthly-status').textContent='正在讀取全部歷史賽日…';
 try{
  const index=await read('history.json',revision);if(!Array.isArray(index.meetings))throw Error('歷史目錄格式有誤');
  const dates=[...new Set(index.meetings.map(m=>m.date))];if(dates.some(d=>!/^\d{4}-\d{2}-\d{2}$/.test(d)))throw Error('歷史日期格式有誤');
  const results=await Promise.allSettled(dates.map(date=>read(date+'.json',revision)));
  if(request!==monthlyRequest||revision!==base)return;
  if(results.some(r=>r.status==='rejected'))throw Error('部分歷史紀錄讀取失敗，暫不更新命中率。');
  const sources=results.map(r=>r.value);if(sources.some((m,i)=>m.date!==dates[i]||m.venue!==index.meetings.find(x=>x.date===dates[i]).venue||!Array.isArray(m.races)))throw Error('歷史賽日資料不符，暫不更新命中率。');
  monthlySources=sources;monthlyRevision=revision;renderMonthly();
 }catch(err){if(request===monthlyRequest&&revision===base){monthlyError=err.message;renderMonthly()}}
}
function confidenceBadge(r){const reason=confidenceReason(r);return reason?`<span class="confidence-badge" title="${e(reason)}" aria-label="信心：${e(reason)}">信心</span>`:''}
function render(source){sourceMeeting=source;let saved=getManual(source),m=applyManual(source,saved);for(const r of m.races){r.venue=m.venue;r.date=m.date}if(saved)persistManual(saved);meeting=m;$('title').textContent=m.date+' · '+(m.venue==='HV'?'跑馬地':'沙田');$('eyebrow').textContent=history?'歷史紀錄':'最新賽日';$('subtitle').textContent=`${m.races.length}場 · 第一場 ${clock(m.races[0].off).slice(0,5)} · 馬號及馬名按官方排位核對`;$('status').textContent=m.status==='archived'?'全日紀錄已保存':m.status==='live'?'賽日收集中':m.status==='interrupted'?'抓取中斷':'等待賽日';$('updated').textContent='最近保存：'+clock(m.updated_at)+(m.manual_checked_at?' · 手動檢查：'+clock(m.manual_checked_at):'');$('cutoff').textContent=m.record_type==='historical_backfill'?'歷史補錄：'+m.backfilled_at.slice(0,10)+' '+clock(m.backfilled_at):m.tips_checked_at?'貼士已檢查：'+clock(m.tips_checked_at):'貼士檢查時間：'+m.tips_due_at.slice(0,10)+' '+clock(m.tips_due_at);const stale=m.heartbeat&&(Date.now()-Date.parse(m.heartbeat)>180000)&&m.status==='live';$('notice').textContent=m.record_type==='historical_backfill'?m.notice:stale?'抓取狀態超過3分鐘未更新，請查看工作狀態。':m.status==='interrupted'?'抓取工作中斷；未取得的資料會保留缺失狀態。':'';
if(m.venue==='ST')$('notice').textContent+=($('notice').textContent?' ':'')+'M＝明治朗原次序；B＝膽拖網初版：B1膽、B2腳1、B3腳2、B4腳3、B5腳4。T=0／1指條件分；T1–T4指唯一有貼士專家原次序。退出馬剔除後順延。「信心」：明治朗首選不在初版膽、腳1、腳2內，T=0另須草地；資料齊全才標示。';
if(m.venue==='HV')$('notice').textContent+=($('notice').textContent?' ':'')+'跑馬地H=1、2、3均列為信心場；H指條件分。';
if(m.races.some(r=>r.manual_local))$('notice').textContent+=($('notice').textContent?' ':'')+'本頁含目前瀏覽器保存的手動貼士及選擇。';
$('rows').innerHTML=m.races.map(r=>`<tr><td><div class="race-label"><b>第${e(r.race)}場</b>${confidenceBadge(r)}</div><div class="clock">${e(clock(r.off).slice(0,5))}</div></td><td data-result>${resultHtml(r)}</td><td data-score>${r.score==null?'<span class="muted">待確認</span>':`<span class="score">${r.score}</span>`}</td><td>${tips(r.tips.meiji)}</td><td data-banker-tips>${bankerTips(r)}</td><td data-draw-top5>${drawTop5(r)}</td><td>${tips(r.tips.ball)}</td><td>${tips(r.tips.ma)}</td><td>${tips(r.tips.computer)}</td><td class="pattern">${pattern(r)}</td><td>${bets(r)}</td></tr>`).join('');renderColdWin(m);renderConfidence(m);renderMonthly()}
let historyIndexRevision=null;
async function refreshHistoryDates(force=false){
 if(!history||(!force&&historyIndexRevision===base))return;
 const selected=$('dates').value,h=await read('history.json');
 if(!Array.isArray(h.meetings))throw Error('歷史目錄格式有誤');
 $('history-controls').hidden=false;
 $('dates').innerHTML=h.meetings.map(m=>`<option value="${e(m.date)}">${e(m.date)} · ${m.venue==='HV'?'跑馬地':'沙田'}${m.results_enabled===false?'（不收集賽果）':m.complete?'':'（部分賽果待補）'}</option>`).join('');
 $('dates').disabled=!h.meetings.length;
 if(h.meetings.some(m=>m.date===selected))$('dates').value=selected;
 if(!h.meetings.length){$('title').textContent='歷史紀錄';$('status').textContent='尚未有紀錄';$('rows').innerHTML='<tr><td colspan="11">暫時沒有已結束賽日紀錄。</td></tr>'}
 historyIndexRevision=base;
}
async function load(force=false){
 if(busy)return;busy=true;
 try{
  await pinDataRevision(force);await refreshHistoryDates(force);
  if(history){if($('dates').value)render(await read($('dates').value+'.json'))}else render(await read('latest.json'));
  if(force||monthlyRevision!==base||monthlyError)await refreshMonthly();
 }catch(err){$('notice').textContent=err.message+'；保留最後成功讀取資料。'}finally{busy=false}
}
async function start(){if(history)$('dates').onchange=()=>load();await load(true)}
const names={meiji:'明治朗',ball:'波仔',ma:'馬觀微',computer:'電腦評分',index:'指數馬'};
const manualKey=m=>'hkjc-manual-tips-v1:'+m.date+':'+m.venue;
function getManual(m){try{return JSON.parse(localStorage.getItem(manualKey(m))||'null')}catch{return null}}
function persistManual(saved){try{localStorage.setItem(manualKey(saved),JSON.stringify(saved));return true}catch{if($('manual-message'))$('manual-message').textContent='無法保存：請容許瀏覽器儲存資料。';return false}}
function editable(r){return r&&!r.locked&&!r.result&&Date.now()<Date.parse(r.off)}
function fillManual(){
 const r=sourceMeeting?.races.find(r=>r.race===Number($('manual-race').value));if(!r)return;
 const entry=getManual(sourceMeeting)?.races?.[r.race],can=editable(r);
 $('manual-field').textContent=r.horses.map(h=>h.no+'. '+h.name).join('　');
 $('manual-inputs').innerHTML=Object.entries(names).map(([k,name])=>{
  const tip=entry?.overrides?.[k],mode=tip?(tip.status==='absent'?'absent':'manual'):'auto';
  return `<div class="manual-row"><label for="input-${k}">${name}</label><select id="mode-${k}" aria-label="${name}輸入方式" ${can?'':'disabled'}><option value="auto" ${mode==='auto'?'selected':''}>使用自動來源</option><option value="manual" ${mode==='manual'?'selected':''}>手動馬號</option>${['ball','ma','computer'].includes(k)?`<option value="absent" ${mode==='absent'?'selected':''}>此場無貼士 /</option>`:''}</select><input id="input-${k}" type="text" inputmode="text" autocomplete="off" aria-label="${name}馬號" placeholder="按次序：3、7、10、11" value="${e(tip?.horses?.map(h=>h.no).join('、')||'')}" ${can&&mode==='manual'?'':'disabled'}><span id="preview-${k}" class="manual-preview"></span></div>`;
 }).join('');
 for(const k of Object.keys(names)){
  const preview=()=>{const mode=$('mode-'+k).value;$('input-'+k).disabled=!can||mode!=='manual';let text='';if(mode==='manual')try{text=parseManual($('input-'+k).value,r,k).map(h=>h.no+'. '+h.name).join('　')}catch(err){text=err.message}$('preview-'+k).textContent=text};
  $('mode-'+k).onchange=preview;$('input-'+k).oninput=preview;preview();
 }
 $('manual-message').textContent=can?'明治朗及指數馬填4匹；其他專家填1至4匹，或選「此場無貼士 /」。':'本場已開跑或已鎖定，不能修改。';
 $('manual-form').querySelector('[type="submit"]').disabled=!can;$('manual-reset').disabled=!can;
}
if(!history&&$('manual-open')){
 $('manual-open').onclick=()=>{if(!sourceMeeting)return;$('manual-panel').hidden=false;$('manual-race').innerHTML=sourceMeeting.races.map(r=>`<option value="${r.race}">第${r.race}場 · ${clock(r.off).slice(0,5)}</option>`).join('');fillManual();$('manual-panel').scrollIntoView({behavior:'smooth',block:'start'})};
 $('manual-close').onclick=()=>{$('manual-panel').hidden=true};$('manual-race').onchange=fillManual;
 $('manual-form').onsubmit=event=>{
  event.preventDefault();const r=sourceMeeting.races.find(r=>r.race===Number($('manual-race').value));
  if(!editable(r)){$('manual-message').textContent='本場已開跑或鎖定，不能修改。';return}
  try{
   const saved=getManual(sourceMeeting)||{version:1,date:sourceMeeting.date,venue:sourceMeeting.venue,races:{}},overrides={},at=new Date().toISOString();
   for(const k of Object.keys(names)){const mode=$('mode-'+k).value;if(mode==='auto')continue;overrides[k]={status:mode==='absent'?'absent':'ready',horses:mode==='absent'?[]:parseManual($('input-'+k).value,r,k),manual:true,captured_at:at,source_date:sourceMeeting.date,source:'manual-local'}}
   if(!editable(r))throw Error('本場已開跑，不能修改。');
   if(Object.keys(overrides).length)saved.races[r.race]={overrides};else delete saved.races[r.race];
   applyManual(sourceMeeting,saved);if(!persistManual(saved))return;render(sourceMeeting);$('manual-message').textContent='已保存第'+r.race+'場手動貼士；條件分及買法已更新。';
  }catch(err){$('manual-message').textContent=err.message}
 };
 $('manual-reset').onclick=()=>{const r=sourceMeeting.races.find(r=>r.race===Number($('manual-race').value));if(!editable(r)){$('manual-message').textContent='本場已開跑，不能修改。';return}const saved=getManual(sourceMeeting);if(saved){delete saved.races[r.race];if(!persistManual(saved))return}render(sourceMeeting);fillManual();$('manual-message').textContent='已恢復本場自動資料。'};
 $('manual-export').onclick=()=>{const saved=getManual(sourceMeeting);if(!saved||!Object.keys(saved.races).length){$('manual-message').textContent='目前沒有手動紀錄可下載。';return}const url=URL.createObjectURL(new Blob([JSON.stringify(saved,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='manual-tips-'+saved.date+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
}
$('st-win-form').onsubmit=event=>{
 event.preventDefault();if(history||!meeting)return;
 try{
  const writes=[];
  for(const r of meeting.races){
   if(r.locked||Date.now()>=Date.parse(r.off))continue;
   const state=coldWinState(r);if(!['ready','awaiting_odds'].includes(state.status))continue;
   const odds={};
   for(const h of state.candidates){
    const value=$('st-odd-'+r.race+'-'+h.no).value.trim();if(!value)continue;
    const n=Number(value);if(!Number.isFinite(n)||n<=0)throw Error('第'+r.race+'場 '+h.no+'號：請輸入正數賠率');odds[h.no]=n;
   }
   const at=new Date().toISOString(),plan=coldWinSelect({status:'ready',candidates:state.candidates},odds);
   writes.push({r,data:{version:1,date:r.date,race:r.race,at,odds,plan}});
  }
  if(!writes.length)throw Error('沒有資料齊全而未開跑的場次可保存');
  for(const {r,data} of writes){if(r.locked||Date.now()>=Date.parse(r.off))throw Error('第'+r.race+'場已開跑，不能保存');localStorage.setItem(coldOddsKey(r),JSON.stringify(data))}
  render(sourceMeeting);$('st-win-message').textContent='已保存於此瀏覽器；完整輸入賠率後才產生最多兩匹買法。開跑後鎖定。';
 }catch(err){$('st-win-message').textContent='未能完成保存：'+err.message}
};
$('refresh').onclick=()=>load(true);
const resume=()=>{if(document.visibilityState!=='hidden')return load(true)};
window.addEventListener?.('pageshow',resume);
document.addEventListener?.('visibilitychange',resume);
window.addEventListener?.('online',resume);
await start();setInterval(()=>{if(document.visibilityState!=='hidden')return load()},20000);

if(!history&&$('collect'))$('collect').onclick=()=>{
 const url='https://github.com/Ljackylau/hkjc-scraper/actions/workflows/expert-tips-run.yml';
 window.open(url,'_blank','noopener');
 $('collect-help').hidden=false;
 $('collect-help').textContent='已開啟 GitHub。登入後按 Run workflow，mode 選 manual，date 填 '+(meeting?.date||'latest')+'，再確認執行。完成後本頁會於90秒內核對最新版本，亦可按「重新讀取」即時更新；已有抓取工作時會排隊。GitHub Pages 目前不能單次點擊直接啟動工作。';
};
