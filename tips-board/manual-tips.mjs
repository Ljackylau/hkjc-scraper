const experts=['ball','ma','computer'];
export function parseManual(text,r,key){
 const tokens=String(text).trim().split(/[\s,，、;；]+/).filter(Boolean);
 if(!tokens.length||tokens.some(x=>!/^\d{1,2}$/.test(x)))throw Error('請按次序輸入馬號，例如 3、7、10、11');
 const nos=tokens.map(Number);if(new Set(nos).size!==nos.length)throw Error('馬號不能重覆');
 if((key==='meiji'||key==='index')?nos.length!==4:nos.length>4)throw Error(key==='meiji'||key==='index'?'明治朗及指數馬須輸入4匹':'專家貼士可輸入1至4匹');
 return nos.map(no=>{const h=r.horses.find(h=>h.no===no);if(!h)throw Error('本場沒有 '+no+' 號馬');return{no,name:h.name}});
}
export function chooseManual(r){
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
 const m=structuredClone(source);
 if(!saved||saved.date!==m.date||saved.venue!==m.venue)return m;
 for(const r of m.races){
  const entry=saved.races?.[r.race];if(!entry||!Object.keys(entry.overrides||{}).length)continue;
  if(time>=Date.parse(r.off)||r.locked){
   if(entry.snapshot&&Date.parse(entry.snapshot.at)<Date.parse(r.off)){
    Object.assign(r,structuredClone(entry.snapshot.data));r.locked=true;r.manual_local=true;r.lock_type='manual_local';
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
