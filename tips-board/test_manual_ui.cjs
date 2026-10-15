const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname,source=JSON.parse(fs.readFileSync(path.join(root,'data/latest.json'))),storage=new Map();
class Clock extends Date{constructor(...args){super(...(args.length?args:['2026-10-13T21:00:00+08:00']))}static now(){return Date.parse('2026-10-13T21:00:00+08:00')}}
async function open(){
 const elements={};let poll;
 function el(id){return elements[id]??={textContent:'',value:'',disabled:false,hidden:false,_html:'',scrollIntoView(){},querySelector(){return el('submit')},set innerHTML(s){this._html=s;
  if(id==='manual-race')this.value=s.match(/value="([^"]+)/)?.[1]||'';
  if(id==='manual-inputs'){
   for(const match of s.matchAll(/<select id="(mode-[^"]+)"[^>]*>(.*?)<\/select>/g)){const opts=[...match[2].matchAll(/<option value="([^"]+)"([^>]*)>/g)];el(match[1]).value=(opts.find(x=>x[2].includes('selected'))||opts[0])[1]}
   for(const match of s.matchAll(/<input id="(input-[^"]+)"[^>]*value="([^"]*)"/g))el(match[1]).value=match[2];
  }
 },get innerHTML(){return this._html}}}
 const ctx=vm.createContext({document:{body:{dataset:{}},getElementById:el},window:{open(){}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},structuredClone,Date:Clock,Intl,setInterval:f=>{poll=f},fetch:async url=>({ok:true,json:async()=>url.includes('/git/refs/')?{object:{sha:'a'.repeat(40)}}:structuredClone(source)})});
 const main=new vm.SourceTextModule(fs.readFileSync(path.join(root,'app.mjs'),'utf8'),{context:ctx});
 await main.link(spec=>new vm.SourceTextModule(fs.readFileSync(path.join(root,spec.split('?')[0]),'utf8'),{context:ctx}));await main.evaluate();return{el,poll};
}
(async()=>{
 let app=await open();app.el('manual-open').onclick();assert.equal(app.el('manual-panel').hidden,false);
 const nos=source.races[0].horses.slice(0,4).map(h=>h.no).join(',');
 for(const k of ['ball','ma','computer'])app.el('mode-'+k).value='absent';
 app.el('mode-index').value='manual';app.el('input-index').value=nos;app.el('mode-index').onchange();
 assert(app.el('preview-index').textContent.includes(source.races[0].horses[0].name));
 app.el('manual-form').onsubmit({preventDefault(){}});assert(app.el('manual-message').textContent.includes('已保存'));
 assert(app.el('rows').innerHTML.includes('manual-badge'));assert(app.el('rows').innerHTML.includes('獨贏W '+nos.split(',').slice(0,2).join('、')));
 const saved=[...storage.values()][0];app.el('input-index').value='1,1,1,1';app.el('manual-form').onsubmit({preventDefault(){}});assert(app.el('manual-message').textContent.includes('重覆'));assert.equal([...storage.values()][0],saved);
 await app.poll();assert(app.el('rows').innerHTML.includes('manual-badge'));await app.el('refresh').onclick();assert(app.el('rows').innerHTML.includes('manual-badge'));
 app=await open();assert(app.el('rows').innerHTML.includes('manual-badge'),'Reload restores storage');app.el('manual-open').onclick();assert.equal(app.el('mode-index').value,'manual');
 app.el('manual-reset').onclick();assert(!app.el('rows').innerHTML.includes('manual-badge'));assert(app.el('manual-message').textContent.includes('已恢復'));
 console.log('PASS: editor, name preview, save, invalid edit, polling, refresh, reload and restore');
})().catch(e=>{console.error(e);process.exitCode=1});
