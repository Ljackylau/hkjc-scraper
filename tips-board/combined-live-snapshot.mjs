// Persists preoff paper decisions only; no archived final odds are read here.
import fs from'node:fs';import{evaluateMeeting}from'./combined-model.mjs?v=combined1';
const m=JSON.parse(fs.readFileSync(0,'utf8')),now=Date.now(),oddsByRace={};
for(const r of m.races){const p=r.win_odds,t=Date.parse(p?.captured_at);if(p?.date===m.date&&p.venue===m.venue&&p.race===r.race&&t<Date.parse(r.off)&&t<=now&&now-t<=600000)oddsByRace[r.race]=p.odds||{};}
const out={};for(const x of evaluateMeeting(m,{ledger:'paper',oddsByRace,now}))if(x.snapshot&&x.r.date>='2026-10-22')out[x.r.race]=x.snapshot;process.stdout.write(JSON.stringify(out));
