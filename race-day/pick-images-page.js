(function(){
 'use strict';
 const P=window.PickImages,$=id=>document.getElementById(id);
 const source='https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/race-day-data/race-day-data/';
 let phases=[],selection=null,loading=null,busy=false,files=[],objectUrls=[];
 function numberView(){try{$('nextNumber').textContent=P.nextNumber(localStorage)}catch(e){$('nextNumber').textContent='無法保存';$('message').textContent=e.message}}
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
   view();numberView();
  })().catch(()=>{phases=[];view();$('reason').textContent='暫時未能讀取推介，請更新後再試。'}).finally(()=>{loading=null;$('refresh').disabled=false});
  return loading;
 }
 async function renderPlans(plans){
  if(document.fonts?.ready)await document.fonts.ready;
  const images=await Promise.all(plans.map(async plan=>{
   const canvas=P.draw(plan,document.createElement('canvas'));
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
   const img=document.createElement('img');img.src=url;img.width=1125;img.height=1100;
   img.alt=`第${image.plan.race}場 ${image.plan.horse.number} ${image.plan.horse.name} ${image.plan.pool} $${image.plan.amount}，未提交投注，編號${result.number}`;
   const link=document.createElement('a');link.href=url;link.download=image.name;link.textContent='下載PNG圖片';
   card.append(heading,img,link);$('images').append(card);
  }
  const zipUrl=URL.createObjectURL(result.archive);objectUrls.push(zipUrl);
  $('zip').href=zipUrl;$('zip').download=`${result.selection.date}_R${result.selection.race}_${result.number}_四張推介.zip`;
  $('batchTitle').textContent=result.demo?'版面示例 · 虛構馬名及場次':`${result.selection.venueName} 第${result.selection.race}場 · 編號${result.number}`;
  $('share').hidden=!(navigator.share&&navigator.canShare?.({files}));
  $('output').hidden=false;$('message').textContent=result.demo?'示例圖片已生成，未使用正式編號。':`已生成4張圖片，編號${result.number}。可下載或長按儲存。`;
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
   const at=Date.now(),weekday=new Intl.DateTimeFormat('zh-HK',{timeZone:'Asia/Hong_Kong',weekday:'long'}).format(new Date(at));
   const plans=P.plans.map((p,i)=>({...p,demo:true,index:i+1,number:'示例',date:P.hkDay(at),race:1,venue:'示例場地',weekday,time:P.timestamp(at),
    horse:{number:p.role==='banker'?2:9,name:p.role==='banker'?'示例膽馬':'示例冷馬'},filename:`example_${i+1}_${p.label}_${p.pool}_${p.amount}.png`}));
   display({...await renderPlans(plans),demo:true,number:'示例',selection:{date:P.hkDay(at),race:1,venueName:'示例場地'}});
   $('output').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){$('message').textContent='未能預覽：'+e.message}
  finally{busy=false;view();$('preview').disabled=false}
 });
 $('refresh').addEventListener('click',refresh);
 window.addEventListener('storage',e=>{if(e.key===P.numberKey)numberView()});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
 numberView();refresh();setInterval(()=>{view();if(!document.hidden&&!busy){
  const seconds=selection?.off?(selection.off-Date.now())/1000:Infinity;
  if(seconds<=280&&seconds>0||Date.now()-(window._pickImagesPoll||0)>=15000){window._pickImagesPoll=Date.now();refresh()}
 }},2000);
})();
