import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {coldWinCandidates,coldWinSelect,AUTHORS,ST_WIN_METHOD} from './st-coldwin.mjs';
import {coldWinArchives} from './st-coldwin-history.mjs';
import {confidenceReason} from './manual-tips.mjs';
const r={date:'2026-10-21',race:1,venue:'ST',track:'TURF',horses:Array.from({length:14},(_,i)=>({no:i+1,name:'馬'+(i+1)})),tips:{meiji:{status:'ready',horses:[1,2,3,4].map(no=>({no}))}},banker_initial:{status:'ready',date:'2026-10-21',race:1,venue:'ST',as_of_race_no:0,reason:'initial',numbers:[5,6,7,8,9]}};
const s={method:ST_WIN_METHOD,status:'ready',date:r.date,race:1,venue:'ST',authors:Object.fromEntries(AUTHORS.map((a,i)=>[a,{status:'ready',numbers:[[10,11,12,13],[10,12,14,1],[12,10,11,1],[11,14,10,1]][i]}])),forms:Object.fromEntries([10,11,12,13,14].map(no=>[no,{status:'ready',last_date:no<12||no===13?'2026-07-01':'2026-10-01',last_finish:no===14?4:2,style_n:3,median:7}]))};
const c=coldWinCandidates(r,s,true);assert.equal(c.status,'ready');assert.deepEqual(c.candidates.map(h=>h.no),[10,11,12,13]);
assert.deepEqual(coldWinSelect(c,{10:8,11:15,12:9,13:20}).picks.map(h=>h.no),[11,12],'strict >8 filter precedes two-horse cap');
assert.equal(coldWinSelect(c,{11:15,12:9,13:20}).status,'awaiting_odds');
assert.equal(coldWinSelect(c,{10:8,11:8,12:8,13:8}).picks.length,0);
assert.equal(coldWinCandidates({...r,track:'AWT'},s,true).status,'not_applicable');
assert.equal(coldWinCandidates({...r,venue:'HV'},s,true).status,'not_applicable');
assert.equal(coldWinCandidates(r,s,false).status,'not_applicable');
assert.equal(coldWinCandidates(r,{...s,date:'2026-10-20'},true).status,'pending');
const missing=structuredClone(s);delete missing.forms[10];assert.equal(coldWinCandidates(r,missing,true).status,'pending');
const scratched=coldWinCandidates({...r,scratched:[11]},s,true);assert.deepEqual(coldWinSelect(scratched,{10:8,12:9,13:20}).picks.map(h=>h.no),[12,13]);
const fixture=JSON.parse(readFileSync(new URL('./fixtures/st-coldwin-replay.json',import.meta.url)));let bets=0,returns=0,wins=0;
for(const row of fixture.races){
 const archive=coldWinArchives[row.race.date+'~'+row.race.race];
 const p=coldWinSelect(coldWinCandidates(row.race,archive.support,Boolean(confidenceReason(row.race))),archive.final_odds);
 assert.equal(p.status,'ready');assert.deepEqual(p.picks.map(h=>h.no),row.expected,'dated race replay '+row.race.date+' R'+row.race.race);
 bets+=p.picks.length;for(const h of p.picks){const paid=row.win_dividends.filter(x=>String(x.combination)===String(h.no));wins+=paid.length;returns+=paid.reduce((n,x)=>n+x.dividend_hkd,0)}
}
assert.equal(fixture.races.length,31);assert.equal(bets,28);assert.equal(wins,4);assert.equal(returns,542);assert.equal(returns-10*bets,262);
console.log('PASS: eligibility, missing data, strict price threshold, filter-before-cap, scratch replacement; 31 ST turf races reproduce 28 bets / 4 wins / +$262.');
