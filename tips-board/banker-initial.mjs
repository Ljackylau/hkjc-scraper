const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function initialBankerView(m){
 const races=m.races.filter(r=>r.banker_initial?.status==='ready'&&r.banker_initial.reason==='initial'&&r.banker_initial.numbers?.length===5);
 const p=m.initial_v1_source;
 const note=p?`${m.date} · ${m.venue==='ST'?'沙田':'跑馬地'} · ${races.length}場${p.track==='TURF'?'草地':''} · ${p.rail}欄 · 首場 ${new Date(m.races[0].off).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false}).slice(0,5)} · 場地狀況：${p.going??'未公布（用戶提供時）'}。V1 邏輯回歸；reason=initial。用戶提供，模型未獨立驗證；未使用當日賽果選馬。原始預測時間未提供，保存時間為匯入時間。`:'';
 const horse=(r,b,n)=>{const h=b.horses?.find(h=>h.no===n)||r.horses.find(h=>h.no===n);return '<span class="horse"><b class="num">'+esc(n)+'</b> '+esc(h?.name)+'</span>'};
 return {visible:races.length>0,note,rows:races.map(r=>{
  const b=r.banker_initial,p=b.banker_top3_probability,probability=typeof p==='number'&&Number.isFinite(p)&&p>=0&&p<=1?(p*100).toFixed(1)+'%':'未提供';
  const withdrawn=(r.scratched||[]).map(n=>horse(r,b,n)+' 已退出').join('、');
  return '<tr data-initial-race="'+r.race+'"><td>R'+r.race+'</td><td>'+esc(r.distance??b.distance)+'米<br>'+esc(r.race_class??b.race_class??'班次未提供')+'</td><td>'+horse(r,b,b.numbers[0])+'</td><td>'+b.numbers.slice(1).map((n,i)=>'<div>腳'+(i+1)+' '+horse(r,b,n)+'</div>').join('')+'</td><td data-banker-probability>'+probability+'</td><td>'+esc(b.model_version||'')+' · '+esc(b.reason)+(b.source_type==='user_provided'?'<small>用戶提供</small>':'')+(withdrawn?'<div class="withdrawal">'+withdrawn+'</div>':'')+(r.initial_withdrawal?.note?'<small>'+esc(r.initial_withdrawal.note)+'</small>':'')+'</td></tr>';
 }).join('')};
}
