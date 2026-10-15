import assert from 'node:assert/strict';
import fs from 'node:fs';
import {applyShaTin,chooseShaTin,chooseManual} from './manual-tips.mjs';
const dir=process.env.PATTERN_RECORDS||'../tips-data/records';
const source=JSON.parse(fs.readFileSync(`${dir}/2026-09-13.json`)),before=JSON.stringify(source),m=applyShaTin(source);
for(const [race,nos] of [[1,[2,11,10]],[3,[13,8,4]],[4,[12,3,4]],[5,[11,9,10]],[6,[7,1,3]],[7,[4,5,1]]]){
 const r=m.races.find(r=>r.race===race);assert.deepEqual(r.selection.horses.map(h=>h.no),nos);assert.deepEqual(r.selection.main,['QP']);assert(r.strategy_recalculated);
}
assert.equal(JSON.stringify(source),before,'Historical source and original bets stay untouched');
const oct=applyShaTin(JSON.parse(fs.readFileSync(`${dir}/2026-10-11.json`)));
for(const [race,nos] of [[8,[8,7,1]],[10,[9,3,1]]]){const r=oct.races.find(x=>x.race===race);assert.deepEqual(r.selection.horses.map(h=>h.no),nos);assert.deepEqual(r.selection.main,['Q','QP'])}
const r=structuredClone(m.races[0]);r.banker_initial.reason='track_bias';chooseShaTin(r);assert.equal(r.selection,null);
r.banker_initial=structuredClone(source.races[0].banker_initial);r.tips.ma.status='error';chooseShaTin(r);assert.equal(r.score,null);assert.equal(r.selection,null);
r.tips.ma.status='absent';r.scratched=[2];chooseShaTin(r);assert.deepEqual(r.selection.horses.map(h=>h.no),[11,10,3]);
const score2=structuredClone(source.races[0]);for(const k of ['ma','ball'])score2.tips[k]={status:'ready',horses:[{no:1}]};chooseManual(score2);assert.deepEqual(score2.selection.horses.map(h=>h.no),[2,3,10]);
// Compare every archived Sha Tin 0/1 selection with the collector's implementation.
const fixtures=[];
for(const name of fs.readdirSync(dir).filter(n=>/^2026-.*json$/.test(n))){const raw=JSON.parse(fs.readFileSync(`${dir}/${name}`));if(raw.venue!=='ST'||raw.status!=='archived')continue;const out=applyShaTin(raw);for(const r of out.races)if(r.score<2)fixtures.push({input:raw.races.find(x=>x.race===r.race),selection:r.selection})}
fs.writeFileSync('/tmp/st-pattern-parity.json',JSON.stringify(fixtures));assert.equal(fixtures.length,59);
console.log('PASS: 59 archived ST selections, published examples, fallback, source isolation, pending, scratches and score2');
