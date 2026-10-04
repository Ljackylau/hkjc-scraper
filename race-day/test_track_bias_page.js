const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Bias=require('./track-bias.js');
const ids=['trackBiasEditor','biasDate','biasHistory','biasPreviews','biasVenue','biasRail','biasFamily','biasDirection','biasPace','biasConfidence','biasFrom','biasUntil','biasEvidence','biasNote','biasMessage','biasSave','biasReset','biasResetReason','biasExport','biasImport'];
const nodes=Object.fromEntries(ids.map(id=>[id,{value:'',textContent:'',innerHTML:'',open:true,addEventListener(){}}]));
const storage={data:null,getItem(){return this.data},setItem(k,v){this.data=v}};
const now=Date.now(),date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(now));
const tip={date,race:2,status:'ready',legs_status:'ready',freeze:new Date(now+3600000).toISOString(),received_at:new Date(now).toISOString(),banker:1,legs:[4,5,6,7],leg_scores:Object.fromEntries(Array.from({length:9},(_,i)=>[i+1,1-(i+1)/10])),runner_rows:Array.from({length:9},(_,i)=>[String(i+1),'','',String(i+1)])};
const contexts=Object.fromEntries([1,2,3].map(race=>[race,{status:'ready',date,race,venue:'ST',track:'TURF',rail:'A',distance:1400,prepared_at:new Date(now-600000).toISOString()}]));
const sandbox={TrackBias:Bias,document:{getElementById:id=>nodes[id]},localStorage:storage,window:{},Date,Map,Set,Intl,Blob,URL,AbortSignal,setTimeout,console,
 fetch:async url=>({ok:true,json:async()=>contexts[Number(url.match(/race_(\d+)/)[1])]}),navigator:{clipboard:{writeText:async text=>sandbox.copied=text}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/track-bias-page.js','utf8'),sandbox);
(async()=>{
 const api=sandbox.window.TrackBiasEditor;
 await api.refresh({date,root:'https://example.test',races:[{number:1,completed:true},{number:2,tip,completed:false}]});
 Object.assign(nodes.biasVenue,{value:'ST'});nodes.biasRail.value='A';nodes.biasFamily.value='turn1200_1800';nodes.biasDirection.value='inside';nodes.biasPace.value='unknown';nodes.biasConfidence.value='low';nodes.biasFrom.value='2';nodes.biasUntil.value='11';nodes.biasEvidence.value='1';nodes.biasNote.value='<img src=x onerror=alert(1)>';
 nodes.biasSave.onclick();
 assert.match(nodes.biasMessage.textContent,/已保存/);assert.match(nodes.biasPreviews.innerHTML,/7號換2號/);
 assert.ok(!nodes.biasHistory.innerHTML.includes('<img'));assert.match(nodes.biasHistory.innerHTML,/&lt;img/);
 assert.equal(JSON.parse(storage.data).length,1);
 await nodes.biasPreviews.onclick({target:{closest:()=>({dataset:{biasCopy:'2'}})}});
 assert.match(sandbox.copied,/非原Telegram/);assert.match(sandbox.copied,/4、5、6、2/);
 nodes.biasConfidence.value='high';nodes.biasSave.onclick();assert.match(nodes.biasMessage.textContent,/只有一場/);assert.equal(JSON.parse(storage.data).length,1);
 nodes.biasConfidence.value='low';nodes.biasEvidence.value='2';nodes.biasFrom.value='3';nodes.biasSave.onclick();assert.match(nodes.biasMessage.textContent,/尚未有已公布/);
 nodes.biasEvidence.value='1';nodes.biasFrom.value='2';nodes.biasResetReason.value='watering';nodes.biasReset.onclick();assert.match(nodes.biasPreviews.innerHTML,/已重設為未知/);assert.ok(!nodes.biasPreviews.innerHTML.includes('data-bias-copy'));
 nodes.biasFrom.value='3';nodes.biasSave.onclick();assert.match(nodes.biasMessage.textContent,/請使用重設場次/);
 // Importing an old predeadline timestamp must produce a new current edit.
 const old=JSON.parse(storage.data)[0];old.created_at='2020-01-01T00:00:00Z';const target={files:[{size:100,text:async()=>JSON.stringify({version:1,events:[old]})}],value:'file'};
 await nodes.biasImport.onchange({target});assert.ok(Date.parse(JSON.parse(storage.data).at(-1).created_at)>=now);assert.equal(target.value,'');
 assert.ok(!Bias.active(JSON.parse(storage.data),{...tip,freeze:'2020-01-02T00:00:00Z',received_at:'2020-01-01T00:00:00Z'},{...contexts[2],prepared_at:'2020-01-01T00:00:00Z'}));
 console.log('Track-bias editor save, copy, reset, evidence, escaping and import-clock checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
