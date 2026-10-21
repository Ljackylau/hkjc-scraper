import assert from 'node:assert/strict';import fs from 'node:fs';import {historyRows,summarize} from './strategy-history-model.mjs';import {mergeManualResults} from './manual-results.mjs';
const raw=JSON.parse(fs.readFileSync(new URL('./fixtures/strategy-next-hv.json',import.meta.url))),overlay=JSON.parse(fs.readFileSync(new URL('./fixtures/strategy-history-results-20261021.json',import.meta.url))),m=mergeManualResults(raw,overlay),before=structuredClone(m);
const rows=historyRows(m),s=summarize(rows);assert.equal(rows.length,9);assert.deepEqual([s.cost,s.returned,s.profit,s.races,s.hits],[70,47,-23,5,1]);assert.equal(rows[0].bets.length,0);assert.equal(rows[8].bets.length,0);assert.equal(rows[6].bets[0].status,'miss');assert.equal(rows[7].bets[0].status,'hit');
const replay=historyRows(m,{mode:'current'});assert.deepEqual(m,before);assert.equal(summarize(replay).cost,70);
const pending=structuredClone(m);pending.races[7].result=null;const q=summarize(historyRows(pending));assert.equal(q.pending,1);assert.equal(q.cost,60);assert.equal(q.returned,0);
const empty=summarize([]);assert.equal(empty.roi,null);assert.equal(empty.rate,null);
const both=structuredClone(m);both.races[7].selection.main=['W','P'];both.races[7].selection.optional=['Q'];const b=historyRows(both)[7].bets;assert.deepEqual(b.map(x=>x.pool),['W','P']);assert.deepEqual(b.map(x=>x.returned),[47,17.5]);
assert.equal(mergeManualResults({...raw,venue:'ST'},overlay).races[7].result,raw.races[7].result);
console.log('Strategy history: nine official results; saved $70/$47/-$23; immutable current replay, missing payouts, no-bet races, multiple main pools and optional pool exclusion passed.');
