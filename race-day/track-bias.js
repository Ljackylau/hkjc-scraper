(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.TrackBias=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const VERSION=1,KEY='raceDayTrackBiasV1';
 const directions=['unknown','neutral','inside','outside'];
 const families=['turn1200_1800','straight1000'];
 function validate(event){
  if(!event||event.version!==VERSION||!/^\d{4}-\d{2}-\d{2}$/.test(event.date)||!['ST','HV'].includes(event.venue)||!families.includes(event.family)||!/^([ABC](\+\d+)?)$/.test(event.rail)||!directions.includes(event.direction)||!['low','medium','high'].includes(event.confidence)||!['observe','watering','rolling','rain','reset'].includes(event.kind))throw Error('請完整選擇場地、欄位及偏差');
  if(!['unknown','neutral','front','back'].includes(event.pace))throw Error('跑法訊號無效');
  if(!Number.isInteger(event.from)||!Number.isInteger(event.until)||event.from<1||event.until<event.from||event.until>20)throw Error('生效場次須介乎1至20，結束不得早於開始');
  if(!Number.isFinite(Date.parse(event.created_at)))throw Error('缺有效編輯時間');
  if(!Array.isArray(event.evidence)||event.evidence.some(n=>!Number.isInteger(n)||n<1||n>=event.from)||new Set(event.evidence).size!==event.evidence.length)throw Error('依據場次須早於生效場次，並且不可重複');
  if(event.kind==='observe'&&!['unknown','neutral'].includes(event.direction)&&!event.evidence.length)throw Error('偏差調整須填已完成的依據場次');
  if(event.kind==='observe'&&event.evidence.length===1&&event.confidence!=='low')throw Error('只有一場依據時，請先使用低信心');
  if(event.kind!=='observe'&&event.direction!=='unknown')throw Error('保養／天雨後須先重設為未知，再重新觀察');
  if(typeof event.note!=='string'||event.note.length>300)throw Error('備註最多300字');
  return event;
 }
 function read(storage){try{const rows=JSON.parse(storage.getItem(KEY)||'[]');if(!Array.isArray(rows))return [];return rows.filter(e=>{try{validate(e);return true}catch{return false}})}catch{return []}}
 function same(a,b){return a.date===b.date&&a.venue===b.venue&&a.family===b.family&&a.rail===b.rail;}
 function save(storage,rows,event){validate(event);
  const reset=rows.filter(e=>same(e,event)&&e.kind!=='observe'&&e.from<=event.from&&Date.parse(e.created_at)<=Date.parse(event.created_at)).at(-1);
  if(reset&&event.kind==='observe'&&['inside','outside'].includes(event.direction)&&event.evidence.some(n=>n<reset.from))throw Error('保養／重設後，請使用重設場次或之後的新賽果');
  const next=[...rows,event];storage.setItem(KEY,JSON.stringify(next));return next;
 }
 function scope(e,c){return c&&c.status==='ready'&&e.date===c.date&&e.venue===c.venue&&c.track==='TURF'&&e.rail===c.rail&&e.family===(c.venue==='ST'&&c.distance===1000?'straight1000':c.distance>=1200&&c.distance<=1800?'turn1200_1800':'other')}
 function active(rows,tip,context){
  const freeze=Date.parse(tip.freeze),n=Number(tip.race);
  if(!Number.isFinite(freeze)||context?.race!==n||context.date!==tip.date||Date.parse(context.prepared_at)>freeze||!Number.isFinite(Date.parse(context.prepared_at)))return null;
  if(tip.status==='ready'&&(!Number.isFinite(Date.parse(tip.received_at))||Date.parse(tip.received_at)>freeze))return null;
  const eligible=rows.filter(e=>{try{validate(e);return scope(e,context)&&e.from<=n&&e.evidence.every(k=>k<n)&&Date.parse(e.created_at)<=freeze}catch{return false}}).map((e,i)=>({e,i})).sort((a,b)=>Date.parse(b.e.created_at)-Date.parse(a.e.created_at)||b.i-a.i);
  let latest=eligible[0]?.e;
  const reset=eligible.find(x=>x.e.kind!=='observe')?.e;
  if(reset&&latest?.kind==='observe'&&['inside','outside'].includes(latest.direction)&&latest.evidence.some(k=>k<reset.from))latest=reset;
  // An expired or reset entry must never resurrect an older bias.
  return latest&&latest.until>=n?latest:null;
 }
 function preview(tip,event,context){
  const out={status:'unchanged',legs:[...(tip.legs||[])],banker:tip.banker,changed:false,manual:true,reason:'沒有截止前適用的編輯'};
  if(!event)return out;
  out.event=event;
  if(event.kind!=='observe'||event.direction==='unknown')return {...out,reason:'場地已重設為未知；等待新的賽果觀察'};
  if(event.direction==='neutral')return {...out,reason:'未見明顯檔位偏差，保留原四腳'};
  if(event.family==='straight1000')return {...out,reason:'直路獨立觀察；暫不套用轉彎草地換腳規則'};
  if(tip.status!=='ready'||tip.legs_status!=='ready'||tip.legs.length!==4||new Set(tip.legs).size!==4||tip.legs.includes(tip.banker))return {...out,reason:'缺有效原四腳'};
  const scores=new Map(Object.entries(tip.leg_scores||{}).map(([h,v])=>[Number(h),Number(v)]).filter(([h,v])=>Number.isInteger(h)&&Number.isFinite(v)));
  const rows=tip.runner_rows||[],draws=new Map(rows.map(r=>[Number(r[0]),Number(r[3])]));
  if(draws.size<5||draws.size!==rows.length||new Set(draws.values()).size!==draws.size||[...draws.values()].some(d=>!Number.isInteger(d)||d<=0)||[tip.banker,...tip.legs].some(h=>!draws.has(h)))return {...out,reason:'缺有效賽前檔位'};
  const preferred=h=>event.direction==='inside'?draws.get(h)<=Math.ceil(draws.size/3):draws.get(h)>Math.ceil(2*draws.size/3);
  if(tip.legs.filter(preferred).length>=2)return {...out,reason:'原腳已有兩匹符合檔位方向'};
  const add=[...draws.keys()].filter(h=>h!==tip.banker&&!tip.legs.includes(h)&&preferred(h)&&scores.has(h)).sort((a,b)=>scores.get(b)-scores.get(a)||a-b);
  const remove=tip.legs.filter(h=>!preferred(h)&&scores.has(h)).sort((a,b)=>scores.get(a)-scores.get(b)||tip.legs.indexOf(b)-tip.legs.indexOf(a));
  if(!add.length||!remove.length)return {...out,reason:'沒有可用的替換候選'};
  const legs=[...tip.legs];legs[legs.indexOf(remove[0])]=add[0];
  return {...out,status:'adjusted',legs,changed:true,added:add[0],removed:remove[0],reason:`手動${event.direction==='inside'?'內':'外'}檔觀察：${remove[0]}號換${add[0]}號；保留原膽`};
 }
 return {VERSION,KEY,validate,read,save,active,preview,matches:scope};
});
