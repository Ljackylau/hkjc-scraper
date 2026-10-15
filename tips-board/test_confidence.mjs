import assert from 'node:assert/strict';
import {confidenceReason,ST_METHOD} from './manual-tips.mjs';
const base={venue:'ST',date:'2026-10-19',race:1,score:0,track:'TURF',selection:{method:ST_METHOD,horses:[{no:2},{no:11},{no:10}]},tips:{meiji:{status:'ready',horses:[{no:2}]}},banker_initial:{status:'ready',as_of_race_no:0,reason:'initial',date:'2026-10-19',venue:'ST',race:1,numbers:[11,10,1,12,3]}};
assert(confidenceReason(base));assert.equal(confidenceReason({...base,track:'AWT'}),null);
assert(confidenceReason({...base,score:1,track:'AWT'}),'T=1 does not require turf');
for(const patch of [{venue:'HV'},{score:2},{score:null},{selection:null},{tips:{meiji:{status:'pending',horses:[]}}},{tips:{meiji:{status:'ready',horses:[{no:10}]}}},{banker_initial:{...base.banker_initial,reason:'track_bias'}},{banker_initial:{...base.banker_initial,date:'2026-10-11'}},{banker_initial:{...base.banker_initial,numbers:[]}}])assert.equal(confidenceReason({...base,...patch}),null);
const changedResult={...base,result:{horses:[{no:14}]}};assert.equal(confidenceReason(changedResult),confidenceReason(base),'Badge never depends on race result');
console.log('PASS: T=0 turf, T=1 any track, initial first3 exclusion, missing inputs, venue/date and result independence');
