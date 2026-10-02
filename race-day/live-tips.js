/* Live tips use two small collector summaries, independent of Horse103. */
(function(root){
 const policy='cold_top2_priority_v2_exploratory_2026-10-02';
 const fusion='f2_qp1_cold_10_30_exploratory_2026_10_02';
 function validate(tip,date,race){
  if(tip.date!==date||Number(tip.race)!==Number(race)||tip.method!=='independent_hybrid_v1')throw Error('推介日期／場次不符');
  if(tip.status==='ready'&&!(Date.parse(tip.received_at)<=Date.parse(tip.freeze)))throw Error('主膽收到時間遲於截止');
  if(tip.cold_policy!==policy){
   if(tip.legs_method===fusion&&tip.legs_fusion_changed)throw Error('換腳冷馬方法不符');
   return {...tip,cold:[],cold_status:'unavailable',cold_reason:'等待最新冷馬方法；請以main版本啟動Runner',cold_policy:policy};
  }
  if(tip.cold_status==='ready'){
   const freeze=Date.parse(tip.cold_freeze);
   if(!Number.isFinite(freeze)||(tip.cold||[]).length>1)throw Error('冷馬截止或馬匹數目不符');
   if(!(Date.parse(tip.cold_received_at)<=freeze&&Date.parse(tip.cold_fct_received_at)<=freeze&&Date.parse(tip.cold_sources?.historical_prepared_at)<=freeze))throw Error('冷馬資料收到時間遲於截止');
   if((tip.cold||[]).length&&!(Number(tip.cold_win)>10))throw Error('冷馬WIN門檻不符');
  }
  if(tip.legs_method===fusion&&tip.legs_status==='ready'){
   const legs=(tip.legs||[]).map(Number),original=(tip.legs_original||[]).map(Number),banker=Number(tip.banker);
   if(legs.length!==4||original.length!==4||legs.some(h=>!Number.isInteger(h))||original.some(h=>!Number.isInteger(h))||new Set(legs).size!==4||new Set(original).size!==4||legs.includes(banker)||original.includes(banker))throw Error('融合四腳紀錄不符');
   if(legs.slice(0,3).some((h,i)=>h!==original[i]))throw Error('融合前三腳紀錄不符');
   if(tip.legs_fusion_changed){
    const cold=Number(tip.cold?.[0]),win=Number(tip.legs_fusion_win);
    if(tip.cold_status!=='ready'||tip.cold.length!==1||!(win>10&&win<=30)||win!==Number(tip.cold_win)||cold!==Number(tip.legs_added)||cold!==legs[3]||original.includes(cold)||Number(tip.legs_removed)!==original[3]||Date.parse(tip.cold_freeze)!==Date.parse(tip.freeze))throw Error('冷馬換腳紀錄不符');
   }else if(legs.some((h,i)=>h!==original[i]))throw Error('保留四腳紀錄不符');
  }
  return tip;
 }
 function phases(shadow,date,legUpdate=x=>x){
  return shadow.filter(Boolean).map(p=>{
   const phase=p.phase.replace('hkjc-',''),horse103={},results={};
   const numbers=new Set([...Object.keys(p.races||{}),...Object.keys(p.independent_tips||{})]);
   for(const n of numbers){
    const source=p.races?.[n]||{},saved=p.independent_tips?.[n];
    let tip=null,error='';
    try{if(saved)tip=legUpdate(validate(saved,date,n))}catch(e){error=e.message}
    horse103[n]={target:tip?.cutoff||source.target,status:tip?(tip.status==='ready'?'saved':'unavailable'):'waiting',
     picks:tip?.status==='ready'?[{horse_number:tip.banker}]:[],original:[],
     independent_tip:tip,reason:error||tip?.reason||source.reason||'',
     market:tip?{legs:tip.legs||[],golden:tip.golden||[],cold:tip.cold||[]}:null};
   }
   return {...p,phase,horse103,results,state:'running'};
  });
 }
 function critical(targets,at=Date.now()){
  return targets.some(t=>{const d=Date.parse(t)-at;return Number.isFinite(d)&&d<=100000&&d>=-45000});
 }
 const api={validate,phases,critical};if(typeof module!=='undefined')module.exports=api;else root.LiveTips=api;
})(typeof window==='undefined'?globalThis:window);
