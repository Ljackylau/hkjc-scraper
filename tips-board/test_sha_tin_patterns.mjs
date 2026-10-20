import assert from 'node:assert/strict';
import fs from 'node:fs';
import {applyShaTin,chooseShaTin,chooseManual,ST_METHOD} from './manual-tips.mjs';
const dir=process.env.PATTERN_RECORDS||'../tips-data/records';
const source=JSON.parse(fs.readFileSync(dir+'/2026-09-13.json')),before=JSON.stringify(source),m=applyShaTin(source);
for(const [race,nos] of [[1,[2,11,10]],[3,[13,8,4]],[5,[11,9,10]],[6,[7,1,3]],[7,[4,5,1]]]){
 const r=m.races.find(r=>r.race===race);assert.deepEqual(r.selection.horses.map(h=>h.no),nos);assert.deepEqual(r.selection.main,['QP']);assert(r.strategy_recalculated);assert.equal(r.selection.method,ST_METHOD);
}
assert.equal(m.races.find(r=>r.race===4).selection,null,'inside initial first three must skip');
assert.equal(m.races.find(r=>r.race===4).st_plan_state,'skip');
assert.equal(JSON.stringify(source),before,'Original archive untouched');
const h1=m.races.find(r=>r.race===2);assert.deepEqual(h1.selection.horses.map(h=>h.no),[2,8,11]);assert.deepEqual(h1.selection.main,['QP']);assert.deepEqual(h1.selection.optional,[]);
const oct=applyShaTin(JSON.parse(fs.readFileSync(dir+'/2026-10-11.json')));
for(const race of [5,8,10])assert.equal(oct.races.find(r=>r.race===race).selection,null,'AWT or inside-gate race skipped');
const r=structuredClone(m.races[0]);r.banker_initial.reason='track_bias';chooseShaTin(r);assert.equal(r.selection,null);assert.equal(r.st_plan_state,'pending');
r.banker_initial=structuredClone(source.races[0].banker_initial);r.tips.ma.status='error';chooseShaTin(r);assert.equal(r.score,null);assert.equal(r.selection,null);
r.tips.ma.status='absent';r.scratched=[2];chooseShaTin(r);assert.deepEqual(r.selection.horses.map(h=>h.no),[11,10,3]);
const score2=structuredClone(source.races[0]);score2.st_plan_state='skip';for(const k of ['ma','ball'])score2.tips[k]={status:'ready',horses:[{no:1}]};chooseManual(score2);assert.deepEqual(score2.selection.horses.map(h=>h.no),[2,3,10]);assert.equal(score2.st_plan_state,undefined);
const fixtures=[];
for(const name of fs.readdirSync(dir).filter(n=>/^2026-.*json$/.test(n))){
 const raw=JSON.parse(fs.readFileSync(dir+'/'+name));if(raw.venue!=='ST'||raw.status!=='archived')continue;
 const out=applyShaTin(raw);
 for(const r of out.races)if(r.score<2){assert(!r.selection||r.selection.main.length===1&&r.selection.main[0]==='QP');fixtures.push({input:{...raw.races.find(x=>x.race===r.race),date:raw.date,venue:raw.venue},selection:r.selection})}
}
fs.writeFileSync('/tmp/st-pattern-parity.json',JSON.stringify(fixtures));assert(fixtures.length>=70);
console.log('PASS: ST turf/gate/QP-only rules, archived source preservation, pending, scratches, H2 transition and parity fixtures');
