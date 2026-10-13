import {settle} from './settlement.mjs';
const RAW='https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/tips-data/records/';
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=id=>document.getElementById(id),history=document.body.dataset.history==='true';let meeting=null,busy=false,base=RAW,revisionCheckedAt=0;
const clock=d=>d?new Date(d).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false}):'—';
async function read(name){const r=await fetch(base+name+'?v='+Math.floor(Date.now()/20000),{cache:'no-store'});if(!r.ok)throw Error('數據讀取失敗 ('+r.status+')');return r.json()}
async function pinDataRevision(force=false){
 if(!force&&revisionCheckedAt&&Date.now()-revisionCheckedAt<90000)return;
 const r=await fetch('https://api.github.com/repos/Ljackylau/hkjc-scraper/git/refs/heads/tips-data?v='+Date.now(),{cache:'no-store'});
 if(!r.ok)throw Error('資料版本讀取失敗 ('+r.status+')');
 const j=await r.json(),sha=j.object?.sha;if(!/^[a-f0-9]{40}$/.test(sha||''))throw Error('資料版本資料無效');
 base=RAW.replace('/tips-data/records/','/'+sha+'/records/');revisionCheckedAt=Date.now();
}
function horses(h){return h.map(x=>`<div class="horse"><span class="num">${e(x.no)}</span><span>${e(x.name)}</span></div>`).join('')}
function tips(t,index=false){if(!t)return '<span class="muted">待更新</span>';let text=t.horses?.length?horses(t.horses):t.status==='absent'?'/':t.status==='stale'?'待更新（來源 '+e(t.source_date)+'）':t.status==='error'?'<span class="error">讀取失敗'+(t.error?'：'+e(t.error):'')+'</span>':t.status==='missed'?'未取得賽前資料':t.status==='historical_missing'?'歷史資料未找到':index?'待開跑前2分鐘':'待賽前檢查';if(t.timing_note)text+=`<div class="error">${e(t.timing_note)}</div>`;if(t.captured_at)text+=`<details><summary>${t.record_type==='historical_backfill'?'補錄':'取得'} ${e(clock(t.captured_at))}</summary><p>${e(t.source_date||t.raceid||'')}<br>${e(t.captured_at)}${t.reported_live_created_at?`<br>來源生成時間：${e(t.reported_live_created_at)}`:''}${t.source?`<br><a href="${e(t.source)}" target="_blank" rel="noopener">原始來源</a>`:''}</p></details>`;return text}
function pattern(r){if(r.score==null)return '待確認條件分';return r.score===0?'指數馬第1、2匹':r.score===1?'有貼士專家首選＋明治朗首選<br><span class="muted">重覆則明治朗第2匹</span>':'明治朗第1、2、3匹'}
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
 return `<div class="bet-item"><div class="bets">${labels[pool]} ${e(nos.join('、'))}</div>${text}</div>`;
}
function bets(r){const s=r.selection;if(!s)return '<span class="muted">'+(r.locked?(r.lock_type==='historical_reconstruction'?'歷史資料不足，未重建買法':'賽前資料不足，未產生買法'):'等待所需貼士')+'</span>';return s.main.map(k=>betLine(k,r)).join('')+`<div class="muted">${e(s.horses.map(h=>h.no+'.'+h.name).join('　'))}</div>`+(s.optional.length?`<div class="optional">可選：${s.optional.map(k=>betLine(k,r)).join('')}</div>`:'')+(r.locked?'<div class="locked">'+(r.lock_type==='historical_reconstruction'?'按歷史存檔重建':'已鎖定賽前選擇')+'</div>':'')}

