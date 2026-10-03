/* Deterministic plan images. All four images use one frozen race and one batch number. */
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
  return plans.map((p,i)=>({...p,index:i+1,number,date:selection.date,race:selection.race,venue:selection.venueName,
   horse:{...selection[p.role]},weekday,time:timestamp(at),generatedAt:at,
   filename:`${selection.date}_R${selection.race}_${number}_${i+1}_${p.label}_${p.pool}_${p.amount}.png`}));
 }
 function rounded(ctx,x,y,w,h,r){
  ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();
 }
 const font='"PingFang TC","Microsoft JhengHei","Noto Sans CJK TC","Noto Sans TC",sans-serif';
 function text(ctx,value,x,y,size=46,color='#111',weight=500,maxWidth){
  ctx.fillStyle=color;ctx.textBaseline='alphabetic';
  let actual=size;ctx.font=`${weight} ${actual}px ${font}`;
  while(maxWidth&&ctx.measureText(value).width>maxWidth&&actual>24){actual--;ctx.font=`${weight} ${actual}px ${font}`}
  ctx.fillText(value,x,y);
 }
 function draw(plan,canvas){
  canvas.width=1125;canvas.height=1100;
  const c=canvas.getContext('2d');if(!c)throw Error('瀏覽器未能建立圖片。');
  c.fillStyle='#f1f1f1';c.fillRect(0,0,1125,1100);c.fillStyle='#fff';c.fillRect(0,0,1125,165);
  text(c,plan.demo?'版面示例':'投注計劃',36,69,58,'#111',700);text(c,'時間:'+plan.time,36,130,40,'#555',500);
  c.fillStyle='#f9f9f9';c.fillRect(0,165,1125,136);
  c.strokeStyle='#b97820';c.lineWidth=7;c.beginPath();c.arc(72,220,32,0,2*Math.PI);c.stroke();
  c.beginPath();c.moveTo(72,198);c.lineTo(72,220);c.lineTo(89,230);c.stroke();
  text(c,plan.demo?'示例圖片 · 虛構資料 · 未提交':'推介圖片 · 未提交投注',133,235,44,'#111',650,950);
  const x=24,y=324,w=1077,h=690;
  c.save();c.shadowColor='#00000018';c.shadowBlur=22;c.shadowOffsetY=8;rounded(c,x,y,w,h,24);c.fillStyle='#fff';c.fill();c.restore();
  c.save();rounded(c,x,y,w,h,24);c.clip();c.fillStyle='#90918f';c.fillRect(x,y,w,100);
  text(c,`圖${plan.index} · ${plan.label}`,60,390,52,'#fff',600);
  rounded(c,807,339,265,75,38);c.fillStyle='#ffe000';c.fill();text(c,'投注計劃',848,391,43,'#111',600);
  const rows=[{top:424,height:102,label:'狀況',value:'未提交投注',color:'#9a6111'},
   {top:526,height:102,label:'編號',value:String(plan.number)},
   {top:628,height:102,label:'投注類別',value:plan.pool},
   {top:730,height:174,label:'細節'},
   {top:904,height:110,label:'金額',value:'$'+plan.amount.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}];
  for(const row of rows){
   if(row.top===424){c.fillStyle='#fff4df';c.fillRect(410,row.top,w-386,row.height)}
   c.strokeStyle='#ccc';c.lineWidth=3;c.beginPath();c.moveTo(24,row.top);c.lineTo(1101,row.top);c.stroke();
   c.beginPath();c.moveTo(409,row.top+9);c.lineTo(409,row.top+row.height-9);c.stroke();
   text(c,row.label,60,row.top+68,47,'#111',500);
   if(row.value)text(c,row.value,446,row.top+68,49,row.color||'#111',500,622);
  }
  text(c,`${plan.venue} ${plan.weekday} ${plan.pool} 第${plan.race}場`,446,795,40,'#111',500,625);
  text(c,`${plan.horse.number} ${plan.horse.name} $${plan.amount}`,446,852,43,'#111',500,625);
  c.restore();text(c,plan.demo?'版面示例｜馬名及場次均為示例，未提交投注':'推介計劃｜圖片不代表已投注或已接納',34,1070,28,'#666',500);
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
 const api={plans,numberKey,startNumber,step,hkDay,timestamp,nextNumber,commitNumber,resolve,batch,draw,png,zip,crc32};
 if(typeof module!=='undefined')module.exports=api;else root.PickImages=api;
})(typeof window==='undefined'?globalThis:window);
