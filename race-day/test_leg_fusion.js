const assert=require('node:assert/strict'),Hybrid=require('./leg-selection.js'),Live=require('./live-tips.js');
const freeze='2026-10-04T12:26:50+08:00';
const tip={date:'2026-10-04',race:1,method:'independent_hybrid_v1',status:'ready',banker:1,received_at:freeze,freeze,
 legs:[2,3,4,6],legs_original:[2,3,4,5],legs_method:Hybrid.fusionMethod,legs_status:'ready',
 legs_fusion_changed:true,legs_added:6,legs_removed:5,legs_fusion_win:20,
 banker_qp_odds:{2:3,3:4,4:5,5:6,6:100},leg_scores:{2:.9,3:.8,4:.7,5:.6,6:.1},
 cold_policy:'cold_top2_priority_v2_exploratory_2026-10-02',cold_status:'ready',cold:[6],cold_win:20,
 cold_freeze:freeze,cold_received_at:freeze,cold_fct_received_at:freeze,cold_sources:{historical_prepared_at:'2026-10-04T11:00:00+08:00'}};
assert.equal(Hybrid.update(tip),tip);
assert.equal(Live.validate(tip,tip.date,1),tip);
assert.match(Hybrid.note(tip),/第四腳換入冷馬6號.*原5號/);
assert.equal(Hybrid.note(undefined),'');
const phases=Live.phases([{phase:'hkjc-early',independent_tips:{1:tip}}],tip.date,Hybrid.update);
assert.deepEqual(phases[0].horse103[1].market.legs,[2,3,4,6]);
for(const fields of [{legs:[2,3,4,5]},{legs:[2,3,4,4]},{legs:[3,2,4,6]},
 {legs_removed:4},{legs_fusion_win:31},{cold:[5]},{cold_policy:'old'},{cold_freeze:'2026-10-04T12:26:40+08:00'}]){
 assert.throws(()=>Live.validate({...tip,...fields},tip.date,1));
}
const keep={...tip,legs:[2,3,4,5],legs_fusion_changed:false,legs_added:null,legs_removed:null,
 cold_status:'unavailable',cold:[],legs_fusion_reason:'冷馬資料未就緒，保留原四腳'};
assert.equal(Live.validate(keep,tip.date,1),keep);
assert.deepEqual(Hybrid.update(keep).legs,[2,3,4,5]);
assert.match(Hybrid.note(keep),/保留原四腳/);
console.log('Frozen fusion legs, fourth-slot audits, unavailable-cold fallback and display validation passed');
