const assert=require('node:assert/strict'),Live=require('./live-tips.js'),Cold=require('./cold-signal.js');
const freeze='2026-10-04T12:26:50+08:00';
const tip={date:'2026-10-04',race:1,method:'independent_hybrid_v1',status:'unavailable',reason:'缺T−10',freeze,cutoff:'2026-10-04T12:27:00+08:00',
 cold_policy:'cold_top2_priority_v2_exploratory_2026-10-02',cold_status:'ready',cold:[9],cold_win:18,cold_freeze:freeze,
 cold_received_at:freeze,cold_fct_received_at:freeze,cold_sources:{historical_prepared_at:'2026-10-04T11:00:00+08:00'},banker:9};
assert.equal(Live.validate(tip,tip.date,1),tip);
assert.throws(()=>Live.validate({...tip,cold_received_at:tip.cutoff},tip.date,1));
assert.throws(()=>Live.validate({...tip,cold:[9,10]},tip.date,1));
assert.throws(()=>Live.validate({...tip,cold_win:10},tip.date,1));
const phases=Live.phases([{phase:'hkjc-early',races:{1:{target:tip.cutoff}},independent_tips:{1:tip}}],tip.date);
assert.equal(phases[0].horse103[1].independent_tip.cold[0],9);
assert.equal(phases[0].horse103[1].status,'unavailable');
assert.match(Cold.text(tip),/9號/); // retain a cold horse even when it is the banker
assert.equal(Live.critical([tip.cutoff],Date.parse(tip.cutoff)-1000),true);
assert.equal(Live.critical([tip.cutoff],Date.parse(tip.cutoff)-120000),false);
global.fetch=()=>{throw Error('The v2 result must never fetch legacy trainer data')};
Cold.update(tip,'unused','early').then(value=>assert.equal(value,tip));
console.log('Live cold policy, receipt validation, independent display and deadline window passed');
