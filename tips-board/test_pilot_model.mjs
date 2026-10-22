import assert from 'node:assert/strict';import fs from 'node:fs';import {evidence,allocations,choosePilot,planMeeting,validSnapshot,summarizePlans,key} from './pilot-model.mjs';
const read=f=>JSON.parse(fs.readFileSync(new URL(f,import.meta.url))),config=read('./pilot-config.json'),registry=read('./roi-methods.json'),stats=read('./pilot-evidence.json').stats,audit=read('./pilot-audit.json'),replay=read('./roi-replay.json');
assert.equal(evidence({n:9,days:['1','2','3'],cost:90,profit:100,maxreturn:50},config).ok,false);
assert.equal(evidence({n:10,days:['1','2','2'],cost:100,profit:100,maxreturn:50},config).ok,false);
assert.equal(evidence({n:10,days:['1','2','3'],cost:100,profit:50,maxreturn:50},config).ok,false);
assert.equal(evidence({n:10,days:['1','2','3'],cost:100,profit:51,maxreturn:50},config).ok,true);
assert.equal(config.assignments['HV|TURF|1'],'hv1');assert.equal(config.assignments['ST|TURF|1'],null);
const m=read('./roi-meetings/2026-10-21.json'),original=structuredClone(m),off='2026-10-22T19:00:00+08:00',r={...structuredClone(m.races[1]),date:'2026-10-22',venue:'HV',off,locked:false,result:null};
// Avoid relying on old dated raw tips for a synthetic new preoff card.
for(const tip of Object.values(r.tips||{}))tip.source_date=r.date;
if(r.banker_initial){r.banker_initial.date=r.date;r.banker_initial.race=r.race;}
r.draw_top5.before_date=r.date;let p=choosePilot(r,registry.methods,stats,config,{});assert.equal(p.status,'ready');assert.equal(p.method.id,'hv0');
const bad=structuredClone(r);bad.tips.meiji.horses[0].no=bad.banker_initial.numbers[0];assert.equal(choosePilot(bad,registry.methods,stats,config,{}).status,'skip','no fallback when fixed method condition fails');
assert.equal(choosePilot({...r,score:2},registry.methods,stats,config,{}).status,'skip');
const make=(race)=>({...structuredClone(r),race,banker_initial:{...r.banker_initial,race}}),meeting={date:r.date,venue:'HV',races:Array.from({length:8},(_,i)=>make(i+1))};
const time=Date.parse(off)-120000,rows=planMeeting(meeting,registry.methods,stats,config,{ledger:'paper',now:time});assert.equal(rows.filter(x=>x.plan.status==='ready').length,6);assert.equal(rows[6].plan.status,'skip');assert.equal(summarizePlans(rows).cost,60);assert(rows.every(x=>x.snapshot.finalized));
const snap=rows[0].snapshot;assert(validSnapshot(snap,rows[0].r,config));assert(!('result' in snap.input));assert.equal(snap.input.odds&&Object.keys(snap.input.odds).length,0);
const changed=structuredClone(meeting);changed.races[0].tips.meiji.horses[0].no=changed.races[0].banker_initial.numbers[0];changed.races[0].roi_strategy=snap;
assert.deepEqual(planMeeting(changed,registry.methods,stats,config,{ledger:'paper',now:time+10000})[0].snapshot,snap,'sealed plan and input never rewritten by later tips');
const early=planMeeting(meeting,registry.methods,stats,config,{ledger:'paper',now:Date.parse(off)-240000})[0].snapshot;assert.equal(early.finalized,false);assert(!validSnapshot(early,r,config));
assert(!validSnapshot({...snap,version:'old'},rows[0].r,config));assert(!validSnapshot({...snap,captured_at:off},rows[0].r,config));
assert.equal(planMeeting(meeting,registry.methods,stats,config,{ledger:'paper',now:Date.parse(off)+1000})[0].origin,'missing','closed race without sealed input is never reconstructed into paper ledger');
const mutated=structuredClone(r);mutated.result={dividends:{W:[{combination:'12',dividend_hkd:999999}]}};assert.deepEqual(choosePilot(mutated,registry.methods,stats,config,{}),p,'target outcome cannot change plan');
assert.deepEqual(m,original,'input archive immutable');
for(const day of audit.days){const meeting=read('./roi-meetings/'+day.date+'.json'),prior=read('./pilot-stats/'+day.date+'.json');assert.equal(prior.before_date,day.date);for(const s of Object.values(prior.stats))assert(s.days.every(d=>d<day.date),'same/future day cannot enter stats');const result=planMeeting(meeting,registry.methods,prior.stats,config,{ledger:'replay',replay,allocation:prior.assignments,now:Date.parse(meeting.races[0].off)-1,oddsByRace:Object.fromEntries(meeting.races.map(r=>[r.race,replay.inputs[key({...r,date:meeting.date,venue:meeting.venue})]?.final_odds||{}]))});const sum=summarizePlans(result);assert.equal(sum.cost,day.cost);assert.equal(sum.profit,day.profit);assert(sum.cost<=60);assert.deepEqual(allocations(registry.methods,prior.stats,config),prior.assignments);}
assert.equal(audit.days.reduce((s,d)=>s+d.cost,0),300);assert.equal(audit.days.reduce((s,d)=>s+d.profit,0),666);assert.equal(audit.days.at(-1).profit,-10);
console.log('Pilot model: prior-only evidence, all gates, fixed assignments/no fallback, $60 cap, T-3 sealing, immutable input snapshots, old-version rejection, no final-price/outcome access in live plans, missing sealed ledger and all 13 replay days verified.');
const qm=read('./roi-meetings/2026-09-27.json'),qr=structuredClone(qm.races[10]);qr.date='2026-10-22';qr.venue='ST';qr.locked=false;qr.result=null;qr.off=off;qr.banker_initial={...qr.banker_initial,date:qr.date};for(const t of Object.values(qr.tips))t.source_date=qr.date;
const qmeet={date:qr.date,venue:'ST',races:[1,2,3].map(race=>({...structuredClone(qr),race,banker_initial:{...qr.banker_initial,race}}))};const qrows=planMeeting(qmeet,registry.methods,stats,config,{ledger:'paper',now:time});assert.equal(qrows[0].plan.pool,'QP');assert.equal(qrows[0].plan.cost,30);assert.equal(qrows.filter(x=>x.plan.status==='ready').length,2);assert.equal(qrows[2].plan.status,'skip');assert.equal(summarizePlans(qrows).cost,60,'whole QP tickets consume budget; no partial third race');
