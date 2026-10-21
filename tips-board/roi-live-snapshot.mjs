// Called by the collector before off. Never reads final prices from replay data.
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
import {preparedRace,choosePolicy} from './roi-policy.mjs?v=roi2';
const root=path.dirname(fileURLToPath(import.meta.url)),read=f=>{try{return JSON.parse(fs.readFileSync(f,'utf8'))}catch{return null}};
const meeting=JSON.parse(fs.readFileSync(0,'utf8')),registry=read(path.join(root,'roi-methods.json')),methods=registry.methods,folder=process.argv[2],now=Date.now();
const context={seed:read(path.join(root,'strategy-draw-seed.json')),history:read(path.join(folder,'draw-history.json')),index:read(path.join(folder,'history.json'))};
const snapshots={};for(const raw of meeting.races){if(raw.locked||Date.parse(raw.off)<=now)continue;const r=preparedRace(meeting,raw,context),p=choosePolicy(r,methods,context);snapshots[r.race]={version:registry.version,captured_at:new Date().toISOString(),status:p.status,method:p.method||null,picks:p.picks||[],pool:p.pool||null,tickets:p.tickets||[],banker:p.banker??null,cost:p.cost||0,reason:p.reason||null,skipped:p.attempts.filter(a=>a.status!=='ready').map(a=>({id:a.method.id,reason:a.reason})),odds_source:'none; price-dependent methods fall through'};}process.stdout.write(JSON.stringify(snapshots));
