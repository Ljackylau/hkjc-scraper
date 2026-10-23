import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {applyInitialV1} from './import-initial-v1.mjs';
import {initialBankerView} from './banker-initial.mjs';

const source=JSON.parse(readFileSync(new URL('./fixtures/initial-v1-2026-10-25.json',import.meta.url)));
const expected=[[2,1,10,3,7],[12,13,4,6,9],[13,11,14,3,2],[1,10,5,9,4],[13,5,14,8,11],[7,6,14,1,11],[7,4,8,1,9],[8,1,3,5,13],[7,4,2,3,13],[3,11,2,8,9],[2,14,9,7,8]];
assert.deepEqual(source.races.map(r=>r.horses.map(h=>h.no)),expected);
assert.deepEqual(source.races.map(r=>r.banker_top3_probability),[.833,.797,.698,.814,.701,.744,.805,.715,.633,.732,null]);
assert.deepEqual(source.races.map(r=>r.distance),[1200,1400,1600,2000,1200,1000,1200,1400,1600,1200,1400]);
assert.deepEqual(source.races.map(r=>r.race_class),['四（條件限制）','五','四','三','四','三','二級賽','四','二','三','三']);
const captured='2026-10-24T00:00:00+08:00';
const base={date:source.date,venue:source.venue,status:'upcoming',tips_due_at:'2026-10-25T10:40:00+08:00',races:source.races.map(r=>({date:source.date,venue:source.venue,race:r.race,off:source.first_off,distance:r.distance,track:'TURF',rail:'A',horses:[...r.horses,...(r.withdrawn||[])],scratched:[],locked:false,result:null,tips:{meiji:{status:'pending',horses:[]}},selection:null,score:null,combined_snapshot:{finalized:false}}))};
const original=structuredClone(base),out=applyInitialV1(base,source,captured);
assert.deepEqual(base,original,'Import must not mutate input');
assert.equal(out.initial_v1_source.going,null);assert.equal(out.initial_v1_source.prediction_created_at,null);
for(const [i,r] of out.races.entries()){
 assert.deepEqual(r.banker_initial.numbers,expected[i]);
 assert.equal(r.banker_initial.reason,'initial');assert.equal(r.banker_initial.as_of_race_no,0);
 assert.equal(r.banker_initial.source_type,'user_provided');assert.equal(r.banker_initial.results_used_for_selection,false);
 assert.equal(r.banker_initial.model,'logistic_regression');assert.equal(r.banker_initial.captured_at,captured);
 for(const k of ['horses','tips','selection','score','result','locked','combined_snapshot'])assert.deepEqual(r[k],base.races[i][k],k+' must be preserved');
}
assert.deepEqual(out.races[3].scratched,[11]);assert.equal(out.races[3].initial_withdrawal.selections_changed,false);
assert.equal(out.races[10].banker_initial.banker_top3_probability,null);
const view=initialBankerView(out);assert(view.visible);assert.equal((view.rows.match(/data-initial-race=/g)||[]).length,11);
assert.equal((view.rows.match(/data-banker-probability>\d/g)||[]).length,10);
assert(view.rows.includes('未提供'));assert(!view.rows.includes('>0.0%'));assert(view.rows.includes('奇異果'));assert(view.rows.includes('已退出'));
assert(view.rows.includes('條件限制'));assert(view.rows.includes('二級賽'));assert(view.note.includes('未公布'));assert(view.note.includes('reason=initial'));
const poison=structuredClone(out);poison.races[0].result={horses:[{no:999,placing:1}]};
assert.equal(initialBankerView(poison).rows,view.rows,'Results must not affect displayed initial picks');
for(const mutate of [m=>m.date='2026-10-26',m=>m.venue='HV',m=>m.races[0].distance=1400,m=>m.races[0].horses[0].name='錯馬',m=>m.races[0].locked=true,m=>m.races[0].result={horses:[]},m=>m.races[0].scratched=[2]]){
 const bad=structuredClone(base);mutate(bad);assert.throws(()=>applyInitialV1(bad,source,captured));
}
assert.throws(()=>applyInitialV1(base,source,source.first_off));
for(const probability of [83.3,NaN,-.1,'0.833']){const bad=structuredClone(source);bad.races[0].banker_top3_probability=probability;assert.throws(()=>applyInitialV1(base,bad,captured));}
if(process.argv[2]){
 const records=process.argv[2],read=name=>JSON.parse(readFileSync(records+'/'+name,'utf8')),latest=read('latest.json');
 assert.deepEqual(latest,read(source.date+'.json'));
 assert.deepEqual(latest.races.map(r=>r.banker_initial.numbers),expected);
 assert.deepEqual(latest.races.map(r=>r.banker_initial.banker_top3_probability),source.races.map(r=>r.banker_top3_probability));
 assert.deepEqual(latest.races[3].scratched,[11]);assert(latest.races.every(r=>r.result===null&&!r.locked));
 assert(!read('history.json').meetings.some(m=>m.date===source.date&&m.complete),'Upcoming meeting cannot become completed history');
}
console.log('Initial V1: 11 supplied selections, probabilities/unknown, identity validation, withdrawal, provenance, no result influence and latest/archive parity passed.');
