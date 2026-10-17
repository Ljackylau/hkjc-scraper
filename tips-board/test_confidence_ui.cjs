const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname,hs=[1,2,3,4].map(no=>({no,name:'馬'+no}));
const tip={status:'ready',horses:hs},absent={status:'absent',horses:[]};
const result={horses:hs.slice(0,3).map((h,i)=>({...h,placing:String(i+1)})),dividends:{W:[{combination:'1',dividend_hkd:40}],P:[{combination:'1',dividend_hkd:20}],QP:[{combination:'1,2',dividend_hkd:50}]}};
const race=(race,score)=>({race,score,off:'2026-10-14T19:00:00+08:00',horses:hs,tips:{meiji:tip,ball:tip,ma:absent,computer:absent},index:{status:'disabled',horses:[]},locked:true,result,selection:{horses:hs.slice(0,score<2?2:3),main:score<2?['W','P']:['QP'],optional:[]}});
const source={date:'2026-10-14',venue:'HV',status:'archived',updated_at:'2026-10-14T23:00:00+08:00',tips_checked_at:'2026-10-14T16:00:00+08:00',races:[race(1,0),race(2,1),race(3,2)]};
const sept={...source,date:'2026-09-09',races:[{...race(1,1),result:null}]};
async function open(history=false,fail=false,rateLimited=false){
 const els={},cache=new Map();
 const el=id=>els[id]??={textContent:'',value:'',hidden:false,disabled:false,_html:'',set innerHTML(s){this._html=s;if(id==='dates')this.value=s.match(/value="([^"]+)/)?.[1]||''},get innerHTML(){return this._html}};
 const ctx=vm.createContext({document:{body:{dataset:history?{history:'true'}:{}},getElementById:el},window:{open(){}},localStorage:{getItem(){return null}},structuredClone,Date,Intl,setInterval(){},fetch:async url=>{
  if(url.includes('/git/refs/')&&rateLimited)return{ok:false,status:403};
  if(url.includes('2026-09-09.json')&&fail)throw Error('offline');
  return{ok:true,json:async()=>url.includes('/git/refs/')?{object:{sha:'a'.repeat(40)}}:url.includes('history.json')?{meetings:[{date:source.date,venue:'HV'},{date:sept.date,venue:'HV'}]}:structuredClone(url.includes('2026-09-09.json')?sept:source)};
 }});
 const mod=spec=>{const f=spec.split('?')[0];if(!cache.has(f))cache.set(f,new vm.SourceTextModule(fs.readFileSync(path.join(root,f),'utf8'),{context:ctx}));return cache.get(f)};
 const main=mod('app.mjs');await main.link(mod);await main.evaluate();return{el,recover(){fail=false}};
}
(async()=>{
 for(const history of [false,true]){
  const app=await open(history),html=app.el('confidence-rows').innerHTML;
  assert(!html.includes('第1場'));assert(html.includes('第2場')&&html.includes('第3場'));assert(html.includes('位置P')&&html.includes('位置Q')&&html.includes('有中'));
  const month=app.el('monthly-rows').innerHTML;assert(month.includes('2026-10')&&month.includes('2026-09')&&month.includes('100.0%'));assert(month.includes('待核對'));assert(!app.el('monthly-status').textContent.includes('正在'));
  if(history){app.el('dates').value='2026-09-09';await app.el('dates').onchange();assert(app.el('confidence-rows').innerHTML.includes('第1場'));assert(app.el('monthly-rows').innerHTML.includes('2026-10'),'monthly stats include all history, independent of selected date')}
 }
 const limited=await open(true,false,true);assert(limited.el('revision-notice').textContent.includes('備用存檔'));assert(limited.el('confidence-rows').innerHTML.includes('第2場'));assert(limited.el('monthly-rows').innerHTML.includes('100.0%'));
 const app=await open(false,true);assert(app.el('monthly-rows').innerHTML.includes('命中率暫不顯示'));app.recover();await app.el('refresh').onclick();assert(app.el('monthly-rows').innerHTML.includes('100.0%'));
 console.log('PASS: both pages filter confidence races, show bets/results, aggregate all months, switch dates and recover from incomplete history');
})().catch(e=>{console.error(e);process.exitCode=1});
