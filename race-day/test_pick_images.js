const assert=require('node:assert/strict'),P=require('./pick-images.js'),Live=require('./live-tips.js');
const date='2026-10-04',at=Date.parse(date+'T13:27:30+08:00');
const off=date+'T13:30:00+08:00',freeze=date+'T13:26:50+08:00',cutoff=date+'T13:27:00+08:00';
const tip={date,race:3,method:'independent_hybrid_v1',status:'ready',off,freeze,cutoff,received_at:freeze,
 banker:2,cold_policy:'cold_top2_priority_v2_exploratory_2026-10-02',cold_status:'ready',cold:[9],cold_win:18,
 cold_freeze:freeze,cold_received_at:freeze,cold_fct_received_at:freeze,cold_sources:{historical_prepared_at:date+'T11:00:00+08:00'},
 runner_rows:[['2','','示例膽馬','4','128','潘頓','廖康銘','4.2','1.8'],['9','','示例冷馬','8','119','巴度','黎昭昇','18','5']]};
function phase(t=tip){return {date,venue:'ST',phase:'early',updated_at:date+'T13:27:10+08:00',races:{3:{target:cutoff}},independent_tips:{3:t}}}
const choose=(phases=[phase()],now=at,d=date)=>P.resolve(phases,d,now,Live.validate);
let checks=0;function check(name,fn){fn();checks++;}
check('live banker and cold names',()=>{const s=choose();assert.equal(s.status,'ready');assert.equal(s.race,3);assert.equal(s.banker.name,'示例膽馬');assert.equal(s.cold.number,9);assert.equal(s.venueName,'沙田')});
check('use Happy Valley from collector',()=>assert.equal(choose([{...phase(),venue:'HV'}]).venueName,'跑馬地'));
check('missing phases wait',()=>assert.equal(choose([]).status,'waiting'));
check('reject stale date rather than fallback',()=>assert.equal(choose([{...phase(),date:'2026-10-01'}]).status,'unavailable'));
check('Hong Kong date around UTC boundary',()=>assert.equal(P.hkDay(Date.parse('2026-10-03T16:30:00Z')),date));
check('reject selected date outside today',()=>assert.equal(choose([phase()],at,'2026-10-03').status,'unavailable'));
check('block missing venue',()=>assert.equal(choose([{...phase(),venue:undefined}]).status,'unavailable'));
check('block disagreeing phases',()=>assert.equal(choose([phase(),{...phase(),phase:'late',venue:'HV',races:{},independent_tips:{}}]).status,'unavailable'));
check('never use prior off race when next waiting',()=>{
 const p=phase();p.races[4]={target:date+'T14:02:00+08:00'};
 const s=choose([p],Date.parse(date+'T13:31:00+08:00'));assert.equal(s.race,4);assert.equal(s.status,'waiting');assert.equal(s.banker,undefined);
});
check('do not use older complete tip if nearer race cold missing',()=>{
 const p=phase({...tip,cold:[]});const t={...tip,race:4,off:date+'T14:05:00+08:00',freeze:date+'T14:01:50+08:00',cutoff:date+'T14:02:00+08:00'};
 p.races[4]={target:t.cutoff};p.independent_tips[4]=t;assert.equal(choose([p]).race,3);assert.equal(choose([p]).status,'unavailable');
});
check('never expose a tip before its freeze',()=>assert.equal(choose([phase()],Date.parse(freeze)-1).status,'waiting'));
check('published locked tip enables export without an extra wait to T-3',()=>assert.equal(choose([phase()],Date.parse(freeze)).status,'ready'));
check('reject rescheduled off mismatch',()=>assert.equal(choose([{...phase(),races:{3:{target:date+'T13:28:00+08:00'}}}]).status,'unavailable'));
check('reject late banker inputs',()=>assert.equal(choose([phase({...tip,received_at:cutoff})]).status,'unavailable'));
check('reject late cold inputs',()=>assert.equal(choose([phase({...tip,cold_fct_received_at:cutoff})]).status,'unavailable'));
check('reject old cold policy',()=>assert.equal(choose([phase({...tip,cold_policy:'legacy'})]).status,'unavailable'));
check('no cold candidate cannot fabricate four images',()=>assert.equal(choose([phase({...tip,cold:[]})]).status,'unavailable'));
check('same horse may be banker and cold according to existing model',()=>assert.equal(choose([phase({...tip,cold:[2]})]).cold.number,2));
check('missing horse name blocks generation',()=>assert.equal(choose([phase({...tip,runner_rows:tip.runner_rows.slice(0,1)})]).status,'unavailable'));
check('withdrawn horse blocks generation',()=>assert.equal(choose([phase({...tip,runner_rows:[tip.runner_rows[0],[...tip.runner_rows[1],'SCR']]})]).status,'unavailable'));
check('no reconstructed result for a live image',()=>assert.equal(choose([phase({...tip,reconstruction:{kind:'archived_preoff_reconstruction'}})]).status,'unavailable'));
check('reject impossible freeze',()=>assert.equal(choose([phase({...tip,freeze:date+'T13:27:00+08:00'})]).status,'unavailable'));
check('malformed schedule never selects another race',()=>assert.equal(choose([{...phase(),races:{3:{target:'invalid'}}}]).status,'unavailable'));
const images=P.batch(choose(),7720,at);
check('exact four allocations and names',()=>{
 assert.equal(images.length,4);assert.deepEqual(images.map(p=>p.amount),[100,300,50,150]);assert.deepEqual(images.map(p=>p.pool),['獨贏','位置','獨贏','位置']);
 assert.deepEqual(images.map(p=>p.horse.number),[2,2,9,9]);assert.equal(images.reduce((a,p)=>a+p.amount,0),600);
 assert.equal(new Set(images.map(p=>p.number)).size,1);assert.equal(new Set(images.map(p=>p.time)).size,1);assert.equal(images[0].weekday,'星期日');assert.equal(images[0].time,'04-10-2026 13:27');
});
check('off-time export cannot proceed',()=>assert.throws(()=>P.batch(choose(),7720,Date.parse(off))));
const values=new Map(),storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)};
check('starts at 7720 and next successful group is 7723',()=>{assert.equal(P.nextNumber(storage),7720);P.commitNumber(storage,7720);assert.equal(P.nextNumber(storage),7723)});
check('next page reads persisted group number',()=>{const second={getItem:k=>values.get(k)??null};assert.equal(P.nextNumber(second),7723)});
check('stale concurrent writer cannot overwrite next counter',()=>{assert.throws(()=>P.commitNumber(storage,7720));assert.equal(P.nextNumber(storage),7723)});
check('render failure alone does not consume a number',()=>{assert.throws(()=>P.batch({status:'waiting'},7723,at));assert.equal(P.nextNumber(storage),7723)});
check('storage failure is not a silent successful counter',()=>{const blocked={getItem:()=>null,setItem:()=>{throw Error('QuotaExceeded')}};assert.throws(()=>P.commitNumber(blocked,7720))});
check('reject corrupt counter rather than reset and duplicate',()=>{values.set(P.numberKey,'broken');assert.throws(()=>P.nextNumber(storage))});
check('CRC known vector',()=>assert.equal(P.crc32(new TextEncoder().encode('123456789')),0xcbf43926));
(async()=>{
 const files=images.map((p,i)=>({name:p.filename,blob:new Blob([`fixture-${i}`],{type:'image/png'})}));
 const blob=await P.zip(files),bytes=Buffer.from(await blob.arrayBuffer());
 assert.equal(bytes.readUInt32LE(0),0x04034b50);assert.equal(bytes.readUInt32LE(bytes.length-22),0x06054b50);assert.equal(bytes.readUInt16LE(bytes.length-14),4);
 if(process.argv[2])require('node:fs').writeFileSync(process.argv[2],bytes);
 console.log(`${checks+1} image-plan checks passed: current race, receipt cutoff, four allocations, persistent numbering and ZIP.`);
})().catch(e=>{console.error(e);process.exitCode=1});
