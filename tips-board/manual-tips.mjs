const experts=['ball','ma','computer'];
export function parseManual(text,r,key){
 const tokens=String(text).trim().split(/[\s,，、;；]+/).filter(Boolean);
 if(!tokens.length||tokens.some(x=>!/^\d{1,2}$/.test(x)))throw Error('請按次序輸入馬號，例如 3、7、10、11');
 const nos=tokens.map(Number);if(new Set(nos).size!==nos.length)throw Error('馬號不能重覆');
 if((key==='meiji'||key==='index')?nos.length!==4:nos.length>4)throw Error(key==='meiji'||key==='index'?'明治朗及指數馬須輸入4匹':'專家貼士可輸入1至4匹');
 return nos.map(no=>{const h=r.horses.find(h=>h.no===no);if(!h)throw Error('本場沒有 '+no+' 號馬');return{no,name:h.name}});
}
export const ST_METHOD='st-d-qqp-20261015';
export function chooseShaTin(r){
 const sources=experts.map(k=>r.tips[k]);r.selection=null;
 if(sources.some(s=>!['ready','absent'].includes(s.status))){r.score=null;return}
 const h=r.score=sources.filter(s=>s.horses.length).length;if(h>1)return;
 const meiji=r.tips.meiji,b=r.banker_initial;
 if([meiji,...sources].some(s=>s.source_date&&s.source_date!==r.date))return;
 if(meiji.status!=='ready'||meiji.horses.length<4||!b||b.status!=='ready'||b.as_of_race_no!==0||b.reason!=='initial'||b.numbers?.length!==5||b.date!==r.date||b.venue!=='ST'||b.race!==r.race)return;
 const M=meiji.horses.map(x=>Number(x.no)),B=b.numbers.map(Number);let order;
 if(h===0){const rest=M.slice(1);order=[M[0],B[0],...rest.filter(n=>B.slice(0,3).includes(n)),...rest.filter(n=>!B.slice(0,3).includes(n))]}
 else {const T=sources.find(s=>s.horses.length).horses.map(x=>Number(x.no));if(T.length<3)return;order=[M[2],T[1],T[2],B[0],B[3],M[0],M[1],M[3],B[1],T[0],T[3],B[2],B[4]]}
 const field=new Map(r.horses.map(x=>[Number(x.no),x])),scratched=new Set((r.scratched||[]).map(Number));
 const nos=[...new Set(order)].filter(n=>field.has(n)&&!scratched.has(n)).slice(0,3);if(nos.length!==3)return;
 r.selection={horses:nos.map(n=>({no:n,name:field.get(n).name})),main:h===0?['QP']:['Q','QP'],optional:[],method:ST_METHOD,roles:h===0?'新D':'M3+T2+T3'};
}
export function confidenceReason(r){
 if(r.venue==='HV'&&[1,2,3].includes(r.score))return '跑馬地H='+r.score+'：此條件分列為信心場';
 if(r.venue!=='ST'||![0,1].includes(r.score)||r.selection?.method!==ST_METHOD||r.selection.horses.length!==3)return null;
 const b=r.banker_initial,m=r.tips.meiji;
 if(m.status!=='ready'||!m.horses.length||b?.status!=='ready'||b.as_of_race_no!==0||b.reason!=='initial'||b.numbers?.length!==5||b.date!==r.date||b.venue!=='ST'||b.race!==r.race)return null;
 if(b.numbers.slice(0,3).map(Number).includes(Number(m.horses[0].no)))return null;
 if(r.score===0&&r.track!=='TURF')return null;
 return (r.score===0?'沙田T=0・草地':'沙田T=1')+'：明治朗首選不在膽拖網初版「膽、腳1、腳2」內';
}
export function applyShaTin(source,time=Date.now()){
 const m=structuredClone(source);if(m.venue!=='ST')return m;
 for(const r of m.races){
  r.venue=m.venue;r.date=m.date;
  // Previously stored selections remain in the source record. Historical display is a labelled recalculation.
  if((r.score===0||r.score===1||r.score==null)&&r.selection?.method!==ST_METHOD){
   const past=r.locked||time>=Date.parse(r.off);chooseShaTin(r);if(past)r.strategy_recalculated=true;
  }
 }
 return m;
}
export function chooseManual(r){
 if(r.venue==='ST'&&experts.filter(k=>r.tips[k].horses.length).length<2){chooseShaTin(r);if(r.selection)r.selection.manual=true;return}
 const sources=experts.map(k=>r.tips[k]);r.selection=null;
 if(sources.some(s=>!['ready','absent'].includes(s.status))){r.score=null;return}
 const h=r.score=sources.filter(s=>s.horses.length).length,m=r.tips.meiji.horses;let p=[];
 if(h===0)p=r.index.horses.slice(0,2);
 else if(h===1){const first=sources.find(s=>s.horses.length).horses[0],other=m.slice(0,2).find(x=>x.no!==first.no);if(other)p=[first,other]}
 else if(m.length>=3)p=m.slice(0,3);
 if(p.length!==(h<2?2:3))return;
 r.selection={horses:p,main:h<2?['W','P']:['QP'],optional:h===0?[]:h===1?['QP']:['W','Q'],manual:true};
}
export function applyManual(source,saved,time=Date.now()){
 const m=applyShaTin(source,time);
 if(!saved||saved.date!==m.date||saved.venue!==m.venue)return m;
 for(const r of m.races){
  const entry=saved.races?.[r.race];if(!entry||!Object.keys(entry.overrides||{}).length)continue;
  if(time>=Date.parse(r.off)||r.locked){
   if(entry.snapshot&&Date.parse(entry.snapshot.at)<Date.parse(r.off)){
    Object.assign(r,structuredClone(entry.snapshot.data));if(m.venue==='ST'&&(r.score===0||r.score===1||r.score==null)&&r.selection?.method!==ST_METHOD){chooseShaTin(r);r.strategy_recalculated=true}else {delete r.strategy_recalculated}r.locked=true;r.manual_local=true;r.lock_type='manual_local';
   }
   continue;
  }
  for(const [key,tip] of Object.entries(entry.overrides)){
   if(key==='index')r.index=structuredClone(tip);else if(['meiji',...experts].includes(key))r.tips[key]=structuredClone(tip);
  }
  chooseManual(r);r.manual_local=true;
  entry.snapshot={at:new Date(time).toISOString(),data:{tips:structuredClone(r.tips),index:structuredClone(r.index),score:r.score,selection:structuredClone(r.selection)}};
 }
 return m;
}
