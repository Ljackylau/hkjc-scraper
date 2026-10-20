import assert from 'node:assert/strict';
import {chooseHappyValley,applyManual,HV_METHOD} from './manual-tips.mjs';
const base=()=>({date:'2026-10-21',venue:'HV',race:2,score:0,off:'2026-10-21T19:00:00+08:00',locked:false,horses:Array.from({length:12},(_,i)=>({no:i+1,name:'馬'+(i+1),draw:i+1,jockey_id:'J'+(i+1)})),scratched:[],tips:{meiji:{status:'ready',source_date:'2026-10-21',horses:[11,3,8,4].map(no=>({no,name:'馬'+no}))},...Object.fromEntries(['ball','ma','computer'].map(k=>[k,{status:'absent',horses:[]}]))},banker_initial:{status:'ready',date:'2026-10-21',venue:'HV',race:2,as_of_race_no:0,reason:'initial',numbers:[1,3,8,9,10]},draw_top5:{status:'ready',method_version:'jockey_draw_only_v3',before_date:'2026-10-21',riders:[{no:3,draw:3,jockey_id:'J3'},{no:1,draw:1,jockey_id:'J1'}]},selection:null});
let r=base();chooseHappyValley(r);assert.deepEqual(r.selection.horses.map(h=>h.no),[1]);assert.deepEqual(r.selection.main,['P']);assert.deepEqual(r.selection.optional,[]);
r=base();r.tips.meiji.horses[0].no=3;chooseHappyValley(r);assert.equal(r.hv_plan_state,'skip');assert.equal(r.selection,null);
for(const mutate of [r=>r.banker_initial.reason='bias',r=>r.banker_initial.date='2026-10-14',r=>r.draw_top5.riders[1].draw=99,r=>r.tips.ma.status='error']){r=base();mutate(r);chooseHappyValley(r);assert.equal(r.selection,null);assert.equal(r.hv_plan_state,'pending')}
r=base();r.scratched=[1];chooseHappyValley(r);assert.equal(r.hv_plan_state,'skip');
r=base();r.tips.ball={status:'ready',horses:[{no:7,name:'馬7'}]};chooseHappyValley(r);assert.deepEqual(r.selection.horses.map(h=>h.no),[7]);assert.deepEqual(r.selection.main,['W']);assert.deepEqual(r.selection.optional,[]);
const source={date:r.date,venue:r.venue,races:[{...base(),locked:true,score:1,tips:r.tips,selection:{horses:[{no:7,name:'馬7'},{no:11,name:'馬11'}],main:['W','P'],optional:['QP']}}]},saved=JSON.stringify(source);
const out=applyManual(source,null,Date.parse('2026-10-22'));assert.equal(out.races[0].selection.method,HV_METHOD);assert.equal(out.races[0].original_selection.horses.length,2);assert.equal(out.races[0].strategy_recalculated,true);assert.equal(JSON.stringify(source),saved);
console.log('PASS: HV current rules, no bet/pending, initial identity, draw changes, scratches and labelled immutable historical replay');

r=base();r.hv_plan_state='skip';r.hv_plan_reason='old';r.tips.ball={status:'ready',horses:[{no:7}]};r.tips.ma={status:'ready',horses:[{no:8}]};chooseHappyValley(r);assert.equal(r.score,2);assert.equal(r.hv_plan_state,undefined);
