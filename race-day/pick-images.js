/* All four images use one frozen race and one batch number. */
(function(root){
 'use strict';
 const numberKey='raceDay.pickImages.nextNumber.v1',startNumber=7720,step=3;
 const plans=[{role:'banker',label:'膽馬',pool:'獨贏',amount:100},
  {role:'banker',label:'膽馬',pool:'位置',amount:300},
  {role:'cold',label:'冷馬',pool:'獨贏',amount:50},
  {role:'cold',label:'冷馬',pool:'位置',amount:150}];
 function hkParts(at=Date.now()){
  return Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(at)).map(p=>[p.type,p.value]));
 }
 function hkDay(at=Date.now()){const p=hkParts(at);return `${p.year}-${p.month}-${p.day}`}
 function timestamp(at){const p=hkParts(at);return `${p.day}-${p.month}-${p.year} ${p.hour}:${p.minute}`}
 function nextNumber(storage){
  const raw=storage.getItem(numberKey);
  if(raw===null)return startNumber;
  const n=Number(raw);
  if(!/^\d+$/.test(raw)||!Number.isSafeInteger(n)||n<startNumber||(n-startNumber)%step!==0)throw Error('已保存編號無效；請保留目前頁面並檢查瀏覽器儲存。');
  return n;
 }
 function commitNumber(storage,n){
  if(nextNumber(storage)!==n)throw Error('其他分頁已使用這個編號，請重新生成。');
  if(!Number.isSafeInteger(n+step))throw Error('編號已超出可用範圍。');
  storage.setItem(numberKey,String(n+step));
  if(nextNumber(storage)!==n+step)throw Error('未能保存下一個編號，請允許此網站儲存資料。');
 }
 function resolve(phases,date,at,validate){
  const fail=(status,reason,extra={})=>({status,reason,date,...extra});
  if(date!==hkDay(at))return fail('unavailable','只可使用當日推介，未有沿用其他賽日。');
  if(!phases.length)return fail('waiting','今天尚未有賽事資料，或 Runner 尚未啟動。');
  if(phases.some(p=>p.date!==date))return fail('unavailable','收到其他賽日資料，請更新後再試。');
  const venues=new Set(phases.map(p=>p.venue));
  if(venues.size!==1||!['ST','HV'].includes([...venues][0]))return fail('unavailable','未有可核對的當日場地資料，等待 Runner 更新。');
  const venue=[...venues][0],upcoming=[],seen=new Set();
  for(const p of phases){
   const keys=new Set([...Object.keys(p.races||{}),...Object.keys(p.independent_tips||{})]);
   for(const key of keys){
    const race=Number(key),tip=p.independent_tips?.[key],target=p.races?.[key]?.target;
    if(!Number.isInteger(race)||race<1||race>14||seen.has(race))return fail('unavailable','場次資料不完整或重複。');
    seen.add(race);
    const off=target?Date.parse(target)+180000:Date.parse(tip?.off);
    if(!Number.isFinite(off)||hkDay(off)!==date)return fail('unavailable','未有可核對的當日開跑時間。');
    if(off>at)upcoming.push({race,off,tip,phase:p.phase,updated_at:p.updated_at});
   }
  }
  if(!upcoming.length)return fail('finished','已收到資料的場次均已開跑；等待下一場資料。',{venue});
  upcoming.sort((a,b)=>a.off-b.off||a.race-b.race);
  const chosen=upcoming[0],extra={...chosen,venue,venueName:venue==='ST'?'沙田':'跑馬地'};
  if(!chosen.tip)return fail('waiting','等待本場 T−3 推介鎖定。',extra);
  try{
   const tip=validate(chosen.tip,date,chosen.race);
   if(tip.status!=='ready')return fail('unavailable','膽馬資料不足：'+(tip.reason||'等待有效賽前快照'),extra);
   if(Date.parse(tip.off)!==chosen.off||Date.parse(tip.freeze)!==chosen.off-190000||Date.parse(tip.cutoff)!==chosen.off-180000)throw Error('推介與目前開跑時間不符');
   if(at<Date.parse(tip.freeze))return fail('waiting','等待本場賽前推介鎖定。',extra);
   if(tip.reconstruction)throw Error('重建資料不作即場圖片');
   if(tip.cold_status!=='ready')return fail('unavailable','冷馬資料不足：'+(tip.cold_reason||'等待有效賽前快照'),extra);
   if((tip.cold||[]).length!==1)return fail('unavailable','本場沒有符合條件的冷馬，未能生成完整四張。',extra);
   const horse=n=>{
    const number=Number(n);
    if(!Number.isInteger(number)||number<1||number>14)throw Error('馬號無效');
    const rows=(tip.runner_rows||[]).filter(r=>Number(r[0])===number);
    if(rows.length!==1||!String(rows[0][2]||'').trim())throw Error('缺少推薦馬匹名稱');
    if(/SCR|退出|退賽/i.test(rows[0].join(' ')))throw Error('推薦馬匹已標示退出');
    return {number,name:String(rows[0][2]).replace(/\s+/g,' ').trim()};
   };
   return {...extra,date,status:'ready',reason:'膽馬及冷馬已鎖定，可生成四張。',banker:horse(tip.banker),cold:horse(tip.cold[0]),tip};
  }catch(e){return fail('unavailable','推介未能核對：'+e.message,extra)}
 }
 function batch(selection,number,at){
  if(selection.status!=='ready'||hkDay(at)!==selection.date||at>=selection.off)throw Error('本場已開跑或推介未就緒，請更新後再試。');
  const weekday=new Intl.DateTimeFormat('zh-HK',{timeZone:'Asia/Hong_Kong',weekday:'long'}).format(new Date(selection.off));
  return plans.map((p,i)=>({...p,deposit:0,index:i+1,number,date:selection.date,race:selection.race,venue:selection.venueName,
   horse:{...selection[p.role]},weekday,time:timestamp(at),generatedAt:at,
   filename:`${selection.date}_R${selection.race}_${number}_${i+1}_${p.label}_${p.pool}_${p.amount}.png`}));
 }
 function manualBatch(input,number){
  const value=String(input.datetime||'');
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw Error('請填寫完整日期及時間。');
  const at=Date.parse(value+':00+08:00');
  if(!Number.isFinite(at)||hkDay(at)!==value.slice(0,10)||timestamp(at).slice(-5)!==value.slice(-5))throw Error('日期或時間無效。');
  const race=Number(input.race);
  if(!Number.isInteger(race)||race<1||race>14)throw Error('場次須為1至14。');
  if(!['ST','HV'].includes(input.venue))throw Error('請選擇場地。');
  const horses={};
  for(const role of ['banker','cold']){
   const h=input[role]||{},n=Number(h.number),name=String(h.name||'').trim().replace(/\s+/g,' ');
   if(!Number.isInteger(n)||n<1||n>14||!name||name.length>24)throw Error('請填寫有效馬號（1至14）及馬名。');
   horses[role]={number:n,name};
  }
  if(!Array.isArray(input.entries)||input.entries.length!==4)throw Error('需要四張圖片的投注資料。');
  const money=(value,positive)=>{
   const n=Number(value);
   if(String(value??'').trim()===''||!Number.isFinite(n)||n<(positive?0.01:0)||n>9999999.99||Math.abs(n*100-Math.round(n*100))>0.00001)throw Error('金額須為有效數字，最多兩位小數。');
   return n;
  };
  const date=hkDay(at),venue=input.venue==='ST'?'沙田':'跑馬地';
  const weekday=new Intl.DateTimeFormat('zh-HK',{timeZone:'Asia/Hong_Kong',weekday:'long'}).format(new Date(at));
  return plans.map((p,i)=>{
   const entry=input.entries[i];if(!['獨贏','位置'].includes(entry.pool))throw Error('投注類別須為獨贏或位置。');
   const amount=money(entry.amount,true),deposit=money(entry.deposit,false);
   return {...p,pool:entry.pool,amount,deposit,index:i+1,number,date,race,venue,weekday,time:timestamp(at),horse:horses[p.role],
    filename:`${date}_R${race}_${number}_${i+1}_${p.label}_${entry.pool}_${amount}.png`};
  });
 }
 const reference={width:750,height:424,pool:'獨贏',venue:'沙田',weekday:'星期日',race:4,
  horse:{number:10,name:'志醒大將'},amount:50000,deposit:200000,time:'06-09-2026 13:48'};
 const assetBase='assets/';let assets=null,assetPromise=null;
 function prepare(){
  if(assetPromise)return assetPromise;
  assetPromise=(async()=>{
   if(typeof FontFace==='undefined'||!document.fonts)throw Error('瀏覽器未能載入圖片字體。');
   const image=new Image();image.decoding='async';
   const template=new Promise((resolve,reject)=>{
    image.onload=()=>image.naturalWidth===reference.width&&image.naturalHeight===reference.height?resolve(image):reject(Error('原圖尺寸不符。'));
    image.onerror=()=>reject(Error('原圖版面未能載入。'));image.src=assetBase+'record-layout-20261003.png';
   });
   const fontFiles=[['RecordCJK','record-cjk-500.woff2'],['RecordLatin','record-latin-500.ttf']];
   const fonts=fontFiles.map(async([family,file])=>{
    const face=await new FontFace(family,`url("${assetBase+file}")`,{style:'normal',weight:'400'}).load();
    document.fonts.add(face);return face;
   });
   const [loaded]=await Promise.all([template,...fonts]);
   assets={template:loaded};return assets;
  })().catch(e=>{assetPromise=null;throw e});
  return assetPromise;
 }
 function fields(plan){
  return [
   {value:plan.time,original:reference.time,rect:[304,6,410,55],x:309,y:43},
   {value:plan.pool,original:reference.pool,rect:[304,79,410,54],x:309,y:117},
   {value:`${plan.venue} ${plan.weekday} ${plan.pool} 第${plan.race}場`,original:'沙田 星期日 獨贏 第4場',rect:[304,151,410,48],x:309,y:189},
   {value:`${plan.horse.number} ${plan.horse.name} $${plan.amount}`,original:'10 志醒大將 $50000',rect:[304,199,410,47],x:309,y:228},
   {value:plan.amount.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}),original:'50,000.00',rect:[328,263,386,55],x:327,y:301},
   {value:(plan.deposit??0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}),original:'200,000.00',rect:[328,337,386,55],x:327,y:374}
  ];
 }
 function draw(plan,canvas,loaded=assets){
  if(!loaded?.template)throw Error('圖片版面及字體尚未載入，請稍後再試。');
  canvas.width=reference.width;canvas.height=reference.height;
  const c=canvas.getContext('2d');if(!c)throw Error('瀏覽器未能建立圖片。');
  c.drawImage(loaded.template,0,0);
  c.font='400 32px "RecordLatin","RecordCJK"';c.textBaseline='alphabetic';c.textAlign='left';
  for(const field of fields(plan)){
   if(field.value===field.original)continue;
   if(c.measureText(field.value).width>field.rect[2]-6)throw Error('文字超出原圖欄位，未有更改字體大小。');
   c.save();c.beginPath();c.rect(...field.rect);c.clip();c.fillStyle='#fff';c.fillRect(...field.rect);
   c.fillStyle='#000';c.fillText(field.value,field.x,field.y);c.restore();
  }
  return canvas;
 }
 function png(canvas){return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('未能匯出PNG圖片。')),'image/png'))}
 // ZIP "stored" entries: PNG already compresses its pixels; no external scripts needed.
 const crcTable=Uint32Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0});
 function crc32(bytes){let n=0xffffffff;for(const b of bytes)n=crcTable[(n^b)&255]^(n>>>8);return (n^0xffffffff)>>>0}
 async function zip(files){
  const encoder=new TextEncoder(),locals=[],central=[];let offset=0,centralLength=0;
  for(const file of files){
   const name=encoder.encode(file.name),bytes=new Uint8Array(await file.blob.arrayBuffer()),crc=crc32(bytes);
   const local=new Uint8Array(30+name.length),l=new DataView(local.buffer);
   l.setUint32(0,0x04034b50,true);l.setUint16(4,20,true);l.setUint16(6,0x800,true);l.setUint16(12,33,true);
   l.setUint32(14,crc,true);l.setUint32(18,bytes.length,true);l.setUint32(22,bytes.length,true);l.setUint16(26,name.length,true);local.set(name,30);
   locals.push(local,bytes);
   const record=new Uint8Array(46+name.length),r=new DataView(record.buffer);
   r.setUint32(0,0x02014b50,true);r.setUint16(4,20,true);r.setUint16(6,20,true);r.setUint16(8,0x800,true);r.setUint16(14,33,true);
   r.setUint32(16,crc,true);r.setUint32(20,bytes.length,true);r.setUint32(24,bytes.length,true);r.setUint16(28,name.length,true);r.setUint32(42,offset,true);record.set(name,46);
   central.push(record);centralLength+=record.length;offset+=local.length+bytes.length;
  }
  const end=new Uint8Array(22),e=new DataView(end.buffer);e.setUint32(0,0x06054b50,true);
  e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,centralLength,true);e.setUint32(16,offset,true);
  return new Blob([...locals,...central,end],{type:'application/zip'});
 }
 const api={plans,numberKey,startNumber,step,hkDay,timestamp,nextNumber,commitNumber,resolve,batch,manualBatch,reference,prepare,fields,draw,png,zip,crc32};
 if(typeof module!=='undefined')module.exports=api;else root.PickImages=api;
})(typeof window==='undefined'?globalThis:window);
