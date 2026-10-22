// Paper-only T-3 lock. Uses frozen evidence; does not read results or final odds archives.
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
import {planMeeting} from './pilot-model.mjs?v=pilot1';
const root=path.dirname(fileURLToPath(import.meta.url)),read=f=>JSON.parse(fs.readFileSync(path.join(root,f),'utf8'));
const meeting=JSON.parse(fs.readFileSync(0,'utf8')),registry=read('roi-methods.json'),config=read('pilot-config.json'),evidence=read('pilot-evidence.json');
if(evidence.trained_through!==config.trained_through)throw Error('Pilot evidence version mismatch');
const rows=planMeeting(meeting,registry.methods,evidence.stats,config,{ledger:'paper'}),snapshots={};
for(const x of rows)if(x.snapshot&&x.r.date>=config.launched_on)snapshots[x.r.race]=x.snapshot;
process.stdout.write(JSON.stringify(snapshots));
