import assert from 'node:assert/strict';
import {monthlyConfidence} from './confidence-stats.mjs';
const horses=[{no:1,name:'甲'},{no:2,name:'乙'}];
const race=(race,patch={})=>({race,score:2,off:'2026-10-14T19:00:00+08:00',horses,tips:{},selection:{horses,main:['QP'],optional:[]},...patch});
const meeting=races=>({date:'2026-10-14',venue:'HV',races});
const paid={horses:[{no:9,placing:'1'}],dividends:{QP:[{combination:'2,1',dividend_hkd:50}]},pool_status:{QP:'settled'}};
const source=meeting([
 race(1,{selection:{horses,main:['QP'],optional:['Q','QP']},result:paid}),
 race(2,{result:{...paid,dividends:{QP:[{combination:'8,9',dividend_hkd:100}]}}}),
 race(3),
 race(4,{result:{...paid,withdrawn:[1,2],dividends:{QP:[{combination:'8,9',dividend_hkd:100}]}}}),
 race(5,{result:{pool_status:{QP:'not_offered'}}}),
 race(6,{score:0,result:paid}),
 race(7,{score:3,result:paid}),
 race(8,{score:1,selection:null}),
]);
const before=JSON.stringify(source),rows=monthlyConfidence([source,structuredClone(source)]),g=rows.find(x=>x.score===2&&x.pool==='QP');
assert.deepEqual([g.races,g.settled,g.hits,g.pending,g.refunds,g.notOffered,g.rate],[5,2,1,1,1,1,.5]);
assert.equal(rows.find(x=>x.pool==='Q').role,'optional');assert.equal(rows.filter(x=>x.pool==='QP'&&x.score===2).length,1,'main pool not double-counted as optional');
assert.equal(rows.find(x=>x.score===3).hits,1);assert(!rows.some(x=>x.score===1),'no pair plan means no pair-rate row');assert(rows.every(x=>['Q','QP'].includes(x.pool)));
assert.equal(JSON.stringify(source),before,'Source archive is immutable');
const nov={...source,date:'2026-11-01'};assert.equal(monthlyConfidence([source,nov]).filter(x=>x.pool==='QP'&&x.score===2).length,2);
const p=meeting([race(1,{score:1,selection:{horses,main:['P'],optional:[]},result:{dividends:{P:[{combination:'1',dividend_hkd:20},{combination:'2',dividend_hkd:30}]}}})]);
assert.deepEqual(monthlyConfidence([p]),[],'single-horse pools are excluded');
const ordered=monthlyConfidence([source,{...source,date:'2026-09-09'}]);assert.deepEqual(ordered.map(x=>[x.score,x.month,x.pool]),[[2,'2026-10','QP'],[2,'2026-10','Q'],[2,'2026-09','QP'],[2,'2026-09','Q'],[3,'2026-10','QP'],[3,'2026-09','QP']]);
console.log('PASS: venue/H/month/pool/role grouping, deduplication, paid combinations, pending/refund/not-offered and per-race denominator');