function render(m){meeting=m;$('title').textContent=m.date+' · '+(m.venue==='HV'?'跑馬地':'沙田');$('eyebrow').textContent=history?'歷史紀錄':'最新賽日';$('subtitle').textContent=`${m.races.length}場 · 第一場 ${clock(m.races[0].off).slice(0,5)} · 馬號及馬名按官方排位核對`;$('status').textContent=m.status==='archived'?'全日紀錄已保存':m.status==='live'?'賽日收集中':m.status==='interrupted'?'抓取中斷':'等待賽日';$('updated').textContent='最近保存：'+clock(m.updated_at)+(m.manual_checked_at?' · 手動檢查：'+clock(m.manual_checked_at):'');$('cutoff').textContent=m.record_type==='historical_backfill'?'歷史補錄：'+m.backfilled_at.slice(0,10)+' '+clock(m.backfilled_at):m.tips_checked_at?'貼士已檢查：'+clock(m.tips_checked_at):'貼士檢查時間：'+m.tips_due_at.slice(0,10)+' '+clock(m.tips_due_at);const stale=m.heartbeat&&(Date.now()-Date.parse(m.heartbeat)>180000)&&m.status==='live';$('notice').textContent=m.record_type==='historical_backfill'?m.notice:stale?'抓取狀態超過3分鐘未更新，請查看工作狀態。':m.status==='interrupted'?'抓取工作中斷；未取得的資料會保留缺失狀態。':'';
$('rows').innerHTML=m.races.map(r=>`<tr><td><b>第${e(r.race)}場</b><div class="clock">${e(clock(r.off).slice(0,5))}</div></td><td>${tips(r.tips.meiji)}</td><td>${tips(r.tips.ball)}</td><td>${tips(r.tips.ma)}</td><td>${tips(r.tips.computer)}</td><td>${tips(r.index,true)}</td><td>${r.score==null?'<span class="muted">待確認</span>':`<span class="score">${r.score}</span>`}</td><td class="pattern">${pattern(r)}</td><td>${bets(r)}</td><td>${r.result?r.result.horses.map((h,i)=>`<div class="horse"><span class="muted">${(['','冠','亞','季','四'][parseInt(h.placing)]||e(h.placing))}</span><span class="num">${e(h.no)}</span>${e(h.name)}</div>`).join(''):'<span class="muted">'+(r.locked?'待官方賽果':'未開跑')+'</span>'}</td></tr>`).join('')}
async function load(){if(busy)return;busy=true;try{if(!history)await pinDataRevision();if(history){if($('dates').value)render(await read($('dates').value+'.json'))}else render(await read('latest.json'))}catch(err){$('notice').textContent=err.message+'；保留最後成功讀取資料。'}finally{busy=false}}
async function start(){try{await pinDataRevision(true);if(history){$('history-controls').hidden=false;const h=await read('history.json');if(!h.meetings.length){$('title').textContent='歷史紀錄';$('status').textContent='尚未有紀錄';$('subtitle').textContent='每個賽日結束後，會自動保存全日表格。';$('rows').innerHTML='<tr><td colspan="10">暫時沒有已結束賽日紀錄。</td></tr>';$('dates').innerHTML='<option>尚未有紀錄</option>';$('dates').disabled=true;return}$('dates').innerHTML=h.meetings.map(m=>`<option value="${e(m.date)}">${e(m.date)} · ${m.venue==='HV'?'跑馬地':'沙田'}${m.complete?'':'（部分賽果待補）'}</option>`).join('');$('dates').onchange=load}await load()}catch(err){$('notice').textContent=err.message}}
$('refresh').onclick=async()=>{try{await pinDataRevision(true);await load()}catch(err){$('notice').textContent=err.message}};await start();if(!history)setInterval(load,20000);

if(!history&&$('collect'))$('collect').onclick=()=>{
 const url='https://github.com/Ljackylau/hkjc-scraper/actions/workflows/expert-tips-run.yml';
 window.open(url,'_blank','noopener');
 $('collect-help').hidden=false;
 $('collect-help').textContent='已開啟 GitHub。登入後按 Run workflow，mode 選 manual，date 填 '+(meeting?.date||'latest')+'，再確認執行。完成後本頁會於90秒內核對最新版本，亦可按「重新讀取」即時更新；已有抓取工作時會排隊。GitHub Pages 目前不能單次點擊直接啟動工作。';
};
