(function(){
 'use strict';
 const P=window.PickImages,$=id=>document.getElementById(id);
 const source='https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/';
 let phases=[],selection=null,loading=null,busy=false,files=[],objectUrls=[];
 function numberView(){try{const n=P.nextNumber(localStorage);$('nextNumber').textContent=n;$('manualNextNumber').textContent=n}catch(e){$('nextNumber').textContent='無法保存';$('manualNextNumber').textContent='無法保存';$('message').textContent=e.message}}
 function view(){
  selection=P.resolve(phases,P.hkDay(),Date.now(),LiveTips.validate);
  const labels={ready:'推介已鎖定',waiting:'等待推介',unavailable:'資料未齊',finished:'等待下一場'};
  $('stateLabel').textContent=labels[selection.status];$('stateLabel').className='pill '+(selection.status==='ready'?'ready':'waiting');
  const clock=selection.off?new Date(selection.off).toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour:'2-digit',minute:'2-digit',hour12:false}):'';
  $('meeting').textContent=`${selection.date}${selection.venueName?' · '+selection.venueName:''}${selection.race?' · 第'+selection.race+'場':''}${clock?' · '+clock:''}`;
  $('reason').textContent=selection.reason;
  $('banker').textContent=selection.banker?`${selection.banker.number} ${selection.banker.name}`:'等待推介';
  $('cold').textContent=selection.cold?`${selection.cold.number} ${selection.cold.name}`:'等待推介';
  $('generate').disabled=busy||selection.status!=='ready';
  $('manualGenerate').disabled=busy;$('useLive').disabled=busy||selection.status!=='ready';
  $('autoMode').disabled=busy;$('manualMode').disabled=busy;
 }
 async function refresh(){
  if(loading)return loading;
  const date=P.hkDay();$('refresh').disabled=true;
  loading=(async()=>{
   const results=await Promise.allSettled(['early','late'].map(async phase=>{
    const response=await fetch(`${source}${date}/hkjc-${phase}/status.json?live=${Date.now()}`,{cache:'no-store',signal:AbortSignal.timeout(7000)});
    if(!response.ok)throw Error('HTTP '+response.status);
    return {...await response.json(),phase};
   }));
   phases=results.filter(r=>r.status==='fulfilled').map(r=>r.value);
   $('checked').textContent='最後檢查：'+new Date().toLocaleTimeString('zh-HK',{timeZone:'Asia/Hong_Kong',hour12:false});
   view();numberView();if($('manualMeetingDate').value===date)loadMeeting();
  })().catch(()=>{phases=[];view();$('reason').textContent='暫時未能讀取推介，請更新後再試。'}).finally(()=>{loading=null;$('refresh').disabled=false});
  return loading;
 }
 async function renderPlans(plans){
  const assets=await P.prepare();
  const images=await Promise.all(plans.map(async plan=>{
   const canvas=P.draw(plan,document.createElement('canvas'),assets);
   return {plan,blob:await P.png(canvas),name:plan.filename};
  }));
  const archive=await P.zip(images);
  return {plans,images,archive};
 }
 async function render(selection,number){
  const result=await renderPlans(P.batch(selection,number,Date.now()));
  if(P.hkDay()!==selection.date||Date.now()>=selection.off)throw Error('圖片生成期間本場已開跑，請更新下一場。');
  return {...result,selection,number};
 }
 function display(result){
  for(const url of objectUrls)URL.revokeObjectURL(url);objectUrls=[];
  $('images').replaceChildren();
  files=result.images.map(image=>new File([image.blob],image.name,{type:'image/png'}));
  for(const image of result.images){
   const card=document.createElement('article');card.className='image-card';
   const heading=document.createElement('h3');heading.textContent=`${image.plan.index} · ${image.plan.label}${image.plan.pool} $${image.plan.amount}`;
   const url=URL.createObjectURL(image.blob);objectUrls.push(url);
   const img=document.createElement('img');img.src=url;img.width=P.reference.width;img.height=P.reference.height;
   img.alt=`第${image.plan.race}場 ${image.plan.horse.number} ${image.plan.horse.name} ${image.plan.pool} $${image.plan.amount}，編號${result.number}`;
   const link=document.createElement('a');link.href=url;link.download=image.name;link.textContent='下載PNG圖片';
   card.append(heading,img,link);$('images').append(card);
  }
  const zipUrl=URL.createObjectURL(result.archive);objectUrls.push(zipUrl);
  $('zip').href=zipUrl;$('zip').download=`${result.selection.date}_R${result.selection.race}_${result.number}_四張推介.zip`;
  $('batchTitle').textContent=result.preview?'原圖格式 · 四張圖片':`${result.manual?'手動輸入 · ':''}${result.selection.venueName} 第${result.selection.race}場 · 編號${result.number}`;
  $('share').hidden=!(navigator.share&&navigator.canShare?.({files}));
  $('output').hidden=false;$('message').textContent=result.preview?'已按原圖資料顯示四張圖片格式，編號沒有遞增。':`已生成4張圖片，編號${result.number}。可下載或長按儲存。`;
 }
 $('generate').addEventListener('click',async()=>{
  if(busy)return;busy=true;view();$('generate').textContent='正在生成…';$('message').textContent='正在核對最新推介…';
  try{
   await refresh();view();if(selection.status!=='ready')throw Error(selection.reason);
   const frozen=selection;
   const generate=async()=>{
    const n=P.nextNumber(localStorage),result=await render(frozen,n);
    P.commitNumber(localStorage,n);return result;
   };
   const result=navigator.locks?.request?await navigator.locks.request(P.numberKey,generate):await generate();
   display(result);numberView();$('output').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){$('message').textContent='未能生成：'+e.message}
  finally{busy=false;$('generate').textContent='一鍵生成4張圖片';view()}
 });
 $('share').addEventListener('click',async()=>{
  try{await navigator.share({files,title:'賽日推介圖片'})}
  catch(e){if(e.name!=='AbortError')$('message').textContent='未能分享；請使用PNG或ZIP下載。'}
 });
 $('preview').addEventListener('click',async()=>{
  if(busy)return;busy=true;view();$('preview').disabled=true;
  try{
   const number=P.nextNumber(localStorage),date=P.hkDay();
   const plans=P.plans.map((p,i)=>({...P.reference,...p,index:i+1,number,date,horse:{...P.reference.horse},filename:`format_${i+1}_${p.pool}_${p.amount}.png`}));
   display({...await renderPlans(plans),preview:true,number,selection:{date,race:P.reference.race,venueName:P.reference.venue}});
   $('output').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){$('message').textContent='未能預覽：'+e.message}
  finally{busy=false;view();$('preview').disabled=false}
 });
 $('refresh').addEventListener('click',refresh);
 const draftKey='raceDay.pickImages.manualDraft.v1';
 function setMode(manual){
  if(busy)return;
  document.querySelectorAll('[data-mode="auto"]').forEach(el=>el.hidden=manual);
  $('manualPanel').hidden=!manual;$('autoMode').setAttribute('aria-pressed',String(!manual));$('manualMode').setAttribute('aria-pressed',String(manual));
 }
 $('autoMode').addEventListener('click',()=>setMode(false));$('manualMode').addEventListener('click',()=>setMode(true));
 for(const [index,p] of P.plans.entries()){
  const i=index+1,fieldset=document.createElement('fieldset');
  fieldset.innerHTML=`<legend>圖片${i} · ${p.label}</legend><label>投注類別<select id="manualPool${i}"><option>獨贏</option><option>位置</option></select></label><label>投注／支出<input id="manualAmount${i}" type="number" min="0.01" max="9999999.99" step="0.01" value="${p.amount}" required></label><label>存入<input id="manualDeposit${i}" type="number" min="0" max="9999999.99" step="0.01" value="0" required></label>`;
  $('manualEntries').append(fieldset);$('manualPool'+i).value=p.pool;
 }
 function saveDraft(){
  try{localStorage.setItem(draftKey,JSON.stringify(Object.fromEntries([...$('manualForm').querySelectorAll('input,select')].map(el=>[el.id,el.value]))))}catch(e){}
 }
 $('manualDatetime').value=P.hkDay()+'T'+P.timestamp(Date.now()).slice(-5);
 try{const draft=JSON.parse(localStorage.getItem(draftKey)||'{}');for(const el of $('manualForm').querySelectorAll('input,select'))if(typeof draft[el.id]==='string')el.value=draft[el.id]}catch(e){}
 $('manualForm').addEventListener('input',saveDraft);$('manualForm').addEventListener('change',saveDraft);

 const publicApi='https://pkrdkibqjwwgtvfdtwya.supabase.co/rest/v1/';
 const publicHeaders={apikey:'sb_publishable_pP988ZhTMZ4GDYKk8AAnYw_kAViFMFI'};
 let meetings=[],horses=[],meetingRequest=0,horseRequest=0,autoTime=false,meetingChecked=0,meetingLoading=false,rosterKey='';
 function options(select,items,placeholder){
  select.replaceChildren(new Option(placeholder,''),...items.map(x=>new Option(x.label,x.value)));
 }
 async function readJson(url,headers){
  const r=await fetch(url,{headers,cache:'no-store',signal:AbortSignal.timeout(7000)});
  if(!r.ok)throw Error('HTTP '+r.status);return r.json();
 }
 function currentMeeting(){return meetings.find(r=>`${r.venue}:${r.race}`===$('manualMeetingRace').value)}
 function fillHorse(key){
  const h=horses.find(h=>h.number===Number($('manual'+key+'Number').value));
  $('manual'+key+'Horse').value=h?String(h.number):'';
  // Never retain a previous horse's name after changing its number.
  $('manual'+key+'Name').value=h?h.name:'';saveDraft();
 }
 async function loadHorses(r,clear=false){
  const token=++horseRequest,date=$('manualMeetingDate').value;
  horses=[];rosterKey='';
  for(const key of ['Banker','Cold']){
   options($('manual'+key+'Horse'),[],'正在讀取馬匹…');
   if(clear){$('manual'+key+'Number').value='';$('manual'+key+'Name').value=''}
  }
  let found=P.roster(r.tip?.runner_rows),from='HKJC';
  if(!found.length&&r.id)try{
   const params=new URLSearchParams({select:'horse_number,horses(name_tc)',race_id:'eq.'+r.id,is_standby:'eq.false',withdrawn_at:'is.null'});
   found=P.roster(await readJson(publicApi+'race_entries?'+params,publicHeaders));from='Horse103';
  }catch(e){}
  if(!found.length){
   for(const suffix of ['t3','t30'])try{
    const value=await readJson(`${source}${date}/hkjc-${r.phase}/race_${String(r.race).padStart(2,'0')}_${suffix}.json`);
    found=P.roster(value.runner_rows);if(found.length)break;
   }catch(e){}
  }
  if(token!==horseRequest||$('manualMeetingRace').value!==`${r.venue}:${r.race}`||date!==$('manualMeetingDate').value)return;
  horses=found;rosterKey=date+'/'+r.venue+':'+r.race;
  for(const key of ['Banker','Cold']){
   options($('manual'+key+'Horse'),horses.map(h=>({value:String(h.number),label:`${h.number} · ${h.name}`})),horses.length?'請選擇馬號':'未有馬匹資料，可手動填寫');
   const h=horses.find(h=>h.number===Number($('manual'+key+'Number').value));
   if(h){$('manual'+key+'Horse').value=String(h.number);$('manual'+key+'Name').value=h.name}
  }
  $('manualMeetingStatus').textContent=horses.length?`馬匹資料：${from}。選馬號會自動填入馬名；日期時間及馬名仍可手動修改。`:'暫時未能取得本場馬名，請更新賽事再試，或手動填寫。';saveDraft();
 }
 function applyMeeting(clear=true){
  const r=currentMeeting();if(!r)return;
  autoTime=true;$('manualDatetime').value=P.twoMinutesBefore(r.off);
  $('manualVenue').value=r.venue;$('manualRace').value=r.race;
  $('manualMeetingStatus').textContent='已填入開跑前2分鐘；正在讀取馬匹。';saveDraft();loadHorses(r,clear);
 }
 async function loadMeeting(force=false){
  const date=$('manualMeetingDate').value;if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return;
  if(!force&&(meetingLoading||Date.now()-meetingChecked<15000))return;
  const token=++meetingRequest;meetingLoading=true;meetingChecked=Date.now();
  $('manualMeetingRefresh').disabled=true;
  if(!meetings.length)$('manualMeetingStatus').textContent='正在讀取賽事…';
  try{
   const tasks=[readJson(publicApi+'races?'+new URLSearchParams({select:'id,race_number,post_time,venue',race_date:'eq.'+date,order:'race_number.asc'}),publicHeaders),
    ...['early','late'].map(phase=>date===P.hkDay()?Promise.resolve(phases.find(p=>p.phase===phase)||null):readJson(`${source}${date}/hkjc-${phase}/status.json`).then(p=>({...p,phase})))];
   const results=await Promise.allSettled(tasks);
   if(token!==meetingRequest||date!==$('manualMeetingDate').value)return;
   const rows=results[0].status==='fulfilled'&&Array.isArray(results[0].value)?results[0].value:[];
   const statuses=results.slice(1).filter(r=>r.status==='fulfilled'&&r.value).map(r=>r.value);
   const chosen=$('manualMeetingRace').value,old=currentMeeting();meetings=P.meeting(statuses,date,rows);
   options($('manualMeetingRace'),meetings.map(r=>({value:`${r.venue}:${r.race}`,label:`${r.venue==='ST'?'沙田':'跑馬地'} 第${r.race}場 · 開跑 ${P.timestamp(r.off).slice(-5)} → ${P.timestamp(r.off-120000).slice(-5)}`})),'請選擇賽事');
   $('manualMeetingRace').value=meetings.some(r=>`${r.venue}:${r.race}`===chosen)?chosen:'';
   const r=currentMeeting();
   if(r){
    if(autoTime){$('manualDatetime').value=P.twoMinutesBefore(r.off);saveDraft()}
    if(force||rosterKey!==date+'/'+r.venue+':'+r.race)loadHorses(r);
    if(old&&old.off!==r.off&&autoTime)$('manualMeetingStatus').textContent='開跑時間已更新；日期時間已同步至新開跑前2分鐘。';
   }else $('manualMeetingStatus').textContent=meetings.length?'選擇賽事即可填入開跑前2分鐘及場地、場次。':'這個日期未有賽事資料；仍可手動輸入日期時間、場次及馬名。';
  }finally{if(token===meetingRequest){meetingLoading=false;$('manualMeetingRefresh').disabled=false}}
 }
 $('manualMeetingDate').value=$('manualMeetingDate').value||$('manualDatetime').value.slice(0,10)||P.hkDay();
 $('manualMeetingRace').addEventListener('change',()=>{if(currentMeeting())applyMeeting();else autoTime=false});
 $('manualMeetingRefresh').addEventListener('click',()=>loadMeeting(true));
 $('manualMeetingDate').addEventListener('change',()=>{
  ++horseRequest;meetings=[];horses=[];rosterKey='';autoTime=false;meetingChecked=0;
  options($('manualMeetingRace'),[],'請選擇賽事');
  for(const key of ['Banker','Cold']){options($('manual'+key+'Horse'),[],'請先選擇賽事');$('manual'+key+'Number').value='';$('manual'+key+'Name').value=''}
  saveDraft();loadMeeting(true);
 });
 $('manualDatetime').addEventListener('input',()=>{
  autoTime=false;const date=$('manualDatetime').value.slice(0,10);
  if(date&&date!==$('manualMeetingDate').value){$('manualMeetingDate').value=date;$('manualMeetingDate').dispatchEvent(new Event('change'))}
 });
 for(const key of ['Banker','Cold']){
  $('manual'+key+'Horse').addEventListener('change',()=>{$('manual'+key+'Number').value=$('manual'+key+'Horse').value;fillHorse(key)});
  $('manual'+key+'Number').addEventListener('input',()=>fillHorse(key));
 }
 for(const id of ['manualVenue','manualRace'])$(id).addEventListener('change',()=>{
  const key=$('manualVenue').value+':'+$('manualRace').value;
  $('manualMeetingRace').value=meetings.some(r=>`${r.venue}:${r.race}`===key)?key:'';
  ++horseRequest;horses=[];rosterKey='';
  for(const role of ['Banker','Cold']){options($('manual'+role+'Horse'),[],'請先選擇賽事');$('manual'+role+'Number').value='';$('manual'+role+'Name').value=''}
  if(currentMeeting())applyMeeting();else autoTime=false;saveDraft();
 });
 loadMeeting(true);

 $('useLive').addEventListener('click',()=>{
  view();if(selection.status!=='ready')return;
  $('manualMeetingDate').value=selection.date;$('manualDatetime').value=P.twoMinutesBefore(selection.off);$('manualVenue').value=selection.venue;$('manualRace').value=selection.race;
  $('manualMeetingRace').value=selection.venue+':'+selection.race;autoTime=true;
  for(const [role,key] of [['banker','Banker'],['cold','Cold']]){$('manual'+key+'Number').value=selection[role].number;$('manual'+key+'Name').value=selection[role].name}
  saveDraft();const r=currentMeeting();if(r)loadHorses(r);
 });
 $('manualForm').addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;
  const input={datetime:$('manualDatetime').value,venue:$('manualVenue').value,race:$('manualRace').value,
   banker:{number:$('manualBankerNumber').value,name:$('manualBankerName').value},
   cold:{number:$('manualColdNumber').value,name:$('manualColdName').value},
   entries:P.plans.map((_,i)=>({pool:$('manualPool'+(i+1)).value,amount:$('manualAmount'+(i+1)).value,deposit:$('manualDeposit'+(i+1)).value}))};
  busy=true;view();$('manualGenerate').textContent='正在生成…';$('message').textContent='正在生成圖片…';saveDraft();
  try{
   const generate=async()=>{
    const number=P.nextNumber(localStorage),plans=P.manualBatch(input,number),result=await renderPlans(plans);
    P.commitNumber(localStorage,number);
    return {...result,manual:true,number,selection:{date:plans[0].date,race:plans[0].race,venueName:plans[0].venue}};
   };
   const result=navigator.locks?.request?await navigator.locks.request(P.numberKey,generate):await generate();
   display(result);numberView();$('output').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){$('message').textContent='未能生成：'+e.message}
  finally{busy=false;$('manualGenerate').textContent='生成4張圖片';view()}
 });
 window.addEventListener('storage',e=>{if(e.key===P.numberKey)numberView()});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
 P.prepare().catch(()=>{});numberView();refresh();setInterval(()=>{view();if(!document.hidden&&!busy){
  const seconds=selection?.off?(selection.off-Date.now())/1000:Infinity;
  if(seconds<=280&&seconds>0||Date.now()-(window._pickImagesPoll||0)>=15000){window._pickImagesPoll=Date.now();refresh()}
 }},2000);
})();
