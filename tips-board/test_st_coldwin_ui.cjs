const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname,storage=new Map();let instant='2026-10-21T12:00:00+08:00';
class Clock extends Date{constructor(...args){super(...(args.length?args:[instant]))}static now(){return Date.parse(instant)}}
const date='2026-10-21',horses=Array.from({length:14},(_,i)=>({no:i+1,name:'馬'+(i+1)})),absent={status:'absent',horses:[]};
const race={date,venue:'ST',track:'TURF',race:1,score:0,off:date+'T13:00:00+08:00',horses,locked:false,result:null,tips:{meiji:{status:'ready',horses:horses.slice(0,4)},ball:absent,ma:absent,computer:absent},index:{status:'disabled',horses:[]},banker_initial:{status:'ready',date,race:1,venue:'ST',as_of_race_no:0,reason:'initial',numbers:[5,6,7,8,9]},selection:{method:'st-d-qqp-20261015',horses:[horses[0],horses[4],horses[1]],main:['QP'],optional:[]}};
race.st_win_support={method:'st-turf-coldwin-v1',status:'ready',date,race:1,venue:'ST',authors:Object.fromEntries(['西門獨','諸葛數','陳志懷','兆文'].map((a,i)=>[a,{status:'ready',numbers:[[10,11,12,13],[10,12,14,1],[12,10,11,1],[11,14,10,1]][i]}])),forms:Object.fromEntries([10,11,12,13,14].map(no=>[no,{status:'ready',last_date:no<12||no===13?'2026-07-01':'2026-10-01',last_finish:no===14?4:2,style_n:3,median:7}]))};
const source={date,venue:'ST',status:'upcoming',updated_at:instant,tips_checked_at:instant,races:[race]};
async function open(history=false){
 const els={},cache=new Map(),events={},requests=[];let poll,revision='a'.repeat(40);
 const el=id=>els[id]??={textContent:'',value:'',hidden:false,disabled:false,_html:'',set innerHTML(s){this._html=s;if(id==='dates')this.value=s.match(/value="([^"]+)/)?.[1]||'';if(id==='st-win-rows')for(const m of s.matchAll(/<input id="([^"]+)"[^>]*value="([^"]*)"/g))el(m[1]).value=m[2]},get innerHTML(){return this._html}};
 const ctx=vm.createContext({document:{addEventListener:(name,fn)=>events['document:'+name]=fn,body:{dataset:history?{history:'true'}:{}},getElementById:el,activeElement:null},window:{open(){},addEventListener:(name,fn)=>events['window:'+name]=fn},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},AbortController,setTimeout,clearTimeout,structuredClone,Date:Clock,Intl,setInterval:f=>{poll=f},fetch:async url=>{requests.push(url);return {ok:true,json:async()=>url.includes('/git/refs/')?{object:{sha:revision}}:url.includes('history.json')?{meetings:history?[{date,venue:'ST'}]:[]}:structuredClone(source)}}});
 const mod=spec=>{const f=spec.split('?')[0];if(!cache.has(f))cache.set(f,new vm.SourceTextModule(fs.readFileSync(path.join(root,f),'utf8'),{context:ctx}));return cache.get(f)};const main=mod('app.mjs');await main.link(mod);await main.evaluate();return{el,poll,events,requests,setRevision:value=>revision=value};
}
(async()=>{
 let app=await open();assert(app.el('st-win-rows').innerHTML.includes('馬10'));assert(app.el('st-win-rows').innerHTML.includes('待確認全部候選賠率'));
 for(const [no,odd] of Object.entries({10:8,11:15,12:9,13:20}))app.el('st-odd-1-'+no).value=String(odd);
 app.el('st-win-form').onsubmit({preventDefault(){}});let saved=JSON.parse(storage.get('hkjc-st-win-odds-v1:'+date+':1'));assert.deepEqual(saved.plan.picks.map(h=>h.no),[11,12]);assert(app.el('confidence-rows').innerHTML.includes('沙草補Win｜每匹 $10 W'));
 await app.poll();app=await open();assert.equal(app.el('st-odd-1-11').value,'15');
 instant='2026-10-21T13:01:00+08:00';source.races[0].st_win_support.authors['西門獨'].numbers=[13,14,1,2];
 await app.poll();assert(app.el('st-win-rows').innerHTML.includes('已鎖定賽前確認'));assert.equal(app.el('st-win-save').hidden,true);
 const before=storage.get('hkjc-st-win-odds-v1:'+date+':1');app.el('st-odd-1-11').value='1';app.el('st-win-form').onsubmit({preventDefault(){}});assert.equal(storage.get('hkjc-st-win-odds-v1:'+date+':1'),before,'post-off edit is rejected');
 const past=await open(true);assert(past.el('st-win-rows').innerHTML.includes('已鎖定賽前確認'));
 const selected=past.el('dates').value;past.setRevision('b'.repeat(40));
 await past.events['window:pageshow']();
 assert.equal(past.el('dates').value,selected,'restoring history keeps the chosen date');
 assert(past.requests.some(u=>u.includes('/'+'b'.repeat(40)+'/records/'+selected+'.json')),'history refreshes to the latest commit after phone tab restoration');
 assert.equal(storage.get('hkjc-st-win-odds-v1:'+date+':1'),before,'refresh preserves local pre-off receipts');
 console.log('PASS: latest/history render, manual prices persist across polling/reload, strict >8 selects two, pre-off receipt freezes after off.');
})().catch(e=>{console.error(e);process.exitCode=1});
