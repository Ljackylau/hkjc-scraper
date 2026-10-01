const assert=require('node:assert/strict'),C=require('./cold-signal.js');
const tip={race:2,freeze:'2026-10-01T13:26:50+08:00',market:[1,2],runner_rows:[['1','','','','','','甲'],['2','','','','','','乙']]};
function sample(source,received,odds){return {state:'observed',source_updated_at:`2026-10-01T${source}+08:00`,received_at:`2026-10-01T${received}+08:00`,selection_roster_complete:true,participants:[{selection_id:'1',name:'甲',current_odds:odds},{selection_id:'21',name:'其他練馬師',is_other:true,current_odds:odds}],race_context:[{race_number:1,post_time:'2026-10-01T13:00:00+08:00'}]}}
const base=sample('12:50:00','12:59:30',100),end=sample('13:10:00','13:26:40',60);let r=C.calculate(tip,[base,end]);
assert.deepEqual(r.cold,[1]);assert.equal(r.cold_group[0].horse,2);assert.equal(r.cold_partial,false);assert.match(C.text(r),/組合訊號，非個別練王落飛/);
base.selection_roster_complete=false;r=C.calculate(tip,[base,end]);assert.equal(r.cold_group.length,0);assert.equal(r.cold_partial,true);
end.participants[0].current_odds=null;end.participants[0].quote_text='未能勝出';r=C.calculate({...tip,market:[1]},[base,end]);assert.equal(r.cold_status,'ready');assert.equal(r.cold_excluded.length,1);
end.race_context.push({race_number:2,post_time:'2026-10-01T13:30:00+08:00'});r=C.calculate(tip,[base,end]);assert.equal(r.cold_applicable,false);assert.match(C.text(r),/尾二場/);
console.log('Other-group, eliminated-option and closing-time checks passed');
