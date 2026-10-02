/* Preserve frozen cold-fusion legs; legacy F2 + banker QP2 remains archived. */
(function(root){
 const method='f2_banker_qp2_v1';
 const fusionMethod='f2_qp1_cold_10_30_exploratory_2026_10_02';
 function update(tip){
  if(tip.status!=='ready'||[method,fusionMethod].includes(tip.legs_method)||!tip.banker_qp_odds)return tip;
  const main=Number(tip.banker),scores=new Map(Object.entries(tip.leg_scores||{}).map(([h,f])=>[Number(h),Number(f)]).filter(([h,f])=>h!==main&&Number.isFinite(f)));
  const head=[...scores].sort((a,b)=>b[1]-a[1]||a[0]-b[0]).slice(0,2).map(([h])=>h);
  const tail=Object.entries(tip.banker_qp_odds).map(([h,p])=>[Number(h),Number(p)]).filter(([h,p])=>scores.has(h)&&!head.includes(h)&&Number.isFinite(p)&&p>0).sort((a,b)=>a[1]-b[1]||scores.get(b[0])-scores.get(a[0])||a[0]-b[0]).slice(0,2).map(([h])=>h);
  const ready=head.length===2&&tail.length===2,legs=ready?[...head,...tail]:[];
  return {...tip,published_legs:tip.published_legs??tip.legs,legs,legs_f:head,legs_qp:tail,golden:(tip.golden||[]).filter(h=>legs.includes(Number(h))),legs_method:method,legs_recomputed:true,legs_status:ready?'ready':'unavailable',legs_reason:ready?'':head.length<2?'缺有效T−10份額基準，無法計算F頭兩腳':'缺完整主膽位置Q配搭，無法補足兩腳'};
 }
 function note(tip,label=h=>`${h}號`){
  if(tip?.legs_method!==fusionMethod)return '';
  if(tip.legs_fusion_changed)return `第四腳換入冷馬${label(tip.legs_added)}（截止WIN ${Number(tip.legs_fusion_win)}倍）；原${label(tip.legs_removed)}`;
  return tip.legs_fusion_reason||'';
 }
 const api={update,note,method,fusionMethod};if(typeof module!=='undefined')module.exports=api;else root.HybridLegs=api;
})(typeof window==='undefined'?globalThis:window);
