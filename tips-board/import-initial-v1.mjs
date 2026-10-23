import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

// This imports a supplied prediction, without scoring or reading results/odds.
export function applyInitialV1(meeting,source,capturedAt){
 assert.equal(meeting.date,source.date);assert.equal(meeting.venue,source.venue);
 assert.equal(source.reason,'initial');assert.equal(source.source_type,'user_provided');
 assert.equal(source.results_used_for_selection,false);
 assert.equal(meeting.races.length,source.races.length);
 assert.equal(new Set(source.races.map(r=>r.race)).size,source.races.length);
 assert.equal(meeting.races[0].off,source.first_off);
 assert(Number.isFinite(Date.parse(capturedAt)));
 const m=structuredClone(meeting);
 const provenance={source:'user-provided',source_type:source.source_type,source_reference:source.source_reference,source_note:source.source_note,captured_at:capturedAt,prediction_created_at:null,model_version:source.model_version,model:source.model,results_used_for_selection:false,verification:'User supplied before meeting; model and original prediction timestamp not independently verified'};
 for(const pick of source.races){
  const r=m.races.find(r=>r.race===pick.race);assert(r,'Unknown race');
  assert(!r.locked&&!r.result,'Cannot replace started/result-bearing race');
  assert(Date.parse(capturedAt)<Date.parse(r.off),'Import must be before off');
  assert.equal(r.distance,pick.distance);assert.equal(r.track,source.track);assert.equal(r.rail,source.rail);
  const numbers=pick.horses.map(h=>h.no),field=new Map(r.horses.map(h=>[h.no,h.name]));
  assert.equal(numbers.length,5);assert.equal(new Set(numbers).size,5);
  for(const h of [...pick.horses,...(pick.withdrawn||[])])assert.equal(field.get(h.no),h.name,'Horse number/name mismatch');
  assert(pick.banker_top3_probability===null||typeof pick.banker_top3_probability==='number'&&Number.isFinite(pick.banker_top3_probability)&&pick.banker_top3_probability>=0&&pick.banker_top3_probability<=1);
  r.scratched=[...new Set([...(r.scratched||[]),...(pick.withdrawn||[]).map(h=>h.no)])];
  assert(!numbers.some(n=>r.scratched.includes(n)),'Selected runner withdrawn; do not silently substitute');
  r.race_class=pick.race_class;
  r.banker_initial={status:'ready',date:m.date,venue:m.venue,race:r.race,as_of_race_no:0,reason:'initial',numbers,horses:structuredClone(pick.horses),distance:pick.distance,race_class:pick.race_class,banker_top3_probability:pick.banker_top3_probability,...provenance};
  if(pick.withdrawn?.length)r.initial_withdrawal={horses:structuredClone(pick.withdrawn),note:pick.withdrawal_note,selections_changed:false,...provenance};
 }
 m.initial_v1_source={...provenance,track:source.track,rail:source.rail,going:source.going,going_status:source.going_status};
 m.updated_at=capturedAt;
 return m;
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const [recordsPath,sourcePath]=process.argv.slice(2);
 assert(recordsPath&&sourcePath,'Usage: node import-initial-v1.mjs RECORDS_DIR SOURCE_JSON');
 const read=p=>JSON.parse(readFileSync(p,'utf8')),source=read(sourcePath),latest=read(resolve(recordsPath,'latest.json')),dated=read(resolve(recordsPath,source.date+'.json'));
 assert.deepEqual(latest,dated,'Latest and dated records differ; reconcile before importing');
 const updated=applyInitialV1(latest,source,new Date().toISOString()),body=JSON.stringify(updated,null,2)+'\n';
 for(const name of [source.date+'.json','latest.json'])writeFileSync(resolve(recordsPath,name),body);
 console.log(`Imported ${updated.races.length} initial V1 races into latest and dated records; history index preserved.`);
}
